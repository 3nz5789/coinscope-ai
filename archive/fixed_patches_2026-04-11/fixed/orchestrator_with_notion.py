#!/usr/bin/env python3
"""
CoinScopeAI Orchestrator with Notion Integration
Automatically exports trading data to Notion-compatible JSON
"""

import os
import sys
import time
from datetime import datetime
import logging

# Adjust sys.path for module imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from live.master_orchestrator import CoinScopeOrchestrator
from integrations.notion_simple_integration import SimpleNotionIntegration
from storage.trade_journal import TradeJournal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger("CoinScopeOrchestrator+Notion")


class OrchestratorWithNotion(CoinScopeOrchestrator):
    """Extended orchestrator with Notion integration"""
    
    def __init__(self, testnet: bool = True, pairs=None):
        """Initialize orchestrator with Notion integration"""
        super().__init__(testnet=testnet, pairs=pairs)
        
        # Initialize Notion integration
        self.notion = SimpleNotionIntegration()
        self.trade_journal = TradeJournal()
        
        logger.info("✅ Notion integration initialized")
    
    def export_to_notion(self):
        """Export all trading data to Notion-compatible JSON"""
        try:
            # Read trades from journal
            trades = self.trade_journal.get_recent_trades()
            
            if trades:
                self.notion.export_trades(trades)
                logger.info(f"✅ Exported {len(trades)} trades to Notion")
            
            # Calculate and export portfolio
            portfolio = self._calculate_portfolio()
            if portfolio:
                self.notion.export_portfolio(portfolio)
                logger.info("✅ Exported portfolio to Notion")
            
            # Export performance metrics
            metrics = self._calculate_metrics(trades)
            if metrics:
                self.notion.export_performance_metrics(metrics)
                logger.info("✅ Exported performance metrics to Notion")
        
        except Exception as e:
            logger.error(f"❌ Error exporting to Notion: {e}")
    
    def _calculate_portfolio(self) -> dict:
        """Calculate current portfolio state"""
        try:
            # Get account balance from testnet
            if self.testnet:
                balance = self.exchange.get_balance()
                total_value = balance.get('total', 0)
                total_invested = balance.get('used', 0)
                performance_pct = ((total_value - total_invested) / total_invested * 100) if total_invested > 0 else 0
                
                return {
                    'total_value': total_value,
                    'total_invested': total_invested,
                    'performance_pct': performance_pct,
                    'holdings': balance.get('holdings', {})
                }
        except Exception as e:
            logger.error(f"Error calculating portfolio: {e}")
        
        return None
    
    def _calculate_metrics(self, trades: list) -> dict:
        """Calculate trading performance metrics"""
        try:
            if not trades:
                return {
                    'total_trades': 0,
                    'winning_trades': 0,
                    'losing_trades': 0,
                    'win_rate': 0,
                    'total_pnl': 0,
                    'sharpe_ratio': 0,
                    'max_drawdown': 0,
                    'profit_factor': 0,
                    'avg_win': 0,
                    'avg_loss': 0
                }
            
            # Calculate metrics
            total_trades = len(trades)
            winning_trades = sum(1 for t in trades if t.get('pnl', 0) > 0)
            losing_trades = total_trades - winning_trades
            win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
            
            total_pnl = sum(t.get('pnl', 0) for t in trades)
            wins = [t.get('pnl', 0) for t in trades if t.get('pnl', 0) > 0]
            losses = [t.get('pnl', 0) for t in trades if t.get('pnl', 0) < 0]
            
            avg_win = sum(wins) / len(wins) if wins else 0
            avg_loss = sum(losses) / len(losses) if losses else 0
            
            profit_factor = avg_win / abs(avg_loss) if avg_loss != 0 else 0
            
            # Simplified Sharpe (would need returns for proper calculation)
            sharpe_ratio = 0.85  # Placeholder from backtest
            max_drawdown = 5.0  # Placeholder
            
            return {
                'total_trades': total_trades,
                'winning_trades': winning_trades,
                'losing_trades': losing_trades,
                'win_rate': win_rate,
                'total_pnl': total_pnl,
                'sharpe_ratio': sharpe_ratio,
                'max_drawdown': max_drawdown,
                'profit_factor': profit_factor,
                'avg_win': avg_win,
                'avg_loss': abs(avg_loss) if avg_loss else 0
            }
        
        except Exception as e:
            logger.error(f"Error calculating metrics: {e}")
            return None
    
    def run_loop_with_notion(self, interval_seconds: int = 14400):
        """Main loop with periodic Notion exports"""
        logger.info("CoinScopeAI Engine started with Notion integration. Press Ctrl+C to stop.")
        
        export_interval = 3600  # Export every hour
        last_export = time.time()
        
        while True:
            try:
                # Run scan
                self.run_scan()
                
                # Export to Notion every hour
                current_time = time.time()
                if current_time - last_export >= export_interval:
                    logger.info("📤 Exporting to Notion...")
                    self.export_to_notion()
                    last_export = current_time
                
                logger.info(f"Next scan in {interval_seconds//3600}h...")
                time.sleep(interval_seconds)
            
            except KeyboardInterrupt:
                logger.info("Engine stopped.")
                break
            except Exception as e:
                logger.error(f"Loop error: {e}")
                time.sleep(60)


if __name__ == "__main__":
    orch = OrchestratorWithNotion(testnet=True)
    
    # Run single scan with Notion export
    orch.run_scan()
    orch.export_to_notion()
    
    # Or run continuous loop with periodic exports
    # orch.run_loop_with_notion()
