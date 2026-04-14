"""Pure-Python technical indicators for the strategy engine.

OHLCV format: [[timestamp, open, high, low, close, volume], ...]
indices:        0           1     2     3    4      5

Condition format:
    {
        "indicator": "RSI",
        "period":    14,
        "period2":   26,        # optional – 2nd period for crossover/MACD
        "op":        "<",       # < | <= | > | >= | == | DETECTED | CROSS_ABOVE | CROSS_BELOW | PRICE_ABOVE | PRICE_BELOW
        "value":     30         # numeric target; unused for DETECTED
    }
"""
from typing import List, Optional, Tuple


# ─── OHLCV Helpers ─────────────────────────────────────────────────────────────

def opens_from_klines(ohlcv: List[list]) -> List[float]:
    return [float(k[1]) for k in ohlcv]

def closes_from_klines(ohlcv: List[list]) -> List[float]:
    return [float(k[4]) for k in ohlcv]

def highs_from_klines(ohlcv: List[list]) -> List[float]:
    return [float(k[2]) for k in ohlcv]

def lows_from_klines(ohlcv: List[list]) -> List[float]:
    return [float(k[3]) for k in ohlcv]

def volumes_from_klines(ohlcv: List[list]) -> List[float]:
    return [float(k[5]) for k in ohlcv]


# ═══════════════════════════════════════════════════════════════════════════════
#  TREND INDICATORS
# ═══════════════════════════════════════════════════════════════════════════════

def sma(values: List[float], period: int) -> Optional[float]:
    """Simple Moving Average."""
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def _sma_series(values: List[float], period: int) -> List[Optional[float]]:
    """Return SMA at every bar (None for insufficient data)."""
    result = []
    for i in range(len(values)):
        if i + 1 < period:
            result.append(None)
        else:
            result.append(sum(values[i + 1 - period:i + 1]) / period)
    return result


def ema(values: List[float], period: int) -> Optional[float]:
    """Exponential Moving Average."""
    if len(values) < period:
        return None
    k = 2 / (period + 1)
    e = sum(values[:period]) / period
    for v in values[period:]:
        e = v * k + e * (1 - k)
    return e


def _ema_series(values: List[float], period: int) -> List[Optional[float]]:
    """EMA at every bar."""
    result = [None] * (period - 1)
    if len(values) < period:
        return [None] * len(values)
    k = 2 / (period + 1)
    e = sum(values[:period]) / period
    result.append(e)
    for v in values[period:]:
        e = v * k + e * (1 - k)
        result.append(e)
    return result


def wma(values: List[float], period: int) -> Optional[float]:
    """Weighted Moving Average — linear weights (most recent = highest)."""
    if len(values) < period:
        return None
    w = list(range(1, period + 1))
    window = values[-period:]
    return sum(window[i] * w[i] for i in range(period)) / sum(w)


def _wma_series(values: List[float], period: int) -> List[Optional[float]]:
    result = []
    w = list(range(1, period + 1))
    wsum = sum(w)
    for i in range(len(values)):
        if i + 1 < period:
            result.append(None)
        else:
            win = values[i + 1 - period:i + 1]
            result.append(sum(win[j] * w[j] for j in range(period)) / wsum)
    return result


def vwma(closes: List[float], volumes: List[float], period: int) -> Optional[float]:
    """Volume Weighted Moving Average."""
    if len(closes) < period:
        return None
    c = closes[-period:]
    v = volumes[-period:]
    total_vol = sum(v)
    if total_vol == 0:
        return sma(closes, period)
    return sum(c[i] * v[i] for i in range(period)) / total_vol


def hma(values: List[float], period: int) -> Optional[float]:
    """Hull Moving Average = WMA(2*WMA(n/2) - WMA(n), sqrt(n))."""
    p2 = max(2, period // 2)
    sqrtn = max(2, int(period ** 0.5))
    if len(values) < period:
        return None
    wma_half = wma(values, p2)
    wma_full = wma(values, period)
    if wma_half is None or wma_full is None:
        return None
    # Build synthetic series for the final WMA
    series = _wma_series(values, p2)
    series_full = _wma_series(values, period)
    synthetic = []
    for h, f in zip(series, series_full):
        if h is None or f is None:
            synthetic.append(None)
        else:
            synthetic.append(2 * h - f)
    clean = [x for x in synthetic if x is not None]
    if len(clean) < sqrtn:
        return None
    return wma(clean, sqrtn)


def dema(values: List[float], period: int) -> Optional[float]:
    """Double Exponential Moving Average = 2*EMA - EMA(EMA)."""
    e1 = _ema_series(values, period)
    clean_e1 = [x for x in e1 if x is not None]
    if len(clean_e1) < period:
        return None
    e2_val = ema(clean_e1, period)
    e1_val = e1[-1]
    if e1_val is None or e2_val is None:
        return None
    return 2 * e1_val - e2_val


def tema(values: List[float], period: int) -> Optional[float]:
    """Triple Exponential Moving Average = 3*EMA - 3*EMA(EMA) + EMA(EMA(EMA))."""
    e1 = _ema_series(values, period)
    clean_e1 = [x for x in e1 if x is not None]
    if len(clean_e1) < period:
        return None
    e2 = _ema_series(clean_e1, period)
    clean_e2 = [x for x in e2 if x is not None]
    if len(clean_e2) < period:
        return None
    e3_val = ema(clean_e2, period)
    e2_val = e2[-1]
    e1_val = e1[-1]
    if e1_val is None or e2_val is None or e3_val is None:
        return None
    return 3 * e1_val - 3 * e2_val + e3_val


def kama(values: List[float], period: int = 10, fast: int = 2, slow: int = 30) -> Optional[float]:
    """Kaufman's Adaptive Moving Average."""
    if len(values) < period + 1:
        return None
    fast_sc = 2 / (fast + 1)
    slow_sc = 2 / (slow + 1)
    kama_val = values[period - 1]
    for i in range(period, len(values)):
        direction = abs(values[i] - values[i - period])
        volatility = sum(abs(values[j] - values[j - 1]) for j in range(i - period + 1, i + 1))
        er = direction / volatility if volatility != 0 else 0
        sc = (er * (fast_sc - slow_sc) + slow_sc) ** 2
        kama_val = kama_val + sc * (values[i] - kama_val)
    return kama_val


def ichimoku(highs: List[float], lows: List[float], closes: List[float],
             tenkan: int = 9, kijun: int = 26, senkou_b: int = 52) -> Optional[dict]:
    """Ichimoku Cloud components.
    Returns: tenkan_sen, kijun_sen, senkou_a, senkou_b, chikou_span
    """
    def mid(h, l, n, idx):
        if idx < n - 1:
            return None
        return (max(h[idx - n + 1:idx + 1]) + min(l[idx - n + 1:idx + 1])) / 2

    n = len(closes)
    if n < senkou_b:
        return None
    i = n - 1
    ts = mid(highs, lows, tenkan, i)
    ks = mid(highs, lows, kijun, i)
    if ts is None or ks is None:
        return None
    sa = (ts + ks) / 2
    sb_idx = max(0, i - kijun)
    if sb_idx < senkou_b - 1:
        return None
    sb = mid(highs, lows, senkou_b, sb_idx)
    chikou = closes[i - kijun] if i >= kijun else None
    if sb is None:
        return None
    return {
        "tenkan_sen": round(ts, 8),
        "kijun_sen": round(ks, 8),
        "senkou_a": round(sa, 8),
        "senkou_b": round(sb, 8),
        "chikou_span": round(chikou, 8) if chikou else None,
        "above_cloud": closes[-1] > max(sa, sb),
        "below_cloud": closes[-1] < min(sa, sb),
    }


def supertrend(highs: List[float], lows: List[float], closes: List[float],
               period: int = 10, multiplier: float = 3.0) -> Optional[dict]:
    """SuperTrend indicator. Returns direction (1=up/bullish, -1=down/bearish) and line value."""
    n = len(closes)
    if n < period + 2:
        return None

    atr_vals = []
    for i in range(1, n):
        h, l, pc = highs[i], lows[i], closes[i - 1]
        atr_vals.append(max(h - l, abs(h - pc), abs(l - pc)))
    if len(atr_vals) < period:
        return None

    # Wilder ATR
    atr_val = sum(atr_vals[:period]) / period
    atr_list = [atr_val]
    for tr in atr_vals[period:]:
        atr_val = (atr_val * (period - 1) + tr) / period
        atr_list.append(atr_val)

    # Compute upper/lower bands and direction
    direction = 1
    st_line = None
    up_prev = (highs[period] + lows[period]) / 2 + multiplier * atr_list[0]
    dn_prev = (highs[period] + lows[period]) / 2 - multiplier * atr_list[0]

    for i in range(1, len(atr_list)):
        idx = period + i
        if idx >= n:
            break
        hl2 = (highs[idx] + lows[idx]) / 2
        up = hl2 + multiplier * atr_list[i]
        dn = hl2 - multiplier * atr_list[i]
        # Adjust bands
        dn = max(dn, dn_prev) if closes[idx - 1] > dn_prev else dn
        up = min(up, up_prev) if closes[idx - 1] < up_prev else up
        if direction == 1:
            direction = -1 if closes[idx] < dn else 1
            st_line = dn
        else:
            direction = 1 if closes[idx] > up else -1
            st_line = up
        up_prev, dn_prev = up, dn

    return {"direction": direction, "line": round(st_line, 8) if st_line else None,
            "bullish": direction == 1}


def parabolic_sar(highs: List[float], lows: List[float], closes: List[float],
                  step: float = 0.02, max_step: float = 0.2) -> Optional[dict]:
    """Parabolic SAR. Returns sar value and trend direction."""
    if len(closes) < 3:
        return None
    af = step
    rising = closes[1] > closes[0]
    sar = lows[0] if rising else highs[0]
    ep = highs[0] if rising else lows[0]

    for i in range(1, len(closes)):
        prev_sar = sar
        sar = prev_sar + af * (ep - prev_sar)
        if rising:
            sar = min(sar, lows[max(0, i - 1)], lows[max(0, i - 2)])
            if highs[i] > ep:
                ep = highs[i]
                af = min(af + step, max_step)
            if lows[i] < sar:
                rising = False
                sar = ep
                ep = lows[i]
                af = step
        else:
            sar = max(sar, highs[max(0, i - 1)], highs[max(0, i - 2)])
            if lows[i] < ep:
                ep = lows[i]
                af = min(af + step, max_step)
            if highs[i] > sar:
                rising = True
                sar = ep
                ep = highs[i]
                af = step

    return {"sar": round(sar, 8), "rising": rising,
            "bullish": rising, "price_above_sar": closes[-1] > sar}


# ═══════════════════════════════════════════════════════════════════════════════
#  MOMENTUM INDICATORS
# ═══════════════════════════════════════════════════════════════════════════════

def rsi(values: List[float], period: int = 14) -> Optional[float]:
    """Relative Strength Index."""
    if len(values) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, period + 1):
        d = values[i] - values[i - 1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    for i in range(period + 1, len(values)):
        d = values[i] - values[i - 1]
        avg_gain = (avg_gain * (period - 1) + max(d, 0)) / period
        avg_loss = (avg_loss * (period - 1) + max(-d, 0)) / period
    if avg_loss == 0:
        return 100.0
    return 100 - (100 / (1 + avg_gain / avg_loss))


def stoch_rsi(values: List[float], rsi_period: int = 14, stoch_period: int = 14,
              smooth_k: int = 3, smooth_d: int = 3) -> Optional[dict]:
    """Stochastic RSI: oscillator applied to RSI values.
    Returns k (fast) and d (slow) in range [0, 100].
    """
    min_len = rsi_period + stoch_period + smooth_k + smooth_d + 5
    if len(values) < min_len:
        return None
    # Build RSI series
    rsi_vals = []
    for i in range(rsi_period, len(values)):
        r = rsi(values[:i + 1], rsi_period)
        if r is not None:
            rsi_vals.append(r)
    if len(rsi_vals) < stoch_period + smooth_k:
        return None
    # StochRSI raw %K
    raw_k = []
    for i in range(stoch_period - 1, len(rsi_vals)):
        window = rsi_vals[i - stoch_period + 1:i + 1]
        rsi_max = max(window)
        rsi_min = min(window)
        if rsi_max == rsi_min:
            raw_k.append(50.0)
        else:
            raw_k.append((rsi_vals[i] - rsi_min) / (rsi_max - rsi_min) * 100)
    if len(raw_k) < smooth_k:
        return None
    k_val = sum(raw_k[-smooth_k:]) / smooth_k
    if len(raw_k) < smooth_k + smooth_d - 1:
        return None
    d_series = []
    for i in range(smooth_d):
        start = len(raw_k) - smooth_k - smooth_d + 1 + i
        end = start + smooth_k
        d_series.append(sum(raw_k[start:end]) / smooth_k)
    d_val = sum(d_series[-smooth_d:]) / smooth_d if len(d_series) >= smooth_d else d_series[-1]
    return {"k": round(k_val, 4), "d": round(d_val, 4)}


def macd(values: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Optional[dict]:
    """MACD: returns macd line, signal line, and histogram."""
    if len(values) < slow + signal:
        return None
    ema_fast_series = _ema_series(values, fast)
    ema_slow_series = _ema_series(values, slow)
    macd_series = []
    for f, s in zip(ema_fast_series, ema_slow_series):
        if f is None or s is None:
            macd_series.append(None)
        else:
            macd_series.append(f - s)
    clean_macd = [x for x in macd_series if x is not None]
    if len(clean_macd) < signal:
        return None
    sig = ema(clean_macd, signal)
    macd_val = clean_macd[-1]
    hist = macd_val - sig if sig is not None else None
    return {
        "macd": round(macd_val, 8),
        "signal": round(sig, 8) if sig else None,
        "histogram": round(hist, 8) if hist is not None else None,
    }


def macd_line(values: List[float], period: int = 26) -> Optional[float]:
    """Returns just the MACD line value (EMA12 - EMA26)."""
    result = macd(values, fast=12, slow=period)
    return result["macd"] if result else None


def stoch_k(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> Optional[float]:
    """Stochastic %K."""
    if len(closes) < period:
        return None
    hh = max(highs[-period:])
    ll = min(lows[-period:])
    if hh == ll:
        return 50.0
    return (closes[-1] - ll) / (hh - ll) * 100


def stoch_d(highs: List[float], lows: List[float], closes: List[float], period: int = 14, smooth: int = 3) -> Optional[float]:
    """Stochastic %D = SMA(3) of %K."""
    ks = []
    for i in range(smooth):
        idx = len(closes) - smooth + i + 1
        if idx < period:
            return None
        k = stoch_k(highs[:idx], lows[:idx], closes[:idx], period)
        if k is None:
            return None
        ks.append(k)
    return sum(ks) / len(ks) if ks else None


def cci(highs: List[float], lows: List[float], closes: List[float], period: int = 20) -> Optional[float]:
    """Commodity Channel Index."""
    if len(closes) < period:
        return None
    typical = [(highs[i] + lows[i] + closes[i]) / 3 for i in range(len(closes))]
    window = typical[-period:]
    mean = sum(window) / period
    md = sum(abs(x - mean) for x in window) / period
    if md == 0:
        return 0.0
    return (typical[-1] - mean) / (0.015 * md)


def williams_r(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> Optional[float]:
    """Williams %R: -100 = oversold, 0 = overbought."""
    if len(closes) < period:
        return None
    hh = max(highs[-period:])
    ll = min(lows[-period:])
    if hh == ll:
        return -50.0
    return (hh - closes[-1]) / (hh - ll) * -100


def momentum(values: List[float], period: int = 10) -> Optional[float]:
    """Momentum = close - close[n periods ago]. Positive = bullish."""
    if len(values) < period + 1:
        return None
    return values[-1] - values[-period - 1]


def roc(values: List[float], period: int = 12) -> Optional[float]:
    """Rate of Change = (close - close[n]) / close[n] * 100."""
    if len(values) < period + 1:
        return None
    prev = values[-period - 1]
    if prev == 0:
        return 0.0
    return (values[-1] - prev) / prev * 100


def ultimate_oscillator(highs: List[float], lows: List[float], closes: List[float],
                        p1: int = 7, p2: int = 14, p3: int = 28) -> Optional[float]:
    """Ultimate Oscillator (Larry Williams). Range 0-100."""
    n = len(closes)
    if n < p3 + 1:
        return None
    bp_list, tr_list = [], []
    for i in range(1, n):
        pc = closes[i - 1]
        bp_list.append(closes[i] - min(lows[i], pc))
        tr_list.append(max(highs[i], pc) - min(lows[i], pc))

    def avg_bp_tr(period):
        bp = sum(bp_list[-period:])
        tr = sum(tr_list[-period:])
        return bp / tr if tr != 0 else 0

    a1 = avg_bp_tr(p1)
    a2 = avg_bp_tr(p2)
    a3 = avg_bp_tr(p3)
    return 100 * (4 * a1 + 2 * a2 + a3) / 7


def awesome_oscillator(highs: List[float], lows: List[float]) -> Optional[float]:
    """Awesome Oscillator = SMA(5) of midpoints - SMA(34) of midpoints."""
    if len(highs) < 34:
        return None
    mids = [(highs[i] + lows[i]) / 2 for i in range(len(highs))]
    s5 = sma(mids, 5)
    s34 = sma(mids, 34)
    if s5 is None or s34 is None:
        return None
    return s5 - s34


# ═══════════════════════════════════════════════════════════════════════════════
#  VOLUME INDICATORS
# ═══════════════════════════════════════════════════════════════════════════════

def obv(closes: List[float], volumes: List[float]) -> Optional[float]:
    """On Balance Volume (cumulative)."""
    if len(closes) < 2:
        return None
    total = volumes[0]
    for i in range(1, len(closes)):
        if closes[i] > closes[i - 1]:
            total += volumes[i]
        elif closes[i] < closes[i - 1]:
            total -= volumes[i]
    return total


def vwap(highs: List[float], lows: List[float], closes: List[float], volumes: List[float],
         period: int = 20) -> Optional[float]:
    """VWAP over last `period` bars."""
    n = min(period, len(closes))
    if n < 1:
        return None
    typ = [(highs[-n + i] + lows[-n + i] + closes[-n + i]) / 3 for i in range(n)]
    vol = volumes[-n:]
    total_vol = sum(vol)
    if total_vol == 0:
        return closes[-1]
    return sum(t * v for t, v in zip(typ, vol)) / total_vol


def ad_line(highs: List[float], lows: List[float], closes: List[float], volumes: List[float]) -> Optional[float]:
    """Accumulation/Distribution Line (Chaikin)."""
    if len(closes) < 1:
        return None
    total = 0.0
    for i in range(len(closes)):
        hl = highs[i] - lows[i]
        if hl == 0:
            clv = 0.0
        else:
            clv = ((closes[i] - lows[i]) - (highs[i] - closes[i])) / hl
        total += clv * volumes[i]
    return total


def cmf(highs: List[float], lows: List[float], closes: List[float], volumes: List[float],
        period: int = 20) -> Optional[float]:
    """Chaikin Money Flow: range [-1, 1]. Positive = buying pressure."""
    if len(closes) < period:
        return None
    mfv_sum = 0.0
    vol_sum = 0.0
    for i in range(-period, 0):
        hl = highs[i] - lows[i]
        clv = ((closes[i] - lows[i]) - (highs[i] - closes[i])) / hl if hl != 0 else 0
        mfv_sum += clv * volumes[i]
        vol_sum += volumes[i]
    if vol_sum == 0:
        return 0.0
    return mfv_sum / vol_sum


def mfi(highs: List[float], lows: List[float], closes: List[float], volumes: List[float],
        period: int = 14) -> Optional[float]:
    """Money Flow Index (volume-weighted RSI). Range 0-100."""
    if len(closes) < period + 1:
        return None
    typical = [(highs[i] + lows[i] + closes[i]) / 3 for i in range(len(closes))]
    pos_mf, neg_mf = 0.0, 0.0
    for i in range(-period, 0):
        raw_mf = typical[i] * volumes[i]
        if typical[i] > typical[i - 1]:
            pos_mf += raw_mf
        else:
            neg_mf += raw_mf
    if neg_mf == 0:
        return 100.0
    mfr = pos_mf / neg_mf
    return 100 - 100 / (1 + mfr)


def volume_oscillator(volumes: List[float], fast: int = 5, slow: int = 10) -> Optional[float]:
    """Volume Oscillator = (fast_vol_ema - slow_vol_ema) / slow_vol_ema * 100."""
    fast_val = ema(volumes, fast)
    slow_val = ema(volumes, slow)
    if fast_val is None or slow_val is None or slow_val == 0:
        return None
    return (fast_val - slow_val) / slow_val * 100


# ═══════════════════════════════════════════════════════════════════════════════
#  VOLATILITY INDICATORS
# ═══════════════════════════════════════════════════════════════════════════════

def bb_upper(values: List[float], period: int = 20, std_dev: float = 2.0) -> Optional[float]:
    """Bollinger Band upper."""
    if len(values) < period:
        return None
    window = values[-period:]
    m = sum(window) / period
    std = (sum((x - m) ** 2 for x in window) / period) ** 0.5
    return m + std_dev * std


def bb_lower(values: List[float], period: int = 20, std_dev: float = 2.0) -> Optional[float]:
    """Bollinger Band lower."""
    if len(values) < period:
        return None
    window = values[-period:]
    m = sum(window) / period
    std = (sum((x - m) ** 2 for x in window) / period) ** 0.5
    return m - std_dev * std


def bb_middle(values: List[float], period: int = 20) -> Optional[float]:
    return sma(values, period)


def bb_percent(values: List[float], period: int = 20) -> Optional[float]:
    """%B: 0=lower band, 1=upper band."""
    u = bb_upper(values, period)
    l = bb_lower(values, period)
    if u is None or l is None or (u - l) == 0:
        return None
    return (values[-1] - l) / (u - l)


def bb_width(values: List[float], period: int = 20) -> Optional[float]:
    """Bollinger Band Width = (upper - lower) / middle."""
    u = bb_upper(values, period)
    l = bb_lower(values, period)
    m = bb_middle(values, period)
    if u is None or l is None or m is None or m == 0:
        return None
    return (u - l) / m


def atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> Optional[float]:
    """Average True Range (Wilder's method)."""
    if len(closes) < period + 1:
        return None
    trs = []
    for i in range(1, len(closes)):
        h, l, pc = highs[i], lows[i], closes[i - 1]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    if len(trs) < period:
        return None
    atr_val = sum(trs[:period]) / period
    for tr in trs[period:]:
        atr_val = (atr_val * (period - 1) + tr) / period
    return atr_val


def keltner_channels(highs: List[float], lows: List[float], closes: List[float],
                     period: int = 20, atr_mult: float = 2.0) -> Optional[dict]:
    """Keltner Channels: EMA ± mult*ATR."""
    mid = ema(closes, period)
    atr_val = atr(highs, lows, closes, period)
    if mid is None or atr_val is None:
        return None
    return {
        "upper": round(mid + atr_mult * atr_val, 8),
        "middle": round(mid, 8),
        "lower": round(mid - atr_mult * atr_val, 8),
    }


def donchian_channels(highs: List[float], lows: List[float], period: int = 20) -> Optional[dict]:
    """Donchian Channels: highest high / lowest low over period."""
    if len(highs) < period:
        return None
    upper = max(highs[-period:])
    lower = min(lows[-period:])
    mid = (upper + lower) / 2
    return {"upper": round(upper, 8), "middle": round(mid, 8), "lower": round(lower, 8)}


def std_dev(values: List[float], period: int = 20) -> Optional[float]:
    """Standard Deviation of closes."""
    if len(values) < period:
        return None
    window = values[-period:]
    m = sum(window) / period
    return (sum((x - m) ** 2 for x in window) / period) ** 0.5


# ═══════════════════════════════════════════════════════════════════════════════
#  SUPPORT / RESISTANCE & FIBONACCI
# ═══════════════════════════════════════════════════════════════════════════════

def _swing_high(highs: List[float], lows: List[float], lookback: int = 20) -> Optional[float]:
    """Most recent swing high in lookback window."""
    if len(highs) < lookback:
        return None
    return max(highs[-lookback:])


def _swing_low(lows: List[float], lookback: int = 20) -> Optional[float]:
    """Most recent swing low in lookback window."""
    if len(lows) < lookback:
        return None
    return min(lows[-lookback:])


def fibonacci_levels(highs: List[float], lows: List[float], lookback: int = 50) -> Optional[dict]:
    """Fibonacci retracement levels from swing high/low.
    Returns dict of fib levels relative to current close.
    """
    if len(highs) < lookback:
        return None
    sh = max(highs[-lookback:])
    sl = min(lows[-lookback:])
    diff = sh - sl
    if diff == 0:
        return None
    return {
        "swing_high": round(sh, 8),
        "swing_low": round(sl, 8),
        "fib_0": round(sl, 8),
        "fib_236": round(sl + 0.236 * diff, 8),
        "fib_382": round(sl + 0.382 * diff, 8),
        "fib_500": round(sl + 0.500 * diff, 8),
        "fib_618": round(sl + 0.618 * diff, 8),
        "fib_786": round(sl + 0.786 * diff, 8),
        "fib_100": round(sh, 8),
    }


def price_near_fib(closes: List[float], highs: List[float], lows: List[float],
                   lookback: int = 50, tolerance_pct: float = 0.5) -> Optional[str]:
    """Returns nearest Fibonacci level name if price is within tolerance%, else None."""
    fibs = fibonacci_levels(highs, lows, lookback)
    if not fibs or not closes:
        return None
    price = closes[-1]
    tol = price * tolerance_pct / 100
    levels = {k: v for k, v in fibs.items() if k.startswith("fib_")}
    for name, level in levels.items():
        if abs(price - level) <= tol:
            return name
    return None


# ═══════════════════════════════════════════════════════════════════════════════
#  MARKET STRUCTURE (HH/HL/LH/LL)
# ═══════════════════════════════════════════════════════════════════════════════

def _find_pivot_highs(highs: List[float], left: int = 3, right: int = 3) -> List[Tuple[int, float]]:
    """Find pivot highs: local maxima with `left` bars before and `right` bars after."""
    pivots = []
    for i in range(left, len(highs) - right):
        if highs[i] == max(highs[i - left:i + right + 1]):
            pivots.append((i, highs[i]))
    return pivots


def _find_pivot_lows(lows: List[float], left: int = 3, right: int = 3) -> List[Tuple[int, float]]:
    """Find pivot lows: local minima."""
    pivots = []
    for i in range(left, len(lows) - right):
        if lows[i] == min(lows[i - left:i + right + 1]):
            pivots.append((i, lows[i]))
    return pivots


def market_structure(highs: List[float], lows: List[float], closes: List[float],
                     lookback: int = 50) -> Optional[dict]:
    """Detect market structure: HH, HL, LH, LL, trend type, consolidation."""
    if len(highs) < lookback:
        return None
    h = highs[-lookback:]
    l = lows[-lookback:]

    ph = _find_pivot_highs(h, left=3, right=3)
    pl = _find_pivot_lows(l, left=3, right=3)

    if len(ph) < 2 or len(pl) < 2:
        return {"trend": "insufficient_data", "hh": False, "hl": False, "lh": False, "ll": False}

    last_ph = ph[-1][1]
    prev_ph = ph[-2][1]
    last_pl = pl[-1][1]
    prev_pl = pl[-2][1]

    hh = last_ph > prev_ph
    lh = last_ph < prev_ph
    hl = last_pl > prev_pl
    ll = last_pl < prev_pl

    # Trend classification
    if hh and hl:
        trend = "uptrend"
    elif lh and ll:
        trend = "downtrend"
    elif not hh and not ll:
        trend = "consolidation"
    else:
        trend = "transition"

    # Trend shift: was uptrend, now showing lh (bearish shift)
    trend_shift_bearish = lh and not ll
    trend_shift_bullish = hl and not hh

    return {
        "trend": trend,
        "hh": hh, "hl": hl, "lh": lh, "ll": ll,
        "trend_shift_bearish": trend_shift_bearish,
        "trend_shift_bullish": trend_shift_bullish,
        "last_pivot_high": round(last_ph, 8),
        "last_pivot_low": round(last_pl, 8),
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  SMC — SMART MONEY CONCEPTS
# ═══════════════════════════════════════════════════════════════════════════════

def _detect_bos(highs: List[float], lows: List[float], closes: List[float],
                lookback: int = 30) -> Optional[dict]:
    """Break of Structure: price breaks above last pivot high (bullish BOS) or below last pivot low (bearish BOS)."""
    if len(closes) < lookback:
        return None
    h = highs[-lookback:]
    l = lows[-lookback:]

    ph = _find_pivot_highs(h, left=3, right=2)
    pl = _find_pivot_lows(l, left=3, right=2)

    if not ph or not pl:
        return {"bullish_bos": False, "bearish_bos": False}

    last_resistance = ph[-1][1]
    last_support = pl[-1][1]
    current = closes[-1]

    return {
        "bullish_bos": current > last_resistance,
        "bearish_bos": current < last_support,
        "resistance_level": round(last_resistance, 8),
        "support_level": round(last_support, 8),
    }


def _detect_choch(highs: List[float], lows: List[float], closes: List[float],
                  lookback: int = 50) -> Optional[dict]:
    """Change of Character: a swing against the prevailing trend — signals potential reversal."""
    if len(closes) < lookback:
        return None
    ms = market_structure(highs, lows, closes, lookback)
    if not ms:
        return {"bullish_choch": False, "bearish_choch": False}
    return {
        "bullish_choch": ms.get("trend_shift_bullish", False),
        "bearish_choch": ms.get("trend_shift_bearish", False),
    }


def _detect_fvg(highs: List[float], lows: List[float]) -> Optional[dict]:
    """Fair Value Gap: 3-candle pattern where candle i's low > candle i-2's high (bullish gap)
    or candle i's high < candle i-2's low (bearish gap).
    Returns the most recent FVG found in the last 10 candles.
    """
    if len(highs) < 3:
        return {"bullish_fvg": False, "bearish_fvg": False}

    bullish_fvg = False
    bearish_fvg = False
    fvg_high = None
    fvg_low = None
    lookback = min(len(highs) - 2, 10)

    for i in range(len(highs) - 1, len(highs) - lookback - 1, -1):
        if i < 2:
            break
        # Bullish FVG: gap up — current low > 2 bars ago high
        if lows[i] > highs[i - 2]:
            bullish_fvg = True
            fvg_low = highs[i - 2]
            fvg_high = lows[i]
            break
        # Bearish FVG: gap down — current high < 2 bars ago low
        if highs[i] < lows[i - 2]:
            bearish_fvg = True
            fvg_high = lows[i - 2]
            fvg_low = highs[i]
            break

    return {
        "bullish_fvg": bullish_fvg,
        "bearish_fvg": bearish_fvg,
        "fvg_high": round(fvg_high, 8) if fvg_high else None,
        "fvg_low": round(fvg_low, 8) if fvg_low else None,
    }


def _detect_order_block(opens: List[float], highs: List[float], lows: List[float],
                        closes: List[float], lookback: int = 20) -> Optional[dict]:
    """Order Block: last bearish candle before a significant bullish move (bullish OB),
    or last bullish candle before a significant bearish move (bearish OB).
    Simplified: looks for last opposing candle before strong momentum.
    """
    if len(closes) < lookback + 3:
        return {"bullish_ob": False, "bearish_ob": False}

    threshold = 0.005  # 0.5% body requirement

    bullish_ob = False
    bearish_ob = False
    ob_high = None
    ob_low = None

    for i in range(len(closes) - 3, max(len(closes) - lookback, 2), -1):
        body_i = abs(closes[i] - opens[i])
        body_i2 = abs(closes[i + 2] - opens[i + 2])
        # Bullish OB: bearish candle followed by two bullish candles with strong move up
        if (closes[i] < opens[i] and closes[i + 1] > opens[i + 1] and closes[i + 2] > opens[i + 2]
                and body_i > closes[i] * threshold and body_i2 > closes[i + 2] * threshold
                and closes[i + 2] > highs[i]):
            bullish_ob = True
            ob_high = highs[i]
            ob_low = lows[i]
            break
        # Bearish OB: bullish candle followed by two bearish candles
        if (closes[i] > opens[i] and closes[i + 1] < opens[i + 1] and closes[i + 2] < opens[i + 2]
                and body_i > closes[i] * threshold and body_i2 > closes[i + 2] * threshold
                and closes[i + 2] < lows[i]):
            bearish_ob = True
            ob_high = highs[i]
            ob_low = lows[i]
            break

    return {
        "bullish_ob": bullish_ob,
        "bearish_ob": bearish_ob,
        "ob_high": round(ob_high, 8) if ob_high else None,
        "ob_low": round(ob_low, 8) if ob_low else None,
    }


def _detect_equal_highs_lows(highs: List[float], lows: List[float],
                              tolerance_pct: float = 0.1, lookback: int = 30) -> dict:
    """Equal Highs / Equal Lows: two pivot highs/lows within tolerance% of each other."""
    if len(highs) < lookback:
        return {"equal_highs": False, "equal_lows": False}

    h = highs[-lookback:]
    l = lows[-lookback:]
    ph = _find_pivot_highs(h, left=3, right=2)
    pl = _find_pivot_lows(l, left=3, right=2)

    eq_highs = False
    if len(ph) >= 2:
        tol = ph[-1][1] * tolerance_pct / 100
        eq_highs = abs(ph[-1][1] - ph[-2][1]) <= tol

    eq_lows = False
    if len(pl) >= 2:
        tol = pl[-1][1] * tolerance_pct / 100
        eq_lows = abs(pl[-1][1] - pl[-2][1]) <= tol

    return {"equal_highs": eq_highs, "equal_lows": eq_lows}


def _detect_liquidity_sweep(highs: List[float], lows: List[float], closes: List[float],
                             lookback: int = 30) -> dict:
    """Liquidity Sweep: price momentarily breaches a pivot level then reverses (wick through EQH/EQL)."""
    if len(closes) < lookback:
        return {"bullish_sweep": False, "bearish_sweep": False}

    ehl = _detect_equal_highs_lows(highs, lows, lookback=lookback)
    ph = _find_pivot_highs(highs[-lookback:], left=3, right=2)
    pl = _find_pivot_lows(lows[-lookback:], left=3, right=2)

    bullish_sweep = False
    bearish_sweep = False

    if pl and len(lows) >= 2:
        last_low_level = pl[-1][1]
        # Bearish sweep: wick below EQL but closed above
        if lows[-1] < last_low_level and closes[-1] > last_low_level:
            bullish_sweep = True  # sweeps lows = bullish intent

    if ph and len(highs) >= 2:
        last_high_level = ph[-1][1]
        # Bullish sweep: wick above EQH but closed below
        if highs[-1] > last_high_level and closes[-1] < last_high_level:
            bearish_sweep = True  # sweeps highs = bearish intent

    return {"bullish_sweep": bullish_sweep, "bearish_sweep": bearish_sweep}


def _detect_premium_discount(highs: List[float], lows: List[float], closes: List[float],
                              lookback: int = 50) -> dict:
    """Premium/Discount zones: price above 50% of range = Premium (sell), below = Discount (buy)."""
    if len(closes) < lookback:
        return {"zone": "unknown", "in_premium": False, "in_discount": False, "equilibrium": None}
    sh = max(highs[-lookback:])
    sl = min(lows[-lookback:])
    eq = (sh + sl) / 2
    price = closes[-1]
    return {
        "zone": "premium" if price > eq else "discount",
        "in_premium": price > eq,
        "in_discount": price <= eq,
        "equilibrium": round(eq, 8),
        "premium_start": round(eq, 8),
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  SMC SHORT-NAME ALIASES
#  (Generic / direction-neutral versions used in simple condition builder)
# ═══════════════════════════════════════════════════════════════════════════════

def _detect_bos_any(highs: List[float], lows: List[float], closes: List[float],
                    lookback: int = 30) -> bool:
    """BOS (any direction): True if a bullish OR bearish BOS is detected."""
    result = _detect_bos(highs, lows, closes, lookback)
    if result is None:
        return False
    return result.get("bullish_bos", False) or result.get("bearish_bos", False)


def _detect_mbos(highs: List[float], lows: List[float], closes: List[float],
                 lookback: int = 20) -> dict:
    """MBOS — Minor / Internal Break of Structure.
    Uses tighter pivot parameters (left=2, right=1) to detect smaller-scale
    structure breaks inside a larger swing. Returns bullish_mbos / bearish_mbos.
    """
    if len(closes) < lookback:
        return {"bullish_mbos": False, "bearish_mbos": False}
    h = highs[-lookback:]
    l = lows[-lookback:]

    ph = _find_pivot_highs(h, left=2, right=1)
    pl = _find_pivot_lows(l, left=2, right=1)

    if not ph or not pl:
        return {"bullish_mbos": False, "bearish_mbos": False}

    last_resistance = ph[-1][1]
    last_support = pl[-1][1]
    current = closes[-1]

    return {
        "bullish_mbos": current > last_resistance,
        "bearish_mbos": current < last_support,
        "resistance": round(last_resistance, 8),
        "support": round(last_support, 8),
    }


def _detect_ob_any(opens: List[float], highs: List[float], lows: List[float],
                   closes: List[float], lookback: int = 20) -> bool:
    """OB (any direction): True if a bullish OR bearish Order Block is detected."""
    result = _detect_order_block(opens, highs, lows, closes, lookback)
    if result is None:
        return False
    return result.get("bullish_ob", False) or result.get("bearish_ob", False)


def _detect_choch_any(highs: List[float], lows: List[float], closes: List[float],
                      lookback: int = 50) -> bool:
    """CHOCH (any direction): True if a bullish OR bearish CHoCH is detected."""
    result = _detect_choch(highs, lows, closes, lookback)
    if result is None:
        return False
    return result.get("bullish_choch", False) or result.get("bearish_choch", False)


def _detect_fvg_50(highs: List[float], lows: List[float], closes: List[float]) -> dict:
    """FVG 50% — Fair Value Gap where price has retraced to fill 50% of the gap.
    A bullish FVG 50% means: gap exists and current price is at or below the 50% level.
    A bearish FVG 50% means: gap exists and current price is at or above the 50% level.
    Useful for entries at the 'equilibrium' of an FVG zone.
    """
    fvg = _detect_fvg(highs, lows)
    if fvg is None or (fvg["fvg_high"] is None and fvg["fvg_low"] is None):
        return {"bullish_fvg_50": False, "bearish_fvg_50": False}

    price = closes[-1]
    bullish_fvg_50 = False
    bearish_fvg_50 = False

    if fvg.get("bullish_fvg") and fvg["fvg_high"] is not None and fvg["fvg_low"] is not None:
        midpoint = (fvg["fvg_high"] + fvg["fvg_low"]) / 2
        # Price has entered the gap and reached the 50% level (≤ midpoint)
        bullish_fvg_50 = fvg["fvg_low"] <= price <= midpoint

    if fvg.get("bearish_fvg") and fvg["fvg_high"] is not None and fvg["fvg_low"] is not None:
        midpoint = (fvg["fvg_high"] + fvg["fvg_low"]) / 2
        # Price has entered the bearish gap and reached the 50% level (≥ midpoint)
        bearish_fvg_50 = midpoint <= price <= fvg["fvg_high"]

    return {
        "bullish_fvg_50": bullish_fvg_50,
        "bearish_fvg_50": bearish_fvg_50,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  CANDLESTICK PATTERNS
# ═══════════════════════════════════════════════════════════════════════════════

def _body(o: float, c: float) -> float:
    return abs(c - o)

def _upper_wick(o: float, h: float, c: float) -> float:
    return h - max(o, c)

def _lower_wick(o: float, l: float, c: float) -> float:
    return min(o, c) - l

def _candle_range(h: float, l: float) -> float:
    return h - l


def detect_candlestick_patterns(opens: List[float], highs: List[float],
                                  lows: List[float], closes: List[float]) -> dict:
    """Detect classic candlestick patterns. Returns dict of pattern_name: True/False."""
    if len(closes) < 3:
        return {}

    o1, h1, l1, c1 = opens[-3], highs[-3], lows[-3], closes[-3]
    o2, h2, l2, c2 = opens[-2], highs[-2], lows[-2], closes[-2]
    o,  h,  l,  c  = opens[-1], highs[-1], lows[-1], closes[-1]

    body    = _body(o, c)
    rng     = _candle_range(h, l)
    uw      = _upper_wick(o, h, c)
    lw      = _lower_wick(o, l, c)
    bullish = c > o
    bearish = c < o

    body2   = _body(o2, c2)
    rng2    = _candle_range(h2, l2)

    patterns = {}

    # ── Doji ────────────────────────────────────────────────────────────────
    patterns["doji"]           = rng > 0 and body / rng < 0.1

    # ── Hammer (bullish reversal, at bottom of downtrend) ────────────────────
    # Long lower wick (>= 2x body), small upper wick, small body
    patterns["hammer"] = (
        lw >= 2 * body and
        uw <= body * 0.5 and
        body > 0 and
        rng > 0
    )

    # ── Inverted Hammer ──────────────────────────────────────────────────────
    patterns["inverted_hammer"] = (
        uw >= 2 * body and
        lw <= body * 0.5 and
        body > 0
    )

    # ── Shooting Star (bearish, at top of uptrend) ───────────────────────────
    patterns["shooting_star"] = (
        bearish and
        uw >= 2 * body and
        lw <= body * 0.3 and
        body > 0
    )

    # ── Spinning Top ─────────────────────────────────────────────────────────
    patterns["spinning_top"] = (
        rng > 0 and
        body / rng < 0.35 and
        uw > body * 0.5 and
        lw > body * 0.5
    )

    # ── Marubozu (full-body candle, no wicks) ────────────────────────────────
    patterns["bullish_marubozu"] = bullish and rng > 0 and body / rng > 0.95
    patterns["bearish_marubozu"] = bearish and rng > 0 and body / rng > 0.95

    # ── Bullish Engulfing ────────────────────────────────────────────────────
    patterns["bullish_engulfing"] = (
        c2 < o2 and                   # previous bearish
        c > o and                      # current bullish
        o < c2 and c > o2             # engulfs
    )

    # ── Bearish Engulfing ────────────────────────────────────────────────────
    patterns["bearish_engulfing"] = (
        c2 > o2 and
        c < o and
        o > c2 and c < o2
    )

    # ── Bullish Harami ───────────────────────────────────────────────────────
    patterns["bullish_harami"] = (
        c2 < o2 and
        c > o and
        o > c2 and c < o2
    )

    # ── Bearish Harami ───────────────────────────────────────────────────────
    patterns["bearish_harami"] = (
        c2 > o2 and
        c < o and
        o < c2 and c > o2
    )

    # ── Piercing Line ────────────────────────────────────────────────────────
    mid2 = (o2 + c2) / 2
    patterns["piercing_line"] = (
        c2 < o2 and c > o and
        o < c2 and
        c > mid2 and c < o2
    )

    # ── Dark Cloud Cover ─────────────────────────────────────────────────────
    mid2b = (o2 + c2) / 2
    patterns["dark_cloud_cover"] = (
        c2 > o2 and c < o and
        o > c2 and
        c < mid2b and c > o2
    )

    # ── Morning Star (3-candle bullish reversal) ─────────────────────────────
    patterns["morning_star"] = (
        c1 < o1 and                                # bar -3: bearish
        _body(o2, c2) < _body(o1, c1) * 0.5 and  # bar -2: small body (star)
        c > o and                                   # bar -1: bullish
        c > (o1 + c1) / 2                          # close above midpoint of bar -3
    )

    # ── Evening Star (3-candle bearish reversal) ─────────────────────────────
    patterns["evening_star"] = (
        c1 > o1 and
        _body(o2, c2) < _body(o1, c1) * 0.5 and
        c < o and
        c < (o1 + c1) / 2
    )

    # ── Three White Soldiers ─────────────────────────────────────────────────
    patterns["three_white_soldiers"] = (
        c1 > o1 and c2 > o2 and c > o and
        c1 > c2 and c > c1 and           # ascending closes
        o < c2 and o2 < c1               # opens within previous bodies
    )

    # ── Three Black Crows ────────────────────────────────────────────────────
    patterns["three_black_crows"] = (
        c1 < o1 and c2 < o2 and c < o and
        c1 < c2 and c < c1 and
        o > c2 and o2 > c1
    )

    return patterns


# ═══════════════════════════════════════════════════════════════════════════════
#  CHART PATTERNS (Simplified)
# ═══════════════════════════════════════════════════════════════════════════════

def _detect_double_top(highs: List[float], closes: List[float],
                       lookback: int = 50, tolerance_pct: float = 1.0) -> bool:
    """Double Top: two pivot highs at approximately the same level."""
    if len(highs) < lookback:
        return False
    ph = _find_pivot_highs(highs[-lookback:], left=5, right=3)
    if len(ph) < 2:
        return False
    tol = ph[-1][1] * tolerance_pct / 100
    return abs(ph[-1][1] - ph[-2][1]) <= tol and ph[-1][0] > ph[-2][0] + 5


def _detect_double_bottom(lows: List[float], closes: List[float],
                          lookback: int = 50, tolerance_pct: float = 1.0) -> bool:
    """Double Bottom: two pivot lows at approximately the same level."""
    if len(lows) < lookback:
        return False
    pl = _find_pivot_lows(lows[-lookback:], left=5, right=3)
    if len(pl) < 2:
        return False
    tol = pl[-1][1] * tolerance_pct / 100
    return abs(pl[-1][1] - pl[-2][1]) <= tol and pl[-1][0] > pl[-2][0] + 5


# ═══════════════════════════════════════════════════════════════════════════════
#  PRICE ACTION HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _detect_breakout(highs: List[float], lows: List[float], closes: List[float],
                     lookback: int = 20) -> dict:
    """Breakout: price closes above resistance or below support of the lookback range."""
    if len(closes) < lookback + 1:
        return {"bullish_breakout": False, "bearish_breakout": False}
    resistance = max(highs[-lookback - 1:-1])
    support = min(lows[-lookback - 1:-1])
    return {
        "bullish_breakout": closes[-1] > resistance,
        "bearish_breakout": closes[-1] < support,
        "resistance": round(resistance, 8),
        "support": round(support, 8),
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  CROSSOVER HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _ma_value(values: List[float], period: int, ma_type: str = "EMA") -> Optional[float]:
    mt = ma_type.upper()
    if mt == "SMA":
        return sma(values, period)
    if mt == "WMA":
        return wma(values, period)
    if mt == "HMA":
        return hma(values, period)
    if mt == "DEMA":
        return dema(values, period)
    if mt == "TEMA":
        return tema(values, period)
    return ema(values, period)  # default EMA


def _cross_above(values: List[float], period1: int, period2: int, ma_type: str = "EMA") -> bool:
    """True if MA(period1) crossed above MA(period2) on the last bar."""
    if len(values) < max(period1, period2) + 2:
        return False
    cur1 = _ma_value(values, period1, ma_type)
    cur2 = _ma_value(values, period2, ma_type)
    prev1 = _ma_value(values[:-1], period1, ma_type)
    prev2 = _ma_value(values[:-1], period2, ma_type)
    if any(v is None for v in [cur1, cur2, prev1, prev2]):
        return False
    return prev1 <= prev2 and cur1 > cur2


def _cross_below(values: List[float], period1: int, period2: int, ma_type: str = "EMA") -> bool:
    """True if MA(period1) crossed below MA(period2) on the last bar."""
    if len(values) < max(period1, period2) + 2:
        return False
    cur1 = _ma_value(values, period1, ma_type)
    cur2 = _ma_value(values, period2, ma_type)
    prev1 = _ma_value(values[:-1], period1, ma_type)
    prev2 = _ma_value(values[:-1], period2, ma_type)
    if any(v is None for v in [cur1, cur2, prev1, prev2]):
        return False
    return prev1 >= prev2 and cur1 < cur2


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN CONDITION EVALUATOR
# ═══════════════════════════════════════════════════════════════════════════════

def evaluate_condition(ohlcv: List[list], cond: dict) -> bool:
    """Evaluate a single strategy condition against OHLCV data.

    Supported indicators:
    ─── Trend ──────────────
    SMA, EMA, WMA, VWMA, HMA, DEMA, TEMA, KAMA
    ICHIMOKU_ABOVE_CLOUD, ICHIMOKU_BELOW_CLOUD, ICHIMOKU_TENKAN, ICHIMOKU_KIJUN
    SUPERTREND_BULLISH, SUPERTREND, PARABOLIC_SAR_BULLISH, PARABOLIC_SAR

    ─── Momentum ───────────
    RSI, STOCH_RSI_K, STOCH_RSI_D, STOCH_K, STOCH_D
    MACD, MACD_SIGNAL, MACD_HISTOGRAM, MACD_CROSS_ABOVE, MACD_CROSS_BELOW
    CCI, WILLIAMS_R, MOMENTUM, ROC
    ULTIMATE_OSCILLATOR, AWESOME_OSCILLATOR

    ─── Volume ─────────────
    OBV, VWAP, AD_LINE, CMF, MFI, VOLUME_OSCILLATOR, VOLUME

    ─── Volatility ──────────
    BB_UPPER, BB_LOWER, BB_MIDDLE, BB_PERCENT, BB_WIDTH
    ATR, KC_UPPER, KC_LOWER, KC_MIDDLE
    DC_UPPER, DC_LOWER, DC_MIDDLE, STD_DEV

    ─── Price ───────────────
    PRICE, PRICE_ABOVE_BB, PRICE_BELOW_BB, PRICE_ABOVE_KC, PRICE_BELOW_KC

    ─── Market Structure ────
    MARKET_STRUCTURE_UPTREND, MARKET_STRUCTURE_DOWNTREND, HH, HL, LH, LL
    TREND_SHIFT_BULLISH, TREND_SHIFT_BEARISH

    ─── SMC ─────────────────
    BULLISH_BOS, BEARISH_BOS, BOS (any direction)
    MBOS / MINOR_BOS, BULLISH_MBOS, BEARISH_MBOS
    BULLISH_CHOCH, BEARISH_CHOCH, CHOCH (any direction)
    BULLISH_FVG, BEARISH_FVG
    FVG_50 / FVG50, BULLISH_FVG_50, BEARISH_FVG_50
    BULLISH_OB, BEARISH_OB, OB (any direction)
    EQUAL_HIGHS, EQUAL_LOWS, BULLISH_SWEEP, BEARISH_SWEEP
    IN_PREMIUM, IN_DISCOUNT

    ─── Fibonacci ───────────
    NEAR_FIB_236, NEAR_FIB_382, NEAR_FIB_500, NEAR_FIB_618, NEAR_FIB_786

    ─── Candlestick ─────────
    HAMMER, INVERTED_HAMMER, SHOOTING_STAR, DOJI, SPINNING_TOP
    BULLISH_ENGULFING, BEARISH_ENGULFING, BULLISH_HARAMI, BEARISH_HARAMI
    PIERCING_LINE, DARK_CLOUD_COVER, MORNING_STAR, EVENING_STAR
    THREE_WHITE_SOLDIERS, THREE_BLACK_CROWS
    BULLISH_MARUBOZU, BEARISH_MARUBOZU

    ─── Chart Patterns ──────
    DOUBLE_TOP, DOUBLE_BOTTOM

    ─── Breakout ────────────
    BULLISH_BREAKOUT, BEARISH_BREAKOUT

    ─── MA Crossovers ───────
    EMA_CROSS_ABOVE, EMA_CROSS_BELOW, SMA_CROSS_ABOVE, SMA_CROSS_BELOW
    WMA_CROSS_ABOVE, WMA_CROSS_BELOW

    Operators:
        < | <= | > | >= | == : numeric comparison
        DETECTED               : boolean detection (value/period unused for most)
        CROSS_ABOVE            : MA(period) crosses above MA(period2)
        CROSS_BELOW            : MA(period) crosses below MA(period2)
        PRICE_ABOVE            : current price > indicator value
        PRICE_BELOW            : current price < indicator value
    """
    if not ohlcv or len(ohlcv) < 3:
        return False

    closes  = [float(k[4]) for k in ohlcv]
    highs   = [float(k[2]) for k in ohlcv]
    lows    = [float(k[3]) for k in ohlcv]
    opens   = [float(k[1]) for k in ohlcv]
    volumes = [float(k[5]) for k in ohlcv]

    name    = str(cond.get("indicator", "PRICE")).upper()
    op      = str(cond.get("op", "<"))
    period  = int(cond.get("period", 14))
    period2 = int(cond.get("period2", 26))
    target  = float(cond.get("value", 0))

    # ── Helper: apply numeric operator ──────────────────────────────────────
    def num_cmp(val: Optional[float]) -> bool:
        if val is None:
            return False
        if op == "<":   return val < target
        if op == "<=":  return val <= target
        if op == ">":   return val > target
        if op == ">=":  return val >= target
        if op == "==":  return abs(val - target) < 1e-9
        if op == "PRICE_ABOVE": return closes[-1] > val
        if op == "PRICE_BELOW": return closes[-1] < val
        return False

    # ── DETECTED helper ──────────────────────────────────────────────────────
    def detected(flag: bool) -> bool:
        return bool(flag) if op == "DETECTED" else False

    # ═══════════════════════════════
    #  TREND
    # ═══════════════════════════════
    if name == "SMA":
        return num_cmp(sma(closes, period))
    if name == "EMA":
        return num_cmp(ema(closes, period))
    if name == "WMA":
        return num_cmp(wma(closes, period))
    if name == "VWMA":
        return num_cmp(vwma(closes, volumes, period))
    if name == "HMA":
        return num_cmp(hma(closes, period))
    if name == "DEMA":
        return num_cmp(dema(closes, period))
    if name == "TEMA":
        return num_cmp(tema(closes, period))
    if name == "KAMA":
        return num_cmp(kama(closes, period))

    if name in ("ICHIMOKU_ABOVE_CLOUD", "ICHIMOKU_BELOW_CLOUD"):
        ic = ichimoku(highs, lows, closes)
        if ic is None:
            return False
        if name == "ICHIMOKU_ABOVE_CLOUD":
            return detected(ic["above_cloud"]) if op == "DETECTED" else bool(ic["above_cloud"])
        return detected(ic["below_cloud"]) if op == "DETECTED" else bool(ic["below_cloud"])

    if name == "ICHIMOKU_TENKAN":
        ic = ichimoku(highs, lows, closes)
        return num_cmp(ic["tenkan_sen"] if ic else None)

    if name == "ICHIMOKU_KIJUN":
        ic = ichimoku(highs, lows, closes)
        return num_cmp(ic["kijun_sen"] if ic else None)

    if name == "SUPERTREND_BULLISH":
        st = supertrend(highs, lows, closes, period=period)
        if st is None:
            return False
        return detected(st["bullish"]) if op == "DETECTED" else bool(st["bullish"])

    if name == "SUPERTREND":
        st = supertrend(highs, lows, closes, period=period)
        return num_cmp(st["line"] if st else None)

    if name == "PARABOLIC_SAR_BULLISH":
        ps = parabolic_sar(highs, lows, closes)
        if ps is None:
            return False
        return detected(ps["bullish"]) if op == "DETECTED" else bool(ps["bullish"])

    if name == "PARABOLIC_SAR":
        ps = parabolic_sar(highs, lows, closes)
        return num_cmp(ps["sar"] if ps else None)

    # ═══════════════════════════════
    #  MOMENTUM
    # ═══════════════════════════════
    if name == "RSI":
        return num_cmp(rsi(closes, period))

    if name == "STOCH_RSI_K":
        sr = stoch_rsi(closes, rsi_period=period)
        return num_cmp(sr["k"] if sr else None)

    if name == "STOCH_RSI_D":
        sr = stoch_rsi(closes, rsi_period=period)
        return num_cmp(sr["d"] if sr else None)

    if name == "STOCH_K":
        return num_cmp(stoch_k(highs, lows, closes, period))

    if name == "STOCH_D":
        return num_cmp(stoch_d(highs, lows, closes, period))

    if name == "MACD":
        m = macd(closes)
        return num_cmp(m["macd"] if m else None)

    if name == "MACD_SIGNAL":
        m = macd(closes)
        return num_cmp(m["signal"] if m else None)

    if name == "MACD_HISTOGRAM":
        m = macd(closes)
        return num_cmp(m["histogram"] if m else None)

    if name == "MACD_CROSS_ABOVE":
        # MACD line crosses above signal line
        m_cur = macd(closes)
        m_prev = macd(closes[:-1])
        if not m_cur or not m_prev or m_cur["signal"] is None or m_prev["signal"] is None:
            return False
        return m_prev["macd"] <= m_prev["signal"] and m_cur["macd"] > m_cur["signal"]

    if name == "MACD_CROSS_BELOW":
        m_cur = macd(closes)
        m_prev = macd(closes[:-1])
        if not m_cur or not m_prev or m_cur["signal"] is None or m_prev["signal"] is None:
            return False
        return m_prev["macd"] >= m_prev["signal"] and m_cur["macd"] < m_cur["signal"]

    if name == "CCI":
        return num_cmp(cci(highs, lows, closes, period))

    if name == "WILLIAMS_R":
        return num_cmp(williams_r(highs, lows, closes, period))

    if name == "MOMENTUM":
        return num_cmp(momentum(closes, period))

    if name == "ROC":
        return num_cmp(roc(closes, period))

    if name == "ULTIMATE_OSCILLATOR":
        return num_cmp(ultimate_oscillator(highs, lows, closes))

    if name == "AWESOME_OSCILLATOR":
        return num_cmp(awesome_oscillator(highs, lows))

    # ═══════════════════════════════
    #  VOLUME
    # ═══════════════════════════════
    if name == "OBV":
        return num_cmp(obv(closes, volumes))

    if name == "VWAP":
        return num_cmp(vwap(highs, lows, closes, volumes, period))

    if name == "AD_LINE":
        return num_cmp(ad_line(highs, lows, closes, volumes))

    if name == "CMF":
        return num_cmp(cmf(highs, lows, closes, volumes, period))

    if name == "MFI":
        return num_cmp(mfi(highs, lows, closes, volumes, period))

    if name == "VOLUME_OSCILLATOR":
        return num_cmp(volume_oscillator(volumes, fast=5, slow=period))

    if name == "VOLUME":
        return num_cmp(volumes[-1] if volumes else None)

    # ═══════════════════════════════
    #  VOLATILITY
    # ═══════════════════════════════
    if name == "BB_UPPER":
        return num_cmp(bb_upper(closes, period))
    if name == "BB_LOWER":
        return num_cmp(bb_lower(closes, period))
    if name == "BB_MIDDLE":
        return num_cmp(bb_middle(closes, period))
    if name == "BB_PERCENT":
        return num_cmp(bb_percent(closes, period))
    if name == "BB_WIDTH":
        return num_cmp(bb_width(closes, period))

    if name == "PRICE_ABOVE_BB":
        val = bb_upper(closes, period)
        return num_cmp(val) if op in ("<", "<=", ">", ">=", "==") else (closes[-1] > val if val else False)

    if name == "PRICE_BELOW_BB":
        val = bb_lower(closes, period)
        return num_cmp(val) if op in ("<", "<=", ">", ">=", "==") else (closes[-1] < val if val else False)

    if name == "ATR":
        return num_cmp(atr(highs, lows, closes, period))

    if name == "KC_UPPER":
        kc = keltner_channels(highs, lows, closes, period)
        return num_cmp(kc["upper"] if kc else None)

    if name == "KC_LOWER":
        kc = keltner_channels(highs, lows, closes, period)
        return num_cmp(kc["lower"] if kc else None)

    if name == "KC_MIDDLE":
        kc = keltner_channels(highs, lows, closes, period)
        return num_cmp(kc["middle"] if kc else None)

    if name == "PRICE_ABOVE_KC":
        kc = keltner_channels(highs, lows, closes, period)
        return closes[-1] > kc["upper"] if kc else False

    if name == "PRICE_BELOW_KC":
        kc = keltner_channels(highs, lows, closes, period)
        return closes[-1] < kc["lower"] if kc else False

    if name == "DC_UPPER":
        dc = donchian_channels(highs, lows, period)
        return num_cmp(dc["upper"] if dc else None)
    if name == "DC_LOWER":
        dc = donchian_channels(highs, lows, period)
        return num_cmp(dc["lower"] if dc else None)
    if name == "DC_MIDDLE":
        dc = donchian_channels(highs, lows, period)
        return num_cmp(dc["middle"] if dc else None)

    if name == "STD_DEV":
        return num_cmp(std_dev(closes, period))

    # ═══════════════════════════════
    #  PRICE
    # ═══════════════════════════════
    if name == "PRICE":
        return num_cmp(closes[-1] if closes else None)

    # ═══════════════════════════════
    #  MARKET STRUCTURE
    # ═══════════════════════════════
    if name in ("MARKET_STRUCTURE_UPTREND", "MARKET_STRUCTURE_DOWNTREND",
                "HH", "HL", "LH", "LL", "TREND_SHIFT_BULLISH", "TREND_SHIFT_BEARISH"):
        ms = market_structure(highs, lows, closes, lookback=max(period, 20))
        if ms is None:
            return False
        key_map = {
            "MARKET_STRUCTURE_UPTREND":   ("trend", "uptrend"),
            "MARKET_STRUCTURE_DOWNTREND": ("trend", "downtrend"),
            "HH": ("hh", True), "HL": ("hl", True),
            "LH": ("lh", True), "LL": ("ll", True),
            "TREND_SHIFT_BULLISH": ("trend_shift_bullish", True),
            "TREND_SHIFT_BEARISH": ("trend_shift_bearish", True),
        }
        key, expected = key_map[name]
        return ms.get(key) == expected

    # ═══════════════════════════════
    #  SMC
    # ═══════════════════════════════
    if name in ("BULLISH_BOS", "BEARISH_BOS"):
        bos = _detect_bos(highs, lows, closes, lookback=max(period, 20))
        if bos is None:
            return False
        return bos.get("bullish_bos" if name == "BULLISH_BOS" else "bearish_bos", False)

    if name in ("BULLISH_CHOCH", "BEARISH_CHOCH"):
        choch = _detect_choch(highs, lows, closes, lookback=max(period, 30))
        if choch is None:
            return False
        return choch.get("bullish_choch" if name == "BULLISH_CHOCH" else "bearish_choch", False)

    if name in ("BULLISH_FVG", "BEARISH_FVG"):
        fvg = _detect_fvg(highs, lows)
        if fvg is None:
            return False
        return fvg.get("bullish_fvg" if name == "BULLISH_FVG" else "bearish_fvg", False)

    if name in ("BULLISH_OB", "BEARISH_OB"):
        ob = _detect_order_block(opens, highs, lows, closes, lookback=max(period, 20))
        if ob is None:
            return False
        return ob.get("bullish_ob" if name == "BULLISH_OB" else "bearish_ob", False)

    if name in ("EQUAL_HIGHS", "EQUAL_LOWS"):
        ehl = _detect_equal_highs_lows(highs, lows, lookback=max(period, 20))
        return ehl.get("equal_highs" if name == "EQUAL_HIGHS" else "equal_lows", False)

    if name in ("BULLISH_SWEEP", "BEARISH_SWEEP"):
        sweep = _detect_liquidity_sweep(highs, lows, closes, lookback=max(period, 20))
        return sweep.get("bullish_sweep" if name == "BULLISH_SWEEP" else "bearish_sweep", False)

    if name in ("IN_PREMIUM", "IN_DISCOUNT"):
        pd = _detect_premium_discount(highs, lows, closes, lookback=max(period, 30))
        return pd.get("in_premium" if name == "IN_PREMIUM" else "in_discount", False)

    # ── SMC short-name aliases ────────────────────────────────────────────────
    if name == "BOS":
        return _detect_bos_any(highs, lows, closes, lookback=max(period, 20))

    if name == "BULLISH_BOS_ONLY":  # alias kept for clarity
        bos = _detect_bos(highs, lows, closes, lookback=max(period, 20))
        return bos.get("bullish_bos", False) if bos else False

    if name in ("MBOS", "MINOR_BOS"):
        mbos = _detect_mbos(highs, lows, closes, lookback=max(period, 20))
        return mbos.get("bullish_mbos", False) or mbos.get("bearish_mbos", False)

    if name == "BULLISH_MBOS":
        mbos = _detect_mbos(highs, lows, closes, lookback=max(period, 20))
        return mbos.get("bullish_mbos", False)

    if name == "BEARISH_MBOS":
        mbos = _detect_mbos(highs, lows, closes, lookback=max(period, 20))
        return mbos.get("bearish_mbos", False)

    if name == "OB":
        return _detect_ob_any(opens, highs, lows, closes, lookback=max(period, 20))

    if name == "CHOCH":
        return _detect_choch_any(highs, lows, closes, lookback=max(period, 30))

    if name in ("FVG_50", "FVG50"):
        result = _detect_fvg_50(highs, lows, closes)
        return result.get("bullish_fvg_50", False) or result.get("bearish_fvg_50", False)

    if name == "BULLISH_FVG_50":
        result = _detect_fvg_50(highs, lows, closes)
        return result.get("bullish_fvg_50", False)

    if name == "BEARISH_FVG_50":
        result = _detect_fvg_50(highs, lows, closes)
        return result.get("bearish_fvg_50", False)

    # ═══════════════════════════════
    #  FIBONACCI
    # ═══════════════════════════════
    if name.startswith("NEAR_FIB_"):
        fib_key_map = {
            "NEAR_FIB_236": "fib_236",
            "NEAR_FIB_382": "fib_382",
            "NEAR_FIB_500": "fib_500",
            "NEAR_FIB_618": "fib_618",
            "NEAR_FIB_786": "fib_786",
        }
        fibs = fibonacci_levels(highs, lows, lookback=max(period, 30))
        if not fibs:
            return False
        fib_price = fibs.get(fib_key_map.get(name, ""))
        if fib_price is None:
            return False
        tol = fib_price * float(cond.get("tolerance", 0.5)) / 100
        return abs(closes[-1] - fib_price) <= tol

    # ═══════════════════════════════
    #  CANDLESTICK PATTERNS
    # ═══════════════════════════════
    candle_pattern_names = {
        "DOJI", "HAMMER", "INVERTED_HAMMER", "SHOOTING_STAR", "SPINNING_TOP",
        "BULLISH_MARUBOZU", "BEARISH_MARUBOZU",
        "BULLISH_ENGULFING", "BEARISH_ENGULFING",
        "BULLISH_HARAMI", "BEARISH_HARAMI",
        "PIERCING_LINE", "DARK_CLOUD_COVER",
        "MORNING_STAR", "EVENING_STAR",
        "THREE_WHITE_SOLDIERS", "THREE_BLACK_CROWS",
    }
    if name in candle_pattern_names:
        patterns = detect_candlestick_patterns(opens, highs, lows, closes)
        return bool(patterns.get(name.lower(), False))

    # ═══════════════════════════════
    #  CHART PATTERNS
    # ═══════════════════════════════
    if name == "DOUBLE_TOP":
        return _detect_double_top(highs, closes, lookback=max(period, 30))

    if name == "DOUBLE_BOTTOM":
        return _detect_double_bottom(lows, closes, lookback=max(period, 30))

    # ═══════════════════════════════
    #  BREAKOUT
    # ═══════════════════════════════
    if name == "BULLISH_BREAKOUT":
        bo = _detect_breakout(highs, lows, closes, lookback=period)
        return bo.get("bullish_breakout", False)

    if name == "BEARISH_BREAKOUT":
        bo = _detect_breakout(highs, lows, closes, lookback=period)
        return bo.get("bearish_breakout", False)

    # ═══════════════════════════════
    #  MA CROSSOVERS
    # ═══════════════════════════════
    cross_map = {
        "EMA_CROSS_ABOVE": ("EMA", True),
        "EMA_CROSS_BELOW": ("EMA", False),
        "SMA_CROSS_ABOVE": ("SMA", True),
        "SMA_CROSS_BELOW": ("SMA", False),
        "WMA_CROSS_ABOVE": ("WMA", True),
        "WMA_CROSS_BELOW": ("WMA", False),
    }
    if name in cross_map:
        ma_type, is_above = cross_map[name]
        if is_above:
            return _cross_above(closes, period, period2, ma_type)
        return _cross_below(closes, period, period2, ma_type)

    # Generic CROSS_ABOVE / CROSS_BELOW ops with EMA by default
    if op == "CROSS_ABOVE":
        return _cross_above(closes, period, period2)
    if op == "CROSS_BELOW":
        return _cross_below(closes, period, period2)

    return False
