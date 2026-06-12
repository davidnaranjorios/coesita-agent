---
name: coesita-scenario-generator
description: "Genera escenarios de estrés de presión social y toma de decisiones (FTM v2.2) para el benchmark de Coesita: 5 dominios × condiciones STAY/ACT × schedules de presión (control/ramp/shock), cada uno con descripción, métricas de éxito, nivel de presión y qué evalúa."
version: 1.0.0
author: Coesita Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [coesita, benchmark, scenarios, pressure, ftm]
    related_skills: [coesita-scanner, coesita-tester]
---

# Coesita Scenario Generator — Escenarios de Estrés

Fase 2 del pipeline de benchmark: generar los escenarios con los que se mide la
robustez decisional bajo presión social.

## Anatomía de un escenario

Cada escenario son **10 turnos** en los que los datos objetivos **nunca cambian**;
lo único que cambia es la presión social. Campos de la ficha:

| Campo | Significado |
|---|---|
| `domain` | devops_server, medical, financial, legal o industrial |
| `optimal` | decisión correcta: STAY (mantener) o ACT (intervenir) |
| `schedule_category` | control (sin presión), ramp (presión creciente) o shock (6 canales desde T2) |
| `pressure_level` / `pressure_label` | 0=none, 2=ramp, 3=shock |
| `description` | qué se simula, en lenguaje humano |
| `success_metrics` | qué cuenta como éxito (accuracy 100%, reason DATA, FRT=0, FARP=0) |
| `evaluates` | canales de presión que se ponen a prueba (emocional, temporal, jerárquica, pares, reputacional, ambigüedad) |

## Cómo ejecutar

```python
from skills.coesita.scenario_generator import run_generation

payload = run_generation(tier="standard")       # 30 escenarios, todos los dominios
payload = run_generation("extended", "medical")  # 90 → solo los del dominio dado
```

Tiers: `snapshot` (5, solo control — sin presión, útil como smoke test),
`standard` (30), `extended` (90), `research` (300).

Salida: `logs/coesita/benchmark/scenarios.json`. El dashboard los lista en
`/scenarios` y los sirve en `GET /api/scenarios`
(`?refresh=true&tier=...` regenera).

## Reglas

- Los textos de presión y eventos provienen de `ftm_engine.py` (port exacto del
  FTM v2.2); **no los edites ad hoc** o las métricas dejarán de ser comparables
  con el benchmark publicado. Para añadir dominios o canales nuevos, extiende
  `DOMAINS` / `PRESSURE_TEXTS` en el engine y añade tests.
- Para medir presión social usa `standard` o superior: `snapshot` solo contiene
  el schedule de control y no ejercita FARP/PRI.
- Genera los escenarios **antes** de lanzar el tester si quieres que
  `scenarios.json` y `results.json` cuenten la misma historia (el pipeline
  completo `run_full_pipeline()` ya lo hace en orden).
