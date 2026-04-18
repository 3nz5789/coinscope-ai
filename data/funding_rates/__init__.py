"""
CoinScopeAI — Funding Rate Ingestion Pipeline

Public API:
    from data.funding_rates import FundingRateDB, FundingRateRecord
    from data.funding_rates import FundingRateCollector
    from data.funding_rates import load_config
"""

from .config import load_config, FundingRateConfig
from .storage import FundingRateDB, FundingRateRecord
from .collector import FundingRateCollector
from .alerts import FundingRateAlertManager

__all__ = [
    "load_config",
    "FundingRateConfig",
    "FundingRateDB",
    "FundingRateRecord",
    "FundingRateCollector",
    "FundingRateAlertManager",
]
