import './globals.css';
import { I18nProvider } from '@/lib/i18n';
import { ThemeProvider } from '@/lib/theme';
import { ToastProvider } from '@/lib/toast';

export const metadata = { title: 'Trading Bot', description: 'Auto trading panel' };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <ThemeProvider>
          <I18nProvider>
            <ToastProvider>
              {children}
            </ToastProvider>
          </I18nProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
