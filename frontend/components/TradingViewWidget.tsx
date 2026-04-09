'use client';
export default function TradingViewWidget({ symbol = 'BINANCE:BTCUSDT' }: { symbol?: string }) {
  const src = `https://www.tradingview.com/widgetembed/?symbol=${encodeURIComponent(
    symbol
  )}&interval=15&theme=dark&style=1&hide_side_toolbar=0&allow_symbol_change=1`;
  return (
    <iframe
      src={src}
      style={{ width: '100%', height: 500, border: 0 }}
      title="tradingview"
    />
  );
}
