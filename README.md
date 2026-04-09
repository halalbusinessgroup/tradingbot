# 🤖 Trading Bot — Tam Sistem (Azərbaycan)

Python (FastAPI) + Next.js + Binance Spot + Telegram + PostgreSQL + Celery + Redis əsaslı çox istifadəçili avtomatik trading bot platforması.

> ⚠️ **VACİB XƏBƏRDARLIQ:** Real pulla işə salmazdan əvvəl mütləq Binance Testnet-də sınayın. Bir kod xətası bütün balansı sıfırlaya bilər. `.env`-də `BINANCE_TESTNET=true` qoymaq kifayətdir — bütün kod eynidir.

---

## ✨ Xüsusiyyətlər

- 🔐 JWT autentifikasiya, AES (Fernet) ilə şifrələnmiş Binance açarları
- 📊 İstifadəçi paneli: dashboard, açıq trade-lər, PnL, balans
- 🎯 Strategiya konstruktoru (RSI, EMA, SMA, PRICE şərtləri)
- 🔄 Celery + Redis ilə hər user üçün periodic worker
- 📈 TradingView qrafiki frontend-də
- 💱 Binance Spot — Market BUY + OCO (TP/SL) avtomatik
- 🛡 Withdraw icazəli açar avtomatik rədd edilir
- 📱 Ümumi Telegram bot — `/start <token>` ilə user bağlanma
- 👑 Admin paneli — bütün userlər, statistika, blok/aktiv
- 🐳 Docker Compose ilə tək komandada deploy
- 🔒 Nginx + Let's Encrypt SSL prod konfiqurasiyası

---

## 📁 Layihə strukturu

```
trading-bot/
├── backend/              # FastAPI + Celery + SQLAlchemy
│   ├── app/
│   │   ├── api/          # REST endpoints (auth, users, strategies, trades, admin)
│   │   ├── core/         # security (JWT, AES), deps
│   │   ├── models/       # DB modelləri
│   │   ├── schemas/      # Pydantic
│   │   ├── services/     # Binance, Telegram, indicators, strategy_engine
│   │   ├── workers/      # Celery tasks
│   │   ├── config.py
│   │   ├── database.py
│   │   └── main.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/             # Next.js 14 (App Router) + Tailwind
│   ├── app/              # login, register, dashboard, strategy, trades, settings, admin
│   ├── components/       # Nav, TradingViewWidget
│   ├── lib/api.ts
│   └── Dockerfile
├── nginx/nginx.conf
├── docker-compose.yml
└── README.md
```

---

## 🚀 BAŞLANĞIC — 5 DƏQİQƏDƏ LOKAL İŞƏ SALMAQ

### 1. Tələblər
- Docker + Docker Compose (Docker Desktop bəs edir)
- Git

### 2. Repo-nu klonla / qovluğa keç
```bash
cd trading-bot
```

### 3. `.env` faylını hazırla
```bash
cp backend/.env.example backend/.env
```

`backend/.env` faylını aç və **3 vacib şeyi** dəyiş:

```env
JWT_SECRET=istənilən_uzun_təsadüfi_string_buraya
AES_KEY=Fernet_key_buraya
TELEGRAM_BOT_TOKEN=BotFather_token
TELEGRAM_BOT_USERNAME=YourBotUsername
ADMIN_EMAIL=sənin@email.com
ADMIN_PASSWORD=GüclüParol123!
BINANCE_TESTNET=true
```

**AES_KEY-i necə yaradım?** Aşağıdakı komandanı işlət:
```bash
docker run --rm python:3.11-slim python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
Çıxan stringi `AES_KEY=`-dən sonra yapışdır.

**JWT_SECRET üçün:**
```bash
openssl rand -hex 32
```

### 4. Telegram botu yarat (5 dəqiqə)
1. Telegram-da `@BotFather`-i aç
2. `/newbot` yaz
3. Bot adı və username ver (məs: `MyTradingBot`, `mytrading_bot`)
4. Verilən tokeni `TELEGRAM_BOT_TOKEN`-ə yapışdır
5. Username-i (`@`-siz) `TELEGRAM_BOT_USERNAME`-ə yaz

### 5. İşə sal
```bash
docker compose up -d --build
```

İlk dəfə 3-5 dəqiqə çəkir (image-lər yığılır). Sonra:

```bash
docker compose logs -f backend
```

Hər şey qaydasındadırsa görəcəksən: `Admin user created: ...` və `Application startup complete`.

### 6. Aç
- **Frontend:** http://localhost:3000
- **Backend Swagger:** http://localhost:8000/docs

Admin emaili və parolu ilə daxil ol → `/admin` paneli açılacaq.

---

## 🧪 BINANCE TESTNET AÇARI ALMAQ (PULSUZ)

1. https://testnet.binance.vision saytına get
2. Sağ üstdən GitHub və ya Google ilə daxil ol
3. "Generate HMAC_SHA256 Key" düyməsinə bas
4. **API Key** və **Secret Key** kopyala (bir də göstərilməyəcək!)
5. Sayta veb-panelində: Settings → Binance API → açarları daxil et
6. Sistem withdraw permission-u yoxlayır — testnet-də problemsizdir

Testnet-də sənin balansın **virtual 10,000 USDT-dir**, real pul deyil. Hər şeyi sınamaq üçün idealdır.

---

## ⚙️ İLK DƏFƏ İSTİFADƏ — ADIM ADIM

### Yeni user kimi:
1. `/register` səhifəsində qeydiyyatdan keç
2. **Settings** → Binance API açarını daxil et
3. **Settings** → "Telegram bağla" → linki aç → botda görünən tokenlə `/start <token>` yaz → Telegram bağlanır
4. **Strategy** → yeni strategiya yarat:
   - Ad: "SOL RSI 30"
   - Coin: SOLUSDT seç
   - Məbləğ: 10 USDT
   - TP: 5%, SL: 1%
   - Maksimum açıq trade: 2
   - Timeframe: 15m
   - Şərt: RSI < 30
5. **Dashboard** → "▶ Botu İşə Sal" düyməsinə bas
6. Bot hər 30 saniyədə bütün strategiyaları yoxlayacaq
7. Şərt ödənəndə BUY edəcək, OCO ilə TP/SL qoyacaq, Telegram bildiriş gələcək

### Admin kimi:
1. ADMIN_EMAIL/PASSWORD ilə daxil ol → `/admin` açılacaq
2. Bütün userləri, statistikanı, açıq/bağlı trade-ləri görə bilərsən
3. Hər useri blok edib aktivləşdirə bilərsən

---

## 🧠 STRATEGİYA ÖRNƏKLƏRİ

### 1. Sadə RSI Oversold
```
Coin: BTCUSDT, ETHUSDT
Şərt: RSI(14) < 30
TP: +3%, SL: -1.5%
Timeframe: 15m
```

### 2. EMA Trend Following
```
Coin: SOLUSDT
Şərt 1: PRICE > EMA(50)
Şərt 2: RSI(14) > 50
Şərt 3: RSI(14) < 70
TP: +5%, SL: -2%
```

### 3. Aggressive Scalping
```
Coin: SOLUSDT
Şərt: RSI(7) < 25
TP: +1.5%, SL: -0.7%
Timeframe: 1m
```

> 📌 **Qayda:** Strategy-də ən azı 1 şərt olmalıdır, əks halda bot heç vaxt al-ver etmir (təhlükəsizlik).

---

## 🌐 CANLI DEPLOY — VPS-də

### ADDIM 1 — Domain
**Namecheap**, **Porkbun** və ya **Cloudflare Registrar**-da `.com` al ($8-12/il).

### ADDIM 2 — VPS
**Hetzner Cloud** tövsiyə olunur (ən yaxşı qiymət/keyfiyyət):
- hetzner.com/cloud → "Create Server"
- **CX22**: 2 vCPU, 4GB RAM, 40GB SSD — €4.5/ay
- Image: **Ubuntu 24.04**
- SSH key əlavə et (lokal kompüterdə `ssh-keygen -t ed25519` ilə yarat)
- Yarat → IP ünvanını al (məs: `78.47.123.45`)

### ADDIM 3 — DNS bağla
Domain provayderində DNS panelində 3 A record əlavə et:
```
@      A   78.47.123.45
www    A   78.47.123.45
api    A   78.47.123.45
```
10-30 dəqiqə yayılma. Yoxla: `ping mytradingbot.com`

### ADDIM 4 — VPS hazırlığı
```bash
ssh root@78.47.123.45

# Sistem
apt update && apt upgrade -y

# Docker
curl -fsSL https://get.docker.com | sh

# Firewall
ufw allow 22 && ufw allow 80 && ufw allow 443 && ufw enable

# fail2ban
apt install fail2ban -y

# Yeni user (root ilə işləmə!)
adduser trader
usermod -aG sudo,docker trader
su - trader
```

### ADDIM 5 — Kodu çək
```bash
git clone https://github.com/SƏNİN_USERNAME/trading-bot.git
cd trading-bot
cp backend/.env.example backend/.env
nano backend/.env   # prod dəyərlər: BINANCE_TESTNET=false, güclü secret-lər
```

### ADDIM 6 — SSL (HTTPS pulsuz)
```bash
sudo apt install certbot -y
sudo certbot certonly --standalone -d mytradingbot.com -d www.mytradingbot.com
```

`nginx/nginx.conf`-da `mytradingbot.com` öz domain-inlə əvəz et.

### ADDIM 7 — İşə sal
```bash
docker compose up -d --build
docker compose logs -f
```

Bitdi! https://mytradingbot.com açılır.

### ADDIM 8 — SSL avtomatik yenilənmə
```bash
sudo crontab -e
# əlavə et:
0 3 * * * certbot renew --quiet && docker compose -f /home/trader/trading-bot/docker-compose.yml restart nginx
```

### ADDIM 9 — Backup (vacib!)
```bash
sudo nano /etc/cron.daily/db-backup
```
İçinə:
```bash
#!/bin/bash
mkdir -p /backups
docker exec $(docker ps -qf name=postgres) pg_dump -U trader tradingbot | gzip > /backups/db_$(date +\%F).sql.gz
find /backups -name "db_*.sql.gz" -mtime +14 -delete
```
```bash
sudo chmod +x /etc/cron.daily/db-backup
```

### ADDIM 10 — Monitoring
- **UptimeRobot.com** — pulsuz, hər 5 dəqiqədə saytı yoxlayır, düşəndə email göndərir
- **Sentry.io** — backend xəta tracking (pulsuz developer plan)

---

## 🔐 TƏHLÜKƏSİZLİK YOXLAMA

- [ ] `.env` git-ə düşmür (`.gitignore`-da var)
- [ ] `JWT_SECRET` ən az 32 simvol təsadüfi
- [ ] `AES_KEY` Fernet ilə generasiya olunub
- [ ] `ADMIN_PASSWORD` güclüdür (12+ simvol)
- [ ] Binance açarında **withdraw deaktivdir** (sistem yoxlayır)
- [ ] Production-da `BINANCE_TESTNET=false`
- [ ] HTTPS məcburidir (Nginx redirect)
- [ ] SSH parolu deaktivdir, yalnız key
- [ ] root login qadağandır
- [ ] fail2ban işləyir
- [ ] DB backup hər gecə işləyir

---

## 🛠 ƏMRLƏR (CHEAT SHEET)

```bash
# Lokal başlat
docker compose up -d --build

# Loglar
docker compose logs -f backend
docker compose logs -f worker
docker compose logs -f telegram_listener

# Restart
docker compose restart backend worker

# DB-yə daxil ol
docker compose exec postgres psql -U trader -d tradingbot

# Bütün userləri sil (DİQQƏT!)
docker compose exec postgres psql -U trader -d tradingbot -c "DELETE FROM users WHERE role='user';"

# Yenidən qur
docker compose down -v && docker compose up -d --build
```

---

## 📚 API SƏNƏDLƏRİ

Backend işə düşəndə avtomatik Swagger açılır:
- http://localhost:8000/docs
- http://localhost:8000/redoc

Əsas endpointlər:
- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET  /api/auth/me`
- `POST /api/users/binance-key`
- `POST /api/users/telegram-link`
- `POST /api/users/bot/toggle`
- `GET  /api/users/balance`
- `GET/POST/PUT/DELETE /api/strategies`
- `GET /api/trades`
- `GET /api/trades/stats`
- `GET /api/admin/users` (admin)
- `GET /api/admin/stats` (admin)

---

## 🎯 GƏLƏCƏK ƏLAVƏLƏR

- Backtesting engine (tarixi dataya görə test)
- Paper trading mode
- Trailing Stop Loss
- Partial Take Profit
- Multi-exchange (Bybit, OKX) — `ccxt`-ə keçid
- TradingView webhook (alert → trade)
- Strategy marketplace
- Copy trading

---

## ⚠️ HÜQUQİ QEYD

Bu proqram **təhsil məqsədli**dir. Avtomatik ticarət **böyük risklə** bağlıdır. Müəllif heç bir maliyyə itkisinə görə cavabdeh deyil. Yalnız itirə biləcəyiniz məbləğdə işlədin.

---

## 🆘 KÖMƏK

Problem yaranarsa:
1. `docker compose logs -f` ilə logları yoxla
2. `backend/.env` faylının düzgün doldurulduğunu yoxla
3. Binance API açarında withdraw deaktivdir?
4. Telegram bot tokeni düzgündür?

🚀 **Uğurlar!**
# tradingbot
