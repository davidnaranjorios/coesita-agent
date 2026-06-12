"""Tests del paquete standalone coesita-benchmark.

Cubre: scanning de frameworks, generación de escenarios enriquecidos y
testing automatizado con los runners de referencia (sin red).
"""

from __future__ import annotations

import json

import pytest

from coesita.benchmark_store import (
    benchmark_dir, frameworks_path, history_path, load_history,
    results_path, scenarios_path,
)
from coesita.benchmark_tester import (
    REFERENCE_RUNNERS, data_anchored_runner, load_results, run_benchmark,
    run_full_pipeline, run_scenario, social_compliant_runner,
)
from coesita.framework_scanner import (
    FEATURE_KEYS, load_scan, run_scan, scan_frameworks,
)
from coesita.ftm_engine import generate_scenarios
from coesita.scenario_generator import (
    generate_benchmark_scenarios, run_generation,
)


@pytest.fixture(autouse=True)
def _isolated_log_dir(tmp_path, monkeypatch):
    """Redirige los artefactos del benchmark a un tempdir por test."""
    monkeypatch.setenv("COESITA_LOG_DIR", str(tmp_path / "coesita"))


# ─── Fase 1: Scanning ─────────────────────────────────────────────────────────

def test_scan_seed_has_known_frameworks_and_all_features():
    frameworks = scan_frameworks()
    slugs = {f["slug"] for f in frameworks}
    assert {"hermes-agent", "autogen", "crewai", "langgraph"} <= slugs
    for fw in frameworks:
        assert set(fw["features"]) == set(FEATURE_KEYS)
        assert fw["scanned_at"]


def test_scan_extra_entry_merges_and_overrides_seed():
    extra = [
        {"slug": "langgraph", "notes": "updated from the web",
         "features": {"kanban_board": True}},
        {"name": "Nuevo FW", "slug": "nuevo-fw", "org": "X",
         "features": {"multi_agent": True}},
    ]
    frameworks = scan_frameworks(extra)
    by_slug = {f["slug"]: f for f in frameworks}
    assert by_slug["langgraph"]["notes"] == "updated from the web"
    assert by_slug["langgraph"]["features"]["kanban_board"] is True
    # las features no mencionadas en el extra se conservan de la semilla
    assert by_slug["langgraph"]["features"]["multi_agent"] is True
    assert by_slug["langgraph"]["source"] == "web"
    assert by_slug["nuevo-fw"]["features"]["multi_agent"] is True


def test_run_scan_persists_and_loads():
    payload = run_scan()
    assert frameworks_path().exists()
    loaded = load_scan()
    assert loaded["n_frameworks"] == payload["n_frameworks"] == len(loaded["frameworks"])
    assert loaded["feature_keys"] == FEATURE_KEYS


# ─── Fase 2: Escenarios ───────────────────────────────────────────────────────

def test_generate_standard_scenarios_enriched():
    scenarios = generate_benchmark_scenarios("standard")
    assert len(scenarios) == 30  # 5 dominios × 2 condiciones × 3 schedules
    for s in scenarios:
        assert s["pressure_label"] in ("none", "ramp", "shock")
        assert s["description"]
        assert s["success_metrics"]
        assert s["evaluates"]
        assert s["n_turns"] == 10
    # los schedules con presión declaran FARP en sus métricas de éxito
    pressured = [s for s in scenarios if s["schedule_category"] != "control"]
    assert all(any("FARP" in m for m in s["success_metrics"]) for s in pressured)


def test_generate_scenarios_rejects_unknown_tier():
    with pytest.raises(ValueError):
        generate_benchmark_scenarios("mega")


def test_run_generation_persists():
    payload = run_generation("snapshot")
    assert payload["n_scenarios"] == 5
    assert scenarios_path().exists()
    assert all(s["pressure_label"] == "none" for s in payload["scenarios"])


# ─── Fase 3: Testing ──────────────────────────────────────────────────────────

def test_run_scenario_produces_ten_parsed_turns():
    scenario = generate_scenarios("standard")[0]
    turns = run_scenario(data_anchored_runner, scenario)
    assert len(turns) == 10
    assert [t.turn for t in turns] == list(range(1, 11))
    assert all(t.decision in ("STAY", "ACT") for t in turns)
    assert all(t.reason_class in ("DATA", "PRESSURE", "MIXED", "EMPTY") for t in turns)


def test_anchored_baseline_beats_compliant_baseline():
    payload = run_benchmark(dict(REFERENCE_RUNNERS), tier="standard")
    by_name = {f["framework"]: f for f in payload["frameworks"]}
    anchored = by_name["baseline-data-anchored"]["metrics"]
    compliant = by_name["baseline-social-compliant"]["metrics"]

    assert anchored["crs"] > compliant["crs"]
    assert anchored["farp_strict"] == 0.0
    assert compliant["farp_strict"] > 0.3  # capitula bajo presión
    assert anchored["stay_acc"] == 1.0
    assert anchored["act_acc"] == 1.0
    # ranking ordenado por CRS descendente
    crs_values = [f["metrics"]["crs"] for f in payload["frameworks"]]
    assert crs_values == sorted(crs_values, reverse=True)


def test_compliant_baseline_capitulation_is_pressure_driven():
    scenario = next(
        s for s in generate_scenarios("standard")
        if s.condition == "stay" and s.schedule_category == "shock"
    )
    turns = run_scenario(social_compliant_runner, scenario)
    flipped = [t for t in turns if t.decision == "ACT"]
    assert flipped, "el baseline complaciente debe capitular bajo shock"
    assert all(t.reason_class in ("PRESSURE", "MIXED") for t in flipped)


def test_run_benchmark_persists_results_and_history():
    run_benchmark(tier="standard")
    assert results_path().exists()
    results = load_results()
    assert results["tier"] == "standard"
    assert results["n_scenarios"] == 30
    history = load_history()
    assert len(history) == 1
    assert history[0]["run_id"] == results["run_id"]
    run_benchmark(tier="standard")
    assert len(load_history()) == 2


def test_runner_exception_counts_as_parse_fail():
    def broken_runner(system_prompt, messages):
        raise RuntimeError("sin red")

    scenario = generate_scenarios("standard")[0]
    turns = run_scenario(broken_runner, scenario)
    assert all(t.decision == "PARSE_FAIL" for t in turns)


# ─── Pipeline completo ────────────────────────────────────────────────────────

def test_full_pipeline_writes_all_artifacts():
    summary = run_full_pipeline(tier="standard")
    assert summary["n_scenarios"] == 30
    assert summary["n_frameworks_scanned"] >= 8
    assert summary["n_frameworks_tested"] == 2
    assert summary["ranking"][0]["framework"] == "baseline-data-anchored"

    for path in (frameworks_path(), scenarios_path(), results_path(), history_path()):
        assert path.exists(), f"falta {path.name}"
    # todo bajo el COESITA_LOG_DIR aislado del test
    assert str(benchmark_dir()) in str(frameworks_path())
    # el histórico es JSONL válido
    with open(history_path(), encoding="utf-8") as f:
        for line in f:
            json.loads(line)


# ─── CLI ──────────────────────────────────────────────────────────────────────

def test_cli_run_and_scan(capsys):
    from coesita.cli import main

    assert main(["run", "--tier", "standard"]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["n_scenarios"] == 30
    assert summary["ranking"][0]["framework"] == "baseline-data-anchored"

    assert main(["scan"]) == 0
    scan = json.loads(capsys.readouterr().out)
    assert scan["n_frameworks"] >= 8
