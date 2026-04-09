'use client';
import { useEffect, useState } from 'react';
import Nav from '@/components/Nav';
import { api } from '@/lib/api';
import { useI18n } from '@/lib/i18n';
import { useToast } from '@/lib/toast';

export default function TradesPage() {
  const { t } = useI18n();
  const { show } = useToast();
  const [trades, setTrades] = useState<any[]>([]);
  const [stratStats, setStratStats] = useState<any[]>([]);
  const [filter, setFilter] = useState('');
  const [tab, setTab] = useState<'history' | 'stats'>('history');

  async function load() {
    const url = filter ? `/api/trades?status=${filter}` : '/api/trades';
    const { data } = await api.get(url);
    setTrades(data);
  }

  async function loadStratStats() {
    try {
      const { data } = await api.get('/api/trades/strategy-stats');
      setStratStats(data);
    } catch {}
  }

  useEffect(() => { load(); loadStratStats(); }, [filter]);

  async function exportFile(fmt: 'xlsx' | 'csv') {
    try {
      const resp = await api.get(`/api/trades/export?fmt=${fmt}`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([resp.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `trades.${fmt}`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      show(`✅ trades.${fmt} yükləndi`, 'success');
    } catch {
      show(t('error'), 'error');
    }
  }

  return (
    <div>
      <Nav />
      <div className="max-w-7xl mx-auto p-4 sm:p-6 space-y-4">
        <div className="flex justify-between items-center flex-wrap gap-3">
          <h1 className="text-2xl font-bold">{t('tradeHistory')}</h1>
          <div className="flex gap-2 flex-wrap">
            <button onClick={() => exportFile('xlsx')} className="btn btn-secondary text-sm">
              📊 {t('exportXlsx')}
            </button>
            <button onClick={() => exportFile('csv')} className="btn btn-secondary text-sm">
              📄 CSV
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-2">
          <button onClick={() => setTab('history')}
            className={`btn text-sm ${tab === 'history' ? 'btn-primary' : 'btn-secondary'}`}>
            📋 {t('tradeHistory')}
          </button>
          <button onClick={() => setTab('stats')}
            className={`btn text-sm ${tab === 'stats' ? 'btn-primary' : 'btn-secondary'}`}>
            📈 {t('strategyStats')}
          </button>
        </div>

        {/* Strategy Stats */}
        {tab === 'stats' && (
          <div className="space-y-3">
            {stratStats.length === 0 ? (
              <div className="card"><p style={{ color: 'var(--text-muted)' }}>{t('noStrategies')}</p></div>
            ) : stratStats.map(s => (
              <div key={s.id} className="card">
                <div className="flex items-center justify-between flex-wrap gap-3 mb-3">
                  <div>
                    <div className="font-bold">{s.name}</div>
                    <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
                      {s.exchange?.toUpperCase()} |
                      <span className="ml-1" style={{ color: s.is_active ? '#22c55e' : '#888' }}>
                        {s.is_active ? '● ' + t('active') : '○ ' + t('inactive')}
                      </span>
                    </div>
                  </div>
                  <div className="text-lg font-bold" style={{ color: s.total_pnl >= 0 ? '#22c55e' : '#ef4444' }}>
                    {s.total_pnl >= 0 ? '+' : ''}{s.total_pnl} USDT
                  </div>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
                  <StatBox label={t('totalTrades')} value={s.total_trades} />
                  <StatBox label={t('winRate')} value={`${s.win_rate}%`}
                    color={s.win_rate >= 50 ? '#22c55e' : '#f59e0b'} />
                  <StatBox label="✅ Win" value={s.wins} color="#22c55e" />
                  <StatBox label="❌ Loss" value={s.losses} color="#ef4444" />
                  <StatBox label={t('avgDuration')} value={`${s.avg_duration_h}h`} />
                </div>
                {/* Win rate bar */}
                <div className="mt-3 h-2 rounded-full overflow-hidden" style={{ background: 'var(--bg)' }}>
                  <div style={{
                    width: `${s.win_rate}%`, height: '100%',
                    background: s.win_rate >= 50 ? '#22c55e' : '#f59e0b',
                    borderRadius: 4, transition: 'width 0.3s',
                  }} />
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Trade History */}
        {tab === 'history' && (
          <>
            <select className="input" style={{ maxWidth: 200 }} value={filter}
              onChange={e => setFilter(e.target.value)}>
              <option value="">{t('all')}</option>
              <option value="OPEN">{t('openTrades')}</option>
              <option value="CLOSED_TP">{t('closedTP')}</option>
              <option value="CLOSED_SL">{t('closedSL')}</option>
              <option value="CLOSED_MANUAL">Manual</option>
            </select>
            <div className="card overflow-x-auto">
              <table>
                <thead><tr>
                  <th>ID</th><th>{t('coin')}</th><th>{t('entry')}</th><th>{t('exitPrice')}</th>
                  <th>{t('qty')}</th><th>TP</th><th>SL</th><th>{t('status')}</th>
                  <th>{t('pnl')}</th><th>{t('date')}</th>
                </tr></thead>
                <tbody>
                  {trades.length === 0 ? (
                    <tr><td colSpan={10} className="text-center py-8" style={{ color: 'var(--text-muted)' }}>
                      {t('noOpenTrades')}
                    </td></tr>
                  ) : trades.map(tr => (
                    <tr key={tr.id}>
                      <td>{tr.id}</td>
                      <td className="font-bold">
                        {tr.symbol}
                        {tr.paper_trade && (
                          <span className="ml-1 text-xs px-1 rounded"
                            style={{ background: '#1e3a5f', color: '#60a5fa' }}>📄</span>
                        )}
                      </td>
                      <td>{tr.entry_price?.toFixed(6)}</td>
                      <td>{tr.exit_price?.toFixed(6) || '—'}</td>
                      <td>{tr.qty?.toFixed(4)}</td>
                      <td className="text-accent">{tr.tp_price?.toFixed(4)}</td>
                      <td className="text-danger">{tr.sl_price?.toFixed(4)}</td>
                      <td>
                        <span style={{ fontSize: '0.75rem', padding: '2px 8px', borderRadius: 999,
                          background: tr.status === 'OPEN' ? '#1a3a2a' : tr.status?.includes('TP') ? '#1a3a2a' : '#3a1a1a',
                          color: tr.status === 'OPEN' ? '#22c55e' : tr.status?.includes('TP') ? '#22c55e' : '#ef4444' }}>
                          {tr.status}
                        </span>
                      </td>
                      <td className={tr.pnl >= 0 ? 'text-accent' : 'text-danger'}>
                        {tr.pnl?.toFixed(4)} ({tr.pnl_percent?.toFixed(2)}%)
                      </td>
                      <td style={{ fontSize: '0.75rem' }}>
                        {new Date(tr.opened_at).toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function StatBox({ label, value, color }: { label: string; value: any; color?: string }) {
  return (
    <div className="p-2 rounded text-center" style={{ background: 'var(--bg)' }}>
      <div className="text-xs" style={{ color: 'var(--text-muted)' }}>{label}</div>
      <div className="font-bold" style={{ color: color || 'var(--text)' }}>{value}</div>
    </div>
  );
}
