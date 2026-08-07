#!/usr/bin/env bash
set -euo pipefail

RUN_ID="$$"
IMAGE_NAME="control-plane-kit-server-sdk-test:${RUN_ID}"
CONTAINER_NAME="cpk-server-sdk-test-${RUN_ID}"
POLICY_IMAGE="python:3.14-slim"
DEPENDENCY_MODE="${CPK_SERVER_SDK_DEPENDENCY_MODE:-pinned}"
CORE_REPO="${CPK_CORE_REPO:-}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd "$ROOT"

cleanup() {
  docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
  docker image rm -f "$IMAGE_NAME" >/dev/null 2>&1 || true
}

trap cleanup EXIT

echo "phase=policy-self-tests"
docker run --rm \
  -v "$ROOT:/source:ro" \
  -v "$ROOT/test_support:/test-support:ro" \
  -e CPK_PACKAGE_ROOT=/source \
  -e PYTHONDONTWRITEBYTECODE=1 \
  "$POLICY_IMAGE" \
  sh -c 'cd /test-support && python -m unittest discover -s tests -v'

echo "phase=package-integrity"
docker run --rm \
  -v "$ROOT:/source:ro" \
  -v "$ROOT/test_support:/test-support:ro" \
  -e PYTHONDONTWRITEBYTECODE=1 \
  "$POLICY_IMAGE" \
  python /test-support/package_integrity.py \
    --package-root /source \
    --source-root src \
    --test-root tests \
    --gate-file test.sh

echo "phase=dependency-preflight"
docker run --rm \
  -v "$ROOT:/source:ro" \
  -v "$ROOT/test_support:/test-support:ro" \
  -e PYTHONDONTWRITEBYTECODE=1 \
  "$POLICY_IMAGE" \
  python /test-support/dependency_preflight.py /source/pyproject.toml

case "$DEPENDENCY_MODE" in
  pinned)
    if [[ -n "$CORE_REPO" ]]; then
      echo "CPK_CORE_REPO requires CPK_SERVER_SDK_DEPENDENCY_MODE=local-core" >&2
      exit 2
    fi
    echo "dependency-mode=pinned"
    ;;
  local-core)
    if [[ -z "$CORE_REPO" || ! -d "$CORE_REPO/control-plane-kit-core" ]]; then
      echo "local-core mode requires CPK_CORE_REPO containing control-plane-kit-core" >&2
      exit 2
    fi
    echo "dependency-mode=local-core composition-evidence core-repo=$(cd "$CORE_REPO" && pwd)"
    ;;
  *)
    echo "unsupported CPK_SERVER_SDK_DEPENDENCY_MODE: $DEPENDENCY_MODE" >&2
    exit 2
    ;;
esac

echo "phase=package-build"
docker build --target test -t "$IMAGE_NAME" .

if [[ "$DEPENDENCY_MODE" == "local-core" ]]; then
  docker run \
    --name "$CONTAINER_NAME" \
    -v "$ROOT/test_support:/test-support:ro" \
    -v "$(cd "$CORE_REPO" && pwd):/workspace/control-plane-kit:ro" \
    "$IMAGE_NAME" \
    sh -ceu '
      cp -R /workspace/control-plane-kit/control-plane-kit-core /tmp/control-plane-kit-core
      python -m pip install /tmp/control-plane-kit-core
      python -m pip install --no-deps --force-reinstall .
      python -m compileall src tests
      python -m unittest discover -s tests -v
      cd /tmp
      python /test-support/installed_import.py
    '
else
  docker run \
    --name "$CONTAINER_NAME" \
    -v "$ROOT/test_support:/test-support:ro" \
    "$IMAGE_NAME" \
    sh -ceu '
      python -m pip install --force-reinstall .
      python -m compileall src tests
      python -m unittest discover -s tests -v
      cd /tmp
      python /test-support/installed_import.py
    '
fi
