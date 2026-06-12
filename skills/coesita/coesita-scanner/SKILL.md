---
name: coesita-scanner
description: "Escanea frameworks de agentes (AutoGen, CrewAI, LangGraph, OpenAI Agents SDK, Semantic Kernel, LlamaIndex Workflows, smolagents, ...) y extrae sus características clave (multi-agente, Kanban, memoria persistente, tools, subagentes) en un JSON estructurado que alimenta el benchmark de Coesita."
version: 1.0.0
author: Coesita Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [coesita, benchmark, frameworks, scanning, research]
    related_skills: [coesita-scenario-generator, coesita-tester]
---

# Coesita Scanner — Scanning de Agent Frameworks

Fase 1 del pipeline de benchmark de Coesita: mantener un registro estructurado y
actualizado de los frameworks de agentes existentes y de qué soportan.

## Qué produce

Un JSON en `logs/coesita/benchmark/frameworks.json` con una ficha por framework:

```json
{
  "name": "LangGraph", "slug": "langgraph", "org": "LangChain",
  "repo": "https://github.com/langchain-ai/langgraph", "language": "Python",
  "features": {
    "multi_agent": true, "kanban_board": false, "persistent_memory": true,
    "tool_use": true, "subagents": true, "human_in_loop": true, "streaming": true
  },
  "notes": "...", "source": "web", "scanned_at": "2026-06-12T00:00:00Z"
}
```

El dashboard lo expone en `GET /scanning/frameworks` y lo pinta como tabla
comparativa en `/benchmark`.

## Cómo ejecutar

**Scan rápido (registro semilla curado, sin red):**

```bash
python3 -c "from skills.coesita.framework_scanner import run_scan; import json; print(json.dumps(run_scan(), indent=2, ensure_ascii=False))"
```

**Scan enriquecido con investigación web (el flujo completo de la skill):**

1. Busca en la web el estado actual de cada framework del registro semilla
   (`SEED_FRAMEWORKS` en `skills/coesita/framework_scanner.py`) y de cualquier
   framework nuevo relevante. Fuentes útiles: el README del repo oficial, la
   página de releases, y comparativas recientes.
2. Para cada framework, determina las 7 features de `FEATURE_KEYS`:
   `multi_agent`, `kanban_board`, `persistent_memory`, `tool_use`,
   `subagents`, `human_in_loop`, `streaming`.
3. Construye la lista de fichas (formato de arriba, `source: "web"`) y persiste:

```python
from skills.coesita.framework_scanner import run_scan
extra = [
    {"name": "...", "slug": "...", "org": "...", "repo": "...",
     "language": "...", "features": {"multi_agent": True}, "notes": "..."},
]
run_scan(extra)  # mergea con el semilla (mismo slug → reemplaza) y guarda
```

## Reglas

- **No inventes features.** Si no puedes verificar una capacidad, déjala en
  `false` y anótalo en `notes`.
- Una entrada extra con el mismo `slug` que una semilla **reemplaza** la ficha
  semilla; usa eso para refrescar datos obsoletos.
- Tras el scan, verifica el resultado con `GET /scanning/frameworks` en el
  dashboard (puerto 5050).
