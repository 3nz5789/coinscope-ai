"""
ML Model Store — wing_models
==============================
Logs model training runs, parameter changes, and performance snapshots.
Filed into ``wing_models`` with rooms: training-runs, param-changes, snapshots.

Hall strategy:
  - training-runs → hall_events    (timestamped training run events)
  - param-changes → hall_decisions (hyperparameter change decisions)
  - snapshots     → hall_facts     (verified performance snapshot data)
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..base_store import PalaceStore


class MLModelStore(PalaceStore):
    _wing = "wing_models"
    _default_room = "training-runs"
    _default_hall = "hall_events"

    def log_training_run(
        self,
        model_name: str,
        symbol: str,
        timeframe: str,
        params: Dict[str, Any],
        metrics: Dict[str, float],
        reasoning: str = "",
        extra: Optional[Dict[str, Any]] = None,
        event_id: str = "",
    ) -> str:
        now = datetime.now(timezone.utc)
        params_str = ", ".join(f"{k}={v}" for k, v in params.items())
        metrics_str = ", ".join(f"{k}={v}" for k, v in metrics.items())
        text = (
            f"[{now:%Y-%m-%d %H:%M UTC}] Training: {model_name} "
            f"on {symbol}/{timeframe}\n"
            f"Parameters: {params_str}\n"
            f"Metrics: {metrics_str}"
        )
        if reasoning:
            text += f"\nReasoning: {reasoning}"

        meta: Dict[str, Any] = {
            "event_type": "training_run",
            "model_name": model_name,
            "symbol": symbol,
            "timeframe": timeframe,
        }
        for k, v in params.items():
            if isinstance(v, (str, int, float, bool)):
                meta[f"param_{k}"] = v
        for k, v in metrics.items():
            if isinstance(v, (str, int, float, bool)):
                meta[f"metric_{k}"] = v
        if extra:
            for k, v in extra.items():
                if isinstance(v, (str, int, float, bool)):
                    meta[k] = v

        return self.file_drawer(
            content=text, room="training-runs", hall="hall_events",
            metadata=meta, event_id=event_id,
        )

    def log_param_change(
        self,
        model_name: str,
        param_name: str,
        old_value: Any,
        new_value: Any,
        reasoning: str = "",
        event_id: str = "",
    ) -> str:
        now = datetime.now(timezone.utc)
        text = (
            f"[{now:%Y-%m-%d %H:%M UTC}] Param change: {model_name} "
            f"| {param_name}: {old_value} → {new_value}"
        )
        if reasoning:
            text += f"\nReasoning: {reasoning}"

        meta: Dict[str, Any] = {
            "event_type": "param_change",
            "model_name": model_name,
            "param_name": param_name,
            "old_value": str(old_value),
            "new_value": str(new_value),
        }
        return self.file_drawer(
            content=text, room="param-changes", hall="hall_decisions",
            metadata=meta, event_id=event_id,
        )

    def log_performance_snapshot(
        self,
        model_name: str,
        symbol: str,
        metrics: Dict[str, float],
        context: str = "",
        event_id: str = "",
    ) -> str:
        now = datetime.now(timezone.utc)
        metrics_str = ", ".join(f"{k}={v}" for k, v in metrics.items())
        text = (
            f"[{now:%Y-%m-%d %H:%M UTC}] Snapshot: {model_name} "
            f"on {symbol} | {metrics_str}"
        )
        if context:
            text += f"\nContext: {context}"

        meta: Dict[str, Any] = {
            "event_type": "performance_snapshot",
            "model_name": model_name,
            "symbol": symbol,
        }
        for k, v in metrics.items():
            if isinstance(v, (str, int, float, bool)):
                meta[f"metric_{k}"] = v

        return self.file_drawer(
            content=text, room="snapshots", hall="hall_facts",
            metadata=meta, event_id=event_id,
        )

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def by_model(self, model_name: str, n: int = 20) -> List[Dict]:
        return self.get_drawers(
            where={"$and": [{"wing": self._wing}, {"model_name": model_name}]}, limit=n
        )

    def training_runs(self, symbol: str = "", n: int = 20) -> List[Dict]:
        if symbol:
            where = {"$and": [{"wing": self._wing}, {"room": "training-runs"}, {"symbol": symbol}]}
        else:
            where = {"$and": [{"wing": self._wing}, {"room": "training-runs"}]}
        return self.get_drawers(where=where, limit=n)
