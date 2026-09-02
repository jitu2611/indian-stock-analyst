<div align="center">

# 📊 Indian Stock Analyst

**NSE/BSE portfolio analysis powered by the [TradingAgents](https://github.com/jitu2611/TradingAgents) multi-agent engine.**

</div>

Indian Stock Analyst reads a Zerodha, Groww, or other broker holdings export, normalizes each symbol for Yahoo Finance (`RELIANCE.NS` / `500325.BO`), and runs it through TradingAgents' complete research graph:

- Market/technical, news, and fundamentals analysts by default
- Bull and bear researchers plus a research manager
- Trader, risk-management debate, and portfolio manager
- Five-tier engine rating mapped to this project's Buy/Hold/Avoid portfolio view
- One consolidated portfolio report plus complete per-stock agent reports

> Research only. The integration never places orders.

## Architecture

```text
Broker CSV/XLSX
    │
    ├─ parse + deduplicate holdings
    ├─ normalize NSE → .NS / BSE → .BO
    │
    ▼
jitu2611/TradingAgents
    ├─ market + news + fundamentals analysts
    ├─ bull/bear research debate
    ├─ trader + risk debate
    └─ portfolio-manager rating
    │
    ▼
portfolio-report.md + results.json + per-stock report trees
```

The integration pins TradingAgents commit `9dee508c44662702281a8dbaad1f7b42179b5ba7` for reproducible installation. TradingAgents uses Yahoo Finance for Indian price/fundamental data, Nifty 50 (`^NSEI`) as the `.NS` benchmark, and Sensex (`^BSESN`) as the `.BO` benchmark. India-specific RBI, SEBI, rupee, crude, GDP, FII, and monsoon queries replace the default US-centric macro query set.

## Installation

TradingAgents requires Python 3.10 or newer. Python 3.12 is recommended.

```bash
git clone https://github.com/jitu2611/indian-stock-analyst.git
cd indian-stock-analyst
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e '.[engine]'
cp .env.example .env
```

### Option A: provider API key

Add an API key for your selected LLM provider to `.env`, for example:

```dotenv
ANTHROPIC_API_KEY=...
# or OPENAI_API_KEY / GOOGLE_API_KEY / OPENROUTER_API_KEY
```

TradingAgents supports additional providers and local/OpenAI-compatible models; see its [provider documentation](https://github.com/jitu2611/TradingAgents#required-apis).

### Option B: Pi OAuth backbone

If Pi is already authenticated through `/login` (including ChatGPT Plus/Pro Codex OAuth), use the bundled
LangChain-to-Pi RPC adapter. It starts Pi with no coding tools, extensions, skills, or context files; each
LangChain call receives a fresh ephemeral Pi session. TradingAgents still owns its market-data tools and graph.

```bash
pi --list-models | grep openai-codex
indian-stock-analyst holdings.csv \
  --provider pi \
  --pi-provider openai-codex \
  --deep-model gpt-5.6-sol \
  --quick-model gpt-5.6-luna \
  --max-stocks 1
```

The adapter translates LangChain tool schemas into a strict JSON contract, converts Pi responses back into
`AIMessage.tool_calls` for TradingAgents' ToolNodes, and validates Pydantic structured outputs. OAuth tokens
remain managed by Pi and are never copied into the Python process or `.env`.

### Configure FRED macro data

TradingAgents' macro tool requires a free FRED API key. Configure it through the hidden-input helper so the
key is validated and stored in the ignored `.env` file with mode `0600`:

```bash
./scripts/configure-fred.sh
```

Create a key at <https://fred.stlouisfed.org/docs/api/api_key.html>. Do not paste it into chat or commit `.env`.
FRED primarily supplies US/global macro series; it complements rather than replaces RBI and Indian macro sources.

## Run a portfolio analysis

```bash
indian-stock-analyst holdings.csv \
  --date 2026-08-31 \
  --provider anthropic \
  --deep-model claude-sonnet-4-6 \
  --quick-model claude-haiku-4-5
```

Or invoke the Python module directly:

```bash
python -m indian_stock_analyst holdings.xlsx --exchange NSE
```

Useful options:

```text
--exchange NSE|BSE       Default exchange for unsuffixed symbols
--output PATH            Output directory (default: analysis-output/<date>)
--max-stocks N           Limit a test run and control LLM cost
--analysts LIST          market,news,fundamentals (social is opt-in)
--debate-rounds N        Bull/bear research depth
--risk-rounds N          Risk-team discussion depth
--no-checkpoint          Disable crash/resume checkpoints
--debug                  Stream verbose TradingAgents output
--pi-provider NAME       Pi provider used when --provider pi
--pi-deep-thinking LEVEL Pi reasoning for deep agents (default: high)
--pi-quick-thinking LVL  Pi reasoning for quick agents (default: minimal)
--pi-timeout SECONDS     Timeout for each Pi model call (default: 600)
```

Start with `--max-stocks 1`: the full graph makes multiple LLM calls per stock and can be slow or expensive on large portfolios.

## Output

```text
analysis-output/<date>/
├── portfolio-report.md       # consolidated human-readable decisions
├── results.json              # machine-readable ratings and errors
├── artifacts/
│   └── RELIANCE.NS/
│       ├── complete_report.md
│       ├── 1_analysts/
│       ├── 2_research/
│       ├── 3_trading/
│       ├── 4_risk/
│       └── 5_portfolio/
└── runtime/                  # TradingAgents state/log output
```

A bad ticker or transient provider failure is recorded against that stock without aborting the rest of the portfolio. Checkpointing is on by default so interrupted agent runs can resume.

## Rating mapping

TradingAgents retains its nuanced five-tier rating in every report. The portfolio summary maps it as follows:

| TradingAgents rating | Portfolio verdict |
|---|---|
| Buy / Overweight | 🟢 BUY |
| Hold | 🟡 HOLD |
| Underweight / Sell | 🔴 AVOID |
| Unparseable result | ⚪ REVIEW |

### Social-source policy

The social analyst is disabled by default. Anonymous Reddit RSS/search is intermittently rate-limited with
HTTP 429, and StockTwits' anonymous API is intermittently blocked by Cloudflare or returns no Indian-symbol
stream. Treating those failures as neutral sentiment understated uncertainty and slowed every run. Reports now
omit sentiment fields unless the social analyst is explicitly enabled with `--analysts ...,social` in an
environment where authorized, reliable source access has been configured.

## Portfolio file format

CSV, XLSX, and XLSM are supported. The symbol column may be named `Instrument`, `Trading Symbol`, `Symbol`, `Ticker`, `Security`, or `Stock`.

```csv
Instrument,Qty.,Avg. cost,LTP
RELIANCE,10,2450.00,2980.00
TCS,5,3200.00,3550.00
BSE:500325,12,2200.00,2450.00
```

Accepted symbol forms include `RELIANCE`, `NSE:RELIANCE`, `RELIANCE-EQ`, `RELIANCE.NS`, and BSE numeric codes. An `Exchange`/`Segment` column overrides the default exchange when present. Duplicate normalized tickers are analyzed once.

## Use as a Claude skill

`SKILL.md` instructs Claude to parse the portfolio, invoke this CLI, and treat TradingAgents—not ad-hoc web-search verdicts—as the analysis engine. Install the project and configure an LLM provider in the environment where the skill runs.

## Development

The adapter is deliberately thin and can be tested without making market-data or LLM calls:

```bash
pip install -e '.[dev]'
pytest
```

## Disclaimer

This project and TradingAgents are research tools. Their output may be incomplete, stale, non-deterministic, or wrong. Nothing generated here is financial, investment, or trading advice. Verify all data and consult a SEBI-registered investment adviser before acting.
