'use client';
import Nav from '@/components/Nav';
import { useI18n } from '@/lib/i18n';

const sections = [
  {
    icon: '⚡',
    titleKey: 'How does the platform work?',
    items: [
      'Register and wait for admin approval.',
      'Add your Binance or Bybit API key in Settings (disable Withdrawals permission on the exchange).',
      'Create a Strategy — choose coins, amount, TP/SL, and entry conditions.',
      'Start the bot from the Dashboard.',
      'The bot checks your strategies every ~30 seconds and places trades when conditions are met.',
    ],
  },
  {
    icon: '📊',
    titleKey: 'Entry Conditions (Indicators)',
    items: [
      'RSI < 30 — buys when market is oversold.',
      'EMA crossover — buys when short EMA crosses long EMA.',
      'MACD — momentum confirmation.',
      'You can combine multiple conditions (ALL must be true).',
      'No Conditions mode — bot buys every cycle (use with caution).',
    ],
  },
  {
    icon: '📡',
    titleKey: 'TradingView Webhook Mode',
    items: [
      'Enable Webhook Mode in your strategy.',
      'Copy the Webhook URL shown in the strategy list.',
      'In TradingView, create an alert and paste the URL.',
      'Alert message must be JSON: {"action":"buy","symbol":"BTCUSDT","amount_usdt":50}',
      'When alert fires → bot places the trade immediately.',
    ],
  },
  {
    icon: '💰',
    titleKey: 'TP / SL — Take Profit & Stop Loss',
    items: [
      '% Mode: TP 3% means close trade when +3% profit. SL 1.5% means close at -1.5% loss.',
      '$ Price Mode: Set exact USDT price for TP and SL (e.g. TP at $105, SL at $92).',
      'Trailing SL: moves stop loss upward as price rises, locking in profit.',
      'Trailing TP: activates once trade reaches activation %, then trails price to lock gains.',
    ],
  },
  {
    icon: '📋',
    titleKey: 'Order Types',
    items: [
      'Market: instant buy at current market price (default, fastest).',
      'Limit: place a buy order at your specified price. Waits until that price is reached.',
      'Stop Market: triggers a market buy when price reaches your stop level.',
      'Stop Limit: triggers a limit buy when price reaches your stop level.',
    ],
  },
  {
    icon: '📉',
    titleKey: 'DCA — Dollar Cost Averaging',
    items: [
      'If price drops X% below your entry price, bot buys more of the same coin.',
      'Averages down your entry price, increasing position size.',
      'Enable in Strategy → Advanced Options.',
    ],
  },
  {
    icon: '🔄',
    titleKey: 'Auto-Convert on Deactivation',
    items: [
      'When enabled, deactivating a strategy will market-sell all open trades to USDT.',
      'Useful when you want to exit all positions instantly.',
      'Enable per-strategy in Advanced Options.',
    ],
  },
  {
    icon: '📄',
    titleKey: 'Paper Trading Mode',
    items: [
      'Simulates trades without real money.',
      'Uses real market prices but no actual orders are placed.',
      'Perfect for testing your strategy before going live.',
    ],
  },
  {
    icon: '📬',
    titleKey: 'Telegram Notifications',
    items: [
      'Link your Telegram account in Settings.',
      'Receive trade opened, closed, and error notifications on Telegram.',
      'Bot: @HalalSpotPy_bot',
    ],
  },
  {
    icon: '🔒',
    titleKey: 'API Key Security',
    items: [
      'Your API keys are encrypted with AES-256 before being stored.',
      'NEVER enable Withdrawal permission on your exchange API key.',
      'The bot only needs: Spot Trading and Read Info permissions.',
    ],
  },
  {
    icon: '🔄',
    titleKey: 'Updating the Bot',
    items: [
      'Developer makes changes and pushes to GitHub.',
      'On VPS: git pull && docker compose up -d --build',
      'No downtime — only the changed service restarts.',
    ],
  },
];

export default function GuidePage() {
  const { t } = useI18n();

  return (
    <div>
      <Nav />
      <div className="max-w-4xl mx-auto p-4 sm:p-6 space-y-6">
        <div className="space-y-1">
          <h1 className="text-2xl font-bold">📖 {t('guideTitle')}</h1>
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
            Everything you need to know about using the TradingBot platform.
          </p>
        </div>

        <div className="space-y-4">
          {sections.map((sec, idx) => (
            <div key={idx} className="card space-y-3">
              <h2 className="font-bold text-base flex items-center gap-2">
                <span>{sec.icon}</span>
                <span>{sec.titleKey}</span>
              </h2>
              <ul className="space-y-2">
                {sec.items.map((item, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm" style={{ color: 'var(--text-muted)' }}>
                    <span style={{ color: 'var(--accent)', minWidth: 16, marginTop: 1 }}>•</span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        {/* Quick reference card */}
        <div className="card">
          <h2 className="font-bold mb-3">⚡ Quick Reference</h2>
          <div className="overflow-x-auto">
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  {['Feature', 'Where', 'Notes'].map(h => (
                    <th key={h} style={{ textAlign: 'left', padding: '8px 12px', color: 'var(--text-muted)', fontWeight: 600 }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {[
                  ['Add API Key', 'Settings → API Keys', 'Disable Withdrawals!'],
                  ['Create Strategy', 'Strategy page', 'Coins, TP/SL, conditions'],
                  ['Start/Stop Bot', 'Dashboard', 'Toggle button'],
                  ['View Trades', 'Trades page', 'History, PnL, filters'],
                  ['Backtest', 'Backtest page', 'Historical simulation'],
                  ['Markets', 'Markets page', 'Live prices & charts'],
                  ['Webhook URL', 'Strategy list', 'Click Copy on strategy'],
                  ['Telegram', 'Settings → Telegram', 'Link bot for alerts'],
                ].map(([feat, where, notes], i) => (
                  <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={{ padding: '8px 12px', fontWeight: 600 }}>{feat}</td>
                    <td style={{ padding: '8px 12px', color: 'var(--accent)' }}>{where}</td>
                    <td style={{ padding: '8px 12px', color: 'var(--text-muted)' }}>{notes}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <p className="text-xs text-center pb-4" style={{ color: 'var(--text-muted)' }}>
          Found something wrong or have a suggestion? Use the{' '}
          <a href="/feedback" style={{ color: 'var(--accent)' }}>Feedback</a> page.
        </p>
      </div>
    </div>
  );
}
