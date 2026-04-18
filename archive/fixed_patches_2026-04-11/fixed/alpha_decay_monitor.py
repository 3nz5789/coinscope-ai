"""
Alpha Decay Monitor — Phase 9
Detects when the strategy's edge is degrading in real-time.
Runs daily on closed trades from PostgreSQL.
Alerts before live losses mount.

Reference: https://www.linkedin.com/pulse/alpha-decay-when-launch-new-quant-strategy-genieaitech-njptc
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import logging

logger = logging.getLogger(__name__)


class AlphaDecayMonitor:
    """
    Monitors strategy edge degradation through multiple metrics:
    - Win rate decay (7d vs 30d baseline)
    - Profit factor decline
    - Sharpe ratio erosion
    - Consecutive loss streaks
    - Regime transition failures
    """
    
    DECAY_THRESHOLDS = {
        "win_rate_drop": 0.05,      # Alert if 7d WR drops 5% vs 30d
        "sharpe_drop": 0.3,          # Alert if rolling Sharpe drops 0.3
        "pf_below": 1.2,             # Alert if profit factor < 1.2
        "consec_loss_warn": 4,       # Warn at 4+ consecutive losses
        "regime_transition_fail": 0.15,  # Alert if regime accuracy drops 15%
    }
    
    def __init__(self, trade_journal, telegram_alerts):
        """
        Args:
            trade_journal: TradeJournal instance (PostgreSQL)
            telegram_alerts: TelegramAlertBot instance
        """
        self.journal = trade_journal
        self.alerts = telegram_alerts
        self.baseline_metrics = {}
        self.alert_history = []
    
    async def run_daily_check(self) -> Dict:
        """
        Run full alpha decay check. Called once per day.
        
        Returns:
            Dict with decay signals and recommendations
        """
        
        try:
            # BUG-8 FIX: use the correct synchronous method get_recent_trades(days=30)
            trades_30d = self.journal.get_recent_trades(days=30)
            trades_7d = [t for t in trades_30d if
                        (datetime.utcnow() - datetime.fromisoformat(
                            t["closed_at"] if isinstance(t, dict) else t.closed_at
                        )).days <= 7]
            
            if len(trades_30d) < 20:
                logger.info("⏳ Not enough trades yet for decay analysis")
                return {"status": "insufficient_data"}
            
            # Calculate metrics
            baseline_wr = self._win_rate(trades_30d)
            recent_wr = self._win_rate(trades_7d)
            baseline_sharpe = self._sharpe(trades_30d)
            recent_sharpe = self._sharpe(trades_7d)
            pf_7d = self._profit_factor(trades_7d)
            
            decay_signals = []
            severity = "INFO"
            
            # Win rate decay
            if len(trades_7d) >= 10:
                wr_decay = baseline_wr - recent_wr
                if wr_decay > self.DECAY_THRESHOLDS["win_rate_drop"]:
                    decay_signals.append({
                        'type': 'win_rate_decay',
                        'baseline': baseline_wr,
                        'recent': recent_wr,
                        'decay': wr_decay,
                        'message': f"⚠️ Win rate decay: {recent_wr:.1%} (7d) vs {baseline_wr:.1%} (30d baseline)"
                    })
                    severity = "WARN"
            
            # Profit factor
            if pf_7d < self.DECAY_THRESHOLDS["pf_below"]:
                decay_signals.append({
                    'type': 'low_profit_factor',
                    'value': pf_7d,
                    'threshold': self.DECAY_THRESHOLDS["pf_below"],
                    'message': f"⚠️ Low profit factor: {pf_7d:.2f} (7d) — target > 1.2"
                })
                severity = "WARN"
            
            # Sharpe decay
            if len(trades_7d) >= 10:
                sharpe_decay = baseline_sharpe - recent_sharpe
                if sharpe_decay > self.DECAY_THRESHOLDS["sharpe_drop"]:
                    decay_signals.append({
                        'type': 'sharpe_decay',
                        'baseline': baseline_sharpe,
                        'recent': recent_sharpe,
                        'decay': sharpe_decay,
                        'message': f"⚠️ Sharpe decay: {recent_sharpe:.2f} (7d) vs {baseline_sharpe:.2f} (30d)"
                    })
                    severity = "WARN"
            
            # Consecutive losses
            consec_losses = self._consecutive_losses(trades_7d)
            if consec_losses >= self.DECAY_THRESHOLDS["consec_loss_warn"]:
                decay_signals.append({
                    'type': 'consecutive_losses',
                    'value': consec_losses,
                    'message': f"⚠️ {consec_losses} consecutive losses — check regime"
                })
                severity = "CRITICAL" if consec_losses >= 6 else "WARN"
            
            # Compile report
            report = {
                'timestamp': datetime.utcnow().isoformat(),
                'severity': severity,
                'metrics': {
                    'trades_30d': len(trades_30d),
                    'trades_7d': len(trades_7d),
                    'win_rate_30d': baseline_wr,
                    'win_rate_7d': recent_wr,
                    'sharpe_30d': baseline_sharpe,
                    'sharpe_7d': recent_sharpe,
                    'profit_factor_7d': pf_7d,
                    'consecutive_losses': consec_losses,
                },
                'decay_signals': decay_signals,
                'recommendations': self._get_recommendations(decay_signals)
            }
            
            # Send alerts
            if decay_signals:
                await self._send_decay_alert(report)
            else:
                await self._send_health_check(report)
            
            self.alert_history.append(report)
            return report
        
        except Exception as e:
            logger.error(f"❌ Alpha decay check failed: {e}")
            return {"status": "error", "error": str(e)}
    
    @staticmethod
    def _pnl(t) -> float:
        """Extract PnL from a trade — works with both dicts and dataclass objects.
        TradeJournal.get_recent_trades() returns dicts with key 'pnl_pct'.
        (BUG dict/object mismatch fix: t.realized_pnl_pct → dict-safe accessor)
        """
        if isinstance(t, dict):
            return t.get("pnl_pct", t.get("realized_pnl_pct", 0.0))
        return getattr(t, "pnl_pct", getattr(t, "realized_pnl_pct", 0.0))

    def _win_rate(self, trades: List) -> float:
        """Calculate win rate from trade list"""
        if not trades:
            return 0.0
        wins = sum(1 for t in trades if self._pnl(t) > 0)
        return wins / len(trades)

    def _profit_factor(self, trades: List) -> float:
        """Calculate profit factor (gross wins / gross losses)"""
        if not trades:
            return 0.0

        wins = sum(self._pnl(t) for t in trades if self._pnl(t) > 0)
        losses = abs(sum(self._pnl(t) for t in trades if self._pnl(t) < 0))

        return wins / losses if losses > 0 else 0.0

    def _sharpe(self, trades: List) -> float:
        """Calculate annualized Sharpe ratio"""
        if len(trades) < 5:
            return 0.0

        pnls = np.array([self._pnl(t) for t in trades])
        mean_pnl = np.mean(pnls)
        std_pnl = np.std(pnls)

        if std_pnl == 0:
            return 0.0

        # BUG-14 FIX: annualize correctly for 4 trades per day
        trades_per_day = 4
        daily_sharpe = mean_pnl / std_pnl
        return daily_sharpe * np.sqrt(365 * trades_per_day)

    def _consecutive_losses(self, trades: List) -> int:
        """Count current consecutive losses"""
        if not trades:
            return 0

        count = 0
        for t in reversed(trades):
            if self._pnl(t) < 0:
                count += 1
            else:
                break

        return count
    
    def _get_recommendations(self, decay_signals: List) -> List[str]:
        """Generate actionable recommendations based on decay signals"""
        recommendations = []
        
        for signal in decay_signals:
            if signal['type'] == 'win_rate_decay':
                recommendations.append(
                    "🔧 Review multi-timeframe filter — may be too strict"
                )
                recommendations.append(
                    "🔧 Check regime detector — might be misclassifying"
                )
            
            elif signal['type'] == 'low_profit_factor':
                recommendations.append(
                    "🔧 Increase stop-loss distance (currently 2.06%)"
                )
                recommendations.append(
                    "🔧 Review take-profit levels — may be too tight"
                )
            
            elif signal['type'] == 'sharpe_decay':
                recommendations.append(
                    "🔧 Retrain HMM regime detector on latest data"
                )
                recommendations.append(
                    "🔧 Check for regime drift — market conditions may have changed"
                )
            
            elif signal['type'] == 'consecutive_losses':
                recommendations.append(
                    "🔧 Reduce position size temporarily (Kelly fraction 0.25 → 0.15)"
                )
                recommendations.append(
                    "🔧 Review recent market regime — may be in transition"
                )
        
        return list(set(recommendations))  # Deduplicate
    
    async def _send_decay_alert(self, report: Dict):
        """Send critical decay alert to Telegram"""
        msg = "🔴 *ALPHA DECAY DETECTED*\n\n"
        
        for signal in report['decay_signals']:
            msg += f"• {signal['message']}\n"
        
        msg += f"\n*Metrics:*\n"
        msg += f"• Win Rate (7d): {report['metrics']['win_rate_7d']:.1%}\n"
        msg += f"• Sharpe (7d): {report['metrics']['sharpe_7d']:.2f}\n"
        msg += f"• Profit Factor: {report['metrics']['profit_factor_7d']:.2f}\n"
        
        msg += f"\n*Recommendations:*\n"
        for rec in report['recommendations'][:3]:  # Top 3 recommendations
            msg += f"• {rec}\n"
        
        msg += f"\n_Action: Review and consider retraining HMM_"
        
        # BUG-6 FIX: use existing TelegramAlerts methods (synchronous, no await)
        self.alerts.send_critical(msg)
    
    async def _send_health_check(self, report: Dict):
        """Send health check message to Telegram"""
        msg = f"""
✅ *Alpha Health Check*

• Trades (7d): {report['metrics']['trades_7d']}
• Win Rate: {report['metrics']['win_rate_7d']:.1%}
• Sharpe: {report['metrics']['sharpe_7d']:.2f}
• Profit Factor: {report['metrics']['profit_factor_7d']:.2f}

_All metrics within normal ranges_
"""
        # BUG-6 FIX: use existing TelegramAlerts.send_heartbeat (synchronous, no await)
        self.alerts.send_heartbeat(report['metrics'])
    
    def get_alert_history(self, days: int = 7) -> List[Dict]:
        """Get alert history for the past N days"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        return [
            a for a in self.alert_history
            if datetime.fromisoformat(a['timestamp']) > cutoff
        ]


# Example usage
async def example():
    from trade_journal import TradeJournal
    from telegram_alerts import TelegramAlertBot
    
    journal = TradeJournal()
    await journal.connect()
    
    alerts = TelegramAlertBot()
    
    monitor = AlphaDecayMonitor(journal, alerts)
    report = await monitor.run_daily_check()
    
    print(f"Alpha Decay Report: {report}")
    
    await journal.disconnect()


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO)
    asyncio.run(example())
