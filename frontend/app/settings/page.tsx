'use client';
import { useEffect, useState } from 'react';
import Nav from '@/components/Nav';
import { api } from '@/lib/api';
import { useI18n } from '@/lib/i18n';

function KeySection({ exchange, t }: { exchange: string; t: any }) {
  const [key, setKey] = useState<any>(null);
  const [apiKey, setApiKey] = useState('');
  const [apiSecret, setApiSecret] = useState('');
  const [msg, setMsg] = useState('');

  async function load() {
    const { data } = await api.get('/api/users/exchange-keys');
    setKey(data[exchange] || null);
  }
  useEffect(() => { load(); }, [exchange]);

  async function save() {
    setMsg('');
    try {
      await api.post('/api/users/exchange-key', { exchange, api_key: apiKey, api_secret: apiSecret });
      setApiKey(''); setApiSecret('');
      setMsg('✅ OK'); load();
    } catch (e: any) { setMsg('❌ ' + (e.response?.data?.detail || t('error'))); }
  }

  async function del() {
    if (!confirm(`${exchange} silinsin?`)) return;
    await api.delete(`/api/users/exchange-key/${exchange}`);
    setKey(null);
  }

  const label = exchange === 'binance' ? t('binanceKey') : t('bybitKey');

  return (
    <div className="card space-y-3">
      <h2 className="font-bold">{label}</h2>
      <p className="text-sm" style={{ color: 'var(--text-muted)' }}>{t('withdrawalWarning')}</p>
      {key ? (
        <div className="flex items-center justify-between p-3 rounded" style={{ background: 'var(--bg)' }}>
          <span className="font-mono text-sm">{key.masked_key}</span>
          <button onClick={del} className="btn btn-danger text-sm">{t('deleteKey')}</button>
        </div>
      ) : (
        <>
          <div><label className="label">{t('apiKey')}</label>
            <input className="input" value={apiKey} onChange={e => setApiKey(e.target.value)} /></div>
          <div><label className="label">{t('apiSecret')}</label>
            <input className="input" type="password" value={apiSecret} onChange={e => setApiSecret(e.target.value)} /></div>
          <button onClick={save} className="btn btn-primary">{t('saveKey')}</button>
          {msg && <p className="text-sm">{msg}</p>}
        </>
      )}
    </div>
  );
}

export default function SettingsPage() {
  const { t } = useI18n();
  const [me, setMe] = useState<any>(null);
  const [profile, setProfile] = useState({ first_name: '', last_name: '', phone: '', address: '' });
  const [profileMsg, setProfileMsg] = useState('');
  const [tgLink, setTgLink] = useState<any>(null);
  const [newEmail, setNewEmail] = useState('');
  const [code, setCode] = useState('');
  const [emailStep, setEmailStep] = useState<'input' | 'verify'>('input');
  const [emailMsg, setEmailMsg] = useState('');

  // 2FA state
  const [qrCode, setQrCode] = useState('');
  const [totpSecret, setTotpSecret] = useState('');
  const [totpInput, setTotpInput] = useState('');
  const [twoFaStep, setTwoFaStep] = useState<'idle' | 'setup' | 'verify'>('idle');
  const [twoFaMsg, setTwoFaMsg] = useState('');

  // Watchlist
  const [watchlist, setWatchlist]     = useState<any[]>([]);
  const [wlInput, setWlInput]         = useState('');
  const [wlExchange, setWlExchange]   = useState('binance');
  const [wlLoading, setWlLoading]     = useState(false);
  const [wlMsg, setWlMsg]             = useState('');

  // Telegram groups
  const [tgGroups, setTgGroups]       = useState<any[]>([]);
  const [groupToken, setGroupToken]   = useState<any>(null);
  const [groupsMsg, setGroupsMsg]     = useState('');

  // Telegram config (global channel)
  const [tgConfig, setTgConfig]       = useState<any>(null);
  const [tgChatId, setTgChatId]       = useState('');
  const [tgConfigMsg, setTgConfigMsg] = useState('');
  const [tgTestResult, setTgTestResult] = useState<any>(null);
  const [tgTesting, setTgTesting]     = useState(false);
  const [tgSaving, setTgSaving]       = useState(false);

  // Email notifications
  const [emailNotif, setEmailNotif] = useState(true);
  const [notifMsg, setNotifMsg] = useState('');

  async function load() {
    const { data } = await api.get('/api/auth/me');
    setMe(data);
    setProfile({ first_name: data.first_name || '', last_name: data.last_name || '', phone: data.phone || '', address: data.address || '' });
    setEmailNotif(data.email_notifications ?? true);
  }

  async function loadWatchlist() {
    try { const { data } = await api.get('/api/users/watchlist'); setWatchlist(data); } catch {}
  }

  async function loadTgGroups() {
    try { const { data } = await api.get('/api/users/telegram-groups'); setTgGroups(data); } catch {}
  }

  async function loadTgConfig() {
    try {
      const { data } = await api.get('/api/telegram/config');
      setTgConfig(data);
      setTgChatId(data.signal_chat_id || '');
    } catch {}
  }

  useEffect(() => { load(); loadWatchlist(); loadTgGroups(); loadTgConfig(); }, []);

  async function saveProfile() {
    setProfileMsg('');
    try {
      await api.put('/api/users/profile', profile);
      setProfileMsg(t('profileSaved'));
    } catch { setProfileMsg('❌ ' + t('error')); }
  }

  async function linkTg() {
    const { data } = await api.post('/api/users/telegram-link');
    setTgLink(data);
  }

  async function sendEmailCode() {
    setEmailMsg('');
    try {
      await api.post('/api/users/email-change/request', { new_email: newEmail });
      setEmailMsg(t('codeSent'));
      setEmailStep('verify');
    } catch (e: any) { setEmailMsg('❌ ' + (e.response?.data?.detail || t('error'))); }
  }

  async function confirmEmailCode() {
    try {
      const { data } = await api.post('/api/users/email-change/confirm', { code });
      setEmailMsg('✅ ' + data.new_email);
      setEmailStep('input'); setCode(''); load();
    } catch (e: any) { setEmailMsg('❌ ' + (e.response?.data?.detail || t('error'))); }
  }

  // 2FA: start setup (get QR)
  async function setup2fa() {
    setTwoFaMsg('');
    try {
      const { data } = await api.get('/api/auth/2fa/setup');
      setQrCode(data.qr_code);
      setTotpSecret(data.secret);
      setTwoFaStep('setup');
    } catch (e: any) { setTwoFaMsg('❌ ' + (e.response?.data?.detail || t('error'))); }
  }

  // 2FA: save secret & verify code, then enable
  async function enable2fa() {
    setTwoFaMsg('');
    try {
      await api.post('/api/auth/2fa/save-secret', { secret: totpSecret });
      await api.post('/api/auth/2fa/enable', { code: totpInput });
      setTwoFaMsg(t('twoFactorEnabled'));
      setTwoFaStep('idle');
      setTotpInput('');
      load();
    } catch (e: any) { setTwoFaMsg('❌ ' + (e.response?.data?.detail || t('error'))); }
  }

  // 2FA: disable
  async function disable2fa() {
    setTwoFaMsg('');
    try {
      await api.post('/api/auth/2fa/disable', { code: totpInput });
      setTwoFaMsg(t('twoFactorDisabled'));
      setTotpInput('');
      setTwoFaStep('idle');
      load();
    } catch (e: any) { setTwoFaMsg('❌ ' + (e.response?.data?.detail || t('error'))); }
  }

  // Watchlist actions
  async function addToWatchlist() {
    const sym = wlInput.trim().toUpperCase();
    if (!sym) return;
    setWlLoading(true); setWlMsg('');
    try {
      await api.post('/api/users/watchlist', { symbol: sym, exchange: wlExchange });
      setWlInput(''); setWlMsg('✅ ' + sym + ' əlavə edildi');
      loadWatchlist();
    } catch (e: any) { setWlMsg('❌ ' + (e.response?.data?.detail || 'Xəta')); }
    finally { setWlLoading(false); }
  }

  async function removeFromWatchlist(symbol: string, exchange: string) {
    try {
      await api.delete(`/api/users/watchlist/${symbol}?exchange=${exchange}`);
      loadWatchlist();
    } catch {}
  }

  async function getGroupLinkToken() {
    setGroupsMsg('');
    try {
      const { data } = await api.post('/api/users/telegram-groups/link-token');
      setGroupToken(data);
    } catch (e: any) { setGroupsMsg('❌ ' + (e.response?.data?.detail || 'Xəta')); }
  }

  async function removeGroup(id: number) {
    try { await api.delete(`/api/users/telegram-groups/${id}`); loadTgGroups(); } catch {}
  }

  async function toggleGroup(id: number) {
    try { await api.put(`/api/users/telegram-groups/${id}/toggle`); loadTgGroups(); } catch {}
  }

  // Telegram config
  async function saveTgConfig() {
    setTgConfigMsg(''); setTgSaving(true);
    try {
      await api.post('/api/telegram/config', { signal_chat_id: tgChatId });
      setTgConfigMsg('✅ Saxlanıldı');
      loadTgConfig();
    } catch (e: any) { setTgConfigMsg('❌ ' + (e.response?.data?.detail || 'Xəta')); }
    finally { setTgSaving(false); }
  }

  async function testTelegram() {
    setTgTestResult(null); setTgTesting(true);
    try {
      const { data } = await api.post('/api/telegram/test');
      setTgTestResult(data);
    } catch (e: any) { setTgTestResult({ error: e.response?.data?.detail || 'Xəta' }); }
    finally { setTgTesting(false); }
  }

  // Email notifications toggle
  async function saveNotifications() {
    setNotifMsg('');
    try {
      await api.put('/api/users/profile', { ...profile, email_notifications: emailNotif });
      setNotifMsg('✅ OK');
    } catch { setNotifMsg('❌ ' + t('error')); }
  }

  if (!me) return <div className="p-10">{t('loading')}</div>;

  return (
    <div>
      <Nav />
      <div className="max-w-3xl mx-auto p-6 space-y-6">
        <h1 className="text-2xl font-bold">{t('settingsTitle')}</h1>

        {/* Profile */}
        <div className="card space-y-3">
          <h2 className="font-bold">{t('profileTitle')}</h2>
          <div className="grid grid-cols-2 gap-3">
            <div><label className="label">{t('firstName')}</label>
              <input className="input" value={profile.first_name} onChange={e => setProfile(p => ({ ...p, first_name: e.target.value }))} /></div>
            <div><label className="label">{t('lastName')}</label>
              <input className="input" value={profile.last_name} onChange={e => setProfile(p => ({ ...p, last_name: e.target.value }))} /></div>
          </div>
          <div><label className="label">{t('phone')}</label>
            <input className="input" value={profile.phone} onChange={e => setProfile(p => ({ ...p, phone: e.target.value }))} /></div>
          <div><label className="label">{t('address')}</label>
            <input className="input" value={profile.address} onChange={e => setProfile(p => ({ ...p, address: e.target.value }))} /></div>
          <button onClick={saveProfile} className="btn btn-primary">{t('saveProfile')}</button>
          {profileMsg && <p className="text-sm">{profileMsg}</p>}
        </div>

        {/* Email change */}
        <div className="card space-y-3">
          <h2 className="font-bold">{t('emailChange')}</h2>
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
            {t('email')}: <b>{me.email}</b>
          </p>
          {emailStep === 'input' ? (
            <>
              <div><label className="label">{t('newEmail')}</label>
                <input className="input" type="email" value={newEmail} onChange={e => setNewEmail(e.target.value)} /></div>
              <button onClick={sendEmailCode} className="btn btn-primary">{t('sendCode')}</button>
            </>
          ) : (
            <>
              <div><label className="label">{t('verifyCode')}</label>
                <input className="input" value={code} onChange={e => setCode(e.target.value)} maxLength={6} /></div>
              <div className="flex gap-2">
                <button onClick={confirmEmailCode} className="btn btn-primary">{t('confirmChange')}</button>
                <button onClick={() => setEmailStep('input')} className="btn btn-secondary">{t('cancelEdit')}</button>
              </div>
            </>
          )}
          {emailMsg && <p className="text-sm">{emailMsg}</p>}
        </div>

        {/* 2FA */}
        <div className="card space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="font-bold">{t('twoFactorSetup')}</h2>
            {me.totp_enabled && (
              <span className="text-xs px-2 py-1 rounded-full"
                style={{ background: '#1a3a2a', color: '#22c55e' }}>✅ Active</span>
            )}
          </div>

          {!me.totp_enabled && twoFaStep === 'idle' && (
            <button onClick={setup2fa} className="btn btn-primary">
              🔐 {t('enable2fa')}
            </button>
          )}

          {twoFaStep === 'setup' && qrCode && (
            <div className="space-y-3">
              <p className="text-sm" style={{ color: 'var(--text-muted)' }}>{t('scan2faQr')}</p>
              <div className="flex justify-center">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={`data:image/png;base64,${qrCode}`} alt="QR Code"
                  className="rounded" style={{ width: 200, height: 200 }} />
              </div>
              <div className="p-2 rounded text-xs font-mono text-center break-all"
                style={{ background: 'var(--bg)', color: 'var(--text-muted)' }}>
                {totpSecret}
              </div>
              <div>
                <label className="label">{t('twoFactorVerify')}</label>
                <input className="input text-center text-xl tracking-widest"
                  value={totpInput} onChange={e => setTotpInput(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  placeholder="000000" maxLength={6} />
              </div>
              <div className="flex gap-2">
                <button onClick={enable2fa} className="btn btn-primary flex-1">{t('enable2fa')}</button>
                <button onClick={() => { setTwoFaStep('idle'); setTotpInput(''); }} className="btn btn-secondary">{t('cancelEdit')}</button>
              </div>
            </div>
          )}

          {me.totp_enabled && twoFaStep === 'idle' && (
            <div className="space-y-3">
              <div>
                <label className="label">{t('twoFactorCode')}</label>
                <input className="input text-center text-xl tracking-widest"
                  value={totpInput} onChange={e => setTotpInput(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  placeholder="000000" maxLength={6} />
              </div>
              <button onClick={disable2fa} className="btn btn-danger">{t('disable2fa')}</button>
            </div>
          )}

          {twoFaMsg && <p className="text-sm">{twoFaMsg}</p>}
        </div>

        {/* Email Notifications */}
        <div className="card space-y-3">
          <h2 className="font-bold">{t('emailNotificationsTitle')}</h2>
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>{t('emailNotificationsHint')}</p>
          <label className="flex items-center gap-3 cursor-pointer">
            <div className="relative">
              <input type="checkbox" className="sr-only" checked={emailNotif} onChange={e => setEmailNotif(e.target.checked)} />
              <div style={{
                width: 44, height: 24, borderRadius: 12,
                background: emailNotif ? '#22c55e' : '#3a3a3a',
                transition: 'background 0.2s', position: 'relative',
              }}>
                <div style={{
                  position: 'absolute', top: 2,
                  left: emailNotif ? 22 : 2,
                  width: 20, height: 20, borderRadius: '50%',
                  background: 'white', transition: 'left 0.2s',
                }} />
              </div>
            </div>
            <span className="text-sm">{t('emailNotificationsTitle')}</span>
          </label>
          <button onClick={saveNotifications} className="btn btn-primary">{t('saveNotifications')}</button>
          {notifMsg && <p className="text-sm">{notifMsg}</p>}
        </div>

        {/* ── Watchlist ── */}
        <div className="card space-y-3">
          <h2 className="font-bold">📊 İzlənilən Coinlər (Watchlist)</h2>
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
            Bu siyahıdaki coinlər üçün siqnal gələndə Telegram-a avtomatik mesaj göndərilir.
          </p>

          {/* Current watchlist */}
          {watchlist.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {watchlist.map((w: any) => (
                <div key={w.id} className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-semibold"
                  style={{ background: 'rgba(34,197,94,0.12)', border: '1px solid #22c55e', color: '#22c55e' }}>
                  <span>{w.symbol}</span>
                  <span style={{ fontSize: 10, opacity: 0.7 }}>{w.exchange}</span>
                  <button onClick={() => removeFromWatchlist(w.symbol, w.exchange)}
                    style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer', fontSize: 14, lineHeight: 1 }}>×</button>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Heç bir coin əlavə edilməyib.</p>
          )}

          {/* Add coin */}
          <div className="flex gap-2 flex-wrap">
            <input
              className="input" style={{ maxWidth: 160, fontFamily: 'monospace' }}
              placeholder="BTCUSDT"
              value={wlInput}
              onChange={e => setWlInput(e.target.value.toUpperCase())}
              onKeyDown={e => e.key === 'Enter' && addToWatchlist()}
            />
            <select className="input" style={{ maxWidth: 120 }} value={wlExchange} onChange={e => setWlExchange(e.target.value)}>
              <option value="binance">Binance</option>
              <option value="bybit">Bybit</option>
            </select>
            <button onClick={addToWatchlist} disabled={wlLoading || !wlInput.trim()} className="btn btn-primary">
              {wlLoading ? '⏳' : '+ Əlavə et'}
            </button>
          </div>
          {wlMsg && <p className="text-sm">{wlMsg}</p>}
        </div>

        {/* ── Telegram Groups ── */}
        <div className="card space-y-3">
          <h2 className="font-bold">📢 Telegram Qrupları / Kanalları</h2>
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
            Botu qrupa əlavə edib aşağıdakı tokeni qrupda göndərərək bağlayın.
            Siqnallar həm şəxsi chatə, həm də bağlı qruplara gedəcək.
          </p>

          {/* Existing groups */}
          {tgGroups.length > 0 && (
            <div className="space-y-2">
              {tgGroups.map((g: any) => (
                <div key={g.id} className="flex items-center justify-between p-2.5 rounded-lg"
                  style={{ background: 'var(--bg)', border: '1px solid var(--border)' }}>
                  <div>
                    <span className="font-medium text-sm">{g.title || g.chat_id}</span>
                    <span className="ml-2 text-xs" style={{ color: 'var(--text-muted)' }}>{g.chat_id}</span>
                  </div>
                  <div className="flex gap-2">
                    <button onClick={() => toggleGroup(g.id)}
                      className="text-xs px-2 py-1 rounded"
                      style={{
                        background: g.is_active ? 'rgba(34,197,94,0.12)' : 'var(--bg)',
                        border: g.is_active ? '1px solid #22c55e' : '1px solid var(--border)',
                        color: g.is_active ? '#22c55e' : 'var(--text-muted)', cursor: 'pointer'
                      }}>
                      {g.is_active ? '● Aktiv' : '○ Deaktiv'}
                    </button>
                    <button onClick={() => removeGroup(g.id)}
                      className="btn btn-danger text-xs px-2 py-1">Sil</button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Get link token */}
          <button onClick={getGroupLinkToken} className="btn btn-primary">
            🔗 Yeni qrup bağlama tokeni al
          </button>

          {groupToken && (
            <div className="p-3 rounded-lg space-y-2" style={{ background: 'var(--bg)', border: '1px solid #0088cc' }}>
              <p className="text-sm font-semibold" style={{ color: '#0088cc' }}>📋 Addımlar:</p>
              <ol className="text-sm space-y-1" style={{ color: 'var(--text-muted)' }}>
                <li>1. Botu qrupa/kanala admin kimi əlavə edin</li>
                <li>2. Qrupda bu komandanı göndərin:</li>
              </ol>
              <div className="flex items-center gap-2 p-2 rounded"
                style={{ background: 'var(--panel)', border: '1px solid var(--border)', fontFamily: 'monospace', fontSize: 13 }}>
                <code className="flex-1 break-all">{groupToken.command}</code>
                <button
                  onClick={() => { navigator.clipboard.writeText(groupToken.command); }}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#0088cc', fontSize: 12 }}>
                  📋
                </button>
              </div>
              <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                ⚠️ Token bir dəfə istifadə olunur. Yeni qrup üçün yenidən token alın.
              </p>
            </div>
          )}
          {groupsMsg && <p className="text-sm">{groupsMsg}</p>}
        </div>

        {/* Exchange Keys */}
        <KeySection exchange="binance" t={t} />
        <KeySection exchange="bybit" t={t} />

        {/* ── Telegram Setup ── */}
        <div className="card space-y-4">
          <h2 className="font-bold">📱 Telegram Ayarları</h2>

          {/* Bot status row */}
          {tgConfig && (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {/* Bot token */}
              <div className="p-3 rounded-lg" style={{ background: 'var(--bg)', border: '1px solid var(--border)' }}>
                <div className="text-xs mb-1" style={{ color: 'var(--text-muted)' }}>Bot Token</div>
                {tgConfig.bot_token_set ? (
                  <span className="text-sm font-semibold" style={{ color: '#22c55e' }}>✅ Aktiv {tgConfig.bot_token_masked}</span>
                ) : (
                  <span className="text-sm" style={{ color: '#ef4444' }}>❌ .env-də yoxdur</span>
                )}
              </div>
              {/* Bot link */}
              <div className="p-3 rounded-lg" style={{ background: 'var(--bg)', border: '1px solid var(--border)' }}>
                <div className="text-xs mb-1" style={{ color: 'var(--text-muted)' }}>Bot linki</div>
                {tgConfig.bot_link ? (
                  <a href={tgConfig.bot_link} target="_blank" rel="noreferrer"
                    className="text-sm font-semibold" style={{ color: '#0088cc' }}>
                    @{tgConfig.bot_username} ↗
                  </a>
                ) : (
                  <span className="text-sm" style={{ color: 'var(--text-muted)' }}>Təyin edilməyib</span>
                )}
              </div>
              {/* Personal link */}
              <div className="p-3 rounded-lg" style={{ background: 'var(--bg)', border: '1px solid var(--border)' }}>
                <div className="text-xs mb-1" style={{ color: 'var(--text-muted)' }}>Şəxsi hesab</div>
                {tgConfig.personal_linked ? (
                  <span className="text-sm font-semibold" style={{ color: '#22c55e' }}>✅ Bağlıdır</span>
                ) : (
                  <span className="text-sm" style={{ color: '#f59e0b' }}>⚠️ Bağlanmayıb</span>
                )}
              </div>
            </div>
          )}

          {/* Global channel ID */}
          <div>
            <label className="label">📢 Global Siqnal Kanalı / Qrupu (Chat ID)</label>
            <p className="text-xs mb-2" style={{ color: 'var(--text-muted)' }}>
              Bütün siqnallar bu kanala/qrupa göndəriləcək. Botu kanala admin əlavə et,
              sonra <a href="https://api.telegram.org/bot{tgConfig?.bot_token_masked}/getUpdates" target="_blank" rel="noreferrer" style={{ color: '#0088cc' }}>getUpdates</a> ilə chat ID-ni tap (məs: -1001234567890).
            </p>
            <div className="flex gap-2">
              <input
                className="input flex-1"
                placeholder="-1001234567890"
                value={tgChatId}
                onChange={e => setTgChatId(e.target.value)}
                style={{ fontFamily: 'monospace' }}
              />
              <button onClick={saveTgConfig} disabled={tgSaving} className="btn btn-primary">
                {tgSaving ? '⏳' : '💾 Saxla'}
              </button>
            </div>
            {tgConfigMsg && <p className="text-sm mt-1">{tgConfigMsg}</p>}
          </div>

          {/* Personal Telegram link */}
          <div className="p-3 rounded-lg" style={{ background: 'var(--bg)', border: '1px solid var(--border)' }}>
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-semibold">👤 Şəxsi Telegram</span>
              {me.telegram_chat_id && (
                <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: 'rgba(34,197,94,0.12)', color: '#22c55e', border: '1px solid #22c55e' }}>
                  ✅ Bağlıdır
                </span>
              )}
            </div>
            {me.telegram_chat_id ? (
              <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Chat ID: {me.telegram_chat_id}</p>
            ) : (
              <>
                <p className="text-xs mb-2" style={{ color: 'var(--text-muted)' }}>
                  Şəxsi Telegram-ınıza siqnal almaq üçün aşağıdakı düyməyə basın, verilən linki açın.
                </p>
                <button onClick={linkTg} className="btn btn-primary text-sm">
                  🔗 Telegram-ı bağla
                </button>
                {tgLink && (
                  <div className="mt-2 p-2 rounded" style={{ background: 'var(--panel)', border: '1px solid #0088cc' }}>
                    {tgLink.link
                      ? <a href={tgLink.link} target="_blank" rel="noreferrer" className="text-sm break-all" style={{ color: '#0088cc' }}>{tgLink.link}</a>
                      : <code className="text-xs">/start {tgLink.token}</code>}
                  </div>
                )}
              </>
            )}
          </div>

          {/* Test button */}
          <div>
            <button onClick={testTelegram} disabled={tgTesting} className="btn btn-secondary w-full">
              {tgTesting ? '⏳ Yoxlanılır...' : '🧪 Telegram Testi Göndər'}
            </button>

            {tgTestResult && (
              <div className="mt-3 p-3 rounded-lg space-y-2" style={{ background: 'var(--bg)', border: '1px solid var(--border)', fontSize: 13 }}>
                {tgTestResult.error ? (
                  <p style={{ color: '#ef4444' }}>❌ {tgTestResult.error}</p>
                ) : (
                  <>
                    <div className="flex items-center justify-between">
                      <span style={{ color: 'var(--text-muted)' }}>📢 Global kanal</span>
                      <span style={{ color: tgTestResult.global?.ok ? '#22c55e' : '#ef4444', fontWeight: 600 }}>
                        {tgTestResult.global?.ok ? '✅ OK' : `❌ ${tgTestResult.global?.error || 'Xəta'}`}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span style={{ color: 'var(--text-muted)' }}>👤 Şəxsi chat</span>
                      <span style={{ color: tgTestResult.personal?.ok ? '#22c55e' : '#ef4444', fontWeight: 600 }}>
                        {tgTestResult.personal?.ok ? '✅ OK' : `❌ ${tgTestResult.personal?.error || 'Xəta'}`}
                      </span>
                    </div>
                    {tgTestResult.groups?.length > 0 && tgTestResult.groups.map((g: any, i: number) => (
                      <div key={i} className="flex items-center justify-between">
                        <span style={{ color: 'var(--text-muted)' }}>📢 {g.title}</span>
                        <span style={{ color: g.ok ? '#22c55e' : '#ef4444', fontWeight: 600 }}>
                          {g.ok ? '✅ OK' : `❌ ${g.error}`}
                        </span>
                      </div>
                    ))}
                    <div className="flex items-center justify-between pt-1" style={{ borderTop: '1px solid var(--border)' }}>
                      <span style={{ color: 'var(--text-muted)' }}>Bot token</span>
                      <span style={{ color: tgTestResult.bot_token_set ? '#22c55e' : '#ef4444' }}>
                        {tgTestResult.bot_token_set ? '✅ Aktiv' : '❌ Yoxdur'}
                      </span>
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
