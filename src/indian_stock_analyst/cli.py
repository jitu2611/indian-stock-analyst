"""Command-line portfolio runner."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

from .engine import TradingAgentsEngine
from .portfolio import load_portfolio
from .report import render_report


def _analysis_date(value: str) -> str:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError("date must use YYYY-MM-DD") from exc
    if parsed > date.today():
        raise argparse.ArgumentTypeError("analysis date cannot be in the future")
    return parsed.isoformat()


def _safe_component(ticker: str) -> str:
    return re.sub(r"[^A-Za-z0-9._=-]+", "_", ticker).strip("._") or "symbol"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analyze an NSE/BSE portfolio with jitu2611/TradingAgents."
    )
    parser.add_argument("portfolio", help="Broker holdings CSV or Excel file")
    parser.add_argument("--date", type=_analysis_date, default=date.today().isoformat())
    parser.add_argument("--exchange", choices=("NSE", "BSE"), default="NSE")
    parser.add_argument("--output", default=None, help="Output directory")
    parser.add_argument("--provider", help="TradingAgents LLM provider")
    parser.add_argument("--deep-model", help="Model used for deep reasoning agents")
    parser.add_argument("--quick-model", help="Model used for quick analyst tasks")
    parser.add_argument(
        "--pi-provider",
        default=None,
        help="Pi backbone provider when --provider pi (default: current PI_PROVIDER or openai-codex)",
    )
    thinking_levels = ("off", "minimal", "low", "medium", "high", "xhigh", "max")
    parser.add_argument("--pi-deep-thinking", choices=thinking_levels, default="high")
    parser.add_argument("--pi-quick-thinking", choices=thinking_levels, default="minimal")
    parser.add_argument("--pi-timeout", type=float, default=600.0, help="Seconds allowed per Pi call")
    parser.add_argument("--pi-executable", default="pi")
    parser.add_argument("--debate-rounds", type=int, default=1)
    parser.add_argument("--risk-rounds", type=int, default=1)
    parser.add_argument(
        "--analysts",
        default="market,news,fundamentals",
        help=(
            "Comma-separated subset of market,news,fundamentals; social is opt-in because "
            "anonymous Reddit/StockTwits access is unreliable"
        ),
    )
    parser.add_argument("--max-stocks", type=int, help="Analyze only the first N unique symbols")
    parser.add_argument("--no-checkpoint", action="store_true")
    parser.add_argument("--debug", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        holdings = load_portfolio(args.portfolio, args.exchange)
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"Portfolio error: {exc}", file=sys.stderr)
        return 2

    if args.max_stocks is not None:
        if args.max_stocks < 1:
            print("--max-stocks must be at least 1", file=sys.stderr)
            return 2
        holdings = holdings[: args.max_stocks]

    analysts = tuple(part.strip().lower() for part in args.analysts.split(",") if part.strip())
    valid_analysts = {"market", "social", "news", "fundamentals"}
    if not analysts or not set(analysts).issubset(valid_analysts):
        print("--analysts must contain market,social,news and/or fundamentals", file=sys.stderr)
        return 2
    if args.debate_rounds < 1 or args.risk_rounds < 1:
        print("debate and risk rounds must be at least 1", file=sys.stderr)
        return 2

    output_dir = Path(args.output or f"analysis-output/{args.date}").expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "portfolio-report.md"

    try:
        engine = TradingAgentsEngine(
            provider=args.provider,
            deep_model=args.deep_model,
            quick_model=args.quick_model,
            selected_analysts=analysts,
            debate_rounds=args.debate_rounds,
            risk_rounds=args.risk_rounds,
            checkpoint=not args.no_checkpoint,
            debug=args.debug,
            results_dir=output_dir / "runtime",
            pi_provider=args.pi_provider,
            pi_deep_thinking=args.pi_deep_thinking,
            pi_quick_thinking=args.pi_quick_thinking,
            pi_timeout=args.pi_timeout,
            pi_executable=args.pi_executable,
        )
    except (RuntimeError, ValueError) as exc:
        print(f"Engine error: {exc}", file=sys.stderr)
        return 2

    results = []
    for index, holding in enumerate(holdings, 1):
        print(f"[{index}/{len(holdings)}] Analyzing {holding.ticker} ...", flush=True)
        result = engine.analyze(
            holding,
            args.date,
            output_dir / "artifacts" / _safe_component(holding.ticker),
        )
        results.append(result)
        if result.error:
            print(f"  failed: {result.error}", file=sys.stderr)
        else:
            print(f"  {result.signal} -> {result.verdict}")

    report_path.write_text(render_report(results, args.date, report_path), encoding="utf-8")
    (output_dir / "results.json").write_text(
        json.dumps([result.to_dict() for result in results], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nPortfolio report: {report_path}")
    print(f"Machine-readable results: {output_dir / 'results.json'}")
    return 1 if all(result.error for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
