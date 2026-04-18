"""
run_trade.py — CoinScopeAI testnet trading entry point.

Run this script to execute a trade based on a scanner signal.

Usage:
    python run_trade.py                          # uses defaults below
    python run_trade.py ETHUSDT SHORT 9.5        # symbol, direction, score
    python run_trade.py BTCUSDT LONG 11.0 1h     # symbol, direction, score, timeframe

Environment (.env file):
    BINANCE_TESTNET=true        ← must be true for testnet
    BINANCE_API_KEY=...         ← your testnet API key
    BINANCE_API_SECRET=...      ← your testnet secret
    RISK_PCT=1.0                ← % of balance to risk per trade
    LEVERAGE=10                 ← futures leverage
    SL_PCT=1.5                  ← stop-loss % distance from entry
    RR_RATIO=2.0                ← reward:risk ratio (TP = SL × RR)
"""

import sys
import time

from config import load_config, startup_check, trade_params
from client import BinanceFuturesRestClient, BinanceAPIError
from trade_executor import Signal, PositionSizer, TradeExecutor


# ── Default signal (simulates what the scanner outputs) ───────────────────────
# Override via command-line args: python run_trade.py BTCUSDT LONG 10.5
DEFAULT_SIGNAL = Signal(
    symbol    = "BTCUSDT",
    direction = "LONG",
    score     = 10.5,
    timeframe = "15m",
    source    = "scanner",
)


def parse_args() -> Signal:
    """Parse optional CLI args to override the default signal."""
    args = sys.argv[1:]
    if not args:
        return DEFAULT_SIGNAL

    symbol    = args[0].upper() if len(args) > 0 else DEFAULT_SIGNAL.symbol
    direction = args[1].upper() if len(args) > 1 else DEFAULT_SIGNAL.direction
    score     = float(args[2])  if len(args) > 2 else DEFAULT_SIGNAL.score
    timeframe = args[3]         if len(args) > 3 else DEFAULT_SIGNAL.timeframe

    if direction not in ("LONG", "SHORT"):
        print(f"[Error] Direction must be LONG or SHORT, got: {direction}")
        sys.exit(1)

    return Signal(symbol=symbol, direction=direction, score=score, timeframe=timeframe)


def main():
    print("\n" + "═" * 55)
    print("  CoinScopeAI  —  Testnet Trade Executor")
    print("═" * 55)

    # ── 1. Load environment config ─────────────────────────────────────────────
    cfg = load_config()
    startup_check(cfg)     # exits on mainnet if user doesn't confirm

    # ── 2. Parse signal ────────────────────────────────────────────────────────
    signal = parse_args()
    print(f"[Signal] {signal.direction} {signal.symbol}  score={signal.score:+.1f}  tf={signal.timeframe}")

    # Minimum score guard — don't trade weak signals
    MIN_SCORE = 7.0
    if signal.score < MIN_SCORE:
        print(f"\n[Skip] Score {signal.score:.1f} is below minimum threshold {MIN_SCORE}. Not trading.\n")
        sys.exit(0)

    # ── 3. Build client and sync clock ─────────────────────────────────────────
    client = BinanceFuturesRestClient(cfg)
    client.sync_clock()   # corrects -1021 timestamp drift errors

    # ── 4. Build position sizer from env params ────────────────────────────────
    params = trade_params()
    print(
        f"\n[Params] risk={params['risk_pct']}%  lev={params['leverage']}x  "
        f"SL={params['sl_pct']}%  RR={params['rr_ratio']}:1"
    )

    sizer = PositionSizer(
        risk_pct = params["risk_pct"],
        sl_pct   = params["sl_pct"],
        rr_ratio = params["rr_ratio"],
        leverage = params["leverage"],
    )

    # ── 5. Quick sanity-check: is the symbol valid on this environment? ────────
    print(f"\n[Check] Verifying {signal.symbol} is available on testnet…")
    try:
        mark = client.get_mark_price(signal.symbol)
        price = float(mark["markPrice"])
        print(f"[Check] ✅ {signal.symbol} mark price = ${price:,.4f}")
    except BinanceAPIError as e:
        print(f"[Check] ❌ {signal.symbol} not available: {e}")
        print("        Testnet supports major pairs only (BTCUSDT, ETHUSDT, BNBUSDT, etc.)")
        sys.exit(1)

    # ── 6. Execute the trade ───────────────────────────────────────────────────
    print(f"\n[Execute] Placing {signal.direction} trade on {signal.symbol}…\n")
    time.sleep(0.5)   # brief pause so output is readable

    executor = TradeExecutor(client=client, sizer=sizer)
    result   = executor.execute(signal)

    # ── 7. Print confirmation ──────────────────────────────────────────────────
    result.print_confirmation()

    if result.success:
        print("Trade is live on testnet. Monitor at: https://testnet.binancefuture.com")
        print(f"Rate limit status: {client.rate.summary()}\n")
    else:
        print(f"Trade failed: {result.error}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
