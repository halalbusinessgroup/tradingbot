'use client';
import { useState } from 'react';
import { api } from '@/lib/api';
import { useI18n } from '@/lib/i18n';

export default function ForgotPasswordPage() {
  const { t } = useI18n();
  const [email, setEmail] = useState('');
  const [msg, setMsg] = useState('');
  const [err, setErr] = useState('');
  const [loading, setLoading] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(''); setMsg('');
    setLoading(true);
    try {
      await api.post('/api/auth/forgot-password', { email });
      setMsg(t('resetSent'));
    } catch (e: any) {
      setErr(e.response?.data?.detail || t('error'));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center">
      <form onSubmit={submit} className="card w-full max-w-md space-y-4">
        <h1 className="text-2xl font-bold">{t('forgotPassword')}</h1>

        {msg && (
          <div className="p-3 rounded text-sm" style={{ background: 'rgba(34,197,94,0.1)', border: '1px solid var(--accent)', color: 'var(--accent)' }}>
            {msg}
          </div>
        )}
        {err && <p style={{ color: 'var(--danger)' }} className="text-sm">{err}</p>}

        {!msg && (
          <>
            <div>
              <label className="label">{t('email')}</label>
              <input className="input" type="email" value={email}
                onChange={(e) => setEmail(e.target.value)} required />
            </div>
            <button className="btn btn-primary w-full" disabled={loading}>
              {loading ? '...' : t('sendResetLink')}
            </button>
          </>
        )}

        <p className="text-sm text-center" style={{ color: 'var(--text-muted)' }}>
          <a className="text-accent" href="/login">{t('backToLogin')}</a>
        </p>
      </form>
    </div>
  );
}
