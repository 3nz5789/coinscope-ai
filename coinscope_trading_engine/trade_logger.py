"""
Trade Auto-Logger Module
Automatically logs executed trades to Notion Trading Journal
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from integrations.notion_integration import get_notion_integration

logger = logging.getLogger(__name__)

class TradeLogger:
    """Handles automatic trade logging to Notion"""
    
    def __init__(self):
        """Initialize trade logger"""
        self.notion = get_notion_integration()
        self.pending_trades = {}
        logger.info("✅ Trade Logger initialized")
    
    async def log_trade_execution(self, trade_data: Dict[str, Any]) -> bool:
        """
        Log a trade execution to Notion
        
        Args:
            trade_data: Trade information from orchestrator
        
        Returns:
            bool: True if logged successfully
        """
        try:
            # Format trade for Notion
            formatted_trade = {
                'pair': trade_data.get('pair'),
                'entry_price': trade_data.get('entry_price'),
                'exit_price': trade_data.get('exit_price'),
                'quantity': trade_data.get('quantity'),
                'strategy': trade_data.get('strategy', 'CoinScopeAI MTF'),
                'pnl': trade_data.get('pnl', 0),
                'pnl_pct': trade_data.get('pnl_pct', 0),
                'entry_time': trade_data.get('entry_time', datetime.now()),
                'exit_time': trade_data.get('exit_time', datetime.now()),
                'notes': trade_data.get('notes', '')
            }
            
            # Log to Notion
            success = await self.notion.log_trade_to_journal(formatted_trade)
            
            if success:
                logger.info(f"✅ Trade logged: {formatted_trade['pair']} {formatted_trade['pnl_pct']:+.2f}%")
            else:
                logger.warning(f"⚠️ Failed to log trade to Notion: {formatted_trade['pair']}")
            
            return success
        
        except Exception as e:
            logger.error(f"❌ Error logging trade: {e}")
            return False
    
    async def log_batch_trades(self, trades: list) -> int:
        """
        Log multiple trades in batch
        
        Args:
            trades: List of trade data dictionaries
        
        Returns:
            int: Number of trades successfully logged
        """
        logged_count = 0
        
        for trade in trades:
            if await self.log_trade_execution(trade):
                logged_count += 1
        
        logger.info(f"✅ Batch logged: {logged_count}/{len(trades)} trades")
        return logged_count
    
    async def track_open_trade(self, trade_id: str, trade_data: Dict[str, Any]):
        """
        Track an open trade (not yet closed)
        
        Args:
            trade_id: Unique trade identifier
            trade_data: Trade information
        """
        self.pending_trades[trade_id] = {
            'data': trade_data,
            'opened_at': datetime.now()
        }
        logger.info(f"📊 Tracking open trade: {trade_id}")
    
    async def close_tracked_trade(self, trade_id: str, exit_data: Dict[str, Any]) -> bool:
        """
        Close and log a tracked trade
        
        Args:
            trade_id: Unique trade identifier
            exit_data: Exit information
        
        Returns:
            bool: True if logged successfully
        """
        if trade_id not in self.pending_trades:
            logger.warning(f"⚠️ Trade not tracked: {trade_id}")
            return False
        
        trade_info = self.pending_trades[trade_id]
        
        # Merge entry and exit data
        complete_trade = {
            **trade_info['data'],
            **exit_data,
            'entry_time': trade_info['opened_at']
        }
        
        # Log to Notion
        success = await self.log_trade_execution(complete_trade)
        
        if success:
            del self.pending_trades[trade_id]
        
        return success


# Singleton instance
_trade_logger = None

def get_trade_logger() -> TradeLogger:
    """Get or create trade logger singleton"""
    global _trade_logger
    if _trade_logger is None:
        _trade_logger = TradeLogger()
    return _trade_logger
