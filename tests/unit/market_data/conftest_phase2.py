"""
CoinScopeAI Phase 2 — pytest configuration

Adds the project root to sys.path so that imports like
``from services.market_data.models import ...`` work correctly.
"""

import sys
from pathlib import Path

# Ensure project root is on the Python path
sys.path.insert(0, str(Path(__file__).resolve().parent))
