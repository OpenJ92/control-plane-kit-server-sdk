"""Private FastAPI interpreter for authenticated variable routes."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response
from fastapi.concurrency import run_in_threadpool

from control_plane_kit_core import (
    ControlPlaneVariableDescriptor, NodeControlGraphReference,
    NodeControlGraphReferenceRole, NodeControlOperation, NodeControlResultCodec,
    NodeControlTarget, WorkloadNodeControlSurfaceDeclaration,
)
from control_plane_kit_server_sdk._replay import _ProcessLocalNodeControlReplay
from control_plane_kit_server_sdk.verification import (
    Ed25519WorkloadNodeControlVerifier,
    WorkloadNodeControlVerificationError,
)
from control_plane_kit_server_sdk._control_dispatch import (
    _build_variable_registry, _interpret_variable,
)
from control_plane_kit_server_sdk._http_framing import (
    _ERROR_BODIES, _MAX_BODY_BYTES, _MAX_PATH_BYTES,
    _RequestInvalid, _RequestTooLarge, _credential, _query_status,
)


def _response(status: int, body: bytes) -> Response:
    return Response(content=body, status_code=status, media_type="application/json")


def _error(status: int) -> Response:
    return _response(status, _ERROR_BODIES[status])


async def _body(request: Request) -> bytes:
    chunks: list[bytes] = []
    total = 0
    try:
        async for chunk in request.stream():
            if type(chunk) is not bytes:
                raise _RequestInvalid
            total += len(chunk)
            if total > _MAX_BODY_BYTES:
                raise _RequestTooLarge
            chunks.append(chunk)
    except (_RequestInvalid, _RequestTooLarge):
        raise
    except Exception:
        raise _RequestInvalid
    return b"".join(chunks)


async def _handle(
    request: Request,
    variable_name: str,
    operation: NodeControlOperation,
    *,
    target: NodeControlTarget,
    registry: dict[
        str,
        tuple[object, ControlPlaneVariableDescriptor, NodeControlResultCodec],
    ],
    verifier: Ed25519WorkloadNodeControlVerifier,
    replay: _ProcessLocalNodeControlReplay,
) -> Response:
    raw_path = request.scope.get("raw_path")
    if type(raw_path) is not bytes:
        return _error(400)
    if len(raw_path) > _MAX_PATH_BYTES:
        return _error(413)
    query_status = _query_status(request.scope.get("query_string"))
    if query_status is not None:
        return _error(query_status)
    try:
        credential = _credential(request.scope.get("headers"))
        candidate_bytes = await _body(request)
        if operation is NodeControlOperation.READ_STATE:
            if candidate_bytes:
                return _error(400)
            candidate = None
        else:
            candidate = candidate_bytes
        route_variable = NodeControlGraphReference(
            NodeControlGraphReferenceRole.VARIABLE,
            variable_name,
        )
    except _RequestTooLarge:
        return _error(413)
    except WorkloadNodeControlVerificationError:
        return _error(401)
    except Exception:
        return _error(400)

    status, body = await run_in_threadpool(
        _interpret_variable,
        credential=credential,
        candidate=candidate,
        route_operation=operation,
        route_variable=route_variable,
        target=target,
        registry=registry,
        verifier=verifier,
        replay=replay,
    )
    return _response(status, body)


def _build_variable_routes_from_registry(
    *,
    target: NodeControlTarget,
    registry: dict[
        str,
        tuple[object, ControlPlaneVariableDescriptor, NodeControlResultCodec],
    ],
    verifier: Ed25519WorkloadNodeControlVerifier,
    replay: _ProcessLocalNodeControlReplay,
) -> tuple[object, ...]:
    if (
        type(target) is not NodeControlTarget
        or type(registry) is not dict
        or type(verifier) is not Ed25519WorkloadNodeControlVerifier
        or type(replay) is not _ProcessLocalNodeControlReplay
    ):
        raise ValueError("FastAPI variable route construction is invalid")

    router = APIRouter()

    async def read_variable(variable_name: str, request: Request) -> Response:
        return await _handle(
            request,
            variable_name,
            NodeControlOperation.READ_STATE,
            target=target,
            registry=registry,
            verifier=verifier,
            replay=replay,
        )

    async def apply_command(variable_name: str, request: Request) -> Response:
        return await _handle(
            request,
            variable_name,
            NodeControlOperation.APPLY_COMMAND,
            target=target,
            registry=registry,
            verifier=verifier,
            replay=replay,
        )

    router.add_api_route(
        "/__control/variables/{variable_name}",
        read_variable,
        methods=["GET"],
        name="read-variable",
        include_in_schema=False,
    )
    router.add_api_route(
        "/__control/variables/{variable_name}/commands",
        apply_command,
        methods=["POST"],
        name="apply-variable-command",
        include_in_schema=False,
    )
    return tuple(router.routes)


def _build_variable_routes(
    *,
    target: NodeControlTarget,
    declaration: WorkloadNodeControlSurfaceDeclaration,
    variables: tuple[object, ...],
    verifier: Ed25519WorkloadNodeControlVerifier,
    replay: _ProcessLocalNodeControlReplay,
) -> tuple[object, ...]:
    if (
        type(target) is not NodeControlTarget
        or type(declaration) is not WorkloadNodeControlSurfaceDeclaration
        or type(variables) is not tuple
        or type(verifier) is not Ed25519WorkloadNodeControlVerifier
        or type(replay) is not _ProcessLocalNodeControlReplay
        or target.provider_socket_name != declaration.surface.provider_socket_name
    ):
        raise ValueError("FastAPI variable route construction is invalid")
    registry = _build_variable_registry(
        declaration=declaration,
        variables=variables,
    )
    return _build_variable_routes_from_registry(
        target=target,
        registry=registry,
        verifier=verifier,
        replay=replay,
    )


__all__: list[str] = []
