"""Private bodyless FastAPI adapter for the closed workload-health dispatcher."""
from __future__ import annotations

from fastapi import APIRouter, Request, Response
from fastapi.concurrency import run_in_threadpool

from control_plane_kit_core import NodeHealthReadKind
from control_plane_kit_core.control_routes import NODE_HEALTH_ROUTES
from control_plane_kit_server_sdk._fastapi_variable_routes import (
    _MAX_BODY_BYTES,
    _MAX_PATH_BYTES,
    _RequestInvalid,
    _RequestTooLarge,
    _credential,
    _query_status,
)
from control_plane_kit_server_sdk.health import WorkloadNodeHealthReadDispatcher
from control_plane_kit_server_sdk.verification import (
    WorkloadNodeControlVerificationError,
    WorkloadNodeHealthReadVerificationError,
)


_ERROR_BODIES = {
    400: b'{"code":"node-health.request-invalid"}',
    401: b'{"code":"node-health.credential-rejected"}',
    404: b'{"code":"node-health.kind-not-found"}',
    413: b'{"code":"node-health.request-too-large"}',
    500: b'{"code":"node-health.internal-failure"}',
}


def _response(status: int, body: bytes) -> Response:
    return Response(body, status_code=status, media_type="application/json",
                    headers={"Cache-Control": "no-store"})


def _error(status: int) -> Response:
    return _response(status, _ERROR_BODIES[status])


def _interpret(
    dispatcher: WorkloadNodeHealthReadDispatcher, credential: bytes, kind: NodeHealthReadKind,
) -> tuple[int, bytes]:
    try:
        result = dispatcher.read(credential, route_kind=kind, candidate=None)
        return 200, result.canonical_bytes()
    except WorkloadNodeHealthReadVerificationError:
        return 401, _ERROR_BODIES[401]
    except Exception:
        return 500, _ERROR_BODIES[500]


async def _handle(
    request: Request, health_kind: str, dispatcher: WorkloadNodeHealthReadDispatcher,
) -> Response:
    raw_path = request.scope.get("raw_path")
    if type(raw_path) is not bytes or request.method != "GET":
        return _error(400)
    if len(raw_path) > _MAX_PATH_BYTES:
        return _error(413)
    try:
        kind = NodeHealthReadKind(health_kind)
    except (TypeError, ValueError):
        return _error(404)
    if raw_path != b"/__control/health/" + kind.value.encode("ascii"):
        return _error(400)
    query_status = _query_status(request.scope.get("query_string"))
    if query_status is not None:
        return _error(query_status)
    try:
        credential = _credential(request.scope.get("headers"))
        async for chunk in request.stream():
            if type(chunk) is not bytes:
                raise _RequestInvalid
            if len(chunk) > _MAX_BODY_BYTES:
                raise _RequestTooLarge
            if chunk:
                raise _RequestInvalid
    except _RequestTooLarge:
        return _error(413)
    except WorkloadNodeControlVerificationError:
        return _error(401)
    except Exception:
        return _error(400)
    status, body = await run_in_threadpool(_interpret, dispatcher, credential, kind)
    return _response(status, body)


def _build_health_routes(*, dispatcher: WorkloadNodeHealthReadDispatcher) -> tuple[object, ...]:
    if type(dispatcher) is not WorkloadNodeHealthReadDispatcher:
        raise ValueError("FastAPI health route construction is invalid")
    router = APIRouter()

    async def health_read(request: Request, health_kind: str) -> Response:
        return await _handle(request, health_kind, dispatcher)

    route = NODE_HEALTH_ROUTES.routes[0]
    router.add_api_route(route.path, health_read, methods=[route.method.value],
                         name=route.name, include_in_schema=False)
    return tuple(router.routes)


__all__: list[str] = []
