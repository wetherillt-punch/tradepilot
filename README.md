# TradePilot

Professional-grade AI trade plan generator for day and swing traders.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Frontend (Next.js 14 / Vercel)                                 │
│  Dashboard │ Analyze │ Journal │ Performance                    │
└──────────────────────────┬──────────────────────────────────────┘
                           │ REST API
┌──────────────────────────▼──────────────────────────────────────┐
│  Python Engine (FastAPI / Railway)                               │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────┐ │
│  │ CSV Parsers   │  │ yfinance     │  │ Indicator Engine       │ │
│  │ TOS + TV      │  │ Auto-Fetch   │  │ 14 indicators          │ │
│  └──────────────┘  └──────────────┘  └────────────────────────┘ │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────┐ │
│  │ Regime Engine │  │ Catalyst     │  │ Options Strategy       │ │
│  │ SPY/QQQ/VIX  │  │ Engine       │  │ Decision Tree          │ │
│  └──────────────┘  └──────────────┘  └────────────────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ 5-Stage LLM Pipeline (Claude API)                          │  │
│  │                                                            │  │
│  │  Session (cached):                                         │  │
│  │    Stage 1: Catalyst & Macro Context                       │  │
│  │    Stage 2: Market Regime Analysis                         │  │
│  │                                                            │  │
│  │  Per-Ticker:                                               │  │
│  │    Stage 3: Technical Analysis                             │  │
│  │    Stage 4: Risk Scenario Modeling                         │  │
│  │    Stage 5: Trade Plan Synthesis                           │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│  MongoDB Atlas                                                   │
│  Trade Plans │ Journal │ Performance │ Historical Events         │
└─────────────────────────────────────────────────────────────────┘
```

## Features

- **5-Stage LLM Pipeline** — Mimics a professional trading desk (macro strategist → market analyst → chartist → risk manager → portfolio manager)
- **Market Regime Engine** — Classifies market conditions before any ticker analysis
- **Catalyst Engine** — Tracks macro events, earnings, geopolitical risks with historical analogs
- **14 Technical Indicators** — Computed deterministically (no LLM hallucination on numbers)
- **7-Component Confidence Score** — Transparent, auditable, catalyst-aware
- **Options Strategy Decision Tree** — IV-aware strategy selection
- **Thesis Invalidation** — Every plan includes conditions that kill the trade
- **Correlation Warnings** — Flags hidden exposure through bellwether earnings
- **Trade Journal** — Log trades, get instant AI debriefs
- **Performance Analytics** — Win rate by setup type, weekly AI digest

## Setup

### Prerequisites
- Python 3.12+
- Node.js 18+
- MongoDB Atlas account (free tier works)
- Anthropic API key

### Python Engine (Backend)

```bash
cd py-engine
cp .env.example .env
# Edit .env with your API keys

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install

# Create .env.local
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local

npm run dev
```

### Deploy

**Backend → Railway:**
```bash
cd py-engine
railway login
railway init
railway up
```

**Frontend → Vercel:**
```bash
cd frontend
vercel
# Set NEXT_PUBLIC_API_URL to your Railway URL
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/session/init` | Initialize session (Stages 1-2) |
| POST | `/api/analyze/quick` | Analyze ticker via yfinance |
| POST | `/api/analyze/upload` | Analyze with CSV upload |
| POST | `/api/journal/log` | Log trade + get AI debrief |
| GET | `/api/journal` | Get journal entries |
| GET | `/api/performance` | Get performance stats |
| POST | `/api/performance/weekly-digest` | AI weekly review |
| GET | `/api/plans` | Get recent trade plans |
| GET | `/api/catalysts/bellwethers` | Bellwether mapping |
| GET | `/health` | Health check |

## Workflow

1. **Start your day** → Hit "Initialize Session" — fetches market data, runs regime + catalyst analysis
2. **Analyze tickers** → Enter ticker or upload CSV — 5-stage pipeline generates trade plan
3. **Execute trades** → Follow the plan with confidence scores and thesis invalidation
4. **Log results** → Journal the trade, get instant AI debrief
5. **Review weekly** → Generate performance digest to identify patterns and improve
