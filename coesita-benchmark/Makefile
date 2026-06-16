# Coesita Benchmark — developer shortcuts
#
# Requirements: Python ≥ 3.10, Docker (for the docker target).
# All Python targets install the package in a local .venv the first time.

VENV      := .venv
PYTHON    := $(VENV)/bin/python
PIP       := $(VENV)/bin/pip
COESITA   := $(VENV)/bin/coesita
PORT      ?= 5050

.PHONY: all venv install demo test lint docker docker-up clean

all: install

$(VENV)/bin/activate:
	python3 -m venv $(VENV)

venv: $(VENV)/bin/activate

install: venv
	$(PIP) install -q -e ".[dev]"
	@echo "✓ Coesita installed in $(VENV)"

# ── demo ─────────────────────────────────────────────────────────────────────
# Run the full pipeline with the built-in baselines (no API key needed),
# then open the dashboard. Ctrl-C to stop.
demo: install
	@echo ""
	@echo "=== Coesita Demo ==="
	@echo "Running benchmark pipeline (tier: standard, ~1s with built-in baselines)..."
	$(COESITA) run --tier standard
	@echo ""
	@echo "Pipeline complete. Starting dashboard on http://localhost:$(PORT)/benchmark"
	@echo "Press Ctrl-C to stop."
	$(COESITA) dashboard --port $(PORT)

# ── tests ─────────────────────────────────────────────────────────────────────
test: install
	$(VENV)/bin/pytest -q

lint: install
	$(VENV)/bin/ruff check src tests

# ── docker ───────────────────────────────────────────────────────────────────
docker:
	docker build -t coesita-benchmark:local .

docker-up:
	docker compose up -d
	@echo "Dashboard → http://localhost:5050/benchmark"
	@echo "Run: curl -X POST http://localhost:5050/benchmark/run  (or click ▶ Run benchmark)"

# ── cleanup ──────────────────────────────────────────────────────────────────
clean:
	rm -rf $(VENV) build dist *.egg-info __pycache__ .pytest_cache .ruff_cache
