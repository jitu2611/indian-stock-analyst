"""Broker portfolio parsing and Yahoo Finance symbol normalization."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


_SYMBOL_HEADERS = (
    "instrument",
    "tradingsymbol",
    "trading symbol",
    "symbol",
    "ticker",
    "security",
    "stock",
)
_COMPANY_HEADERS = ("company name", "company", "name", "security name")
_EXCHANGE_HEADERS = ("exchange", "segment", "market")
_QUANTITY_HEADERS = ("quantity", "qty", "qty.", "net quantity")


@dataclass(frozen=True)
class Holding:
    source_symbol: str
    ticker: str
    company_name: str = ""
    quantity: float | None = None
    row: dict[str, object] = field(default_factory=dict, compare=False)


def _canonical_header(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").strip().lower()).strip()


def _find_header(headers: Iterable[object], candidates: tuple[str, ...]) -> object | None:
    canonical = {_canonical_header(header): header for header in headers if header is not None}
    for candidate in candidates:
        match = canonical.get(_canonical_header(candidate))
        if match is not None:
            return match
    return None


def normalize_ticker(symbol: str, exchange: str = "NSE") -> str:
    """Convert broker symbols to Yahoo/TradingAgents NSE or BSE tickers."""
    value = str(symbol or "").strip().upper()
    if not value:
        raise ValueError("empty stock symbol")

    inferred_exchange = exchange.upper().strip()
    if ":" in value:
        prefix, value = value.split(":", 1)
        if prefix in {"NSE", "BSE"}:
            inferred_exchange = prefix

    value = re.sub(r"-(EQ|BE|BZ|BL)$", "", value)
    if value.endswith(".NSE"):
        return value[:-4] + ".NS"
    if value.endswith(".BSE"):
        return value[:-4] + ".BO"
    if value.endswith((".NS", ".BO")):
        return value

    suffix = ".BO" if "BSE" in inferred_exchange else ".NS"
    return value + suffix


def _parse_quantity(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except ValueError:
        return None


def _rows_from_csv(path: Path) -> list[dict[str, object]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        sample = handle.read(4096)
        handle.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        return list(csv.DictReader(handle, dialect=dialect))


def _rows_from_excel(path: Path) -> list[dict[str, object]]:
    try:
        import openpyxl
    except ImportError as exc:  # pragma: no cover - dependency error is user-facing
        raise RuntimeError("Excel input requires openpyxl: pip install openpyxl") from exc

    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    sheet = workbook.active
    values = sheet.iter_rows(values_only=True)
    try:
        headers = next(values)
    except StopIteration:
        return []
    return [dict(zip(headers, row)) for row in values]


def load_portfolio(path: str | Path, default_exchange: str = "NSE") -> list[Holding]:
    """Load and deduplicate holdings from a broker CSV or Excel export."""
    portfolio_path = Path(path).expanduser()
    if not portfolio_path.exists():
        raise FileNotFoundError(portfolio_path)

    if portfolio_path.suffix.lower() == ".csv":
        rows = _rows_from_csv(portfolio_path)
    elif portfolio_path.suffix.lower() in {".xlsx", ".xlsm"}:
        rows = _rows_from_excel(portfolio_path)
    else:
        raise ValueError("portfolio must be a .csv, .xlsx, or .xlsm file")

    if not rows:
        raise ValueError("portfolio contains no holdings")

    headers = rows[0].keys()
    symbol_header = _find_header(headers, _SYMBOL_HEADERS)
    if symbol_header is None:
        expected = ", ".join(_SYMBOL_HEADERS[:5])
        raise ValueError(f"could not find a symbol column (expected one of: {expected})")
    company_header = _find_header(headers, _COMPANY_HEADERS)
    exchange_header = _find_header(headers, _EXCHANGE_HEADERS)
    quantity_header = _find_header(headers, _QUANTITY_HEADERS)

    holdings: list[Holding] = []
    seen: set[str] = set()
    for row in rows:
        source_symbol = str(row.get(symbol_header) or "").strip()
        if not source_symbol:
            continue
        row_exchange = str(row.get(exchange_header) or default_exchange) if exchange_header else default_exchange
        ticker = normalize_ticker(source_symbol, row_exchange)
        if ticker in seen:
            continue
        seen.add(ticker)
        holdings.append(
            Holding(
                source_symbol=source_symbol,
                ticker=ticker,
                company_name=str(row.get(company_header) or "").strip() if company_header else "",
                quantity=_parse_quantity(row.get(quantity_header)) if quantity_header else None,
                row=row,
            )
        )

    if not holdings:
        raise ValueError("portfolio contains no non-empty stock symbols")
    return holdings
