'use client';
import { useEffect, useState, useRef } from 'react';
import Nav from '@/components/Nav';
import TradingViewWidget from '@/components/TradingViewWidget';
import { api } from '@/lib/api';
import { useI18n } from '@/lib/i18n';
import { useToast } from '@/lib/toast';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from 'recharts';

export default function Dashboard() {
  const { t } = useI18n();
  const { show } = useToast();
  const [me, setMe] = useState<any>(null);
  const [stats, setStats] = useState<any>(null);
  const [trades, setTrades] = useState<any[]>([]);
  const [closedTrades, setClosedTrades] = useState<any[]>([]);
  const [balance, setBalance] = useState<any>(null);
  const [logs, setLogs] = useState<any[]>([]);
  const [balanceExchange, setBalanceExchange] = useState('binance');
  const [closingId, setClosingId] = useState<number | null>(null);
  const [chartPeriod, setChartPeriod] = useState<'all' | '7d' | '30d'>('all');
  const logsRef = useRef<HTMLDivElement>(null);

  async function load() {
    try {
      const [m, s, tr, cl] = await Promise.all([
        api.get('/api/auth/me'),
        api.get('/api/trades/stats'),
        api.get('/api/trades?status=OPEN'),
        api.get('/api/trades?limit=30'),
      ]);
      setMe(m.data); setStats(s.data); setTrades(tr.data); setClosedTrades(cl.data);
      try { const b = await api.get(`/api/users/balance?exchange=${balanceExchange}`); setBalance(b.data); } catch {}
    } catch (e: any) {
      if (e.response?.status === 401) window.location.href = '/login';
    }
  }

  async function loadLogs() {
    try {
      const { data } = await api.get('/api/users/bot-logs?limit=40');
      setLogs(data);
    } catch {}
  }

  useEffect(() => {
    load();
    loadLogs();
    const id1 = setInterval(load, 6000);
    const id2 = setInterval(loadLogs, 10000);
    return () => { clearInterval(id1); clearInterval(id2); };
  }, [balanceExchange]);

  async function toggleBot() {
    if (!me.can_trade) {
      show(t('tradingDisabledByAdmin'), 'error');
      return;
    }
    try {
      const next = !me.bot_enabled;
      await api.post('/api/users/bot/toggle', { enabled: next });
      show(next ? t('botStarted') : t('botStopped'), next ? 'success' : 'warning');
      load();
    } catch (e: any) {
      show(e.response?.data?.detail || t('error'), 'error');
    }
  }

  async function closeTrade(tradeId: number) {
    if (!confirm(t('confirmCloseTrade'))) return;
    setClosingId(tradeId);
    try {
      const { data } = await api.post(`/api/trades/${tradeId}/close`);
      show(`✅ Trade bağlandı | PnL: ${data.pnl >= 0 ? '+' : ''}${data.pnl?.toFixed(4)} USDT`, 'success');
      load();
    } catch (e: any) {
      show(e.response?.data?.detail || t('error'), 'error');
    } finally {
      setClosingId(null);
    }
  }

  // Build equity curve from closed trades
  const allClosed = closedTrades
    .filter(t => t.status !== 'OPEN' && t.pnl !== null && t.closed_at)
    .sort((a, b) => new Date(a.closed_at).getTime() - new Date(b.closed_at).getTime());

  const now = Date.now();
  const periodMs: Record<string, number> = { '7d': 7 * 86400000, '30d': 30 * 86400000, all: Infinity };
  const filteredClosed = chartPeriod === 'all'
    ? allClosed
    : allClosed.filter(t => now - new Date(t.closed_at).getTime() <= periodMs[chartPeriod]);

  let cumulative = 0;
  const chartData = filteredClosed.map((t, i) => {
    cumulative += t.pnl || 0;
    return {
      name: `#${i + 1}`,
      date: new Date(t.closed_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
      pnl: parseFloat(cumulative.toFixed(4)),
      tradePnl: parseFloat((t.pnl || 0).toFixed(4)),
      symbol: t.symbol,
      reason: t.status?.replace('CLOSED_', '') || '',
    };
  });

  if (!me) return <div className="p-10">{t('loading')}</div>;

  return (
    <div>
      <Nav />
      <div className="max-w-7xl mx-auto p-4 sm:p-6 space-y-5">

        {/* Header */}
        <div className="flex items-center justify-between flex-wrap gap-3">
          <h1 className="text-xl sm:text-2xl font-bold">
            {t('hello')}, {me.first_name || me.email}!
          </h1>
          <div className="flex items-center gap-2 flex-wrap">
            {trades.some((tr: any) => tr.paper_trade) && (
              <span className="text-xs px-2 py-1 rounded-full"
                style={{ background: '#1e3a5f', color: '#60a5fa' }}>
                📄 {t('paperMode')}
              </span>
            )}
            <button onClick={toggleBot}
              disabled={!me.can_trade}
              className={`btn ${me.bot_enabled ? 'btn-danger' : 'btn-primary'}`}
              title={!me.can_trade ? t('tradingDisabledByAdmin') : ''}>
              {me.bot_enabled ? t('stopBot') : t('startBot')}
            </button>
          </div>
        </div>

        {!me.can_trade && (
          <div className="p-3 rounded-lg text-sm"
            style={{ background: '#3a1a1a', border: '1px solid #ef4444', color: '#ef4444' }}>
            ⚠️ {t('tradingDisabledByAdmin')}
          </div>
        )}

        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Stat label={t('openTrades')} value={stats?.open_trades ?? 0} />
          <Stat label={t('closedTrades')} value={stats?.closed_trades ?? 0} />
          <Stat label={t('totalPnl')} value={`${(stats?.total_pnl ?? 0).toFixed(4)} USDT`}
            color={(stats?.total_pnl ?? 0) >= 0 ? '#22c55e' : '#ef4444'} />
          <Stat label={t('winRate')} value={`${stats?.win_rate ?? 0}%`} />
        </div>

        {/* PnL Equity Curve (recharts) */}
        <div className="card">
          <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
            <h2 className="font-bold">📈 {t('pnlChart')}</h2>
            <div className="flex gap-1">
              {(['7d', '30d', 'all'] as const).map(p => (
                <button key={p} onClick={() => setChartPeriod(p)}
                  className="text-xs px-3 py-1 rounded-full"
                  style={{
                    background: chartPeriod === p ? 'var(--accent)' : 'var(--bg)',
                    color: chartPeriod === p ? '#000' : 'var(--text-muted)',
                    border: '1px solid var(--border)',
                    fontWeight: chartPeriod === p ? 700 : 400,
                  }}>
                  {p === 'all' ? 'All' : p}
                </button>
              ))}
            </div>
          </div>

          {chartData.length < 2 ? (
            <div className="flex items-center justify-center" style={{ height: 140, color: 'var(--text-muted)', fontSize: '0.85rem' }}>
              {chartData.length === 0 ? 'No closed trades yet.' : 'Need at least 2 trades to draw chart.'}
            </div>
          ) : (
            <>
              <ResponsiveContainer width="100%" height={160}>
                <AreaChart data={chartData} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                  <defs>
                    <linearGradient id="pnlGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={chartData[chartData.length - 1].pnl >= 0 ? '#22c55e' : '#ef4444'} stopOpacity={0.3} />
                      <stop offset="95%" stopColor={chartData[chartData.length - 1].pnl >= 0 ? '#22c55e' : '#ef4444'} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="date" tick={{ fontSize: 10, fill: 'var(--text-muted)' }} tickLine={false} />
                  <YAxis tick={{ fontSize: 10, fill: 'var(--text-muted)' }} tickLine={false} axisLine={false}
                    tickFormatter={v => `${v >= 0 ? '+' : ''}${v}`} width={55} />
                  <ReferenceLine y={0} stroke="var(--border)" strokeDasharray="4 2" />
                  <Tooltip
                    contentStyle={{ background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }}
                    formatter={(value: any, name: string) => [
                      `${value >= 0 ? '+' : ''}${value} USDT`,
                      name === 'pnl' ? 'Cumulative PnL' : 'Trade PnL',
                    ]}
                    labelFormatter={(label, payload) => {
                      const d = payload?.[0]?.payload;
                      return d ? `${d.symbol} ${d.reason} — ${label}` : label;
                    }}
                  />
                  <Area type="monotone" dataKey="pnl" stroke={chartData[chartData.length - 1].pnl >= 0 ? '#22c55e' : '#ef4444'}
                    strokeWidth={2} fill="url(#pnlGrad)" dot={false} />
                </AreaChart>
              </ResponsiveContainer>
              <div className="flex justify-between text-xs mt-2" style={{ color: 'var(--text-muted)' }}>
                <span>{chartData.length} {t('closedTrades')}</span>
                <span style={{ color: chartData[chartData.length - 1].pnl >= 0 ? '#22c55e' : '#ef4444', fontWeight: 600 }}>
                  {chartData[chartData.length - 1].pnl >= 0 ? '+' : ''}{chartData[chartData.length - 1].pnl} USDT
                </span>
              </div>
            </>
          )}
        </div>

        {/* Balance */}
        {balance && Object.keys(balance).length > 0 && (
          <div className="card">
            <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
              <h2 className="font-bold">{t('balance')}</h2>
              <select className="input" style={{ maxWidth: 160 }} value={balanceExchange}
                onChange={e => setBalanceExchange(e.target.value)}>
                <option value="binance">Binance</option>
                <option value="bybit">Bybit</option>
              </select>
            </div>
            <div className="grid grid-cols-3 sm:grid-cols-5 md:grid-cols-8 gap-2 text-sm">
              {Object.entries(balance).map(([asset, v]: any) => (
                <div key={asset} className="p-2 rounded text-center" style={{ background: 'var(--bg)' }}>
                  <div className="text-xs" style={{ color: 'var(--text-muted)' }}>{asset}</div>
                  <div className="font-bold text-sm">{v.free.toFixed(4)}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Chart */}
        <div className="card">
          <h2 className="font-bold mb-3">{t('marketChart')}</h2>
          <TradingViewWidget symbol="BINANCE:BTCUSDT" />
        </div>

        {/* Open Trades */}
        <div className="card">
          <h2 className="font-bold mb-3">{t('openTradesTitle')}</h2>
          {trades.length === 0 ? (
            <p style={{ color: 'var(--text-muted)' }}>{t('noOpenTrades')}</p>
          ) : (
            <div className="overflow-x-auto">
              <table>
                <thead><tr>
                  <th>{t('coin')}</th>
                  <th>{t('entry')}</th>
                  <th>{t('qty')}</th>
                  <th style={{ color: '#22c55e' }}>TP</th>
                  <th style={{ color: '#ef4444' }}>SL</th>
                  <th>{t('status')}</th>
                  <th></th>
                </tr></thead>
                <tbody>
                  {trades.map(tr => (
                    <tr key={tr.id}>
                      <td className="font-bold">
                        {tr.symbol}
                        {tr.paper_trade && (
                          <span className="ml-1 text-xs px-1 rounded"
                            style={{ background: '#1e3a5f', color: '#60a5fa' }}>📄</span>
                        )}
                      </td>
                      <td>{tr.entry_price?.toFixed(4)}</td>
                      <td>{tr.qty?.toFixed(4)}</td>
                      <td style={{ color: '#22c55e' }}>{tr.tp_price?.toFixed(4)}</td>
                      <td style={{ color: '#ef4444' }}>{tr.sl_price?.toFixed(4)}</td>
                      <td>
                        <span className="text-xs px-2 py-1 rounded-full"
                          style={{ background: '#1a3a2a', color: '#22c55e' }}>
                          {tr.status}
                        </span>
                      </td>
                      <td>
                        <button
                          onClick={() => closeTrade(tr.id)}
                          disabled={closingId === tr.id}
                          className="btn btn-danger text-xs"
                          style={{ padding: '4px 8px' }}>
                          {closingId === tr.id ? '...' : t('closeTrade')}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Bot Logs */}
        <div className="card">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-bold">{t('botLogsTitle')}</h2>
            <button onClick={loadLogs} className="btn btn-secondary text-sm">↻ {t('refresh')}</button>
          </div>
          <div ref={logsRef} style={{ maxHeight: 280, overflowY: 'auto', fontFamily: 'monospace', fontSize: '0.78rem' }}>
            {logs.length === 0 ? (
              <p style={{ color: 'var(--text-muted)' }}>
                {me.bot_enabled ? t('botRunning') : t('botInactive')}
              </p>
            ) : logs.map(l => (
              <div key={l.id} className="flex gap-2 py-1"
                style={{ borderBottom: '1px solid var(--border)' }}>
                <span style={{
                  color: l.level === 'ERROR' ? '#ef4444' : l.level === 'WARN' ? '#f59e0b' : '#22c55e',
                  minWidth: 48, fontWeight: 600,
                }}>
                  {l.level}
                </span>
                <span style={{ color: 'var(--text-muted)', minWidth: 80 }}>
                  {l.created_at ? new Date(l.created_at).toLocaleTimeString() : ''}
                </span>
                <span style={{ color: 'var(--text)', wordBreak: 'break-all' }}>{l.message}</span>
              </div>
            ))}
          </div>
          {logs.length === 0 && me.bot_enabled && (
            <p className="text-xs mt-2" style={{ color: 'var(--text-muted)' }}>
              {t('logHint')}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value, color }: { label: string; value: any; color?: string }) {
  return (
    <div className="card">
      <div style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>{label}</div>
      <div className="text-xl font-bold mt-1" style={{ color: color || 'var(--text)' }}>{value}</div>
    </div>
  );
}
