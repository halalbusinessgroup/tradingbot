'use client';
import { useState, useMemo } from 'react';
import { api } from '@/lib/api';
import { useI18n, LANGS } from '@/lib/i18n';
import { useTheme } from '@/lib/theme';

// Email format check
function isValidEmail(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

// Password strength check
function checkPassword(pwd: string) {
  return {
    upper:  /[A-Z]/.test(pwd),
    lower:  /[a-z]/.test(pwd),
    number: /[0-9]/.test(pwd),
    symbol: /[^A-Za-z0-9]/.test(pwd),
    length: pwd.length >= 8,
  };
}

export default function RegisterPage() {
  const { t, lang, setLang } = useI18n();
  const { theme, toggle } = useTheme();
  const [form, setForm] = useState({
    firstName: '', lastName: '', phone: '', address: '', email: '', password: '',
  });
  const [showPwd, setShowPwd]   = useState(false);
  const [err, setErr]           = useState('');
  const [pending, setPending]   = useState(false);
  const [loading, setLoading]   = useState(false);
  const [touched, setTouched]   = useState<Record<string, boolean>>({});

  const set = (k: string, v: string) => setForm(f => ({ ...f, [k]: v }));
  const touch = (k: string) => setTouched(t => ({ ...t, [k]: true }));

  // Derived states
  const emailOk  = isValidEmail(form.email);
  const pwdCheck = useMemo(() => checkPassword(form.password), [form.password]);
  const pwdScore = Object.values(pwdCheck).filter(Boolean).length; // 0-5
  const pwdStrength = pwdScore <= 2 ? 'weak' : pwdScore <= 4 ? 'medium' : 'strong';
  const pwdColor    = pwdStrength === 'strong' ? '#22c55e' : pwdStrength === 'medium' ? '#f59e0b' : '#ef4444';

  const canSubmit = emailOk && pwdCheck.upper && pwdCheck.lower && pwdCheck.number && pwdCheck.symbol && pwdCheck.length;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    setErr('');
    setLoading(true);
    try {
      const { data } = await api.post('/api/auth/register', {
        email: form.email, password: form.password,
        first_name: form.firstName, last_name: form.lastName,
        phone: form.phone, address: form.address,
      });
      if (data.access_token) {
        localStorage.setItem('token', data.access_token);
        localStorage.setItem('role', data.role);
        window.location.href = '/dashboard';
      } else {
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
        style={{ background: 'var(--panel)', border: '1px solid var(--border)', color: 'var(--text-muted)', cursor: 'pointer' }}
        title={theme === 'dark' ? t('lightMode') : t('darkMode')}
      >
        {theme === 'dark' ? '☀️' : '🌙'}
      </button>
      <div className="flex items-center gap-1 px-2 py-1 rounded-lg"
        style={{ background: 'var(--panel)', border: '1px solid var(--border)' }}>
        {LANGS.map(l => (
          <button key={l.code} onClick={() => setLang(l.code)}
            className="px-1.5 py-0.5 rounded text-xs font-bold transition-colors"
            style={{ background: lang === l.code ? 'var(--accent)' : 'transparent', color: lang === l.code ? '#000' : 'var(--text-muted)', cursor: 'pointer', border: 'none' }}>
            {l.label}
          </button>
        ))}
      </div>
    </div>
  );

  if (pending) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <TopBar />
        <div className="card w-full max-w-md space-y-5 text-center">
          <div className="text-6xl">⏳</div>
          <h1 className="text-xl font-bold">{t('pendingApprovalTitle')}</h1>
          <p className="text-sm leading-relaxed" style={{ color: 'var(--text-muted)' }}>{t('pendingApprovalMsg')}</p>
          <div className="p-3 rounded-lg text-sm" style={{ background: '#1e3a5f', border: '1px solid #3b82f6', color: '#93c5fd' }}>
            📧 {form.email}
          </div>
          <a href="/login" className="btn btn-secondary w-full block text-center">{t('backToLogin')}</a>
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

        {/* Email with real-time validation */}
        <div>
          <label className="label">{t('email')} *</label>
          <div className="relative">
            <input
              className="input"
              style={{ paddingRight: 36, borderColor: touched.email ? (emailOk ? 'var(--accent)' : 'var(--danger)') : undefined }}
              value={form.email}
              onChange={e => set('email', e.target.value)}
              onBlur={() => touch('email')}
              type="email"
              required
              autoComplete="email"
            />
            {touched.email && form.email && (
              <span style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', fontSize: 16 }}>
                {emailOk ? '✅' : '❌'}
              </span>
            )}
          </div>
          {touched.email && form.email && !emailOk && (
            <p className="text-xs mt-1" style={{ color: 'var(--danger)' }}>{t('emailInvalid')}</p>
          )}
        </div>

        {/* Password with strength meter */}
        <div>
          <label className="label">{t('password')} *</label>
          <div className="relative">
            <input
              className="input"
              style={{ paddingRight: 60, borderColor: form.password ? pwdColor : undefined }}
              value={form.password}
              onChange={e => { set('password', e.target.value); touch('password'); }}
              type={showPwd ? 'text' : 'password'}
              autoComplete="new-password"
              required
            />
            <button
              type="button"
              onClick={() => setShowPwd(v => !v)}
              style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', fontSize: 12 }}>
              {showPwd ? t('hidePassword') : t('showPassword')}
            </button>
          </div>

          {/* Strength bar */}
          {form.password && (
            <>
              <div className="flex gap-1 mt-2">
                {[1,2,3,4,5].map(i => (
                  <div key={i} className="h-1 flex-1 rounded-full transition-all"
                    style={{ background: i <= pwdScore ? pwdColor : 'var(--border)' }} />
                ))}
              </div>
              <p className="text-xs mt-1 font-semibold" style={{ color: pwdColor }}>
                {pwdStrength === 'strong' ? t('pwdStrong') : pwdStrength === 'medium' ? t('pwdMedium') : t('pwdWeak')}
              </p>
            </>
          )}

          {/* Requirements checklist */}
          {(touched.password || form.password) && (
            <div className="mt-2 p-2 rounded-lg space-y-1" style={{ background: 'var(--bg)', border: '1px solid var(--border)' }}>
              <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>{t('pwdRequirements')}</p>
              {[
                { key: 'length', label: 'Min 8 characters' },
                { key: 'upper',  label: t('pwdUppercase') },
                { key: 'lower',  label: t('pwdLowercase') },
                { key: 'number', label: t('pwdNumber') },
                { key: 'symbol', label: t('pwdSymbol') },
              ].map(({ key, label }) => (
                <div key={key} className="flex items-center gap-2 text-xs">
                  <span style={{ color: (pwdCheck as any)[key] ? '#22c55e' : '#ef4444', fontSize: 14 }}>
                    {(pwdCheck as any)[key] ? '✓' : '✗'}
                  </span>
                  <span style={{ color: (pwdCheck as any)[key] ? '#22c55e' : 'var(--text-muted)' }}>{label}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <button className="btn btn-primary w-full" disabled={loading || !canSubmit}
          style={{ opacity: (!canSubmit && !loading) ? 0.6 : 1 }}>
          {loading ? t('loading') : t('registerBtn')}
        </button>
        <p className="text-sm text-center" style={{ color: 'var(--text-muted)' }}>
          {t('haveAccount')} <a className="text-accent" href="/login">{t('loginBtn')}</a>
        </p>
      </form>
    </div>
  );
}
