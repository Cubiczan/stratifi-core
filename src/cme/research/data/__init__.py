"""External data clients for the research workbench.

Three providers are wired in:
    - AlphaVantage   (company fundamentals, earnings, quotes, news sentiment)
    - FRED           (Federal Reserve Economic Data — macro context series)
    - SEC EDGAR      (filing history, full-text search, document text)

Plus extended filing-type parsers for S-1, 13F, Form D, and PRE 14A.

All clients degrade gracefully if their key (or, for EDGAR, a User-Agent
override) is missing. AV/FRED return ``None`` when no key is set; EDGAR is
keyless but its calls can be skipped entirely if the workbench is configured
without an EdgarClient.

A 24-hour on-disk cache lives under ``~/.cache/research-workbench/`` so reruns
do not burn quota.
"""

from cme.research.data.alphavantage import AlphaVantageClient, AlphaVantageError
from cme.research.data.cache import DiskCache
from cme.research.data.cusip_map import CusipResolver, CusipResolution, resolve_cusip
from cme.research.data.edgar import EdgarClient, EdgarError, FilingRef
from cme.research.data.filing_types import (
    # S-1
    S1Summary,
    sweep_s1_filings,
    # 13F
    FilingHolding,
    Form13FSummary,
    sweep_13f_filings,
    # Form D
    FormDSummary,
    sweep_form_d_filings,
    # PRE 14A
    Pre14ASummary,
    sweep_pre14a_filings,
)
from cme.research.data.fred import FredClient, FredError

__all__ = [
    "AlphaVantageClient",
    "AlphaVantageError",
    "CusipResolver",
    "CusipResolution",
    "resolve_cusip",
    "DiskCache",
    "EdgarClient",
    "EdgarError",
    "FilingRef",
    # S-1
    "S1Summary",
    "sweep_s1_filings",
    # 13F
    "FilingHolding",
    "Form13FSummary",
    "sweep_13f_filings",
    # Form D
    "FormDSummary",
    "sweep_form_d_filings",
    # PRE 14A
    "Pre14ASummary",
    "sweep_pre14a_filings",
    "FredClient",
    "FredError",
]
