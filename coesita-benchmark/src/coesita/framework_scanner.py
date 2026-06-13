# framework_scanner.py
# Fase 1 — Scanning de Agent Frameworks.
#
# Mantiene un registro estructurado de frameworks de agentes y sus
# características clave (multi-agente, Kanban, memoria persistente, tools,
# subagentes, ...). El registro semilla (SEED_FRAMEWORKS) es la línea base
# curada; la skill `coesita-scanner` lo enriquece con investigación web
# escribiendo entradas adicionales que `scan_frameworks()` mergea.
#
# Salida: logs/coesita/benchmark/frameworks.json
# Endpoint: GET /scanning/frameworks (dashboard/app.py)

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from coesita.benchmark_store import (
    frameworks_path, load_json, save_json, utc_now_iso,
)
from coesita.ftm_engine import DOMAINS

# Características que se extraen de cada framework. Mantener esta lista
# sincronizada con la tabla comparativa del dashboard (/benchmark).
FEATURE_KEYS = [
    "multi_agent",         # orquestación de varios agentes
    "kanban_board",        # tablero de tareas persistente integrado
    "persistent_memory",   # memoria que sobrevive a la sesión
    "tool_use",            # invocación de herramientas/función
    "subagents",           # spawn de subagentes/delegación
    "human_in_loop",       # aprobación/intervención humana nativa
    "streaming",           # respuestas en streaming
]


def _valid_domains(domains) -> list[str]:
    """Filtra a los dominios FTM soportados (el corpus solo cubre esos 5)."""
    return [d for d in (domains or []) if d in DOMAINS]


@dataclass
class FrameworkInfo:
    """Ficha estructurada de un framework de agentes."""
    name: str
    slug: str
    org: str
    repo: str
    language: str
    features: dict[str, bool] = field(default_factory=dict)
    # Dominios FTM donde el framework se despliega típicamente (curado por la
    # skill coesita-scanner). Vacío = uso general → escenarios en los 5.
    domains: list[str] = field(default_factory=list)
    notes: str = ""
    source: str = "seed"          # "seed" | "web" | "manual"
    scanned_at: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        # Garantiza que todas las features conocidas estén presentes
        d["features"] = {k: bool(self.features.get(k, False)) for k in FEATURE_KEYS}
        d["domains"] = _valid_domains(self.domains)
        return d


def _f(**kwargs) -> dict[str, bool]:
    return {k: bool(kwargs.get(k, False)) for k in FEATURE_KEYS}


# Registro semilla — línea base curada (la skill coesita-scanner lo
# actualiza/expande con investigación web cuando hay acceso a red).
SEED_FRAMEWORKS: list[FrameworkInfo] = [
    FrameworkInfo(
        name="Hermes Agent (Coesita base)", slug="hermes-agent", org="Nous Research",
        repo="https://github.com/NousResearch/hermes-agent", language="Python",
        features=_f(multi_agent=True, kanban_board=True, persistent_memory=True,
                    tool_use=True, subagents=True, human_in_loop=True, streaming=True),
        domains=["devops_server"],
        notes="Base de Coesita. Kanban nativo (kanban_create/delegate_task), perfiles y skills.",
    ),
    FrameworkInfo(
        name="AutoGen / AG2", slug="autogen", org="Microsoft",
        repo="https://github.com/microsoft/autogen", language="Python",
        features=_f(multi_agent=True, persistent_memory=True, tool_use=True,
                    subagents=True, human_in_loop=True, streaming=True),
        domains=["devops_server", "financial"],
        notes="Conversaciones multi-agente (GroupChat); el fork comunitario AG2 mantiene la API clásica.",
    ),
    FrameworkInfo(
        name="CrewAI", slug="crewai", org="CrewAI Inc.",
        repo="https://github.com/crewAIInc/crewAI", language="Python",
        features=_f(multi_agent=True, persistent_memory=True, tool_use=True,
                    subagents=True, human_in_loop=True),
        domains=["financial", "legal", "devops_server"],
        notes="Equipos de agentes por roles (crew + tasks); memoria de corto/largo plazo opcional.",
    ),
    FrameworkInfo(
        name="LangGraph", slug="langgraph", org="LangChain",
        repo="https://github.com/langchain-ai/langgraph", language="Python",
        features=_f(multi_agent=True, persistent_memory=True, tool_use=True,
                    subagents=True, human_in_loop=True, streaming=True),
        domains=["devops_server", "financial", "medical"],
        notes="Grafos de estado con checkpointing persistente; interrupts nativos para human-in-the-loop.",
    ),
    FrameworkInfo(
        name="OpenAI Agents SDK (ex-Swarm)", slug="openai-agents", org="OpenAI",
        repo="https://github.com/openai/openai-agents-python", language="Python",
        features=_f(multi_agent=True, tool_use=True, subagents=True, streaming=True),
        domains=["devops_server", "medical", "financial", "legal", "industrial"],
        notes="Sucesor oficial de Swarm: handoffs entre agentes, guardrails y tracing.",
    ),
    FrameworkInfo(
        name="Semantic Kernel", slug="semantic-kernel", org="Microsoft",
        repo="https://github.com/microsoft/semantic-kernel", language="C#/Python/Java",
        features=_f(multi_agent=True, persistent_memory=True, tool_use=True,
                    subagents=True, streaming=True),
        domains=["financial", "legal"],
        notes="Plugins/planners empresariales; Agent Framework unifica SK y AutoGen.",
    ),
    FrameworkInfo(
        name="LlamaIndex Workflows", slug="llamaindex-workflows", org="LlamaIndex",
        repo="https://github.com/run-llama/llama_index", language="Python",
        features=_f(multi_agent=True, persistent_memory=True, tool_use=True,
                    subagents=True, human_in_loop=True, streaming=True),
        domains=["legal", "financial"],
        notes="Workflows dirigidos por eventos; contexto serializable entre pasos.",
    ),
    FrameworkInfo(
        name="smolagents", slug="smolagents", org="Hugging Face",
        repo="https://github.com/huggingface/smolagents", language="Python",
        features=_f(multi_agent=True, tool_use=True, subagents=True, streaming=True),
        domains=["devops_server"],
        notes="Agentes minimalistas que escriben acciones como código Python (CodeAgent).",
    ),
    FrameworkInfo(
        name="PydanticAI", slug="pydantic-ai", org="Pydantic",
        repo="https://github.com/pydantic/pydantic-ai", language="Python",
        features=_f(tool_use=True, streaming=True, multi_agent=True),
        domains=["financial", "devops_server"],
        notes="Salidas tipadas con validación Pydantic; foco en producción y testing.",
    ),
    FrameworkInfo(
        name="MetaGPT", slug="metagpt", org="DeepWisdom",
        repo="https://github.com/FoundationAgents/MetaGPT", language="Python",
        features=_f(multi_agent=True, persistent_memory=True, tool_use=True, subagents=True),
        domains=["devops_server"],
        notes="Compañía de software simulada: roles SOP (PM, arquitecto, ingeniero).",
    ),
]


def scan_frameworks(extra: list[dict] | None = None) -> list[dict]:
    """Escanea frameworks: registro semilla + entradas extra (p. ej. de la web).

    `extra` permite a la skill coesita-scanner inyectar fichas investigadas
    en caliente; una entrada extra con el mismo `slug` reemplaza a la semilla.
    """
    now = utc_now_iso()
    by_slug: dict[str, dict] = {}
    for fw in SEED_FRAMEWORKS:
        d = fw.to_dict()
        d["scanned_at"] = now
        by_slug[d["slug"]] = d
    for raw in extra or []:
        slug = raw.get("slug") or raw.get("name", "").lower().replace(" ", "-")
        if not slug:
            continue
        base = by_slug.get(slug, {
            "name": raw.get("name", slug), "slug": slug, "org": "", "repo": "",
            "language": "", "features": {}, "domains": [], "notes": "", "source": "web",
        })
        merged = {**base, **{k: v for k, v in raw.items() if v not in (None, "")}}
        merged["features"] = {
            k: bool({**base.get("features", {}), **raw.get("features", {})}.get(k, False))
            for k in FEATURE_KEYS
        }
        # domains: la entrada extra reemplaza (no mergea) si la trae; siempre
        # se valida contra los 5 dominios FTM soportados por el corpus.
        merged["domains"] = _valid_domains(raw.get("domains", base.get("domains", [])))
        merged["source"] = raw.get("source", "web")
        merged["scanned_at"] = now
        by_slug[slug] = merged
    return list(by_slug.values())


def save_scan(frameworks: list[dict]) -> str:
    """Persiste el resultado del scan en frameworks.json."""
    payload = {
        "scanned_at": utc_now_iso(),
        "n_frameworks": len(frameworks),
        "feature_keys": FEATURE_KEYS,
        "frameworks": frameworks,
    }
    return str(save_json(frameworks_path(), payload))


def load_scan() -> dict | None:
    """Carga el último scan persistido, o None si no existe."""
    return load_json(frameworks_path())


def run_scan(extra: list[dict] | None = None) -> dict:
    """Conveniencia: escanea, persiste y devuelve el payload completo."""
    frameworks = scan_frameworks(extra)
    save_scan(frameworks)
    return load_scan()
