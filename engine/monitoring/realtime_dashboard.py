"""
Real-Time Trading Dashboard

Displays live trading status, performance metrics, and alerts.
"""

import os
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
import logging


from engine.integrations.trade_journal import TradeJournal
from engine.core.pair_monitor import PairMonitor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Dashboard")


class RealtimeDashboard:
    """Real-time trading dashboard"""
    
    def __init__(self, journal_path: str = "trades.json"):
        self.journal = TradeJournal(journal_path)
        self.pair_monitor = PairMonitor()
        self.start_time = datetime.now()
        self.last_update = None
    
    def get_trades(self, hours: int = 24) -> list:
        """Get trades from last N hours"""
        cutoff = datetime.now() - timedelta(hours=hours)
        all_trades = self.journal.get_all_trades()
        
        recent = []
        for trade in all_trades:
            try:
                trade_time = datetime.fromisoformat(trade.get('timestamp', ''))
                if trade_time > cutoff:
                    recent.append(trade)
            except:
                pass
        
        return recent
    
    def calculate_metrics(self, trades: list) -> dict:
        """Calculate performance metrics"""
        if not trades:
            return {
                'total_trades': 0,
                'wins': 0,
                'losses': 0,
                'win_rate': 0.0,
                'total_pnl': 0.0,
                'avg_win': 0.0,
                'avg_loss': 0.0,
                'sharpe': 0.0,
                'max_dd': 0.0,
            }
        
        wins = sum(1 for t in trades if t.get('pnl', 0) > 0)
        losses = sum(1 for t in trades if t.get('pnl', 0) < 0)
        total_pnl = sum(t.get('pnl', 0) for t in trades)
        
        win_pnls = [t.get('pnl', 0) for t in trades if t.get('pnl', 0) > 0]
        loss_pnls = [t.get('pnl', 0) for t in trades if t.get('pnl', 0) < 0]
        
        avg_win = sum(win_pnls) / len(win_pnls) if win_pnls else 0
        avg_loss = abs(sum(loss_pnls) / len(loss_pnls)) if loss_pnls else 0
        
        # Calculate Sharpe ratio
        pnls = [t.get('pnl', 0) for t in trades]
        if len(pnls) > 1:
            import numpy as np
            returns = np.array(pnls)
            sharpe = np.mean(returns) / (np.std(returns) + 1e-6) * np.sqrt(252)
        else:
            sharpe = 0.0
        
        # Calculate max drawdown
        cumulative = 0
        peak = 0
        max_dd = 0
        for pnl in pnls:
            cumulative += pnl
            if cumulative > peak:
                peak = cumulative
            dd = peak - cumulative
            if dd > max_dd:
                max_dd = dd
        
        return {
            'total_trades': len(trades),
            'wins': wins,
            'losses': losses,
            'win_rate': wins / len(trades) if trades else 0.0,
            'total_pnl': total_pnl,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'sharpe': sharpe,
            'max_dd': max_dd,
        }
    
    def get_pair_stats(self, trades: list) -> dict:
        """Get per-pair statistics"""
        pair_trades = {}
        
        for trade in trades:
            pair = trade.get('symbol', 'UNKNOWN')
            if pair not in pair_trades:
                pair_trades[pair] = []
            pair_trades[pair].append(trade)
        
        pair_stats = {}
        for pair, pair_list in pair_trades.items():
            metrics = self.calculate_metrics(pair_list)
            pair_stats[pair] = metrics
        
        return pair_stats
    
    def get_alerts(self, trades: list, metrics: dict) -> list:
        """Generate alerts based on metrics"""
        alerts = []
        
        # Win rate alert
        if metrics['win_rate'] < 0.35 and metrics['total_trades'] >= 20:
            alerts.append({
                'level': 'WARNING',
                'message': f"Low win rate: {metrics['win_rate']:.1%} (target: 36%+)"
            })
        
        # Winning streak alert
        if len(trades) >= 30:
            recent_30 = trades[-30:]
            recent_wins = sum(1 for t in recent_30 if t.get('pnl', 0) > 0)
            if recent_wins / 30 > 0.60:
                alerts.append({
                    'level': 'CRITICAL',
                    'message': f"Anomaly: {recent_wins}/30 wins (>60% = data leakage?)"
                })
        
        # Drawdown alert
        if metrics['max_dd'] > 750:  # 15% of 5000 USDT
            alerts.append({
                'level': 'CRITICAL',
                'message': f"Max drawdown: {metrics['max_dd']:.0f} USDT (limit: 750)"
            })
        
        # Sharpe alert
        if metrics['sharpe'] < 0.4 and metrics['total_trades'] >= 20:
            alerts.append({
                'level': 'WARNING',
                'message': f"Low Sharpe ratio: {metrics['sharpe']:.2f} (target: 0.5+)"
            })
        
        return alerts
    
    def print_dashboard(self):
        """Print real-time dashboard"""
        trades_24h = self.get_trades(hours=24)
        trades_7d = self.get_trades(hours=168)
        
        metrics_24h = self.calculate_metrics(trades_24h)
        metrics_7d = self.calculate_metrics(trades_7d)
        
        pair_stats = self.get_pair_stats(trades_7d)
        alerts = self.get_alerts(trades_7d, metrics_7d)
        
        # Clear screen
        os.system('clear' if os.name == 'posix' else 'cls')
        
        # Header
        print("\n" + "=" * 70)
        print(" CoinScopeAI - Real-Time Trading Dashboard")
        print("=" * 70)
        print(f" Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(" Testnet Mode | Binance Futures")
        print("=" * 70)
        
        # Alerts
        if alerts:
            print("\n🚨 ALERTS:")
            for alert in alerts:
                icon = "🔴" if alert['level'] == 'CRITICAL' else "🟡"
                print(f"  {icon} [{alert['level']}] {alert['message']}")
        
        # 24h Performance
        print("\n📊 24-Hour Performance:")
        print(f"  Trades: {metrics_24h['total_trades']}")
        print(f"  Win Rate: {metrics_24h['win_rate']:.1%} ({metrics_24h['wins']}W/{metrics_24h['losses']}L)")
        print(f"  P&L: {metrics_24h['total_pnl']:+.2f} USDT")
        print(f"  Avg Win: {metrics_24h['avg_win']:.2f} | Avg Loss: {metrics_24h['avg_loss']:.2f}")
        
        # 7d Performance
        print("\n📈 7-Day Performance:")
        print(f"  Trades: {metrics_7d['total_trades']}")
        print(f"  Win Rate: {metrics_7d['win_rate']:.1%} ({metrics_7d['wins']}W/{metrics_7d['losses']}L)")
        print(f"  P&L: {metrics_7d['total_pnl']:+.2f} USDT")
        print(f"  Sharpe Ratio: {metrics_7d['sharpe']:.2f}")
        print(f"  Max Drawdown: {metrics_7d['max_dd']:.2f} USDT")
        
        # Pair Performance
        print("\n🎯 Pair Performance (7d):")
        print("  " + "-" * 60)
        print(f"  {'Pair':<12} {'Trades':<8} {'Win%':<8} {'P&L':<12} {'Sharpe':<8}")
        print("  " + "-" * 60)
        
        for pair in sorted(pair_stats.keys()):
            stats = pair_stats[pair]
            print(f"  {pair:<12} {stats['total_trades']:<8} "
                  f"{stats['win_rate']:<7.1%} {stats['total_pnl']:<11.2f} "
                  f"{stats['sharpe']:<8.2f}")
        
        print("  " + "-" * 60)
        
        # Risk Metrics
        print("\n⚠️  Risk Metrics:")
        print(f"  Account Balance: 5,000 USDT (starting)")
        print(f"  Current P&L: {metrics_7d['total_pnl']:+.2f} USDT")
        print(f"  Max Drawdown: {metrics_7d['max_dd']:.2f} / 750 USDT (15%)")
        print(f"  Drawdown %: {(metrics_7d['max_dd'] / 5000):.1%}")
        
        # Status
        status_color = "🟢" if not alerts else ("🔴" if any(a['level'] == 'CRITICAL' for a in alerts) else "🟡")
        print(f"\n{status_color} System Status: {'RUNNING' if metrics_7d['total_trades'] > 0 else 'IDLE'}")
        
        print("\n" + "=" * 70)
        print(" Press Ctrl+C to exit | Refreshing every 5 seconds...")
        print("=" * 70 + "\n")


def main():
    """Main dashboard loop"""
    dashboard = RealtimeDashboard()
    
    try:
        while True:
            dashboard.print_dashboard()
            time.sleep(5)
    except KeyboardInterrupt:
        print("\n✅ Dashboard closed")


if __name__ == "__main__":
    main()
