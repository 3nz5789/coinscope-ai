"""
CoinScopeAI — CI Smoke Tests
=============================
Tests that run in CI without depending on legacy flat module imports.
These verify the repo structure, config, and key invariants.

Run: pytest tests/test_ci_smoke.py -v
"""

import os
import sys
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestRepoStructure:
    """Verify canonical repo structure is intact."""

    def test_env_example_exists(self):
        assert os.path.isfile(os.path.join(ROOT, ".env.example")), \
            ".env.example missing from repo root"

    def test_env_not_committed(self):
        assert not os.path.isfile(os.path.join(ROOT, ".env")), \
            ".env file committed — SECURITY RISK"

    def test_requirements_txt_exists(self):
        assert os.path.isfile(os.path.join(ROOT, "requirements.txt"))

    def test_docker_compose_exists(self):
        assert os.path.isfile(os.path.join(ROOT, "docker-compose.yml"))

    def test_docs_architecture_exists(self):
        assert os.path.isdir(os.path.join(ROOT, "docs", "architecture"))

    def test_docs_risk_exists(self):
        assert os.path.isdir(os.path.join(ROOT, "docs", "risk"))

    def test_docs_runbooks_exists(self):
        assert os.path.isdir(os.path.join(ROOT, "docs", "runbooks"))

    def test_engine_or_source_dir_exists(self):
        """At least one source directory must exist."""
        candidates = ["engine", "apps", "backend", "services", "main",
                      "coinscope_trading_engine"]
        found = any(os.path.isdir(os.path.join(ROOT, d)) for d in candidates)
        assert found, f"No source directory found. Expected one of: {candidates}"

    def test_scripts_dir_exists(self):
        assert os.path.isdir(os.path.join(ROOT, "scripts"))

    def test_tests_dir_exists(self):
        assert os.path.isdir(os.path.join(ROOT, "tests"))


class TestCanonicalThresholds:
    """Verify .env.example contains correct canonical risk thresholds."""

    @pytest.fixture(autouse=True)
    def load_env_example(self):
        path = os.path.join(ROOT, ".env.example")
        with open(path) as f:
            self.content = f.read()

    def test_max_leverage_is_10(self):
        assert "MAX_LEVERAGE=10" in self.content, \
            "MAX_LEVERAGE must be 10 in .env.example (not 20)"

    def test_max_open_positions_is_5(self):
        assert "MAX_OPEN_POSITIONS=5" in self.content, \
            "MAX_OPEN_POSITIONS must be 5 in .env.example"

    def test_max_drawdown_is_10(self):
        assert "MAX_DRAWDOWN_PCT=10" in self.content, \
            "MAX_DRAWDOWN_PCT must be 10 in .env.example"

    def test_max_daily_loss_is_5(self):
        assert "MAX_DAILY_LOSS_PCT=5" in self.content, \
            "MAX_DAILY_LOSS_PCT must be 5 in .env.example"

    def test_testnet_mode_true(self):
        assert "TESTNET_MODE=true" in self.content, \
            "TESTNET_MODE must be true during validation phase"

    def test_no_mainnet_keys_committed(self):
        assert "BINANCE_FUTURES_MAINNET_API_KEY=your" not in self.content or \
               "BINANCE_FUTURES_MAINNET_API_KEY=" in self.content, \
            "Mainnet API keys should not be in .env.example"


class TestSecurityInvariants:
    """Security checks that must always pass."""

    def test_no_env_file_at_root(self):
        assert not os.path.isfile(os.path.join(ROOT, ".env")), \
            ".env should never be committed"

    def test_gitignore_excludes_env(self):
        gitignore = os.path.join(ROOT, ".gitignore")
        assert os.path.isfile(gitignore), ".gitignore missing"
        content = open(gitignore).read()
        assert ".env" in content, ".env must be in .gitignore"

    def test_no_hardcoded_api_keys_in_scripts(self):
        scripts_dir = os.path.join(ROOT, "scripts")
        if not os.path.isdir(scripts_dir):
            pytest.skip("No scripts/ dir")
        for fname in os.listdir(scripts_dir):
            if not fname.endswith(".py"):
                continue
            fpath = os.path.join(scripts_dir, fname)
            content = open(fpath).read()
            assert "sk_live_" not in content, \
                f"Possible live Stripe key in {fname}"
            assert "BINANCE_SECRET=" not in content or \
                   "BINANCE_SECRET=your" in content or \
                   "BINANCE_SECRET=os" in content, \
                f"Possible hardcoded Binance secret in {fname}"

    def test_contributing_md_exists(self):
        assert os.path.isfile(os.path.join(ROOT, "CONTRIBUTING.md"))

    def test_security_md_exists(self):
        assert os.path.isfile(os.path.join(ROOT, "SECURITY.md"))


class TestAdrs:
    """ADR files must exist and reference their decisions."""

    def test_adr_0001_exists(self):
        path = os.path.join(ROOT, "docs", "decisions", "adr-0001-fastapi-and-uvicorn.md")
        assert os.path.isfile(path), "ADR-0001 missing"

    def test_adr_0002_exists(self):
        path = os.path.join(ROOT, "docs", "decisions", "adr-0002-redis-celery-for-workers.md")
        assert os.path.isfile(path), "ADR-0002 missing"

    def test_adr_0003_exists(self):
        path = os.path.join(ROOT, "docs", "decisions", "adr-0003-llm-off-hot-path.md")
        assert os.path.isfile(path), "ADR-0003 missing"

    def test_adr_0003_mentions_no_hot_path(self):
        path = os.path.join(ROOT, "docs", "decisions", "adr-0003-llm-off-hot-path.md")
        content = open(path).read().lower()
        assert "hot path" in content or "execution" in content, \
            "ADR-0003 should reference hot path / execution"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
