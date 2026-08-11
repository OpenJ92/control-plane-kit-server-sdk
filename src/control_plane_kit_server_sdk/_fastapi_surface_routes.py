"""Private FastAPI interpreter for authenticated surface-read routes."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response
from fastapi.concurrency import run_in_threadpool

from control_plane_kit_core import (
    ControlPlaneVariableDescriptor,
    NodeControlGraphReference,
    NodeControlGraphReferenceRole,
    NodeControlResultCodec,
    NodeControlSurfaceReadKind,
    NodeControlSurfaceReadResultCodec,
    NodeControlTarget,
    WorkloadNodeControlSurfaceDeclaration,
)
from control_plane_kit_server_sdk._fastapi_variable_routes import (
    _ERROR_BODIES,
    _MAX_PATH_BYTES,
    _RequestInvalid,
    _RequestTooLarge,
    _body,
    _credential,
    _error,
    _query_status,
    _response,
)
from control_plane_kit_server_sdk.verification import (
    Ed25519WorkloadNodeControlSurfaceReadVerifier,
    WorkloadNodeControlVerificationError,
    WorkloadNodeControlSurfaceReadVerificationError,
)


def _interpret_surface_read(
    *,
    credential: bytes,
    route_kind: NodeControlSurfaceReadKind,
    target: NodeControlTarget,
    declaration: WorkloadNodeControlSurfaceDeclaration,
    installed_variable_names: tuple[NodeControlGraphReference, ...],
    verifier: Ed25519WorkloadNodeControlSurfaceReadVerifier,
) -> tuple[int, bytes]:
    try:
        request = verifier.admit(
            credential,
            route_kind=route_kind,
            candidate=None,
        )
    except WorkloadNodeControlSurfaceReadVerificationError:
        return 401, _ERROR_BODIES[401]
    except Exception:
        return 500, _ERROR_BODIES[500]

    if (
        request.target != target
        or request.declaration_identity != declaration.identity()
    ):
        return 403, _ERROR_BODIES[403]

    try:
        codec = NodeControlSurfaceReadResultCodec(request, declaration)
        if route_kind is NodeControlSurfaceReadKind.CAPABILITIES:
            result = codec.capabilities_result()
        else:
            result = codec.status_result(installed_variable_names)
        body = result.canonical_bytes()
        if type(body) is not bytes:
            raise ValueError
    except Exception:
        return 500, _ERROR_BODIES[500]
    return 200, body


async def _handle_surface_read(
    request: Request,
    route_kind: NodeControlSurfaceReadKind,
    *,
    target: NodeControlTarget,
    declaration: WorkloadNodeControlSurfaceDeclaration,
    installed_variable_names: tuple[NodeControlGraphReference, ...],
    verifier: Ed25519WorkloadNodeControlSurfaceReadVerifier,
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
        if await _body(request):
            return _error(400)
    except _RequestTooLarge:
        return _error(413)
    except (
        WorkloadNodeControlVerificationError,
        WorkloadNodeControlSurfaceReadVerificationError,
    ):
        return _error(401)
    except _RequestInvalid:
        return _error(400)
    except Exception:
        return _error(400)

    status, body = await run_in_threadpool(
        _interpret_surface_read,
        credential=credential,
        route_kind=route_kind,
        target=target,
        declaration=declaration,
        installed_variable_names=installed_variable_names,
        verifier=verifier,
    )
    return _response(status, body)


def _build_surface_routes(
    *,
    target: NodeControlTarget,
    declaration: WorkloadNodeControlSurfaceDeclaration,
    registry: dict[
        str,
        tuple[object, ControlPlaneVariableDescriptor, NodeControlResultCodec],
    ],
    verifier: Ed25519WorkloadNodeControlSurfaceReadVerifier,
) -> tuple[object, ...]:
    if (
        type(target) is not NodeControlTarget
        or type(declaration) is not WorkloadNodeControlSurfaceDeclaration
        or type(registry) is not dict
        or type(verifier) is not Ed25519WorkloadNodeControlSurfaceReadVerifier
        or target.provider_socket_name != declaration.surface.provider_socket_name
    ):
        raise ValueError("FastAPI surface route construction is invalid")
    installed_variable_names = tuple(
        NodeControlGraphReference(NodeControlGraphReferenceRole.VARIABLE, name)
        for name in sorted(registry)
    )
    router = APIRouter()

    async def surface_capabilities(request: Request) -> Response:
        return await _handle_surface_read(
            request,
            NodeControlSurfaceReadKind.CAPABILITIES,
            target=target,
            declaration=declaration,
            installed_variable_names=installed_variable_names,
            verifier=verifier,
        )

    async def surface_status(request: Request) -> Response:
        return await _handle_surface_read(
            request,
            NodeControlSurfaceReadKind.STATUS,
            target=target,
            declaration=declaration,
            installed_variable_names=installed_variable_names,
            verifier=verifier,
        )

    router.add_api_route(
        "/__control/capabilities",
        surface_capabilities,
        methods=["GET"],
        name="surface-capabilities",
        include_in_schema=False,
    )
    router.add_api_route(
        "/__control/status",
        surface_status,
        methods=["GET"],
        name="surface-status",
        include_in_schema=False,
    )
    return tuple(router.routes)


__all__: list[str] = []
