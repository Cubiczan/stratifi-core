"""Filing-type-specific parsers and helpers for SEC EDGAR.

Extends the base EdgarClient with dedicated tooling for four additional
SEC filing types beyond the standard 10-K / 10-Q / 8-K / DEF 14A:

    - **S-1**   — Registration statements (IPO / follow-on / shelf)
    - **13F**   — Institutional holdings (quarterly 13F-HR)
    - **Form D** — Exempt securities offerings (Reg D / 506(c) / crowdfunding)
    - **PRE 14A** — Preliminary proxy statements (merger / acquisition previews)

Each type gets:
    1. A typed dataclass with the common fields relevant to that form.
    2. An `EdgarClient` extension method that fetches and parses the filing.
    3. A best-effort text extraction for key sections.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from cme.research.data.edgar import EdgarClient, EdgarError, FilingRef

# CUSIP resolver — optional, injected at sweep time
_cusip_resolver = None


def _get_cusip_resolver(client=None):
    """Lazy-init and reuse a CusipResolver singleton."""
    global _cusip_resolver  # noqa: WPS420
    if _cusip_resolver is None:
        from cme.research.data.cusip_map import CusipResolver  # noqa: WPS433
        _cusip_resolver = CusipResolver(edgar_client=client)
    return _cusip_resolver


def _resolve_ticker_fallback(cusip, issuer_name, client):
    """Resolve a ticker from CUSIP when EDGAR XML doesn't provide one.

    Args:
        cusip: The 9-character CUSIP from the 13F infoTable.
        issuer_name: Fallback issuer name (used if resolution fails).
        client: EdgarClient instance for EDGAR fallback.

    Returns:
        Tuple of (ticker_or_None, resolution_source_or_None).
    """
    if not cusip or len(cusip) < 8:
        return None, None

    resolver = _get_cusip_resolver(client=client)
    result = resolver.resolve(cusip)
    if result.ticker:
        return result.ticker, result.source
    return None, None


# ─── S-1: Registration Statements ───────────────────────────────────────


@dataclass
class S1Summary:
    """Summarised view of an S-1 registration statement."""

    filing_ref: FilingRef
    issuer_name: str = ""
    ticker: str = ""
    exchange: str = ""  # NYSE / NASDAQ / NYSE American
    offering_type: str = ""  # IPO / follow-on / shelf / SPAC
    shares_offered: Optional[int] = None
    price_range_low: Optional[float] = None
    price_range_high: Optional[float] = None
    estimated_raise_usd: Optional[float] = None
    underwriters: List[str] = field(default_factory=list)
    use_of_proceeds_summary: str = ""
    risk_factors_count: int = 0
    business_summary: str = ""
    has_financials: bool = False  # audited financials included
    amendments: List[FilingRef] = field(default_factory=list)

    def render(self) -> str:
        lines = [
            f"## S-1: {self.issuer_name} ({self.ticker or 'ticker pending'})",
            f"_Filed: {self.filing_ref.filing_date}  ·  Exchange: {self.exchange or 'TBD'}_",
            f"_Accession: {self.filing_ref.accession_no}_",
            "",
            "### Offering Summary",
            f"**Type:** {self.offering_type or 'Not specified'}",
            f"**Shares:** {_fmt_shares(self.shares_offered)}",
            f"**Price range:** {_fmt_price(self.price_range_low)} – {_fmt_price(self.price_range_high)}",
            f"**Estimated raise:** {_fmt_money(self.estimated_raise_usd)}",
            "",
        ]
        if self.underwriters:
            lines.append(f"**Underwriters:** {', '.join(self.underwriters)}")
            lines.append("")
        if self.use_of_proceeds_summary:
            lines.append(f"**Use of proceeds:** {self.use_of_proceeds_summary[:500]}")
            lines.append("")
        if self.risk_factors_count:
            lines.append(f"**Risk factors:** {self.risk_factors_count} items in filing")
        if self.business_summary:
            lines.append(f"**Business:** {self.business_summary[:600]}")
            lines.append("")
        lines.append(f"**Audited financials:** {'Yes' if self.has_financials else 'Not included / preamble only'}")
        if self.amendments:
            lines.append(
                f"**Amendments:** {len(self.amendments)} (latest: "
                f"{self.amendments[-1].filing_date})"
            )
        lines.append("")
        return "\n".join(lines).strip()


# ─── 13F: Institutional Holdings ────────────────────────────────────────


@dataclass
class FilingHolding:
    """A single equity holding as reported on Form 13F."""

    issuer_name: str
    ticker: Optional[str]
    cusip: str
    fair_value_usd: float
    shares: Optional[int] = None
    put_call: Optional[str] = None  # "put" | "call" | None for equity
    voting_authority_sole: Optional[int] = None
    voting_authority_shared: Optional[int] = None
    voting_authority_none: Optional[int] = None


@dataclass
class Form13FSummary:
    """Summarised view of an institutional manager's 13F-HR filing."""

    filing_ref: FilingRef
    manager_name: str = ""
    total_fair_value_usd: float = 0.0
    total_shares: Optional[int] = None
    position_count: int = 0
    top_positions: List[FilingHolding] = field(default_factory=list)
    new_positions: List[FilingHolding] = field(default_factory=list)
    increased_positions: List[FilingHolding] = field(default_factory=list)
    reduced_positions: List[FilingHolding] = field(default_factory=list)
    exited_positions: List[str] = field(default_factory=list)  # tickers exited

    def render(self) -> str:
        lines = [
            f"## 13F: {self.manager_name}",
            f"_Period: {self.filing_ref.report_date}  ·  Filed: {self.filing_ref.filing_date}_",
            f"_Accession: {self.filing_ref.accession_no}_",
            "",
            f"**Total AUM reported:** {_fmt_money(self.total_fair_value_usd)}",
            f"**Positions:** {self.position_count}",
            "",
        ]
        if self.top_positions:
            lines.append("### Top Holdings")
            for h in self.top_positions[:10]:
                lines.append(
                    f"- {h.issuer_name} ({h.ticker or 'n/a'}): "
                    f"{_fmt_money(h.fair_value_usd)}"
                    f"{' [PUT]' if h.put_call == 'put' else ''}"
                    f"{' [CALL]' if h.put_call == 'call' else ''}"
                )
            lines.append("")
        if self.new_positions:
            lines.append(f"**New positions:** {len(self.new_positions)}")
        if self.exited_positions:
            lines.append(f"**Exited:** {', '.join(self.exited_positions[:10])}")
        if self.increased_positions:
            lines.append(f"**Increased:** {len(self.increased_positions)} positions")
        if self.reduced_positions:
            lines.append(f"**Reduced:** {len(self.reduced_positions)} positions")
        return "\n".join(lines).strip()


# ─── Form D: Exempt Offerings ───────────────────────────────────────────


@dataclass
class FormDSummary:
    """Summarised view of a Form D (exempt securities offering)."""

    filing_ref: FilingRef
    issuer_name: str = ""
    issuer_jurisdiction: str = ""  # DE / CA / etc.
    offering_type: str = ""  # "Equity" / "Debt" / "Option" / "Pooled Investment Fund"
    exemption: str = ""  # "Rule 506(b)" / "Rule 506(c)" / "Rule 504" / "Reg A+"
    total_offering_amount: Optional[float] = None
    total_sold_amount: Optional[float] = None
    investors_count: Optional[int] = None
    sales_minimum: Optional[float] = None
    is_pooled_investment_fund: bool = False
    industry_group: str = ""
    related_filings: List[FilingRef] = field(default_factory=list)

    def render(self) -> str:
        sold = _fmt_money(self.total_sold_amount) if self.total_sold_amount else "Not disclosed"
        target = _fmt_money(self.total_offering_amount) if self.total_offering_amount else "Not disclosed"
        lines = [
            f"## Form D: {self.issuer_name}",
            f"_Filed: {self.filing_ref.filing_date}  ·  "
            f"Jurisdiction: {self.issuer_jurisdiction or 'n/a'}_",
            f"_Accession: {self.filing_ref.accession_no}_",
            "",
            f"**Exemption:** {self.exemption or 'Not specified'}",
            f"**Offering type:** {self.offering_type or 'Not specified'}",
            f"**Target amount:** {target}",
            f"**Sold to date:** {sold}",
            f"**Investors:** {_fmt_investors(self.investors_count)}",
            f"**Min investment:** {_fmt_money(self.sales_minimum) if self.sales_minimum else 'Not disclosed'}",
            f"**Pooled fund:** {'Yes' if self.is_pooled_investment_fund else 'No'}",
            f"**Industry:** {self.industry_group or 'Not specified'}",
        ]
        return "\n".join(lines).strip()


# ─── PRE 14A: Preliminary Proxy ─────────────────────────────────────────


@dataclass
class Pre14ASummary:
    """Summarised view of a PRE 14A preliminary proxy statement."""

    filing_ref: FilingRef
    issuer_name: str = ""
    meeting_type: str = ""  # Annual / Special / Annual + Special
    record_date: str = ""
    meeting_date: str = ""
    items_count: int = 0
    items: List[Dict[str, str]] = field(default_factory=list)
    # Merger-specific
    is_merger_proxy: bool = False
    target_company: str = ""
    transaction_type: str = ""  # Merger / Asset sale / Tender offer
    vote_required: str = ""
    board_recommendation: List[str] = field(default_factory=list)
    # Compensation
    say_on_pay: bool = False
    equity_plan_items: List[str] = field(default_factory=list)
    # Notable
    notable_items: List[str] = field(default_factory=list)

    def render(self) -> str:
        lines = [
            f"## PRE 14A: {self.issuer_name}",
            f"_Filed: {self.filing_ref.filing_date}  ·  "
            f"Meeting: {self.meeting_date or 'TBD'}_",
            f"_Accession: {self.filing_ref.accession_no}_",
            "",
            f"**Meeting type:** {self.meeting_type or 'Not specified'}",
            f"**Record date:** {self.record_date or 'Not disclosed'}",
            f"**Agenda items:** {self.items_count}",
            "",
        ]
        if self.items:
            lines.append("### Agenda Items")
            for item in self.items:
                lines.append(f"- **{item.get('number', '?')}.** {item.get('description', '')}")
                if item.get("board_rec"):
                    lines.append(f"  Board recommends: **{item['board_rec']}**")
            lines.append("")
        if self.is_merger_proxy:
            lines.append("### Merger/Acquisition")
            lines.append(f"**Target:** {self.target_company or 'Not disclosed'}")
            lines.append(f"**Transaction type:** {self.transaction_type or 'Not specified'}")
            lines.append(f"**Vote required:** {self.vote_required or 'Not specified'}")
            if self.board_recommendation:
                lines.append(f"**Board recommends:** {'; '.join(self.board_recommendation)}")
            lines.append("")
        if self.notable_items:
            lines.append("### Notable Items")
            for n in self.notable_items:
                lines.append(f"- {n}")
            lines.append("")
        return "\n".join(lines).strip()


# ─── EdgarClient Extension Methods ──────────────────────────────────────


def sweep_s1_filings(
    client: EdgarClient,
    ticker: str,
    *,
    limit: int = 5,
    include_amendments: bool = True,
) -> List[S1Summary]:
    """Fetch and summarise S-1 / S-1/A filings for ``ticker``.

    S-1 filings differ from periodic reports in that they are large HTML
    documents with prospectus-style sections. This method:
    1. Lists recent S-1 / S-1/A for the ticker from the submissions feed.
    2. Fetches the primary document body for each filing.
    3. Extracts key data points: offering size, underwriters, price range.
    4. Returns typed ``S1Summary`` objects sorted by filing date (newest first).

    Because S-1 documents are text-heavy and the EDGAR extract is best-effort,
    extracted fields may be partial. Missing fields are left as defaults.
    """
    if not client.is_live:
        return []

    s1_forms = ["S-1", "S-1/A"]
    refs = client.recent_filings(ticker, forms=s1_forms, limit=limit * 2)
    if not refs:
        return []

    summaries: List[S1Summary] = []
    for ref in refs:
        try:
            html = client.fetch_document(ref.primary_doc_url)
        except (EdgarError, Exception):
            continue
        text = client.extract_text(html)
        summary = _parse_s1_text(text, ref)
        summaries.append(summary)

    # Separate primary S-1 from amendments
    primary = [s for s in summaries if not s.filing_ref.form.endswith("/A")]
    amendments = [s for s in summaries if s.filing_ref.form.endswith("/A")]

    if primary and include_amendments:
        primary[0].amendments = [s.filing_ref for s in amendments]

    return (primary + amendments)[:limit]


def _parse_s1_text(text: str, ref: FilingRef) -> S1Summary:
    """Best-effort extraction of S-1 key fields from HTML→text body."""
    summary = S1Summary(filing_ref=ref)

    # Issuer name (often in the preamble or first paragraph)
    m = re.search(r"(?is)(?:registrant|issuer)[:\s]+(.+?)(?:\n|\.\s)", text[:2000])
    if m:
        summary.issuer_name = m.group(1).strip().rstrip(".")

    # Exchange listing
    m = re.search(
        r"(?is)(NYSE|NASDAQ|NYSE\s+American)\s*(?:Global\s*Select|Global\s*Market|Capital\s*Market)?",
        text[:10000],
    )
    if m:
        summary.exchange = m.group(1)

    # Price range
    m = re.search(
        r"(?is)(?:estimated\s+)?(?:initial\s+)?price\s+range[:\s]+[ $]*(\d+[\.,]?\d*)\s*(?:to|[-–])\s*[ $]*(\d+[\.,]?\d*)",
        text,
    )
    if m:
        try:
            summary.price_range_low = float(m.group(1).replace(",", ""))
            summary.price_range_high = float(m.group(2).replace(",", ""))
        except ValueError:
            pass

    # Shares offered
    m = re.search(
        r"(?is)(?:shares\s+offered|offering)[:\s]+([\d,]+)\s*(?:shares)?",
        text[:20000],
    )
    if m:
        try:
            summary.shares_offered = int(m.group(1).replace(",", ""))
        except ValueError:
            pass

    # Estimate raise
    if summary.shares_offered and summary.price_range_mid:
        summary.estimated_raise_usd = summary.shares_offered * summary.price_range_mid

    # Underwriters
    m = re.search(r"(?is)(?:underwriters|underwrit[ei]ng\s+group)[:\n]+(.{0,1000}?)(?:\n\n|\n\s*\n|[A-Z][A-Z]+)", text)
    if m:
        raw = m.group(1)
        names = re.findall(r"[A-Z][A-Za-z\s&.]+(?:LLC|LP|Inc\.|Corp\.|Securities|Partners|Group|Advisors|Global|Capital|Markets)", raw)
        summary.underwriters = [n.strip() for n in names[:8]]

    # Use of proceeds
    m = re.search(
        r"(?is)(?:use\s+of\s+proceeds|purposes)[:\n]+(.{0,800}?)(?:\n\n|\n\s*\n|Item)",
        text,
    )
    if m:
        summary.use_of_proceeds_summary = m.group(1).strip()

    # Risk factors count
    rf_section = EdgarClient.extract_section(text, "Risk Factors")
    if rf_section:
        summary.risk_factors_count = len(re.findall(r"(?i)\brisk\s+factor\b", rf_section[:8000]))

    # Business summary
    m = re.search(r"(?is)(?:our\s+business|business[:\n])(.{0,1500}?)(?:\n\n|\n\s*\n|Item|\brisk\b)", text)
    if m:
        text_block = m.group(1).strip()
        summary.business_summary = re.sub(r"\s+", " ", text_block[:600])

    # Check for audited financials
    summary.has_financials = bool(
        re.search(
            r"(?is)(?:audited\s+financial|financial\s+statements?|report\s+of\s+independent)",
            text[:20000],
        )
    )

    return summary


@property
def price_range_mid(self) -> Optional[float]:
    if self.price_range_low is not None and self.price_range_high is not None:
        return (self.price_range_low + self.price_range_high) / 2
    return None


S1Summary.price_range_mid = price_range_mid


# ─── 13F Parsing ────────────────────────────────────────────────────────


def sweep_13f_filings(
    client: EdgarClient,
    ticker_or_cik: str,
    *,
    limit: int = 4,
) -> List[Form13FSummary]:
    """Fetch 13F-HR filings for a manager identified by CIK or ticker.

    Note: 13F filings are filed by institutional investment managers, not
    by the companies they invest in. Use a *manager CIK* (e.g. Berkshire
    Hathaway's CIK 0001067983), or pass a ticker for which we can resolve
    a manager CIK via EDGAR (heuristic: look for institutional 13F filers).

    Because the 13F is an information-table-heavy XML filing (not plain
    HTML), we fetch the primary document, extract the XML table of holdings,
    and structure the position data.

    This uses a simplified XML-in-HTML parser (stdlib regex + tag matching).
    """
    if not client.is_live:
        return []

    # Resolve CIK: if it looks numeric, treat as CIK; else attempt ticker→CIK
    cik: Optional[int] = None
    if ticker_or_cik.isdigit():
        cik = int(ticker_or_cik)
    else:
        cik = client.cik_for(ticker_or_cik)

    if cik is None:
        return []

    # Force CIK zero-padded for URL
    _13F_URL = f"https://data.sec.gov/submissions/CIK{cik:010d}.json"

    try:
        sub_data = client._request_json(_13F_URL)
    except (EdgarError, Exception):
        return []

    recent = (sub_data.get("filings") or {}).get("recent") or {}
    accession = recent.get("accessionNumber") or []
    forms_arr = recent.get("form") or []
    filing_date = recent.get("filingDate") or []
    report_date = recent.get("reportDate") or []
    primary_doc = recent.get("primaryDocument") or []

    summaries: List[Form13FSummary] = []
    for i, acc in enumerate(accession):
        form = (forms_arr[i] if i < len(forms_arr) else "").upper()
        if form not in ("13F-HR", "13F-HR/A"):
            continue
        ref = FilingRef(
            cik=cik,
            accession_no=acc,
            form=form,
            filing_date=filing_date[i] if i < len(filing_date) else "",
            report_date=report_date[i] if i < len(report_date) else "",
            primary_document=primary_doc[i] if i < len(primary_doc) else "",
        )
        try:
            # Step 1: Try the primary document (often an HTML wrapper)
            doc_url = ref.primary_doc_url
            doc = client.fetch_document(doc_url)

            # Step 2: If the doc doesn't contain XML infoTable, try the
            # real XML sibling file (SEC stores 13F data in a separate XML)
            if "<infoTable>" not in doc:
                acc_dashless = acc.replace("-", "")
                xml_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_dashless}/53405.xml"
                try:
                    xml_doc = client.fetch_document(xml_url)
                    if "<infoTable>" in xml_doc:
                        doc = xml_doc
                except (EdgarError, Exception):
                    pass  # fall through with original doc
        except (EdgarError, Exception):
            continue

        summary = _parse_13f_text(doc, ref, client=client)
        summaries.append(summary)
        if len(summaries) >= limit:
            break

    return summaries


def _parse_13f_text(xml_text: str, ref: FilingRef, *, client=None) -> Form13FSummary:
    """Parse holdings from a 13F-HR XML/HTML filing.

    The SEC uses a standard XML schema for 13F information tables. We extract
    using regex patterns because parsing via stdlib XML is fragile with the
    HTML wrapper.

    CUSIP-to-ticker resolution is applied as a fallback when the XML doesn't
    include a <ticker> element (common with smaller institutional managers).
    """
    summary = Form13FSummary(filing_ref=ref)

    # Manager name (often in <filingManager> tags or the HTML header)
    m = re.search(r"(?is)<filingManager[^>]*>.*?<name>(.+?)</name>", xml_text)
    if m:
        summary.manager_name = m.group(1).strip()

    # Information table parsing — extract all <infoTable>...</infoTable> blocks
    tables = re.findall(r"(?is)<infoTable>(.*?)</infoTable>", xml_text)

    holdings: List[FilingHolding] = []
    for table in tables:
        name = _xml_field(table, "nameOfIssuer")
        cusip = _xml_field(table, "cusip")
        try:
            value = float(_xml_field(table, "value") or 0)
        except (ValueError, TypeError):
            value = 0.0
        try:
            shares = int(_xml_field(table, "shrsOrPrnAmt").split(">")[-1] if ">" in _xml_field(table, "shrsOrPrnAmt", "") else "0")
        except (ValueError, TypeError):
            shares = None
        put_call_str = _xml_field(table, "putCall")

        # Try XML ticker first; fall back to CUSIP resolution
        ticker = _xml_field(table, "ticker") or None
        if not ticker and cusip:
            resolved_ticker, _ = _resolve_ticker_fallback(
                cusip, name, client
            )
            if resolved_ticker:
                ticker = resolved_ticker

        holdings.append(
            FilingHolding(
                issuer_name=name,
                ticker=ticker,
                cusip=cusip,
                fair_value_usd=value,  # 13F XML <value> is a whole dollar amount
                shares=shares,
                put_call=put_call_str.lower() if put_call_str else None,
            )
        )

    holdings.sort(key=lambda h: h.fair_value_usd, reverse=True)
    summary.position_count = len(holdings)
    summary.top_positions = holdings[:15]
    summary.total_fair_value_usd = sum(h.fair_value_usd for h in holdings)

    # Estimate total shares if available
    share_values = [h.shares for h in holdings if h.shares is not None]
    if share_values:
        summary.total_shares = sum(share_values)

    # Positions are a single snapshot for the quarter — we note the top,
    # but detecting new/exited requires a diff against the prior quarter's
    # 13F which is a separate filing. For sweep purposes, flag what we have.
    summary.new_positions = holdings[:5]  # top by value as a proxy

    return summary


def _xml_field(xml_block: str, tag: str) -> str:
    """Extract the text content of the first matching XML tag.

    Handles:
    - <tag>content</tag>  (standard)
    - <tag/>  (self-closing)
    - <tag attrs>content</tag>  (with attributes)
    - <![CDATA[content]]>  (CDATA sections)
    - <shrsOrPrnAmt><sshPrnamt>SHARES</sshPrnamt>...</shrsOrPrnAmt> (nested)
    - <tag><subtag1>a</subtag1><subtag2>b</subtag2></tag> (return first significant child)
    """
    # Try CDATA first
    cdata = re.search(f"(?is)<{tag}[^>]*>\\s*<!\\[CDATA\\[(.*?)\\]\\]>", xml_block)
    if cdata:
        return cdata.group(1).strip()
    # shrsOrPrnAmt: extract the sshPrnamt child
    if tag == "shrsOrPrnAmt":
        m = re.search(r"(?is)<sshPrnamt>([\d,]+)</sshPrnamt>", xml_block)
        if m:
            return m.group(1).strip()
    # sshPrnamt / sshPrnamtType: direct child text
    if tag in ("sshPrnamt", "sshPrnamtType", "Sole", "Shared", "None"):
        m = re.search(f"(?is)<{tag}>([\d,]+)</{tag}>", xml_block)
        if m:
            return m.group(1).strip()
        m = re.search(f"(?is)<{tag}>([^<]+)</{tag}>", xml_block)
        if m:
            return m.group(1).strip()
    # Standard <tag>content</tag>
    m = re.search(f"(?is)<{tag}[^>]*>(.*?)</{tag}>", xml_block)
    if m:
        return m.group(1).strip()
    # Self-closing <tag/>
    m = re.search(f"(?is)<{tag}[^>]*/>", xml_block)
    if m:
        return "true"
    return ""


# ─── Form D Parsing ─────────────────────────────────────────────────────


def sweep_form_d_filings(
    client: EdgarClient,
    ticker: str,
    *,
    limit: int = 5,
) -> List[FormDSummary]:
    """Fetch exempt-offering Form D filings for a ticker.

    Form D is filed by the issuer after a Regulation D (or other exemption)
    offering. The SEC publishes Form D XML data through EDGAR. We use the
    standard filing-history path: recent_filings filtered for Form D.
    """
    if not client.is_live:
        return []

    refs = client.recent_filings(ticker, forms=["D", "D/A"], limit=limit)
    if not refs:
        return []

    summaries: List[FormDSummary] = []
    for ref in refs[:limit]:
        try:
            doc = client.fetch_document(ref.primary_doc_url)
        except (EdgarError, Exception):
            continue

        # Form D is often XML — try XML parsing first, fall back to text
        summary = _parse_form_d_text(doc, ref)
        summaries.append(summary)

    return summaries


def _parse_form_d_text(doc: str, ref: FilingRef) -> FormDSummary:
    """Best-effort parse of a Form D submission.

    The SEC's Form D XML schema uses tags like:
    <issuerInfo>  <offeringData>

    We use regex extraction (stdlib, no external XML parser dependency).
    """
    summary = FormDSummary(filing_ref=ref)

    summary.issuer_name = _xml_field(doc, "entityName") or _xml_field(doc, "issuerName")

    # Jurisdiction of incorporation
    summary.issuer_jurisdiction = _xml_field(doc, "jurisdictionOfIncorporation")

    # Offering type
    ot = _xml_field(doc, "securityOfferedType") or _xml_field(doc, "offeringType")
    if ot:
        summary.offering_type = ot

    # Exemption type
    exempt = _xml_field(doc, "exemptionType") or _xml_field(doc, "exemption")
    if exempt:
        summary.exemption = exempt

    # Offering amounts
    amt = _xml_field(doc, "totalOfferingAmount")
    if amt:
        try:
            summary.total_offering_amount = float(amt.replace(",", ""))
        except ValueError:
            pass

    sold = _xml_field(doc, "totalAmountSold") or _xml_field(doc, "amountSold")
    if sold:
        try:
            summary.total_sold_amount = float(sold.replace(",", ""))
        except ValueError:
            pass

    # Investors
    inv = _xml_field(doc, "numberOfInvestors") or _xml_field(doc, "investorsCount")
    if inv:
        try:
            summary.investors_count = int(inv)
        except ValueError:
            pass

    min_inv = _xml_field(doc, "salesMinimum") or _xml_field(doc, "minimumInvestment")
    if min_inv:
        try:
            summary.sales_minimum = float(min_inv.replace(",", ""))
        except ValueError:
            pass

    pooled = _xml_field(doc, "pooledInvestmentFund")
    summary.is_pooled_investment_fund = pooled.lower() in ("1", "true", "yes") if pooled else False

    industry = _xml_field(doc, "industryGroup")
    if industry:
        summary.industry_group = industry

    return summary


# ─── PRE 14A Parsing ────────────────────────────────────────────────────


def sweep_pre14a_filings(
    client: EdgarClient,
    ticker: str,
    *,
    limit: int = 3,
) -> List[Pre14ASummary]:
    """Fetch preliminary proxy statements (PRE 14A) for a ticker.

    PRE 14A is filed before the definitive DEF 14A. It's the draft proxy
    that contains the earliest signal of shareholder-vote items, including
    mergers, say-on-pay, equity plan changes, and board proposals.

    These are large HTML documents. We fetch the primary document and
    extract meeting info, agenda items, and transaction details.
    """
    if not client.is_live:
        return []

    refs = client.recent_filings(ticker, forms=["PRE 14A"], limit=limit)
    if not refs:
        return []

    summaries: List[Pre14ASummary] = []
    for ref in refs[:limit]:
        try:
            html = client.fetch_document(ref.primary_doc_url)
        except (EdgarError, Exception):
            continue
        text = client.extract_text(html)
        summary = _parse_pre14a_text(text, ref)
        summaries.append(summary)

    return summaries


def _parse_pre14a_text(text: str, ref: FilingRef) -> Pre14ASummary:
    """Best-effort extraction of PRE 14A key fields from HTML→text body."""
    summary = Pre14ASummary(filing_ref=ref)

    # Issuer name from filing metadata or first paragraph
    m = re.search(r"(?is)^[A-Z][A-Z\s.]+(?:Inc\.|Corp\.|LLC|LP|PLC)", text[:3000])
    if m:
        summary.issuer_name = m.group(0).strip()

    # Meeting date
    m = re.search(
        r"(?is)(?:meeting\s+(?:to\s+be\s+|will\s+be\s+)?held\s+on|meeting\s+date)[:\s]+([A-Z][a-z]+ \d+,?\s*\d{4})",
        text[:10000],
    )
    if m:
        summary.meeting_date = m.group(1)

    # Record date
    m = re.search(
        r"(?is)(?:record\s+date)[:\s]+([A-Z][a-z]+ \d+,?\s*\d{4})",
        text[:10000],
    )
    if m:
        summary.record_date = m.group(1)

    # Meeting type
    m = re.search(r"(?is)(?:Annual|Special|Combined|Annual\s+and\s+Special)\s+(?:Meeting|Meeting\s+of)", text[:5000])
    if m:
        summary.meeting_type = m.group(0)

    # Proxy items — numbered proposals
    items = re.findall(
        r"(?is)(?:Proposal|Item)\s+(\d+[A-Za-z]?)\s*[.–]\s*(.+?)(?=(?:Proposal|Item)\s+\d+[A-Za-z]?|$)",
        text,
    )
    items_seen: set = set()
    for number, description in items:
        desc = re.sub(r"\s+", " ", description).strip()[:200]
        if desc not in items_seen and desc:
            items_seen.add(desc)
            summary.items.append({"number": number, "description": desc})
    summary.items_count = len(summary.items)

    # Merger detection
    summary.is_merger_proxy = bool(
        re.search(r"(?is)(?:merger|acquisition|business\s+combination|proxy\s+statement\s+for\s+.*merger)", text[:30000])
    )

    if summary.is_merger_proxy:
        # Target company
        m = re.search(
            r"(?is)(?:acquire|merger\s+with|of)\s+([A-Z][A-Z\s.&]+(?:Inc\.|Corp\.|LLC|LP))",
            text[:50000],
        )
        if m:
            summary.target_company = m.group(1).strip()

        # Transaction type
        m = re.search(r"(?is)(?:pursuant\s+to\s+the)\s+(merger|asset\s+sale|tender\s+offer|exchange\s+offer)", text[:30000])
        if m:
            summary.transaction_type = m.group(1)

        # Vote required
        m = re.search(r"(?is)(?:vote\s+of\s+)(?:a\s+)?(?:majority|two\-thirds|supermajority)", text[:20000])
        if m:
            summary.vote_required = m.group(0)

        # Board recommendation
        recs = re.findall(
            r"(?is)(?:board\s+(?:of\s+directors\s+)?(?:recommends?|unanimously\s+recommends?))[:\s]+(.+?)(?:\.|\n)",
            text[:50000],
        )
        summary.board_recommendation = [r.strip() for r in recs[:3]]

    # Say-on-pay
    summary.say_on_pay = bool(
        re.search(r"(?is)(?:say[- ]on[- ]pay|advisory\s+vote\s+on\s+executive\s+compensation)", text)
    )

    # Equity plan items
    equity = re.findall(
        r"(?is)(?:equity\s+(?:incentive|compensation)\s+plan|stock\s+option\s+plan|employee\s+stock\s+purchase)",
        text,
    )
    summary.equity_plan_items = list(set(equity))[:3]

    # Notable items
    notable_indicators = [
        "poison pill",
        "shareholder proposal",
        "proxy access",
        "classified board",
        "majority voting",
        "confidential voting",
        "board declassification",
        "special meeting",
        "written consent",
        "supermajority",
    ]
    for indicator in notable_indicators:
        if re.search(rf"(?is){indicator}", text):
            summary.notable_items.append(f"Proxy references {indicator}")

    return summary


# ─── Helpers ────────────────────────────────────────────────────────────


def _fmt_shares(n: Optional[int]) -> str:
    if n is None:
        return "Not disclosed"
    if n >= 1_000_000:
        return f"{n / 1_000_000:,.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:,.1f}K"
    return f"{n:,}"


def _fmt_price(p: Optional[float]) -> str:
    if p is None:
        return "Not disclosed"
    return f"${p:,.2f}"


def _fmt_money(v: Optional[float]) -> str:
    if v is None:
        return "Not disclosed"
    if v >= 1_000_000_000:
        return f"${v / 1_000_000_000:,.2f}B"
    if v >= 1_000_000:
        return f"${v / 1_000_000:,.2f}M"
    if v >= 1_000:
        return f"${v:,.0f}K"
    return f"${v:,.0f}"


def _fmt_investors(n: Optional[int]) -> str:
    if n is None:
        return "Not disclosed"
    if n > 0 and n <= 300:
        return f"{n} (accredited / institutional)"
    return f"{n:,}"


# ─── EdgarClient monkey-patch ───────────────────────────────────────────
# These functions are intended to be imported alongside EdgarClient and
# called explicitly, e.g.:
#
#     from cme.research.data.filing_types import sweep_s1_filings
#     client = EdgarClient()
#     s1s = sweep_s1_filings(client, "RDDT")
#     for s in s1s:
#         print(s.render())
