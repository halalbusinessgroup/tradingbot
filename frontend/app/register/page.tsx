'use client';
import { useState } from 'react';
import { api } from '@/lib/api';
import { useI18n, LANGS } from '@/lib/i18n';
import { useTheme } from '@/lib/theme';

export default function RegisterPage() {
  const { t, lang, setLang } = useI18n();
  const { theme, toggle } = useTheme();
  const [form, setForm] = useState({
    firstName: '', lastName: '', phone: '', address: '', email: '', password: '',
  });
  const [err, setErr] = useState('');
  const [pending, setPending] = useState(false);
  const [loading, setLoading] = useState(false);

  const set = (k: string, v: string) => setForm(f => ({ ...f, [k]: v }));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr('');
    setLoading(true);
    try {
      const { data } = await api.post('/api/auth/register', {
        email: form.email, password: form.password,
        first_name: form.firstName, last_name: form.lastName,
        phone: form.phone, address: form.address,
      });

      // First user: auto-approved and gets a token
      if (data.access_token) {
        localStorage.setItem('token', data.access_token);
        localStorage.setItem('role', data.role);
        window.location.href = '/dashboard';
      } else {
        // Subsequent users: must wait for admin approval
        setPending(true);
      }
    } catch (e: any) {
      setErr(e.response?.data?.detail || t('error'));
    } finally {
      setLoading(false);
    }
  }

  // ── Top bar ──────────────────────────────────────────────
  const TopBar = () => (
    <div className="fixed top-4 right-4 flex items-center gap-2 z-50">
      <button
        onClick={toggle}
        className="px-3 py-1.5 rounded-lg text-xs font-medium"
        style={{
          background: 'var(--panel)',
          border: '1px solid var(--border)',
          color: 'var(--text-muted)',
          cursor: 'pointer',
        }}
        title={theme === 'dark' ? t('lightMode') : t('darkMode')}
      >
        {theme === 'dark' ? '☀️' : '🌙'}
      </button>

      <div className="flex items-center gap-1 px-2 py-1 rounded-lg"
        style={{ background: 'var(--panel)', border: '1px solid var(--border)' }}>
        {LANGS.map(l => (
          <button
            key={l.code}
            onClick={() => setLang(l.code)}
            className="px-1.5 py-0.5 rounded text-xs font-bold transition-colors"
            style={{
              background: lang === l.code ? 'var(--accent)' : 'transparent',
              color: lang === l.code ? '#000' : 'var(--text-muted)',
              cursor: 'pointer',
              border: 'none',
            }}
          >
            {l.label}
          </button>
        ))}
      </div>
    </div>
  );

  // Pending approval screen shown after registration
  if (pending) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <TopBar />
        <div className="card w-full max-w-md space-y-5 text-center">
          <div className="text-6xl">⏳</div>
          <h1 className="text-xl font-bold">{t('pendingApprovalTitle')}</h1>
          <p className="text-sm leading-relaxed" style={{ color: 'var(--text-muted)' }}>
            {t('pendingApprovalMsg')}
          </p>
          <div className="p-3 rounded-lg text-sm"
            style={{ background: '#1e3a5f', border: '1px solid #3b82f6', color: '#93c5fd' }}>
            📧 {form.email}
          </div>
          <a href="/login" className="btn btn-secondary w-full block text-center">
            {t('backToLogin')}
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center py-10">
      <TopBar />
      <form onSubmit={submit} className="card w-full max-w-md space-y-4">
        <div className="text-center space-y-1">
          <div className="text-3xl">⚡</div>
          <h1 className="text-2xl font-bold">{t('register')}</h1>
        </div>
        {err && <p style={{ color: 'var(--danger)' }} className="text-sm">{err}</p>}

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label">{t('firstName')} *</label>
            <input className="input" value={form.firstName} onChange={e => set('firstName', e.target.value)} required />
          </div>
          <div>
            <label className="label">{t('lastName')} *</label>
            <input className="input" value={form.lastName} onChange={e => set('lastName', e.target.value)} required />
          </div>
        </div>

        <div>
          <label className="label">{t('phone')} *</label>
          <input className="input" value={form.phone} onChange={e => set('phone', e.target.value)} required type="tel" />
        </div>

        <div>
          <label className="label">{t('address')} *</label>
          <input className="input" value={form.address} onChange={e => set('address', e.target.value)} required />
        </div>

        <div>
          <label className="label">{t('email')} *</label>
          <input className="input" value={form.email} onChange={e => set('email', e.target.value)}
            type="email" required autoComplete="email" />
        </div>

        <div>
          <label className="label">{t('password')} * (min 8)</label>
          <input className="input" value={form.password} onChange={e => set('password', e.target.value)}
            type="password" minLength={8} required autoComplete="new-password" />
        </div>

        <button className="btn btn-primary w-full" disabled={loading}>
          {loading ? t('loading') : t('registerBtn')}
        </button>
        <p className="text-sm text-center" style={{ color: 'var(--text-muted)' }}>
          {t('haveAccount')} <a className="text-accent" href="/login">{t('loginBtn')}</a>
        </p>
      </form>
    </div>
  );
}
