"""
HMM Regime Detector with Ensemble Voting

3-state Hidden Markov Model for market regime classification:
- Bull: positive returns, low volatility
- Bear: negative returns, high volatility
- Chop: sideways, high volatility

Ensemble combines HMM + Random Forest for robust predictions.
"""

import numpy as np
from hmmlearn.hmm import GaussianHMM
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings("ignore")


class HMMRegimeDetector:
    """Hidden Markov Model for regime detection"""
    
    def __init__(self, n_regimes=3):
        self.n_regimes = n_regimes
        self.model = GaussianHMM(
            n_components=n_regimes,
            covariance_type="full",
            n_iter=1000,
            random_state=42
        )
        self.scaler = StandardScaler()
        self.fitted = False
        self.regime_map = {}  # maps HMM state → bull/bear/chop

    def fit(self, returns: np.ndarray, volatility: np.ndarray):
        """Fit HMM on returns and volatility"""
        min_len = min(len(returns), len(volatility))
        X = np.column_stack([returns[-min_len:], volatility[-min_len:]])
        X_scaled = self.scaler.fit_transform(X)
        self.model.fit(X_scaled)
        self.fitted = True
        self._label_regimes(returns[-min_len:], volatility[-min_len:])

    def _label_regimes(self, returns, volatility):
        """Label HMM states by return characteristics"""
        X = self.scaler.transform(np.column_stack([returns, volatility]))
        states = self.model.predict(X)
        
        # Label each state by mean return
        means = {}
        for s in range(self.n_regimes):
            mask = states == s
            means[s] = returns[mask].mean() if mask.sum() > 0 else 0
        
        sorted_states = sorted(means, key=means.get)
        self.regime_map = {
            sorted_states[0]: "bear",
            sorted_states[1]: "chop",
            sorted_states[2]: "bull"
        }

    def predict(self, returns: np.ndarray, volatility: np.ndarray) -> dict:
        """Predict current regime"""
        if not self.fitted:
            return {"regime": "chop", "confidence": 0.5}
        
        min_len = min(len(returns), len(volatility))
        X = self.scaler.transform(
            np.column_stack([returns[-min_len:], volatility[-min_len:]])
        )
        probs = self.model.predict_proba(X)
        last_probs = probs[-1]
        state = np.argmax(last_probs)
        regime = self.regime_map.get(state, "chop")
        confidence = float(last_probs[state])
        
        return {"regime": regime, "confidence": round(confidence, 3)}


class EnsembleRegimeDetector:
    """HMM + Random Forest ensemble for robust regime detection"""

    def __init__(self):
        self.hmm = HMMRegimeDetector(n_regimes=3)
        self.rf = RandomForestClassifier(
            n_estimators=100, random_state=42, n_jobs=-1
        )
        self.rf_fitted = False

    def fit(self, returns: np.ndarray, volatility: np.ndarray):
        """Fit both HMM and Random Forest"""
        # Fit HMM
        self.hmm.fit(returns, volatility)

        # Build RF features from rolling windows
        features, labels = self._build_features(returns, volatility)
        if len(features) > 50:
            self.rf.fit(features, labels)
            self.rf_fitted = True

    def _build_features(self, returns, volatility):
        """Build features for Random Forest"""
        features, labels = [], []
        window = 20
        
        for i in range(window, len(returns)):
            r_window = returns[i-window:i]
            v_window = volatility[i-window:i] if len(volatility) >= i else np.zeros(window)
            
            feat = [
                r_window.mean(),
                r_window.std(),
                r_window[-5:].mean(),   # short-term momentum
                v_window.mean(),
                v_window[-5:].mean(),
                np.sum(r_window > 0) / window,  # % positive days
            ]
            features.append(feat)
            
            # Label using HMM prediction on this window
            hmm_result = self.hmm.predict(r_window, v_window[:len(r_window)])
            labels.append(hmm_result["regime"])
        
        return np.array(features), np.array(labels)

    def predict_regime(self, returns: np.ndarray, volatility: np.ndarray) -> dict:
        """Predict regime using ensemble voting"""
        hmm_result = self.hmm.predict(returns, volatility)

        if not self.rf_fitted or len(returns) < 20:
            return hmm_result

        # RF prediction
        r_w = returns[-20:]
        v_w = volatility[-20:] if len(volatility) >= 20 else np.zeros(20)
        feat = np.array([[
            r_w.mean(), r_w.std(), r_w[-5:].mean(),
            v_w.mean(), v_w[-5:].mean(),
            np.sum(r_w > 0) / 20
        ]])
        
        rf_regime = self.rf.predict(feat)[0]
        rf_probs  = self.rf.predict_proba(feat)[0]
        rf_conf   = float(rf_probs.max())

        # Ensemble vote
        if hmm_result["regime"] == rf_regime:
            return {
                "regime": rf_regime,
                "confidence": round((hmm_result["confidence"] + rf_conf) / 2, 3)
            }
        else:
            # Disagreement — use higher confidence
            if hmm_result["confidence"] >= rf_conf:
                return {
                    "regime": hmm_result["regime"],
                    "confidence": round(hmm_result["confidence"] * 0.8, 3)
                }
            else:
                return {
                    "regime": rf_regime,
                    "confidence": round(rf_conf * 0.8, 3)
                }

    def cross_val_accuracy(self, returns, volatility) -> float:
        """Quick cross-validation accuracy estimate"""
        from sklearn.model_selection import cross_val_score
        features, labels = self._build_features(returns, volatility)
        if len(features) < 50:
            return 0.0
        scores = cross_val_score(self.rf, features, labels, cv=3)
        return float(scores.mean())
