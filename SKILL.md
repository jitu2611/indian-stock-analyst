---
name: indian-stock-analyst
description: >
  Analyzes NSE/BSE stock portfolios with the jitu2611/TradingAgents multi-agent engine and produces
  Buy/Hold/Avoid decisions plus full analyst, bull/bear, trader, risk, and portfolio-manager reports.
  Use whenever the user uploads a Zerodha, Groww, Upstox, Angel One, or other Indian holdings CSV/XLSX
  and asks to "analyze my portfolio", "review my Indian stocks", "what should I buy or sell", "what
  should I exit", "check my NSE holdings", "give verdicts on my stocks", "find portfolio risks", or
  "run TradingAgents on my holdings". Also trigger for a list of NSE/BSE symbols when the user requests
  portfolio-level analysis. TradingAgents must be the analysis engine; do not substitute ad-hoc web-search
  verdicts when the engine is unavailable.
---

# Indian Stock Analyst

Run every unique holding through the TradingAgents graph, then present its five-tier ratings and the
project's Buy/Hold/Avoid mapping. This workflow performs research only and never places orders.

## Step 1: Detect the Runtime and Authentication

Check both the installed CLI and Python package rather than assuming either exists:

```bash
command -v indian-stock-analyst || echo "CLI_NOT_FOUND"
command -v pi && pi --version || echo "PI_NOT_FOUND"
python3 -c "import tradingagents, indian_stock_analyst; print('PYTHON_READY')" 2>/dev/null || echo "PYTHON_NOT_READY"
python3 -c "import sys; print(sys.version_info >= (3, 10))"
for key in OPENAI_API_KEY ANTHROPIC_API_KEY GOOGLE_API_KEY OPENROUTER_API_KEY; do
  [ -n "$(printenv "$key")" ] && echo "$key=SET"
done
printf 'PI_BACKBONE=%s/%s\n' "$PI_PROVIDER" "$PI_MODEL"
```

Use this decision tree:

1. **CLI found + an LLM key is set** → use the direct-provider CLI path in Step 3.
2. **CLI found + Pi is authenticated** → use `--provider pi`; Pi may use OAuth without exposing a key.
3. **Python packages found** → use `python -m indian_stock_analyst` with the matching provider path.
4. **Project checkout found but packages are absent** → with user permission, create a Python 3.10+
   virtual environment and run `pip install -e '.[engine]'`, then repeat detection.
5. **Neither a provider key nor working Pi authentication exists** → guide setup; never print secrets.
6. **Engine remains unavailable** → report the blocker. Do not silently replace TradingAgents with a
   different verdict engine.

**Exit gate:** a Python 3.10+ runtime can import both packages and either a direct provider or Pi is authenticated.

## Step 2: Resolve Inputs and Defaults

Locate the uploaded CSV/XLSX/XLSM and use these defaults unless the user overrides them:

| Parameter | Default |
|---|---|
| Analysis date | Today, `YYYY-MM-DD` |
| Unsuffixed symbol exchange | NSE |
| Analysts | market, social, news, fundamentals |
| Research debate rounds | 1 |
| Risk debate rounds | 1 |
| Checkpoint/resume | Enabled |
| Output directory | `analysis-output/<date>` |
| LLM provider/models | TradingAgents environment/default config |
| Verdict mapping | Buy/Overweight → BUY; Hold → HOLD; Underweight/Sell → AVOID |
| Order execution | Never |

The parser accepts symbol columns named Instrument, Trading Symbol, Symbol, Ticker, Security, or Stock.
It converts NSE symbols to `.NS`, BSE symbols to `.BO`, honors an Exchange/Segment column, strips broker
prefixes such as `NSE:` and series suffixes such as `-EQ`, and analyzes duplicate normalized symbols once.

For a portfolio with more than 10 stocks, warn that the full graph makes many LLM calls. Unless the user
already approved a full run, recommend validating configuration with `--max-stocks 1` first.

**Exit gate:** identify one readable portfolio file and the intended analysis date/exchange.

## Step 3: Run TradingAgents

Preferred installed-CLI method:

```bash
indian-stock-analyst "<portfolio-path>" \
  --date "<YYYY-MM-DD>" \
  --exchange NSE \
  --output "<output-directory>"
```

Python-module fallback:

```bash
python3 -m indian_stock_analyst "<portfolio-path>" \
  --date "<YYYY-MM-DD>" \
  --exchange NSE \
  --output "<output-directory>"
```

For a direct API provider, add explicit model flags only when supplied:

```bash
--provider <provider> --deep-model <model> --quick-model <model>
```

For a Pi OAuth backbone, use:

```bash
--provider pi --pi-provider <pi-provider> \
--deep-model <pi-deep-model> --quick-model <pi-quick-model>
```

The Pi adapter launches strict-LF RPC sessions with no Pi tools, extensions, skills, prompts, or context files.
TradingAgents remains responsible for tool execution. OAuth credentials stay inside Pi's credential runtime.

For the initial cost/config check, append `--max-stocks 1`. After it succeeds, remove the limit to run the
approved portfolio. Keep checkpointing enabled unless the user requests `--no-checkpoint`.

The adapter configures Yahoo Finance data, Nifty/Sensex benchmark resolution, and India-specific RBI,
SEBI, rupee, crude, GDP, FII, and monsoon macro queries before invoking `TradingAgentsGraph.propagate()`.

**Exit gate:** the command writes `portfolio-report.md` and `results.json`. A per-stock failure is acceptable
only if recorded; continue analyzing the remaining holdings.

## Step 4: Validate the Artifacts

Read the generated `portfolio-report.md` and `results.json`. Verify:

- Every parsed ticker has either a TradingAgents rating or an explicit error.
- Every completed stock has a linked `artifacts/<ticker>/complete_report.md`.
- Ratings are only Buy, Overweight, Hold, Underweight, Sell, or REVIEW.
- REVIEW remains REVIEW; never turn an unparseable output into HOLD.
- "Sentiment confidence" is described as source/data quality, not prediction confidence.
- No report implies that an order was or will be placed.

If all stocks failed, summarize the common provider, key, rate-limit, model, or data error and stop. If only
some failed, clearly separate them from completed analyses.

**Exit gate:** summary counts match `results.json`, links exist, and mapping is correct.

## Step 5: Respond to the User

Use this exact structure:

1. **Run summary** — date, number completed/failed, engine/provider, and output path.
2. **Portfolio decisions** — table with ticker, TradingAgents rating, mapped verdict, sentiment confidence,
   and status.
3. **Key portfolio observations** — concise themes grounded in completed TradingAgents decisions; distinguish
   portfolio-manager conclusions from your own aggregation.
4. **Failures or limitations** — missing symbols/data, stale inputs, low sentiment confidence, and provider errors.
5. **Artifacts** — link the consolidated report, JSON, and per-stock complete reports.
6. **Disclaimer** — AI-generated research is not financial advice; verify data and consult a SEBI-registered adviser.

Do not invent confidence scores, news, prices, or rationale beyond the generated artifacts. Preserve the
TradingAgents five-tier rating alongside the simplified verdict so users can see the original engine output.
