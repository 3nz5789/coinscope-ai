-- COI-101 — 12-month 1h OHLCV reference store for HMM regime retrain.
-- Source: GET https://fapi.binance.com/fapi/v1/klines (Binance USD-M Futures public).
-- Idempotent: re-running yields the same schema; loader uses ON CONFLICT DO NOTHING.

CREATE TABLE IF NOT EXISTS ohlcv_1h (
    symbol     TEXT          NOT NULL,
    open_time  TIMESTAMPTZ   NOT NULL,
    open       NUMERIC(20,8) NOT NULL,
    high       NUMERIC(20,8) NOT NULL,
    low        NUMERIC(20,8) NOT NULL,
    close      NUMERIC(20,8) NOT NULL,
    volume     NUMERIC(28,8) NOT NULL,
    trades     INTEGER       NOT NULL,
    PRIMARY KEY (symbol, open_time)
);

CREATE INDEX IF NOT EXISTS ohlcv_1h_symbol_time_idx
    ON ohlcv_1h (symbol, open_time DESC);
