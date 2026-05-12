"""
tests/test_directory_boundaries.py — Validation-Safe vs Experimental Boundary Enforcement
===========================================================================================

During P0 validation, the live trading path must only use code from
validation-safe directories. Experimental directories (models/, signals/backtester.py,
intelligence/hmm_*, validation/) contain ML research, LSTM predictors, and
offline tools that must not be imported by the hot path.

Boundary map
------------

VALIDATION-SAFE (may be imported by the live trading path):
  coinscope_trading_engine/
    risk/               — circuit_breaker, position_sizer, exposure_tracker, correlation_analyzer
    core/               — scoring_fixed, risk_gate, multi_timeframe_filter
    scanner/            — base_scanner, volume/pattern/funding/orderbook/liquidation
    signals/            — confluence_scorer, entry_exit_calculator, indicator_engine, signal_generator
    data/               — binance_rest, cache_manager, data_normalizer
    alerts/             — telegram_notifier, scale_up_manager
    storage/            — trade_journal, decision_journal, historical_klines
    monitoring/         — prometheus_metrics, metrics_exporter
    billing/            — stripe_gateway (read-only during P0)
    utils/              — helpers, logger
    live/               — master_orchestrator, pair_monitor, WS clients, executor
    config.py           — settings singleton
    api.py              — FastAPI app

EXPERIMENTAL (must NOT be imported by the live trading path during P0):
  coinscope_trading_engine/
    models/price_predictor.py   — LSTM price direction model (PyTorch; not in live path)
    signals/backtester.py       — offline backtester (async Binance fetch; not in live path)
    validation/                 — walk-forward validation (offline research)
    intelligence/hmm_*          — HMM regime detector used only as fallback (not P0 primary)

The v3 ML classifier (ml/regime_classifier_v3.py) is loaded optionally in api.py
via a try/except — its absence does not break the engine.

Enforcement rules
-----------------
1. Experimental modules must not import from each other as if they were stable.
2. Experimental modules must not be in sys.modules during a clean engine import.
3. The validation/ directory must not contain any file that writes to Notion, Telegram,
   or Binance (it is read/observe only).
4. The backtester must declare a BacktestConfig that does not override canonical risk thresholds.
5. The price_predictor must not be imported at module level by any hot-path file.

Run:
    pytest tests/test_directory_boundaries.py -v
"""

from __future__ import annotations

import ast
import importlib
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Optional

import pytest

# ---------------------------------------------------------------------------
# Root paths
# ---------------------------------------------------------------------------

REPO_ROOT   = Path(__file__).parent.parent
ENGINE_ROOT = REPO_ROOT / "coinscope_trading_engine"

# ---------------------------------------------------------------------------
# Boundary definitions
# ---------------------------------------------------------------------------

VALIDATION_SAFE_DIRS = {
    "risk",
    "core",
    "scanner",
    "scanners",
    "signals",       # except backtester.py
    "data",
    "alerts",
    "storage",
    "monitoring",
    "billing",
    "utils",
    "live",
}

EXPERIMENTAL_FILES = {
    "models/price_predictor.py",
    "signals/backtester.py",
    "validation/walk_forward_validation.py",
    "intelligence/hmm_regime_detector.py",
    "intelligence/finbert_sentiment_filter.py",
    "intelligence/whale_signal_filter.py",
    "intelligence/funding_rate_filter.py",
}

# Hot-path files that must not have top-level imports of experimental modules
HOT_PATH_FILES = [
    "risk/circuit_breaker.py",
    "risk/position_sizer.py",
    "risk/exposure_tracker.py",
    "risk/correlation_analyzer.py",
    "core/scoring_fixed.py",
    "core/risk_gate.py",
    "core/multi_timeframe_filter.py",
    "signals/confluence_scorer.py",
    "signals/entry_exit_calculator.py",
    "signals/indicator_engine.py",
    "config.py",
]

# Module strings for the experimental imports we're guarding against
EXPERIMENTAL_MODULE_PATTERNS = [
    "price_predictor",
    "backtester",
    "walk_forward_validation",
    "hmm_regime_detector",
    "finbert_sentiment_filter",
    "whale_signal_filter",
    "hmmlearn",
    "torch",
    "tensorflow",
    "sklearn",
    "ccxt",
]

# Canonical risk thresholds that must never be overridden in experimental code
CANONICAL_THRESHOLDS = {
    "MAX_LEVERAGE":          10,
    "MAX_OPEN_POSITIONS":    5,
    "MAX_DRAWDOWN_PCT":      0.10,
    "MAX_DAILY_LOSS_PCT":    0.05,
    "POSITION_HEAT_CAP_PCT": 80,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _engine_file(relative: str) -> Optional[Path]:
    p = ENGINE_ROOT / relative
    return p if p.exists() else None


def _parse_imports(path: Path) -> list[str]:
    """Return all module names imported at the top level of a Python file."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return []

    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
    return imports


def _top_level_imports(path: Path) -> list[str]:
    """Return only module names imported at module scope (not inside functions/try blocks)."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return []

    imports: list[str] = []
    # Only walk direct children of the module (top-level statements)
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
        # try/except blocks at top level — still consider these guarded, not top-level
        # Function/class definitions — skip (their imports are local scope)
    return imports


def _file_source(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


# ===========================================================================
# SECTION 1 — Experimental Directory Structure
# ===========================================================================

class TestExperimentalDirectoryStructure:
    """
    Invariant: every file declared as experimental must exist where expected,
    and no experimental file should silently migrate into a safe directory.
    """

    def test_experimental_files_exist(self):
        """All declared experimental files must exist in the engine."""
        missing = []
        for rel in EXPERIMENTAL_FILES:
            p = ENGINE_ROOT / rel
            if not p.exists():
                missing.append(rel)
        assert not missing, f"Declared experimental files not found: {missing}"

    def test_no_price_predictor_in_safe_dirs(self):
        """price_predictor.py must not appear in any validation-safe directory."""
        for safe_dir in VALIDATION_SAFE_DIRS:
            d = ENGINE_ROOT / safe_dir
            if not d.is_dir():
                continue
            for f in d.rglob("price_predictor.py"):
                pytest.fail(f"price_predictor.py found in safe dir: {f}")

    def test_no_backtester_in_safe_dirs(self):
        """backtester.py must only exist in signals/ — not in risk/, core/, etc."""
        guarded = VALIDATION_SAFE_DIRS - {"signals"}
        for safe_dir in guarded:
            d = ENGINE_ROOT / safe_dir
            if not d.is_dir():
                continue
            for f in d.rglob("backtester.py"):
                pytest.fail(f"backtester.py found in safe dir {safe_dir}: {f}")

    def test_validation_dir_exists_and_is_isolated(self):
        """validation/ must exist and must not contain an __init__ that exports to risk/."""
        val_dir = ENGINE_ROOT / "validation"
        assert val_dir.is_dir(), "validation/ directory is missing"
        init = val_dir / "__init__.py"
        if init.exists():
            source = _file_source(init)
            # __init__.py must not re-export to risk or core namespaces
            assert "from risk" not in source, \
                "validation/__init__.py must not re-export from risk/"
            assert "from core" not in source, \
                "validation/__init__.py must not re-export from core/"

    def test_models_dir_contains_only_known_files(self):
        """models/ should only contain known files — no surprise new models."""
        known = {
            "__init__.py", "price_predictor.py", "regime_detector.py",
            "sentiment_analyzer.py", "anomaly_detector.py",
        }
        models_dir = ENGINE_ROOT / "models"
        if not models_dir.is_dir():
            pytest.skip("models/ not present in repo")
        actual = {f.name for f in models_dir.iterdir()
                  if f.is_file() and not f.name.startswith(".")}
        unknown = actual - known - {"__pycache__"}
        assert not unknown, (
            f"Unknown files in models/ (experimental boundary violation): {unknown}. "
            f"Add them to EXPERIMENTAL_FILES or move to a safe directory."
        )


# ===========================================================================
# SECTION 2 — Hot-Path Files Must Not Top-Level Import Experimental Modules
# ===========================================================================

class TestHotPathImportBoundaries:
    """
    Invariant: hot-path files (risk/, core/, signals/ scorers) must not
    have unconditional top-level imports of experimental modules.
    An import inside a try/except or a function body is acceptable (lazy/optional).
    """

    @pytest.mark.parametrize("hot_file", HOT_PATH_FILES)
    def test_hot_path_file_has_no_experimental_top_level_import(self, hot_file: str):
        path = _engine_file(hot_file)
        if path is None:
            pytest.skip(f"{hot_file} not present in repo")

        top_imports = _top_level_imports(path)
        violations = [
            imp for imp in top_imports
            if any(pat in imp for pat in EXPERIMENTAL_MODULE_PATTERNS)
        ]
        assert not violations, (
            f"{hot_file} has top-level import(s) of experimental modules: {violations}. "
            f"Move these inside a try/except or a function to keep the hot path clean."
        )

    def test_circuit_breaker_has_no_ml_imports(self):
        path = _engine_file("risk/circuit_breaker.py")
        if path is None:
            pytest.skip("circuit_breaker.py not found")
        source = _file_source(path)
        for ml_lib in ["torch", "tensorflow", "sklearn", "hmmlearn", "numpy.random.seed"]:
            assert ml_lib not in source, \
                f"circuit_breaker.py references ML library {ml_lib!r}"

    def test_position_sizer_has_no_ml_imports(self):
        path = _engine_file("risk/position_sizer.py")
        if path is None:
            pytest.skip("position_sizer.py not found")
        source = _file_source(path)
        for ml_lib in ["torch", "tensorflow", "sklearn", "hmmlearn"]:
            assert ml_lib not in source, \
                f"position_sizer.py references ML library {ml_lib!r}"

    def test_risk_gate_has_no_backtester_import(self):
        path = _engine_file("core/risk_gate.py")
        if path is None:
            pytest.skip("core/risk_gate.py not found")
        source = _file_source(path)
        assert "backtester" not in source.lower(), \
            "core/risk_gate.py must not import the backtester"

    def test_confluence_scorer_has_no_price_predictor(self):
        path = _engine_file("signals/confluence_scorer.py")
        if path is None:
            pytest.skip("confluence_scorer.py not found")
        source = _file_source(path)
        assert "price_predictor" not in source.lower(), \
            "confluence_scorer.py must not import the LSTM price predictor"


# ===========================================================================
# SECTION 3 — Experimental Modules Must Not Write to Live Systems
# ===========================================================================

class TestExperimentalModulesReadOnly:
    """
    Invariant: experimental modules (validation/, backtester, price_predictor)
    must not directly call Telegram send, Notion write, or Binance order placement.
    They are read/observe-only tools.
    """

    def test_walk_forward_validator_has_no_telegram_send(self):
        path = _engine_file("validation/walk_forward_validation.py")
        if path is None:
            pytest.skip("walk_forward_validation.py not found")
        source = _file_source(path)
        assert "send_message" not in source, \
            "walk_forward_validation.py must not send Telegram messages"
        assert "TelegramNotifier" not in source, \
            "walk_forward_validation.py must not import TelegramNotifier"

    def test_walk_forward_validator_has_no_order_placement(self):
        path = _engine_file("validation/walk_forward_validation.py")
        if path is None:
            pytest.skip("walk_forward_validation.py not found")
        source = _file_source(path)
        assert "place_order" not in source, \
            "walk_forward_validation.py must not call place_order"
        assert "fapi/v1/order" not in source, \
            "walk_forward_validation.py must not call Binance order endpoint"

    def test_backtester_has_no_telegram_send(self):
        path = _engine_file("signals/backtester.py")
        if path is None:
            pytest.skip("backtester.py not found")
        source = _file_source(path)
        assert "TelegramNotifier" not in source, \
            "backtester.py must not import TelegramNotifier"
        assert "send_message" not in source, \
            "backtester.py must not send Telegram messages"

    def test_backtester_has_no_live_order_placement(self):
        path = _engine_file("signals/backtester.py")
        if path is None:
            pytest.skip("backtester.py not found")
        source = _file_source(path)
        assert "place_order" not in source, \
            "backtester.py must not place real orders"
        assert "fapi/v1/order" not in source, \
            "backtester.py must not reference Binance order endpoint"

    def test_price_predictor_has_no_order_placement(self):
        path = _engine_file("models/price_predictor.py")
        if path is None:
            pytest.skip("price_predictor.py not found")
        source = _file_source(path)
        assert "place_order" not in source, \
            "price_predictor.py must not place orders"
        assert "TelegramNotifier" not in source, \
            "price_predictor.py must not send Telegram alerts"

    def test_validation_dir_has_no_notion_writes(self):
        """No file in validation/ must write to Notion databases."""
        val_dir = ENGINE_ROOT / "validation"
        if not val_dir.is_dir():
            pytest.skip("validation/ not present")
        notion_write_patterns = [
            "pages.create", "databases.query", "notion_create",
            "NOTION_SIGNAL_LOG_DB", "NOTION_TRADE_JOURNAL_DB",
        ]
        for py_file in val_dir.rglob("*.py"):
            source = _file_source(py_file)
            for pat in notion_write_patterns:
                assert pat not in source, (
                    f"{py_file.name} in validation/ contains Notion write pattern {pat!r}. "
                    f"validation/ is read-only — no DB writes permitted."
                )


# ===========================================================================
# SECTION 4 — Canonical Threshold Invariants in Experimental Code
# ===========================================================================

class TestCanonicalThresholdsNotOverriddenByExperimental:
    """
    Invariant: experimental files (backtester, walk-forward validator) must
    not hard-code values that contradict the canonical risk thresholds locked
    in PCC v2 §8. A backtest that silently uses MAX_LEVERAGE=20 would produce
    meaningless results and mislead the operator.
    """

    def test_backtester_default_leverage_not_above_canonical(self):
        path = _engine_file("signals/backtester.py")
        if path is None:
            pytest.skip("backtester.py not found")
        source = _file_source(path)
        # Backtester should not reference leverage > 10 as a default
        bad_patterns = [
            "leverage=20", "leverage = 20",
            "max_leverage=20", "max_leverage = 20",
            "leverage=15", "leverage = 15",
        ]
        for pat in bad_patterns:
            assert pat not in source, (
                f"backtester.py contains {pat!r} — violates MAX_LEVERAGE=10 (PCC v2 §8)"
            )

    def test_walk_forward_validator_risk_params_reasonable(self):
        """WFV thresholds should not encourage reckless sizing."""
        path = _engine_file("validation/walk_forward_validation.py")
        if path is None:
            pytest.skip("walk_forward_validation.py not found")
        source = _file_source(path)
        # Should not hard-code a max_drawdown threshold above 25%
        # (anything larger would pass catastrophically bad strategies)
        assert "mdd > -0.50" not in source, \
            "WFV max_drawdown threshold is too permissive (> 50%)"
        assert "mdd > -0.75" not in source, \
            "WFV max_drawdown threshold is too permissive (> 75%)"

    def test_backtester_config_has_commission(self):
        """BacktestConfig must include commission to produce realistic results."""
        path = _engine_file("signals/backtester.py")
        if path is None:
            pytest.skip("backtester.py not found")
        source = _file_source(path)
        assert "commission_pct" in source, \
            "BacktestConfig must include commission_pct — zero-commission backtests overfit"

    def test_backtester_config_has_slippage(self):
        """BacktestConfig must include slippage."""
        path = _engine_file("signals/backtester.py")
        if path is None:
            pytest.skip("backtester.py not found")
        source = _file_source(path)
        assert "slippage_pct" in source, \
            "BacktestConfig must include slippage_pct — zero-slippage backtests overfit"


# ===========================================================================
# SECTION 5 — API Layer Guards (api.py Imports Experimental Safely)
# ===========================================================================

class TestApiLayerExperimentalGuards:
    """
    Invariant: api.py may import experimental modules only inside try/except
    blocks, never at top level. This ensures that a missing PyTorch or ccxt
    install does not crash the engine on startup.
    """

    def test_api_imports_regime_v3_inside_try_except(self):
        path = _engine_file("api.py")
        if path is None:
            pytest.skip("api.py not found")
        source = _file_source(path)
        # The v3 classifier import must be inside a try block
        assert "try:" in source, "api.py should have try/except blocks"
        # Verify it's not a bare top-level import
        top_imports = _top_level_imports(ENGINE_ROOT / "api.py")
        ml_top = [i for i in top_imports if "regime_classifier" in i or "RegimeClassifierV3" in i]
        assert not ml_top, \
            f"api.py imports ML classifier at top level: {ml_top}. Must be inside try/except."

    def test_api_does_not_top_level_import_price_predictor(self):
        path = _engine_file("api.py")
        if path is None:
            pytest.skip("api.py not found")
        top_imports = _top_level_imports(ENGINE_ROOT / "api.py")
        assert not any("price_predictor" in i for i in top_imports), \
            "api.py imports price_predictor at top level — must be lazy or removed"

    def test_api_does_not_top_level_import_backtester(self):
        path = _engine_file("api.py")
        if path is None:
            pytest.skip("api.py not found")
        top_imports = _top_level_imports(ENGINE_ROOT / "api.py")
        assert not any("backtester" in i for i in top_imports), \
            "api.py imports backtester at top level — must be lazy (inside the endpoint function)"

    def test_api_does_not_top_level_import_torch(self):
        path = _engine_file("api.py")
        if path is None:
            pytest.skip("api.py not found")
        top_imports = _top_level_imports(ENGINE_ROOT / "api.py")
        assert not any("torch" in i for i in top_imports), \
            "api.py imports torch at top level — PyTorch must be optional"

    def test_api_does_not_top_level_import_hmmlearn(self):
        path = _engine_file("api.py")
        if path is None:
            pytest.skip("api.py not found")
        top_imports = _top_level_imports(ENGINE_ROOT / "api.py")
        assert not any("hmmlearn" in i for i in top_imports), \
            "api.py imports hmmlearn at top level — must be inside try/except"


# ===========================================================================
# SECTION 6 — Boundary ADR Compliance Check
# ===========================================================================

class TestBoundaryAdrCompliance:
    """
    Ensure the ADR documenting these boundaries exists and contains
    the required sections. A missing ADR means the boundary is undocumented
    and will be silently violated in the next sprint.
    """

    def test_boundary_adr_exists(self):
        """ADR-0005 for directory boundaries must exist."""
        adr_path = REPO_ROOT / "docs" / "decisions" / "adr-0005-validation-safe-vs-experimental-boundaries.md"
        assert adr_path.exists(), (
            f"ADR-0005 not found at {adr_path}. "
            f"Run: create docs/decisions/adr-0005-validation-safe-vs-experimental-boundaries.md"
        )

    def test_boundary_adr_contains_required_sections(self):
        adr_path = REPO_ROOT / "docs" / "decisions" / "adr-0005-validation-safe-vs-experimental-boundaries.md"
        if not adr_path.exists():
            pytest.skip("ADR-0005 not found — covered by test_boundary_adr_exists")
        content = adr_path.read_text(encoding="utf-8")
        required_sections = [
            "validation-safe", "experimental",
            "price_predictor", "backtester",
            "Consequences", "Decision",
        ]
        for section in required_sections:
            assert section.lower() in content.lower(), \
                f"ADR-0005 is missing required section/term: {section!r}"


# ===========================================================================
# MAIN
# ===========================================================================

if __name__ == "__main__":
    import pytest as _pytest
    _pytest.main([__file__, "-v", "--tb=short"])
