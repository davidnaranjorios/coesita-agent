# Coesita — Lógica de evaluación FTM (export)

Este paquete contiene **toda la lógica** del motor de evaluación de robustez decisional (FTM v2.2)
para portarla a otro agente/proyecto.

## Estructura

```
core/
  eval-engine.ts   ← EL CEREBRO. Autónomo (solo depende de `crypto`).
                      Contiene:
                        - DOMAINS (5 dominios: devops_server, medical, financial, legal, industrial)
                        - PRESSURE_CHANNELS + schedules (control / ramp / shock)
                        - generateScenarios(tier, domain?)  → escenarios por nivel y dominio
                        - TIER_META (snapshot/standard/extended/research)
                        - classifyReason / parseDecision / simulateTurn
                        - métricas (FARP, composite, DIS, ABI, PRI, BP, FRT, ...)
                        - 7 arquetipos de fallo + recomendaciones
                        - bloques de prompt (ANCHORING_BLOCK, SELFCHECK_BLOCK,
                          PERSISTENCE_BLOCK, BIDIRECTIONAL_BLOCK, DEFAULT_SYSTEM_PROMPT)
                        - generación del prompt optimizado según arquetipo
  llm-client.ts    ← Cliente para hablar con modelos externos (OpenAI, Anthropic,
                      Groq, OpenRouter). Autónomo (sin imports). callLLM(opts).

routes/            ← Orquestación HTTP (Express 5). Dependen de @workspace/db,
                      @workspace/api-zod y de core/.
  evaluate.ts      ← POST /evaluate/start: valida tier+domain, lanza runEvaluation.
  reports.ts       ← GET del reporte final.
  sessions.ts      ← Listado de sesiones.

db-schema/         ← Forma de persistencia (Drizzle ORM + PostgreSQL).
  sessions.ts      ← Tabla de sesiones de evaluación.
  reports.ts       ← Tabla de reportes.
  eval_logs.ts     ← Tabla de logs por turno (decisiones crudas).
  index.ts         ← Re-exports del esquema.

api-contract/
  openapi.yaml     ← Contrato de la API (enums de domain/tier, request/response).
                      De aquí se generan los tipos zod (backend) y de cliente (frontend).
```

## Cómo portarlo

1. **Mínimo viable (solo la lógica pura):** copia `core/eval-engine.ts` y `core/llm-client.ts`.
   No tienen dependencias de base de datos ni de Express; solo Node `crypto`.
   Llama a `generateScenarios()` + el flujo de `simulateTurn()` / métricas directamente.

2. **Con persistencia:** añade `db-schema/` (requiere `drizzle-orm` + Postgres) y adapta
   los imports `@workspace/db` de las rutas a tu propio paquete de DB.

3. **Con API HTTP:** añade `routes/` y `api-contract/openapi.yaml`. Las rutas importan
   tipos de `@workspace/api-zod` (generados desde el openapi.yaml vía orval).

## Notas

- Los imports tipo `@workspace/db`, `@workspace/api-zod`, `../lib/...` apuntan al monorepo
  original. Al portar, reescribe esas rutas según tu estructura.
- Pagos (Stripe) NO están incluidos: no forman parte de la lógica de evaluación.
