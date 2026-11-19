PY ?= python3
extract:  ; $(PY) -m src.pipeline.extract
extract-full: ; $(PY) -m src.pipeline.extract --force
extract-scheduled: ; $(PY) -m src.pipeline.extract --require-token   # opt-in: stop without a Socrata app token (decision D5 was revised: a token is optional)
gate1:    ; $(PY) -m src.pipeline.extract --gate
build:    ; $(PY) -m src.pipeline.build
gate3:    ; $(PY) -m pytest -q tests/test_reference.py
all:      extract build
test:     ; $(PY) -m pytest -q tests
test-fault: ; $(PY) -m pytest -q tests/test_fault_injection.py
reconcile: ; $(PY) -m src.pipeline.reconcile $(RECONCILE_FLAGS)
parity:   ; $(PY) -m src.pipeline.parity --legacy $(or $(LEGACY),legacy/gst/out) --strict
export:   ; $(PY) -m src.pipeline.export $(EXPORT_FLAGS)
datamarts: ; $(PY) -m src.pipeline.datamarts $(DATAMART_FLAGS)
snapshot: ; $(PY) -m src.pipeline.snapshot create
restore:  ; $(PY) -m src.pipeline.snapshot restore $(SNAP) $(RESTORE_FLAGS)
figures:  ; $(PY) -m src.pipeline.figures
diagrams: ; mmdc -i docs/figures/pipeline.mmd -o docs/figures/pipeline.png -b white -s 2 && mmdc -i docs/figures/data_hierarchy.mmd -o docs/figures/data_hierarchy.png -b white -s 2 \
	&& mmdc -i docs/figures/readme/pipeline.mmd -o docs/figures/readme/pipeline_light.png -t default -b white -w 1800 -s 2 \
	&& mmdc -i docs/figures/readme/pipeline.mmd -o docs/figures/readme/pipeline_dark.png -t dark -b '#0d1117' -w 1800 -s 2
readme-shots: site ; $(PY) -m src.pipeline.readme_shots
docs:     ; $(PY) -m src.pipeline.governance $(if $(DASH),--dashboard $(DASH))
site:     ; $(PY) -m src.pipeline.site $(SITE_FLAGS)
site-snapshot: ; $(PY) -m src.pipeline.site --refresh-snapshot
# Opt-in (decision #12): mirror the marts into a local Postgres. DuckDB stays the default.
# Dry run without a database: make postgres DRY_RUN=1  (add SRC=--duckdb to read the marts instead of the CSV export)
postgres:
	$(if $(DRY_RUN),,$(if $(DATABASE_URL),,$(error DATABASE_URL is not set — point it at a local Postgres, e.g. export DATABASE_URL=postgresql://localhost:5432/md_marts (preview without connecting: make postgres DRY_RUN=1))))
	$(PY) mcp_server/db/load_postgres.py $(if $(DRY_RUN),--dry-run) $(SRC)
site-artifact: ; $(PY) -m src.pipeline.site --artifact $(or $(ARTIFACT_OUT),$${TMPDIR:-/tmp}/gmi-site-artifact)
docs-strict: ; $(PY) -m src.pipeline.governance --strict $(if $(DASH),--dashboard $(DASH))

# Reproducibility and review targets (work offline, from the published tables in site_data/)
forecast-check: ; $(PY) -m src.models.forecast_published --check   # rebuild the forecast from site_data and compare with what was published
overview-figures: ; $(PY) -m src.pipeline.overview_figures          # docs/figures/overview/*.png
notebook: ; $(PY) scripts/build_walkthrough.py && $(PY) scripts/render_notebook.py   # write the walkthrough notebook, execute it, render it, refresh the figures
notebook-check: ; $(PY) scripts/render_notebook.py --check
lock: ; uv lock && uv export --frozen --extra dev --extra mcp --extra notebook --no-emit-project -o requirements.lock.txt -q
docker-build: ; docker build -t gmi-savings-tracker:local .
docker-test: docker-build ; docker run --rm gmi-savings-tracker:local

.PHONY: forecast-check overview-figures notebook notebook-check lock docker-build docker-test
.PHONY: readme-shots
.PHONY: datamarts
.PHONY: extract extract-full gate1 build gate3 all test test-fault docs docs-strict reconcile figures diagrams parity export snapshot restore site site-snapshot site-artifact postgres extract-scheduled
