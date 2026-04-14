'use client';
import Link from 'next/link';
import { useState, useEffect } from 'react';
import { logout } from '@/lib/api';
import { useI18n, LANGS, Lang } from '@/lib/i18n';
import { useTheme } from '@/lib/theme';

const NAV_LINKS = [
  { href: '/dashboard', key: 'dashboard' },
  { href: '/strategy',  key: 'strategy' },
  { href: '/trades',    key: 'trades' },
  { href: '/backtest',  key: 'backtest' },
  { href: '/markets',   key: 'markets' },
  { href: '/ai-analysis', key: 'aiAnalysis' },
  { href: '/guide',       key: 'guide' },
  { href: '/feedback',    key: 'feedback' },
  { href: '/settings',  key: 'settings' },
];

export default function Nav() {
  const { t, lang, setLang } = useI18n();
  const { theme, toggle } = useTheme();
  const [langOpen,    setLangOpen]    = useState(false);
  const [menuOpen,    setMenuOpen]    = useState(false);
  const [role,        setRole]        = useState<string | null>(null);
  const currentLabel = LANGS.find(l => l.code === lang)?.label || 'EN';

  useEffect(() => {
    setRole(localStorage.getItem('role'));
    // close mobile menu on resize to desktop
    const onResize = () => { if (window.innerWidth >= 768) setMenuOpen(false); };
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  const links = role === 'admin'
    ? [...NAV_LINKS, { href: '/admin', key: 'admin' }]
    : NAV_LINKS;

  return (
    <nav style={{ background: 'var(--panel)', borderBottom: '1px solid var(--border)' }}>

      {/* Desktop / top bar */}
      <div className="px-4 py-3 flex items-center gap-4">
        {/* Logo */}
        <span className="font-bold text-accent text-lg mr-2">⚡ TradingBot</span>

        {/* Desktop links */}
        <div className="hidden md:flex items-center gap-4 flex-1">
          {links.map(l => (
            <Link key={l.href} href={l.href} className="hover:text-accent text-sm">{t(l.key)}</Link>
          ))}
        </div>

        {/* Right controls (always visible) */}
        <div className="ml-auto flex items-center gap-2">

          {/* Language */}
          <div className="relative">
            <button onClick={() => { setLangOpen(!langOpen); setMenuOpen(false); }}
              className="btn-secondary text-sm px-3 py-1.5 flex items-center gap-1 font-semibold">
              {currentLabel} <span className="text-xs">▾</span>
            </button>
            {langOpen && (
              <div className="absolute right-0 mt-1 z-50 rounded-lg shadow-lg overflow-hidden"
                style={{ background: 'var(--panel)', border: '1px solid var(--border)', minWidth: 110 }}>
                {LANGS.map(l => (
                  <button key={l.code}
                    onClick={() => { setLang(l.code as Lang); setLangOpen(false); }}
                    className="w-full text-left px-4 py-2 text-sm hover:text-accent font-semibold"
                    style={{ background: lang === l.code ? 'var(--bg)' : 'transparent' }}>
                    {l.label}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Theme */}
          <button onClick={toggle} className="btn-secondary text-lg px-3 py-1.5" title="Toggle theme">
            {theme === 'dark' ? '☀️' : '🌙'}
          </button>

          {/* Logout — desktop only */}
          <button onClick={logout} className="btn-secondary text-sm px-3 py-1.5 hidden md:block">
            {t('logout')}
          </button>

          {/* Hamburger — mobile only */}
          <button onClick={() => { setMenuOpen(!menuOpen); setLangOpen(false); }}
            className="btn-secondary text-sm px-3 py-1.5 md:hidden"
            aria-label="Menu">
            {menuOpen ? '✕' : '☰'}
          </button>
        </div>
      </div>

      {/* Mobile dropdown menu */}
      {menuOpen && (
        <div className="md:hidden px-4 pb-4 space-y-1"
          style={{ borderTop: '1px solid var(--border)' }}>
          {links.map(l => (
            <Link key={l.href} href={l.href}
              onClick={() => setMenuOpen(false)}
              className="block py-2.5 px-2 rounded hover:text-accent text-sm font-medium"
              style={{ borderBottom: '1px solid var(--border)' }}>
              {t(l.key)}
            </Link>
          ))}
          <button onClick={() => { logout(); setMenuOpen(false); }}
            className="w-full text-left py-2.5 px-2 text-sm"
            style={{ color: 'var(--danger)' }}>
            {t('logout')}
          </button>
        </div>
      )}
    </nav>
  );
}
