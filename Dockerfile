# Reproducible environment for the tests, the site build, the notebook and (with a token) the full pipeline.
# Dependencies come only from uv.lock. The full Debian base already carries make and libgomp1 (LightGBM),
# so the build needs no apt step and reaches only Docker Hub and PyPI.
FROM python:3.12-bookworm

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    MPLBACKEND=Agg

# Behind a TLS-inspecting proxy, pass its CA bundle as an optional build secret; without one this is a no-op:
#   docker build --secret id=extra_ca,src=/path/to/ca-bundle.crt -t gmi-savings-tracker:local .
RUN --mount=type=secret,id=extra_ca,required=false \
    if [ -s /run/secrets/extra_ca ]; then export PIP_CERT=/run/secrets/extra_ca; fi; \
    pip install --no-cache-dir uv==0.11.32

WORKDIR /app

# Dependency layer first: it is rebuilt only when the lockfile changes.
COPY pyproject.toml uv.lock .python-version ./
RUN --mount=type=secret,id=extra_ca,required=false \
    if [ -s /run/secrets/extra_ca ]; then export SSL_CERT_FILE=/run/secrets/extra_ca; fi; \
    uv sync --frozen --no-install-project --extra dev --extra mcp --extra notebook

RUN useradd --create-home --uid 1000 app && chown app:app /app
COPY --chown=app:app . .
USER app

CMD ["make", "test", "site", "PY=python"]
