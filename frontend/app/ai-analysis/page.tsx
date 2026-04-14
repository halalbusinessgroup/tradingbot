'use client';
import { useState, useEffect, useRef, useCallback } from 'react';
import Nav from '@/components/Nav';
import { useI18n } from '@/lib/i18n';
import { API } from '@/lib/api';

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

// ─── Signal badge helper ─────────────────────────────────────────────────────

const SIGNAL_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  'STRONG BUY':  { bg: '#064e3b', text: '#34d399', border: '#059669' },
  'BUY':         { bg: '#052e16', text: '#4ade80', border: '#16a34a' },
  'NEUTRAL':     { bg: '#1c1917', text: '#a8a29e', border: '#57534e' },
  'SELL':        { bg: '#450a0a', text: '#f87171', border: '#dc2626' },
  'STRONG SELL': { bg: '#3b0764', text: '#e879f9', border: '#a21caf' },
};

function extractSignal(text: string): string | null {
  const patterns = ['STRONG BUY', 'STRONG SELL', 'BUY', 'SELL', 'NEUTRAL'];
  for (const p of patterns) {
    if (text.includes(p)) return p;
  }
  return null;
}

// ─── Simple markdown renderer ─────────────────────────────────────────────────

function renderMarkdown(text: string): string {
  return text
    // Code blocks
    .replace(/```[\w]*\n?([\s\S]*?)```/g, '<pre class="ai-code">$1</pre>')
    // Bold
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    // Italic
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    // Headers
    .replace(/^### (.*?)$/gm, '<h3 class="ai-h3">$1</h3>')
    .replace(/^## (.*?)$/gm, '<h2 class="ai-h2">$1</h2>')
    .replace(/^# (.*?)$/gm, '<h1 class="ai-h1">$1</h1>')
    // Horizontal rule
    .replace(/^---$/gm, '<hr class="ai-hr" />')
    // Bullet lists
    .replace(/^[-•] (.*?)$/gm, '<li class="ai-li">$1</li>')
    // Numbered lists
    .replace(/^\d+\. (.*?)$/gm, '<li class="ai-li ai-li-num">$1</li>')
    // Line breaks
    .replace(/\n\n/g, '</p><p class="ai-p">')
    .replace(/\n/g, '<br/>');
}

// ─── TIMEFRAMES ──────────────────────────────────────────────────────────────

const TIMEFRAMES = ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '12h', '1d', '3d', '1w'];

// ─── Main page ───────────────────────────────────────────────────────────────

export default function AIAnalysisPage() {
  const { t, lang } = useI18n();

  const [enabled, setEnabled]         = useState<boolean | null>(null);
  const [strategies, setStrategies]   = useState<Strategy[]>([]);
  const [symbol, setSymbol]           = useState('BTCUSDT');
  const [exchange, setExchange]       = useState('binance');
  const [timeframe, setTimeframe]     = useState('1h');
  const [strategyId, setStrategyId]   = useState<number | null>(null);
  const [loading, setLoading]         = useState(false);
  const [streamText, setStreamText]   = useState('');
  const [signal, setSignal]           = useState<string | null>(null);
  const [done, setDone]               = useState(false);

  const abortRef    = useRef<AbortController | null>(null);
  const outputRef   = useRef<HTMLDivElement>(null);

  // Check if AI is enabled on server
  useEffect(() => {
    API.get('/api/ai/enabled')
      .then(r => r.json())
      .then(d => setEnabled(d.enabled))
      .catch(() => setEnabled(false));
  }, []);

  // Load user's strategies for the optional dropdown
  useEffect(() => {
    API.get('/api/strategies')
      .then(r => r.json())
      .then(d => setStrategies(Array.isArray(d) ? d : []))
      .catch(() => {});
  }, []);

  // Auto-scroll to bottom while streaming
  useEffect(() => {
    if (outputRef.current && loading) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [streamText, loading]);

  // Extract signal when new text arrives
  useEffect(() => {
    if (streamText) {
      const found = extractSignal(streamText);
      if (found) setSignal(found);
    }
  }, [streamText]);

  const handleAnalyze = useCallback(async () => {
    if (!symbol.trim()) return;

    // Cancel any ongoing stream
    if (abortRef.current) abortRef.current.abort();
    abortRef.current = new AbortController();

    setLoading(true);
    setStreamText('');
    setSignal(null);
    setDone(false);

    const selectedStrategy = strategyId
      ? strategies.find(s => s.id === strategyId) ?? null
      : null;

    const body: Record<string, unknown> = {
      symbol: symbol.trim().toUpperCase(),
      exchange,
      timeframe,
      lang,
    };

    if (selectedStrategy) {
      body.strategy = {
        name: selectedStrategy.name,
        symbols: selectedStrategy.symbols,
        timeframe: selectedStrategy.timeframe,
        tp_percent: selectedStrategy.tp_percent,
        sl_percent: selectedStrategy.sl_percent,
        amount_usdt: selectedStrategy.amount_usdt,
        entry_conditions: selectedStrategy.entry_conditions,
        order_type: selectedStrategy.order_type,
      };
    }

    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || ''}/api/ai/analyze`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(body),
        signal: abortRef.current.signal,
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setStreamText(`❌ Error: ${err.detail || res.statusText}`);
        setLoading(false);
        return;
      }

      const reader = res.body?.getReader();
      const decoder = new TextDecoder();
      if (!reader) { setLoading(false); return; }

      let buffer = '';

      while (true) {
        const { done: rdDone, value } = await reader.read();
        if (rdDone) break;

        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop() ?? '';

        for (const part of parts) {
          const line = part.trim();
          if (!line.startsWith('data: ')) continue;
          const data = line.slice(6);
          if (data === '[DONE]') {
            setDone(true);
            setLoading(false);
            return;
          }
          try {
            const payload = JSON.parse(data);
            if (payload.text) {
              setStreamText(prev => prev + payload.text);
            }
          } catch {
            // ignore malformed
          }
        }
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') return;
      setStreamText(prev => prev + '\n\n❌ Stream interrupted.');
    } finally {
      setLoading(false);
    }
  }, [symbol, exchange, timeframe, lang, strategyId, strategies]);

  const handleStop = () => {
    if (abortRef.current) abortRef.current.abort();
    setLoading(false);
  };

  const signalStyle = signal ? SIGNAL_COLORS[signal] ?? SIGNAL_COLORS['NEUTRAL'] : null;

  return (
    <>
      <Nav />
      <style>{`
        .ai-output {
          font-family: inherit;
          line-height: 1.75;
          color: var(--fg);
        }
        .ai-h1 { font-size: 1.4rem; font-weight: 700; margin: 1rem 0 0.5rem; color: var(--accent); }
        .ai-h2 { font-size: 1.2rem; font-weight: 700; margin: 1rem 0 0.4rem; color: var(--accent); }
        .ai-h3 { font-size: 1rem;   font-weight: 700; margin: 0.8rem 0 0.3rem; }
        .ai-p  { margin: 0.5rem 0; }
        .ai-li { margin: 0.25rem 0 0.25rem 1.25rem; list-style: disc; }
        .ai-li-num { list-style: decimal; }
        .ai-hr { border: none; border-top: 1px solid var(--border); margin: 1rem 0; }
        .ai-code {
          background: var(--bg);
          border: 1px solid var(--border);
          border-radius: 6px;
          padding: 0.75rem 1rem;
          overflow-x: auto;
          font-size: 0.85rem;
          margin: 0.5rem 0;
        }
        .ai-cursor::after {
          content: '▋';
          animation: blink 1s step-end infinite;
          color: var(--accent);
        }
        @keyframes blink {
          0%, 100% { opacity: 1; }
          50%       { opacity: 0; }
        }
        .pulse-dot {
          width: 8px; height: 8px; border-radius: 50%;
          background: var(--accent);
          animation: pulse 1.2s ease-in-out infinite;
        }
        @keyframes pulse {
          0%, 100% { transform: scale(1); opacity: 1; }
          50%       { transform: scale(1.5); opacity: 0.5; }
        }
      `}</style>

      <main className="max-w-3xl mx-auto px-4 py-8">

        {/* Header */}
        <div className="mb-6">
          <h1 className="text-2xl font-bold mb-1">{t('aiAnalysisTitle')}</h1>
          <p style={{ color: 'var(--fg-muted)', fontSize: '0.9rem' }}>{t('aiAnalysisSubtitle')}</p>
        </div>

        {/* Not enabled warning */}
        {enabled === false && (
          <div className="rounded-xl p-4 mb-6 text-sm"
            style={{ background: '#450a0a', color: '#fca5a5', border: '1px solid #dc2626' }}>
            🔑 {t('aiNotEnabled')}
          </div>
        )}

        {/* Config card */}
        <div className="rounded-xl p-5 mb-6"
          style={{ background: 'var(--panel)', border: '1px solid var(--border)' }}>

          <div className="grid gap-4" style={{ gridTemplateColumns: '1fr 1fr 1fr' }}>

            {/* Symbol */}
            <div>
              <label className="block text-xs font-semibold mb-1.5" style={{ color: 'var(--fg-muted)' }}>
                {t('symbolLabel')}
              </label>
              <input
                value={symbol}
                onChange={e => setSymbol(e.target.value.toUpperCase())}
                placeholder={t('symbolPlaceholder')}
                className="w-full input-field text-sm font-mono"
                style={{ letterSpacing: '0.05em' }}
                disabled={loading}
              />
            </div>

            {/* Exchange */}
            <div>
              <label className="block text-xs font-semibold mb-1.5" style={{ color: 'var(--fg-muted)' }}>
                {t('exchange')}
              </label>
              <select
                value={exchange}
                onChange={e => setExchange(e.target.value)}
                className="w-full input-field text-sm"
                disabled={loading}
              >
                <option value="binance">Binance</option>
                <option value="bybit">Bybit</option>
              </select>
            </div>

            {/* Timeframe */}
            <div>
              <label className="block text-xs font-semibold mb-1.5" style={{ color: 'var(--fg-muted)' }}>
                {t('timeframe')}
              </label>
              <select
                value={timeframe}
                onChange={e => setTimeframe(e.target.value)}
                className="w-full input-field text-sm"
                disabled={loading}
              >
                {TIMEFRAMES.map(tf => <option key={tf} value={tf}>{tf}</option>)}
              </select>
            </div>
          </div>

          {/* Strategy selector */}
          <div className="mt-4">
            <label className="block text-xs font-semibold mb-1.5" style={{ color: 'var(--fg-muted)' }}>
              {t('selectStrategy')}
            </label>
            <select
              value={strategyId ?? ''}
              onChange={e => setStrategyId(e.target.value ? Number(e.target.value) : null)}
              className="w-full input-field text-sm"
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

          {/* Analyze button */}
          <div className="flex gap-3 mt-5 items-center">
            <button
              onClick={handleAnalyze}
              disabled={loading || enabled === false || !symbol.trim()}
              className="btn-primary px-6 py-2.5 text-sm font-semibold"
              style={{ minWidth: 140 }}
            >
              {loading ? (
                <span className="flex items-center gap-2">
                  <span className="pulse-dot" />
                  {t('analyzing')}
                </span>
              ) : t('analyzeBtn')}
            </button>

            {loading && (
              <button
                onClick={handleStop}
                className="btn-secondary px-4 py-2.5 text-sm"
                style={{ color: 'var(--danger)', borderColor: 'var(--danger)' }}
              >
                ⏹ Stop
              </button>
            )}

            {/* Signal badge */}
            {signal && signalStyle && (
              <div className="ml-auto px-4 py-2 rounded-lg font-bold text-sm"
                style={{
                  background: signalStyle.bg,
                  color: signalStyle.text,
                  border: `1px solid ${signalStyle.border}`,
                  letterSpacing: '0.05em',
                }}>
                {signal}
              </div>
            )}
          </div>
        </div>

        {/* Output card */}
        {(streamText || loading) && (
          <div className="rounded-xl overflow-hidden"
            style={{ border: '1px solid var(--border)', background: 'var(--panel)' }}>

            {/* Output header bar */}
            <div className="px-5 py-3 flex items-center gap-3"
              style={{ borderBottom: '1px solid var(--border)', background: 'var(--bg)' }}>
              <span className="text-xs font-semibold" style={{ color: 'var(--fg-muted)' }}>
                🤖 {t('aiPowered')}
              </span>
              {loading && (
                <span className="ml-auto flex items-center gap-2 text-xs" style={{ color: 'var(--accent)' }}>
                  <span className="pulse-dot" style={{ width: 6, height: 6 }} />
                  {t('analyzing')}
                </span>
              )}
              {done && !loading && (
                <span className="ml-auto text-xs" style={{ color: '#4ade80' }}>
                  ✅ {t('analysisReady')}
                </span>
              )}
            </div>

            {/* Scrollable output */}
            <div
              ref={outputRef}
              className="px-5 py-5 overflow-y-auto ai-output"
              style={{ maxHeight: '65vh', minHeight: 200 }}
            >
              {streamText ? (
                <div
                  className={loading ? 'ai-cursor' : ''}
                  dangerouslySetInnerHTML={{
                    __html: '<p class="ai-p">' + renderMarkdown(streamText) + '</p>'
                  }}
                />
              ) : (
                <div className="flex items-center gap-3 h-24" style={{ color: 'var(--fg-muted)' }}>
                  <span className="pulse-dot" />
                  <span className="text-sm">{t('analyzing')}</span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Empty state */}
        {!streamText && !loading && (
          <div className="rounded-xl p-10 text-center"
            style={{ border: '1px dashed var(--border)', color: 'var(--fg-muted)' }}>
            <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>🤖</div>
            <p className="text-sm">{t('aiAnalysisSubtitle')}</p>
          </div>
        )}

        {/* Disclaimer */}
        <p className="text-xs mt-4 text-center" style={{ color: 'var(--fg-muted)' }}>
          {t('aiDisclaimer')}
        </p>

      </main>
    </>
  );
}
