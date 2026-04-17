'use client';
import { useState, useEffect, useCallback } from 'react';
import Nav from '@/components/Nav';
import { useI18n } from '@/lib/i18n';
import { api } from '@/lib/api';

// ─── Types ───────────────────────────────────────────────────────────────────

interface ScoreBreakdown {
  trend: number; momentum: number; volume: number;
  volatility: number; candlestick: number; sr: number;
}

interface Details {
  trend?: string[]; momentum?: string[]; volume?: string[];
  volatility?: string[]; candlestick?: string[]; sr?: string[];
}

interface SignalRecord {
  id: number;
  symbol: string;
  exchange: string;
  timeframe: string;
  signal: string;
  score: number;
  price: number;
  atr: number | null;
  sl: number | null;
  tp1: number | null;
  tp2: number | null;
  rr_ratio: number | null;
  support: number | null;
  resistance: number | null;
  details?: Details;
  score_breakdown?: ScoreBreakdown;
  telegram_message?: string;
  created_at: string;
}

interface Stats {
  total: number; days: number;
  by_signal: Record<string, number>;
  by_symbol: Record<string, Record<string, number>>;
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

const SIGNAL_STYLE: Record<string, { bg: string; color: string; border: string; label: string }> = {
  STRONG_BUY:  { bg: '#052e16', color: '#4ade80', border: '#16a34a', label: '🟢 STRONG BUY'  },
  WEAK_BUY:    { bg: '#1c2e10', color: '#a3e635', border: '#65a30d', label: '🟡 WEAK BUY'    },
  NEUTRAL:     { bg: '#1c1917', color: '#a8a29e', border: '#57534e', label: '⚪ NEUTRAL'      },
  WEAK_SELL:   { bg: '#2a1a00', color: '#fb923c', border: '#c2410c', label: '🟠 WEAK SELL'   },
  STRONG_SELL: { bg: '#450a0a', color: '#f87171', border: '#dc2626', label: '🔴 STRONG SELL' },
};

const fmt = (v: number | null | undefined, d = 4) =>
  v == null ? '—' : v.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });

const fmtScore = (s: number) =>
  `${s >= 0 ? '+' : ''}${s.toFixed(1)}`;

const timeAgo = (iso: string) => {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
};

const SCORE_KEYS: Array<keyof ScoreBreakdown> = ['trend', 'momentum', 'volume', 'volatility', 'candlestick', 'sr'];
const SCORE_LABELS: Record<string, string> = {
  trend: 'Trend', momentum: 'Momentum', volume: 'Volume',
  volatility: 'Volatility', candlestick: 'Candle', sr: 'S/R',
};

// ─── Sub-components ───────────────────────────────────────────────────────────

function ScoreBar({ value }: { value: number }) {
  const pct = Math.min(100, Math.abs(value) / 3 * 100);
  const color = value > 0 ? '#4ade80' : value < 0 ? '#f87171' : '#78716c';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <div style={{ flex: 1, height: 4, background: 'var(--border)', borderRadius: 2, overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 2 }} />
      </div>
      <span style={{ fontSize: '0.7rem', color, minWidth: 28, textAlign: 'right', fontFamily: 'monospace' }}>
        {fmtScore(value)}
      </span>
    </div>
  );
}

function SignalBadge({ signal }: { signal: string }) {
  const s = SIGNAL_STYLE[signal] || SIGNAL_STYLE.NEUTRAL;
  return (
    <span style={{
      padding: '0.25rem 0.6rem', borderRadius: 6, fontSize: '0.7rem',
      fontWeight: 700, letterSpacing: '0.04em',
      background: s.bg, color: s.color, border: `1px solid ${s.border}`,
    }}>
      {s.label}
    </span>
  );
}

function SignalCard({ s, expanded, onToggle }: {
  s: SignalRecord; expanded: boolean; onToggle: () => void
}) {
  const style = SIGNAL_STYLE[s.signal] || SIGNAL_STYLE.NEUTRAL;
  const strength = Math.min(10, Math.abs(s.score)).toFixed(1);
  const [sending, setSending] = useState(false);
  const [sent, setSent]       = useState<string | null>(null);

  const sendTelegram = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (sending) return;
    setSending(true);
    setSent(null);
    try {
      const r = await api.post(`/api/signals/${s.id}/send-telegram`);
      setSent(`✅ Channel: ${r.data.channel ? 'OK' : '—'} · Users: ${r.data.users_sent}/${r.data.users_total}`);
    } catch (e: any) {
      setSent(`❌ ${e.response?.data?.detail || 'Error'}`);
    } finally {
      setSending(false);
      setTimeout(() => setSent(null), 5000);
    }
  };

  return (
    <div style={{ border: `1px solid ${style.border}`, borderRadius: 12, overflow: 'hidden', marginBottom: '0.75rem' }}>
      {/* Header */}
      <div
        onClick={onToggle}
        style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '0.8rem 1rem', cursor: 'pointer', background: style.bg }}
      >
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <span style={{ fontWeight: 700, fontSize: '1rem', color: style.color }}>{s.symbol}</span>
            <SignalBadge signal={s.signal} />
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', background: 'var(--bg)', padding: '0.1rem 0.4rem', borderRadius: 4 }}>
              {s.timeframe.toUpperCase()} · {s.exchange}
            </span>
          </div>
          <div style={{ marginTop: '0.3rem', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            💰 {fmt(s.price, 6)} USDT &nbsp;·&nbsp; Score: <strong style={{ color: style.color }}>{fmtScore(s.score)}</strong> &nbsp;·&nbsp; Strength: {strength}/10
          </div>
        </div>
        <div style={{ textAlign: 'right', fontSize: '0.7rem', color: 'var(--text-muted)', flexShrink: 0 }}>
          <div>{timeAgo(s.created_at)}</div>
          <div style={{ marginTop: 2 }}>{expanded ? '▲' : '▼'}</div>
        </div>
      </div>

      {/* Expanded details */}
      {expanded && (
        <div style={{ padding: '1rem', background: 'var(--panel)' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
            {/* Risk */}
            <div style={{ background: 'var(--bg)', borderRadius: 8, padding: '0.75rem' }}>
              <div style={{ fontSize: '0.7rem', fontWeight: 700, color: 'var(--text-muted)', marginBottom: '0.4rem', textTransform: 'uppercase' }}>Risk Management</div>
              <div style={{ fontSize: '0.8rem', display: 'flex', flexDirection: 'column', gap: 3 }}>
                <div>🛑 SL: <strong style={{ color: '#f87171' }}>{fmt(s.sl, 4)}</strong></div>
                <div>🎯 TP1: <strong style={{ color: '#4ade80' }}>{fmt(s.tp1, 4)}</strong></div>
                <div>🎯 TP2: <strong style={{ color: '#34d399' }}>{fmt(s.tp2, 4)}</strong></div>
                <div>📐 R/R: <strong>1:{s.rr_ratio?.toFixed(2) || '—'}</strong></div>
              </div>
            </div>

            {/* S/R */}
            <div style={{ background: 'var(--bg)', borderRadius: 8, padding: '0.75rem' }}>
              <div style={{ fontSize: '0.7rem', fontWeight: 700, color: 'var(--text-muted)', marginBottom: '0.4rem', textTransform: 'uppercase' }}>Support / Resistance</div>
              <div style={{ fontSize: '0.8rem', display: 'flex', flexDirection: 'column', gap: 3 }}>
                <div>🟦 Support: <strong>{fmt(s.support, 4)}</strong></div>
                <div>🟥 Resistance: <strong>{fmt(s.resistance, 4)}</strong></div>
                <div>📊 ATR: <strong>{fmt(s.atr, 4)}</strong></div>
              </div>
            </div>
          </div>

          {/* Score breakdown */}
          {s.score_breakdown && (
            <div style={{ background: 'var(--bg)', borderRadius: 8, padding: '0.75rem', marginBottom: '1rem' }}>
              <div style={{ fontSize: '0.7rem', fontWeight: 700, color: 'var(--text-muted)', marginBottom: '0.5rem', textTransform: 'uppercase' }}>Score Breakdown</div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.4rem 1rem' }}>
                {SCORE_KEYS.map(k => (
                  <div key={k}>
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: 2 }}>{SCORE_LABELS[k]}</div>
                    <ScoreBar value={s.score_breakdown![k]} />
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Detail lines */}
          {s.details && (
            <div style={{ fontSize: '0.78rem', display: 'flex', flexDirection: 'column', gap: '0.75rem', marginBottom: '1rem' }}>
              {(['trend', 'momentum', 'volume', 'volatility', 'candlestick'] as const).map(section => {
                const items = s.details![section];
                if (!items?.length) return null;
                return (
                  <div key={section}>
                    <div style={{ fontSize: '0.7rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '0.3rem' }}>
                      {SCORE_LABELS[section]}
                    </div>
                    {items.map((line, i) => (
                      <div key={i} style={{ padding: '0.1rem 0', color: 'var(--text)' }}>{line}</div>
                    ))}
                  </div>
                );
              })}
            </div>
          )}

          {/* Telegram send button */}
          <div style={{ borderTop: '1px solid var(--border)', paddingTop: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
            <button
              onClick={sendTelegram}
              disabled={sending}
              style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: '0.45rem 1rem', borderRadius: 8, fontSize: '0.8rem', fontWeight: 600, cursor: sending ? 'not-allowed' : 'pointer',
                background: sending ? 'rgba(0,136,204,0.1)' : 'rgba(0,136,204,0.15)',
                border: '1px solid #0088cc', color: '#0088cc',
                transition: 'all 0.15s',
              }}
            >
              {sending ? '⏳' : '✈️'} {sending ? 'Sending...' : 'Send to Telegram'}
            </button>
            {sent && (
              <span style={{ fontSize: '0.75rem', color: sent.startsWith('✅') ? '#4ade80' : '#f87171' }}>
                {sent}
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Analyze form ─────────────────────────────────────────────────────────────

function AnalyzeForm({ onResult }: { onResult: (r: SignalRecord) => void }) {
  const { t } = useI18n();
  const [symbol, setSymbol]     = useState('BTCUSDT');
  const [exchange, setExchange] = useState('binance');
  const [tf, setTf]             = useState('1h');
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState('');

  const TIMEFRAMES = ['1m','5m','15m','30m','1h','4h','1d'];

  const run = async () => {
    if (!symbol.trim() || loading) return;
    setLoading(true);
    setError('');
    try {
      const r = await api.post('/api/signals/analyze', {
        symbol: symbol.trim().toUpperCase(),
        exchange,
        timeframe: tf,
      });
      onResult(r.data as SignalRecord);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Error';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 12, padding: '1rem', marginBottom: '1.25rem' }}>
      <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '0.75rem', textTransform: 'uppercase' }}>
        {t('runSignalAnalysis')}
      </div>
      <div style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap', alignItems: 'flex-end' }}>
        <input
          value={symbol}
          onChange={e => setSymbol(e.target.value.toUpperCase())}
          onKeyDown={e => e.key === 'Enter' && run()}
          placeholder="BTCUSDT"
          className="input-field"
          style={{ width: 130, fontFamily: 'monospace' }}
          disabled={loading}
        />
        <select value={exchange} onChange={e => setExchange(e.target.value)} className="input-field" style={{ width: 110 }} disabled={loading}>
          <option value="binance">Binance</option>
          <option value="bybit">Bybit</option>
        </select>
        <select value={tf} onChange={e => setTf(e.target.value)} className="input-field" style={{ width: 80 }} disabled={loading}>
          {TIMEFRAMES.map(x => <option key={x} value={x}>{x}</option>)}
        </select>
        <button onClick={run} disabled={loading || !symbol.trim()} className="btn-primary" style={{ padding: '0.5rem 1.2rem', fontSize: '0.85rem' }}>
          {loading ? '⏳' : t('analyze')}
        </button>
      </div>
      {error && <div style={{ color: 'var(--danger)', fontSize: '0.8rem', marginTop: '0.5rem' }}>❌ {error}</div>}
    </div>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function SignalsPage() {
  const { t } = useI18n();

  const [signals, setSignals]     = useState<SignalRecord[]>([]);
  const [stats, setStats]         = useState<Stats | null>(null);
  const [expandedId, setExpanded] = useState<number | null>(null);
  const [filter, setFilter]       = useState('ALL');
  const [loading, setLoading]     = useState(true);

  const FILTERS = ['ALL', 'STRONG_BUY', 'WEAK_BUY', 'NEUTRAL', 'WEAK_SELL', 'STRONG_SELL'];

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [sr, st] = await Promise.all([
        api.get('/api/signals/latest?limit=50'),
        api.get('/api/signals/stats?days=7'),
      ]);
      setSignals(sr.data);
      setStats(st.data);
    } catch { /* silent */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const displayed = filter === 'ALL'
    ? signals
    : signals.filter(s => s.signal === filter);

  const handleAnalyzed = (r: SignalRecord) => {
    setSignals(prev => [r, ...prev]);
    setExpanded(r.id);
  };

  return (
    <>
      <Nav />
      <main style={{ maxWidth: 820, margin: '0 auto', padding: '2rem 1rem' }}>

        {/* Title */}
        <div style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div style={{ flex: 1 }}>
            <h1 style={{ fontSize: '1.4rem', fontWeight: 700, marginBottom: '0.25rem' }}>{t('signalsTitle')}</h1>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>{t('signalsSubtitle')}</p>
          </div>
          <button onClick={load} className="btn-secondary" style={{ padding: '0.4rem 0.8rem', fontSize: '0.8rem' }}>
            ↻ {t('refresh')}
          </button>
        </div>

        {/* Stats row */}
        {stats && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: '0.6rem', marginBottom: '1.25rem' }}>
            {Object.entries(SIGNAL_STYLE).filter(([k]) => k !== 'NEUTRAL').map(([key, s]) => (
              <div key={key} style={{ background: s.bg, border: `1px solid ${s.border}`, borderRadius: 10, padding: '0.6rem 0.8rem', textAlign: 'center' }}>
                <div style={{ fontSize: '1.1rem', fontWeight: 700, color: s.color }}>{stats.by_signal[key] || 0}</div>
                <div style={{ fontSize: '0.65rem', color: s.color, opacity: 0.8 }}>{s.label}</div>
              </div>
            ))}
            <div style={{ background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 10, padding: '0.6rem 0.8rem', textAlign: 'center' }}>
              <div style={{ fontSize: '1.1rem', fontWeight: 700 }}>{stats.total}</div>
              <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>Total ({stats.days}d)</div>
            </div>
          </div>
        )}

        {/* Analyze form */}
        <AnalyzeForm onResult={handleAnalyzed} />

        {/* Filter tabs */}
        <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
          {FILTERS.map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={filter === f ? 'btn-primary' : 'btn-secondary'}
              style={{ padding: '0.3rem 0.7rem', fontSize: '0.75rem' }}
            >
              {f === 'ALL' ? `All (${signals.length})` : (SIGNAL_STYLE[f]?.label || f)}
            </button>
          ))}
        </div>

        {/* Signal list */}
        {loading ? (
          <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
            ⏳ {t('loading')}
          </div>
        ) : displayed.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '3rem 1rem', border: '1px dashed var(--border)', borderRadius: 12, color: 'var(--text-muted)' }}>
            <div style={{ fontSize: '2.5rem', marginBottom: '0.5rem' }}>📊</div>
            <p style={{ fontSize: '0.875rem' }}>{t('noSignalsYet')}</p>
          </div>
        ) : (
          displayed.map(s => (
            <SignalCard
              key={s.id}
              s={s}
              expanded={expandedId === s.id}
              onToggle={() => setExpanded(expandedId === s.id ? null : s.id)}
            />
          ))
        )}

        <p style={{ textAlign: 'center', fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '1.5rem' }}>
          ⚠️ {t('signalsDisclaimer')}
        </p>
      </main>
    </>
  );
}
