# therapy-stack -- common commands
#
# Targets are listed in roughly the order a new contributor will use them.
# `make help` lists them. Most targets defer to a script in scripts/ so
# the Makefile is a thin orchestration layer; the actual work is Python.

PY ?= sandbox/.venv/Scripts/python.exe
SET ?= val

.PHONY: help
help:
	@echo "therapy-stack makefile"
	@echo ""
	@echo "  make preflight       -- pytest + lint + diversity + baselines (no LLM)"
	@echo "  make test            -- unit tests only"
	@echo "  make lint            -- benchmark YAML lint (schema + leakage)"
	@echo "  make diversity       -- dataset diversity per split"
	@echo "  make baselines       -- compute no-LLM baselines on all splits"
	@echo "  make bench-dev       -- run local-Llama bench on dev split"
	@echo "  make bench-val       -- run local-Llama bench on val split"
	@echo "  make bench-adv       -- run local-Llama bench on adversarial split"
	@echo "  make review RUN=...  -- generate full review markdown + HTML"
	@echo "  make manifest        -- regenerate sandbox/MANIFEST.md"
	@echo "  make release-ready   -- pre-tag drift checks"
	@echo ""
	@echo "Environment variables:"
	@echo "  PY     python interpreter (default: $(PY))"
	@echo "  SET    split for bench (default: $(SET); one of dev/val/adversarial/all)"
	@echo "  LLAMA_MODEL_PATH  path to GGUF for local Llama bench"

.PHONY: preflight
preflight:
	$(PY) scripts/preflight.py

.PHONY: test
test:
	$(PY) -m pytest tests/ -v

.PHONY: lint
lint:
	$(PY) scripts/benchmark_lint.py

.PHONY: diversity
diversity:
	$(PY) scripts/dataset_diversity.py > sandbox/DIVERSITY.md
	@echo "Wrote sandbox/DIVERSITY.md"

.PHONY: baselines
baselines:
	cd sandbox && ../$(PY) run_blinded.py --baselines-only --set all

.PHONY: bench-dev
bench-dev:
	cd sandbox && THERAPY_AGENT_LLM_BACKEND=llama ../$(PY) run_blinded.py \
		--set dev --out dev_results.json

.PHONY: bench-val
bench-val:
	cd sandbox && THERAPY_AGENT_LLM_BACKEND=llama ../$(PY) run_blinded.py \
		--set val --out val_results.json

.PHONY: bench-adv
bench-adv:
	cd sandbox && THERAPY_AGENT_LLM_BACKEND=llama ../$(PY) run_blinded.py \
		--set adversarial --out adv_results.json

.PHONY: review
review:
ifndef RUN
	@echo "usage: make review RUN=sandbox/blinded_v20_val_llama.json"
	@exit 1
endif
	$(PY) scripts/full_review.py $(RUN)

.PHONY: manifest
manifest:
	$(PY) scripts/sandbox_manifest.py > sandbox/MANIFEST.md
	@echo "Wrote sandbox/MANIFEST.md"

.PHONY: release-ready
release-ready:
	$(PY) scripts/release_readiness.py
