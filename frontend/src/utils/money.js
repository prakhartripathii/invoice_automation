// Hardcoded demo FX rates (USD base). For a real app, wire to a live FX API
// and cache daily rates on the backend.
const RATES_TO_USD = {
  USD: 1,
  EUR: 1.08,   // 1 EUR = 1.08 USD
  JPY: 0.0065, // 1 JPY = 0.0065 USD
  INR: 0.012,  // 1 INR = 0.012 USD
};

export const SUPPORTED_CURRENCIES = ['USD', 'EUR', 'JPY', 'INR'];

export const CURRENCY_LABELS = {
  USD: 'USD',
  EUR: 'EUR',
  JPY: 'JPY',
  INR: 'INR',
};

export const CURRENCY_SYMBOLS = {
  USD: '$',
  EUR: '€',
  JPY: '¥',
  INR: '₹',
};

const LOCALES = {
  USD: 'en-US',
  EUR: 'de-DE',
  JPY: 'ja-JP',
  INR: 'en-IN',
};

export function convert(amount, from = 'USD', to = 'USD') {
  if (amount == null || amount === '') return null;
  const n = Number(amount);
  if (Number.isNaN(n)) return null;
  const src = RATES_TO_USD[from] ?? 1;
  const dst = RATES_TO_USD[to] ?? 1;
  return (n * src) / dst;
}

export function formatMoney(amount, from = 'USD', to = 'USD') {
  const converted = convert(amount, from, to);
  if (converted == null) return '—';
  const locale = LOCALES[to] || 'en-US';
  const fractionDigits = to === 'JPY' ? 0 : 2;
  try {
    return new Intl.NumberFormat(locale, {
      style: 'currency',
      currency: to,
      minimumFractionDigits: fractionDigits,
      maximumFractionDigits: fractionDigits,
    }).format(converted);
  } catch {
    return `${CURRENCY_SYMBOLS[to] || ''}${converted.toFixed(fractionDigits)}`;
  }
}
