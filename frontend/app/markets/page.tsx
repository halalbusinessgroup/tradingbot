'use client';
import { useEffect, useState, useMemo, useCallback } from 'react';
import Nav from '@/components/Nav';
import { api } from '@/lib/api';
import { useI18n } from '@/lib/i18n';

type Market  = { symbol: string; base: string; quote: string; ccxt_symbol: string };
type Ticker  = { price: number; change24h: number; volume24h: number; high24h: number; low24h: number };
type SortKey = 'volume' | 'change' | 'name';

function fmt(n: number, decimals = 2): string {
  if (!n) return '—';
  if (n >= 1_000_000_000) return (n / 1_000_000_000).toFixed(2) + 'B';
  if (n >= 1_000_000)     return (n / 1_000_000).toFixed(2) + 'M';
  if (n >= 1_000)         return (n / 1_000).toFixed(2) + 'K';
  return n.toFixed(decimals);
}

function fmtPrice(n: number): string {
  if (!n) return '—';
  if (n >= 1000) return n.toLocaleString(undefined, { maximumFractionDigits: 2 });
  if (n >= 1)    return n.toFixed(4);
  if (n >= 0.01) return n.toFixed(6);
  return n.toFixed(8);
}

export default function MarketsPage() {
  const { t } = useI18n();
  const [exchange, setExchange]   = useState('binance');
  const [markets, setMarkets]     = useState<Market[]>([]);
  const [tickers, setTickers]     = useState<Record<string, Ticker>>({});
  const [loading, setLoading]     = useState(false);
  const [tickLoading, setTickLoading] = useState(false);
  const [error, setError]         = useState('');
  const [search, setSearch]       = useState('');
  const [sortKey, setSortKey]     = useState<SortKey>('volume');
  const [keys, setKeys]           = useState<any>({});
  const [modal, setModal]         = useState<{ symbol: string; base: string; tvSym: string } | null>(null);

  useEffect(() => {
    api.get('/api/users/exchange-keys').then(r => setKeys(r.data)).catch(() => {});
  }, []);

  const hasKey = (ex: string) => !!keys[ex];

  const loadMarkets = useCallback(async () => {
    setLoading(true); setError(''); setMarkets([]); setTickers({});
    try {
      const { data } = await api.get(`/api/users/markets?exchange=${exchange}`);
      setMarkets(data);
      // Fetch tickers async after markets load
      setTickLoading(true);
      try {
        const { data: t } = await api.get(`/api/users/tickers?exchange=${exchange}`);
        setTickers(t);
      } catch { /* tickers optional */ }
      setTickLoading(false);
    } catch (e: any) {
      setError(e.response?.data?.detail || t('error'));
    } finally {
      setLoading(false);
    }
  }, [exchange]);

  const filtered = useMemo(() => {
    let list = markets.filter(m =>
      !search ||
      m.base.toLowerCase().includes(search.toLowerCase()) ||
      m.symbol.toLowerCase().includes(search.toLowerCase())
    );
    list = [...list].sort((a, b) => {
      if (sortKey === 'volume') {
        return (tickers[b.symbol]?.volume24h || 0) - (tickers[a.symbol]?.volume24h || 0);
      }
      if (sortKey === 'change') {
        return (tickers[b.symbol]?.change24h || 0) - (tickers[a.symbol]?.change24h || 0);
      }
      return a.base.localeCompare(b.base);
    });
    return list;
  }, [markets, search, sortKey, tickers]);

  return (
    <div>
      <Nav />
      <div className="max-w-7xl mx-auto p-4 space-y-4">

        {/* Header row */}
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-xl font-bold">{t('spotMarkets')}</h1>

          {/* Exchange toggle */}
          <div className="flex gap-1 p-1 rounded-lg" style={{ background: 'var(--bg)', border: '1px solid var(--border)' }}>
            {['binance', 'bybit'].map(ex => (
              <button key={ex} onClick={() => { setExchange(ex); setMarkets([]); setTickers({}); setSearch(''); }}
                className="px-4 py-1.5 rounded text-sm font-semibold transition"
                style={{
                  background: exchange === ex ? 'var(--accent)' : 'transparent',
                  color: exchange === ex ? '#000' : 'var(--text)',
                }}>
                {ex === 'binance' ? '🟡 Binance' : '🟠 Bybit'}
                {!hasKey(ex) && <span style={{ color: 'var(--danger)', fontSize: '0.7rem' }}> ✕</span>}
              </button>
            ))}
          </div>

          <button onClick={loadMarkets} disabled={loading}
            className="btn btn-primary"
            style={{ opacity: loading ? 0.6 : 1 }}>
            {loading ? '⏳' : '🔄'} {t('loadMarkets')}
          </button>
        </div>

        {/* No key warning */}
        {!hasKey(exchange) && (
          <div className="card" style={{ borderColor: 'var(--danger)', background: 'rgba(239,68,68,0.05)' }}>
            <p style={{ color: 'var(--danger)', fontSize: '0.875rem' }}>
              ⚠️ {t('noApiKey')} <a href="/settings" className="text-accent">{t('addApiKey')}</a>
            </p>
          </div>
        )}

        {error && (
          <div className="card" style={{ borderColor: 'var(--danger)' }}>
            <p style={{ color: 'var(--danger)' }}>❌ {error}</p>
          </div>
        )}

        {/* Search + sort + stats */}
        {markets.length > 0 && (
          <div className="flex flex-wrap gap-3 items-center">
            <input className="input" style={{ maxWidth: 200 }}
              placeholder={t('search')}
              value={search} onChange={e => setSearch(e.target.value)} />

            <div className="flex gap-1 text-xs">
              {([['volume', t('sortByVolume')], ['change', t('sortByChange')], ['name', t('sortByName')]] as [SortKey, string][]).map(([k, label]) => (
                <button key={k} onClick={() => setSortKey(k)}
                  className="px-3 py-1.5 rounded font-semibold"
                  style={{
                    background: sortKey === k ? 'var(--accent)' : 'var(--bg)',
                    color: sortKey === k ? '#000' : 'var(--text)',
                    border: '1px solid var(--border)',
                  }}>
                  {label}
                </button>
              ))}
            </div>

            <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem', marginLeft: 'auto' }}>
              {filtered.length} {t('pairs')} {tickLoading && '⏳'}
            </span>
          </div>
        )}

        {/* Market table */}
        {markets.length > 0 && (
          <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
            {/* Table header */}
            <div className="grid text-xs font-semibold px-4 py-2"
              style={{
                gridTemplateColumns: '2fr 1fr 1fr 1fr 1fr',
                borderBottom: '1px solid var(--border)',
                color: 'var(--text-muted)',
              }}>
              <span>{t('coins')}</span>
              <span className="text-right">{t('price')}</span>
              <span className="text-right">{t('change24h')}</span>
              <span className="text-right hidden sm:block">{t('volume24h')}</span>
              <span className="text-right hidden sm:block">{t('high24h')}</span>
            </div>

            {/* Rows */}
            <div style={{ maxHeight: '70vh', overflowY: 'auto' }}>
              {filtered.map(m => {
                const tick = tickers[m.symbol];
                const ch = tick?.change24h ?? null;
                const color = ch === null ? 'var(--text-muted)' : ch >= 0 ? '#22c55e' : '#ef4444';
                const tvSym = `${exchange === 'binance' ? 'BINANCE' : 'BYBIT'}:${m.symbol}`;

                return (
                  <button key={m.symbol}
                    onClick={() => setModal({ symbol: m.symbol, base: m.base, tvSym })}
                    className="grid w-full px-4 py-3 text-left hover:bg-[var(--bg)] transition"
                    style={{
                      gridTemplateColumns: '2fr 1fr 1fr 1fr 1fr',
                      borderBottom: '1px solid var(--border)',
                      background: 'transparent',
                    }}>
                    {/* Coin name */}
                    <div className="flex items-center gap-2">
                      <div className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold"
                        style={{ background: 'var(--accent)', color: '#000', flexShrink: 0 }}>
                        {m.base.slice(0, 2)}
                      </div>
                      <div>
                        <div className="font-semibold text-sm">{m.base}</div>
                        <div style={{ color: 'var(--text-muted)', fontSize: '0.7rem' }}>/USDT</div>
                      </div>
                    </div>
                    {/* Price */}
                    <div className="text-right font-mono text-sm self-center">
                      {tick ? fmtPrice(tick.price) : '—'}
                    </div>
                    {/* Change */}
                    <div className="text-right font-semibold text-sm self-center" style={{ color }}>
                      {ch !== null ? `${ch >= 0 ? '+' : ''}${ch.toFixed(2)}%` : '—'}
                    </div>
                    {/* Volume */}
                    <div className="text-right text-sm self-center hidden sm:block" style={{ color: 'var(--text-muted)' }}>
                      {tick ? '$' + fmt(tick.volume24h) : '—'}
                    </div>
                    {/* High */}
                    <div className="text-right text-sm self-center hidden sm:block" style={{ color: '#22c55e' }}>
                      {tick ? fmtPrice(tick.high24h) : '—'}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Empty state */}
        {!loading && markets.length === 0 && !error && (
          <div className="card text-center py-16">
            <div className="text-5xl mb-3">📊</div>
            <p style={{ color: 'var(--text-muted)' }}>
              {hasKey(exchange)
                ? t('loadMarkets') + ' →'
                : t('noApiKey')}
            </p>
            {hasKey(exchange) && (
              <button onClick={loadMarkets} className="btn btn-primary mt-4">
                🔄 {t('loadMarkets')}
              </button>
            )}
          </div>
        )}
      </div>

      {/* TradingView Modal */}
      {modal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          style={{ background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(4px)' }}
          onClick={() => setModal(null)}>
          <div
            onClick={e => e.stopPropagation()}
            className="rounded-xl overflow-hidden"
            style={{
              background: 'var(--panel)', border: '1px solid var(--border)',
              width: '100%', maxWidth: 900,
            }}>
            {/* Modal header */}
            <div className="flex items-center justify-between px-4 py-3"
              style={{ borderBottom: '1px solid var(--border)' }}>
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold"
                  style={{ background: 'var(--accent)', color: '#000' }}>
                  {modal.base.slice(0, 2)}
                </div>
                <div>
                  <span className="font-bold">{modal.base}/USDT</span>
                  <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem', marginLeft: 6 }}>{modal.symbol}</span>
                </div>
                {tickers[modal.symbol] && (() => {
                  const t2 = tickers[modal.symbol];
                  const ch = t2.change24h;
                  return (
                    <div className="flex gap-4 text-sm ml-4">
                      <span className="font-mono font-bold">${fmtPrice(t2.price)}</span>
                      <span style={{ color: ch >= 0 ? '#22c55e' : '#ef4444', fontWeight: 600 }}>
                        {ch >= 0 ? '+' : ''}{ch.toFixed(2)}%
                      </span>
                      <span style={{ color: 'var(--text-muted)' }}>Vol: ${fmt(t2.volume24h)}</span>
                    </div>
                  );
                })()}
              </div>
              <div className="flex gap-2 items-center">
                <a href={`/dashboard?symbol=${modal.tvSym}`}
                  className="btn btn-primary text-sm">
                  {t('viewChart')} →
                </a>
                <button onClick={() => setModal(null)}
                  className="btn btn-secondary text-lg px-3" style={{ lineHeight: 1 }}>×</button>
              </div>
            </div>

            {/* TradingView widget */}
            <div style={{ height: 480 }}>
              <iframe
                key={modal.tvSym}
                src={`https://s.tradingview.com/widgetembed/?symbol=${encodeURIComponent(modal.tvSym)}&interval=15&theme=dark&style=1&locale=en&toolbar_bg=%23101418&enable_publishing=false&hide_top_toolbar=false&hide_legend=false&saveimage_showing=false&studies=RSI%40tv-basicstudies`}
                style={{ width: '100%', height: '100%', border: 'none' }}
                allow="clipboard-write"
                sandbox="allow-top-navigation allow-top-navigation-by-user-activation allow-popups allow-popups-to-escape-sandbox allow-scripts allow-forms allow-same-origin allow-presentation allow-downloads"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
