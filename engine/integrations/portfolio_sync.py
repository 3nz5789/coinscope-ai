"""
Portfolio Sync Module
Syncs live trading portfolio with Notion Portfolio Tracker
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from integrations.notion_integration import get_notion_integration

logger = logging.getLogger(__name__)

class PortfolioSync:
    """Handles portfolio synchronization with Notion"""
    
    def __init__(self):
        """Initialize portfolio sync"""
        self.notion = get_notion_integration()
        self.last_sync = None
        self.sync_interval = 300  # 5 minutes
        logger.info("✅ Portfolio Sync initialized")
    
    async def sync_holdings(self, holdings: Dict[str, Any]) -> bool:
        """
        Sync current holdings to Notion Portfolio Tracker
        
        Args:
            holdings: {
                'BTC': {'quantity': 0.5, 'avg_buy': 65000, 'current': 67000},
                'ETH': {'quantity': 2.0, 'avg_buy': 3500, 'current': 3800},
                ...
            }
        
        Returns:
            bool: True if synced successfully
        """
        try:
            synced_count = 0
            
            for asset, data in holdings.items():
                portfolio_entry = {
                    'asset': asset,
                    'quantity': data.get('quantity', 0),
                    'avg_buy_price': data.get('avg_buy', 0),
                    'current_price': data.get('current', 0),
                    'value': data.get('quantity', 0) * data.get('current', 0),
                    'performance': ((data.get('current', 0) - data.get('avg_buy', 0)) / data.get('avg_buy', 1)) * 100
                }
                
                success = await self.notion.update_portfolio_tracker(portfolio_entry)
                if success:
                    synced_count += 1
            
            self.last_sync = datetime.now()
            logger.info(f"✅ Portfolio synced: {synced_count}/{len(holdings)} assets")
            return True
        
        except Exception as e:
            logger.error(f"❌ Error syncing portfolio: {e}")
            return False
    
    async def sync_open_positions(self, positions: List[Dict[str, Any]]) -> int:
        """
        Sync open trading positions
        
        Args:
            positions: List of open position data
        
        Returns:
            int: Number of positions synced
        """
        synced_count = 0
        
        for position in positions:
            try:
                portfolio_entry = {
                    'asset': position.get('pair', 'N/A'),
                    'quantity': position.get('quantity', 0),
                    'avg_buy_price': position.get('entry_price', 0),
                    'current_price': position.get('current_price', 0),
                    'value': position.get('position_value', 0),
                    'performance': position.get('unrealized_pnl_pct', 0)
                }
                
                success = await self.notion.update_portfolio_tracker(portfolio_entry)
                if success:
                    synced_count += 1
            
            except Exception as e:
                logger.error(f"❌ Error syncing position: {e}")
        
        logger.info(f"✅ Positions synced: {synced_count}/{len(positions)}")
        return synced_count
    
    async def should_sync(self) -> bool:
        """
        Check if portfolio should be synced based on interval
        
        Returns:
            bool: True if sync interval has passed
        """
        if self.last_sync is None:
            return True
        
        elapsed = (datetime.now() - self.last_sync).total_seconds()
        return elapsed >= self.sync_interval
    
    async def calculate_portfolio_stats(self, holdings: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate portfolio statistics
        
        Args:
            holdings: Current holdings data
        
        Returns:
            Dict with portfolio stats
        """
        total_value = 0
        total_invested = 0
        
        for asset, data in holdings.items():
            quantity = data.get('quantity', 0)
            current = data.get('current', 0)
            avg_buy = data.get('avg_buy', 0)
            
            total_value += quantity * current
            total_invested += quantity * avg_buy
        
        overall_performance = ((total_value - total_invested) / total_invested * 100) if total_invested > 0 else 0
        
        return {
            'total_value': total_value,
            'total_invested': total_invested,
            'overall_performance': overall_performance,
            'asset_count': len(holdings),
            'last_updated': datetime.now().isoformat()
        }


# Singleton instance
_portfolio_sync = None

def get_portfolio_sync() -> PortfolioSync:
    """Get or create portfolio sync singleton"""
    global _portfolio_sync
    if _portfolio_sync is None:
        _portfolio_sync = PortfolioSync()
    return _portfolio_sync
