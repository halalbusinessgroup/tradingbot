"""Pure-Python technical indicators for the strategy engine.

OHLCV format: [[timestamp, open, high, low, close, volume], ...]
indices:        0           1     2     3    4      5
"""
from typing import List, Optional


# ─── Extract helpers ─────────────────────────────────────────────────────────

def closes_from_klines(ohlcv: List[list]) -> List[float]:
    return [float(k[4]) for k in ohlcv]

def highs_from_klines(ohlcv: List[list]) -> List[float]:
    return [float(k[2]) for k in ohlcv]

def lows_from_klines(ohlcv: List[list]) -> List[float]:
    return [float(k[3]) for k in ohlcv]

def volumes_from_klines(ohlcv: List[list]) -> List[float]:
    return [float(k[5]) for k in ohlcv]


# ─── Base indicators (closes only) ───────────────────────────────────────────

def sma(values: List[float], period: int) -> Optional[float]:
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def ema(values: List[float], period: int) -> Optional[float]:
    if len(values) < period:
        return None
    k = 2 / (period + 1)
    e = sum(values[:period]) / period
    for v in values[period:]:
        e = v * k + e * (1 - k)
    return e


def rsi(values: List[float], period: int = 14) -> Optional[float]:
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


def macd(values: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Optional[dict]:
    if len(values) < slow + signal:
        return None
    ema_fast = ema(values, fast)
    ema_slow = ema(values, slow)
    if ema_fast is None or ema_slow is None:
        return None
    macd_line = ema_fast - ema_slow
    return {"macd": macd_line, "ema_fast": ema_fast, "ema_slow": ema_slow}


def macd_line(values: List[float], period: int = 26) -> Optional[float]:
    """Returns the MACD line value (EMA12 - EMA26). period param = slow EMA period."""
    result = macd(values, fast=12, slow=period)
    return result["macd"] if result else None


# ─── Bollinger Bands ──────────────────────────────────────────────────────────

def bb_upper(values: List[float], period: int = 20) -> Optional[float]:
    """Bollinger Band upper (SMA + 2*stddev)."""
    if len(values) < period:
        return None
    window = values[-period:]
    m = sum(window) / period
    std = (sum((x - m) ** 2 for x in window) / period) ** 0.5
    return m + 2 * std


def bb_lower(values: List[float], period: int = 20) -> Optional[float]:
    """Bollinger Band lower (SMA - 2*stddev)."""
    if len(values) < period:
        return None
    window = values[-period:]
    m = sum(window) / period
    std = (sum((x - m) ** 2 for x in window) / period) ** 0.5
    return m - 2 * std


def bb_middle(values: List[float], period: int = 20) -> Optional[float]:
    return sma(values, period)


def bb_percent(values: List[float], period: int = 20) -> Optional[float]:
    """%B: 0 = at lower band, 1 = at upper band, 0.5 = at middle."""
    u = bb_upper(values, period)
    l = bb_lower(values, period)
    if u is None or l is None or (u - l) == 0:
        return None
    return (values[-1] - l) / (u - l)


# ─── Stochastic ──────────────────────────────────────────────────────────────

def stoch_k(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> Optional[float]:
    """Stochastic %K: (close - lowest_low) / (highest_high - lowest_low) * 100"""
    if len(closes) < period:
        return None
    hh = max(highs[-period:])
    ll = min(lows[-period:])
    if hh == ll:
        return 50.0
    return (closes[-1] - ll) / (hh - ll) * 100


def stoch_d(highs: List[float], lows: List[float], closes: List[float], period: int = 14, smooth: int = 3) -> Optional[float]:
    """Stochastic %D = SMA of %K values."""
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


# ─── ATR ─────────────────────────────────────────────────────────────────────

def atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> Optional[float]:
    """Average True Range."""
    if len(closes) < period + 1:
        return None
    trs = []
    for i in range(1, len(closes)):
        h, l, pc = highs[i], lows[i], closes[i - 1]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    if len(trs) < period:
        return None
    # Smooth with Wilder's method
    atr_val = sum(trs[:period]) / period
    for tr in trs[period:]:
        atr_val = (atr_val * (period - 1) + tr) / period
    return atr_val


# ─── Williams %R ─────────────────────────────────────────────────────────────

def williams_r(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> Optional[float]:
    """Williams %R: -100 = oversold, 0 = overbought."""
    if len(closes) < period:
        return None
    hh = max(highs[-period:])
    ll = min(lows[-period:])
    if hh == ll:
        return -50.0
    return (hh - closes[-1]) / (hh - ll) * -100


# ─── CCI ─────────────────────────────────────────────────────────────────────

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


# ─── OBV ─────────────────────────────────────────────────────────────────────

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


# ─── VWAP ────────────────────────────────────────────────────────────────────

def vwap(highs: List[float], lows: List[float], closes: List[float], volumes: List[float], period: int = 20) -> Optional[float]:
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


# ─── Condition evaluator ──────────────────────────────────────────────────────

def evaluate_condition(ohlcv: List[list], cond: dict) -> bool:
    """Evaluate a single strategy condition against OHLCV data.

    cond format:
        {
            "indicator": "RSI",   # RSI | EMA | SMA | MACD | BB_UPPER | BB_LOWER |
                                  # BB_PERCENT | STOCH_K | ATR | WILLIAMS_R | CCI |
                                  # OBV | VWAP | PRICE | VOLUME
            "period": 14,
            "op": "<",            # < | <= | > | >= | ==
            "value": 30
        }
    """
    closes  = [float(k[4]) for k in ohlcv]
    highs   = [float(k[2]) for k in ohlcv]
    lows    = [float(k[3]) for k in ohlcv]
    volumes = [float(k[5]) for k in ohlcv]

    name   = cond.get("indicator", "PRICE").upper()
    op     = cond.get("op", "<")
    target = float(cond.get("value", 0))
    period = int(cond.get("period", 14))

    val: Optional[float] = None

    if name == "RSI":
        val = rsi(closes, period)
    elif name == "EMA":
        val = ema(closes, period)
    elif name == "SMA":
        val = sma(closes, period)
    elif name == "MACD":
        val = macd_line(closes, 26)
    elif name == "BB_UPPER":
        val = bb_upper(closes, period)
    elif name == "BB_LOWER":
        val = bb_lower(closes, period)
    elif name == "BB_MIDDLE":
        val = bb_middle(closes, period)
    elif name == "BB_PERCENT":
        val = bb_percent(closes, period)
    elif name == "STOCH_K":
        val = stoch_k(highs, lows, closes, period)
    elif name == "STOCH_D":
        val = stoch_d(highs, lows, closes, period)
    elif name == "ATR":
        val = atr(highs, lows, closes, period)
    elif name == "WILLIAMS_R":
        val = williams_r(highs, lows, closes, period)
    elif name == "CCI":
        val = cci(highs, lows, closes, period)
    elif name == "OBV":
        val = obv(closes, volumes)
    elif name == "VWAP":
        val = vwap(highs, lows, closes, volumes, period)
    elif name == "PRICE":
        val = closes[-1] if closes else None
    elif name == "VOLUME":
        val = volumes[-1] if volumes else None

    if val is None:
        return False

    return {
        "<":  val < target,
        "<=": val <= target,
        ">":  val > target,
        ">=": val >= target,
        "==": abs(val - target) < 1e-9,
    }.get(op, False)
