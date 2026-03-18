<div align="center">

# 📊 Indian Stock Analyst — Claude Skill

**A Claude AI skill that turns your Zerodha / Groww portfolio CSV into a professional Buy / Hold / Avoid report — in seconds.**

[![Claude Skill](https://img.shields.io/badge/Claude-Skill-blueviolet?logo=anthropic&logoColor=white)](https://claude.ai)
[![NSE/BSE](https://img.shields.io/badge/Market-NSE%20%2F%20BSE-orange)](https://nseindia.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Made for India](https://img.shields.io/badge/Made%20for-🇮🇳%20India-blue)](https://github.com/jitu2611)

---

> *"Upload your holdings CSV → get a research-backed verdict on every stock in your portfolio."*

</div>

---

## ✨ What It Does

Drop your Zerodha / Groww / Kite holdings CSV into Claude and this skill automatically:

- 🔍 **Researches every stock** using live web search — earnings, news, SEBI actions, analyst ratings
- 📣 **Gauges retail sentiment** from Reddit (r/IndiaInvestments, r/DalalStreetTalks), Twitter/X, and forums
- 🟢🟡🔴 **Assigns a Buy / Hold / Avoid verdict** with High / Medium / Low confidence
- 📋 **Generates a full PDF-ready report** with a summary table + detailed section per stock
- 💡 **Flags sector concentrations**, value traps, and structural risks in plain English
- 🤖 **Incorporates AI theme signals** — which stocks face AI disruption vs. which benefit from it

---

## 🚀 Quick Start

### 1. Install the skill

**Option A — Upload directly on Claude.ai**

1. Go to **Settings → Customize → Skills**
2. Click **+** → Upload a skill → select the `indian-stock-analyst/` folder (or ZIP it first)
3. Done ✅ — the skill auto-activates when you upload a portfolio file

**Option B — Clone this repo**

```bash
git clone https://github.com/jitu2611/indian-stock-analyst.git
```
Then upload the `indian-stock-analyst/` folder via Claude Settings → Skills.

---

### 2. Export your holdings CSV

**Zerodha Kite:**
> Holdings → ⬇️ Download → `holdings.csv`

**Groww:**
> Portfolio → Export → CSV

**Any broker:** Just make sure the CSV has an `Instrument` (or `Symbol`) column with NSE tickers.

---

### 3. Upload & trigger

Open Claude and either:
- Upload the CSV — Claude auto-detects it's a portfolio and runs the skill
- Or type: `/indian-stock-analyst` and upload the file

That's it. You'll get a full report in ~60 seconds.

---

## 📄 Sample Output

> Below is a real analysis generated on a 36-stock Indian portfolio (March 2026).

---

### Summary Table (excerpt)

| # | Stock | Sector | Verdict | Confidence |
|---|-------|--------|---------|------------|
| 1 | SBIN | PSU Banking | 🟢 BUY | High |
| 2 | AXISBANK | Private Banking | 🟢 BUY | High |
| 3 | ACUTAAS | Specialty Chemicals | 🟢 BUY | High |
| 4 | CGPOWER | Electrical Equipment | 🟢 BUY | High |
| 5 | BHEL | Power Equipment | 🟢 BUY | High |
| 6 | TATAPOWER | Power & Renewables | 🟢 BUY | High |
| 7 | KPITTECH | Auto IT / ER&D | 🔴 AVOID | High |
| 8 | TATAELXSI | Auto IT / ER&D | 🔴 AVOID | High |
| 9 | EXIDEIND | Batteries | 🔴 AVOID | Medium |
| 10 | FINCABLES | Cables | 🔴 AVOID | Medium |

📄 **[View the full 34-stock analysis report →](examples/sample-analysis-report.md)**

---

### Sample Stock Verdict

```
### SBIN — STATE BANK OF INDIA
Verdict: 🟢 BUY  |  Confidence: High  |  Your P&L: +17.7%

Latest News:
SBI delivered a blowout Q3 FY26 result — net profit of ₹21,028 crore,
beating analyst estimates by nearly 21%. The bank raised FY26 credit
growth guidance to 13–15% and forged a new partnership with Japan's MUFG.

Retail Sentiment:
Broadly bullish. Widely discussed as a defensive PSU bet amid geopolitical
turbulence and crude spike.

Reasoning:
Strong earnings beat, upgraded loan growth outlook, and outperformance vs.
the index all point decisively in one direction. Standout buy.
```

---

## 🧠 How It Works

```
Your CSV
   │
   ▼
Parse holdings (Instrument, Qty, Avg Cost, LTP, P&L)
   │
   ▼
For each stock → 2 web searches
   ├── 📰 News (ET, Livemint, Moneycontrol, NSE filings)
   └── 💬 Sentiment (Reddit, Twitter/X, forums)
   │
   ▼
Verdict engine
   ├── 🟢 BUY   — strong results, catalysts, positive sentiment
   ├── 🟡 HOLD  — mixed signals, wait-and-watch
   └── 🔴 AVOID — deteriorating fundamentals, regulatory risk, bearish
   │
   ▼
Full Markdown report with summary table + detailed section per stock
```

---

## 📂 Repository Structure

```
indian-stock-analyst/
├── SKILL.md                        ← The Claude skill definition
├── README.md                       ← This file
├── examples/
│   ├── sample-holdings.csv         ← Example portfolio CSV
│   └── sample-analysis-report.md  ← Full real-world analysis output
└── LICENSE
```

---

## 📋 CSV Format

The skill works with standard broker export formats. Minimum required column:

| Instrument | Qty. | Avg. cost | LTP | Invested | Cur. val | P&L |
|------------|------|-----------|-----|----------|----------|-----|
| RELIANCE | 10 | 2450.00 | 2980.00 | 24500 | 29800 | 5300 |
| TCS | 5 | 3200.00 | 3550.00 | 16000 | 17750 | 1750 |
| INFY | 15 | 1450.00 | 1320.00 | 21750 | 19800 | -1950 |

👉 **[Download sample CSV →](examples/sample-holdings.csv)**

---

## ⚙️ Verdict Criteria

| Verdict | When assigned |
|---------|---------------|
| 🟢 **BUY** | Strong recent results or catalysts, positive sentiment, no major red flags |
| 🟡 **HOLD** | Mixed signals — some positives but also concerns; wait-and-watch |
| 🔴 **AVOID** | Negative news (fraud, missed results, regulatory action), bearish sentiment, deteriorating fundamentals |

**Confidence Levels:**
- **High** — Clear signal from multiple independent sources
- **Medium** — Mixed sources or limited recent coverage
- **Low** — Insufficient data; verdict flagged as uncertain

---

## 🌟 Features At A Glance

| Feature | Detail |
|---------|--------|
| 📁 File support | CSV and Excel (.xlsx) |
| 🏦 Brokers | Zerodha, Groww, Upstox, Angel One, HDFC Sky, and any standard export |
| 📈 Markets | NSE and BSE stocks |
| 🔎 Research sources | Economic Times, Livemint, Moneycontrol, NSE filings, Reddit, Twitter/X |
| 🤖 AI awareness | Flags stocks facing AI disruption vs. AI-enabled growth |
| 🧩 ETF handling | Skips ETFs/MFs from stock verdicts, notes them separately |
| ⚠️ Edge cases | Ambiguous tickers flagged, penny stocks skipped, unlisted stocks noted |
| 🗂️ Portfolio size | Works best with 5–40 stocks; groups verdicts for 15+ stock portfolios |

---

## 💬 Example Prompts

Once the skill is installed, try:

```
"Analyze my portfolio"
"What should I sell?"
"Which stocks should I buy more of?"
"Show me my sector breakdown"
"Categorize my holdings by sector"
"Should I swap EXIDEIND with TATAPOWER?"
"Is holding Exide justified for the EV theme?"
```

The skill understands natural language — no special syntax needed.

---

## ⚠️ Disclaimer

This skill is for **informational and educational purposes only**. All reports are AI-generated based on publicly available news and social media signals.

**This is NOT financial advice.** Past performance is not indicative of future results. Please consult a **SEBI-registered investment advisor** before making any investment decisions.

---

## 🤝 Contributing

Contributions welcome! If you'd like to improve the skill:

1. Fork the repo
2. Edit `SKILL.md`
3. Test it on your own portfolio
4. Submit a PR with a description of what you improved

Ideas for contributions:
- Add support for US stocks (NYSE/NASDAQ)
- Add F&O position analysis
- Add mutual fund NAV analysis
- Improve sector classification accuracy
- Add technical analysis signals (RSI, MACD)

---

## 📜 License

MIT License — free to use, share, and modify. See [LICENSE](LICENSE) for details.

---

<div align="center">

**Made with ❤️ for Indian retail investors**

[⭐ Star this repo](https://github.com/jitu2611/indian-stock-analyst) · [🐛 Report a bug](https://github.com/jitu2611/indian-stock-analyst/issues) · [💡 Request a feature](https://github.com/jitu2611/indian-stock-analyst/issues)

</div>
