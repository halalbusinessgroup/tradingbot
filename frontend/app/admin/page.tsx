'use client';
import { useEffect, useState } from 'react';
import Nav from '@/components/Nav';
import { api } from '@/lib/api';
import { useI18n } from '@/lib/i18n';
import { useToast } from '@/lib/toast';

type TabType = 'pending' | 'users' | 'financial' | 'stats' | 'logs';

export default function AdminPage() {
  const { t } = useI18n();
  const { show } = useToast();
  const [tab, setTab] = useState<TabType>('pending');
  const [users, setUsers] = useState<any[]>([]);
  const [pending, setPending] = useState<any[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [daily, setDaily] = useState<any[]>([]);
  const [logs, setLogs] = useState<any[]>([]);
  const [userTrades, setUserTrades] = useState<{ [key: number]: any[] }>({});
  const [financial, setFinancial] = useState<any[]>([]);
  const [myId, setMyId] = useState<number | null>(null);

  // Guard: only admin role may access this page
  useEffect(() => {
    const role = localStorage.getItem('role');
    if (role !== 'admin') window.location.href = '/dashboard';
  }, []);

  async function load() {
    try {
      const [u, s, p, me] = await Promise.all([
        api.get('/api/admin/users'),
        api.get('/api/admin/stats'),
        api.get('/api/admin/users/pending'),
        api.get('/api/auth/me'),
      ]);
      setUsers(u.data);
      setStats(s.data);
      setPending(p.data);
      setMyId(me.data.id);
    } catch (e: any) {
      if (e.response?.status === 401 || e.response?.status === 403)
        window.location.href = '/dashboard';
    }
  }

  async function loadDaily() {
    try {
      const { data } = await api.get('/api/admin/stats/daily?days=14');
      setDaily(data);
    } catch {}
  }

  async function loadLogs() {
    try {
      const { data } = await api.get('/api/admin/logs?limit=100');
      setLogs(data);
    } catch {}
  }

  async function loadFinancial() {
    try {
      const { data } = await api.get('/api/admin/users/financial-overview');
      setFinancial(data);
    } catch {}
  }

  useEffect(() => {
    load();
    loadDaily();
    const id = setInterval(load, 8000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (tab === 'logs') loadLogs();
    if (tab === 'financial') loadFinancial();
  }, [tab]);

  async function approve(userId: number, approved: boolean) {
    try {
      await api.post(`/api/admin/users/${userId}/approve`, { approved });
      show(approved ? '✅ Təsdiqləndi' : '❌ Rədd edildi', approved ? 'success' : 'warning');
      load();
    } catch (e: any) { show(e.response?.data?.detail || t('error'), 'error'); }
  }

  async function toggleActive(userId: number) {
    await api.post(`/api/admin/users/${userId}/toggle-active`);
    show('Yeniləndi', 'success');
    load();
  }

  async function toggleTrading(userId: number) {
    await api.post(`/api/admin/users/${userId}/toggle-trading`);
    show('Trading statusu dəyişdirildi', 'success');
    load();
  }

  async function setRole(userId: number, role: string) {
    await api.post(`/api/admin/users/${userId}/set-role`, { role });
    show(`Rol: ${role}`, 'success');
    load();
  }

  async function toggleBot(userId: number) {
    await api.post(`/api/admin/users/${userId}/toggle-bot`);
    load();
  }

  async function loadUserTrades(userId: number) {
    try {
      const { data } = await api.get(`/api/admin/users/${userId}/trades?limit=20`);
      setUserTrades(prev => ({ ...prev, [userId]: data }));
    } catch {}
  }

  // Simple bar chart component
  const maxPnl = daily.length ? Math.max(...daily.map(d => Math.abs(d.pnl)), 0.01) : 1;

  return (
    <div>
      <Nav />
      <div className="max-w-7xl mx-auto p-4 sm:p-6 space-y-5">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <h1 className="text-2xl font-bold">{t('adminPanel')}</h1>
          {stats?.pending_users > 0 && (
            <span className="px-3 py-1 rounded-full text-sm font-bold"
              style={{ background: '#7c2d12', color: '#fbbf24' }}>
              ⏳ {stats.pending_users} {t('pendingApproval')}
            </span>
          )}
        </div>

        {/* Stats */}
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
            <Stat label={t('totalUsers')} value={stats.total_users} />
            <Stat label={t('pendingApproval')} value={stats.pending_users}
              color={stats.pending_users > 0 ? '#f59e0b' : undefined} />
            <Stat label={t('activeBots')} value={stats.active_bots} color="#22c55e" />
            <Stat label={t('totalTrades')} value={stats.total_trades} />
            <Stat label={t('openCount')} value={stats.open_trades} />
            <Stat label={t('platformPnl')} value={`${stats.platform_pnl} USDT`}
              color={stats.platform_pnl >= 0 ? '#22c55e' : '#ef4444'} />
          </div>
        )}

        {/* Daily PnL Chart */}
        {daily.length > 0 && (
          <div className="card">
            <h2 className="font-bold mb-4">{t('dailyStats')} (14 {t('days')})</h2>
            <div className="flex items-end gap-1" style={{ height: 100 }}>
              {daily.map(d => {
                const h = Math.max((Math.abs(d.pnl) / maxPnl) * 90, 2);
                return (
                  <div key={d.date} className="flex-1 flex flex-col items-center gap-1" title={`${d.date}: ${d.pnl > 0 ? '+' : ''}${d.pnl} USDT, ${d.trades} trades`}>
                    <div style={{
                      height: h,
                      width: '100%',
                      background: d.pnl >= 0 ? '#22c55e' : '#ef4444',
                      borderRadius: 3,
                      opacity: 0.85,
                      minHeight: 2,
                    }} />
                    <span className="text-xs" style={{ color: 'var(--text-muted)', fontSize: 9 }}>
                      {d.date.slice(5)}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Tab navigation */}
        <div className="flex gap-2 flex-wrap">
          {(['pending', 'users', 'financial', 'stats', 'logs'] as TabType[]).map(t2 => (
            <button key={t2} onClick={() => setTab(t2)}
              className={`btn text-sm ${tab === t2 ? 'btn-primary' : 'btn-secondary'}`}>
              {t2 === 'pending'   ? `⏳ ${t('pendingApproval')} (${pending.length})` :
               t2 === 'users'     ? `👥 ${t('allUsers')}` :
               t2 === 'financial' ? `💰 ${t('financialOverview')}` :
               t2 === 'stats'     ? `📊 ${t('tradeHistory')}` :
               `📋 ${t('botLogsTitle')}`}
            </button>
          ))}
        </div>

        {/* PENDING APPROVAL */}
        {tab === 'pending' && (
          <div className="card">
            <h2 className="font-bold mb-4">⏳ {t('pendingApproval')}</h2>
            {pending.length === 0 ? (
              <p style={{ color: 'var(--text-muted)' }}>{t('noPendingUsers')}</p>
            ) : (
              <div className="space-y-3">
                {pending.map(u => (
                  <div key={u.id} className="p-4 rounded-lg"
                    style={{ background: 'var(--bg)', border: '1px solid #f59e0b' }}>
                    <div className="flex items-start justify-between flex-wrap gap-3">
                      <div>
                        <div className="font-bold">{u.first_name} {u.last_name}</div>
                        <div className="text-sm" style={{ color: 'var(--text-muted)' }}>{u.email}</div>
                        <div className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
                          📞 {u.phone || '—'} | {new Date(u.created_at).toLocaleString()}
                        </div>
                      </div>
                      <div className="flex gap-2">
                        <button onClick={() => approve(u.id, true)}
                          className="btn btn-primary text-sm">✅ {t('approve')}</button>
                        <button onClick={() => approve(u.id, false)}
                          className="btn btn-danger text-sm">❌ {t('reject')}</button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ALL USERS */}
        {tab === 'users' && (
          <div className="card overflow-x-auto">
            <h2 className="font-bold mb-3">👥 {t('allUsers')} ({users.length})</h2>
            <table>
              <thead><tr>
                <th>ID</th><th>Email</th><th>{t('firstName')}</th>
                <th>{t('status')}</th><th>Rol</th><th>Trade</th>
                <th>Bot</th><th>API</th><th>{t('openTrades')}</th>
                <th>{t('pnl')}</th><th>{t('date')}</th><th></th>
              </tr></thead>
              <tbody>
                {users.map(u => (
                  <>
                    <tr key={u.id}>
                      <td>{u.id}</td>
                      <td className="text-xs">{u.email}</td>
                      <td>{u.first_name} {u.last_name}</td>
                      <td>
                        <span className="text-xs px-2 py-0.5 rounded-full"
                          style={{
                            background: !u.is_approved ? '#7c2d12' : u.is_active ? '#1a3a2a' : '#3a1a1a',
                            color: !u.is_approved ? '#fbbf24' : u.is_active ? '#22c55e' : '#ef4444',
                          }}>
                          {!u.is_approved ? '⏳' : u.is_active ? '✅' : '❌'}
                        </span>
                      </td>
                      <td>
                        {u.id === myId ? (
                          <span className="text-xs px-2 py-1 rounded"
                            style={{ background: 'var(--bg)', color: 'var(--text-muted)', border: '1px solid var(--border)' }}>
                            ⭐ Admin (you)
                          </span>
                        ) : (
                          <select className="input text-xs" style={{ padding: '2px 4px', minWidth: 100 }}
                            value={u.role} onChange={e => setRole(u.id, e.target.value)}>
                            <option value="user">👤 User</option>
                            <option value="moderator">🛡 Moderator</option>
                            <option value="admin">⭐ Admin</option>
                          </select>
                        )}
                      </td>
                      <td>
                        <button onClick={() => toggleTrading(u.id)}
                          className="text-xs px-1 py-0.5 rounded"
                          style={{ background: u.can_trade ? '#1a3a2a' : '#3a1a1a',
                                   color: u.can_trade ? '#22c55e' : '#ef4444', border: 'none', cursor: 'pointer' }}>
                          {u.can_trade ? '✅' : '❌'}
                        </button>
                      </td>
                      <td>
                        <button onClick={() => toggleBot(u.id)}
                          className="text-xs px-1 py-0.5 rounded"
                          style={{ background: u.bot_enabled ? '#1a2a3a' : '#1e1e1e',
                                   color: u.bot_enabled ? '#60a5fa' : '#666', border: 'none', cursor: 'pointer' }}>
                          {u.bot_enabled ? '▶' : '⏸'}
                        </button>
                      </td>
                      <td className="text-xs">
                        {u.has_binance_key ? 'B✅' : 'B—'} {u.has_bybit_key ? 'By✅' : 'By—'}
                      </td>
                      <td>{u.open_trades}/{u.closed_trades}</td>
                      <td className={u.total_pnl >= 0 ? 'text-accent' : 'text-danger'}>
                        {u.total_pnl}
                      </td>
                      <td className="text-xs" style={{ color: 'var(--text-muted)' }}>
                        {new Date(u.created_at).toLocaleDateString()}
                      </td>
                      <td>
                        <div className="flex gap-1">
                          <button onClick={() => toggleActive(u.id)}
                            className="btn btn-secondary text-xs">
                            {u.is_active ? t('block') : t('activate')}
                          </button>
                          {!u.is_approved && (
                            <button onClick={() => approve(u.id, true)}
                              className="btn btn-primary text-xs">✅</button>
                          )}
                          <button onClick={() => {
                            if (userTrades[u.id]) {
                              setUserTrades(prev => { const n = {...prev}; delete n[u.id]; return n; });
                            } else {
                              loadUserTrades(u.id);
                            }
                          }} className="btn btn-secondary text-xs">
                            {userTrades[u.id] ? '▲' : '▼ Trades'}
                          </button>
                        </div>
                      </td>
                    </tr>
                    {userTrades[u.id] && (
                      <tr key={`trades-${u.id}`}>
                        <td colSpan={12} style={{ background: 'var(--bg)', padding: '8px 12px' }}>
                          <div className="text-xs space-y-1">
                            {userTrades[u.id].length === 0 ? (
                              <span style={{ color: 'var(--text-muted)' }}>Trade yoxdur</span>
                            ) : userTrades[u.id].map((tr: any) => (
                              <div key={tr.id} className="flex gap-3">
                                <span className="font-bold">{tr.symbol}</span>
                                <span style={{ color: 'var(--text-muted)' }}>{tr.status}</span>
                                <span style={{ color: (tr.pnl || 0) >= 0 ? '#22c55e' : '#ef4444' }}>
                                  {(tr.pnl || 0) >= 0 ? '+' : ''}{(tr.pnl || 0).toFixed(4)} USDT
                                </span>
                                {tr.paper_trade && <span style={{ color: '#60a5fa' }}>📄 Paper</span>}
                              </div>
                            ))}
                          </div>
                        </td>
                      </tr>
                    )}
                  </>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* FINANCIAL OVERVIEW */}
        {tab === 'financial' && (
          <div className="card">
            <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
              <h2 className="font-bold">💰 {t('financialOverview')}</h2>
              <button onClick={loadFinancial} className="btn btn-secondary text-sm">↻ {t('refresh')}</button>
            </div>
            {financial.length === 0 ? (
              <p style={{ color: 'var(--text-muted)' }}>{t('noData')}</p>
            ) : (
              <>
                {/* Summary row */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
                  {(() => {
                    const totalPnl = financial.reduce((s, u) => s + u.total_pnl, 0);
                    const totalProfit = financial.reduce((s, u) => s + u.total_profit, 0);
                    const totalLoss = financial.reduce((s, u) => s + u.total_loss, 0);
                    const avgWinRate = financial.length ? financial.reduce((s, u) => s + u.win_rate, 0) / financial.length : 0;
                    return (
                      <>
                        <div className="p-3 rounded-lg text-center" style={{ background: 'var(--bg)', border: '1px solid var(--border)' }}>
                          <div className="text-xs" style={{ color: 'var(--text-muted)' }}>{t('totalPnl')}</div>
                          <div className="text-lg font-bold mt-1" style={{ color: totalPnl >= 0 ? '#22c55e' : '#ef4444' }}>
                            {totalPnl >= 0 ? '+' : ''}{totalPnl.toFixed(2)} USDT
                          </div>
                        </div>
                        <div className="p-3 rounded-lg text-center" style={{ background: 'var(--bg)', border: '1px solid var(--border)' }}>
                          <div className="text-xs" style={{ color: 'var(--text-muted)' }}>{t('totalProfit')}</div>
                          <div className="text-lg font-bold mt-1" style={{ color: '#22c55e' }}>+{totalProfit.toFixed(2)} USDT</div>
                        </div>
                        <div className="p-3 rounded-lg text-center" style={{ background: 'var(--bg)', border: '1px solid var(--border)' }}>
                          <div className="text-xs" style={{ color: 'var(--text-muted)' }}>{t('totalLoss')}</div>
                          <div className="text-lg font-bold mt-1" style={{ color: '#ef4444' }}>{totalLoss.toFixed(2)} USDT</div>
                        </div>
                        <div className="p-3 rounded-lg text-center" style={{ background: 'var(--bg)', border: '1px solid var(--border)' }}>
                          <div className="text-xs" style={{ color: 'var(--text-muted)' }}>{t('avgWinRate')}</div>
                          <div className="text-lg font-bold mt-1" style={{ color: '#60a5fa' }}>{avgWinRate.toFixed(1)}%</div>
                        </div>
                      </>
                    );
                  })()}
                </div>

                {/* Per-user table */}
                <div className="overflow-x-auto">
                  <table>
                    <thead>
                      <tr>
                        <th>ID</th>
                        <th>Email</th>
                        <th>{t('pnl')}</th>
                        <th>{t('totalProfit')}</th>
                        <th>{t('totalLoss')}</th>
                        <th>{t('winRate')}</th>
                        <th>W / L</th>
                        <th>{t('openTrades')}</th>
                        <th>{t('openValue')}</th>
                        <th>{t('bestTrade')}</th>
                        <th>{t('worstTrade')}</th>
                        <th>{t('avgPnl')}</th>
                        <th>📄 Paper</th>
                        <th>Bot</th>
                      </tr>
                    </thead>
                    <tbody>
                      {financial.map(u => (
                        <tr key={u.user_id}>
                          <td className="text-xs">{u.user_id}</td>
                          <td className="text-xs" style={{ maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {u.first_name ? `${u.first_name} ${u.last_name}` : u.email}
                          </td>
                          <td style={{ color: u.total_pnl >= 0 ? '#22c55e' : '#ef4444', fontWeight: 600 }}>
                            {u.total_pnl >= 0 ? '+' : ''}{u.total_pnl}
                          </td>
                          <td style={{ color: '#22c55e' }}>+{u.total_profit}</td>
                          <td style={{ color: '#ef4444' }}>{u.total_loss}</td>
                          <td>
                            <div className="flex items-center gap-1">
                              <div style={{ width: 40, height: 6, background: 'var(--border)', borderRadius: 3, overflow: 'hidden' }}>
                                <div style={{ width: `${u.win_rate}%`, height: '100%', background: '#22c55e', borderRadius: 3 }} />
                              </div>
                              <span style={{ fontSize: 11 }}>{u.win_rate}%</span>
                            </div>
                          </td>
                          <td className="text-xs">{u.wins}W / {u.losses}L</td>
                          <td>{u.open_trades}</td>
                          <td className="text-xs">{u.open_value > 0 ? `$${u.open_value}` : '—'}</td>
                          <td style={{ color: '#22c55e', fontSize: 12 }}>{u.best_trade !== null ? `+${u.best_trade}` : '—'}</td>
                          <td style={{ color: '#ef4444', fontSize: 12 }}>{u.worst_trade !== null ? u.worst_trade : '—'}</td>
                          <td style={{ color: u.avg_pnl >= 0 ? '#22c55e' : '#ef4444', fontSize: 12 }}>
                            {u.avg_pnl >= 0 ? '+' : ''}{u.avg_pnl}
                          </td>
                          <td className="text-xs" style={{ color: '#60a5fa' }}>{u.paper_pnl >= 0 ? '+' : ''}{u.paper_pnl}</td>
                          <td>
                            <span style={{
                              fontSize: 11, padding: '2px 6px', borderRadius: 4,
                              background: u.bot_enabled ? '#1a3a2a' : '#1e1e1e',
                              color: u.bot_enabled ? '#22c55e' : '#666',
                            }}>
                              {u.bot_enabled ? '▶ ON' : '⏸ OFF'}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </div>
        )}

        {/* LOGS */}
        {tab === 'logs' && (
          <div className="card">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-bold">{t('botLogsTitle')}</h2>
              <button onClick={loadLogs} className="btn btn-secondary text-sm">↻ {t('refresh')}</button>
            </div>
            <div style={{ maxHeight: 500, overflowY: 'auto', fontFamily: 'monospace', fontSize: '0.75rem' }}>
              {logs.map(l => (
                <div key={l.id} className="flex gap-2 py-1"
                  style={{ borderBottom: '1px solid var(--border)' }}>
                  <span style={{ color: '#888', minWidth: 36 }}>#{l.user_id}</span>
                  <span style={{
                    color: l.level === 'ERROR' ? '#ef4444' : l.level === 'WARN' ? '#f59e0b' : '#22c55e',
                    minWidth: 48, fontWeight: 600,
                  }}>{l.level}</span>
                  <span style={{ color: '#666', minWidth: 75 }}>
                    {l.created_at ? new Date(l.created_at).toLocaleTimeString() : ''}
                  </span>
                  <span style={{ color: 'var(--text)', wordBreak: 'break-all' }}>{l.message}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Stat({ label, value, color }: { label: string; value: any; color?: string }) {
  return (
    <div className="card">
      <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>{label}</div>
      <div className="text-xl font-bold mt-1" style={{ color: color || 'var(--text)' }}>{value}</div>
    </div>
  );
}
