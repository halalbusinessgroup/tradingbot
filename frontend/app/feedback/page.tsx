'use client';
import { useState } from 'react';
import Nav from '@/components/Nav';
import { api } from '@/lib/api';
import { useI18n } from '@/lib/i18n';
import { useToast } from '@/lib/toast';

export default function FeedbackPage() {
  const { t } = useI18n();
  const { show } = useToast();
  const [type, setType]       = useState<'bug' | 'feature'>('bug');
  const [message, setMessage] = useState('');
  const [sending, setSending] = useState(false);
  const [sent, setSent]       = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (message.trim().length < 10) {
      show('Please write at least 10 characters.', 'error');
      return;
    }
    setSending(true);
    try {
      await api.post('/api/users/feedback', {
        feedback_type: type,
        message: message.trim(),
      });
      setSent(true);
      setMessage('');
      show(t('feedbackSent'), 'success');
    } catch (e: any) {
      show(e.response?.data?.detail || t('error'), 'error');
    } finally {
      setSending(false);
    }
  }

  return (
    <div>
      <Nav />
      <div className="max-w-2xl mx-auto p-4 sm:p-6 space-y-6">
        <div>
          <h1 className="text-2xl font-bold">💬 {t('feedbackTitle')}</h1>
          <p className="text-sm mt-1" style={{ color: 'var(--text-muted)' }}>
            Your message will be sent directly to the admin. We review every submission.
          </p>
        </div>

        {sent ? (
          <div className="card text-center space-y-4 py-8">
            <div className="text-5xl">✅</div>
            <h2 className="text-xl font-bold">{t('feedbackSent')}</h2>
            <p style={{ color: 'var(--text-muted)' }}>We appreciate your input and will review it shortly.</p>
            <button onClick={() => setSent(false)} className="btn btn-secondary">
              Send Another
            </button>
          </div>
        ) : (
          <form onSubmit={submit} className="card space-y-5">

            {/* Type selector */}
            <div>
              <label className="label">{t('feedbackType')}</label>
              <div className="flex gap-3 mt-1">
                <button type="button"
                  onClick={() => setType('bug')}
                  className="flex-1 py-3 rounded-lg font-semibold text-sm flex items-center justify-center gap-2 transition-all"
                  style={{
                    background: type === 'bug' ? 'rgba(239,68,68,0.15)' : 'var(--bg)',
                    border: type === 'bug' ? '2px solid #ef4444' : '1px solid var(--border)',
                    color: type === 'bug' ? '#ef4444' : 'var(--text-muted)',
                    cursor: 'pointer',
                  }}>
                  🐛 {t('bugReport')}
                </button>
                <button type="button"
                  onClick={() => setType('feature')}
                  className="flex-1 py-3 rounded-lg font-semibold text-sm flex items-center justify-center gap-2 transition-all"
                  style={{
                    background: type === 'feature' ? 'rgba(34,197,94,0.15)' : 'var(--bg)',
                    border: type === 'feature' ? '2px solid #22c55e' : '1px solid var(--border)',
                    color: type === 'feature' ? '#22c55e' : 'var(--text-muted)',
                    cursor: 'pointer',
                  }}>
                  💡 {t('featureRequest')}
                </button>
              </div>
            </div>

            {/* Context hint */}
            <div className="p-3 rounded-lg text-xs space-y-1"
              style={{ background: 'var(--bg)', border: '1px solid var(--border)', color: 'var(--text-muted)' }}>
              {type === 'bug' ? (
                <>
                  <p className="font-semibold" style={{ color: '#ef4444' }}>🐛 Bug Report Tips:</p>
                  <p>• What were you doing when the bug occurred?</p>
                  <p>• What did you expect to happen?</p>
                  <p>• What actually happened?</p>
                  <p>• Any error messages you saw?</p>
                </>
              ) : (
                <>
                  <p className="font-semibold" style={{ color: '#22c55e' }}>💡 Feature Request Tips:</p>
                  <p>• What problem would this feature solve?</p>
                  <p>• How would you like it to work?</p>
                  <p>• Any examples from other platforms?</p>
                </>
              )}
            </div>

            {/* Message */}
            <div>
              <label className="label">{t('feedbackMessage')}</label>
              <textarea
                className="input"
                style={{ minHeight: 140, resize: 'vertical' }}
                value={message}
                onChange={e => setMessage(e.target.value)}
                placeholder={t('feedbackPlaceholder')}
                required
                minLength={10}
              />
              <p className="text-xs mt-1" style={{ color: message.length < 10 ? 'var(--danger)' : 'var(--text-muted)' }}>
                {message.length} / min 10 characters
              </p>
            </div>

            <button type="submit" disabled={sending || message.trim().length < 10}
              className="btn btn-primary w-full"
              style={{ opacity: message.trim().length < 10 ? 0.6 : 1 }}>
              {sending ? '...' : `📤 ${t('feedbackSubmit')}`}
            </button>
          </form>
        )}

        {/* Previous suggestions inspiration */}
        <div className="card">
          <h3 className="font-bold mb-3 text-sm">💡 Popular Feature Ideas</h3>
          <div className="space-y-2 text-sm" style={{ color: 'var(--text-muted)' }}>
            {[
              'Mobile push notifications',
              'Multi-exchange portfolio view',
              'Copy trading from other users',
              'Automated backtesting on strategy save',
              'Discord notifications support',
            ].map((idea, i) => (
              <div key={i} className="flex items-center gap-2">
                <span style={{ color: 'var(--accent)' }}>→</span>
                <span>{idea}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
