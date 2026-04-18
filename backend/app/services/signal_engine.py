"""
TA Signal Engine — Score-based trading signal generator.

Scoring weights:
  Core (RSI, MACD, EMA cross, Ichimoku) : ×2
  Support/Resistance proximity           : ×2
  Candlestick patterns                   : ×1.5
  Auxiliary (Volume, Volatility, SAR)    : ×1

Signal thresholds (raw score):
  score >=  7  →  STRONG_BUY
  score >=  4  →  WEAK_BUY
  score <= -7  →  STRONG_SELL
  score <= -4  →  WEAK_SELL
  otherwise    →  NEUTRAL

3-candle confirmation: directional factors check the last 3 candles to
reduce false signals from a single outlier candle.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.services.exchange_service import make_public_client, to_ccxt_symbol
from app.services.indicators import (
    closes_from_klines, highs_from_klines, lows_from_klines,
    opens_from_klines, volumes_from_klines,
    ema, sma, rsi, macd, stoch_rsi, cci, williams_r, mfi, roc,
    bb_upper, bb_lower, bb_middle, bb_percent,
    atr, obv, cmf, vwap,
    supertrend, parabolic_sar, ichimoku,
    fibonacci_levels,
    detect_candlestick_patterns,
    keltner_channels,
    market_structure,
)

log = logging.getLogger(__name__)

# ─── Signal levels ─────────────────────────────────────────────────────────────
STRONG_BUY  = "STRONG_BUY"
WEAK_BUY    = "WEAK_BUY"
NEUTRAL     = "NEUTRAL"
WEAK_SELL   = "WEAK_SELL"
STRONG_SELL = "STRONG_SELL"

EMOJI = {
    STRONG_BUY:  "🟢",
    WEAK_BUY:    "🟡",
    NEUTRAL:     "⚪",
    WEAK_SELL:   "🟠",
    STRONG_SELL: "🔴",
}

LABEL = {
    STRONG_BUY:  "STRONG BUY SIGNAL",
    WEAK_BUY:    "WEAK BUY SIGNAL",
    NEUTRAL:     "NEUTRAL — No Signal",
    WEAK_SELL:   "WEAK SELL SIGNAL",
    STRONG_SELL: "STRONG SELL SIGNAL",
}


# ─── Helpers ───────────────────────────────────────────────────────────────────

def _near(price: float, level: float, pct: float = 0.5) -> bool:
    """True if price is within pct% of level."""
    if not level or not price:
        return False
    return abs(price - level) / price * 100 <= pct


def _fmt(v, digits=2) -> str:
    if v is None:
        return "N/A"
    return f"{v:,.{digits}f}"


# ─── ADX (Average Directional Index) ──────────────────────────────────────────

def _adx(highs, lows, closes, period: int = 14) -> Optional[dict]:
    """Wilder's ADX. Returns adx, plus_di, minus_di, trending, bullish."""
    n = len(closes)
    if n < period * 2 + 2:
        return None

    tr_list, plus_dm, minus_dm = [], [], []
    for i in range(1, n):
        h, l, pc = highs[i], lows[i], closes[i - 1]
        tr = max(h - l, abs(h - pc), abs(l - pc))
        up = highs[i] - highs[i - 1]
        dn = lows[i - 1] - lows[i]
        plus_dm.append(up if up > dn and up > 0 else 0.0)
        minus_dm.append(dn if dn > up and dn > 0 else 0.0)
        tr_list.append(tr)

    if len(tr_list) < period + 1:
        return None

    # Wilder's initial smoothing
    atr_w = sum(tr_list[:period])
    pw    = sum(plus_dm[:period])
    mw    = sum(minus_dm[:period])

    pdi_vals, mdi_vals, dx_vals = [], [], []

    for i in range(period, len(tr_list)):
        atr_w = atr_w - atr_w / period + tr_list[i]
        pw    = pw    - pw    / period + plus_dm[i]
        mw    = mw    - mw    / period + minus_dm[i]

        pdi = 100 * pw / atr_w if atr_w else 0.0
        mdi = 100 * mw / atr_w if atr_w else 0.0
        pdi_vals.append(pdi)
        mdi_vals.append(mdi)
        denom = pdi + mdi
        dx_vals.append(100 * abs(pdi - mdi) / denom if denom else 0.0)

    if len(dx_vals) < period:
        return None

    # Smooth DX → ADX
    adx_val = sum(dx_vals[:period]) / period
    for x in dx_vals[period:]:
        adx_val = (adx_val * (period - 1) + x) / period

    return {
        "adx":      round(adx_val, 2),
        "plus_di":  round(pdi_vals[-1], 2),
        "minus_di": round(mdi_vals[-1], 2),
        "trending": adx_val >= 25,
        "bullish":  pdi_vals[-1] > mdi_vals[-1],
    }


# ─── Classic Pivot Points ──────────────────────────────────────────────────────

def _pivot_points(highs, lows, closes, period: int = 24) -> Optional[dict]:
    """Classic daily/weekly pivot points using last `period` candles as reference."""
    if len(closes) < period + 2:
        return None
    ph = max(highs[-(period + 1):-1])
    pl = min(lows[-(period + 1):-1])
    pc = closes[-(period + 1)]

    p  = (ph + pl + pc) / 3
    r1 = 2 * p - pl
    r2 = p + (ph - pl)
    r3 = ph + 2 * (p - pl)
    s1 = 2 * p - ph
    s2 = p - (ph - pl)
    s3 = pl - 2 * (ph - p)

    return {"p": p, "r1": r1, "r2": r2, "r3": r3, "s1": s1, "s2": s2, "s3": s3}


# ─── USDT Dominance (market sentiment) ────────────────────────────────────────

def _fetch_usdt_dominance() -> Optional[float]:
    """Fetch USDT market cap dominance % from CoinGecko (free, no key needed).
    Returns e.g. 5.8 meaning USDT is 5.8% of total crypto market cap.
    """
    try:
        resp = httpx.get(
            "https://api.coingecko.com/api/v3/global",
            timeout=8,
            headers={"Accept": "application/json"},
        )
        if resp.is_success:
            pct = resp.json().get("data", {}).get("market_cap_percentage", {})
            val = pct.get("usdt") or pct.get("USDT")
            if val is not None:
                return round(float(val), 2)
    except Exception as e:
        log.debug(f"[signal] USDT.D fetch failed: {e}")
    return None


def _score_market_sentiment(usdt_d: Optional[float]) -> tuple[float, list]:
    """USDT Dominance scoring. Max ≈ ±1.5
    High USDT.D → fear, market selling → bearish pressure
    Low USDT.D  → greed, market buying → bullish pressure
    """
    if usdt_d is None:
        return 0.0, ["⚪ USDT.D: N/A (could not fetch)"]

    score = 0.0
    details = []

    if usdt_d >= 8.0:
        score -= 1.5
        details.append(f"❌ USDT.D: {usdt_d:.2f}% — extreme fear, heavy selling pressure")
    elif usdt_d >= 6.5:
        score -= 1.0
        details.append(f"❌ USDT.D: {usdt_d:.2f}% — elevated fear, bearish sentiment")
    elif usdt_d >= 5.5:
        score -= 0.5
        details.append(f"⚠️ USDT.D: {usdt_d:.2f}% — slightly elevated, mild caution")
    elif usdt_d <= 3.5:
        score += 1.5
        details.append(f"✅ USDT.D: {usdt_d:.2f}% — extreme greed, strong buying pressure")
    elif usdt_d <= 4.5:
        score += 1.0
        details.append(f"✅ USDT.D: {usdt_d:.2f}% — low fear, bullish sentiment")
    elif usdt_d <= 5.0:
        score += 0.5
        details.append(f"✅ USDT.D: {usdt_d:.2f}% — neutral-bullish market sentiment")
    else:
        details.append(f"⚪ USDT.D: {usdt_d:.2f}% — neutral market sentiment")

    return round(score, 2), details


# ─── Scoring modules ───────────────────────────────────────────────────────────

def _score_trend(highs, lows, closes, volumes) -> tuple[float, list]:
    """EMA alignment, Ichimoku, SAR, ADX, SuperTrend. Max ≈ ±5.5"""
    score = 0.0
    details = []

    # EMA alignment (3-candle confirmation)
    e9  = [ema(closes[:-(2 - i)] if i < 2 else closes, 9)  for i in range(3)]
    e20 = [ema(closes[:-(2 - i)] if i < 2 else closes, 20) for i in range(3)]
    e50 = [ema(closes[:-(2 - i)] if i < 2 else closes, 50) for i in range(3)]

    e9_now, e20_now, e50_now = ema(closes, 9), ema(closes, 20), ema(closes, 50)
    e200 = ema(closes, 200) if len(closes) >= 200 else None
    price = closes[-1]

    bull_align = all(
        (e9[i] or 0) > (e20[i] or 0) > (e50[i] or 0)
        for i in range(3)
    )
    bear_align = all(
        (e9[i] or 0) < (e20[i] or 0) < (e50[i] or 0)
        for i in range(3)
    )

    if bull_align:
        score += 2.0
        details.append(f"✅ EMA9 > EMA20 > EMA50 (bullish alignment)")
    elif bear_align:
        score -= 2.0
        details.append(f"❌ EMA9 < EMA20 < EMA50 (bearish alignment)")
    elif e9_now and e20_now and e9_now > e20_now:
        score += 1.0
        details.append(f"✅ EMA9 > EMA20 (short-term bullish)")
    elif e9_now and e20_now and e9_now < e20_now:
        score -= 1.0
        details.append(f"❌ EMA9 < EMA20 (short-term bearish)")

    if e200:
        if price > e200:
            score += 0.5
            details.append(f"✅ Price above EMA200 ({_fmt(e200, 4)}) — long-term bullish")
        else:
            score -= 0.5
            details.append(f"❌ Price below EMA200 ({_fmt(e200, 4)}) — long-term bearish")

    # Ichimoku cloud
    ic = ichimoku(highs, lows, closes)
    if ic:
        if ic.get("above_cloud"):
            score += 1.0
            details.append(f"✅ Price above Ichimoku cloud (bullish)")
        elif ic.get("below_cloud"):
            score -= 1.0
            details.append(f"❌ Price below Ichimoku cloud (bearish)")
        else:
            details.append(f"⚠️ Price inside Ichimoku cloud (indecision)")
        tk = ic.get("tenkan_sen")
        kj = ic.get("kijun_sen")
        if tk and kj:
            if tk > kj:
                score += 0.5
                details.append(f"✅ Tenkan ({_fmt(tk,4)}) above Kijun ({_fmt(kj,4)}) — bullish cross")
            else:
                score -= 0.5
                details.append(f"❌ Tenkan ({_fmt(tk,4)}) below Kijun ({_fmt(kj,4)}) — bearish")

    # Parabolic SAR
    psar = parabolic_sar(highs, lows, closes)
    if psar:
        if psar.get("bullish"):
            score += 0.5
            details.append(f"✅ Parabolic SAR bullish (SAR: {_fmt(psar['sar'],4)})")
        else:
            score -= 0.5
            details.append(f"❌ Parabolic SAR bearish (SAR: {_fmt(psar['sar'],4)})")

    # ADX
    adx_r = _adx(highs, lows, closes)
    if adx_r:
        adx_val = adx_r["adx"]
        if adx_r["trending"]:
            if adx_r["bullish"]:
                score += 0.5
                details.append(f"✅ ADX: {adx_val} (strong trend, bullish DI+)")
            else:
                score -= 0.5
                details.append(f"❌ ADX: {adx_val} (strong trend, bearish DI-)")
        else:
            details.append(f"⚪ ADX: {adx_val} (weak/no trend, range-bound)")

    # SuperTrend
    st = supertrend(highs, lows, closes)
    if st:
        if st.get("bullish"):
            score += 0.5
            details.append(f"✅ SuperTrend bullish (line: {_fmt(st['line'],4)})")
        else:
            score -= 0.5
            details.append(f"❌ SuperTrend bearish (line: {_fmt(st['line'],4)})")

    return round(score, 2), details


def _score_momentum(highs, lows, closes, volumes) -> tuple[float, list]:
    """RSI, MACD, StochRSI, CCI, Williams %R, MFI. Max ≈ ±7.5"""
    score = 0.0
    details = []

    # RSI (3-candle check)
    rsi_vals = [
        rsi(closes[:-(2 - i)] if i < 2 else closes, 14)
        for i in range(3)
    ]
    rsi_now = rsi_vals[-1]

    if rsi_now is not None:
        if all((r or 0) < 30 for r in rsi_vals):
            score += 2.0
            details.append(f"✅ RSI: {_fmt(rsi_now,1)} (oversold — strong buy zone)")
        elif all((r or 0) > 70 for r in rsi_vals):
            score -= 2.0
            details.append(f"❌ RSI: {_fmt(rsi_now,1)} (overbought — strong sell zone)")
        elif rsi_now < 45:
            score += 1.0
            details.append(f"✅ RSI: {_fmt(rsi_now,1)} (neutral-bullish zone)")
        elif rsi_now > 55:
            score -= 1.0
            details.append(f"❌ RSI: {_fmt(rsi_now,1)} (neutral-bearish zone)")
        else:
            details.append(f"⚪ RSI: {_fmt(rsi_now,1)} (neutral)")

    # MACD (3-candle confirmation)
    def _macd(c):
        r = macd(c, 12, 26, 9)
        return r.get("histogram") if r else None

    hist_now  = _macd(closes)
    hist_prev = _macd(closes[:-1])
    hist_2    = _macd(closes[:-2])

    macd_r = macd(closes, 12, 26, 9)
    if macd_r:
        hist = macd_r.get("histogram", 0) or 0
        sig  = macd_r.get("signal", 0) or 0
        line = macd_r.get("macd", 0) or 0

        if hist_now and hist_prev and hist_2:
            if hist_now > 0 and hist_prev <= 0:
                score += 2.0
                details.append(f"✅ MACD histogram crossed above zero (bullish)")
            elif hist_now < 0 and hist_prev >= 0:
                score -= 2.0
                details.append(f"❌ MACD histogram crossed below zero (bearish)")
            elif hist_now > 0 and hist > hist_prev > hist_2:
                score += 1.0
                details.append(f"✅ MACD histogram rising ({_fmt(hist,4)})")
            elif hist_now < 0 and hist < hist_prev < hist_2:
                score -= 1.0
                details.append(f"❌ MACD histogram falling ({_fmt(hist,4)})")
            elif hist > 0:
                score += 0.5
                details.append(f"✅ MACD histogram positive ({_fmt(hist,4)})")
            elif hist < 0:
                score -= 0.5
                details.append(f"❌ MACD histogram negative ({_fmt(hist,4)})")

        # MACD line vs signal
        if line > sig:
            details.append(f"✅ MACD line ({_fmt(line,4)}) above signal ({_fmt(sig,4)})")
        else:
            details.append(f"❌ MACD line ({_fmt(line,4)}) below signal ({_fmt(sig,4)})")

    # Stochastic RSI
    sr = stoch_rsi(closes, 14, 14, 3, 3)
    if sr:
        k, d = sr.get("k"), sr.get("d")
        if k is not None and d is not None:
            if k < 20:
                score += 1.0
                details.append(f"✅ StochRSI K: {_fmt(k,1)} (oversold)")
            elif k > 80:
                score -= 1.0
                details.append(f"❌ StochRSI K: {_fmt(k,1)} (overbought)")
            # K crosses D
            sr_prev = stoch_rsi(closes[:-1], 14, 14, 3, 3)
            if sr_prev:
                k_prev = sr_prev.get("k") or 0
                d_prev = sr_prev.get("d") or 0
                if k_prev <= d_prev and k > (d or 0):
                    score += 0.5
                    details.append(f"✅ StochRSI K({_fmt(k,1)}) crossed above D({_fmt(d,1)})")
                elif k_prev >= d_prev and k < (d or 0):
                    score -= 0.5
                    details.append(f"❌ StochRSI K({_fmt(k,1)}) crossed below D({_fmt(d,1)})")

    # CCI
    cci_val = cci(highs, lows, closes, 20)
    if cci_val is not None:
        if cci_val < -100:
            score += 0.5
            details.append(f"✅ CCI: {_fmt(cci_val,1)} (oversold <-100)")
        elif cci_val > 100:
            score -= 0.5
            details.append(f"❌ CCI: {_fmt(cci_val,1)} (overbought >+100)")
        else:
            details.append(f"⚪ CCI: {_fmt(cci_val,1)}")

    # Williams %R
    wr = williams_r(highs, lows, closes, 14)
    if wr is not None:
        if wr < -80:
            score += 0.5
            details.append(f"✅ Williams %R: {_fmt(wr,1)} (oversold)")
        elif wr > -20:
            score -= 0.5
            details.append(f"❌ Williams %R: {_fmt(wr,1)} (overbought)")
        else:
            details.append(f"⚪ Williams %R: {_fmt(wr,1)}")

    # MFI
    mfi_val = mfi(highs, lows, closes, volumes, 14)
    if mfi_val is not None:
        if mfi_val < 20:
            score += 0.5
            details.append(f"✅ MFI: {_fmt(mfi_val,1)} (oversold — money flowing in)")
        elif mfi_val > 80:
            score -= 0.5
            details.append(f"❌ MFI: {_fmt(mfi_val,1)} (overbought — money flowing out)")
        else:
            details.append(f"⚪ MFI: {_fmt(mfi_val,1)}")

    return round(score, 2), details


def _score_volume(highs, lows, closes, volumes) -> tuple[float, list]:
    """OBV, CMF, Volume vs avg. Max ≈ ±2.5"""
    score = 0.0
    details = []

    # OBV direction (3-candle)
    obv_now  = obv(closes, volumes)
    obv_3ago = obv(closes[:-3], volumes[:-3])
    if obv_now is not None and obv_3ago is not None:
        if obv_now > obv_3ago:
            score += 1.0
            details.append(f"✅ OBV rising (trend confirmation)")
        else:
            score -= 1.0
            details.append(f"❌ OBV falling (trend divergence)")

    # CMF
    cmf_val = cmf(highs, lows, closes, volumes, 20)
    if cmf_val is not None:
        if cmf_val > 0.1:
            score += 1.0
            details.append(f"✅ CMF: {_fmt(cmf_val,3)} (money flowing in)")
        elif cmf_val < -0.1:
            score -= 1.0
            details.append(f"❌ CMF: {_fmt(cmf_val,3)} (money flowing out)")
        else:
            details.append(f"⚪ CMF: {_fmt(cmf_val,3)} (neutral)")

    # Volume vs 20-period avg
    vol_ma = sma(volumes, 20)
    if vol_ma and volumes:
        vol_ratio = volumes[-1] / vol_ma
        if vol_ratio > 1.5:
            score += 0.5
            details.append(f"✅ Volume {_fmt(vol_ratio, 1)}× above average (strong interest)")
        elif vol_ratio < 0.5:
            details.append(f"⚠️ Volume {_fmt(vol_ratio, 1)}× below average (weak move)")

    return round(score, 2), details


def _score_volatility(highs, lows, closes) -> tuple[float, list]:
    """Bollinger Bands, Keltner Channel. Max ≈ ±1.5"""
    score = 0.0
    details = []

    # Bollinger Bands %B
    bbp = bb_percent(closes, 20)
    bbu = bb_upper(closes, 20)
    bbl = bb_lower(closes, 20)
    bbm = bb_middle(closes, 20)
    price = closes[-1]

    if bbp is not None:
        if bbp < 0.15:
            score += 1.0
            details.append(f"✅ BB %B: {_fmt(bbp,3)} — price near lower band (oversold)")
        elif bbp > 0.85:
            score -= 1.0
            details.append(f"❌ BB %B: {_fmt(bbp,3)} — price near upper band (overbought)")
        else:
            details.append(f"⚪ BB %B: {_fmt(bbp,3)} (mid-range)")

    # Keltner squeeze (BB narrower than KC = compression before move)
    kc = keltner_channels(highs, lows, closes, 20, 2.0)
    if kc and bbu and bbl:
        bb_width = bbu - bbl
        kc_width = kc["upper"] - kc["lower"]
        if bb_width < kc_width * 0.9:
            score += 0.5
            details.append(f"✅ Bollinger squeeze inside Keltner — volatility breakout expected")

    return round(score, 2), details


def _score_candlestick(opens, highs, lows, closes) -> tuple[float, list]:
    """Candlestick pattern scoring. Max ≈ ±1.5"""
    score = 0.0
    details = []

    patterns = detect_candlestick_patterns(opens, highs, lows, closes)

    BULLISH = {
        "hammer", "inverted_hammer", "bullish_engulfing", "bullish_harami",
        "piercing_line", "morning_star", "three_white_soldiers", "bullish_marubozu",
    }
    BEARISH = {
        "shooting_star", "bearish_engulfing", "bearish_harami",
        "dark_cloud_cover", "evening_star", "three_black_crows", "bearish_marubozu",
    }

    bull_found = [k.replace("_", " ").title() for k, v in patterns.items() if v and k in BULLISH]
    bear_found = [k.replace("_", " ").title() for k, v in patterns.items() if v and k in BEARISH]

    if bull_found:
        score += 1.5
        details.append(f"✅ Bullish pattern: {', '.join(bull_found)}")
    elif bear_found:
        score -= 1.5
        details.append(f"❌ Bearish pattern: {', '.join(bear_found)}")

    if not bull_found and not bear_found:
        # Doji
        if patterns.get("doji"):
            details.append("⚪ Doji detected (indecision)")
        elif patterns.get("spinning_top"):
            details.append("⚪ Spinning Top (indecision)")

    return round(score, 2), details


def _score_support_resistance(highs, lows, closes) -> tuple[float, list, dict]:
    """Pivot points, Fibonacci levels, local S/R. Max ≈ ±4.0"""
    score = 0.0
    details = []
    levels = {"support": None, "resistance": None, "fib_key": None, "fib_val": None}

    price = closes[-1]

    # ── Fibonacci levels ──────────────────────────────────────────────────────
    fibs = fibonacci_levels(highs, lows, lookback=50)
    if fibs:
        fib_support = [
            ("0.786", fibs.get("fib_786")),
            ("0.618", fibs.get("fib_618")),
            ("0.500", fibs.get("fib_500")),
            ("0.382", fibs.get("fib_382")),
        ]
        for label, fv in fib_support:
            if fv and price > fv and _near(price, fv, 0.8):
                score += 1.5
                details.append(f"✅ Price near Fibonacci {label} support ({_fmt(fv,4)})")
                levels["fib_key"] = label
                levels["fib_val"] = fv
                break

        fib_resist = [
            ("0.236", fibs.get("fib_236")),
            ("0.382", fibs.get("fib_382")),
            ("0.500", fibs.get("fib_500")),
        ]
        for label, fv in fib_resist:
            if fv and price < fv and _near(price, fv, 0.8):
                score -= 1.0
                details.append(f"❌ Price near Fibonacci {label} resistance ({_fmt(fv,4)})")
                break

    # ── Classic Pivot Points ──────────────────────────────────────────────────
    pp = _pivot_points(highs, lows, closes, period=24)
    if pp:
        for key, lv in [("S3", pp["s3"]), ("S2", pp["s2"]), ("S1", pp["s1"])]:
            if _near(price, lv, 0.5):
                score += 2.0
                details.append(f"✅ Price at Pivot {key} support ({_fmt(lv,4)})")
                levels["support"] = lv
                break
        for key, lv in [("R1", pp["r1"]), ("R2", pp["r2"]), ("R3", pp["r3"])]:
            if _near(price, lv, 0.5):
                score -= 2.0
                details.append(f"❌ Price at Pivot {key} resistance ({_fmt(lv,4)})")
                levels["resistance"] = lv
                break

        # Find nearest support/resistance (for display even if not "near")
        supports = [pp["s1"], pp["s2"], pp["s3"]]
        resistances = [pp["r1"], pp["r2"], pp["r3"]]
        near_sup = max((s for s in supports if s < price), default=None)
        near_res = min((r for r in resistances if r > price), default=None)
        if near_sup:
            levels["support"] = levels["support"] or near_sup
        if near_res:
            levels["resistance"] = levels["resistance"] or near_res

        details.append(f"📍 Pivot P: {_fmt(pp['p'],4)}  |  S1: {_fmt(pp['s1'],4)}  |  R1: {_fmt(pp['r1'],4)}")

    # ── Local swing highs/lows (last 20 candles) ──────────────────────────────
    recent_high = max(highs[-20:]) if len(highs) >= 20 else max(highs)
    recent_low  = min(lows[-20:])  if len(lows)  >= 20 else min(lows)
    if _near(price, recent_low, 0.6):
        score += 1.0
        details.append(f"✅ Price near 20-bar low support ({_fmt(recent_low,4)})")
        levels["support"] = levels["support"] or recent_low
    if _near(price, recent_high, 0.6):
        score -= 1.0
        details.append(f"❌ Price near 20-bar high resistance ({_fmt(recent_high,4)})")
        levels["resistance"] = levels["resistance"] or recent_high

    if not levels["support"]:
        levels["support"] = recent_low
    if not levels["resistance"]:
        levels["resistance"] = recent_high

    return round(score, 2), details, levels


def _calculate_risk(price: float, atr_val: float, signal: str,
                    risk_mult: float = 1.5, tp1_mult: float = 2.0,
                    tp2_mult: float = 3.5) -> dict:
    """ATR-based SL/TP calculation."""
    if signal in (STRONG_BUY, WEAK_BUY):
        sl  = price - atr_val * risk_mult
        tp1 = price + atr_val * tp1_mult
        tp2 = price + atr_val * tp2_mult
    else:  # SELL signals
        sl  = price + atr_val * risk_mult
        tp1 = price - atr_val * tp1_mult
        tp2 = price - atr_val * tp2_mult

    risk   = abs(price - sl)
    reward = abs(tp1 - price)
    rr     = round(reward / risk, 2) if risk else 0

    return {"sl": sl, "tp1": tp1, "tp2": tp2, "rr": rr}


# ─── Telegram formatter ───────────────────────────────────────────────────────

def _format_telegram(result: dict) -> str:
    signal  = result["signal"]
    sym     = result["symbol"]
    tf      = result["timeframe"].upper()
    price   = result["price"]
    score   = result["score"]
    risk    = result["risk"]
    levels  = result["levels"]
    details = result["details"]

    # Normalise score display 0–10
    strength = min(10, round(abs(score) * 10 / 10, 1))

    lines = [
        f"{EMOJI[signal]} {LABEL[signal]} — {sym}",
        f"💰 Price: {_fmt(price, 6)} USDT",
        f"⏰ Timeframe: {tf}",
        f"📊 Signal Strength: {strength}/10  (raw score: {score:+.1f})",
        f"",
        f"── TREND ──────────────────────────────",
    ]
    for d in details.get("trend", []):
        lines.append(f"  {d}")

    lines += ["", "── MOMENTUM ───────────────────────────"]
    for d in details.get("momentum", []):
        lines.append(f"  {d}")

    lines += ["", "── VOLUME ─────────────────────────────"]
    for d in details.get("volume", []):
        lines.append(f"  {d}")

    lines += ["", "── VOLATILITY ─────────────────────────"]
    for d in details.get("volatility", []):
        lines.append(f"  {d}")

    if details.get("candlestick"):
        lines += ["", "── CANDLESTICK ────────────────────────"]
        for d in details["candlestick"]:
            lines.append(f"  {d}")

    if details.get("sentiment"):
        lines += ["", "── MARKET SENTIMENT (USDT.D) ──────────"]
        for d in details["sentiment"]:
            lines.append(f"  {d}")

    lines += ["", "── RISK MANAGEMENT ────────────────────"]
    if signal in (STRONG_BUY, WEAK_BUY):
        lines += [
            f"  🛑 Stop Loss  : {_fmt(risk['sl'], 4)} USDT",
            f"  🎯 TP1        : {_fmt(risk['tp1'], 4)} USDT",
            f"  🎯 TP2        : {_fmt(risk['tp2'], 4)} USDT",
            f"  📐 Risk/Reward: 1:{risk['rr']}",
        ]
    else:
        lines += [
            f"  🛑 Stop Loss  : {_fmt(risk['sl'], 4)} USDT",
            f"  🎯 TP1 (cover): {_fmt(risk['tp1'], 4)} USDT",
            f"  🎯 TP2 (cover): {_fmt(risk['tp2'], 4)} USDT",
            f"  📐 Risk/Reward: 1:{risk['rr']}",
        ]

    lines += ["", "── SUPPORT / RESISTANCE ───────────────"]
    if levels.get("support"):
        lines.append(f"  🟦 Nearest support    : {_fmt(levels['support'], 4)} USDT")
    if levels.get("resistance"):
        lines.append(f"  🟥 Nearest resistance : {_fmt(levels['resistance'], 4)} USDT")
    if levels.get("fib_key") and levels.get("fib_val"):
        lines.append(f"  📍 Fibonacci {levels['fib_key']}      : {_fmt(levels['fib_val'], 4)} USDT")

    for d in details.get("sr", []):
        if d.startswith("📍 Pivot"):
            lines.append(f"  {d}")

    now = datetime.now(timezone.utc)
    lines += [
        f"",
        f"⚠️  This signal requires confirmation — not financial advice.",
        f"🕐 {now.strftime('%H:%M')}  {now.strftime('%d.%m.%Y')} UTC",
    ]

    return "\n".join(lines)


# ─── Main analysis entry point ────────────────────────────────────────────────

def analyze_symbol(
    symbol: str,
    exchange: str = "binance",
    timeframe: str = "1h",
    risk_multiplier: float = 1.5,
    tp1_multiplier: float = 2.0,
    tp2_multiplier: float = 3.5,
    threshold_strong: float = 7.0,
    threshold_weak: float = 4.0,
) -> Optional[dict]:
    """
    Fetch OHLCV, run full TA scoring, return signal dict (or None if NEUTRAL).

    Returns dict:
        symbol, exchange, timeframe, signal, score, price, atr,
        risk {sl, tp1, tp2, rr}, levels {support, resistance, fib_key, fib_val},
        details {trend, momentum, volume, volatility, candlestick, sr},
        telegram_message, timestamp
    """
    try:
        client = make_public_client(exchange)
        ohlcv  = client.fetch_ohlcv(to_ccxt_symbol(symbol), timeframe=timeframe, limit=300)
    except Exception as e:
        log.error(f"[signal] fetch failed {symbol}@{exchange}: {e}")
        return None

    if not ohlcv or len(ohlcv) < 60:
        log.warning(f"[signal] not enough candles for {symbol}")
        return None

    closes  = closes_from_klines(ohlcv)
    highs   = highs_from_klines(ohlcv)
    lows    = lows_from_klines(ohlcv)
    opens   = opens_from_klines(ohlcv)
    volumes = volumes_from_klines(ohlcv)
    price   = closes[-1]

    # ── Fetch USDT Dominance (market sentiment) ───────────────────────────────
    usdt_d = _fetch_usdt_dominance()

    # ── Run all scorers ───────────────────────────────────────────────────────
    s_trend,  d_trend  = _score_trend(highs, lows, closes, volumes)
    s_mom,    d_mom    = _score_momentum(highs, lows, closes, volumes)
    s_vol,    d_vol    = _score_volume(highs, lows, closes, volumes)
    s_vola,   d_vola   = _score_volatility(highs, lows, closes)
    s_candle, d_candle = _score_candlestick(opens, highs, lows, closes)
    s_sr,     d_sr, levels = _score_support_resistance(highs, lows, closes)
    s_sent,   d_sent   = _score_market_sentiment(usdt_d)

    total = s_trend + s_mom + s_vol + s_vola + s_candle + s_sr + s_sent

    # ── Determine signal ──────────────────────────────────────────────────────
    if total >= threshold_strong:
        signal = STRONG_BUY
    elif total >= threshold_weak:
        signal = WEAK_BUY
    elif total <= -threshold_strong:
        signal = STRONG_SELL
    elif total <= -threshold_weak:
        signal = WEAK_SELL
    else:
        signal = NEUTRAL

    # ── ATR-based risk ────────────────────────────────────────────────────────
    atr_val = atr(highs, lows, closes, 14) or (price * 0.01)
    risk = _calculate_risk(price, atr_val, signal, risk_multiplier, tp1_multiplier, tp2_multiplier)

    result = {
        "symbol":    symbol.upper(),
        "exchange":  exchange,
        "timeframe": timeframe,
        "signal":    signal,
        "score":     round(total, 2),
        "price":     price,
        "atr":       round(atr_val, 6),
        "risk":      risk,
        "levels":    levels,
        "usdt_dominance": usdt_d,
        "details": {
            "trend":      d_trend,
            "momentum":   d_mom,
            "volume":     d_vol,
            "volatility": d_vola,
            "candlestick": d_candle,
            "sr":         d_sr,
            "sentiment":  d_sent,
        },
        "score_breakdown": {
            "trend":      s_trend,
            "momentum":   s_mom,
            "volume":     s_vol,
            "volatility": s_vola,
            "candlestick": s_candle,
            "sr":         s_sr,
            "sentiment":  s_sent,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    result["telegram_message"] = _format_telegram(result)
    return result
