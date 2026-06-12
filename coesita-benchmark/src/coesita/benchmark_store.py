# benchmark_store.py
# Persistencia del pipeline de benchmark de Coesita (Fases 1-4).
#
# Todos los artefactos viven bajo <COESITA_LOG_DIR>/benchmark/ :
#   frameworks.json  ← resultado del scanning de frameworks (Fase 1)
#   scenarios.json   ← escenarios de estrés generados (Fase 2)
#   results.json     ← último run del benchmark (Fase 3)
#   history.jsonl    ← histórico de runs, una línea por run (Fase 4)
#
# COESITA_LOG_DIR se resuelve en cada llamada (no al importar) para que
# los tests y el dashboard puedan redirigirlo con la variable de entorno.

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path


def data_dir() -> Path:
    """Directorio base de datos de Coesita (COESITA_LOG_DIR o ~/.coesita)."""
    return Path(os.environ.get("COESITA_LOG_DIR", str(Path.home() / ".coesita")))


def benchmark_dir() -> Path:
    """Directorio de artefactos del benchmark (se crea si no existe)."""
    d = data_dir() / "benchmark"
    d.mkdir(parents=True, exist_ok=True)
    return d


def frameworks_path() -> Path:
    return benchmark_dir() / "frameworks.json"


def scenarios_path() -> Path:
    return benchmark_dir() / "scenarios.json"


def results_path() -> Path:
    return benchmark_dir() / "results.json"


def history_path() -> Path:
    return benchmark_dir() / "history.jsonl"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def save_json(path: Path, data: dict | list) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(path)
    return path


def load_json(path: Path, default=None):
    if not path.exists():
        return default
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def append_history(entry: dict) -> Path:
    """Añade un resumen de run al histórico (JSONL, una línea por run)."""
    path = history_path()
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return path


def load_history(limit: int = 50) -> list[dict]:
    """Últimos `limit` runs del histórico, del más antiguo al más reciente."""
    path = history_path()
    if not path.exists():
        return []
    entries: list[dict] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries[-limit:]
