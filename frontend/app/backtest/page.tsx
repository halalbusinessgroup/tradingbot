'use client';
import { useState } from 'react';
import Nav from '@/components/Nav';
import { api } from '@/lib/api';
import { useI18n } from '@/lib/i18n';
import { useToast } from '@/lib/toast';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from 'recharts';

const TIMEFRAMES = ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d', '3d', '1w'];
const INDICATOR_GROUPS = [
  { label: 'Trend',      items: ['EMA', 'SMA', 'MACD'] },
  { label: 'Momentum',   items: ['RSI', 'STOCH_K', 'STOCH_D', 'CCI', 'WILLIAMS_R'] },
  { label: 'Volatility', items: ['BB_UPPER', 'BB_LOWER', 'BB_PERCENT', 'ATR'] },
  { label: 'Volume',     items: ['OBV', 'VOLUME'] },
  { label: 'Other',      items: ['PRICE'] },
];
const OPS = ['<', '>', '<=', '>=', '=='];

type Condition = { indicator: string; period: number; op: string; value: number };

const defaultConfig = () => ({
  symbol: 'SOLUSDT',
  exchange: 'binance',
  timeframe: '1h',
  days: 30,
  tp_percent: 3,
  sl_percent: 1.5,
  amount_usdt: 100,
  no_conditions: false,
  conditions: [{ indicator: 'RSI', period: 14, op: '<', value: 30 }] as Condition[],
});

function StatCard({ label, value, color }: { label: string; value: string | number; color?: string }) {
  return (
    <div className="p-3 rounded-lg text-center" style={{ background: 'var(--bg)' }}>
      <div className="text-xs mb-1" style={{ color: 'var(--text-muted)' }}>{label}</div>
      <div className="font-bold" style={{ color: color || 'inherit' }}>{value}</div>
    </div>
  );
}

export default function BacktestPage() {
  const { t } = useI18n();
  const { show } = useToast();
  const [cfg, setCfg] = useState(defaultConfig());
  const [result, setResult] = useState<any>(null);
  const [running, setRunning] = useState(false);
  const [showTrades, setShowTrades] = useState(false);

  const set = (k: string, v: any) => setCfg(p => ({ ...p, [k]: v }));

  function addCondition() {
    set('conditions', [...cfg.conditions, { indicator: 'RSI', period: 14, op: '<', value: 30 }]);
  }
  function removeCondition(i: number) {
    set('conditions', cfg.conditions.filter((_, j) => j !== i));
  }
  function setCondition(i: number, k: string, v: any) {
    const next = cfg.conditions.map((c, j) => j === i ? { ...c, [k]: v } : c);
    set('conditions', next);
  }

  async function runBacktest() {
    setRunning(true);
    setResult(null);
    try {
      const payload = {
        symbol: cfg.symbol.toUpperCase(),
        exchange: cfg.exchange,
        timeframe: cfg.timeframe,
        days: Number(cfg.days),
        tp_percent: Number(cfg.tp_percent),
        sl_percent: Number(cfg.sl_percent),
        amount_usdt: Number(cfg.amount_usdt),
        no_conditions: cfg.no_conditions,
        entry_conditions: cfg.no_conditions ? [] : cfg.conditions,
      };
      const { data } = await api.post('/api/backtest/run', payload);
      setResult(data);
      if (data.total_trades === 0) {
        show('No trades matched in this period. Try adjusting conditions or period.', 'warning');
      }
    } catch (e: any) {
      show(e.response?.data?.detail || t('error'), 'error');
    } finally {
      setRunning(false);
    }
  }

  const pnlColor = result?.total_pnl >= 0 ? '#22c55e' : '#ef4444';

  return (
    <div>
      <Nav />
      <div className="max-w-7xl mx-auto p-4 sm:p-6">
        <h1 className="text-2xl font-bold mb-5">📊 {t('backtestTitle')}</h1>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">

          {/* ── Config Panel ── */}
          <div className="lg:col-span-1 space-y-4">
            <div className="card space-y-3">
              <h2 className="font-bold text-sm">⚙️ Configuration</h2>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="label">Symbol</label>
                  <input className="input" value={cfg.symbol}
                    onChange={e => set('symbol', e.target.value.toUpperCase())}
                    placeholder="SOLUSDT" />
                </div>
                <div>
                  <label className="label">{t('exchange')}</label>
                  <select className="input" value={cfg.exchange} onChange={e => set('exchange', e.target.value)}>
                    <option value="binance">Binance</option>
                    <option value="bybit">Bybit</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="label">{t('timeframe')}</label>
                  <select className="input" value={cfg.timeframe} onChange={e => set('timeframe', e.target.value)}>
                    {TIMEFRAMES.map(tf => <option key={tf}>{tf}</option>)}
                  </select>
                </div>
                <div>
                  <label className="label">{t('backtestDays')}</label>
                  <select className="input" value={cfg.days} onChange={e => set('days', Number(e.target.value))}>
                    {[7, 14, 30, 60, 90, 180, 365].map(d => (
                      <option key={d} value={d}>{d} {t('days')}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-2">
                <div>
                  <label className="label">{t('tp')} %</label>
                  <input className="input" type="number" step="0.1" value={cfg.tp_percent}
                    onChange={e => set('tp_percent', e.target.value)} />
                </div>
                <div>
                  <label className="label">{t('sl')} %</label>
                  <input className="input" type="number" step="0.1" value={cfg.sl_percent}
                    onChange={e => set('sl_percent', e.target.value)} />
                </div>
                <div>
                  <label className="label">USDT</label>
                  <input className="input" type="number" value={cfg.amount_usdt}
                    onChange={e => set('amount_usdt', e.target.value)} />
                </div>
              </div>

              {/* Conditions */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="label mb-0">{t('entryConditions')}</label>
                  <label className="flex items-center gap-1 text-xs cursor-pointer" style={{ color: 'var(--text-muted)' }}>
                    <input type="checkbox" checked={cfg.no_conditions}
                      onChange={e => set('no_conditions', e.target.checked)} />
                    {t('noConditionMode')}
                  </label>
                </div>

                {!cfg.no_conditions && (
                  <div className="space-y-2">
                    {cfg.conditions.map((c, i) => (
                      <div key={i} className="flex gap-1 items-center flex-wrap">
                        <select className="input flex-1" style={{ minWidth: 80 }} value={c.indicator}
                          onChange={e => setCondition(i, 'indicator', e.target.value)}>
                          {INDICATOR_GROUPS.map(g => (
                            <optgroup key={g.label} label={g.label}>
                              {g.items.map(ind => <option key={ind}>{ind}</option>)}
                            </optgroup>
                          ))}
                        </select>
                        <input className="input" style={{ width: 52 }} type="number" value={c.period}
                          onChange={e => setCondition(i, 'period', Number(e.target.value))} />
                        <select className="input" style={{ width: 52 }} value={c.op}
                          onChange={e => setCondition(i, 'op', e.target.value)}>
                          {OPS.map(o => <option key={o}>{o}</option>)}
                        </select>
                        <input className="input" style={{ width: 60 }} type="number" value={c.value}
                          onChange={e => setCondition(i, 'value', Number(e.target.value))} />
                        <button onClick={() => removeCondition(i)}
                          className="text-xs px-2 py-1 rounded"
                          style={{ background: '#3a1a1a', color: '#ef4444' }}>✕</button>
                      </div>
                    ))}
                    <button onClick={addCondition} className="btn btn-secondary w-full text-sm">
                      {t('addCondition')}
                    </button>
                  </div>
                )}
              </div>

              <button onClick={runBacktest} disabled={running}
                className="btn btn-primary w-full">
                {running ? `⏳ ${t('backtestRunning')}` : t('backtestRun')}
              </button>
            </div>
          </div>

          {/* ── Results Panel ── */}
          <div className="lg:col-span-2 space-y-4">
            {!result ? (
              <div className="card flex items-center justify-center text-center"
                style={{ minHeight: 300, color: 'var(--text-muted)' }}>
                <div>
                  <div className="text-4xl mb-3">📊</div>
                  <p>{t('backtestNoResults')}</p>
                </div>
              </div>
            ) : (
              <>
                {/* Stats grid */}
                <div className="card space-y-3">
                  <div className="flex items-center justify-between flex-wrap gap-2">
                    <h2 className="font-bold">
                      {result.symbol} · {result.timeframe} · {result.days}d
                    </h2>
                    <span className="text-xs px-2 py-1 rounded" style={{ background: 'var(--bg)', color: 'var(--text-muted)' }}>
                      {result.candles_analyzed} {t('backtestCandles')}
                    </span>
                  </div>

                  <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
                    <StatCard label={t('totalPnl')}
                      value={`${result.total_pnl >= 0 ? '+' : ''}${result.total_pnl} USDT`}
                      color={pnlColor} />
                    <StatCard label={t('winRate')} value={`${result.win_rate}%`}
                      color={result.win_rate >= 50 ? '#22c55e' : '#f59e0b'} />
                    <StatCard label={t('totalTrades')} value={result.total_trades} />
                    <StatCard label="✅ Wins" value={result.wins} color="#22c55e" />
                    <StatCard label="❌ Losses" value={result.losses} color="#ef4444" />
                    <StatCard label={t('maxDrawdown')}
                      value={`-${result.max_drawdown} USDT`} color="#f59e0b" />
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <div className="p-2 rounded text-sm text-center" style={{ background: 'var(--bg)' }}>
                      <span style={{ color: 'var(--text-muted)' }}>Best trade: </span>
                      <span style={{ color: '#22c55e', fontWeight: 600 }}>
                        +{result.best_trade_pnl} USDT
                      </span>
                    </div>
                    <div className="p-2 rounded text-sm text-center" style={{ background: 'var(--bg)' }}>
                      <span style={{ color: 'var(--text-muted)' }}>Worst trade: </span>
                      <span style={{ color: '#ef4444', fontWeight: 600 }}>
                        {result.worst_trade_pnl} USDT
                      </span>
                    </div>
                  </div>
                </div>

                {/* Equity curve */}
                {result.equity_curve.length >= 2 && (
                  <div className="card">
                    <h2 className="font-bold mb-3">📈 {t('pnlChart')}</h2>
                    <ResponsiveContainer width="100%" height={200}>
                      <AreaChart data={result.equity_curve}
                        margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                        <defs>
                          <linearGradient id="btGrad" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor={pnlColor} stopOpacity={0.3} />
                            <stop offset="95%" stopColor={pnlColor} stopOpacity={0} />
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                        <XAxis dataKey="date" tick={{ fontSize: 9, fill: 'var(--text-muted)' }}
                          tickLine={false} interval="preserveStartEnd" />
                        <YAxis tick={{ fontSize: 10, fill: 'var(--text-muted)' }} tickLine={false}
                          axisLine={false} width={55}
                          tickFormatter={v => `${v >= 0 ? '+' : ''}${v}`} />
                        <ReferenceLine y={0} stroke="var(--border)" strokeDasharray="4 2" />
                        <Tooltip
                          contentStyle={{
                            background: 'var(--panel)', border: '1px solid var(--border)',
                            borderRadius: 8, fontSize: 12,
                          }}
                          formatter={(v: any, n: string) => [
                            `${v >= 0 ? '+' : ''}${v} USDT`, 'Cumulative PnL'
                          ]}
                          labelFormatter={(label, payload) => {
                            const d = payload?.[0]?.payload;
                            return d ? `${d.symbol} [${d.reason}] — ${label}` : label;
                          }}
                        />
                        <Area type="monotone" dataKey="pnl"
                          stroke={pnlColor} strokeWidth={2}
                          fill="url(#btGrad)" dot={false} />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                )}

                {/* Trade list */}
                {result.total_trades > 0 && (
                  <div className="card">
                    <div className="flex items-center justify-between mb-3">
                      <h2 className="font-bold">{t('backtestTrades')} ({result.total_trades})</h2>
                      <button onClick={() => setShowTrades(!showTrades)}
                        className="btn btn-secondary text-sm">
                        {showTrades ? '▲ Hide' : '▼ Show'}
                      </button>
                    </div>

                    {showTrades && (
                      <div className="overflow-x-auto" style={{ maxHeight: 300, overflowY: 'auto' }}>
                        <table>
                          <thead>
                            <tr>
                              <th>#</th>
                              <th>{t('entry')}</th>
                              <th>TP/SL</th>
                              <th>{t('exitPrice')}</th>
                              <th>PnL</th>
                              <th>Result</th>
                              <th>{t('date')}</th>
                            </tr>
                          </thead>
                          <tbody>
                            {result.trades.map((tr: any, i: number) => (
                              <tr key={i}>
                                <td className="text-xs" style={{ color: 'var(--text-muted)' }}>#{i + 1}</td>
                                <td>{tr.entry_price}</td>
                                <td className="text-xs">
                                  <span style={{ color: '#22c55e' }}>{tr.tp_price}</span>
                                  {' / '}
                                  <span style={{ color: '#ef4444' }}>{tr.sl_price}</span>
                                </td>
                                <td>{tr.exit_price ?? '—'}</td>
                                <td style={{ color: tr.pnl >= 0 ? '#22c55e' : '#ef4444', fontWeight: 600 }}>
                                  {tr.pnl != null ? `${tr.pnl >= 0 ? '+' : ''}${tr.pnl}` : '—'}
                                </td>
                                <td>
                                  <span className="text-xs px-2 py-0.5 rounded-full"
                                    style={{
                                      background: tr.reason === 'TP' ? '#1a3a2a' : '#3a1a1a',
                                      color: tr.reason === 'TP' ? '#22c55e' : '#ef4444',
                                    }}>
                                    {tr.reason ?? 'OPEN'}
                                  </span>
                                </td>
                                <td className="text-xs" style={{ color: 'var(--text-muted)' }}>
                                  {tr.closed_at ?? tr.opened_at}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                )}
              </>
            )}
          </div>

        </div>
      </div>
    </div>
  );
}
