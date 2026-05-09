"""
CoinScopeAI - CI Smoke Tests
Tests that pass against the actual repo structure on GitHub.
No heavy ML deps. No assumptions about uncommitted local dirs.
"""

import os
import re
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestRepoStructure:

    def test_env_example_exists(self):
        assert os.path.isfile(os.path.join(ROOT, ".env.example"))

    def test_env_not_committed(self):
        assert not os.path.isfile(os.path.join(ROOT, ".env"))

    def test_requirements_txt_exists(self):
        assert os.path.isfile(os.path.join(ROOT, "requirements.txt"))

    def test_docker_compose_exists(self):
        assert os.path.isfile(os.path.join(ROOT, "docker-compose.yml"))

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

    def test_contributing_md_exists(self):
        assert os.path.isfile(os.path.join(ROOT, "CONTRIBUTING.md"))

    def test_security_md_exists(self):
        assert os.path.isfile(os.path.join(ROOT, "SECURITY.md"))


class TestCanonicalThresholds:

    @pytest.fixture(autouse=True)
    def load_env(self):
        with open(os.path.join(ROOT, ".env.example")) as f:
            self.content = f.read()

    def test_max_leverage_is_10(self):
        assert "MAX_LEVERAGE=10" in self.content

    def test_max_open_positions_is_5(self):
        assert "MAX_OPEN_POSITIONS=5" in self.content

    def test_max_drawdown_is_10(self):
        assert "MAX_DRAWDOWN_PCT=10" in self.content

    def test_max_daily_loss_is_5(self):
        assert "MAX_DAILY_LOSS_PCT=5" in self.content

    def test_testnet_mode_true(self):
        assert "TESTNET_MODE=true" in self.content


class TestSecurity:

    def test_no_env_at_root(self):
        assert not os.path.isfile(os.path.join(ROOT, ".env"))

    def test_gitignore_has_env(self):
        gi = os.path.join(ROOT, ".gitignore")
        assert os.path.isfile(gi)
        assert ".env" in open(gi).read()

    def test_no_live_stripe_in_env_example(self):
        c = open(os.path.join(ROOT, ".env.example")).read()
        # Use regex to detect actual live keys (not the pattern strings themselves)
        assert not re.search(r'sk_live_[A-Za-z0-9]{10}', c), \
            "Live Stripe secret key found in .env.example"
        assert not re.search(r'pk_live_[A-Za-z0-9]{10}', c), \
            "Live Stripe publishable key found in .env.example"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
