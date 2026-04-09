'use client';
import { useState, useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { api } from '@/lib/api';
import { useI18n } from '@/lib/i18n';

function ResetPasswordForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { t } = useI18n();
  const [token, setToken] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [msg, setMsg] = useState('');
  const [err, setErr] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const tok = searchParams.get('token');
    if (tok) setToken(tok);
  }, [searchParams]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(''); setMsg('');
    if (newPassword !== confirm) {
      setErr('Passwords do not match');
      return;
    }
    if (newPassword.length < 8) {
      setErr('Password must be at least 8 characters');
      return;
    }
    setLoading(true);
    try {
      await api.post('/api/auth/reset-password', { token, new_password: newPassword });
      setMsg(t('passwordReset'));
      setTimeout(() => router.push('/login'), 2000);
    } catch (e: any) {
      setErr(e.response?.data?.detail || t('error'));
    } finally {
      setLoading(false);
    }
  }

  if (!token) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="card w-full max-w-md text-center">
          <p style={{ color: 'var(--danger)' }}>Invalid or missing reset token.</p>
          <a className="text-accent text-sm mt-2 block" href="/forgot-password">{t('forgotPassword')}</a>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center">
      <form onSubmit={submit} className="card w-full max-w-md space-y-4">
        <h1 className="text-2xl font-bold">{t('resetPassword')}</h1>

        {msg && (
          <div className="p-3 rounded text-sm" style={{ background: 'rgba(34,197,94,0.1)', border: '1px solid var(--accent)', color: 'var(--accent)' }}>
            {msg}
          </div>
        )}
        {err && <p style={{ color: 'var(--danger)' }} className="text-sm">{err}</p>}

        {!msg && (
          <>
            <div>
              <label className="label">{t('newPassword')}</label>
              <input className="input" type="password" value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)} required minLength={8} />
            </div>
            <div>
              <label className="label">{t('confirmPassword')}</label>
              <input className="input" type="password" value={confirm}
                onChange={(e) => setConfirm(e.target.value)} required minLength={8} />
            </div>
            <button className="btn btn-primary w-full" disabled={loading}>
              {loading ? '...' : t('resetPassword')}
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

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center"><p>Loading...</p></div>}>
      <ResetPasswordForm />
    </Suspense>
  );
}
