# Coesita Benchmark — decisional robustness under social pressure (FTM v2.2)
# https://coesita.dev (product) — based on the Servitorship Bias taxonomy.

__version__ = "1.0.0"

from coesita.ftm_engine import (
    # Constants
    DOMAINS, PRESSURE_CHANNELS, PRESSURE_TEXTS,
    STAY_EVENTS, ACT_EVENTS, DOMAIN_ROLES,
    TIER_META, PRESSURE_SCHEDULES,
    # Classifiers
    classify_reason, parse_decision,
    # Scenario generator (raw FTM)
    generate_scenarios,
    # Metrics engine v10
    compute_metrics, MetricsResult, TurnResult, Scenario,
    # Archetypes (2 healthy + 5 failure modes)
    detect_archetype, ArchetypeResult,
    # Validated intervention blocks
    generate_optimized_prompt,
    ANCHORING_BLOCK, SELFCHECK_BLOCK, PERSISTENCE_BLOCK, BIDIRECTIONAL_BLOCK,
    # FTM prompt builders
    build_ftm_system_prompt, build_turn_user_message,
)

# Agent-side instrumentation (log your own agent's decisions)
from coesita.pressure_detection import detect_pressure
from coesita.decision_logger import DecisionLogger
from coesita.resistant_response import build_resistant_response
from coesita.coesita_self_eval import evaluate_session, FTM_BENCHMARKS

# Benchmark pipeline (scanning → scenarios → testing → dashboard)
from coesita.framework_scanner import (
    SEED_FRAMEWORKS, FrameworkInfo, detect_features_from_text, load_scan,
    run_scan, scan_artifacts, scan_frameworks,
)
from coesita.scenario_generator import (
    generate_benchmark_scenarios, load_scenarios, run_generation,
)
from coesita.benchmark_tester import (
    REFERENCE_RUNNERS, load_results, make_openai_compatible_runner,
    run_benchmark, run_full_pipeline,
)
from coesita.feature_scenarios import (
    FEATURE_PACKS, classify_reason_extended, generate_feature_packs,
    packs_for_features,
)
from coesita.benchmark_store import data_dir, load_history

__all__ = [
    "__version__",
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
    # Agent instrumentation
    "detect_pressure", "DecisionLogger", "build_resistant_response",
    "evaluate_session", "FTM_BENCHMARKS",
    # Benchmark pipeline
    "FrameworkInfo", "SEED_FRAMEWORKS",
    "scan_frameworks", "run_scan", "load_scan",
    "scan_artifacts", "detect_features_from_text",
    "generate_benchmark_scenarios", "run_generation", "load_scenarios",
    "REFERENCE_RUNNERS", "make_openai_compatible_runner",
    "run_benchmark", "run_full_pipeline", "load_results",
    "FEATURE_PACKS", "generate_feature_packs", "packs_for_features",
    "classify_reason_extended",
    "data_dir", "load_history",
]
