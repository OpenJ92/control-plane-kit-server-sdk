"""Private FastAPI interpreter for authenticated variable routes."""

from __future__ import annotations

import json

from fastapi import APIRouter, Request, Response
from fastapi.concurrency import run_in_threadpool

from control_plane_kit_core import (
    ControlPlaneVariableDescriptor,
    NodeControlFailed,
    NodeControlGraphReference,
    NodeControlGraphReferenceRole,
    NodeControlOperation,
    NodeControlReadStateSucceeded,
    NodeControlRejected,
    NodeControlResultCodec,
    NodeControlTarget,
    NodeControlTransitionSucceeded,
    WorkloadNodeControlSurfaceDeclaration,
)
from control_plane_kit_core.node_control import MAX_NODE_CONTROL_PAYLOAD_BYTES
from control_plane_kit_server_sdk._replay import (
    _NodeControlReplayCapacityExhausted,
    _NodeControlReplayConflict,
    _ProcessLocalNodeControlReplay,
)
from control_plane_kit_server_sdk.context import ControlPlaneInvocationContext
from control_plane_kit_server_sdk.verification import (
    Ed25519WorkloadNodeControlVerifier,
    WorkloadNodeControlVerificationError,
)


_MAX_BODY_BYTES = 16_384
_MAX_HEADER_BYTES = 32_768
_MAX_HEADER_COUNT = 64
_MAX_PATH_BYTES = 1_024
_MAX_QUERY_BYTES = 1_024
_READ_RESULTS = (NodeControlReadStateSucceeded, NodeControlRejected, NodeControlFailed)
_APPLY_RESULTS = (NodeControlTransitionSucceeded, NodeControlRejected, NodeControlFailed)
_ERROR_BODIES = {
    400: b'{"code":"node-control.request-invalid"}',
    401: b'{"code":"node-control.credential-rejected"}',
    403: b'{"code":"node-control.target-rejected"}',
    404: b'{"code":"node-control.variable-not-found"}',
    409: b'{"code":"node-control.replay-conflict"}',
    413: b'{"code":"node-control.request-too-large"}',
    500: b'{"code":"node-control.internal-failure"}',
    503: b'{"code":"node-control.replay-capacity"}',
}


class _RequestTooLarge(ValueError):
    pass


class _RequestInvalid(ValueError):
    pass


def _response(status: int, body: bytes) -> Response:
    return Response(content=body, status_code=status, media_type="application/json")


def _error(status: int) -> Response:
    return _response(status, _ERROR_BODIES[status])


def _query_status(query_string: object) -> int | None:
    if type(query_string) is not bytes:
        return 400
    if len(query_string) > _MAX_QUERY_BYTES:
        return 413
    if query_string:
        return 400
    return None


def _credential(headers: object) -> bytes:
    if type(headers) is not list or len(headers) > _MAX_HEADER_COUNT:
        raise _RequestTooLarge
    total = 0
    authorization: list[bytes] = []
    for item in headers:
        if (
            type(item) is not tuple
            or len(item) != 2
            or type(item[0]) is not bytes
            or type(item[1]) is not bytes
        ):
            raise _RequestInvalid
        name, value = item
        total += len(name) + len(value)
        if total > _MAX_HEADER_BYTES:
            raise _RequestTooLarge
        if name.lower() == b"authorization":
            authorization.append(value)
    if len(authorization) != 1:
        raise WorkloadNodeControlVerificationError(
            "workload node-control credential was rejected"
        )
    value = authorization[0]
    prefix = b"Bearer "
    if not value.startswith(prefix) or len(value) == len(prefix):
        raise WorkloadNodeControlVerificationError(
            "workload node-control credential was rejected"
        )
    return value[len(prefix) :]


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


def _compact_result(
    result: object,
    *,
    request_id: str,
    operation: NodeControlOperation,
    codec: NodeControlResultCodec,
) -> bytes:
    allowed = _READ_RESULTS if operation is NodeControlOperation.READ_STATE else _APPLY_RESULTS
    if type(result) not in allowed:
        raise ValueError
    normalized = codec.decode(codec.encode(result))
    if normalized.request_id != request_id or normalized.operation is not operation:
        raise ValueError
    encoded = json.dumps(
        normalized.descriptor(),
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii", errors="strict")
    if not 1 <= len(encoded) <= MAX_NODE_CONTROL_PAYLOAD_BYTES:
        raise ValueError
    return encoded


def _interpret(
    *,
    credential: bytes,
    candidate: bytes | None,
    route_operation: NodeControlOperation,
    route_variable: NodeControlGraphReference,
    target: NodeControlTarget,
    registry: dict[
        str,
        tuple[object, ControlPlaneVariableDescriptor, NodeControlResultCodec],
    ],
    verifier: Ed25519WorkloadNodeControlVerifier,
    replay: _ProcessLocalNodeControlReplay,
) -> tuple[int, bytes]:
    try:
        command = verifier.admit(
            credential,
            route_operation=route_operation,
            route_variable=route_variable,
            candidate=candidate,
        )
    except WorkloadNodeControlVerificationError:
        return 401, _ERROR_BODIES[401]
    except Exception:
        return 500, _ERROR_BODIES[500]

    if command.target != target:
        return 403, _ERROR_BODIES[403]

    registered = registry.get(route_variable.value)
    if registered is None:
        return 404, _ERROR_BODIES[404]
    variable, descriptor, codec = registered
    context = ControlPlaneInvocationContext(command)
    try:
        if route_operation is NodeControlOperation.READ_STATE:
            result = variable.read(context)
        else:
            result = replay.execute(
                command,
                result_codec=codec,
                dispatch=lambda: variable.apply(command, context),
            )
        body = _compact_result(
            result,
            request_id=command.request_id,
            operation=route_operation,
            codec=codec,
        )
    except _NodeControlReplayConflict:
        return 409, _ERROR_BODIES[409]
    except _NodeControlReplayCapacityExhausted:
        return 503, _ERROR_BODIES[503]
    except Exception:
        return 500, _ERROR_BODIES[500]
    return 200, body


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
        _interpret,
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


def _build_variable_registry(
    *,
    declaration: WorkloadNodeControlSurfaceDeclaration,
    variables: tuple[object, ...],
) -> dict[
    str,
    tuple[object, ControlPlaneVariableDescriptor, NodeControlResultCodec],
]:
    if (
        type(declaration) is not WorkloadNodeControlSurfaceDeclaration
        or type(variables) is not tuple
    ):
        raise ValueError("FastAPI variable route registry is invalid")
    declared = {
        descriptor.variable_name.value: descriptor
        for descriptor in declaration.surface.variables
    }
    registry: dict[
        str,
        tuple[object, ControlPlaneVariableDescriptor, NodeControlResultCodec],
    ] = {}
    try:
        for variable in variables:
            descriptor = variable.descriptor()
            if (
                type(descriptor) is not ControlPlaneVariableDescriptor
                or not callable(variable.read)
                or not callable(variable.apply)
                or declared.get(descriptor.variable_name.value) != descriptor
                or descriptor.variable_name.value in registry
            ):
                raise ValueError
            registry[descriptor.variable_name.value] = (
                variable,
                descriptor,
                NodeControlResultCodec(descriptor),
            )
    except Exception:
        raise ValueError("FastAPI variable route registry is invalid") from None
    return registry


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
