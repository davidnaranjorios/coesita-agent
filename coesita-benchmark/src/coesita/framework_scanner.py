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

import re
from dataclasses import asdict, dataclass, field

from coesita.benchmark_store import (
    frameworks_path, load_json, save_json, utc_now_iso,
)

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

# Señales textuales por feature. Se buscan en el contenido REAL del framework
# (system prompt, documentos RAG, código/config) para detectar capacidades a
# partir de evidencia, en vez de asumir un registro. Ver scan_artifacts().
FEATURE_SIGNALS: dict[str, list[str]] = {
    "multi_agent": [
        "multi-agent", "multi agent", "group chat", "groupchat", "agent team",
        "crew", "swarm", "orchestrat", "router agent", "agent network",
    ],
    "kanban_board": [
        "kanban", "task board", "ticket queue", "board column", "backlog",
        "work item",
    ],
    "persistent_memory": [
        "persistent memory", "long-term memory", "long term memory",
        "vector store", "vectorstore", "embedding", "retrieval", "rag",
        "knowledge base", "recall", "remember", "checkpoint", "episodic",
    ],
    "tool_use": [
        "tool call", "tool-call", "function call", "function-calling",
        "function calling", "tool use", "invoke tool", "api call", "use a tool",
        "call tool", "call a tool", "available tools", "tools available",
    ],
    "subagents": [
        "subagent", "sub-agent", "sub agent", "delegate", "spawn", "handoff",
        "worker agent", "child agent", "delegation",
    ],
    "human_in_loop": [
        "human-in-the-loop", "human in the loop", "human approval",
        "human review", "approval step", "sign-off", "signoff", "interrupt",
        "confirmation", "await approval",
    ],
    "streaming": [
        "streaming", "token-by-token", "token by token", "server-sent",
        "sse", "stream response", "stream tokens",
    ],
}


@dataclass
class FrameworkInfo:
    """Ficha estructurada de un framework de agentes."""
    name: str
    slug: str
    org: str
    repo: str
    language: str
    features: dict[str, bool] = field(default_factory=dict)
    notes: str = ""
    source: str = "seed"          # "seed" | "web" | "manual" | "artifact-scan"
    scanned_at: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        # Garantiza que todas las features conocidas estén presentes
        d["features"] = {k: bool(self.features.get(k, False)) for k in FEATURE_KEYS}
        return d


def detect_features_from_text(*texts: str) -> dict[str, bool]:
    """Detecta features buscando las señales de FEATURE_SIGNALS en el texto.

    Recibe uno o más blobs (system prompt, RAG, código...) y devuelve el dict
    de las 7 features. Determinista, sin red.
    """
    blob = "\n".join(t for t in texts if t).lower()
    detected = {
        feat: any(sig in blob for sig in signals)
        for feat, signals in FEATURE_SIGNALS.items()
    }
    # Señal extra para tool_use: sintaxis de invocación tipo `nombre_funcion()`.
    if not detected["tool_use"] and re.search(r"\b\w+\(\s*\)", blob):
        detected["tool_use"] = True
    return detected


_TOOL_STOPWORDS = {
    "def", "return", "if", "elif", "for", "while", "with", "print", "len",
    "str", "int", "float", "list", "dict", "set", "tuple", "bool", "type",
    "the", "you", "and", "for", "this", "that", "your", "any", "all", "not",
    "class", "self", "async", "await", "import", "from", "lambda", "range",
    "open", "format", "super", "object", "none", "true", "false",
}


def extract_tool_names(*texts: str) -> list[str]:
    """Heurística para extraer nombres de herramientas del contenido del agente.

    Busca sintaxis de invocación (`nombre(`) y listas tipo markdown
    (`- nombre:` / `- `nombre``). Es un fallback: la fuente fiable es la lista
    de tools real del framework, que se pasa explícitamente a scan_agent_soul().
    """
    blob = "\n".join(t for t in texts if t)
    names: set[str] = set()
    for m in re.finditer(r"\b([a-z_][a-z0-9_]{2,})\s*\(", blob, re.IGNORECASE):
        names.add(m.group(1))
    for m in re.finditer(r"[-*]\s*`?([a-z_][a-z0-9_]{2,})`?\s*[:(]", blob, re.IGNORECASE):
        names.add(m.group(1))
    return sorted(n for n in names if n.lower() not in _TOOL_STOPWORDS)


def scan_agent_soul(
    name: str,
    *,
    slug: str | None = None,
    system_prompt: str = "",
    rag_text: str = "",
    code: str = "",
    tools: list[str] | None = None,
) -> dict:
    """Ingiere el SOUL completo de UN agente para evaluación individual (Modo B).

    Detecta features del contenido y resuelve la lista de tools del agente
    (preferentemente explícita; si no, la extrae del código/prompt). El
    resultado alimenta soul_scenarios.generate_soul_scenarios().
    """
    features = detect_features_from_text(system_prompt, rag_text, code, name)
    tool_list = list(tools) if tools else extract_tool_names(code, system_prompt)
    return {
        "name": name,
        "slug": slug or re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-"),
        "features": features,
        "tools": tool_list,
        "system_prompt": system_prompt,
        "rag_text": rag_text,
        "code": code,
        "source": "agent-soul",
    }


def scan_artifacts(
    name: str,
    *,
    slug: str | None = None,
    org: str = "",
    repo: str = "",
    language: str = "",
    system_prompt: str = "",
    rag_text: str = "",
    code: str = "",
    notes: str = "",
) -> dict:
    """Procesa los artefactos REALES de un framework/agente y detecta sus
    features a partir del contenido (system prompt, documentos RAG, código).

    No asume dominios ni capacidades declaradas: lee la evidencia. Devuelve una
    ficha lista para pasar a scan_frameworks(extra=[...]) / run_scan(extra=...).
    """
    features = detect_features_from_text(system_prompt, rag_text, code, notes, name)
    return {
        "name": name,
        "slug": slug or re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-"),
        "org": org,
        "repo": repo,
        "language": language,
        "features": features,
        "notes": notes,
        "source": "artifact-scan",
    }


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
        notes="Base de Coesita. Kanban nativo (kanban_create/delegate_task), perfiles y skills.",
    ),
    FrameworkInfo(
        name="AutoGen / AG2", slug="autogen", org="Microsoft",
        repo="https://github.com/microsoft/autogen", language="Python",
        features=_f(multi_agent=True, persistent_memory=True, tool_use=True,
                    subagents=True, human_in_loop=True, streaming=True),
        notes="Conversaciones multi-agente (GroupChat); el fork comunitario AG2 mantiene la API clásica.",
    ),
    FrameworkInfo(
        name="CrewAI", slug="crewai", org="CrewAI Inc.",
        repo="https://github.com/crewAIInc/crewAI", language="Python",
        features=_f(multi_agent=True, persistent_memory=True, tool_use=True,
                    subagents=True, human_in_loop=True),
        notes="Equipos de agentes por roles (crew + tasks); memoria de corto/largo plazo opcional.",
    ),
    FrameworkInfo(
        name="LangGraph", slug="langgraph", org="LangChain",
        repo="https://github.com/langchain-ai/langgraph", language="Python",
        features=_f(multi_agent=True, persistent_memory=True, tool_use=True,
                    subagents=True, human_in_loop=True, streaming=True),
        notes="Grafos de estado con checkpointing persistente; interrupts nativos para human-in-the-loop.",
    ),
    FrameworkInfo(
        name="OpenAI Agents SDK (ex-Swarm)", slug="openai-agents", org="OpenAI",
        repo="https://github.com/openai/openai-agents-python", language="Python",
        features=_f(multi_agent=True, tool_use=True, subagents=True, streaming=True),
        notes="Sucesor oficial de Swarm: handoffs entre agentes, guardrails y tracing.",
    ),
    FrameworkInfo(
        name="Semantic Kernel", slug="semantic-kernel", org="Microsoft",
        repo="https://github.com/microsoft/semantic-kernel", language="C#/Python/Java",
        features=_f(multi_agent=True, persistent_memory=True, tool_use=True,
                    subagents=True, streaming=True),
        notes="Plugins/planners empresariales; Agent Framework unifica SK y AutoGen.",
    ),
    FrameworkInfo(
        name="LlamaIndex Workflows", slug="llamaindex-workflows", org="LlamaIndex",
        repo="https://github.com/run-llama/llama_index", language="Python",
        features=_f(multi_agent=True, persistent_memory=True, tool_use=True,
                    subagents=True, human_in_loop=True, streaming=True),
        notes="Workflows dirigidos por eventos; contexto serializable entre pasos.",
    ),
    FrameworkInfo(
        name="smolagents", slug="smolagents", org="Hugging Face",
        repo="https://github.com/huggingface/smolagents", language="Python",
        features=_f(multi_agent=True, tool_use=True, subagents=True, streaming=True),
        notes="Agentes minimalistas que escriben acciones como código Python (CodeAgent).",
    ),
    FrameworkInfo(
        name="PydanticAI", slug="pydantic-ai", org="Pydantic",
        repo="https://github.com/pydantic/pydantic-ai", language="Python",
        features=_f(tool_use=True, streaming=True, multi_agent=True),
        notes="Salidas tipadas con validación Pydantic; foco en producción y testing.",
    ),
    FrameworkInfo(
        name="MetaGPT", slug="metagpt", org="DeepWisdom",
        repo="https://github.com/FoundationAgents/MetaGPT", language="Python",
        features=_f(multi_agent=True, persistent_memory=True, tool_use=True, subagents=True),
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
            "language": "", "features": {}, "notes": "", "source": "web",
        })
        merged = {**base, **{k: v for k, v in raw.items() if v not in (None, "")}}
        merged["features"] = {
            k: bool({**base.get("features", {}), **raw.get("features", {})}.get(k, False))
            for k in FEATURE_KEYS
        }
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
