"""AI Trading Analysis — powered by Anthropic Claude.

POST /api/ai/analyze   → JSON body, returns SSE stream of analysis text
GET  /api/ai/enabled   → {"enabled": bool}  (no API key → false)
"""
import json
import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
from app.config import settings
from app.core.deps import get_current_user
from app.models.user import User
from app.services.exchange_service import make_public_client, to_ccxt_symbol
from app.services.indicators import (
    closes_from_klines, highs_from_klines, lows_from_klines,
    opens_from_klines, volumes_from_klines,
    sma, ema, rsi, macd, stoch_rsi,
    bb_upper, bb_lower, bb_middle, bb_percent,
    atr, vwap, obv, cmf, mfi, cci, williams_r,
    momentum as mom_indicator, roc, awesome_oscillator,
    supertrend, parabolic_sar, ichimoku,
    market_structure, fibonacci_levels,
    detect_candlestick_patterns,
    donchian_channels, keltner_channels, std_dev,
    _detect_bos, _detect_fvg, _detect_order_block,
    _detect_choch, _detect_premium_discount,
    _detect_liquidity_sweep, _detect_equal_highs_lows,
)

router = APIRouter(prefix="/api/ai", tags=["ai"])


# ─── Request models ─────────────────────────────────────────────────────────

class ConditionIn(BaseModel):
    indicator: str
    period: int = 14
    period2: int = 26
    op: str = "<"
    value: float = 30


class StrategyIn(BaseModel):
    name: Optional[str] = None
    symbols: Optional[List[str]] = None
    timeframe: Optional[str] = None
    tp_percent: Optional[float] = None
    sl_percent: Optional[float] = None
    amount_usdt: Optional[float] = None
    entry_conditions: Optional[List[ConditionIn]] = None
    order_type: Optional[str] = None


class AnalyzeRequest(BaseModel):
    symbol: str = "BTCUSDT"
    exchange: str = "binance"
    timeframe: str = "1h"
    lang: str = "en"
    strategy: Optional[StrategyIn] = None


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _safe(val, digits=2):
    if val is None:
        return "N/A"
    if isinstance(val, bool):
        return "Yes" if val else "No"
    if isinstance(val, float):
        return f"{val:.{digits}f}"
    return str(val)


def _trend_word(val: Optional[float], ref: Optional[float]) -> str:
    if val is None or ref is None:
        return "N/A"
    return "above" if val > ref else "below"


def _rsi_label(r: Optional[float]) -> str:
    if r is None:
        return "N/A"
    if r >= 70:
        return f"{r:.1f} (Overbought ⚠️)"
    if r <= 30:
        return f"{r:.1f} (Oversold 🔥)"
    if r >= 60:
        return f"{r:.1f} (Bullish)"
    if r <= 40:
        return f"{r:.1f} (Bearish)"
    return f"{r:.1f} (Neutral)"


def _build_context(ohlcv: list, symbol: str, timeframe: str,
                   strategy: Optional[StrategyIn] = None) -> str:
    """Build a rich indicator context string for the AI prompt."""
    if len(ohlcv) < 50:
        raise ValueError("Not enough candles (need ≥ 50)")

    closes  = closes_from_klines(ohlcv)
    highs   = highs_from_klines(ohlcv)
    lows    = lows_from_klines(ohlcv)
    opens   = opens_from_klines(ohlcv)
    volumes = volumes_from_klines(ohlcv)

    price = closes[-1]

    # ── Trend MAs ─────────────────────────────────────────────────────────────
    ema9   = ema(closes, 9)
    ema21  = ema(closes, 21)
    ema50  = ema(closes, 50)
    ema200 = ema(closes, 200) if len(closes) >= 200 else None
    sma50  = sma(closes, 50)
    sma200 = sma(closes, 200) if len(closes) >= 200 else None

    # ── Momentum ──────────────────────────────────────────────────────────────
    rsi14    = rsi(closes, 14)
    rsi7     = rsi(closes, 7)
    sr       = stoch_rsi(closes, 14, 14, 3, 3)
    macd_r   = macd(closes, 12, 26, 9)
    cci20    = cci(highs, lows, closes, 20)
    wr14     = williams_r(highs, lows, closes, 14)
    mom10    = mom_indicator(closes, 10)
    roc12    = roc(closes, 12)
    ao       = awesome_oscillator(highs, lows)

    # ── Volatility ─────────────────────────────────────────────────────────────
    atr14    = atr(highs, lows, closes, 14)
    bbu      = bb_upper(closes, 20)
    bbl      = bb_lower(closes, 20)
    bbm      = bb_middle(closes, 20)
    bbpct    = bb_percent(closes, 20)
    stddev20 = std_dev(closes, 20)
    kc       = keltner_channels(highs, lows, closes, 20, 2.0)
    dc       = donchian_channels(highs, lows, 20)

    # ── Volume ────────────────────────────────────────────────────────────────
    obv_val  = obv(closes, volumes)
    obv_prev = obv(closes[:-5], volumes[:-5])
    obv_trend = "Rising 📈" if (obv_val or 0) > (obv_prev or 0) else "Falling 📉"
    cmf20    = cmf(highs, lows, closes, volumes, 20)
    mfi14    = mfi(highs, lows, closes, volumes, 14)
    vwap20   = vwap(highs, lows, closes, volumes, 20)
    vol_ma20 = sma(volumes, 20)
    vol_now  = volumes[-1]
    vol_rel  = f"{vol_now / vol_ma20 * 100:.0f}% of avg" if vol_ma20 else "N/A"

    # ── SuperTrend & SAR ──────────────────────────────────────────────────────
    st       = supertrend(highs, lows, closes, 10, 3.0)
    psar     = parabolic_sar(highs, lows, closes)

    # ── Ichimoku ──────────────────────────────────────────────────────────────
    ichi     = ichimoku(highs, lows, closes)

    # ── SMC ───────────────────────────────────────────────────────────────────
    bos      = _detect_bos(highs, lows, closes, 30)
    choch    = _detect_choch(highs, lows, closes, 50)
    fvg      = _detect_fvg(highs, lows)
    ob       = _detect_order_block(opens, highs, lows, closes, 20)
    pd       = _detect_premium_discount(highs, lows, closes, 50)
    sweep    = _detect_liquidity_sweep(highs, lows, closes, 30)
    ehl      = _detect_equal_highs_lows(highs, lows, 30)

    # ── Market Structure ──────────────────────────────────────────────────────
    ms       = market_structure(highs, lows, closes, 50)
    fibs     = fibonacci_levels(highs, lows, 50)

    # ── Candlestick patterns ──────────────────────────────────────────────────
    patterns = detect_candlestick_patterns(opens, highs, lows, closes)
    active_patterns = [k.replace("_", " ").title() for k, v in patterns.items() if v]

    # ── Price action summary (last 5 candles) ─────────────────────────────────
    candle_summary = []
    for i in range(-5, 0):
        o, h, l, c = opens[i], highs[i], lows[i], closes[i]
        direction = "🟢" if c >= o else "🔴"
        body_pct = abs(c - o) / o * 100 if o else 0
        candle_summary.append(
            f"  {direction} O:{o:.4f} H:{h:.4f} L:{l:.4f} C:{c:.4f} ({body_pct:+.2f}%)"
        )

    # ── 24h stats ─────────────────────────────────────────────────────────────
    high_24 = max(highs[-24:]) if len(highs) >= 24 else max(highs)
    low_24  = min(lows[-24:])  if len(lows)  >= 24 else min(lows)
    chg_24  = (closes[-1] - closes[-24]) / closes[-24] * 100 if len(closes) >= 24 else 0

    # ─────────────────────────────────────────────────────────────────────────
    lines = [
        f"═══════════════════════════════════════════════",
        f"  MARKET DATA: {symbol} | {timeframe} | {len(ohlcv)} candles",
        f"═══════════════════════════════════════════════",
        f"",
        f"📌 PRICE ACTION",
        f"  Current Price : {price:.6g}",
        f"  24h High      : {high_24:.6g}",
        f"  24h Low       : {low_24:.6g}",
        f"  24h Change    : {chg_24:+.2f}%",
        f"",
        f"📊 LAST 5 CANDLES",
        *candle_summary,
        f"",
        f"📈 TREND — Moving Averages",
        f"  EMA 9         : {_safe(ema9,6)}  | price {_trend_word(price, ema9)} EMA9",
        f"  EMA 21        : {_safe(ema21,6)} | price {_trend_word(price, ema21)} EMA21",
        f"  EMA 50        : {_safe(ema50,6)} | price {_trend_word(price, ema50)} EMA50",
        f"  EMA 200       : {_safe(ema200,6)} | price {_trend_word(price, ema200)} EMA200",
        f"  EMA 9>21      : {'✅ Bullish alignment' if (ema9 or 0) > (ema21 or 0) else '❌ Bearish alignment'}",
        f"  EMA 21>50     : {'✅ Bullish' if (ema21 or 0) > (ema50 or 0) else '❌ Bearish'}",
        f"",
        f"⚡ MOMENTUM",
        f"  RSI 14        : {_rsi_label(rsi14)}",
        f"  RSI 7         : {_rsi_label(rsi7)}",
        f"  StochRSI K    : {_safe(sr['k'] if sr else None,1)}",
        f"  StochRSI D    : {_safe(sr['d'] if sr else None,1)}",
        f"  MACD Line     : {_safe(macd_r['macd'] if macd_r else None,6)}",
        f"  MACD Signal   : {_safe(macd_r['signal'] if macd_r else None,6)}",
        f"  MACD Histogram: {_safe(macd_r['histogram'] if macd_r else None,6)} {'📈 Rising' if (macd_r or {}).get('histogram',0) and (macd_r['histogram']>0) else '📉 Falling' if macd_r and macd_r.get('histogram') else ''}",
        f"  CCI 20        : {_safe(cci20,1)}",
        f"  Williams %R   : {_safe(wr14,1)}",
        f"  Momentum 10   : {_safe(mom10,6)}",
        f"  ROC 12        : {_safe(roc12,2)}%",
        f"  Awesome Osc   : {_safe(ao,6)}",
        f"",
        f"📦 VOLUME",
        f"  Volume (now)  : {vol_now:.0f}  ({vol_rel})",
        f"  OBV Trend     : {obv_trend}",
        f"  CMF 20        : {_safe(cmf20,4)} {'Bullish' if (cmf20 or 0) > 0 else 'Bearish'}",
        f"  MFI 14        : {_safe(mfi14,1)} {'(Overbought)' if (mfi14 or 0) > 80 else '(Oversold)' if (mfi14 or 0) < 20 else ''}",
        f"  VWAP          : {_safe(vwap20,6)}",
        f"",
        f"🌊 VOLATILITY",
        f"  ATR 14        : {_safe(atr14,6)} ({_safe((atr14 or 0)/price*100 if price else None, 2)}% of price)",
        f"  BB Upper      : {_safe(bbu,6)}",
        f"  BB Middle     : {_safe(bbm,6)}",
        f"  BB Lower      : {_safe(bbl,6)}",
        f"  BB %B         : {_safe(bbpct,3)} (0=lower, 1=upper band)",
        f"  Std Dev       : {_safe(stddev20,6)}",
        f"  Keltner Upper : {_safe(kc['upper'] if kc else None,6)}",
        f"  Keltner Lower : {_safe(kc['lower'] if kc else None,6)}",
        f"  Donchian High : {_safe(dc['upper'] if dc else None,6)}",
        f"  Donchian Low  : {_safe(dc['lower'] if dc else None,6)}",
        f"",
        f"🔮 TREND SIGNALS",
        f"  SuperTrend    : {'🟢 BULLISH' if st and st['bullish'] else '🔴 BEARISH' if st else 'N/A'}  line={_safe(st['line'] if st else None,6)}",
        f"  Parabolic SAR : {'🟢 BULLISH' if psar and psar['bullish'] else '🔴 BEARISH' if psar else 'N/A'}  sar={_safe(psar['sar'] if psar else None,6)}",
    ]

    if ichi:
        lines += [
            f"  Ichimoku      : {'🟢 Above cloud' if ichi['above_cloud'] else '🔴 Below cloud' if ichi['below_cloud'] else '⚪ Inside cloud'}",
            f"    Tenkan-sen  : {_safe(ichi['tenkan_sen'],6)}",
            f"    Kijun-sen   : {_safe(ichi['kijun_sen'],6)}",
        ]

    lines += [
        f"",
        f"🏗️ MARKET STRUCTURE",
        f"  Trend         : {ms['trend'].upper() if ms else 'N/A'}",
        f"  Higher High   : {_safe(ms['hh'] if ms else None)}",
        f"  Higher Low    : {_safe(ms['hl'] if ms else None)}",
        f"  Lower High    : {_safe(ms['lh'] if ms else None)}",
        f"  Lower Low     : {_safe(ms['ll'] if ms else None)}",
        f"  Trend Shift ↑ : {_safe(ms['trend_shift_bullish'] if ms else None)}",
        f"  Trend Shift ↓ : {_safe(ms['trend_shift_bearish'] if ms else None)}",
        f"",
        f"💎 SMART MONEY CONCEPTS (SMC)",
        f"  Bullish BOS   : {_safe(bos['bullish_bos'] if bos else None)}",
        f"  Bearish BOS   : {_safe(bos['bearish_bos'] if bos else None)}",
        f"  Bullish CHoCH : {_safe(choch['bullish_choch'] if choch else None)}",
        f"  Bearish CHoCH : {_safe(choch['bearish_choch'] if choch else None)}",
        f"  Bullish FVG   : {_safe(fvg['bullish_fvg'] if fvg else None)}" +
            (f"  [{_safe(fvg['fvg_low'],4)} – {_safe(fvg['fvg_high'],4)}]" if fvg and fvg.get('bullish_fvg') else ""),
        f"  Bearish FVG   : {_safe(fvg['bearish_fvg'] if fvg else None)}" +
            (f"  [{_safe(fvg['fvg_low'],4)} – {_safe(fvg['fvg_high'],4)}]" if fvg and fvg.get('bearish_fvg') else ""),
        f"  Bullish OB    : {_safe(ob['bullish_ob'] if ob else None)}" +
            (f"  [{_safe(ob['ob_low'],4)} – {_safe(ob['ob_high'],4)}]" if ob and ob.get('bullish_ob') else ""),
        f"  Bearish OB    : {_safe(ob['bearish_ob'] if ob else None)}" +
            (f"  [{_safe(ob['ob_low'],4)} – {_safe(ob['ob_high'],4)}]" if ob and ob.get('bearish_ob') else ""),
        f"  Zone          : {'PREMIUM (sell zone)' if pd and pd['in_premium'] else 'DISCOUNT (buy zone)'}  EQ={_safe(pd['equilibrium'] if pd else None,4)}",
        f"  Equal Highs   : {_safe(ehl['equal_highs'] if ehl else None)}",
        f"  Equal Lows    : {_safe(ehl['equal_lows'] if ehl else None)}",
        f"  Bullish Sweep : {_safe(sweep['bullish_sweep'] if sweep else None)}",
        f"  Bearish Sweep : {_safe(sweep['bearish_sweep'] if sweep else None)}",
        f"",
        f"📐 FIBONACCI LEVELS (50-bar range)",
    ]

    if fibs:
        for k, v in fibs.items():
            if k.startswith("fib_"):
            # Mark current price proximity
                near = " ← PRICE HERE" if abs(price - v) / price < 0.003 else ""
                lines.append(f"  {k.upper():12}: {v:.6g}{near}")

    lines += [
        f"",
        f"🕯️ CANDLESTICK PATTERNS (last 3 bars)",
        f"  {'  '.join(active_patterns) if active_patterns else 'None detected'}",
    ]

    if strategy:
        lines += [
            f"",
            f"═══════════════════════════════════════════════",
            f"  USER STRATEGY: {strategy.name or 'Unnamed'}",
            f"═══════════════════════════════════════════════",
            f"  Timeframe    : {strategy.timeframe or 'N/A'}",
            f"  TP           : {strategy.tp_percent or 'N/A'}%",
            f"  SL           : {strategy.sl_percent or 'N/A'}%",
            f"  Order Type   : {strategy.order_type or 'market'}",
            f"  Amount       : {strategy.amount_usdt or 'N/A'} USDT",
            f"  Conditions   :",
        ]
        if strategy.entry_conditions:
            for c in strategy.entry_conditions:
                lines.append(f"    {c.indicator} ({c.period}) {c.op} {c.value}")
        else:
            lines.append(f"    No conditions (buys every cycle)")

    return "\n".join(lines)


# ─── SSE streaming helpers ────────────────────────────────────────────────────

LANG_INSTRUCTIONS = {
    "en": "Respond entirely in English.",
    "az": "Bütün cavabı Azərbaycan dilində verin.",
    "tr": "Tüm yanıtı Türkçe olarak verin.",
    "ru": "Отвечайте полностью на русском языке.",
    "ar": "أجب بالكامل باللغة العربية.",
}

SYSTEM_PROMPT = """\
You are an expert cryptocurrency and financial markets analyst with 15+ years of experience.
You specialize in technical analysis, Smart Money Concepts (SMC), price action, risk management, and algorithmic trading strategy design.
Your analysis is objective, data-driven, professional, and actionable.
You clearly distinguish between bullish and bearish signals and always provide specific price levels.
"""

USER_PROMPT_TEMPLATE = """\
Analyze the following real-time cryptocurrency market data and provide a comprehensive professional trading analysis.

{context}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PROVIDE YOUR ANALYSIS IN THE FOLLOWING STRUCTURE:

## 📊 Market Overview
Brief summary of current market condition, trend strength, and momentum.

## 🎯 Overall Signal
State clearly: **STRONG BUY** / **BUY** / **NEUTRAL** / **SELL** / **STRONG SELL**
Include a confidence percentage (0–100%).

## 📈 Technical Analysis
Analyze the most important indicator readings. What do RSI, MACD, Stoch RSI, Bollinger Bands, and SuperTrend say? Are they aligned or conflicting?

## 🏗️ Market Structure & SMC
Analyze trend structure (HH/HL/LH/LL), order blocks, fair value gaps (FVG), BOS/CHoCH, premium/discount zone. What are the key support and resistance levels?

## 🕯️ Price Action & Patterns
Comment on recent candlestick patterns detected. What do they signal?

## 🎯 Entry Zone
Suggest a specific entry price range. Is it a good time to enter NOW or wait?

## 💰 Take Profit Levels
TP1: (conservative)
TP2: (moderate)
TP3: (ambitious)

## 🛑 Stop Loss
Recommended stop-loss level and the technical reason for placing it there.

## ⚖️ Risk/Reward Assessment
Calculate R:R ratio. Describe the key risks (e.g. macro, liquidity, overextension).

{strategy_section}

## 💡 Best Strategy for This Coin
Suggest the optimal entry conditions (indicators + values) for trading this coin in the current market regime.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{lang_instruction}
"""

STRATEGY_SECTION = """\
## 🔧 Strategy Review & Improvements
Review the user's current strategy above. List:
- What's working well ✅
- What should be improved ❌
- Specific suggested changes (indicator values, TP/SL levels, conditions)
"""


async def _stream_anthropic(context: str, lang: str, has_strategy: bool):
    """Yield SSE-formatted chunks from Anthropic streaming API."""
    if not settings.ANTHROPIC_API_KEY:
        yield 'data: {"text":"⚠️ AI analysis is not configured. Please add ANTHROPIC_API_KEY to your .env file."}\n\n'
        yield 'data: [DONE]\n\n'
        return

    prompt = USER_PROMPT_TEMPLATE.format(
        context=context,
        strategy_section=STRATEGY_SECTION if has_strategy else "",
        lang_instruction=LANG_INSTRUCTIONS.get(lang, LANG_INSTRUCTIONS["en"]),
    )

    payload = {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 2500,
        "stream": True,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": prompt}],
    }

    headers = {
        "x-api-key": settings.ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            async with client.stream(
                "POST",
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload,
            ) as resp:
                if resp.status_code != 200:
                    body = await resp.aread()
                    err = body.decode()[:200]
                    yield f'data: {{"text":"❌ Anthropic API error {resp.status_code}: {err}"}}\n\n'
                    yield 'data: [DONE]\n\n'
                    return

                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    raw = line[6:]
                    if raw == "[DONE]":
                        break
                    try:
                        event = json.loads(raw)
                        if event.get("type") == "content_block_delta":
                            text = event.get("delta", {}).get("text", "")
                            if text:
                                yield f"data: {json.dumps({'text': text})}\n\n"
                    except Exception:
                        pass

    except Exception as e:
        yield f'data: {{"text":"❌ Connection error: {str(e)[:120]}"}}\n\n'

    yield 'data: [DONE]\n\n'


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.get("/enabled")
def ai_enabled(user: User = Depends(get_current_user)):
    """Check if AI analysis is configured."""
    return {"enabled": bool(settings.ANTHROPIC_API_KEY)}


@router.post("/analyze")
async def analyze(req: AnalyzeRequest, user: User = Depends(get_current_user)):
    """Stream a comprehensive AI trading analysis for the given symbol."""
    # Fetch OHLCV from exchange (public endpoint, no API key needed)
    try:
        client = make_public_client(req.exchange)
        # Fetch 300 candles for a rich indicator base
        ohlcv = client.fetch_ohlcv(
            to_ccxt_symbol(req.symbol),
            timeframe=req.timeframe,
            limit=300,
        )
    except Exception as e:
        raise HTTPException(400, f"Could not fetch {req.symbol} from {req.exchange}: {str(e)[:100]}")

    if not ohlcv or len(ohlcv) < 50:
        raise HTTPException(400, f"Insufficient data for {req.symbol}")

    # Build context
    try:
        context = _build_context(ohlcv, req.symbol, req.timeframe, req.strategy)
    except Exception as e:
        raise HTTPException(400, f"Indicator calculation failed: {e}")

    return StreamingResponse(
        _stream_anthropic(context, req.lang, has_strategy=req.strategy is not None),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering
        },
    )
