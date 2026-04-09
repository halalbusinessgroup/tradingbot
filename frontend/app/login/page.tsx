'use client';
import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import { useI18n, LANGS } from '@/lib/i18n';
import { useTheme } from '@/lib/theme';

// Map backend error strings → i18n keys
function mapError(detail: string, t: (k: string) => string): string {
  if (!detail) return t('error');
  const d = detail.toLowerCase();
  if (d.includes('şifrə') || d.includes('password') || d.includes('email') ||
      d.includes('credentials') || d.includes('yanlış') || d.includes('неверн') ||
      d.includes('غير صح') || d.includes('yanlış e')) {
    return t('wrongCredentials');
  }
  if (d.includes('bloklan') || d.includes('blocked') || d.includes('заблок') || d.includes('engel') || d.includes('حظر')) {
    return t('accountBlocked');
  }
  if (d.includes('2fa') || d.includes('totp') || d.includes('код 2') || d.includes('2fa kodu')) {
    return t('wrongTotp');
  }
  return detail;
}

export default function LoginPage() {
  const router = useRouter();
  const { t, lang, setLang } = useI18n();
  const { theme, toggle } = useTheme();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [totpCode, setTotpCode] = useState('');
  const [step, setStep] = useState<'login' | '2fa' | 'pending'>('login');
  const [err, setErr] = useState('');
  const [loading, setLoading] = useState(false);
  const [shake, setShake] = useState(false);

  // Check already logged in
  useEffect(() => {
    if (typeof window !== 'undefined' && localStorage.getItem('token')) {
      router.replace('/dashboard');
    }
  }, [router]);

  function triggerShake() {
    setShake(true);
    setTimeout(() => setShake(false), 500);
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr('');
    setLoading(true);
    try {
      const payload: any = { email, password };
      if (step === '2fa') payload.totp_code = totpCode;

      const { data } = await api.post('/api/auth/login', payload);

      if (data.requires_2fa) {
        setStep('2fa');
        setLoading(false);
        return;
      }

      localStorage.setItem('token', data.access_token);
      localStorage.setItem('role', data.role);
      router.push(data.role === 'admin' || data.role === 'moderator' ? '/admin' : '/dashboard');
    } catch (e: any) {
      const detail = e.response?.data?.detail;
      if (!e.response) {
        setErr(t('networkError'));
      } else if (detail === 'pending_approval') {
        setStep('pending');
        setLoading(false);
        return;
      } else {
        setErr(mapError(detail || '', t));
      }
      triggerShake();
    } finally {
      setLoading(false);
    }
  }

  // Auto-submit when 6 digits entered in 2FA
  function handleTotpChange(val: string) {
    const digits = val.replace(/\D/g, '').slice(0, 6);
    setTotpCode(digits);
    if (digits.length === 6) {
      setTimeout(() => {
        document.getElementById('login-submit')?.click();
      }, 100);
    }
  }

  // ── Top bar with lang + theme ──────────────────────────────
  const TopBar = () => (
    <div className="fixed top-4 right-4 flex items-center gap-2 z-50">
      {/* Theme toggle */}
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

      {/* Language selector */}
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

  // ── Pending approval screen ──────────────────────────────
  if (step === 'pending') {
    return (
      <div className="min-h-screen flex items-center justify-center p-4">
        <TopBar />
        <div className="card w-full max-w-md space-y-5 text-center">
          <div className="text-6xl">⏳</div>
          <h1 className="text-xl font-bold">{t('pendingApprovalTitle')}</h1>
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
            {t('pendingApprovalMsg')}
          </p>
          <button className="btn btn-secondary w-full" onClick={() => setStep('login')}>
            ← {t('backToLogin')}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <TopBar />

      <form
        onSubmit={submit}
        className="card w-full max-w-md space-y-5"
        style={shake ? { animation: 'shake 0.4s ease' } : {}}
      >
        {/* Logo / title */}
        <div className="text-center space-y-1">
          <div className="text-3xl">⚡</div>
          <h1 className="text-2xl font-bold">{t('login')}</h1>
        </div>

        {/* Error alert */}
        {err && (
          <div
            className="flex items-start gap-2 rounded-lg px-3 py-2 text-sm"
            style={{ background: 'rgba(239,68,68,0.12)', border: '1px solid rgba(239,68,68,0.35)', color: '#f87171' }}
          >
            <span className="mt-0.5 shrink-0">⚠️</span>
            <span>{err}</span>
          </div>
        )}

        {/* ── Login step ── */}
        {step === 'login' && (
          <>
            <div>
              <label className="label">{t('email')}</label>
              <input
                className="input"
                value={email}
                onChange={e => setEmail(e.target.value)}
                type="email"
                required
                autoComplete="email"
                autoFocus
                placeholder="you@example.com"
              />
            </div>

            <div>
              <label className="label">{t('password')}</label>
              <div className="relative">
                <input
                  className="input pr-16"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  type={showPw ? 'text' : 'password'}
                  required
                  autoComplete="current-password"
                  placeholder="••••••••"
                />
                <button
                  type="button"
                  onClick={() => setShowPw(v => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-xs"
                  style={{ color: 'var(--text-muted)' }}
                  tabIndex={-1}
                >
                  {showPw ? t('hidePassword') : t('showPassword')}
                </button>
              </div>
            </div>
          </>
        )}

        {/* ── 2FA step ── */}
        {step === '2fa' && (
          <div className="space-y-3">
            <div
              className="rounded-lg p-3 text-sm text-center"
              style={{ background: 'rgba(34,197,94,0.08)', border: '1px solid rgba(34,197,94,0.25)' }}
            >
              🔐 {t('enterTotpToLogin')}
            </div>
            <label className="label">{t('twoFactorCode')}</label>
            <input
              className="input text-center text-2xl font-mono tracking-[0.5em]"
              value={totpCode}
              onChange={e => handleTotpChange(e.target.value)}
              placeholder="000000"
              maxLength={6}
              inputMode="numeric"
              autoFocus
              autoComplete="one-time-code"
            />
          </div>
        )}

        {/* Submit */}
        <button
          id="login-submit"
          className="btn btn-primary w-full"
          disabled={loading}
          style={{ fontSize: '1rem', padding: '10px' }}
        >
          {loading
            ? t('loading')
            : step === '2fa'
            ? '→ Verify'
            : t('loginBtn')}
        </button>

        {step === '2fa' && (
          <button
            type="button"
            className="btn btn-secondary w-full text-sm"
            onClick={() => { setStep('login'); setTotpCode(''); setErr(''); }}
          >
            ← {t('backToLogin')}
          </button>
        )}

        {step === 'login' && (
          <div className="space-y-2 text-sm text-center">
            <p>
              <a className="text-accent" href="/forgot-password">{t('forgotPassword')}</a>
            </p>
            <p style={{ color: 'var(--text-muted)' }}>
              {t('noAccount')}{' '}
              <a className="text-accent" href="/register">{t('register')}</a>
            </p>
          </div>
        )}
      </form>

      {/* Shake keyframe */}
      <style>{`
        @keyframes shake {
          0%, 100% { transform: translateX(0); }
          20% { transform: translateX(-8px); }
          40% { transform: translateX(8px); }
          60% { transform: translateX(-5px); }
          80% { transform: translateX(5px); }
        }
      `}</style>
    </div>
  );
}
