from pathlib import Path

from indian_stock_analyst.engine import (
    AnalysisResult,
    TradingAgentsEngine,
    extract_sentiment_confidence,
    map_signal_to_verdict,
)
from indian_stock_analyst.portfolio import Holding, load_portfolio, normalize_ticker
from indian_stock_analyst.report import render_report


def test_normalize_indian_tickers():
    assert normalize_ticker("RELIANCE") == "RELIANCE.NS"
    assert normalize_ticker("NSE:TCS-EQ") == "TCS.NS"
    assert normalize_ticker("500325", "BSE") == "500325.BO"
    assert normalize_ticker("INFY.NS", "BSE") == "INFY.NS"
    assert normalize_ticker("SBIN.NSE") == "SBIN.NS"


def test_load_zerodha_style_csv_deduplicates(tmp_path):
    portfolio = tmp_path / "holdings.csv"
    portfolio.write_text(
        "Instrument,Qty.,Avg. cost\nRELIANCE,10,2500\nNSE:RELIANCE-EQ,2,2600\nTCS,5,3000\n",
        encoding="utf-8",
    )
    holdings = load_portfolio(portfolio)
    assert [holding.ticker for holding in holdings] == ["RELIANCE.NS", "TCS.NS"]
    assert holdings[0].quantity == 10


def test_signal_mapping_and_confidence():
    assert map_signal_to_verdict("Buy") == "BUY"
    assert map_signal_to_verdict("Overweight") == "BUY"
    assert map_signal_to_verdict("Hold") == "HOLD"
    assert map_signal_to_verdict("Underweight") == "AVOID"
    assert map_signal_to_verdict("Sell") == "AVOID"
    assert map_signal_to_verdict("REVIEW") == "REVIEW"
    assert extract_sentiment_confidence("**Confidence:** High") == "High"


class FakeGraph:
    def propagate(self, ticker, analysis_date):
        return {
            "final_trade_decision": "**Rating**: Overweight\n\nEvidence-based thesis.",
            "sentiment_report": "**Confidence:** Medium",
        }, "Overweight"

    def save_reports(self, state, ticker, save_path):
        path = Path(save_path) / "complete_report.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("complete", encoding="utf-8")
        return path


def test_engine_adapter_and_report(tmp_path):
    holding = Holding("RELIANCE", "RELIANCE.NS", "Reliance Industries")
    result = TradingAgentsEngine(graph=FakeGraph()).analyze(
        holding, "2026-08-31", tmp_path / "artifacts" / "RELIANCE.NS"
    )
    assert result.verdict == "BUY"
    assert result.sentiment_confidence == "Medium"
    assert Path(result.report_path).exists()

    report_path = tmp_path / "portfolio-report.md"
    report = render_report([result], "2026-08-31", report_path)
    assert "TradingAgents rating | Verdict" in report
    assert "🟢 BUY" in report
    assert "artifacts/RELIANCE.NS/complete_report.md" in report


def test_report_omits_sentiment_when_social_analyst_is_disabled():
    report = render_report(
        [AnalysisResult("ACE", "ACE.NS", "ACE Limited", signal="Hold", verdict="HOLD")],
        "2026-09-01",
    )
    assert "Sentiment confidence" not in report
    assert "| Stock | TradingAgents rating | Verdict | Status |" in report
