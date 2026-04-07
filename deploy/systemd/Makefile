# ─────────────────────────────────────────────────────────────────────────────
#  CoinScopeAI — systemd Service Management Makefile
# ─────────────────────────────────────────────────────────────────────────────

.PHONY: all install start stop restart status logs uninstall

SERVICES = coinscopeai-engine.service coinscopeai-recorder.service coinscopeai-dashboard.service

all:
	@echo "Usage:"
	@echo "  make install    - Install and enable all services (requires sudo)"
	@echo "  make start      - Start all services"
	@echo "  make stop       - Stop all services"
	@echo "  make restart    - Restart all services"
	@echo "  make status     - Show status of all services"
	@echo "  make logs       - Tail logs for all services"
	@echo "  make uninstall  - Stop, disable, and remove all services (requires sudo)"

install:
	sudo ./install.sh --start

start:
	sudo systemctl start $(SERVICES)

stop:
	sudo systemctl stop $(SERVICES)

restart:
	sudo systemctl restart $(SERVICES)

status:
	@for svc in $(SERVICES); do \
		systemctl status $$svc --no-pager --lines=5 || true; \
		echo "--------------------------------------------------------------------------------"; \
	done

logs:
	sudo journalctl -f -u coinscopeai-engine -u coinscopeai-recorder -u coinscopeai-dashboard

uninstall:
	sudo ./install.sh --uninstall
