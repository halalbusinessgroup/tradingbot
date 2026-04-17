'use client';
import { useEffect, useState, useRef } from 'react';
import Nav from '@/components/Nav';
import { api } from '@/lib/api';
import { useI18n } from '@/lib/i18n';
import { useToast } from '@/lib/toast';

// ── Deactivate Confirmation Modal ────────────────────────────────────────────
function DeactivateModal({
  strategyName,
  onSellToUsdt,
  onKeepCoins,
  onCancel,
  loading,
}: {
  strategyName: string;
  onSellToUsdt: () => void;
  onKeepCoins: () => void;
  onCancel: () => void;
  loading: boolean;
}) {
  const { t } = useI18n();
  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 1000,
        background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 16,
      }}
      onClick={e => { if (e.target === e.currentTarget) onCancel(); }}
    >
      <div className="card" style={{ maxWidth: 420, width: '100%' }}>
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-bold text-lg">⏸ {t('deactivateModalTitle')}</h3>
          <button onClick={onCancel} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', fontSize: 20 }}>×</button>
        </div>

        {/* Strategy name badge */}
        <div className="px-3 py-2 rounded-lg mb-4 text-sm font-semibold"
          style={{ background: 'var(--bg)', border: '1px solid var(--border)' }}>
          📊 {strategyName}
        </div>

        {/* Message */}
        <p className="text-sm mb-5" style={{ color: 'var(--text-muted)', lineHeight: 1.6 }}>
          {t('deactivateModalMsg')}
        </p>

        {/* Buttons */}
        <div className="space-y-3">
          {/* Sell to USDT */}
          <button
            onClick={onSellToUsdt}
            disabled={loading}
            className="w-full py-3 rounded-xl font-semibold text-sm flex flex-col items-center gap-1 transition-all"
            style={{
              background: loading ? 'rgba(249,115,22,0.1)' : 'rgba(249,115,22,0.15)',
              border: '2px solid #f97316',
              color: '#f97316',
              cursor: loading ? 'not-allowed' : 'pointer',
            }}>
            <span>{loading ? '⏳ ...' : t('sellToUsdt')}</span>
            <span style={{ fontSize: 11, fontWeight: 400, color: 'rgba(249,115,22,0.7)' }}>
              {t('sellToUsdtHint')}
            </span>
          </button>

          {/* Keep coins */}
          <button
            onClick={onKeepCoins}
            disabled={loading}
            className="w-full py-3 rounded-xl font-semibold text-sm flex flex-col items-center gap-1 transition-all"
            style={{
              background: 'var(--bg)',
              border: '1px solid var(--border)',
              color: 'var(--text)',
              cursor: loading ? 'not-allowed' : 'pointer',
            }}>
            <span>{t('keepCoins')}</span>
            <span style={{ fontSize: 11, fontWeight: 400, color: 'var(--text-muted)' }}>
              {t('keepCoinsHint')}
            </span>
          </button>

          {/* Cancel */}
          <button
            onClick={onCancel}
            disabled={loading}
            style={{ background: 'none', border: 'none', width: '100%', color: 'var(--text-muted)', cursor: 'pointer', fontSize: 13, padding: '8px 0' }}>
            {t('cancelDeactivate')}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Searchable Indicator Dropdown ────────────────────────────────────────────
function IndicatorSearch({
  value,
  onChange,
  groups,
}: {
  value: string;
  onChange: (v: string) => void;
  groups: { label: string; items: string[] }[];
}) {
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
        setQuery('');
      }
    }
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const q = query.trim().toLowerCase();

  // Filter groups
  const filtered = q
    ? groups
        .map(g => ({
          label: g.label,
          items: g.items.filter(ind => ind.toLowerCase().includes(q)),
        }))
        .filter(g => g.items.length > 0)
    : groups;

  const total = filtered.reduce((s, g) => s + g.items.length, 0);

  function select(ind: string) {
    onChange(ind);
    setOpen(false);
    setQuery('');
  }

  return (
    <div ref={ref} style={{ position: 'relative', minWidth: 170 }}>
      {/* Trigger button */}
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="input"
        style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          gap: 4, cursor: 'pointer', fontSize: 12, padding: '6px 8px',
          minWidth: 170, textAlign: 'left',
        }}
      >
        <span style={{ fontWeight: 600, color: 'var(--accent)' }}>{value}</span>
        <span style={{ color: 'var(--text-muted)', fontSize: 10 }}>{open ? '▲' : '▼'}</span>
      </button>

      {/* Dropdown */}
      {open && (
        <div
          style={{
            position: 'absolute', top: '100%', left: 0, zIndex: 9999,
            background: 'var(--card)', border: '1px solid var(--border)',
            borderRadius: 10, boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
            minWidth: 220, maxWidth: 280,
            display: 'flex', flexDirection: 'column',
          }}
        >
          {/* Search input */}
          <div style={{ padding: '8px 10px', borderBottom: '1px solid var(--border)' }}>
            <input
              autoFocus
              type="text"
              className="input"
              style={{ fontSize: 12, padding: '5px 8px', width: '100%' }}
              placeholder="🔍 Search indicator..."
              value={query}
              onChange={e => setQuery(e.target.value)}
              onClick={e => e.stopPropagation()}
            />
          </div>

          {/* Results list */}
          <div style={{ maxHeight: 260, overflowY: 'auto', padding: '4px 0' }}>
            {total === 0 ? (
              <div style={{ padding: '12px 16px', color: 'var(--text-muted)', fontSize: 12, textAlign: 'center' }}>
                No results for "{query}"
              </div>
            ) : (
              filtered.map(g => (
                <div key={g.label}>
                  {/* Category label */}
                  <div style={{
                    padding: '5px 12px 3px',
                    fontSize: 10, fontWeight: 700, letterSpacing: '0.08em',
                    color: 'var(--accent)', textTransform: 'uppercase',
                    borderTop: '1px solid rgba(255,255,255,0.06)',
                  }}>
                    {g.label}
                  </div>
                  {/* Items */}
                  {g.items.map(ind => (
                    <button
                      key={ind}
                      type="button"
                      onClick={() => select(ind)}
                      style={{
                        display: 'block', width: '100%', textAlign: 'left',
                        padding: '5px 16px', fontSize: 12, cursor: 'pointer',
                        background: ind === value ? 'rgba(34,197,94,0.12)' : 'transparent',
                        color: ind === value ? '#22c55e' : 'var(--text)',
                        border: 'none',
                        fontWeight: ind === value ? 700 : 400,
                        transition: 'background 0.1s',
                      }}
                      onMouseEnter={e => { if (ind !== value) (e.target as HTMLElement).style.background = 'rgba(255,255,255,0.06)'; }}
                      onMouseLeave={e => { if (ind !== value) (e.target as HTMLElement).style.background = 'transparent'; }}
                    >
                      {/* Highlight matching text */}
                      {q ? (() => {
                        const idx = ind.toLowerCase().indexOf(q);
                        if (idx === -1) return ind;
                        return (
                          <>
                            {ind.slice(0, idx)}
                            <span style={{ background: 'rgba(250,204,21,0.3)', borderRadius: 2 }}>
                              {ind.slice(idx, idx + q.length)}
                            </span>
                            {ind.slice(idx + q.length)}
                          </>
                        );
                      })() : ind}
                    </button>
                  ))}
                </div>
              ))
            )}
          </div>

          {/* Footer hint */}
          <div style={{
            padding: '5px 12px', borderTop: '1px solid var(--border)',
            fontSize: 10, color: 'var(--text-muted)', textAlign: 'center',
          }}>
            {total} indicator{total !== 1 ? 's' : ''}
            {q ? ` matching "${query}"` : ' total'}
          </div>
        </div>
      )}
    </div>
  );
}

const TIMEFRAMES = ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d', '3d', '1w'];
const ORDER_TYPES = ['market', 'limit', 'stop_market', 'stop_limit'] as const;

const INDICATOR_GROUPS = [
  { label: 'Trend', items: [
    'EMA', 'SMA', 'WMA', 'VWMA', 'HMA', 'DEMA', 'TEMA', 'KAMA',
    'EMA_CROSS_ABOVE', 'EMA_CROSS_BELOW', 'SMA_CROSS_ABOVE', 'SMA_CROSS_BELOW',
    'SUPERTREND_BULLISH', 'SUPERTREND',
    'PARABOLIC_SAR_BULLISH', 'PARABOLIC_SAR',
    'ICHIMOKU_ABOVE_CLOUD', 'ICHIMOKU_BELOW_CLOUD', 'ICHIMOKU_TENKAN', 'ICHIMOKU_KIJUN',
  ]},
  { label: 'Momentum', items: [
    'RSI', 'STOCH_RSI_K', 'STOCH_RSI_D',
    'STOCH_K', 'STOCH_D',
    'MACD', 'MACD_SIGNAL', 'MACD_HISTOGRAM', 'MACD_CROSS_ABOVE', 'MACD_CROSS_BELOW',
    'CCI', 'WILLIAMS_R', 'MOMENTUM', 'ROC',
    'ULTIMATE_OSCILLATOR', 'AWESOME_OSCILLATOR',
  ]},
  { label: 'Volume', items: [
    'OBV', 'VWAP', 'AD_LINE', 'CMF', 'MFI', 'VOLUME_OSCILLATOR', 'VOLUME',
  ]},
  { label: 'Volatility', items: [
    'BB_UPPER', 'BB_LOWER', 'BB_MIDDLE', 'BB_PERCENT', 'BB_WIDTH',
    'PRICE_ABOVE_BB', 'PRICE_BELOW_BB',
    'ATR', 'STD_DEV',
    'KC_UPPER', 'KC_LOWER', 'KC_MIDDLE', 'PRICE_ABOVE_KC', 'PRICE_BELOW_KC',
    'DC_UPPER', 'DC_LOWER', 'DC_MIDDLE',
  ]},
  { label: 'Market Structure', items: [
    'MARKET_STRUCTURE_UPTREND', 'MARKET_STRUCTURE_DOWNTREND',
    'HH', 'HL', 'LH', 'LL',
    'TREND_SHIFT_BULLISH', 'TREND_SHIFT_BEARISH',
  ]},
  { label: 'SMC', items: [
    // Short aliases (most used)
    'BOS', 'MBOS', 'OB', 'CHOCH', 'FVG_50',
    'BULLISH_FVG_50', 'BEARISH_FVG_50',
    'BULLISH_MBOS', 'BEARISH_MBOS',
    // Full directional
    'BULLISH_BOS', 'BEARISH_BOS',
    'BULLISH_CHOCH', 'BEARISH_CHOCH',
    'BULLISH_FVG', 'BEARISH_FVG',
    'BULLISH_OB', 'BEARISH_OB',
    'EQUAL_HIGHS', 'EQUAL_LOWS',
    'EQH', 'EQL',
    'BULLISH_SWEEP', 'BEARISH_SWEEP',
    'IN_PREMIUM', 'IN_DISCOUNT',
  ]},
  { label: 'Liquidity', items: [
    // Buyside / Sellside Liquidity pools
    'BSL', 'SSL',
    'AT_BSL', 'AT_SSL',
    'BSL_SWEEP', 'SSL_SWEEP',
    // Key daily/weekly levels
    'PDH', 'PDL',
    'PWH', 'PWL',
  ]},
  { label: 'Fibonacci', items: [
    'NEAR_FIB_236', 'NEAR_FIB_382', 'NEAR_FIB_500', 'NEAR_FIB_618', 'NEAR_FIB_786',
  ]},
  { label: 'Candlestick', items: [
    'HAMMER', 'INVERTED_HAMMER', 'SHOOTING_STAR', 'DOJI', 'SPINNING_TOP',
    'BULLISH_ENGULFING', 'BEARISH_ENGULFING',
    'BULLISH_HARAMI', 'BEARISH_HARAMI',
    'PIERCING_LINE', 'DARK_CLOUD_COVER',
    'MORNING_STAR', 'EVENING_STAR',
    'THREE_WHITE_SOLDIERS', 'THREE_BLACK_CROWS',
    'BULLISH_MARUBOZU', 'BEARISH_MARUBOZU',
  ]},
  { label: 'Chart Patterns', items: [
    'DOUBLE_TOP', 'DOUBLE_BOTTOM',
  ]},
  { label: 'Breakout', items: [
    'BULLISH_BREAKOUT', 'BEARISH_BREAKOUT',
  ]},
  { label: 'Price', items: ['PRICE'] },
];

// Indicators that use DETECTED op (boolean, no numeric value needed)
const BOOLEAN_INDICATORS = new Set([
  'EMA_CROSS_ABOVE','EMA_CROSS_BELOW','SMA_CROSS_ABOVE','SMA_CROSS_BELOW','WMA_CROSS_ABOVE','WMA_CROSS_BELOW',
  'MACD_CROSS_ABOVE','MACD_CROSS_BELOW',
  'SUPERTREND_BULLISH','PARABOLIC_SAR_BULLISH',
  'ICHIMOKU_ABOVE_CLOUD','ICHIMOKU_BELOW_CLOUD',
  'PRICE_ABOVE_BB','PRICE_BELOW_BB','PRICE_ABOVE_KC','PRICE_BELOW_KC',
  'MARKET_STRUCTURE_UPTREND','MARKET_STRUCTURE_DOWNTREND',
  'HH','HL','LH','LL','TREND_SHIFT_BULLISH','TREND_SHIFT_BEARISH',
  'BOS','MBOS','OB','CHOCH','FVG_50','FVG50',
  'BULLISH_FVG_50','BEARISH_FVG_50','BULLISH_MBOS','BEARISH_MBOS',
  'BULLISH_BOS','BEARISH_BOS','BULLISH_CHOCH','BEARISH_CHOCH',
  'BULLISH_FVG','BEARISH_FVG','BULLISH_OB','BEARISH_OB',
  'EQUAL_HIGHS','EQUAL_LOWS','BULLISH_SWEEP','BEARISH_SWEEP',
  'IN_PREMIUM','IN_DISCOUNT',
  'EQUAL_HIGHS','EQUAL_LOWS','EQH','EQL',
  // Liquidity — all boolean (DETECTED)
  'BSL','SSL','AT_BSL','AT_SSL','BSL_SWEEP','SSL_SWEEP',
  // PDH/PDL/PWH/PWL default to DETECTED (price near level)
  'PDH','PDL','PWH','PWL',
  'NEAR_FIB_236','NEAR_FIB_382','NEAR_FIB_500','NEAR_FIB_618','NEAR_FIB_786',
  'HAMMER','INVERTED_HAMMER','SHOOTING_STAR','DOJI','SPINNING_TOP',
  'BULLISH_ENGULFING','BEARISH_ENGULFING','BULLISH_HARAMI','BEARISH_HARAMI',
  'PIERCING_LINE','DARK_CLOUD_COVER','MORNING_STAR','EVENING_STAR',
  'THREE_WHITE_SOLDIERS','THREE_BLACK_CROWS','BULLISH_MARUBOZU','BEARISH_MARUBOZU',
  'DOUBLE_TOP','DOUBLE_BOTTOM','BULLISH_BREAKOUT','BEARISH_BREAKOUT',
]);

// Indicators that need a 2nd period (period2) — for MA crossovers
const NEEDS_PERIOD2 = new Set([
  'EMA_CROSS_ABOVE','EMA_CROSS_BELOW','SMA_CROSS_ABOVE','SMA_CROSS_BELOW','WMA_CROSS_ABOVE','WMA_CROSS_BELOW',
]);

const defaultForm = () => ({
  name: '',
  symbols: [] as string[],
  amount: 10,
  tp: 3,
  sl: 1.5,
  // TP/SL mode: 'percent' | 'price'
  tpSlMode: 'percent' as 'percent' | 'price',
  tpPrice: '' as string | number,
  slPrice: '' as string | number,
  maxOpen: 2,
  timeframe: '15m',
  exchange: 'binance',
  // Order type: market | limit | stop_market | stop_limit
  orderType: 'market' as string,
  limitPrice: '' as string | number,
  stopTriggerPrice: '' as string | number,
  noConditions: false,
  webhookMode: false,
  conditions: [{ indicator: 'RSI', period: 14, period2: 26, op: '<', value: 30 }],
  // Advanced
  trailingSl: '' as string | number,
  trailingTp: '' as string | number,
  trailingTpActivation: 3 as string | number,
  paperMode: false,
  dcaEnabled: false,
  dcaPercent: 2,
  dcaAmount: 10,
  autoConvert: false,
  isPublic: false,
  publicDescription: '',
});

export default function StrategyPage() {
  const { t } = useI18n();
  const { show } = useToast();
  const [list, setList]       = useState<any[]>([]);
  const [marketplace, setMarketplace] = useState<any[]>([]);
  const [showMarket, setShowMarket] = useState(false);
  const [form, setForm]       = useState(defaultForm());
  const [editId, setEditId]   = useState<number | null>(null);
  const [saving, setSaving]   = useState(false);
  const [coinInput, setCoinInput] = useState('');
  const [validating, setValidating] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const formRef = useRef<HTMLDivElement>(null);

  // Deactivate modal
  const [deactivateTarget, setDeactivateTarget] = useState<any | null>(null);
  const [deactivating, setDeactivating] = useState(false);

  async function load() {
    const { data } = await api.get('/api/strategies');
    setList(data);
  }
  async function loadMarketplace() {
    try { const { data } = await api.get('/api/strategies/marketplace'); setMarketplace(data); } catch {}
  }
  useEffect(() => { load(); }, []);

  function resetForm() { setForm(defaultForm()); setEditId(null); setCoinInput(''); }

  function startEdit(s: any) {
    const cfg = s.config;
    setForm({
      name: s.name,
      symbols: cfg.symbols || [],
      amount: cfg.amount_usdt || 10,
      tp: cfg.tp_percent || 3,
      sl: cfg.sl_percent || 1.5,
      tpSlMode: cfg.tp_sl_mode || 'percent',
      tpPrice: cfg.tp_price || '',
      slPrice: cfg.sl_price || '',
      maxOpen: cfg.max_open_trades || 2,
      timeframe: cfg.timeframe || '15m',
      exchange: cfg.exchange || 'binance',
      orderType: cfg.order_type || 'market',
      limitPrice: cfg.limit_price || '',
      stopTriggerPrice: cfg.stop_trigger_price || '',
      noConditions: !cfg.entry_conditions || cfg.entry_conditions.length === 0,
      webhookMode: !!cfg.webhook_mode,
      conditions: cfg.entry_conditions?.length ? cfg.entry_conditions : [{ indicator: 'RSI', period: 14, period2: 26, op: '<', value: 30 }],
      trailingSl: cfg.trailing_sl || '',
      trailingTp: cfg.trailing_tp || '',
      trailingTpActivation: cfg.trailing_tp_activation || 3,
      paperMode: !!cfg.paper_mode,
      dcaEnabled: !!cfg.dca_enabled,
      dcaPercent: cfg.dca_percent || 2,
      dcaAmount: cfg.dca_amount || 10,
      autoConvert: !!cfg.auto_convert,
      isPublic: s.is_public || false,
      publicDescription: s.public_description || '',
    });
    setEditId(s.id);
    formRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  async function addCoin() {
    const c = coinInput.trim().toUpperCase();
    if (!c) return;
    if (form.symbols.includes(c)) { show(`${c} ${t('alreadyAdded')}`, 'warning'); return; }
    setValidating(true);
    try {
      const { data } = await api.get(`/api/users/validate-symbol?exchange=${form.exchange}&symbol=${c}`);
      if (data.exists) { setForm(f => ({ ...f, symbols: [...f.symbols, c] })); setCoinInput(''); show(`✅ ${c} ${t('coinAdded')}`, 'success'); }
      else show(`❌ ${c} ${t('coinNotFound')}`, 'error');
    } catch { show(t('validationError'), 'error'); }
    finally { setValidating(false); }
  }

  function removeCoin(sym: string) { setForm(f => ({ ...f, symbols: f.symbols.filter(s => s !== sym) })); }

  async function save() {
    if (!form.name) return show(t('strategyNameRequired'), 'error');
    if (!form.symbols.length) return show(t('addAtLeastOneCoin'), 'error');
    setSaving(true);
    try {
      const payload = {
        name: form.name,
        is_active: true,
        is_public: form.isPublic,
        public_description: form.publicDescription || null,
        config: {
          symbols: form.symbols,
          amount_usdt: form.amount,
          tp_percent: form.tpSlMode === 'percent' ? form.tp : null,
          sl_percent: form.tpSlMode === 'percent' ? form.sl : null,
          tp_sl_mode: form.tpSlMode,
          tp_price: form.tpSlMode === 'price' ? +form.tpPrice : null,
          sl_price: form.tpSlMode === 'price' ? +form.slPrice : null,
          max_open_trades: form.maxOpen,
          timeframe: form.timeframe,
          exchange: form.exchange,
          order_type: form.orderType,
          limit_price: form.orderType !== 'market' ? +form.limitPrice : null,
          stop_trigger_price: (form.orderType === 'stop_market' || form.orderType === 'stop_limit') ? +form.stopTriggerPrice : null,
          entry_conditions: (form.noConditions || form.webhookMode) ? [] : form.conditions,
          no_conditions: form.noConditions,
          webhook_mode: form.webhookMode,
          trailing_sl: form.trailingSl ? +form.trailingSl : null,
          trailing_tp: form.trailingTp ? +form.trailingTp : null,
          trailing_tp_activation: form.trailingTp ? +form.trailingTpActivation : null,
          paper_mode: form.paperMode,
          dca_enabled: form.dcaEnabled,
          dca_percent: form.dcaPercent,
          dca_amount: form.dcaAmount,
          auto_convert: form.autoConvert,
        },
      };
      if (editId !== null) {
        await api.put(`/api/strategies/${editId}`, payload);
        show(`✅ ${t('strategyUpdated')}`, 'success');
      } else {
        await api.post('/api/strategies', payload);
        show(`✅ ${t('strategySaved')}`, 'success');
      }
      resetForm(); load();
    } catch (e: any) { show(e.response?.data?.detail || t('error'), 'error'); }
    finally { setSaving(false); }
  }

  async function toggleActive(s: any) {
    if (s.is_active) {
      // Deactivating → show modal to ask sell/keep
      setDeactivateTarget(s);
      return;
    }
    // Activating → just toggle
    await api.put(`/api/strategies/${s.id}`, { name: s.name, is_active: true, config: s.config });
    load();
  }

  async function handleDeactivateSell() {
    if (!deactivateTarget) return;
    setDeactivating(true);
    try {
      await api.post(`/api/strategies/${deactivateTarget.id}/deactivate`);
      show(`✅ ${t('sellToUsdt')} — ${t('strategyUpdated')}`, 'success');
      setDeactivateTarget(null);
      load();
    } catch (e: any) {
      show(e.response?.data?.detail || t('error'), 'error');
    } finally {
      setDeactivating(false);
    }
  }

  async function handleDeactivateKeep() {
    if (!deactivateTarget) return;
    setDeactivating(true);
    try {
      await api.put(`/api/strategies/${deactivateTarget.id}`, {
        name: deactivateTarget.name,
        is_active: false,
        config: deactivateTarget.config,
      });
      show(`⏸ ${t('strategyUpdated')}`, 'success');
      setDeactivateTarget(null);
      load();
    } catch (e: any) {
      show(e.response?.data?.detail || t('error'), 'error');
    } finally {
      setDeactivating(false);
    }
  }

  async function del(id: number) {
    if (!confirm(t('delete') + '?')) return;
    await api.delete(`/api/strategies/${id}`);
    load();
  }

  function updateCondition(i: number, field: string, val: any) {
    const next = [...form.conditions];
    const numFields = ['period', 'period2', 'value'];
    next[i] = { ...next[i], [field]: numFields.includes(field) ? +val : val };
    // Auto-set op to DETECTED when switching to a boolean indicator
    if (field === 'indicator' && BOOLEAN_INDICATORS.has(val)) {
      next[i] = { ...next[i], op: 'DETECTED' };
    }
    // Reset op to '<' when switching from boolean to numeric
    if (field === 'indicator' && !BOOLEAN_INDICATORS.has(val) && next[i].op === 'DETECTED') {
      next[i] = { ...next[i], op: '<' };
    }
    setForm(f => ({ ...f, conditions: next }));
  }

  const orderTypeLabel = (k: string) => {
    const map: any = { market: t('orderTypeMarket'), limit: t('orderTypeLimit'), stop_market: t('orderTypeStopMarket'), stop_limit: t('orderTypeStopLimit') };
    return map[k] || k;
  };

  return (
    <div>
      <Nav />

      {/* Deactivate confirmation modal */}
      {deactivateTarget && (
        <DeactivateModal
          strategyName={deactivateTarget.name}
          onSellToUsdt={handleDeactivateSell}
          onKeepCoins={handleDeactivateKeep}
          onCancel={() => setDeactivateTarget(null)}
          loading={deactivating}
        />
      )}

      <div className="max-w-5xl mx-auto p-4 sm:p-6 space-y-6">
        <h1 className="text-2xl font-bold">{t('strategyMgmt')}</h1>

        {/* ── Form ── */}
        <div ref={formRef} className="card space-y-5">
          <h2 className="font-bold text-lg">{editId !== null ? t('editStrategy') : t('newStrategy')}</h2>

          {/* Name */}
          <div>
            <label className="label">{t('strategyName')}</label>
            <input className="input" value={form.name}
              onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="SOL RSI Strategy" />
          </div>

          {/* Exchange + Timeframe */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">{t('exchange')}</label>
              <select className="input" value={form.exchange}
                onChange={e => setForm(f => ({ ...f, exchange: e.target.value, symbols: [] }))}>
                <option value="binance">Binance</option>
                <option value="bybit">Bybit</option>
              </select>
            </div>
            <div>
              <label className="label">{t('timeframe')}</label>
              <select className="input" value={form.timeframe}
                onChange={e => setForm(f => ({ ...f, timeframe: e.target.value }))}>
                {TIMEFRAMES.map(tf => <option key={tf}>{tf}</option>)}
              </select>
            </div>
          </div>

          {/* Order Type */}
          <div>
            <label className="label">{t('orderType')}</label>
            <div className="flex flex-wrap gap-2">
              {ORDER_TYPES.map(ot => (
                <button key={ot} type="button"
                  onClick={() => setForm(f => ({ ...f, orderType: ot }))}
                  className="px-3 py-1.5 rounded-lg text-sm font-medium transition-all"
                  style={{
                    background: form.orderType === ot ? 'var(--accent)' : 'var(--bg)',
                    color: form.orderType === ot ? '#000' : 'var(--text-muted)',
                    border: form.orderType === ot ? '1px solid var(--accent)' : '1px solid var(--border)',
                    cursor: 'pointer',
                  }}>
                  {orderTypeLabel(ot)}
                </button>
              ))}
            </div>
            <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>{t('orderTypeHint')}</p>
            {/* Extra inputs for limit/stop orders */}
            {(form.orderType === 'limit' || form.orderType === 'stop_limit') && (
              <div className="mt-2 flex gap-3 flex-wrap">
                <div>
                  <label className="label">{t('limitPrice')}</label>
                  <input className="input" type="number" step="any" min="0" style={{ maxWidth: 160 }}
                    value={form.limitPrice}
                    onChange={e => setForm(f => ({ ...f, limitPrice: e.target.value }))}
                    placeholder="e.g. 95.50" />
                </div>
                {form.orderType === 'stop_limit' && (
                  <div>
                    <label className="label">{t('stopTriggerPrice')}</label>
                    <input className="input" type="number" step="any" min="0" style={{ maxWidth: 160 }}
                      value={form.stopTriggerPrice}
                      onChange={e => setForm(f => ({ ...f, stopTriggerPrice: e.target.value }))}
                      placeholder="e.g. 94.00" />
                  </div>
                )}
              </div>
            )}
            {form.orderType === 'stop_market' && (
              <div className="mt-2">
                <label className="label">{t('stopTriggerPrice')}</label>
                <input className="input" type="number" step="any" min="0" style={{ maxWidth: 160 }}
                  value={form.stopTriggerPrice}
                  onChange={e => setForm(f => ({ ...f, stopTriggerPrice: e.target.value }))}
                  placeholder="e.g. 94.00" />
              </div>
            )}
          </div>

          {/* Amount + TP/SL mode selector */}
          <div>
            <div className="flex items-center justify-between mb-2 flex-wrap gap-2">
              <label className="label mb-0">{t('amount')} / TP / SL</label>
              {/* TP/SL mode toggle */}
              <div className="flex items-center gap-1 rounded-lg p-1" style={{ background: 'var(--bg)', border: '1px solid var(--border)' }}>
                <button type="button" onClick={() => setForm(f => ({ ...f, tpSlMode: 'percent' }))}
                  className="px-3 py-1 rounded text-xs font-semibold transition-all"
                  style={{ background: form.tpSlMode === 'percent' ? 'var(--accent)' : 'transparent', color: form.tpSlMode === 'percent' ? '#000' : 'var(--text-muted)', border: 'none', cursor: 'pointer' }}>
                  {t('tpSlPercent')}
                </button>
                <button type="button" onClick={() => setForm(f => ({ ...f, tpSlMode: 'price' }))}
                  className="px-3 py-1 rounded text-xs font-semibold transition-all"
                  style={{ background: form.tpSlMode === 'price' ? 'var(--accent)' : 'transparent', color: form.tpSlMode === 'price' ? '#000' : 'var(--text-muted)', border: 'none', cursor: 'pointer' }}>
                  {t('tpSlPrice')}
                </button>
              </div>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div>
                <label className="label">{t('amount')}</label>
                <input className="input" type="number" min="1" value={form.amount}
                  onChange={e => setForm(f => ({ ...f, amount: +e.target.value }))} />
              </div>
              {form.tpSlMode === 'percent' ? (
                <>
                  <div>
                    <label className="label">{t('tp')} %</label>
                    <input className="input" type="number" min="0.1" step="0.1" value={form.tp}
                      onChange={e => setForm(f => ({ ...f, tp: +e.target.value }))} />
                  </div>
                  <div>
                    <label className="label">{t('sl')} %</label>
                    <input className="input" type="number" min="0.1" step="0.1" value={form.sl}
                      onChange={e => setForm(f => ({ ...f, sl: +e.target.value }))} />
                  </div>
                </>
              ) : (
                <>
                  <div>
                    <label className="label">{t('tpPriceLabel')}</label>
                    <input className="input" type="number" step="any" min="0" value={form.tpPrice}
                      onChange={e => setForm(f => ({ ...f, tpPrice: e.target.value }))}
                      placeholder="e.g. 105.00" />
                  </div>
                  <div>
                    <label className="label">{t('slPriceLabel')}</label>
                    <input className="input" type="number" step="any" min="0" value={form.slPrice}
                      onChange={e => setForm(f => ({ ...f, slPrice: e.target.value }))}
                      placeholder="e.g. 88.00" />
                  </div>
                </>
              )}
              <div>
                <label className="label">{t('maxOpenTrades')}</label>
                <input className="input" type="number" min="1" value={form.maxOpen}
                  onChange={e => setForm(f => ({ ...f, maxOpen: +e.target.value }))} />
              </div>
            </div>
            {form.tpSlMode === 'price' && (
              <p className="text-xs mt-1" style={{ color: '#f59e0b' }}>⚠️ {t('tpSlModeHint')}</p>
            )}
          </div>

          {/* ── Coins ── */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="label mb-0">{t('coins')}</label>
              {form.symbols.length > 0 && (
                <button type="button" onClick={() => setForm(f => ({ ...f, symbols: [] }))}
                  className="text-xs px-2 py-1 rounded"
                  style={{ color: 'var(--danger)', border: '1px solid var(--danger)', background: 'transparent' }}>
                  {t('clearAll')}
                </button>
              )}
            </div>
            {form.symbols.length > 0 ? (
              <div className="flex flex-wrap gap-2 mb-3">
                {form.symbols.map(sym => (
                  <div key={sym} className="flex items-center gap-1 px-3 py-1 rounded-full text-sm font-semibold"
                    style={{ background: 'var(--accent)', color: '#000' }}>
                    {sym}
                    <button type="button" onClick={() => removeCoin(sym)}
                      className="ml-1 font-bold hover:opacity-70"
                      style={{ lineHeight: 1, background: 'none', border: 'none', color: '#000', cursor: 'pointer' }}>
                      ×
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm mb-3" style={{ color: 'var(--text-muted)' }}>{t('noCoins')}</p>
            )}
            <div className="flex gap-2">
              <input className="input" style={{ maxWidth: 200 }} value={coinInput}
                onChange={e => setCoinInput(e.target.value.toUpperCase())}
                onKeyDown={e => e.key === 'Enter' && addCoin()}
                placeholder={t('customCoin')} />
              <button type="button" onClick={addCoin} disabled={validating} className="btn btn-secondary text-sm whitespace-nowrap">
                {validating ? '⏳' : `+ ${t('addCoin')}`}
              </button>
            </div>
            <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>{t('coinHint')}</p>
          </div>

          {/* ── Entry Conditions ── */}
          <div>
            <div className="flex flex-wrap items-center gap-3 mb-3">
              <label className="label mb-0">{t('entryConditions')}</label>
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input type="checkbox" checked={form.webhookMode}
                  onChange={e => setForm(f => ({ ...f, webhookMode: e.target.checked, noConditions: false }))} />
                <span style={{ color: form.webhookMode ? '#a78bfa' : 'var(--text-muted)' }}>
                  📡 {t('webhookMode')}
                </span>
              </label>
              {!form.webhookMode && (
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <input type="checkbox" checked={form.noConditions}
                    onChange={e => setForm(f => ({ ...f, noConditions: e.target.checked }))} />
                  <span style={{ color: form.noConditions ? 'var(--accent)' : 'var(--text-muted)' }}>
                    {t('noConditionMode')}
                  </span>
                </label>
              )}
            </div>
            {form.webhookMode ? (
              <div className="p-4 rounded-lg space-y-2" style={{ background: 'rgba(167,139,250,0.08)', border: '1px solid rgba(167,139,250,0.4)' }}>
                <p className="text-sm font-semibold" style={{ color: '#a78bfa' }}>📡 {t('webhookMode')}</p>
                <p className="text-xs" style={{ color: 'var(--text-muted)' }}>{t('webhookModeHint')}</p>
              </div>
            ) : form.noConditions ? (
              <div className="p-3 rounded-lg text-sm" style={{ background: 'var(--bg)', border: '1px solid var(--accent)', color: 'var(--accent)' }}>
                {t('noConditionWarning')}
              </div>
            ) : (
              <>
                {form.conditions.map((c, i) => {
                  const isBool = BOOLEAN_INDICATORS.has(c.indicator);
                  const needsP2 = NEEDS_PERIOD2.has(c.indicator);
                  return (
                    <div key={i} className="flex gap-2 mb-2 flex-wrap items-center p-2 rounded-lg"
                      style={{ background: 'var(--panel)', border: '1px solid var(--border)' }}>
                      {/* Searchable indicator picker */}
                      <IndicatorSearch
                        value={c.indicator}
                        onChange={v => updateCondition(i, 'indicator', v)}
                        groups={INDICATOR_GROUPS}
                      />

                      {/* Period 1 */}
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
                        <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>{needsP2 ? t('period') + ' 1' : t('period')}</span>
                        <input className="input" style={{ maxWidth: 70, fontSize: 12 }} type="number" min="1"
                          value={c.period} onChange={e => updateCondition(i, 'period', e.target.value)} />
                      </div>

                      {/* Period 2 (for crossovers) */}
                      {needsP2 && (
                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
                          <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>{t('period')} 2</span>
                          <input className="input" style={{ maxWidth: 70, fontSize: 12 }} type="number" min="1"
                            value={c.period2 || 26} onChange={e => updateCondition(i, 'period2', e.target.value)} />
                        </div>
                      )}

                      {/* Operator or DETECTED badge */}
                      {isBool ? (
                        <span className="px-3 py-1 rounded-lg text-xs font-bold"
                          style={{ background: 'rgba(34,197,94,0.15)', color: '#22c55e', border: '1px solid #22c55e' }}>
                          ✓ DETECTED
                        </span>
                      ) : (
                        <select className="input" style={{ maxWidth: 65, fontSize: 12 }} value={c.op}
                          onChange={e => updateCondition(i, 'op', e.target.value)}>
                          <option value="<">{'<'}</option>
                          <option value="<=">{'<='}</option>
                          <option value=">">{'>'}</option>
                          <option value=">=">{'>='}</option>
                          <option value="==">{'=='}</option>
                          <option value="PRICE_ABOVE">price &gt;</option>
                          <option value="PRICE_BELOW">price &lt;</option>
                        </select>
                      )}

                      {/* Value (only for numeric indicators) */}
                      {!isBool && (
                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
                          <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>{t('value')}</span>
                          <input className="input" style={{ maxWidth: 90, fontSize: 12 }} type="number" step="any"
                            value={c.value} onChange={e => updateCondition(i, 'value', e.target.value)} />
                        </div>
                      )}

                      {/* Remove button */}
                      <button type="button"
                        onClick={() => setForm(f => ({ ...f, conditions: f.conditions.filter((_, j) => j !== i) }))}
                        style={{ background: 'rgba(239,68,68,0.15)', border: '1px solid #ef4444', color: '#ef4444',
                          borderRadius: 6, padding: '4px 10px', cursor: 'pointer', fontSize: 14, fontWeight: 'bold' }}>
                        ×
                      </button>
                    </div>
                  );
                })}
                <button type="button" className="btn btn-secondary text-sm"
                  onClick={() => setForm(f => ({ ...f, conditions: [...f.conditions, { indicator: 'RSI', period: 14, period2: 26, op: '<', value: 30 }] }))}>
                  + {t('addCondition')}
                </button>
              </>
            )}
          </div>

          {/* ── Advanced Options ── */}
          <div>
            <button type="button" onClick={() => setShowAdvanced(v => !v)}
              className="text-sm flex items-center gap-2"
              style={{ color: 'var(--text-muted)', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}>
              {showAdvanced ? '▼' : '▶'} {t('advancedOptions')}
            </button>
            {showAdvanced && (
              <div className="mt-3 space-y-4 p-3 rounded-lg" style={{ background: 'var(--bg)', border: '1px solid var(--border)' }}>

                {/* Paper Trading */}
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <input type="checkbox" checked={form.paperMode}
                    onChange={e => setForm(f => ({ ...f, paperMode: e.target.checked }))} />
                  <span style={{ color: form.paperMode ? '#60a5fa' : 'var(--text-muted)' }}>
                    📄 {t('paperMode')} — {t('paperModeHint')}
                  </span>
                </label>

                {/* Trailing SL */}
                <div className="flex items-center gap-3">
                  <label className="text-sm" style={{ color: 'var(--text-muted)', minWidth: 140 }}>
                    📈 {t('trailingSl')} %
                  </label>
                  <input className="input" type="number" min="0.1" step="0.1" style={{ maxWidth: 100 }}
                    value={form.trailingSl}
                    onChange={e => setForm(f => ({ ...f, trailingSl: e.target.value }))}
                    placeholder={t('off')} />
                  <span className="text-xs" style={{ color: 'var(--text-muted)' }}>{t('trailingSlHint')}</span>
                </div>

                {/* Trailing TP */}
                <div className="space-y-2">
                  <div className="flex items-center gap-3">
                    <label className="text-sm" style={{ color: 'var(--text-muted)', minWidth: 140 }}>
                      🎯 {t('trailingTp')} %
                    </label>
                    <input className="input" type="number" min="0.1" step="0.1" style={{ maxWidth: 100 }}
                      value={form.trailingTp}
                      onChange={e => setForm(f => ({ ...f, trailingTp: e.target.value }))}
                      placeholder={t('off')} />
                    <span className="text-xs" style={{ color: 'var(--text-muted)' }}>{t('trailingTpHint')}</span>
                  </div>
                  {form.trailingTp && (
                    <div className="flex items-center gap-3 ml-5">
                      <label className="text-sm" style={{ color: 'var(--text-muted)', minWidth: 140 }}>
                        {t('trailingTpActivation')} %
                      </label>
                      <input className="input" type="number" min="0.1" step="0.1" style={{ maxWidth: 100 }}
                        value={form.trailingTpActivation}
                        onChange={e => setForm(f => ({ ...f, trailingTpActivation: e.target.value }))} />
                      <span className="text-xs" style={{ color: 'var(--text-muted)' }}>{t('trailingTpActivationHint')}</span>
                    </div>
                  )}
                </div>

                {/* DCA */}
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <input type="checkbox" checked={form.dcaEnabled}
                    onChange={e => setForm(f => ({ ...f, dcaEnabled: e.target.checked }))} />
                  <span style={{ color: form.dcaEnabled ? '#22c55e' : 'var(--text-muted)' }}>
                    📉 {t('dcaMode')}
                  </span>
                </label>
                {form.dcaEnabled && (
                  <div className="grid grid-cols-2 gap-3 ml-5">
                    <div>
                      <label className="label">{t('dcaPercent')} %</label>
                      <input className="input" type="number" min="0.5" step="0.5" value={form.dcaPercent}
                        onChange={e => setForm(f => ({ ...f, dcaPercent: +e.target.value }))} />
                    </div>
                    <div>
                      <label className="label">{t('dcaAmount')} USDT</label>
                      <input className="input" type="number" min="1" value={form.dcaAmount}
                        onChange={e => setForm(f => ({ ...f, dcaAmount: +e.target.value }))} />
                    </div>
                  </div>
                )}

                {/* Marketplace */}
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <input type="checkbox" checked={form.isPublic}
                    onChange={e => setForm(f => ({ ...f, isPublic: e.target.checked }))} />
                  <span style={{ color: form.isPublic ? '#f59e0b' : 'var(--text-muted)' }}>
                    🏪 {t('publishToMarketplace')}
                  </span>
                </label>
                {form.isPublic && (
                  <input className="input ml-5" value={form.publicDescription}
                    onChange={e => setForm(f => ({ ...f, publicDescription: e.target.value }))}
                    placeholder={t('strategyDescription')} />
                )}
              </div>
            )}
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-2">
            <button onClick={save} disabled={saving} className="btn btn-primary">
              {saving ? '...' : editId !== null ? t('updateStrategy') : t('saveStrategy')}
            </button>
            {editId !== null && (
              <button onClick={resetForm} className="btn btn-secondary">{t('cancelEdit')}</button>
            )}
          </div>
        </div>

        {/* ── Marketplace ── */}
        {showMarket && (
          <div className="card">
            <h2 className="font-bold mb-4">🏪 {t('marketplace')}</h2>
            {marketplace.length === 0 ? (
              <p style={{ color: 'var(--text-muted)' }}>{t('noPublicStrategies')}</p>
            ) : (
              <div className="space-y-2">
                {marketplace.map((s: any) => (
                  <div key={s.id} className="p-3 rounded-lg" style={{ background: 'var(--bg)', border: '1px solid var(--border)' }}>
                    <div className="flex items-start justify-between flex-wrap gap-2">
                      <div>
                        <div className="font-bold">{s.name}</div>
                        <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
                          {s.exchange?.toUpperCase()} | {s.timeframe} | TP +{s.tp_percent}% / SL -{s.sl_percent}%
                          {s.trailing_sl ? ` | Trail ${s.trailing_sl}%` : ''}
                          {s.dca_enabled ? ' | DCA' : ''}
                        </div>
                        {s.description && <p className="text-xs mt-1">{s.description}</p>}
                        <div className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>👤 {s.author}</div>
                      </div>
                      {!s.is_mine && (
                        <button onClick={async () => {
                          try {
                            await api.post(`/api/strategies/marketplace/${s.id}/copy`);
                            show(`✅ ${s.name} — ${t('strategyCopied')}`, 'success');
                            load();
                          } catch (e: any) { show(e.response?.data?.detail || t('error'), 'error'); }
                        }} className="btn btn-secondary text-sm">{t('copyStrategy')}</button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ── Strategy List ── */}
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-bold">{t('myStrategies')}</h2>
            <button onClick={() => { setShowMarket(v => !v); if (!showMarket) loadMarketplace(); }}
              className="btn btn-secondary text-sm">
              🏪 {t('marketplace')}
            </button>
          </div>
          {list.length === 0 ? (
            <p style={{ color: 'var(--text-muted)' }}>{t('noStrategies')}</p>
          ) : (
            <div className="space-y-2">
              {list.map(s => (
                <div key={s.id} className="p-3 rounded-lg"
                  style={{ background: 'var(--bg)', border: editId === s.id ? '1px solid var(--accent)' : '1px solid var(--border)' }}>
                  <div className="flex items-start gap-3 flex-wrap">
                    <div className="flex-1 min-w-0">
                      <div className="font-bold">{s.name}</div>
                      <div className="text-xs mt-1 space-y-0.5" style={{ color: 'var(--text-muted)' }}>
                        <div>
                          {(s.config.exchange || 'binance').toUpperCase()} | {s.config.timeframe} |
                          {s.config.tp_sl_mode === 'price'
                            ? ` TP $${s.config.tp_price} / SL $${s.config.sl_price}`
                            : ` TP +${s.config.tp_percent}% / SL -${s.config.sl_percent}%`
                          } | {s.config.amount_usdt} USDT
                          {s.config.order_type && s.config.order_type !== 'market' && (
                            <span className="ml-1 px-1 rounded text-xs" style={{ background: 'var(--panel)' }}>
                              {orderTypeLabel(s.config.order_type)}
                            </span>
                          )}
                        </div>
                        <div className="flex flex-wrap gap-1 mt-1">
                          {(s.config.symbols || []).map((sym: string) => (
                            <span key={sym} className="px-2 py-0.5 rounded-full text-xs font-mono"
                              style={{ background: 'var(--panel)', border: '1px solid var(--border)' }}>
                              {sym}
                            </span>
                          ))}
                        </div>
                        <div className="flex flex-wrap gap-2 items-center">
                          <span>
                            {s.config.webhook_mode ? `📡 ${t('webhookLabel')}` :
                              s.config.entry_conditions?.length ? `${s.config.entry_conditions.length} ${t('conditionsSuffix')}` :
                              t('noConditionLabel')}
                          </span>
                          {s.config.paper_mode && (
                            <span className="px-1.5 py-0.5 rounded text-xs" style={{ background: '#1e3a5f', color: '#60a5fa' }}>📄 Paper</span>
                          )}
                          {s.config.trailing_sl && (
                            <span className="px-1.5 py-0.5 rounded text-xs" style={{ background: '#1a2a0a', color: '#86efac' }}>📈 Trail SL {s.config.trailing_sl}%</span>
                          )}
                          {s.config.trailing_tp && (
                            <span className="px-1.5 py-0.5 rounded text-xs" style={{ background: '#1a1f0a', color: '#fde68a' }}>🎯 Trail TP {s.config.trailing_tp}%</span>
                          )}
                          {s.config.dca_enabled && (
                            <span className="px-1.5 py-0.5 rounded text-xs" style={{ background: '#1a1a2a', color: '#a78bfa' }}>📉 DCA</span>
                          )}
                          {s.is_public && (
                            <span className="px-1.5 py-0.5 rounded text-xs" style={{ background: '#2a1a00', color: '#fbbf24' }}>🏪 Public</span>
                          )}
                        </div>
                        {s.webhook_token && (
                          <div className="mt-1 flex items-center gap-2">
                            <span className="text-xs" style={{ color: 'var(--text-muted)' }}>📡 Webhook:</span>
                            <code className="text-xs px-1 rounded" style={{ background: 'var(--panel)', color: '#60a5fa', fontSize: 10 }}>
                              /api/webhook/{s.webhook_token.slice(0, 12)}...
                            </code>
                            <button type="button" onClick={() => {
                              const url = `${window.location.protocol}//${window.location.host}/api/webhook/${s.webhook_token}`;
                              navigator.clipboard.writeText(url);
                              show('📋 Webhook URL kopyalandı', 'success');
                            }} className="text-xs" style={{ color: '#60a5fa', background: 'none', border: 'none', cursor: 'pointer' }}>
                              {t('copy')}
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                    <div className="flex gap-2 flex-wrap">
                      <button onClick={() => startEdit(s)} className="btn btn-secondary text-sm">{t('edit')}</button>
                      <button onClick={() => toggleActive(s)}
                        className={`btn text-sm ${s.is_active ? 'btn-primary' : 'btn-secondary'}`}>
                        {s.is_active ? '● ' + t('active') : '○ ' + t('inactive')}
                      </button>
                      <button onClick={() => del(s.id)} className="btn btn-danger text-sm">{t('delete')}</button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
