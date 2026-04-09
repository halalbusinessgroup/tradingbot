# Trading Bot Platform

A multi-user automated crypto trading platform built with Python (FastAPI) + Next.js + Binance Spot + Telegram + PostgreSQL + Celery + Redis.

> **WARNING:** Always test on Binance Testnet before using real funds. A single misconfiguration can result in total balance loss. Set `BINANCE_TESTNET=true` in `.env` — all code is identical between testnet and live.

---

## Features

- JWT authentication with AES (Fernet) encrypted Binance API keys
- User dashboard: open trades, PnL, balance overview
- Strategy builder with RSI, EMA, SMA, MACD, Bollinger Bands, and more
- TradingView Webhook mode — trade when a TradingView alert fires
- Celery + Redis periodic workers per user
- TradingView chart integration in frontend
- Binance Spot — Market BUY + OCO (TP/SL) auto-placement
- Automatic rejection of API keys with Withdraw permission enabled
- Telegram bot integration — users connect via `/start <token>`
- Admin panel — all users, statistics, block/activate controls
- 5-language i18n: English, Azerbaijani, Turkish, Russian, Arabic
- Dark and light theme
- Docker Compose single-command deployment
- Nginx + Let's Encrypt SSL production configuration

---

## Project Structure

```
trading-bot/
├── backend/              # FastAPI + Celery + SQLAlchemy
│   ├── app/
│   │   ├── api/          # REST endpoints (auth, users, strategies, trades, admin)
│   │   ├── core/         # security (JWT, AES), dependencies
│   │   ├── models/       # Database models
│   │   ├── schemas/      # Pydantic schemas
│   │   ├── services/     # Binance, Telegram, indicators, strategy engine
│   │   ├── workers/      # Celery tasks
│   │   ├── config.py
│   │   ├── database.py
│   │   └── main.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/             # Next.js 14 (App Router) + Tailwind CSS
│   ├── app/              # login, register, dashboard, strategy, trades, settings, admin
│   ├── components/       # Nav, TradingViewWidget
│   ├── lib/api.ts
│   └── Dockerfile
├── nginx/nginx.conf
├── docker-compose.yml
└── README.md
```

---

## Quick Start — Local (5 Minutes)

### Requirements
- Docker + Docker Compose (Docker Desktop is sufficient)
- Git

### 1. Clone the repo
```bash
git clone https://github.com/halalbusinessgroup/tradingbot.git
cd tradingbot
```

### 2. Prepare the `.env` file
```bash
cp backend/.env.example backend/.env
```

Open `backend/.env` and set the required values:

```env
JWT_SECRET=any_long_random_string_here
AES_KEY=your_fernet_key_here
TELEGRAM_BOT_TOKEN=your_botfather_token
TELEGRAM_BOT_USERNAME=YourBotUsername
ADMIN_EMAIL=your@email.com
ADMIN_PASSWORD=StrongPassword123!
BINANCE_TESTNET=true
```

**Generate AES_KEY:**
```bash
docker run --rm python:3.11-slim python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

**Generate JWT_SECRET:**
```bash
openssl rand -hex 32
```

### 3. Create a Telegram Bot
1. Open `@BotFather` on Telegram
2. Send `/newbot` and follow the prompts
3. Copy the token into `TELEGRAM_BOT_TOKEN`
4. Copy the username (without `@`) into `TELEGRAM_BOT_USERNAME`

### 4. Start
```bash
docker compose up -d --build
```

First run takes 3–5 minutes. Then check logs:

```bash
docker compose logs -f backend
```

When ready you'll see: `Admin user created` and `Application startup complete`.

### 5. Open in browser
- **Frontend:** http://localhost:3000
- **Backend Swagger UI:** http://localhost:8000/docs

---

## Binance Testnet API Key (Free)

1. Go to https://testnet.binance.vision
2. Sign in with GitHub or Google
3. Click "Generate HMAC_SHA256 Key"
4. Copy the **API Key** and **Secret Key** (shown only once)
5. In the platform: Settings → Binance API → enter the keys

Your testnet balance is **virtual 10,000 USDT**. No real money involved.

---

## How Strategy Indicators Work

The bot fetches OHLCV (candlestick) price data from Binance/Bybit via the `ccxt` library, then calculates indicators internally using the `ta` (technical analysis) Python library. Binance itself does not calculate indicators — the bot does the math locally, then places a Market BUY order via the Binance API when all conditions are met.

| Indicator | What it measures | Common use |
|-----------|-----------------|------------|
| RSI | Momentum (0–100) | RSI < 30 = oversold, potential buy |
| EMA / SMA | Moving average of price | Price > EMA(50) = uptrend |
| MACD | Trend direction change | MACD crossover = entry signal |
| BB_UPPER/LOWER | Bollinger Bands | Price near BB_LOWER = potential bounce |
| ATR | Volatility | Used for dynamic SL sizing |
| VOLUME | Trading volume | Confirms breakouts |

### TradingView Webhook Mode
Instead of using indicator conditions, you can set a strategy to **Webhook Mode**. The bot generates a unique webhook URL for each strategy. When a TradingView alert fires and sends a POST request to that URL, the bot immediately places a buy order on the configured coins.

This lets you use TradingView's full Pine Script capabilities as your signal engine, while the bot handles order execution automatically.

---

## First-Time Usage Guide

### As a regular user:
1. Register at `/register`
2. Go to **Settings** → Enter your Binance API key
3. **Settings** → "Connect Telegram" → open the link → send `/start <token>` to the bot
4. **Strategy** → Create a strategy:
   - Name, Symbol (e.g. SOLUSDT), Amount (USDT), TP %, SL %
   - Add entry conditions (e.g. RSI < 30) **or** enable TradingView Webhook Mode
5. **Dashboard** → Click "Start Bot"

### As an admin:
1. Log in with `ADMIN_EMAIL` / `ADMIN_PASSWORD`
2. The `/admin` link appears in the navigation
3. View all users, approve/block accounts, change roles

---

## Strategy Examples

### 1. RSI Oversold
```
Symbol: BTCUSDT
Condition: RSI(14) < 30
TP: +3%, SL: -1.5%
Timeframe: 15m
```

### 2. EMA Trend Following
```
Symbol: SOLUSDT
Condition 1: PRICE > EMA(50)
Condition 2: RSI(14) > 50
TP: +5%, SL: -2%
```

### 3. TradingView Webhook
```
Symbol: ETHUSDT
Mode: Webhook
TP: +4%, SL: -2%
→ Trade fires when TradingView alert hits the webhook URL
```

---

## Docker and IP Addresses

Docker containers are assigned internal IPs that change on restart. This affects Binance API IP whitelisting.

**Solution:** Whitelist your **VPS public IP**, not Docker's internal IP. On the VPS, run:
```bash
curl ifconfig.me
```
Use that IP in Binance API settings. The VPS public IP stays fixed — Docker internal IPs are irrelevant to Binance.

On your local machine, whitelist your home/office public IP the same way.

---

## Production Deployment on a VPS

### Step 1 — Domain
Purchase a `.com` domain at Namecheap, Porkbun, or Cloudflare Registrar (~$8–12/year).

### Step 2 — VPS (Hetzner Cloud recommended)
- hetzner.com/cloud → Create Server
- **CX22**: 2 vCPU, 4GB RAM, 40GB SSD — ~€4.5/month
- Image: **Ubuntu 24.04**
- Add SSH key (generate locally: `ssh-keygen -t ed25519`)
- Note the server IP (e.g. `78.47.123.45`)

### Step 3 — DNS
Add A records in your domain DNS panel:
```
@      A   78.47.123.45
www    A   78.47.123.45
api    A   78.47.123.45
```

### Step 4 — VPS Setup
```bash
ssh root@78.47.123.45
apt update && apt upgrade -y
curl -fsSL https://get.docker.com | sh
ufw allow 22 && ufw allow 80 && ufw allow 443 && ufw enable
apt install fail2ban -y
adduser trader
usermod -aG sudo,docker trader
su - trader
```

### Step 5 — Deploy Code
```bash
git clone https://github.com/halalbusinessgroup/tradingbot.git
cd tradingbot
cp backend/.env.example backend/.env
nano backend/.env   # Set: BINANCE_TESTNET=false, strong secrets
```

### Step 6 — SSL (Free HTTPS)
```bash
sudo apt install certbot -y
sudo certbot certonly --standalone -d yourdomain.com -d www.yourdomain.com
```

Replace `yourdomain.com` in `nginx/nginx.conf` with your actual domain.

### Step 7 — Start
```bash
docker compose up -d --build
```

### Step 8 — Auto-renew SSL
```bash
sudo crontab -e
# Add:
0 3 * * * certbot renew --quiet && docker compose -f /home/trader/tradingbot/docker-compose.yml restart nginx
```

### Step 9 — Daily Database Backup
```bash
sudo nano /etc/cron.daily/db-backup
```
```bash
#!/bin/bash
mkdir -p /backups
docker exec $(docker ps -qf name=postgres) pg_dump -U trader tradingbot | gzip > /backups/db_$(date +\%F).sql.gz
find /backups -name "db_*.sql.gz" -mtime +14 -delete
```
```bash
sudo chmod +x /etc/cron.daily/db-backup
```

### Step 10 — Monitoring
- **UptimeRobot.com** — free uptime monitoring, alerts when site goes down
- **Sentry.io** — backend error tracking (free plan)

---

## Updating the Platform

After making changes and pushing to GitHub, on the VPS:

```bash
cd /home/trader/tradingbot
git pull origin main
docker compose up -d --build backend frontend
```

---

## Security Checklist

- [ ] `.env` is excluded from git (listed in `.gitignore`)
- [ ] `JWT_SECRET` is at least 32 random characters
- [ ] `AES_KEY` was generated with Fernet
- [ ] `ADMIN_PASSWORD` is strong (12+ characters)
- [ ] Binance API key has **Withdraw disabled** (system enforces this)
- [ ] `BINANCE_TESTNET=false` in production
- [ ] HTTPS is enforced via Nginx redirect
- [ ] SSH password login is disabled — key only
- [ ] root login is disabled
- [ ] fail2ban is running
- [ ] DB backup runs nightly

---

## Common Commands

```bash
# Start locally
docker compose up -d --build

# View logs
docker compose logs -f backend
docker compose logs -f worker

# Access the database
docker compose exec postgres psql -U trader -d tradingbot

# Full rebuild (resets all data)
docker compose down -v && docker compose up -d --build

# Get your public IP (for Binance API whitelist)
curl ifconfig.me
```

---

## API Documentation

Swagger UI is auto-generated when the backend is running:
- http://localhost:8000/docs
- http://localhost:8000/redoc

Key endpoints:
- `POST /api/auth/register` / `POST /api/auth/login`
- `GET  /api/auth/me`
- `POST /api/users/binance-key`
- `POST /api/users/bot/toggle`
- `GET  /api/users/balance`
- `GET/POST/PUT/DELETE /api/strategies`
- `GET  /api/trades` / `GET /api/trades/stats`
- `POST /api/webhook/{token}` _(TradingView webhook endpoint)_
- `GET  /api/admin/users` _(admin only)_
- `GET  /api/admin/stats` _(admin only)_

---

## Legal Notice

This software is provided for **educational purposes only**. Automated trading carries significant financial risk. The authors are not responsible for any financial losses. Only trade with capital you can afford to lose.

---

## Troubleshooting

1. Check logs: `docker compose logs -f`
2. Verify `backend/.env` is correctly filled in
3. Confirm Binance API key has Withdraw **disabled**
4. Confirm the VPS public IP is whitelisted in Binance (not Docker's internal IP)
5. Run `docker compose down && docker compose up -d --build` for a clean restart
