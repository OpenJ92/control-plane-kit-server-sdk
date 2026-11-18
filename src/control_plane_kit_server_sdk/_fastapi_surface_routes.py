"""Private FastAPI interpreter for authenticated surface-read routes."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response
from fastapi.concurrency import run_in_threadpool

from control_plane_kit_core import NodeControlSurfaceReadKind
from control_plane_kit_server_sdk._control_dispatch import (
    _PreparedControlDispatch, _interpret_surface_read,
)
from control_plane_kit_server_sdk._fastapi_variable_routes import _body, _error, _response
from control_plane_kit_server_sdk._http_framing import (
    _MAX_PATH_BYTES, _RequestInvalid, _RequestTooLarge, _credential, _query_status,
)
from control_plane_kit_server_sdk.verification import (
    WorkloadNodeControlVerificationError,
    WorkloadNodeControlSurfaceReadVerificationError,
)


async def _handle_surface_read(
    request: Request,
    route_kind: NodeControlSurfaceReadKind,
    *,
    control: _PreparedControlDispatch,
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
        target=control.target,
        declaration=control.declaration,
        installed_variable_names=control.installed_variable_names,
        verifier=control.surface_read_verifier,
    )
    return _response(status, body)


def _build_surface_routes(*, control: _PreparedControlDispatch) -> tuple[object, ...]:
    if type(control) is not _PreparedControlDispatch:
        raise ValueError("FastAPI surface route construction is invalid")
    router = APIRouter()

    async def surface_capabilities(request: Request) -> Response:
        return await _handle_surface_read(
            request,
            NodeControlSurfaceReadKind.CAPABILITIES,
            control=control,
        )

    async def surface_status(request: Request) -> Response:
        return await _handle_surface_read(
            request,
            NodeControlSurfaceReadKind.STATUS,
            control=control,
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
