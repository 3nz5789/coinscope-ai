"""
HMM Auto-Retraining Scheduler — Phase 9
Retrains HMM regime detector every Sunday at 00:00 UTC
on the last 90 days of real data. Saves versioned model to S3.
Rolls back if new model accuracy < old model.

Reference: https://www.quantifiedstrategies.com/algorithmic-trading-strategies/
"""

import asyncio
import ccxt
import pickle
import logging
from datetime import datetime, timedelta
from typing import Optional
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class WeeklyRetrainer:
    """
    Retrains HMM regime detector on a rolling 90-day window.
    
    Process:
    1. Every Sunday at 00:00 UTC
    2. Fetch last 90 days of real OHLCV data
    3. Train new HMM model
    4. Validate accuracy (must be > 75%)
    5. If valid, save to S3 with version tag
    6. Promote to live if better than current model
    7. Alert via Telegram
    """
    
    LOOKBACK_DAYS = 90
    MIN_ACCURACY = 0.75
    PAIRS = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
    RETRAIN_DAY = 6  # Sunday (0=Monday, 6=Sunday)
    RETRAIN_HOUR = 0  # 00:00 UTC
    
    def __init__(self, storage_manager, telegram_alerts, hmm_detector):
        """
        Args:
            storage_manager: S3StorageManager instance
            telegram_alerts: TelegramAlertBot instance
            hmm_detector: EnsembleRegimeDetector instance (current model)
        """
        self.storage = storage_manager
        self.alerts = telegram_alerts
        self.current_model = hmm_detector
        self.exchange = ccxt.binance({"enableRateLimit": True})
        self.model_history = []
    
    async def start_scheduler(self):
        """Start the weekly retraining scheduler"""
        logger.info("🔄 HMM retraining scheduler started")
        
        while True:
            now = datetime.utcnow()
            
            # Check if it's Sunday at 00:00 UTC
            if now.weekday() == self.RETRAIN_DAY and now.hour == self.RETRAIN_HOUR:
                logger.info("🔄 Starting weekly HMM retraining...")
                await self.retrain()
                
                # Sleep for 1 hour to avoid duplicate runs
                await asyncio.sleep(3600)
            
            # Check every minute
            await asyncio.sleep(60)
    
    async def retrain(self) -> bool:
        """
        Execute full retraining cycle.
        
        Returns:
            True if retraining successful and model promoted, False otherwise
        """
        
        try:
            # BUG-7 FIX: use existing TelegramAlerts.send_info (synchronous, no await)
            self.alerts.send_info("🔄 HMM Retraining started — fetching last 90 days of data")
            logger.info("📊 Fetching last 90 days of data...")
            
            # Fetch data for all pairs
            all_returns = []
            all_vol = []
            
            for pair in self.PAIRS:
                try:
                    # Fetch 4-hour candles
                    ohlcv = self.exchange.fetch_ohlcv(
                        pair,
                        "4h",
                        limit=self.LOOKBACK_DAYS * 6  # ~6 candles per day
                    )
                    
                    df = pd.DataFrame(
                        ohlcv,
                        columns=["ts", "open", "high", "low", "close", "volume"]
                    )
                    
                    # Calculate returns and volatility
                    rets = df["close"].pct_change().dropna().values
                    vol = pd.Series(rets).rolling(20).std().dropna().values
                    
                    # Align lengths
                    min_len = min(len(rets), len(vol))
                    all_returns.extend(rets[-min_len:])
                    all_vol.extend(vol[-min_len:])
                    
                    logger.info(f"✅ Fetched {len(rets)} returns for {pair}")
                
                except Exception as e:
                    logger.error(f"❌ Failed to fetch {pair}: {e}")
                    continue
            
            if len(all_returns) < 100:
                logger.error("❌ Insufficient data for retraining")
                # BUG-7 FIX: use send_critical instead of non-existent alert_error
                self.alerts.send_critical("HMM Retraining Failed: Insufficient data collected")
                return False
            
            returns = np.array(all_returns)
            vols = np.array(all_vol)
            
            logger.info(f"📊 Training new HMM model on {len(returns)} samples...")
            
            # Train new model
            from hmm_regime_detector import EnsembleRegimeDetector
            new_model = EnsembleRegimeDetector()
            new_model.fit(returns, vols)
            
            # Validate accuracy
            accuracy = new_model.cross_val_accuracy(returns, vols)
            logger.info(f"📊 New model accuracy: {accuracy:.1%}")
            
            if accuracy < self.MIN_ACCURACY:
                logger.error(
                    f"❌ New model accuracy {accuracy:.1%} < "
                    f"minimum {self.MIN_ACCURACY:.1%}"
                )
                # BUG-7 FIX: use send_critical
                self.alerts.send_critical(
                    f"HMM Retraining Failed: accuracy {accuracy:.1%} below "
                    f"minimum {self.MIN_ACCURACY:.1%}. Keeping current model."
                )
                return False
            
            # Save versioned model to S3
            version = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            model_bytes = pickle.dumps(new_model)
            
            try:
                model_key = f"models/hmm_v{version}.pkl"
                await self.storage.save_model(model_bytes, model_key)
                logger.info(f"💾 Saved model to S3: {model_key}")
            except Exception as e:
                logger.error(f"❌ Failed to save model to S3: {e}")
                return False
            
            # Compare with current model
            current_accuracy = self.current_model.cross_val_accuracy(returns, vols)
            improvement = accuracy - current_accuracy
            
            logger.info(
                f"📊 Current model accuracy: {current_accuracy:.1%}, "
                f"Improvement: {improvement:+.1%}"
            )
            
            # Promote if better
            if accuracy > current_accuracy:
                self.current_model = new_model
                logger.info(f"🚀 Promoted new model (improvement: {improvement:+.1%})")
                
                # BUG-7 FIX: use send_info instead of non-existent alert_scale_up
                self.alerts.send_info(
                    f"🚀 HMM Model promoted to v{version} "
                    f"(accuracy: {accuracy:.1%}, improvement: {improvement:+.1%})"
                )
            else:
                logger.info(
                    f"⏭ Keeping current model "
                    f"(new: {accuracy:.1%}, current: {current_accuracy:.1%})"
                )
                # BUG-7 FIX: use send_info to report no promotion
                self.alerts.send_info(
                    f"⏭ HMM Retraining: keeping current model "
                    f"(new: {accuracy:.1%}, current: {current_accuracy:.1%})"
                )
            
            # Record in history
            self.model_history.append({
                'timestamp': datetime.utcnow().isoformat(),
                'version': version,
                'accuracy': accuracy,
                'current_accuracy': current_accuracy,
                'improvement': improvement,
                'promoted': accuracy > current_accuracy,
            })
            
            logger.info("✅ Weekly HMM retraining completed")
            return True
        
        except Exception as e:
            logger.error(f"❌ Retraining failed: {e}")
            # BUG-7 FIX: use send_critical
            self.alerts.send_critical(f"HMM Retraining Error: {e}")
            return False
    
    async def manual_retrain(self) -> bool:
        """
        Manually trigger retraining (useful for testing or emergency updates).
        
        Returns:
            True if successful
        """
        logger.info("🔄 Manual HMM retraining triggered")
        return await self.retrain()
    
    def get_model_history(self, limit: int = 10) -> list:
        """Get recent model retraining history"""
        return self.model_history[-limit:]
    
    def get_current_model_version(self) -> dict:
        """Get current model version info"""
        if not self.model_history:
            return {
                'version': 'initial',
                'accuracy': 0.0,
                'promoted_at': None,
            }
        
        return self.model_history[-1]


# Standalone scheduler runner
async def run_scheduler(storage_manager, alerts, hmm_detector):
    """
    Run the retraining scheduler in background.
    
    Usage:
        asyncio.create_task(run_scheduler(storage, alerts, hmm))
    """
    retrainer = WeeklyRetrainer(storage_manager, alerts, hmm_detector)
    await retrainer.start_scheduler()


# Example usage
async def example():
    from s3_storage import SignalStorageManager
    from telegram_alerts import TelegramAlertBot
    from hmm_regime_detector import EnsembleRegimeDetector
    
    storage = SignalStorageManager()
    alerts = TelegramAlertBot()
    hmm = EnsembleRegimeDetector()
    
    retrainer = WeeklyRetrainer(storage, alerts, hmm)
    
    # Manual retrain
    success = await retrainer.manual_retrain()
    print(f"Retraining {'succeeded' if success else 'failed'}")
    
    # Get history
    history = retrainer.get_model_history()
    print(f"Model history: {history}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(example())
