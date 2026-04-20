// CoinScopeAI Mock Data — Realistic crypto futures trading data
// All data is demo/mock since the engine API is offline until VPS deployment

export const SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT'] as const;
export type Symbol = typeof SYMBOLS[number];

export const SYMBOL_PRICES: Record<Symbol, { price: number; change24h: number; changePct: number }> = {
  BTCUSDT: { price: 84532.40, change24h: 1247.30, changePct: 1.50 },
  ETHUSDT: { price: 1632.18, change24h: -23.45, changePct: -1.42 },
  SOLUSDT: { price: 131.87, change24h: 5.62, changePct: 4.46 },
  BNBUSDT: { price: 606.33, change24h: 8.91, changePct: 1.49 },
  XRPUSDT: { price: 2.0841, change24h: -0.0312, changePct: -1.48 },
};

// Overview
export const PORTFOLIO = {
  accountBalance: 127843.52,
  totalEquity: 134291.18,
  unrealizedPnl: 6447.66,
  realizedPnlToday: 2134.89,
  pnl24h: 3847.22,
  pnl24hPct: 2.94,
  activePositions: 3,
  riskGateStatus: 'GREEN' as const,
  marginUsed: 42180.00,
  availableMargin: 85663.52,
  winRate: 67.3,
  totalTrades: 847,
};

// 30-day equity curve
export const EQUITY_CURVE_30D = Array.from({ length: 30 }, (_, i) => {
  const base = 115000;
  const trend = i * 650;
  const noise = Math.sin(i * 0.8) * 3000 + Math.cos(i * 1.3) * 1500;
  const val = base + trend + noise;
  const date = new Date(2026, 3, 10 - 29 + i);
  return {
    date: date.toISOString().split('T')[0],
    equity: Math.round(val * 100) / 100,
    drawdown: Math.round(Math.max(0, Math.random() * 3.5) * 100) / 100,
  };
});

// Extended equity curve for 90D
export const EQUITY_CURVE_90D = Array.from({ length: 90 }, (_, i) => {
  const base = 85000;
  const trend = i * 550;
  const noise = Math.sin(i * 0.5) * 5000 + Math.cos(i * 0.9) * 3000;
  const val = base + trend + noise;
  const date = new Date(2026, 0, 10 + i);
  return {
    date: date.toISOString().split('T')[0],
    equity: Math.round(val * 100) / 100,
    drawdown: Math.round(Math.max(0, Math.sin(i * 0.3) * 4 + Math.random() * 2) * 100) / 100,
  };
});

// Scanner signals
export const SCANNER_SIGNALS = [
  { symbol: 'BTCUSDT' as Symbol, mlScore: 0.87, regime: 'Trending' as const, confidence: 92, direction: 'LONG' as const, entryPrice: 84200, targetPrice: 86500, stopLoss: 83100, riskReward: 2.09, timeframe: '4h', lastUpdate: '2 min ago' },
  { symbol: 'ETHUSDT' as Symbol, mlScore: 0.42, regime: 'Mean-Reverting' as const, confidence: 65, direction: 'SHORT' as const, entryPrice: 1645, targetPrice: 1580, stopLoss: 1680, riskReward: 1.86, timeframe: '4h', lastUpdate: '5 min ago' },
  { symbol: 'SOLUSDT' as Symbol, mlScore: 0.91, regime: 'Trending' as const, confidence: 88, direction: 'LONG' as const, entryPrice: 129.50, targetPrice: 142.00, stopLoss: 125.00, riskReward: 2.78, timeframe: '4h', lastUpdate: '1 min ago' },
  { symbol: 'BNBUSDT' as Symbol, mlScore: 0.55, regime: 'Quiet' as const, confidence: 48, direction: 'NEUTRAL' as const, entryPrice: 605, targetPrice: 620, stopLoss: 595, riskReward: 1.50, timeframe: '4h', lastUpdate: '8 min ago' },
  { symbol: 'XRPUSDT' as Symbol, mlScore: 0.73, regime: 'Volatile' as const, confidence: 71, direction: 'LONG' as const, entryPrice: 2.05, targetPrice: 2.25, stopLoss: 1.95, riskReward: 2.00, timeframe: '4h', lastUpdate: '3 min ago' },
];

// Open positions
export const POSITIONS = [
  { id: 1, symbol: 'BTCUSDT' as Symbol, side: 'LONG' as const, entryPrice: 82150.00, currentPrice: 84532.40, size: 0.5, leverage: 10, unrealizedPnl: 1191.20, unrealizedPnlPct: 2.90, liquidationPrice: 74120.00, marginUsed: 4107.50, duration: '2d 14h', stopLoss: 80500, takeProfit: 88000 },
  { id: 2, symbol: 'SOLUSDT' as Symbol, side: 'LONG' as const, entryPrice: 124.30, currentPrice: 131.87, size: 200, leverage: 5, unrealizedPnl: 1514.00, unrealizedPnlPct: 6.09, liquidationPrice: 99.44, marginUsed: 4972.00, duration: '5d 8h', stopLoss: 118.00, takeProfit: 145.00 },
  { id: 3, symbol: 'ETHUSDT' as Symbol, side: 'SHORT' as const, entryPrice: 1680.50, currentPrice: 1632.18, size: 15, leverage: 8, unrealizedPnl: 724.80, unrealizedPnlPct: 2.88, liquidationPrice: 1848.55, marginUsed: 3150.94, duration: '1d 3h', stopLoss: 1720, takeProfit: 1550 },
];

// Trade journal
export const JOURNAL_TRADES = [
  { id: 1, symbol: 'BTCUSDT', side: 'LONG', entryPrice: 79800, exitPrice: 82400, pnl: 2600, pnlPct: 3.26, size: 1.0, leverage: 10, entryDate: '2026-04-02 14:30', exitDate: '2026-04-04 09:15', duration: '1d 18h', strategy: 'Trend Follow', notes: 'Clean breakout above 80k resistance. ML score 0.89.' },
  { id: 2, symbol: 'ETHUSDT', side: 'SHORT', entryPrice: 1720, exitPrice: 1680, pnl: 600, pnlPct: 2.33, size: 15, leverage: 8, entryDate: '2026-04-03 08:00', exitDate: '2026-04-05 16:45', duration: '2d 8h', strategy: 'Mean Reversion', notes: 'Overbought RSI divergence. Regime confirmed mean-reverting.' },
  { id: 3, symbol: 'SOLUSDT', side: 'LONG', entryPrice: 118.50, exitPrice: 115.20, pnl: -660, pnlPct: -2.78, size: 200, leverage: 5, entryDate: '2026-03-28 11:00', exitDate: '2026-03-29 03:30', duration: '16h', strategy: 'Breakout', notes: 'False breakout. Stop hit. Regime shifted to volatile mid-trade.' },
  { id: 4, symbol: 'BNBUSDT', side: 'LONG', entryPrice: 580, exitPrice: 605, pnl: 1250, pnlPct: 4.31, size: 50, leverage: 5, entryDate: '2026-03-25 09:00', exitDate: '2026-03-30 14:00', duration: '5d 5h', strategy: 'Trend Follow', notes: 'Strong uptrend continuation. Held through consolidation.' },
  { id: 5, symbol: 'XRPUSDT', side: 'LONG', entryPrice: 1.98, exitPrice: 2.12, pnl: 1400, pnlPct: 7.07, size: 10000, leverage: 5, entryDate: '2026-03-20 16:00', exitDate: '2026-03-24 11:30', duration: '3d 19h', strategy: 'Momentum', notes: 'Funding rate flip + liquidation cascade signal.' },
  { id: 6, symbol: 'BTCUSDT', side: 'SHORT', entryPrice: 83500, exitPrice: 84100, pnl: -300, pnlPct: -0.72, size: 0.5, leverage: 10, entryDate: '2026-03-18 20:00', exitDate: '2026-03-19 02:15', duration: '6h', strategy: 'Mean Reversion', notes: 'Counter-trend trade. Stop hit quickly. Low confidence signal.' },
  { id: 7, symbol: 'ETHUSDT', side: 'LONG', entryPrice: 1590, exitPrice: 1650, pnl: 900, pnlPct: 3.77, size: 15, leverage: 8, entryDate: '2026-03-15 10:00', exitDate: '2026-03-17 22:00', duration: '2d 12h', strategy: 'Trend Follow', notes: 'ETH/BTC ratio bounce. Strong volume confirmation.' },
  { id: 8, symbol: 'SOLUSDT', side: 'LONG', entryPrice: 108.00, exitPrice: 122.50, pnl: 2900, pnlPct: 13.43, size: 200, leverage: 5, entryDate: '2026-03-10 08:00', exitDate: '2026-03-14 16:00', duration: '4d 8h', strategy: 'Breakout', notes: 'Major breakout above 110 resistance. Held full target.' },
  { id: 9, symbol: 'BTCUSDT', side: 'LONG', entryPrice: 76200, exitPrice: 79500, pnl: 3300, pnlPct: 4.33, size: 1.0, leverage: 10, entryDate: '2026-03-05 14:00', exitDate: '2026-03-08 09:00', duration: '2d 19h', strategy: 'Trend Follow', notes: 'Weekly support bounce. All timeframes aligned.' },
  { id: 10, symbol: 'XRPUSDT', side: 'SHORT', entryPrice: 2.15, exitPrice: 2.08, pnl: 700, pnlPct: 3.26, size: 10000, leverage: 5, entryDate: '2026-03-01 12:00', exitDate: '2026-03-03 18:00', duration: '2d 6h', strategy: 'Mean Reversion', notes: 'Overextended rally. Funding rate extremely positive.' },
];

// Performance metrics
export const PERFORMANCE = {
  winRate: 67.3,
  profitFactor: 2.41,
  sharpeRatio: 1.87,
  maxDrawdown: 8.2,
  maxDrawdownAmount: 11420,
  totalReturn: 34.2,
  totalReturnAmount: 34291.18,
  avgWin: 1578.50,
  avgLoss: -654.30,
  largestWin: 4200,
  largestLoss: -1850,
  totalTrades: 847,
  winningTrades: 570,
  losingTrades: 277,
  avgHoldTime: '2d 4h',
  bestMonth: 'Feb 2026',
  bestMonthReturn: 12.4,
  worstMonth: 'Jan 2026',
  worstMonthReturn: -3.1,
  consecutiveWins: 8,
  consecutiveLosses: 3,
};

export const MONTHLY_PERFORMANCE = [
  { month: 'Oct 2025', pnl: 4200, pnlPct: 4.8, trades: 62, winRate: 64.5 },
  { month: 'Nov 2025', pnl: 6800, pnlPct: 7.2, trades: 78, winRate: 69.2 },
  { month: 'Dec 2025', pnl: 3100, pnlPct: 3.1, trades: 55, winRate: 61.8 },
  { month: 'Jan 2026', pnl: -2900, pnlPct: -3.1, trades: 71, winRate: 52.1 },
  { month: 'Feb 2026', pnl: 11200, pnlPct: 12.4, trades: 89, winRate: 73.0 },
  { month: 'Mar 2026', pnl: 8400, pnlPct: 8.1, trades: 82, winRate: 68.3 },
  { month: 'Apr 2026', pnl: 3847, pnlPct: 2.9, trades: 34, winRate: 70.6 },
];

// Risk gate
export const RISK_GATE = {
  status: 'GREEN' as 'GREEN' | 'YELLOW' | 'RED' | 'BLACK',
  currentDrawdown: 3.2,
  maxDrawdownThreshold: 10,
  dailyLoss: 0.8,
  dailyLossThreshold: 5,
  openPositions: 3,
  maxPositions: 3,
  currentLeverage: 10,
  maxLeverage: 20,
  positionHeat: 42,
  heatCap: 80,
  killSwitchActive: false,
  lastCheck: '2026-04-10 12:00:00',
  alerts: [
    { level: 'INFO' as const, message: 'All risk parameters within normal range', time: '12:00:00' },
    { level: 'WARN' as const, message: 'Position count at maximum (3/3)', time: '11:45:00' },
    { level: 'INFO' as const, message: 'Daily loss reset at 00:00 UTC', time: '00:00:00' },
  ],
};

// Regime detection
export const REGIMES: Record<Symbol, { current: string; confidence: number; history: { date: string; regime: string }[] }> = {
  BTCUSDT: {
    current: 'Trending',
    confidence: 92,
    history: [
      { date: '2026-04-10', regime: 'Trending' },
      { date: '2026-04-09', regime: 'Trending' },
      { date: '2026-04-08', regime: 'Volatile' },
      { date: '2026-04-07', regime: 'Volatile' },
      { date: '2026-04-06', regime: 'Mean-Reverting' },
      { date: '2026-04-05', regime: 'Trending' },
      { date: '2026-04-04', regime: 'Trending' },
      { date: '2026-04-03', regime: 'Quiet' },
      { date: '2026-04-02', regime: 'Trending' },
      { date: '2026-04-01', regime: 'Mean-Reverting' },
    ],
  },
  ETHUSDT: {
    current: 'Mean-Reverting',
    confidence: 65,
    history: [
      { date: '2026-04-10', regime: 'Mean-Reverting' },
      { date: '2026-04-09', regime: 'Mean-Reverting' },
      { date: '2026-04-08', regime: 'Trending' },
      { date: '2026-04-07', regime: 'Quiet' },
      { date: '2026-04-06', regime: 'Quiet' },
      { date: '2026-04-05', regime: 'Mean-Reverting' },
      { date: '2026-04-04', regime: 'Volatile' },
      { date: '2026-04-03', regime: 'Trending' },
      { date: '2026-04-02', regime: 'Trending' },
      { date: '2026-04-01', regime: 'Mean-Reverting' },
    ],
  },
  SOLUSDT: {
    current: 'Trending',
    confidence: 88,
    history: [
      { date: '2026-04-10', regime: 'Trending' },
      { date: '2026-04-09', regime: 'Trending' },
      { date: '2026-04-08', regime: 'Trending' },
      { date: '2026-04-07', regime: 'Volatile' },
      { date: '2026-04-06', regime: 'Volatile' },
      { date: '2026-04-05', regime: 'Trending' },
      { date: '2026-04-04', regime: 'Mean-Reverting' },
      { date: '2026-04-03', regime: 'Trending' },
      { date: '2026-04-02', regime: 'Trending' },
      { date: '2026-04-01', regime: 'Quiet' },
    ],
  },
  BNBUSDT: {
    current: 'Quiet',
    confidence: 48,
    history: [
      { date: '2026-04-10', regime: 'Quiet' },
      { date: '2026-04-09', regime: 'Quiet' },
      { date: '2026-04-08', regime: 'Mean-Reverting' },
      { date: '2026-04-07', regime: 'Quiet' },
      { date: '2026-04-06', regime: 'Trending' },
      { date: '2026-04-05', regime: 'Trending' },
      { date: '2026-04-04', regime: 'Quiet' },
      { date: '2026-04-03', regime: 'Quiet' },
      { date: '2026-04-02', regime: 'Mean-Reverting' },
      { date: '2026-04-01', regime: 'Volatile' },
    ],
  },
  XRPUSDT: {
    current: 'Volatile',
    confidence: 71,
    history: [
      { date: '2026-04-10', regime: 'Volatile' },
      { date: '2026-04-09', regime: 'Trending' },
      { date: '2026-04-08', regime: 'Volatile' },
      { date: '2026-04-07', regime: 'Volatile' },
      { date: '2026-04-06', regime: 'Mean-Reverting' },
      { date: '2026-04-05', regime: 'Trending' },
      { date: '2026-04-04', regime: 'Trending' },
      { date: '2026-04-03', regime: 'Volatile' },
      { date: '2026-04-02', regime: 'Quiet' },
      { date: '2026-04-01', regime: 'Trending' },
    ],
  },
};

// Alpha signals
export const ALPHA_SIGNALS = {
  fundingRates: [
    { symbol: 'BTCUSDT', rate: 0.0082, annualized: 8.97, signal: 'Neutral' as const },
    { symbol: 'ETHUSDT', rate: -0.0045, annualized: -4.93, signal: 'Bullish' as const },
    { symbol: 'SOLUSDT', rate: 0.0210, annualized: 23.01, signal: 'Bearish' as const },
    { symbol: 'BNBUSDT', rate: 0.0051, annualized: 5.59, signal: 'Neutral' as const },
    { symbol: 'XRPUSDT', rate: 0.0156, annualized: 17.09, signal: 'Bearish' as const },
  ],
  liquidationCascades: [
    { symbol: 'BTCUSDT', longLiqZone: 81200, shortLiqZone: 87500, intensity: 'Medium' as const, estimatedVolume: 245000000 },
    { symbol: 'ETHUSDT', longLiqZone: 1560, shortLiqZone: 1720, intensity: 'High' as const, estimatedVolume: 89000000 },
    { symbol: 'SOLUSDT', longLiqZone: 120, shortLiqZone: 145, intensity: 'Low' as const, estimatedVolume: 34000000 },
  ],
  orderBookImbalance: [
    { symbol: 'BTCUSDT', bidDepth: 1250000000, askDepth: 980000000, imbalance: 0.138, signal: 'Bullish' as const },
    { symbol: 'ETHUSDT', bidDepth: 340000000, askDepth: 410000000, imbalance: -0.093, signal: 'Bearish' as const },
    { symbol: 'SOLUSDT', bidDepth: 89000000, askDepth: 72000000, imbalance: 0.106, signal: 'Bullish' as const },
    { symbol: 'BNBUSDT', bidDepth: 45000000, askDepth: 48000000, imbalance: -0.032, signal: 'Neutral' as const },
    { symbol: 'XRPUSDT', bidDepth: 67000000, askDepth: 58000000, imbalance: 0.072, signal: 'Bullish' as const },
  ],
  alphaScores: [
    { symbol: 'BTCUSDT', composite: 78, momentum: 82, meanReversion: 45, volatility: 61, volume: 89 },
    { symbol: 'ETHUSDT', composite: 52, momentum: 38, meanReversion: 72, volatility: 55, volume: 44 },
    { symbol: 'SOLUSDT', composite: 85, momentum: 91, meanReversion: 32, volatility: 68, volume: 92 },
    { symbol: 'BNBUSDT', composite: 41, momentum: 35, meanReversion: 58, volatility: 30, volume: 42 },
    { symbol: 'XRPUSDT', composite: 69, momentum: 74, meanReversion: 48, volatility: 78, volume: 56 },
  ],
};

// Market data
export const MARKET_DATA = {
  exchanges: ['Binance', 'Bybit', 'OKX', 'Hyperliquid'] as const,
  prices: {
    BTCUSDT: { Binance: 84532.40, Bybit: 84528.10, OKX: 84535.80, Hyperliquid: 84530.00 },
    ETHUSDT: { Binance: 1632.18, Bybit: 1631.90, OKX: 1632.45, Hyperliquid: 1632.00 },
    SOLUSDT: { Binance: 131.87, Bybit: 131.82, OKX: 131.90, Hyperliquid: 131.85 },
    BNBUSDT: { Binance: 606.33, Bybit: 606.10, OKX: 606.50, Hyperliquid: 606.20 },
    XRPUSDT: { Binance: 2.0841, Bybit: 2.0838, OKX: 2.0845, Hyperliquid: 2.0840 },
  },
  fundingRates: {
    BTCUSDT: { Binance: 0.0082, Bybit: 0.0079, OKX: 0.0085, Hyperliquid: 0.0080 },
    ETHUSDT: { Binance: -0.0045, Bybit: -0.0042, OKX: -0.0048, Hyperliquid: -0.0044 },
    SOLUSDT: { Binance: 0.0210, Bybit: 0.0205, OKX: 0.0215, Hyperliquid: 0.0208 },
    BNBUSDT: { Binance: 0.0051, Bybit: 0.0048, OKX: 0.0054, Hyperliquid: 0.0050 },
    XRPUSDT: { Binance: 0.0156, Bybit: 0.0152, OKX: 0.0160, Hyperliquid: 0.0155 },
  },
  openInterest: {
    BTCUSDT: { Binance: 8420000000, Bybit: 3210000000, OKX: 2890000000, Hyperliquid: 1540000000 },
    ETHUSDT: { Binance: 4120000000, Bybit: 1680000000, OKX: 1420000000, Hyperliquid: 890000000 },
    SOLUSDT: { Binance: 1890000000, Bybit: 720000000, OKX: 580000000, Hyperliquid: 340000000 },
    BNBUSDT: { Binance: 620000000, Bybit: 280000000, OKX: 210000000, Hyperliquid: 95000000 },
    XRPUSDT: { Binance: 890000000, Bybit: 340000000, OKX: 290000000, Hyperliquid: 180000000 },
  },
  recentLiquidations: [
    { symbol: 'BTCUSDT', side: 'LONG', size: 2450000, price: 83800, exchange: 'Binance', time: '12:04:32' },
    { symbol: 'ETHUSDT', side: 'SHORT', size: 890000, price: 1635, exchange: 'Bybit', time: '12:03:15' },
    { symbol: 'SOLUSDT', side: 'LONG', size: 340000, price: 130.50, exchange: 'OKX', time: '12:02:48' },
    { symbol: 'BTCUSDT', side: 'SHORT', size: 1200000, price: 84600, exchange: 'Hyperliquid', time: '12:01:22' },
    { symbol: 'XRPUSDT', side: 'LONG', size: 560000, price: 2.07, exchange: 'Binance', time: '11:59:45' },
    { symbol: 'ETHUSDT', side: 'LONG', size: 450000, price: 1628, exchange: 'OKX', time: '11:58:10' },
    { symbol: 'BTCUSDT', side: 'LONG', size: 3100000, price: 83500, exchange: 'Binance', time: '11:55:33' },
    { symbol: 'SOLUSDT', side: 'SHORT', size: 210000, price: 132.80, exchange: 'Bybit', time: '11:54:01' },
  ],
};

// Backtest results
export const BACKTEST_RESULTS = {
  walkForward: [
    { period: 'Q1 2025', inSampleReturn: 18.4, outOfSampleReturn: 12.1, sharpe: 1.62, maxDD: 6.8, trades: 156 },
    { period: 'Q2 2025', inSampleReturn: 22.1, outOfSampleReturn: 15.3, sharpe: 1.89, maxDD: 5.2, trades: 178 },
    { period: 'Q3 2025', inSampleReturn: 14.8, outOfSampleReturn: 9.7, sharpe: 1.41, maxDD: 8.1, trades: 142 },
    { period: 'Q4 2025', inSampleReturn: 28.6, outOfSampleReturn: 19.8, sharpe: 2.14, maxDD: 4.5, trades: 201 },
    { period: 'Q1 2026', inSampleReturn: 31.2, outOfSampleReturn: 22.4, sharpe: 2.31, maxDD: 3.9, trades: 215 },
  ],
  strategyComparison: [
    { strategy: 'Trend Follow v3', winRate: 62.4, profitFactor: 2.18, sharpe: 1.76, maxDD: 7.2, totalReturn: 89.4 },
    { strategy: 'Mean Reversion v2', winRate: 71.2, profitFactor: 1.95, sharpe: 1.54, maxDD: 9.1, totalReturn: 67.8 },
    { strategy: 'Momentum Alpha', winRate: 58.9, profitFactor: 2.45, sharpe: 1.92, maxDD: 6.5, totalReturn: 104.2 },
    { strategy: 'Breakout Scanner', winRate: 55.1, profitFactor: 2.67, sharpe: 2.08, maxDD: 5.8, totalReturn: 112.6 },
    { strategy: 'ML Ensemble v2', winRate: 67.3, profitFactor: 2.41, sharpe: 1.87, maxDD: 8.2, totalReturn: 134.2 },
  ],
  mlModelPerformance: {
    version: 'v2.4.1',
    breakthrough: '10/10 4h configs profitable',
    accuracy: 73.8,
    precision: 71.2,
    recall: 76.4,
    f1Score: 73.7,
    configs: [
      { timeframe: '4h', symbol: 'BTCUSDT', winRate: 68.5, return: 24.1, sharpe: 1.92 },
      { timeframe: '4h', symbol: 'ETHUSDT', winRate: 65.2, return: 18.7, sharpe: 1.65 },
      { timeframe: '4h', symbol: 'SOLUSDT', winRate: 71.8, return: 31.4, sharpe: 2.21 },
      { timeframe: '4h', symbol: 'BNBUSDT', winRate: 63.1, return: 15.2, sharpe: 1.48 },
      { timeframe: '4h', symbol: 'XRPUSDT', winRate: 66.9, return: 20.8, sharpe: 1.78 },
      { timeframe: '4h', symbol: 'BTCUSDT-MR', winRate: 72.4, return: 19.3, sharpe: 1.71 },
      { timeframe: '4h', symbol: 'ETHUSDT-MR', winRate: 69.8, return: 16.1, sharpe: 1.55 },
      { timeframe: '4h', symbol: 'SOLUSDT-BR', winRate: 60.2, return: 28.9, sharpe: 2.05 },
      { timeframe: '4h', symbol: 'BTCUSDT-MOM', winRate: 64.7, return: 22.6, sharpe: 1.84 },
      { timeframe: '4h', symbol: 'ETHUSDT-MOM', winRate: 62.3, return: 14.8, sharpe: 1.42 },
    ],
  },
};

// System status
export const SYSTEM_STATUS = {
  engine: { status: 'OFFLINE' as const, version: 'v2.4.1', uptime: '—', lastHeartbeat: '—', note: 'Awaiting VPS deployment' },
  websocket: { status: 'DISCONNECTED' as const, reconnectAttempts: 0, lastConnected: '—' },
  dataFeeds: [
    { name: 'Binance WS', status: 'STANDBY' as const, latency: null, lastMessage: '—' },
    { name: 'Bybit WS', status: 'STANDBY' as const, latency: null, lastMessage: '—' },
    { name: 'OKX WS', status: 'STANDBY' as const, latency: null, lastMessage: '—' },
    { name: 'Hyperliquid WS', status: 'STANDBY' as const, latency: null, lastMessage: '—' },
  ],
  recordingDaemon: { status: 'STANDBY' as const, recordsSaved: 0, diskUsage: '0 MB' },
  telegramBot: { status: 'CONFIGURED' as const, lastAlert: '—', alertsSent: 0 },
};

// Alerts
export const ALERTS = [
  { id: 1, type: 'SIGNAL' as const, symbol: 'BTCUSDT', message: 'ML Score 0.87 — LONG signal detected on 4h timeframe', time: '2026-04-10 12:02:00', sent: true, channel: 'Telegram' },
  { id: 2, type: 'RISK' as const, symbol: null, message: 'Position count at maximum (3/3) — new entries blocked', time: '2026-04-10 11:45:00', sent: true, channel: 'Telegram' },
  { id: 3, type: 'SIGNAL' as const, symbol: 'SOLUSDT', message: 'ML Score 0.91 — Strong LONG signal. Regime: Trending', time: '2026-04-10 11:30:00', sent: true, channel: 'Telegram' },
  { id: 4, type: 'EXECUTION' as const, symbol: 'ETHUSDT', message: 'SHORT position opened at 1680.50 — 15 contracts, 8x leverage', time: '2026-04-09 08:15:00', sent: true, channel: 'Telegram' },
  { id: 5, type: 'REGIME' as const, symbol: 'BTCUSDT', message: 'Regime shift detected: Volatile → Trending (confidence: 92%)', time: '2026-04-08 16:00:00', sent: true, channel: 'Telegram' },
  { id: 6, type: 'RISK' as const, symbol: null, message: 'Daily loss approaching threshold: 3.8% / 5.0%', time: '2026-04-07 14:20:00', sent: true, channel: 'Telegram' },
  { id: 7, type: 'EXECUTION' as const, symbol: 'SOLUSDT', message: 'LONG position opened at 124.30 — 200 contracts, 5x leverage', time: '2026-04-05 02:00:00', sent: true, channel: 'Telegram' },
  { id: 8, type: 'SIGNAL' as const, symbol: 'XRPUSDT', message: 'Funding rate arbitrage opportunity: 17.09% annualized', time: '2026-04-04 20:30:00', sent: true, channel: 'Telegram' },
  { id: 9, type: 'SYSTEM' as const, symbol: null, message: 'Engine v2.4.1 deployed successfully. All systems nominal.', time: '2026-04-03 10:00:00', sent: true, channel: 'Telegram' },
  { id: 10, type: 'EXECUTION' as const, symbol: 'BTCUSDT', message: 'LONG position opened at 82150.00 — 0.5 BTC, 10x leverage', time: '2026-04-02 14:30:00', sent: true, channel: 'Telegram' },
];

// Pricing tiers
export const PRICING_TIERS = [
  {
    name: 'Starter',
    monthlyPrice: 19,
    yearlyPrice: 190,
    description: 'For individual traders getting started with AI-powered signals.',
    features: [
      '5 symbol scanner',
      'Basic ML signals (4h timeframe)',
      'Risk gate monitoring',
      'Email alerts',
      'Basic performance dashboard',
      'Community Discord access',
    ],
    cta: 'Start Free Trial',
    highlighted: false,
  },
  {
    name: 'Pro',
    monthlyPrice: 49,
    yearlyPrice: 490,
    description: 'For serious traders who need the full analytical toolkit.',
    features: [
      'Everything in Starter',
      'All timeframes (1m to 1D)',
      'Regime detection engine',
      'Alpha signal generator',
      'Position sizing calculator',
      'Telegram alerts',
      'Trade journal with analytics',
      'Backtest results access',
      'Priority support',
    ],
    cta: 'Start Free Trial',
    highlighted: true,
    badge: 'Most Popular',
  },
  {
    name: 'Elite',
    monthlyPrice: 99,
    yearlyPrice: 990,
    description: 'For professional traders and fund managers.',
    features: [
      'Everything in Pro',
      'Custom ML model training',
      'API access (REST + WebSocket)',
      'Multi-exchange execution',
      'Advanced risk management',
      'Liquidation cascade detection',
      'Order book imbalance signals',
      'Custom strategy backtesting',
      'Dedicated account manager',
      '1-on-1 onboarding call',
    ],
    cta: 'Start Free Trial',
    highlighted: false,
  },
  {
    name: 'Team',
    monthlyPrice: 299,
    yearlyPrice: null,
    description: 'For crypto funds and trading desks. Custom deployment.',
    features: [
      'Everything in Elite',
      'Multi-user access (up to 10)',
      'Custom model deployment',
      'On-premise option',
      'SLA guarantee (99.9%)',
      'Custom integrations',
      'Dedicated infrastructure',
      'Quarterly strategy review',
      'White-label option',
    ],
    cta: 'Contact Sales',
    highlighted: false,
  },
];

export const PRICING_FAQ = [
  { q: 'Is there a free trial?', a: 'Yes, all plans include a 14-day free trial with full access to plan features. No credit card required to start.' },
  { q: 'Can I change plans later?', a: 'Absolutely. You can upgrade or downgrade at any time. Changes take effect at the start of your next billing cycle.' },
  { q: 'What payment methods do you accept?', a: 'We accept all major credit cards, debit cards, and cryptocurrency payments (BTC, ETH, USDT) through our Stripe integration.' },
  { q: 'Is the annual plan worth it?', a: 'The annual plan saves you approximately 17% compared to monthly billing. It\'s the best value for committed traders.' },
  { q: 'Do you offer refunds?', a: 'We offer a 30-day money-back guarantee on all plans. If you\'re not satisfied, contact support for a full refund.' },
  { q: 'What happens when the engine goes live?', a: 'Currently running with demo data. Once the engine is deployed on VPS, all dashboard data will switch to live feeds automatically.' },
];

// Position sizer calculator defaults
export const POSITION_SIZER_DEFAULTS = {
  accountBalance: 127843.52,
  riskPerTrade: 1.0,
  maxLeverage: 20,
  symbol: 'BTCUSDT' as Symbol,
};

// Format helpers
export function formatUSD(value: number, decimals = 2): string {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: decimals, maximumFractionDigits: decimals }).format(value);
}

export function formatNumber(value: number, decimals = 2): string {
  return new Intl.NumberFormat('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals }).format(value);
}

export function formatCompact(value: number): string {
  if (value >= 1e9) return `$${(value / 1e9).toFixed(2)}B`;
  if (value >= 1e6) return `$${(value / 1e6).toFixed(1)}M`;
  if (value >= 1e3) return `$${(value / 1e3).toFixed(0)}K`;
  return `$${value.toFixed(0)}`;
}

export function formatPct(value: number): string {
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(2)}%`;
}
