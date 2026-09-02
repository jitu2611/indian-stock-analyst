"""Adapter around jitu2611/TradingAgents."""

from __future__ import annotations

import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .portfolio import Holding


INDIA_MACRO_QUERIES = [
    "Reserve Bank of India RBI interest rates inflation liquidity",
    "India GDP rupee crude oil fiscal policy economic outlook",
    "Nifty 50 Indian corporate earnings foreign institutional investors FII",
    "SEBI regulation Indian equity market",
    "India monsoon commodities supply chain energy",
]


@dataclass
class AnalysisResult:
    source_symbol: str
    ticker: str
    company_name: str
    signal: str = "REVIEW"
    verdict: str = "REVIEW"
    sentiment_confidence: str = "Unknown"
    final_decision: str = ""
    report_path: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def map_signal_to_verdict(signal: str) -> str:
    """Map TradingAgents' five-tier rating to this project's three-tier verdict."""
    normalized = str(signal).strip().lower()
    if normalized in {"buy", "overweight"}:
        return "BUY"
    if normalized == "hold":
        return "HOLD"
    if normalized in {"underweight", "sell"}:
        return "AVOID"
    return "REVIEW"


def extract_sentiment_confidence(report: str) -> str:
    match = re.search(r"\*\*Confidence:\*\*\s*(Low|Medium|High)", report or "", re.I)
    return match.group(1).capitalize() if match else "Unknown"


class TradingAgentsEngine:
    """Run one shared TradingAgents graph over every portfolio holding."""

    def __init__(
        self,
        *,
        provider: str | None = None,
        deep_model: str | None = None,
        quick_model: str | None = None,
        selected_analysts: tuple[str, ...] = ("market", "news", "fundamentals"),
        debate_rounds: int = 1,
        risk_rounds: int = 1,
        checkpoint: bool = True,
        debug: bool = False,
        results_dir: str | Path | None = None,
        pi_provider: str | None = None,
        pi_deep_thinking: str = "high",
        pi_quick_thinking: str = "minimal",
        pi_timeout: float = 600.0,
        pi_executable: str = "pi",
        graph: Any = None,
    ) -> None:
        if graph is not None:
            self.graph = graph
            return

        try:
            from dotenv import load_dotenv

            load_dotenv()
            from tradingagents.default_config import DEFAULT_CONFIG
            import tradingagents.graph.trading_graph as trading_graph_module
            from tradingagents.graph.trading_graph import TradingAgentsGraph
            from tradingagents.llm_clients.factory import create_llm_client as default_llm_factory
        except ImportError as exc:
            raise RuntimeError(
                'TradingAgents is not installed. Run: pip install -e ".[engine]"'
            ) from exc

        config = DEFAULT_CONFIG.copy()
        config["global_news_queries"] = INDIA_MACRO_QUERIES.copy()
        config["benchmark_ticker"] = None  # .NS/.BO resolve to Nifty/Sensex in the fork
        config["max_debate_rounds"] = debate_rounds
        config["max_risk_discuss_rounds"] = risk_rounds
        config["checkpoint_enabled"] = checkpoint
        if provider:
            config["llm_provider"] = provider
        using_pi = str(config["llm_provider"]).lower() == "pi"
        if using_pi:
            config["deep_think_llm"] = deep_model or os.getenv("PI_MODEL") or "gpt-5.6-sol"
            config["quick_think_llm"] = quick_model or "gpt-5.6-luna"
        else:
            if deep_model:
                config["deep_think_llm"] = deep_model
            if quick_model:
                config["quick_think_llm"] = quick_model
        if results_dir:
            config["results_dir"] = str(Path(results_dir).expanduser().resolve())

        original_factory = trading_graph_module.create_llm_client
        if using_pi:
            from .pi_langchain import PiLLMClient

            backbone_provider = pi_provider or os.getenv("PI_PROVIDER") or "openai-codex"
            client_number = 0

            def pi_aware_factory(provider: str, model: str, base_url=None, **kwargs):
                nonlocal client_number
                if provider.lower() != "pi":
                    return default_llm_factory(provider, model, base_url, **kwargs)
                thinking = pi_deep_thinking if client_number == 0 else pi_quick_thinking
                client_number += 1
                return PiLLMClient(
                    model,
                    pi_provider=backbone_provider,
                    thinking=thinking,
                    timeout=pi_timeout,
                    executable=pi_executable,
                    cwd=str(Path.cwd()),
                )

            trading_graph_module.create_llm_client = pi_aware_factory

        try:
            self.graph = TradingAgentsGraph(
                selected_analysts=selected_analysts,
                debug=debug,
                config=config,
            )
        finally:
            trading_graph_module.create_llm_client = original_factory

    def analyze(self, holding: Holding, analysis_date: str, artifact_dir: str | Path) -> AnalysisResult:
        artifact_path = Path(artifact_dir)
        result = AnalysisResult(
            source_symbol=holding.source_symbol,
            ticker=holding.ticker,
            company_name=holding.company_name,
        )
        try:
            state, signal = self.graph.propagate(holding.ticker, analysis_date)
            result.signal = str(signal)
            result.verdict = map_signal_to_verdict(result.signal)
            result.final_decision = str(state.get("final_trade_decision", ""))
            result.sentiment_confidence = extract_sentiment_confidence(
                str(state.get("sentiment_report", ""))
            )
            report_path = self.graph.save_reports(state, holding.ticker, save_path=artifact_path)
            result.report_path = str(report_path)
        except Exception as exc:  # keep a large portfolio running if one symbol/provider fails
            result.error = f"{type(exc).__name__}: {exc}"
        return result
