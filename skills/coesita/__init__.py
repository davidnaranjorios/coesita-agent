# Skills de Coesita Agent — Phase 3
# Alineadas con FTM Benchmark v2.2 (Servitorship Bias taxonomy)

from skills.coesita.ftm_engine import (
    # Constantes
    DOMAINS, PRESSURE_CHANNELS, PRESSURE_TEXTS,
    STAY_EVENTS, ACT_EVENTS, DOMAIN_ROLES,
    TIER_META, PRESSURE_SCHEDULES,
    # Clasificadores (port exacto de Cell 11 y Cell 14)
    classify_reason, parse_decision,
    # Generador de escenarios
    generate_scenarios,
    # Motor de métricas v10 (port exacto de Cell 18)
    compute_metrics, MetricsResult, TurnResult, Scenario,
    # Arquetipos (7: 2 sanos + 5 fallos)
    detect_archetype, ArchetypeResult,
    # Bloques de intervención validados (§7)
    generate_optimized_prompt,
    ANCHORING_BLOCK, SELFCHECK_BLOCK, PERSISTENCE_BLOCK, BIDIRECTIONAL_BLOCK,
    # Builders de prompt FTM
    build_ftm_system_prompt, build_turn_user_message,
)
from skills.coesita.pressure_detection import detect_pressure
from skills.coesita.decision_logger import DecisionLogger
from skills.coesita.resistant_response import build_resistant_response
from skills.coesita.coesita_self_eval import evaluate_session, FTM_BENCHMARKS

# Pipeline de benchmark (Fases 1-4: scanning → escenarios → testing → dashboard)
from skills.coesita.framework_scanner import (
    SEED_FRAMEWORKS, FrameworkInfo, detect_features_from_text, load_scan,
    run_scan, scan_artifacts, scan_frameworks,
)
from skills.coesita.scenario_generator import (
    generate_benchmark_scenarios, load_scenarios, run_generation,
)
from skills.coesita.benchmark_tester import (
    REFERENCE_RUNNERS, load_results, make_openai_compatible_runner,
    run_benchmark, run_full_pipeline,
)
from skills.coesita.feature_scenarios import (
    FEATURE_PACKS, classify_reason_extended, generate_feature_packs,
    packs_for_features,
)
from skills.coesita.benchmark_store import load_history

__all__ = [
    # FTM Engine
    "DOMAINS", "PRESSURE_CHANNELS", "PRESSURE_TEXTS",
    "STAY_EVENTS", "ACT_EVENTS", "DOMAIN_ROLES",
    "TIER_META", "PRESSURE_SCHEDULES",
    "classify_reason", "parse_decision",
    "generate_scenarios",
    "compute_metrics", "MetricsResult", "TurnResult", "Scenario",
    "detect_archetype", "ArchetypeResult",
    "generate_optimized_prompt",
    "ANCHORING_BLOCK", "SELFCHECK_BLOCK", "PERSISTENCE_BLOCK", "BIDIRECTIONAL_BLOCK",
    "build_ftm_system_prompt", "build_turn_user_message",
    # Skills runtime
    "detect_pressure",
    "DecisionLogger",
    "build_resistant_response",
    "evaluate_session",
    "FTM_BENCHMARKS",
    # Benchmark pipeline (Fases 1-4)
    "FrameworkInfo", "SEED_FRAMEWORKS",
    "scan_frameworks", "run_scan", "load_scan",
    "scan_artifacts", "detect_features_from_text",
    "generate_benchmark_scenarios", "run_generation", "load_scenarios",
    "REFERENCE_RUNNERS", "make_openai_compatible_runner",
    "run_benchmark", "run_full_pipeline", "load_results",
    "FEATURE_PACKS", "generate_feature_packs", "packs_for_features",
    "classify_reason_extended",
    "load_history",
]
