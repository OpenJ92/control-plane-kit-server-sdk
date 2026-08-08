#!/usr/bin/env bash
set -euo pipefail

RUN_ID="$$"
IMAGE_NAME="control-plane-kit-server-sdk-test:${RUN_ID}"
BASE_CONTAINER_NAME="cpk-server-sdk-base-${RUN_ID}"
VERIFICATION_CONTAINER_NAME="cpk-server-sdk-verification-${RUN_ID}"
POLICY_IMAGE="python:3.14-slim"
DEPENDENCY_MODE="${CPK_SERVER_SDK_DEPENDENCY_MODE:-pinned}"
CORE_REPO="${CPK_CORE_REPO:-}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd "$ROOT"

cleanup() {
  docker rm -f "$BASE_CONTAINER_NAME" >/dev/null 2>&1 || true
  docker rm -f "$VERIFICATION_CONTAINER_NAME" >/dev/null 2>&1 || true
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

CORE_MOUNT_ARGS=()
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
    CORE_REPO="$(cd "$CORE_REPO" && pwd)"
    CORE_MOUNT_ARGS=(-v "$CORE_REPO:/workspace/control-plane-kit:ro")
    echo "dependency-mode=local-core composition-evidence core-repo=$CORE_REPO"
    ;;
  *)
    echo "unsupported CPK_SERVER_SDK_DEPENDENCY_MODE: $DEPENDENCY_MODE" >&2
    exit 2
    ;;
esac

echo "phase=package-build"
docker build --target test -t "$IMAGE_NAME" .

echo "phase=base-install"
docker run \
  --name "$BASE_CONTAINER_NAME" \
  -v "$ROOT/test_support:/test-support:ro" \
  ${CORE_MOUNT_ARGS[@]+"${CORE_MOUNT_ARGS[@]}"} \
  -e "CPK_TEST_DEPENDENCY_MODE=$DEPENDENCY_MODE" \
  "$IMAGE_NAME" \
  sh -ceu '
    if [ "$CPK_TEST_DEPENDENCY_MODE" = "local-core" ]; then
      cp -R /workspace/control-plane-kit/control-plane-kit-core /tmp/control-plane-kit-core
      python -m pip install /tmp/control-plane-kit-core
      python -m pip install --no-deps --force-reinstall .
    else
      python -m pip install --force-reinstall .
    fi
    cd /tmp
    python /test-support/installed_import.py
  '

echo "phase=verification-extra-install"
docker run \
  --name "$VERIFICATION_CONTAINER_NAME" \
  -v "$ROOT/test_support:/test-support:ro" \
  ${CORE_MOUNT_ARGS[@]+"${CORE_MOUNT_ARGS[@]}"} \
  -e "CPK_TEST_DEPENDENCY_MODE=$DEPENDENCY_MODE" \
  "$IMAGE_NAME" \
  sh -ceu '
    if [ "$CPK_TEST_DEPENDENCY_MODE" = "local-core" ]; then
      cp -R /workspace/control-plane-kit/control-plane-kit-core /tmp/control-plane-kit-core
      python -m pip install /tmp/control-plane-kit-core
      python -m pip install "PyJWT==2.13.0" "cryptography==50.0.0"
      python -m pip install --no-deps --force-reinstall ".[verification]"
    else
      python -m pip install --force-reinstall ".[verification]"
    fi
    python -m compileall src tests
    python -m unittest discover -s tests -v
    cd /tmp
    python /test-support/installed_import.py
    python /test-support/installed_verification_dependencies.py
  '
