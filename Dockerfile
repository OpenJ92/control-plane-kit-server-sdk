# syntax=docker/dockerfile:1

ARG PYTHON_VERSION=3.14

FROM python:${PYTHON_VERSION}-slim AS package

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY AGENTS.md GIT-FLOW.md .gitignore pyproject.toml README.md ./
COPY docs ./docs
COPY src ./src

RUN python -m pip install --no-deps .

FROM package AS test

COPY tests ./tests
COPY test_support/installed_verification_dependencies.py ./test_support/

CMD ["python", "-m", "unittest", "discover", "-s", "tests", "-v"]
