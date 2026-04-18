"""
price_predictor.py — LSTM Price Direction Predictor
====================================================
Lightweight LSTM model that predicts next-bar price direction
(UP / DOWN / NEUTRAL) from a rolling window of OHLCV + indicator features.

Architecture
------------
  Input:  sequence_len × n_features  (default 30 × 8)
  Layers: LSTM(64) → Dropout(0.2) → Linear(32) → Linear(3)
  Output: softmax probabilities for [DOWN, NEUTRAL, UP]

Features (per timestep)
-----------------------
  [0] log_return
  [1] high_low_range / close
  [2] volume_normalised   (z-score over window)
  [3] rsi_normalised      (RSI / 100)
  [4] ema_9 / close - 1   (EMA proximity)
  [5] ema_21 / close - 1
  [6] bb_pct_b            (Bollinger %B)
  [7] atr / close         (ATR % of price)

Training
--------
  The model is trained online using recent backtested candles.
  Labels are generated from next-bar close: UP if +0.1%, DOWN if -0.1%,
  NEUTRAL otherwise.

  Only the last `max_train_samples` bars are used to keep training fast.
  Training is triggered automatically if the model hasn't been fitted
  or if `retrain_every` predictions have elapsed.

Usage
-----
    predictor = PricePredictor()
    predictor.train(candles)
    result = predictor.predict(candles)
    print(result.direction, result.confidence)
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np

from data.data_normalizer import Candle
from utils.logger import get_logger

logger = get_logger(__name__)

SEQUENCE_LEN      = 30
N_FEATURES        = 8
HIDDEN_SIZE       = 64
N_CLASSES         = 3     # DOWN, NEUTRAL, UP
DROPOUT           = 0.2
EPOCHS            = 20
BATCH_SIZE        = 32
LEARNING_RATE     = 1e-3
MAX_TRAIN_SAMPLES = 500
RETRAIN_EVERY     = 50    # re-train after this many predictions
UP_THRESHOLD      = 0.001
DOWN_THRESHOLD    = -0.001


class PriceDirection(str, Enum):
    DOWN    = "DOWN"
    NEUTRAL = "NEUTRAL"
    UP      = "UP"


@dataclass
class PredictionResult:
    direction:  PriceDirection
    confidence: float
    probs:      list[float]    # [DOWN, NEUTRAL, UP]
    trained_on: int            # samples used in last training

    def __repr__(self) -> str:
        return (
            f"<PredictionResult {self.direction.value} "
            f"conf={self.confidence:.2f}>"
        )


class PricePredictor:
    """
    LSTM-based price direction predictor.

    Parameters
    ----------
    sequence_len     : Lookback window length (timesteps).
    retrain_every    : Re-train after this many predict() calls.
    max_train_samples: Maximum samples used for training.
    """

    def __init__(
        self,
        sequence_len:      int = SEQUENCE_LEN,
        retrain_every:     int = RETRAIN_EVERY,
        max_train_samples: int = MAX_TRAIN_SAMPLES,
    ) -> None:
        self._seq_len         = sequence_len
        self._retrain_every   = retrain_every
        self._max_samples     = max_train_samples
        self._model           = None
        self._trained_on      = 0
        self._predict_count   = 0
        self._scaler_mean: Optional[np.ndarray] = None
        self._scaler_std:  Optional[np.ndarray] = None

    # ── Public API ───────────────────────────────────────────────────────

    def train(self, candles: list[Candle]) -> bool:
        """
        Train the LSTM on recent candle data.

        Returns True on success, False if insufficient data or PyTorch
        is unavailable.
        """
        try:
            import torch
            import torch.nn as nn
        except ImportError:
            logger.warning("PyTorch not installed — PricePredictor unavailable.")
            return False

        X, y = self._build_dataset(candles)
        if X is None or len(X) < BATCH_SIZE:
            logger.warning("Insufficient data for PricePredictor training.")
            return False

        # Fit scaler
        self._scaler_mean = X.mean(axis=(0, 1))
        self._scaler_std  = X.std(axis=(0, 1)) + 1e-8
        X_scaled = (X - self._scaler_mean) / self._scaler_std

        # Build model
        self._model = _LSTMModel(N_FEATURES, HIDDEN_SIZE, N_CLASSES, DROPOUT)
        optimizer   = torch.optim.Adam(self._model.parameters(), lr=LEARNING_RATE)
        criterion   = nn.CrossEntropyLoss()

        X_t = torch.tensor(X_scaled, dtype=torch.float32)
        y_t = torch.tensor(y, dtype=torch.long)

        self._model.train()
        for epoch in range(EPOCHS):
            perm   = torch.randperm(len(X_t))
            X_shuf = X_t[perm]
            y_shuf = y_t[perm]
            total_loss = 0.0
            for i in range(0, len(X_shuf), BATCH_SIZE):
                xb = X_shuf[i: i + BATCH_SIZE]
                yb = y_shuf[i: i + BATCH_SIZE]
                optimizer.zero_grad()
                out  = self._model(xb)
                loss = criterion(out, yb)
                loss.backward()
                optimizer.step()
                total_loss += loss.item()

        self._trained_on = len(X)
        logger.info(
            "PricePredictor trained on %d samples (%d epochs).",
            len(X), EPOCHS,
        )
        return True

    def predict(self, candles: list[Candle]) -> Optional[PredictionResult]:
        """
        Predict price direction for the next bar.

        Auto-retrains if retrain_every predictions have elapsed.
        Returns None if model not available.
        """
        self._predict_count += 1
        if self._model is None or (self._predict_count % self._retrain_every == 0):
            self.train(candles)

        if self._model is None:
            return None

        features = self._extract_features(candles[-(self._seq_len + 1):])
        if features is None:
            return None

        try:
            import torch
            X = (features - self._scaler_mean) / self._scaler_std
            X_t = torch.tensor(X[np.newaxis], dtype=torch.float32)
            self._model.eval()
            with torch.no_grad():
                logits = self._model(X_t)
                probs  = torch.softmax(logits, dim=-1).squeeze().tolist()

            pred_idx  = int(np.argmax(probs))
            directions = [PriceDirection.DOWN, PriceDirection.NEUTRAL, PriceDirection.UP]

            return PredictionResult(
                direction  = directions[pred_idx],
                confidence = round(float(probs[pred_idx]), 4),
                probs      = [round(p, 4) for p in probs],
                trained_on = self._trained_on,
            )
        except Exception as exc:
            logger.warning("PricePredictor.predict error: %s", exc)
            return None

    # ── Dataset builders ─────────────────────────────────────────────────

    def _build_dataset(
        self, candles: list[Candle]
    ) -> tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        n   = min(len(candles), self._max_samples + self._seq_len + 1)
        sub = candles[-n:]
        if len(sub) < self._seq_len + 2:
            return None, None

        X_list, y_list = [], []
        closes = np.array([c.close for c in sub], dtype=float)

        for i in range(self._seq_len, len(sub) - 1):
            window   = sub[i - self._seq_len: i]
            features = self._extract_features(window)
            if features is None:
                continue

            # Label: direction of next bar
            ret = (closes[i + 1] - closes[i]) / closes[i]
            if ret > UP_THRESHOLD:
                label = 2   # UP
            elif ret < DOWN_THRESHOLD:
                label = 0   # DOWN
            else:
                label = 1   # NEUTRAL

            X_list.append(features)
            y_list.append(label)

        if not X_list:
            return None, None

        return np.array(X_list), np.array(y_list)

    def _extract_features(self, candles: list[Candle]) -> Optional[np.ndarray]:
        if len(candles) < self._seq_len:
            return None

        closes  = np.array([c.close  for c in candles], dtype=float)
        highs   = np.array([c.high   for c in candles], dtype=float)
        lows    = np.array([c.low    for c in candles], dtype=float)
        volumes = np.array([c.volume for c in candles], dtype=float)

        n = len(candles)
        features = np.zeros((n, N_FEATURES))

        # Log returns
        with np.errstate(divide="ignore", invalid="ignore"):
            log_ret = np.diff(np.log(np.where(closes > 0, closes, 1e-10)))
        features[1:, 0] = log_ret

        # HL range / close
        features[:, 1] = (highs - lows) / np.where(closes > 0, closes, 1)

        # Volume z-score
        vol_mean = np.mean(volumes) if volumes.mean() > 0 else 1.0
        vol_std  = np.std(volumes) + 1e-8
        features[:, 2] = (volumes - vol_mean) / vol_std

        # RSI / 100
        rsi = _fast_rsi_seq(closes)
        features[:, 3] = rsi / 100

        # EMA proximity
        ema9  = _ema(closes, 9)
        ema21 = _ema(closes, 21)
        features[:, 4] = ema9  / np.where(closes > 0, closes, 1) - 1
        features[:, 5] = ema21 / np.where(closes > 0, closes, 1) - 1

        # BB %B
        sma20  = np.convolve(closes, np.ones(20) / 20, mode="same")
        std20  = np.array([closes[max(0, i-19):i+1].std() for i in range(n)])
        bb_up  = sma20 + 2 * std20
        bb_lo  = sma20 - 2 * std20
        bb_range = np.where((bb_up - bb_lo) > 0, bb_up - bb_lo, 1)
        features[:, 6] = (closes - bb_lo) / bb_range

        # ATR % of close
        tr = np.maximum(
            highs - lows,
            np.maximum(
                np.abs(highs - np.roll(closes, 1)),
                np.abs(lows  - np.roll(closes, 1)),
            )
        )
        atr = np.convolve(tr, np.ones(14) / 14, mode="same")
        features[:, 7] = atr / np.where(closes > 0, closes, 1)

        return np.nan_to_num(features, nan=0.0, posinf=0.0, neginf=0.0)


# ---------------------------------------------------------------------------
# PyTorch model definition (imported lazily)
# ---------------------------------------------------------------------------

def _build_lstm_model_class():
    try:
        import torch.nn as nn

        class _LSTMModel(nn.Module):
            def __init__(self, n_features, hidden_size, n_classes, dropout):
                super().__init__()
                self.lstm    = nn.LSTM(n_features, hidden_size, batch_first=True)
                self.dropout = nn.Dropout(dropout)
                self.fc1     = nn.Linear(hidden_size, 32)
                self.fc2     = nn.Linear(32, n_classes)
                self.relu    = nn.ReLU()

            def forward(self, x):
                out, _ = self.lstm(x)
                out    = self.dropout(out[:, -1, :])
                out    = self.relu(self.fc1(out))
                return self.fc2(out)

        return _LSTMModel
    except ImportError:
        return None


_LSTMModel = _build_lstm_model_class()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ema(values: np.ndarray, period: int) -> np.ndarray:
    alpha  = 2 / (period + 1)
    result = np.empty_like(values)
    result[0] = values[0]
    for i in range(1, len(values)):
        result[i] = alpha * values[i] + (1 - alpha) * result[i - 1]
    return result


def _fast_rsi_seq(closes: np.ndarray, period: int = 14) -> np.ndarray:
    rsi = np.full(len(closes), 50.0)
    if len(closes) < period + 1:
        return rsi
    deltas = np.diff(closes)
    gains  = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    ag = np.mean(gains[:period])
    al = np.mean(losses[:period])
    for i in range(period, len(deltas)):
        ag = (ag * (period - 1) + gains[i])  / period
        al = (al * (period - 1) + losses[i]) / period
        rs = ag / al if al > 0 else 100.0
        rsi[i + 1] = 100 - 100 / (1 + rs)
    return rsi
