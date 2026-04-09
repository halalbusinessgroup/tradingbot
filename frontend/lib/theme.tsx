'use client';
import { createContext, useContext, useState, useEffect, ReactNode } from 'react';

type Theme = 'dark' | 'light';

const ThemeContext = createContext<{ theme: Theme; toggle: () => void }>({
  theme: 'dark', toggle: () => {},
});

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>('dark');

  useEffect(() => {
    const saved = (localStorage.getItem('theme') as Theme) || 'dark';
    setTheme(saved);
    document.documentElement.classList.toggle('light', saved === 'light');
  }, []);

  const toggle = () => {
    const next: Theme = theme === 'dark' ? 'light' : 'dark';
    setTheme(next);
    localStorage.setItem('theme', next);
    document.documentElement.classList.toggle('light', next === 'light');
  };

  return <ThemeContext.Provider value={{ theme, toggle }}>{children}</ThemeContext.Provider>;
}

export const useTheme = () => useContext(ThemeContext);
