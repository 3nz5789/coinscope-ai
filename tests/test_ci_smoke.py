"""
CoinScopeAI - CI Smoke Tests
Minimal tests against the actual GitHub repo structure.
No assumptions about file contents beyond what's confirmed in git.
"""

import os
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestRepoStructure:

    def test_env_example_exists(self):
        """At least one .env example file must exist"""
        has_env = (
            os.path.isfile(os.path.join(ROOT, ".env.example")) or
            os.path.isfile(os.path.join(ROOT, "coinscope.env.example")) or
            os.path.isfile(os.path.join(ROOT, ".env.template"))
        )
        assert has_env, "No .env example file found at repo root"

    def test_env_not_committed(self):
        assert not os.path.isfile(os.path.join(ROOT, ".env")), \
            ".env committed — SECURITY RISK"

    def test_requirements_txt_exists(self):
        assert os.path.isfile(os.path.join(ROOT, "requirements.txt"))

    def test_docs_dir_exists(self):
        assert os.path.isdir(os.path.join(ROOT, "docs"))

    def test_source_dir_exists(self):
        candidates = ["engine", "apps", "backend", "services", "main",
                      "coinscope_trading_engine", "risk_management"]
        found = [d for d in candidates if os.path.isdir(os.path.join(ROOT, d))]
        assert found, f"No source dir. Checked: {candidates}"

    def test_scripts_dir_exists(self):
        assert os.path.isdir(os.path.join(ROOT, "scripts"))

    def test_tests_dir_exists(self):
        assert os.path.isdir(os.path.join(ROOT, "tests"))

    def test_gitignore_exists(self):
        assert os.path.isfile(os.path.join(ROOT, ".gitignore"))

    def test_gitignore_excludes_env(self):
        gi = os.path.join(ROOT, ".gitignore")
        assert ".env" in open(gi).read()


class TestSecurity:

    def test_no_env_at_root(self):
        assert not os.path.isfile(os.path.join(ROOT, ".env"))

    def test_no_env_production(self):
        assert not os.path.isfile(os.path.join(ROOT, ".env.production"))

    def test_no_env_local(self):
        assert not os.path.isfile(os.path.join(ROOT, ".env.local"))


class TestCanonicalThresholds:
    """Check risk thresholds exist somewhere in the repo"""

    def _find_env_file(self):
        """Find the env example file wherever it is"""
        candidates = [
            ".env.example",
            "coinscope.env.example",
            ".env.template",
            "coinscope_trading_engine/.env.example",
            "coinscope_trading_engine/.env.template",
        ]
        for c in candidates:
            p = os.path.join(ROOT, c)
            if os.path.isfile(p):
                return open(p).read()
        return ""

    def test_max_leverage_canonical(self):
        """MAX_LEVERAGE should be 10 (not 20) somewhere in env files"""
        content = self._find_env_file()
        if not content:
            pytest.skip("No env example file found")
        # Accept 10 or 10.0 but NOT 20
        assert "MAX_LEVERAGE=20" not in content, \
            "Stale MAX_LEVERAGE=20 found — must be 10"

    def test_max_open_positions_canonical(self):
        """MAX_OPEN_POSITIONS should not be 3 (must be 5)"""
        content = self._find_env_file()
        if not content:
            pytest.skip("No env example file found")
        assert "MAX_OPEN_POSITIONS=3" not in content, \
            "Stale MAX_OPEN_POSITIONS=3 found — must be 5"

    def test_testnet_mode(self):
        """Testnet flag should be set"""
        content = self._find_env_file()
        if not content:
            pytest.skip("No env example file found")
        has_testnet = (
            "TESTNET_MODE=true" in content or
            "BINANCE_TESTNET=true" in content or
            "BINANCE_FUTURES_TESTNET" in content
        )
        assert has_testnet, "No testnet configuration found in env example"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
