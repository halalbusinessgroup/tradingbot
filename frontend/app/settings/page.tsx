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

  // Email notifications
  const [emailNotif, setEmailNotif] = useState(true);
  const [notifMsg, setNotifMsg] = useState('');

  async function load() {
    const { data } = await api.get('/api/auth/me');
    setMe(data);
    setProfile({ first_name: data.first_name || '', last_name: data.last_name || '', phone: data.phone || '', address: data.address || '' });
    setEmailNotif(data.email_notifications ?? true);
  }
  useEffect(() => { load(); }, []);

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

        {/* Exchange Keys */}
        <KeySection exchange="binance" t={t} />
        <KeySection exchange="bybit" t={t} />

        {/* Telegram */}
        <div className="card space-y-3">
          <h2 className="font-bold">{t('telegramTitle')}</h2>
          {me.telegram_chat_id ? (
            <p className="text-accent">{t('telegramLinked')} (chat: {me.telegram_chat_id})</p>
          ) : (
            <>
              <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
                {t('telegramLink')}
              </p>
              <button onClick={linkTg} className="btn btn-primary">{t('telegramLink')}</button>
              {tgLink && (
                <div className="p-3 rounded text-sm break-all" style={{ background: 'var(--bg)' }}>
                  {tgLink.link
                    ? <a href={tgLink.link} target="_blank" className="text-accent">{tgLink.link}</a>
                    : `Token: ${tgLink.token}`}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
