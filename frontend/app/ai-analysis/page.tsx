'use client';
import { useState, useEffect, useRef, useCallback } from 'react';
import Nav from '@/components/Nav';
import { useI18n } from '@/lib/i18n';
import { api } from '@/lib/api';

// ─── Types ───────────────────────────────────────────────────────────────────

interface Strategy {
  id: number;
  name: string;
  symbols: string[];
  timeframe: string;
  tp_percent: number;
  sl_percent: number;
  amount_usdt: number;
  entry_conditions: Condition[];
  order_type?: string;
}

interface Condition {
  indicator: string;
  period: number;
  period2: number;
  op: string;
  value: number;
}

// ─── Signal badge ─────────────────────────────────────────────────────────────

const SIGNALS: Record<string, { bg: string; color: string; border: string }> = {
  'STRONG BUY':  { bg: '#052e16', color: '#4ade80', border: '#16a34a' },
  'BUY':         { bg: '#064e3b', color: '#34d399', border: '#059669' },
  'NEUTRAL':     { bg: '#1c1917', color: '#d6d3d1', border: '#78716c' },
  'SELL':        { bg: '#450a0a', color: '#f87171', border: '#dc2626' },
  'STRONG SELL': { bg: '#3b0764', color: '#e879f9', border: '#a21caf' },
};

function extractSignal(text: string): string | null {
  for (const k of ['STRONG BUY', 'STRONG SELL', 'BUY', 'SELL', 'NEUTRAL']) {
    if (text.includes(k)) return k;
  }
  return null;
}

// ─── Markdown → React nodes renderer ─────────────────────────────────────────
// Converts raw markdown text to styled JSX without broken HTML nesting

function MarkdownLine({ line, idx }: { line: string; idx: number }) {
  const applyInline = (text: string) => {
    // Bold: **text**
    const parts = text.split(/(\*\*.*?\*\*)/g);
    return parts.map((p, i) =>
      p.startsWith('**') && p.endsWith('**')
        ? <strong key={i}>{p.slice(2, -2)}</strong>
        : <span key={i}>{p}</span>
    );
  };

  if (line.startsWith('## ')) {
    return (
      <div key={idx} style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--accent)', marginTop: '1.2rem', marginBottom: '0.3rem', borderBottom: '1px solid var(--border)', paddingBottom: '0.3rem' }}>
        {line.slice(3)}
      </div>
    );
  }
  if (line.startsWith('### ')) {
    return (
      <div key={idx} style={{ fontSize: '0.95rem', fontWeight: 700, marginTop: '0.8rem', marginBottom: '0.2rem', color: 'var(--fg)' }}>
        {line.slice(4)}
      </div>
    );
  }
  if (line.startsWith('━') || line.startsWith('─') || line === '---') {
    return <hr key={idx} style={{ border: 'none', borderTop: '1px solid var(--border)', margin: '0.8rem 0' }} />;
  }
  if (line.startsWith('- ') || line.startsWith('• ')) {
    return (
      <div key={idx} style={{ display: 'flex', gap: '0.5rem', marginLeft: '0.75rem', marginBottom: '0.15rem', lineHeight: 1.6 }}>
        <span style={{ color: 'var(--accent)', flexShrink: 0 }}>•</span>
        <span>{applyInline(line.slice(2))}</span>
      </div>
    );
  }
  if (/^\d+\. /.test(line)) {
    const num = line.match(/^(\d+)\. /)?.[1];
    return (
      <div key={idx} style={{ display: 'flex', gap: '0.5rem', marginLeft: '0.75rem', marginBottom: '0.15rem', lineHeight: 1.6 }}>
        <span style={{ color: 'var(--accent)', flexShrink: 0, minWidth: '1.2rem' }}>{num}.</span>
        <span>{applyInline(line.replace(/^\d+\. /, ''))}</span>
      </div>
    );
  }
  if (line.trim() === '') {
    return <div key={idx} style={{ height: '0.4rem' }} />;
  }
  return (
    <div key={idx} style={{ lineHeight: 1.7, marginBottom: '0.1rem' }}>
      {applyInline(line)}
    </div>
  );
}

function MarkdownOutput({ text, streaming }: { text: string; streaming: boolean }) {
  const lines = text.split('\n');
  return (
    <div style={{ fontSize: '0.9rem', color: 'var(--fg)' }}>
      {lines.map((line, i) => <MarkdownLine key={i} line={line} idx={i} />)}
      {streaming && (
        <span style={{ display: 'inline-block', width: 8, height: 16, background: 'var(--accent)', marginLeft: 2, animation: 'blink 1s step-end infinite', verticalAlign: 'middle' }} />
      )}
    </div>
  );
}

// ─── Timeframes ───────────────────────────────────────────────────────────────

const TIMEFRAMES = ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '12h', '1d', '3d', '1w'];

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function AIAnalysisPage() {
  const { t, lang } = useI18n();

  const [enabled,      setEnabled]      = useState<boolean | null>(null);
  const [strategies,   setStrategies]   = useState<Strategy[]>([]);
  const [symbol,       setSymbol]       = useState('BTCUSDT');
  const [exchange,     setExchange]     = useState('binance');
  const [timeframe,    setTimeframe]    = useState('1h');
  const [strategyId,   setStrategyId]   = useState<number | null>(null);
  const [loading,      setLoading]      = useState(false);
  const [streamText,   setStreamText]   = useState('');
  const [signal,       setSignal]       = useState<string | null>(null);
  const [done,         setDone]         = useState(false);
  const [error,        setError]        = useState('');

  const abortRef  = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Check AI enabled
  useEffect(() => {
    api.get('/api/ai/enabled')
      .then(r => setEnabled(r.data.enabled))
      .catch(() => setEnabled(false));
  }, []);

  // Load strategies
  useEffect(() => {
    api.get('/api/strategies')
      .then(r => setStrategies(Array.isArray(r.data) ? r.data : []))
      .catch(() => {});
  }, []);

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [streamText]);

  // Extract signal
  useEffect(() => {
    if (streamText) {
      const s = extractSignal(streamText);
      if (s) setSignal(s);
    }
  }, [streamText]);

  const handleAnalyze = useCallback(async () => {
    if (!symbol.trim() || loading) return;

    abortRef.current?.abort();
    abortRef.current = new AbortController();

    setLoading(true);
    setStreamText('');
    setSignal(null);
    setDone(false);
    setError('');

    const sel = strategyId ? strategies.find(s => s.id === strategyId) : null;
    const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;

    // Use same base URL as axios instance
    const baseURL = (process.env.NEXT_PUBLIC_API_URL || '').replace(/\/$/, '');

    const body: Record<string, unknown> = {
      symbol: symbol.trim().toUpperCase(),
      exchange,
      timeframe,
      lang,
    };

    if (sel) {
      body.strategy = {
        name: sel.name,
        symbols: sel.symbols,
        timeframe: sel.timeframe,
        tp_percent: sel.tp_percent,
        sl_percent: sel.sl_percent,
        amount_usdt: sel.amount_usdt,
        entry_conditions: sel.entry_conditions,
        order_type: sel.order_type,
      };
    }

    try {
      const res = await fetch(`${baseURL}/api/ai/analyze`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(body),
        signal: abortRef.current.signal,
      });

      if (!res.ok) {
        let detail = res.statusText;
        try { const j = await res.json(); detail = j.detail || detail; } catch {}
        setError(`❌ ${res.status}: ${detail}`);
        setLoading(false);
        return;
      }

      // Try streaming first; fall back to full-response (Cloudflare buffer)
      const contentType = res.headers.get('content-type') || '';
      const isSSE = contentType.includes('event-stream');

      if (!isSSE || !res.body) {
        // Cloudflare or proxy buffered the whole response — read as text
        const text = await res.text();
        const lines = text.split('\n');
        let out = '';
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const raw = line.slice(6).trim();
          if (raw === '[DONE]') break;
          try { const p = JSON.parse(raw); if (p.text) out += p.text; } catch {}
        }
        setStreamText(out || '⚠️ Empty response from server.');
        setDone(true);
        setLoading(false);
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = '';

      while (true) {
        const { done: rd, value } = await reader.read();
        if (rd) break;

        buf += decoder.decode(value, { stream: true });
        const chunks = buf.split('\n\n');
        buf = chunks.pop() ?? '';

        for (const chunk of chunks) {
          const line = chunk.trim();
          if (!line.startsWith('data: ')) continue;
          const raw = line.slice(6);
          if (raw === '[DONE]') {
            setDone(true);
            setLoading(false);
            reader.cancel();
            return;
          }
          try {
            const parsed = JSON.parse(raw);
            if (parsed.text) setStreamText(prev => prev + parsed.text);
          } catch { /* ignore */ }
        }
      }
    } catch (e: unknown) {
      if (e instanceof Error && e.name === 'AbortError') return;
      setError(`❌ ${e instanceof Error ? e.message : 'Connection error'}`);
    } finally {
      setLoading(false);
    }
  }, [symbol, exchange, timeframe, lang, strategyId, strategies, loading]);

  const handleStop = () => {
    abortRef.current?.abort();
    setLoading(false);
  };

  const sigStyle = signal ? SIGNALS[signal] : null;

  return (
    <>
      <Nav />

      <style>{`
        @keyframes blink {
          0%, 100% { opacity: 1; }
          50% { opacity: 0; }
        }
        @keyframes pulse {
          0%, 100% { transform: scale(1); opacity: 1; }
          50% { transform: scale(1.4); opacity: 0.5; }
        }
        .pulse-dot {
          width: 7px; height: 7px; border-radius: 50%;
          background: var(--accent);
          animation: pulse 1.1s ease-in-out infinite;
          display: inline-block;
        }
      `}</style>

      <main style={{ maxWidth: 760, margin: '0 auto', padding: '2rem 1rem' }}>

        {/* Title */}
        <div style={{ marginBottom: '1.5rem' }}>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: '0.3rem' }}>
            {t('aiAnalysisTitle')}
          </h1>
          <p style={{ fontSize: '0.875rem', color: 'var(--fg-muted)' }}>
            {t('aiAnalysisSubtitle')}
          </p>
        </div>

        {/* Not configured warning */}
        {enabled === false && (
          <div style={{ background: '#450a0a', color: '#fca5a5', border: '1px solid #dc2626', borderRadius: 10, padding: '0.75rem 1rem', marginBottom: '1.25rem', fontSize: '0.875rem' }}>
            🔑 {t('aiNotEnabled')}
          </div>
        )}

        {/* Config card */}
        <div style={{ background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 12, padding: '1.25rem', marginBottom: '1.25rem' }}>

          {/* Row 1: symbol / exchange / timeframe */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0.75rem', marginBottom: '0.75rem' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: 'var(--fg-muted)', marginBottom: '0.35rem' }}>
                {t('symbolLabel')}
              </label>
              <input
                value={symbol}
                onChange={e => setSymbol(e.target.value.toUpperCase())}
                onKeyDown={e => e.key === 'Enter' && handleAnalyze()}
                placeholder={t('symbolPlaceholder')}
                className="input-field"
                style={{ width: '100%', fontFamily: 'monospace', letterSpacing: '0.04em' }}
                disabled={loading}
              />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: 'var(--fg-muted)', marginBottom: '0.35rem' }}>
                {t('exchange')}
              </label>
              <select value={exchange} onChange={e => setExchange(e.target.value)} className="input-field" style={{ width: '100%' }} disabled={loading}>
                <option value="binance">Binance</option>
                <option value="bybit">Bybit</option>
              </select>
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: 'var(--fg-muted)', marginBottom: '0.35rem' }}>
                {t('timeframe')}
              </label>
              <select value={timeframe} onChange={e => setTimeframe(e.target.value)} className="input-field" style={{ width: '100%' }} disabled={loading}>
                {TIMEFRAMES.map(tf => <option key={tf} value={tf}>{tf}</option>)}
              </select>
            </div>
          </div>

          {/* Strategy selector */}
          <div style={{ marginBottom: '1rem' }}>
            <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: 'var(--fg-muted)', marginBottom: '0.35rem' }}>
              {t('selectStrategy')}
            </label>
            <select
              value={strategyId ?? ''}
              onChange={e => setStrategyId(e.target.value ? Number(e.target.value) : null)}
              className="input-field"
              style={{ width: '100%' }}
              disabled={loading}
            >
              <option value="">{t('noStrategy')}</option>
              {strategies.map(s => (
                <option key={s.id} value={s.id}>
                  {s.name} — {(s.symbols ?? []).slice(0, 3).join(', ')}
                </option>
              ))}
            </select>
          </div>

          {/* Buttons + signal */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
            <button
              onClick={handleAnalyze}
              disabled={loading || !symbol.trim()}
              className="btn-primary"
              style={{ padding: '0.55rem 1.5rem', fontSize: '0.875rem', fontWeight: 600, minWidth: 130 }}
            >
              {loading
                ? <><span className="pulse-dot" style={{ marginRight: 6 }} />{t('analyzing')}</>
                : t('analyzeBtn')
              }
            </button>

            {loading && (
              <button
                onClick={handleStop}
                className="btn-secondary"
                style={{ padding: '0.55rem 1rem', fontSize: '0.875rem', color: 'var(--danger)' }}
              >
                ⏹ Stop
              </button>
            )}

            {signal && sigStyle && (
              <div style={{ marginLeft: 'auto', padding: '0.4rem 1rem', borderRadius: 8, fontWeight: 700, fontSize: '0.85rem', letterSpacing: '0.05em', background: sigStyle.bg, color: sigStyle.color, border: `1px solid ${sigStyle.border}` }}>
                {signal}
              </div>
            )}
          </div>
        </div>

        {/* Error */}
        {error && (
          <div style={{ background: '#450a0a', color: '#fca5a5', border: '1px solid #dc2626', borderRadius: 10, padding: '0.75rem 1rem', marginBottom: '1rem', fontSize: '0.875rem' }}>
            {error}
          </div>
        )}

        {/* Output */}
        {(streamText || loading) && (
          <div style={{ background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 12, overflow: 'hidden' }}>
            {/* Header bar */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.65rem 1.1rem', borderBottom: '1px solid var(--border)', background: 'var(--bg)' }}>
              <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--fg-muted)' }}>🤖 {t('aiPowered')}</span>
              {loading && (
                <span style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.75rem', color: 'var(--accent)' }}>
                  <span className="pulse-dot" style={{ width: 6, height: 6 }} />
                  {t('analyzing')}
                </span>
              )}
              {done && !loading && (
                <span style={{ marginLeft: 'auto', fontSize: '0.75rem', color: '#4ade80' }}>✅ {t('analysisReady')}</span>
              )}
            </div>

            {/* Content */}
            <div style={{ padding: '1.25rem', maxHeight: '70vh', overflowY: 'auto' }}>
              {streamText
                ? <MarkdownOutput text={streamText} streaming={loading} />
                : (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: 'var(--fg-muted)', padding: '2rem 0' }}>
                    <span className="pulse-dot" />
                    <span style={{ fontSize: '0.875rem' }}>{t('analyzing')}</span>
                  </div>
                )
              }
              <div ref={bottomRef} />
            </div>
          </div>
        )}

        {/* Empty state */}
        {!streamText && !loading && !error && (
          <div style={{ textAlign: 'center', padding: '3rem 1rem', border: '1px dashed var(--border)', borderRadius: 12, color: 'var(--fg-muted)' }}>
            <div style={{ fontSize: '3rem', marginBottom: '0.75rem' }}>🤖</div>
            <p style={{ fontSize: '0.875rem' }}>{t('aiAnalysisSubtitle')}</p>
          </div>
        )}

        {/* Disclaimer */}
        <p style={{ textAlign: 'center', fontSize: '0.75rem', color: 'var(--fg-muted)', marginTop: '1.25rem' }}>
          {t('aiDisclaimer')}
        </p>

      </main>
    </>
  );
}
