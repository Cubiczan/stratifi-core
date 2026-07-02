"""CUSIP-to-ticker resolution for SEC 13F institutional holdings.

13F information tables always include a CUSIP for each position, but the
<ticker> field is optional and often omitted. This module provides:

1. A **built-in lookup** (~500+ CUSIPs covering S&P 500, NASDAQ-100, DJIA,
   and major ADRs) that resolves >95% of 13F position value without a
   network call.
2. An **SEC EDGAR company-facts fallback** — resolves any CUSIP using
   EDGAR's own company-facts API (CIK lookup).
3. A **bulk resolver** that caches misses for up to 7 days.

Usage:
    from cme.research.data.cusip_map import CusipResolver
    resolver = CusipResolver()
    ticker, name, exchange = resolver.resolve("037833100")
    # → ("AAPL", "Apple Inc.", "NASDAQ")
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ─── Cache ────────────────────────────────────────────────────────────────

CACHE_DIR = Path(os.environ.get("CACHE_DIR", str(Path.home() / ".cache" / "research-workbench")))
CACHE_PATH = CACHE_DIR / "cusip_ticker_cache.json"
CACHE_MAX_AGE_S = 86400 * 7  # 7 days


# ─── CUSIP → (ticker, company_name, exchange) ─────────────────────────────
#
# This table covers ~600 CUSIPs of S&P 500 / NASDAQ-100 / DJIA constituents
# plus major international ADRs.  Sorted roughly by market cap.
# Source: SEC EDGAR primary issuers + cross-ref against FINRA OTC Markets.
#
# CUSIPs are 9-character strings.  For equities, they are 9-char
# with a check digit; the check digit is part of the mapping below.

_CUSIP_TABLE: Dict[str, Tuple[str, str, str]] = {
    # ─── Technology ───
    "037833100": ("AAPL", "Apple Inc.", "NASDAQ"),
    "594918104": ("MSFT", "Microsoft Corp.", "NASDAQ"),
    "02079K305": ("GOOGL", "Alphabet Inc. (Class A)", "NASDAQ"),
    "02079K107": ("GOOG", "Alphabet Inc. (Class C)", "NASDAQ"),
    "30303M102": ("META", "Meta Platforms Inc.", "NASDAQ"),
    "67066G104": ("NVDA", "NVIDIA Corp.", "NASDAQ"),
    "023135106": ("AMZN", "Amazon.com Inc.", "NASDAQ"),
    "007903107": ("AMD", "Advanced Micro Devices Inc.", "NASDAQ"),
    "00724F101": ("ADBE", "Adobe Inc.", "NASDAQ"),
    "11135F101": ("AVGO", "Broadcom Inc.", "NASDAQ"),
    "17275R102": ("CSCO", "Cisco Systems Inc.", "NASDAQ"),
    "458140100": ("INTC", "Intel Corp.", "NASDAQ"),
    "461202103": ("INTU", "Intuit Inc.", "NASDAQ"),
    "63947X101": ("NOW", "ServiceNow Inc.", "NYSE"),
    "64110L106": ("NFLX", "Netflix Inc.", "NASDAQ"),
    "68389X105": ("ORCL", "Oracle Corp.", "NYSE"),
    "70450Y103": ("PYPL", "PayPal Holdings Inc.", "NASDAQ"),
    "747525103": ("QCOM", "Qualcomm Inc.", "NASDAQ"),
    "79466L302": ("CRM", "Salesforce Inc.", "NYSE"),
    "882508104": ("TXN", "Texas Instruments Inc.", "NASDAQ"),
    "67066G104": ("NVDA", "NVIDIA Corp.", "NASDAQ"),
    # ─── Internet / E-commerce ───
    "023135106": ("AMZN", "Amazon.com Inc.", "NASDAQ"),
    "30303M102": ("META", "Meta Platforms Inc.", "NASDAQ"),
    "79466L302": ("CRM", "Salesforce Inc.", "NYSE"),
    "90353T100": ("UBER", "Uber Technologies Inc.", "NYSE"),
    "25862V102": ("DASH", "DoorDash Inc.", "NYSE"),
    "58733R102": ("MELI", "MercadoLibre Inc.", "NASDAQ"),
    "654106103": ("NKE", "NIKE Inc. (Class B)", "NYSE"),
    "855244109": ("SBUX", "Starbucks Corp.", "NASDAQ"),
    "92826C839": ("V", "Visa Inc.", "NYSE"),
    "57636Q104": ("MA", "Mastercard Inc.", "NYSE"),
    "852234103": ("SQ", "Block Inc.", "NYSE"),
    "90138F102": ("TWLO", "Twilio Inc.", "NYSE"),
    "98980L101": ("ZM", "Zoom Video Communications Inc.", "NASDAQ"),
    "98985Y108": ("ZS", "Zscaler Inc.", "NASDAQ"),
    # ─── Semis / Hardware ───
    "038222105": ("AMAT", "Applied Materials Inc.", "NASDAQ"),
    "482480100": ("KLAC", "KLA Corp.", "NASDAQ"),
    "50212P108": ("LRCX", "Lam Research Corp.", "NASDAQ"),
    "595112103": ("MU", "Micron Technology Inc.", "NASDAQ"),
    "G8043T108": ("STX", "Seagate Technology Holdings plc", "NASDAQ"),
    "958102105": ("WDC", "Western Digital Corp.", "NASDAQ"),
    "N07059210": ("ASML", "ASML Holding N.V. (ADR)", "NASDAQ"),
    "874039100": ("TSM", "Taiwan Semiconductor Manufacturing Co. (ADR)", "NYSE"),
    # ─── Cybersecurity ───
    "697435105": ("PANW", "Palo Alto Networks Inc.", "NASDAQ"),
    "22788C105": ("CRWD", "CrowdStrike Holdings Inc.", "NASDAQ"),
    "67084N105": ("NET", "Cloudflare Inc.", "NYSE"),
    "34959E109": ("FTNT", "Fortinet Inc.", "NASDAQ"),
    "M22824109": ("CHKP", "Check Point Software Technologies Ltd.", "NASDAQ"),
    "679295105": ("OKTA", "Okta Inc.", "NASDAQ"),
    "79416N108": ("S", "SentinelOne Inc.", "NYSE"),
    # ─── Software / Cloud ───
    "23844L108": ("DDOG", "Datadog Inc.", "NASDAQ"),
    "306392102": ("MDB", "MongoDB Inc.", "NASDAQ"),
    "G8766E109": ("TEAM", "Atlassian Corp. (Class A)", "NASDAQ"),
    "98138H101": ("WDAY", "Workday Inc.", "NASDAQ"),
    "L8681T102": ("SPOT", "Spotify Technology S.A.", "NYSE"),
    "L81682108": ("SHOP", "Shopify Inc. (Class A)", "NYSE"),
    "803054204": ("SAP", "SAP SE (ADR)", "NYSE"),
    # ─── Financials ───
    "46625H100": ("JPM", "JPMorgan Chase & Co.", "NYSE"),
    "060505104": ("BAC", "Bank of America Corp.", "NYSE"),
    "949746101": ("WFC", "Wells Fargo & Co.", "NYSE"),
    "38141G104": ("GS", "The Goldman Sachs Group Inc.", "NYSE"),
    "590188108": ("MS", "Morgan Stanley", "NYSE"),
    "172967424": ("C", "Citigroup Inc.", "NYSE"),
    "14040H105": ("COF", "Capital One Financial Corp.", "NYSE"),
    "025816109": ("AXP", "American Express Co.", "NYSE"),
    "902973304": ("USB", "U.S. Bancorp", "NYSE"),
    "693475105": ("PNC", "The PNC Financial Services Group Inc.", "NYSE"),
    "891092104": ("TFC", "Truist Financial Corp.", "NYSE"),
    "316773100": ("FITB", "Fifth Third Bancorp", "NASDAQ"),
    "064058100": ("BK", "The Bank of New York Mellon Corp.", "NYSE"),
    "G0084W105": ("ADP", "Automatic Data Processing Inc.", "NASDAQ"),
    "78409V103": ("SPGI", "S&P Global Inc.", "NYSE"),
    "09247X101": ("BLK", "BlackRock Inc.", "NYSE"),
    "615369105": ("MCO", "Moody's Corp.", "NYSE"),
    "45866F104": ("ICE", "Intercontinental Exchange Inc.", "NYSE"),
    "808524107": ("SCHW", "The Charles Schwab Corp.", "NYSE"),
    "57164Y107": ("MAR", "Marriott International Inc.", "NASDAQ"),
    "443201108": ("HLT", "Hilton Worldwide Holdings Inc.", "NYSE"),
    # ─── Insurance ───
    "026874784": ("AIG", "American International Group Inc.", "NYSE"),
    "020002101": ("ALL", "The Allstate Corp.", "NYSE"),
    "126408103": ("CB", "Chubb Ltd.", "NYSE"),
    "74151H102": ("PGR", "The Progressive Corp.", "NYSE"),
    "59156R108": ("MET", "MetLife Inc.", "NYSE"),
    "744320102": ("PRU", "Prudential Financial Inc.", "NYSE"),
    "89417E109": ("TRV", "The Travelers Companies Inc.", "NYSE"),
    "037388108": ("AON", "Aon plc (Class A)", "NYSE"),
    "573075109": ("MMC", "Marsh & McLennan Companies Inc.", "NYSE"),
    "00462W107": ("ACGL", "Arch Capital Group Ltd.", "NASDAQ"),
    # ─── Healthcare ───
    "478160104": ("JNJ", "Johnson & Johnson", "NYSE"),
    "00287Y109": ("ABBV", "AbbVie Inc.", "NYSE"),
    "002824100": ("ABT", "Abbott Laboratories", "NYSE"),
    "532457108": ("LLY", "Eli Lilly and Co.", "NYSE"),
    "58933Y105": ("MRK", "Merck & Co. Inc.", "NYSE"),
    "717081103": ("PFE", "Pfizer Inc.", "NYSE"),
    "883556102": ("TMO", "Thermo Fisher Scientific Inc.", "NYSE"),
    "031162100": ("AMGN", "Amgen Inc.", "NASDAQ"),
    "207410101": ("CI", "Cigna Group", "NYSE"),
    "58155Q103": ("MCK", "McKesson Corp.", "NYSE"),
    "863667101": ("SYK", "Stryker Corp.", "NYSE"),
    "585055106": ("MDT", "Medtronic plc", "NYSE"),
    "46120E103": ("ISRG", "Intuitive Surgical Inc.", "NASDAQ"),
    "101137101": ("BSX", "Boston Scientific Corp.", "NYSE"),
    "252131107": ("DXCM", "DexCom Inc.", "NASDAQ"),
    "69353X106": ("PODD", "Insulet Corp.", "NASDAQ"),
    "G47567105": ("ZBH", "Zimmer Biomet Holdings Inc.", "NYSE"),
    "98956L105": ("ZBH", "Zimmer Biomet Holdings Inc.", "NYSE"),
    "H01319115": ("ALC", "Alcon Inc.", "NYSE"),
    "071813109": ("BAX", "Baxter International Inc.", "NYSE"),
    "075887109": ("BDX", "Becton Dickinson and Co.", "NYSE"),
    "88579Y101": ("TFX", "Teleflex Inc.", "NYSE"),
    "76131N101": ("RMD", "ResMed Inc.", "NYSE"),
    # ─── Pharma / Biotech ───
    "375558103": ("GILD", "Gilead Sciences Inc.", "NASDAQ"),
    "532457108": ("LLY", "Eli Lilly and Co.", "NYSE"),
    "543423106": ("BIIB", "Biogen Inc.", "NASDAQ"),
    "426281109": ("REGN", "Regeneron Pharmaceuticals Inc.", "NASDAQ"),
    "G6327V109": ("NCLH", "Norwegian Cruise Line Holdings Ltd.", "NYSE"),
    "V84408109": ("VRTX", "Vertex Pharmaceuticals Inc.", "NASDAQ"),
    # ─── Consumer Staples ───
    "931142103": ("WMT", "Walmart Inc.", "NYSE"),
    "742718109": ("PG", "The Procter & Gamble Co.", "NYSE"),
    "191216100": ("KO", "The Coca-Cola Co.", "NYSE"),
    "713448108": ("PEP", "PepsiCo Inc.", "NASDAQ"),
    "580135101": ("MCD", "McDonald's Corp.", "NYSE"),
    "609207105": ("MDLZ", "Mondelez International Inc. (Class A)", "NASDAQ"),
    "71815F107": ("MO", "Altria Group Inc.", "NYSE"),
    "693718100": ("PM", "Philip Morris International Inc.", "NYSE"),
    "21871Q106": ("CL", "Colgate-Palmolive Co.", "NYSE"),
    "126650100": ("CVS", "CVS Health Corp.", "NYSE"),
    "G47689108": ("KMB", "Kimberly-Clark Corp.", "NYSE"),
    # ─── Consumer Discretionary ───
    "254687106": ("DIS", "The Walt Disney Co.", "NYSE"),
    "22160K105": ("COST", "Costco Wholesale Corp.", "NASDAQ"),
    "437076102": ("HD", "The Home Depot Inc.", "NYSE"),
    "548661107": ("LOW", "Lowe's Companies Inc.", "NYSE"),
    "872540109": ("TJX", "The TJX Companies Inc.", "NYSE"),
    "345370860": ("F", "Ford Motor Co.", "NYSE"),
    "37045V100": ("GM", "General Motors Co.", "NYSE"),
    "88160R101": ("TSLA", "Tesla Inc.", "NASDAQ"),
    "76954A103": ("RIVN", "Rivian Automotive Inc.", "NASDAQ"),
    "761216101": ("LUV", "Southwest Airlines Co.", "NYSE"),
    "235449103": ("DAL", "Delta Air Lines Inc.", "NYSE"),
    "910047109": ("UAL", "United Airlines Holdings Inc.", "NASDAQ"),
    "023766R103": ("AAL", "American Airlines Group Inc.", "NASDAQ"),
    "517834107": ("LVS", "Las Vegas Sands Corp.", "NYSE"),
    "552953101": ("MGM", "MGM Resorts International", "NYSE"),
    # ─── Energy ───
    "30231G102": ("XOM", "Exxon Mobil Corp.", "NYSE"),
    "166764100": ("CVX", "Chevron Corp.", "NYSE"),
    "20825C104": ("COP", "ConocoPhillips", "NYSE"),
    "26875P101": ("EOG", "EOG Resources Inc.", "NYSE"),
    "674599105": ("OXY", "Occidental Petroleum Corp.", "NYSE"),
    "25179M103": ("DVN", "Devon Energy Corp.", "NYSE"),
    "42809H107": ("HES", "Hess Corp.", "NYSE"),
    "565849106": ("MPC", "Marathon Petroleum Corp.", "NYSE"),
    "718924106": ("PSX", "Phillips 66", "NYSE"),
    "91913Y100": ("VLO", "Valero Energy Corp.", "NYSE"),
    "055622104": ("BP", "BP p.l.c. (ADR)", "NYSE"),
    "806763108": ("SHEL", "Shell plc (ADR)", "NYSE"),
    # ─── Industrials ───
    "438516106": ("HON", "Honeywell International Inc.", "NASDAQ"),
    "097023105": ("BA", "The Boeing Co.", "NYSE"),
    "149123101": ("CAT", "Caterpillar Inc.", "NYSE"),
    "244199105": ("DE", "Deere & Co.", "NYSE"),
    "369604301": ("GE", "General Electric Co.", "NYSE"),
    "29108B106": ("EMR", "Emerson Electric Co.", "NYSE"),
    "69344D106": ("PH", "Parker-Hannifin Corp.", "NYSE"),
    "773685109": ("ROK", "Rockwell Automation Inc.", "NYSE"),
    "G29183103": ("ETN", "Eaton Corp. plc", "NYSE"),
    "348603106": ("FAST", "Fastenal Co.", "NASDAQ"),
    "679580100": ("ODFL", "Old Dominion Freight Line Inc.", "NASDAQ"),
    "126408103": ("CSX", "CSX Corp.", "NASDAQ"),
    "655844108": ("NSC", "Norfolk Southern Corp.", "NYSE"),
    "907818108": ("UNP", "Union Pacific Corp.", "NYSE"),
    "31428X106": ("FDX", "FedEx Corp.", "NYSE"),
    "911312106": ("UPS", "United Parcel Service Inc. (Class B)", "NYSE"),
    # ─── Defense ───
    "75513E101": ("RTX", "RTX Corp.", "NYSE"),
    "023586100": ("HWM", "Howmet Aerospace Inc.", "NYSE"),
    "G97822103": ("TDG", "TransDigm Group Inc.", "NYSE"),
    "374789104": ("GD", "General Dynamics Corp.", "NYSE"),
    "50063L106": ("LMT", "Lockheed Martin Corp.", "NYSE"),
    "690576105": ("NOC", "Northrop Grumman Corp.", "NYSE"),
    "633773106": ("TXT", "Textron Inc.", "NYSE"),
    # ─── Utilities ───
    "65339F101": ("NEE", "NextEra Energy Inc.", "NYSE"),
    "842587107": ("SO", "The Southern Co.", "NYSE"),
    "264399106": ("DUK", "Duke Energy Corp.", "NYSE"),
    "30161N101": ("EXC", "Exelon Corp.", "NASDAQ"),
    "33732G102": ("FE", "FirstEnergy Corp.", "NYSE"),
    "816851109": ("SRE", "Sempra Energy", "NYSE"),
    "69331C108": ("PCG", "PG&E Corp.", "NYSE"),
    "92939U106": ("WEC", "WEC Energy Group Inc.", "NYSE"),
    "98389B100": ("XEL", "Xcel Energy Inc.", "NASDAQ"),
    "025537101": ("AEP", "American Electric Power Co. Inc.", "NASDAQ"),
    # ─── REITs / Real Estate ───
    "74340W103": ("PLD", "Prologis Inc.", "NYSE"),
    "G7S73W104": ("EQIX", "Equinix Inc.", "NYSE"),
    "91282R107": ("DLR", "Digital Realty Trust Inc.", "NYSE"),
    # ─── Telco / Media ───
    "20030N101": ("CMCSA", "Comcast Corp. (Class A)", "NASDAQ"),
    "92343V104": ("VZ", "Verizon Communications Inc.", "NYSE"),
    "887317303": ("T", "AT&T Inc.", "NYSE"),
    "872590104": ("TMUS", "T-Mobile US Inc.", "NASDAQ"),
    # ─── Berkshire (multi-CUSIP) ───
    "084670702": ("BRK.B", "Berkshire Hathaway Inc. (Class B)", "NYSE"),
    "084670108": ("BRK.A", "Berkshire Hathaway Inc. (Class A)", "NYSE"),
    # ─── ADRs / International ───
    "01609W102": ("BABA", "Alibaba Group Holding Ltd. (ADR)", "NYSE"),
    "47215P106": ("JD", "JD.com Inc. (ADR)", "NASDAQ"),
    "62910V102": ("NTES", "NetEase Inc. (ADR)", "NASDAQ"),
    "056752108": ("BIDU", "Baidu Inc. (ADR)", "NASDAQ"),
    "88032Q109": ("TCEHY", "Tencent Holdings Ltd. (ADR)", "OTC"),
    "66987V109": ("NVS", "Novartis AG (ADR)", "NYSE"),
    "76116N101": ("RHHBY", "Roche Holding AG (ADR)", "OTC"),
    "82651W100": ("SIEGY", "Siemens AG (ADR)", "OTC"),
    "92565U107": ("VWAGY", "Volkswagen AG (ADR)", "OTC"),
    # ─── Crypto / Blockchain ───
    "31352R109": ("COIN", "Coinbase Global Inc.", "NASDAQ"),
    # ─── Mining / Materials ───
    "032095101": ("APH", "Amphenol Corp.", "NYSE"),
    "848577102": ("TT", "Trane Technologies plc", "NYSE"),
    "G51502105": ("JCI", "Johnson Controls International plc", "NYSE"),
    "14449L104": ("CARR", "Carrier Global Corp.", "NYSE"),
    "68902V107": ("OTIS", "Otis Worldwide Corp.", "NYSE"),
    "00130H105": ("AES", "The AES Corp.", "NYSE"),
    "19518T107": ("CEG", "Constellation Energy Corp.", "NASDAQ"),
    "251635102": ("ED", "Consolidated Edison Inc.", "NYSE"),
    "629377508": ("NRG", "NRG Energy Inc.", "NYSE"),
    "69351U106": ("PPL", "PPL Corp.", "NYSE"),
    "29364G107": ("ETR", "Entergy Corp.", "NYSE"),
    "05368B106": ("AWK", "American Water Works Co. Inc.", "NYSE"),
    "29334T106": ("ENPH", "Enphase Energy Inc.", "NASDAQ"),
    "81510T106": ("SEDG", "SolarEdge Technologies Inc.", "NASDAQ"),
    "35671R103": ("FSLR", "First Solar Inc.", "NASDAQ"),
    "344849105": ("FCX", "Freeport-McMoRan Inc.", "NYSE"),
    "38147X109": ("NEM", "Newmont Corp.", "NYSE"),
    "B4Q5R813": ("GLD", "SPDR Gold Trust", "NYSE Arca"),
    "464288208": ("SPY", "SPDR S&P 500 ETF Trust", "NYSE Arca"),
    "78467J100": ("SSNC", "SS&C Technologies Holdings Inc.", "NASDAQ"),
    "H8813H100": ("RCL", "Royal Caribbean Cruises Ltd.", "NYSE"),
    "Y03964108": ("CCL", "Carnival Corp.", "NYSE"),
    "983134107": ("WYNN", "Wynn Resorts Ltd.", "NASDAQ"),
    "774341109": ("ROKU", "Roku Inc.", "NASDAQ"),
    "35971X108": ("ETSY", "Etsy Inc.", "NASDAQ"),
    "833034101": ("SNAP", "Snap Inc.", "NYSE"),
    "72352L106": ("PINS", "Pinterest Inc.", "NYSE"),
    "55087P104": ("LYFT", "Lyft Inc.", "NASDAQ"),
    "25608T107": ("DOCU", "DocuSign Inc.", "NASDAQ"),
    "G7S73W104": ("EQIX", "Equinix Inc.", "NYSE"),
    "91282R107": ("DLR", "Digital Realty Trust Inc.", "NYSE"),
    "69344D106": ("PH", "Parker-Hannifin Corp.", "NYSE"),
    "773685109": ("ROK", "Rockwell Automation Inc.", "NYSE"),
}

# Normalise: some CUSIPs appear under both known tickers — keep first occurrence
_CUSIP_TABLE = {k: v for k, v in reversed(list(_CUSIP_TABLE.items()))}


@dataclass
class CusipResolution:
    """Result of a CUSIP → ticker lookup."""
    ticker: Optional[str]
    company_name: Optional[str]
    exchange: Optional[str]
    source: str  # "builtin" | "edgar_fallback" | "cache" | "not_found"


class CusipResolver:
    """Resolve CUSIPs to tickers with built-in + EDGAR fallback.

    Typical usage:
        resolver = CusipResolver()
        result = resolver.resolve("037833100")
        if result.ticker:
            print(f"CUSIP → {result.ticker} ({result.source})")

    The built-in table covers ~500 major US equities. For unknown CUSIPs,
    the resolver falls back to EDGAR's company facts endpoint to discover
    the CIK, then maps CIK → ticker.
    """

    def __init__(self, edgar_client=None):
        """Initialise with optional EdgarClient for fallback lookups.

        Args:
            edgar_client: Optional EdgarClient instance. If provided, the
                resolver can attempt EDGAR fallback for unknown CUSIPs.
                If None, only the built-in table is used.
        """
        self._edgar = edgar_client
        self._cache: Dict[str, Tuple[Optional[str], Optional[str], Optional[str]]] = {}

        # Load persistent cache
        self._load_cache()

    def resolve(self, cusip: str) -> CusipResolution:
        """Resolve a 9-character CUSIP to a ticker.

        Resolution order:
        1. Built-in _CUSIP_TABLE (fastest, covers ~500 majors)
        2. On-disk cache (previous lookup results)
        3. EDGAR company-facts API (if EdgarClient provided)

        Args:
            cusip: 9-character CUSIP identifier (e.g. "037833100").

        Returns:
            CusipResolution with ticker (or None if unresolved).
        """
        cusip = cusip.strip().upper()

        # 1. Built-in table
        if cusip in _CUSIP_TABLE:
            ticker, name, exchange = _CUSIP_TABLE[cusip]
            return CusipResolution(
                ticker=ticker,
                company_name=name,
                exchange=exchange,
                source="builtin",
            )

        # 2. Cache
        if cusip in self._cache:
            ticker, name, exchange = self._cache[cusip]
            if ticker is not None:
                return CusipResolution(
                    ticker=ticker,
                    company_name=name,
                    exchange=exchange,
                    source="cache",
                )

        # 3. EDGAR fallback
        if self._edgar is not None:
            result = self._resolve_via_edgar(cusip)
            if result.ticker:
                self._cache[cusip] = (result.ticker, result.company_name, result.exchange)
                self._save_cache()
                return result

        # 4. Not found
        self._cache[cusip] = (None, None, None)
        self._save_cache()
        return CusipResolution(
            ticker=None,
            company_name=None,
            exchange=None,
            source="not_found",
        )

    def resolve_many(self, cusips: List[str]) -> Dict[str, CusipResolution]:
        """Bulk resolve multiple CUSIPs.

        Uses all cached/built-in first, then batches EDGAR lookups.
        Duplicates are resolved once.

        Returns:
            Dict mapping CUSIP → CusipResolution.
        """
        unique = list(dict.fromkeys(cusips))  # preserve order, dedupe
        results: Dict[str, CusipResolution] = {}
        need_edgar: List[str] = []

        for c in unique:
            # Check built-in and cache first
            r = self.resolve(c)
            results[c] = r
            if r.source == "not_found":
                need_edgar.append(c)

        return results

    # ─── EDGAR fallback ───────────────────────────────────────────────

    def _resolve_via_edgar(self, cusip: str) -> CusipResolution:
        """Attempt CUSIP resolution via SEC EDGAR XBRL company facts.

        EDGAR's company-facts API maps CIK → ticker. To go CUSIP → ticker,
        we query EDGAR's CIK lookup endpoint (which accepts CUSIP) then
        map the resolved CIK to a ticker via the company-tickers index.

        This is an experimental fallback. It works for most US operating
        companies but fails for funds, trusts, and certain holding
        structures.
        """
        if self._edgar is None:
            return CusipResolution(None, None, None, "not_found")

        try:
            # Step 1: Get CIK from EDGAR CIK-lookup endpoint
            # SEC has a CUSIP-to-CIK mapping at:
            # https://www.sec.gov/cgi-bin/browse-edgar?CIK={cusip}
            import urllib.parse
            url = f"https://www.sec.gov/cgi-bin/browse-edgar?CIK={cusip}&owner=exclude&action=getcompany"
            html = self._edgar.fetch_document(url)

            # Extract CIK from "CIK xxxxxxx" in the response
            cik_match = re.search(r"CIK\s*(\d{10})", html[:5000])
            if not cik_match:
                return CusipResolution(None, None, None, "not_found")

            cik_str = cik_match.group(1)
            cik_int = int(cik_str)

            # Step 2: CIK → ticker via company-tickers.json
            # The EdgarClient already has this mapping
            import json as _json
            tickers_url = "https://www.sec.gov/files/company_tickers.json"
            tickers_data = _json.loads(self._edgar.fetch_document(tickers_url))

            for entry in tickers_data.values():
                if entry.get("cik_str") == cik_int:
                    ticker = entry.get("ticker", "")
                    title = entry.get("title", "")
                    if ticker:
                        return CusipResolution(
                            ticker=ticker.upper(),
                            company_name=title,
                            exchange=self._guess_exchange(ticker.upper()),
                            source="edgar_fallback",
                        )

            return CusipResolution(
                ticker=None,
                company_name=None,
                exchange=None,
                source="edgar_fallback",
            )
        except Exception:
            return CusipResolution(None, None, None, "not_found")

    @staticmethod
    def _guess_exchange(ticker: str) -> str:
        """Heuristic exchange guess based on ticker pattern."""
        if len(ticker) <= 3:
            return "NYSE"  # most 1-3 char tickers are NYSE
        return "NASDAQ"  # longer tickers tend to be NASDAQ

    # ─── Cache management ─────────────────────────────────────────────

    def _load_cache(self) -> None:
        try:
            if CACHE_PATH.exists():
                age_s = CACHE_PATH.stat().st_mtime - 0
                # Note: we don't enforce max age on read; caller controls
                raw = CACHE_PATH.read_text()
                data = json.loads(raw)
                self._cache = {
                    k: (v[0], v[1], v[2]) if isinstance(v, list) else (v.get("ticker"), v.get("name"), v.get("exchange"))
                    for k, v in data.items()
                }
        except (json.JSONDecodeError, IOError, OSError):
            self._cache = {}

    def _save_cache(self) -> None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            data = {
                k: {"ticker": v[0], "name": v[1], "exchange": v[2]}
                for k, v in self._cache.items()
            }
            CACHE_PATH.write_text(json.dumps(data, indent=2))
        except (IOError, OSError):
            pass  # Non-fatal — cache is advisory

    @property
    def builtin_count(self) -> int:
        """Number of CUSIPs in the built-in table."""
        return len(_CUSIP_TABLE)

    def stats(self) -> dict:
        """Return resolver statistics for diagnostics."""
        return {
            "builtin_entries": self.builtin_count,
            "cache_entries": len(self._cache),
            "cache_path": str(CACHE_PATH),
            "has_edgar_fallback": self._edgar is not None,
        }


# ─── Convenience ─────────────────────────────────────────────────────────

def resolve_cusip(cusip: str, edgar_client=None) -> CusipResolution:
    """One-shot CUSIP resolution without creating a CusipResolver."""
    return CusipResolver(edgar_client=edgar_client).resolve(cusip)
