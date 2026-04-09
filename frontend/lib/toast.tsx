'use client';
import { createContext, useContext, useState, useCallback, ReactNode } from 'react';

type ToastType = 'success' | 'error' | 'info' | 'warning';
interface Toast { id: number; message: string; type: ToastType }

const ToastCtx = createContext<{ show: (msg: string, type?: ToastType) => void }>({ show: () => {} });

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  let counter = 0;

  const show = useCallback((message: string, type: ToastType = 'success') => {
    const id = ++counter;
    setToasts(t => [...t, { id, message, type }]);
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 3500);
  }, []);

  const icons = { success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️' };
  const colors = {
    success: '#22c55e', error: '#ef4444', warning: '#f59e0b', info: '#3b82f6',
  };

  return (
    <ToastCtx.Provider value={{ show }}>
      {children}
      <div style={{ position: 'fixed', bottom: 24, right: 24, zIndex: 9999, display: 'flex', flexDirection: 'column', gap: 10 }}>
        {toasts.map(t => (
          <div key={t.id} style={{
            background: 'var(--panel)', border: `1px solid ${colors[t.type]}`,
            borderRadius: 10, padding: '12px 18px', minWidth: 260, maxWidth: 380,
            boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
            animation: 'slideIn 0.25s ease',
            display: 'flex', alignItems: 'center', gap: 10,
          }}>
            <span style={{ fontSize: 18 }}>{icons[t.type]}</span>
            <span style={{ fontSize: '0.9rem' }}>{t.message}</span>
          </div>
        ))}
      </div>
      <style>{`@keyframes slideIn { from { opacity:0; transform:translateY(20px); } to { opacity:1; transform:translateY(0); } }`}</style>
    </ToastCtx.Provider>
  );
}

export const useToast = () => useContext(ToastCtx);
