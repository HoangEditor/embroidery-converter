# 🧵 Embroidery Converter

**One upload → All embroidery formats → Instant ZIP download**

Upload any embroidery file (47 formats supported) and get back a ZIP containing all 9 major formats: DST, PES, JEF, EXP, PEC, VP3, XXX, U01, TBF.

## ✨ Features

- 🚀 **Instant conversion** — 47 input → 9 output formats
- 🔒 **Privacy first** — Files auto-deleted after 10 minutes
- 🎨 **Premium UI** — Dark theme, space background, gold accents
- 🆓 **100% Free** — No account, no limits, no ads

## 🛠 Tech Stack

- **Backend:** FastAPI + pyembroidery
- **Frontend:** Vanilla HTML/CSS/JS (Linear/Framer inspired dark theme)
- **Deploy:** Fly.io (free tier)

## 🏃 Run Locally

```bash
# Setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run
cd backend && uvicorn main:app --reload --port 8000
```

Open http://localhost:8000

## 🚀 Deploy to Fly.io (Free)

```bash
# Install flyctl: brew install flyctl
fly auth signup
fly launch  # Detects fly.toml automatically
fly deploy
```

## 📦 Supported Formats

| Read (47) | Write (19) | Full Convert (16) |
|---|---|---|
| DST, PES, JEF, EXP, PEC, VP3, XXX, U01, TBF, HUS, SEW, PCS, CSD, +35 more | DST, PES, JEF, EXP, PEC, VP3, XXX, U01, TBF, CSV, JSON, SVG, PNG, +6 more | DST, PES, JEF, EXP, PEC, VP3, XXX, U01, TBF, COL, EDR, INF, GCODE, JSON, PMV, TBF |
