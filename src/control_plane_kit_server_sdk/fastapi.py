"""Atomic FastAPI composition for the complete CPK control surface."""

from __future__ import annotations

import fastapi
from fastapi.routing import APIRoute, APIRouter, APIWebSocketRoute
from starlette.routing import Host, Mount, Route, WebSocketRoute

from control_plane_kit_core import (
    NodeControlTarget,
    WorkloadNodeControlSurfaceDeclaration,
    WorkloadNodeControlSurfaceDeclarationProfile,
)
from control_plane_kit_core.control_routes import NODE_CONTROL_ROUTES, NODE_HEALTH_ROUTES
from control_plane_kit_server_sdk._fastapi_health_routes import _build_health_routes
from control_plane_kit_server_sdk.health import WorkloadNodeHealthReadDispatcher
from control_plane_kit_server_sdk._fastapi_surface_routes import (
    _build_surface_routes,
)
from control_plane_kit_server_sdk._fastapi_variable_routes import (
    _build_variable_registry,
    _build_variable_routes_from_registry,
)
from control_plane_kit_server_sdk._replay import _ProcessLocalNodeControlReplay
from control_plane_kit_server_sdk.verification import (
    Ed25519WorkloadNodeControlSurfaceReadVerifier,
    Ed25519WorkloadNodeControlVerifier,
)


_MARKER_ATTRIBUTE = "_cpk_control_route_marker"
_MARKER = object()


class _AlreadyInstalled(ValueError):
    pass


class _RouteCollision(ValueError):
    pass


def _literal_first_segment(path: object, *, mount: bool) -> str | None:
    if type(path) is not str or not path.startswith("/"):
        return None
    first = path.split("/", 2)[1]
    if not first:
        return None if mount else ""
    if "{" in first or "}" in first:
        return None
    return first


def _route_is_disjoint(route: object) -> bool:
    route_type = type(route)
    if route_type in (APIRoute, APIWebSocketRoute, Route, WebSocketRoute):
        first = _literal_first_segment(route.path, mount=False)
        return first is not None and first != "__control"
    if route_type is Mount:
        first = _literal_first_segment(route.path, mount=True)
        return first is not None and first != "__control"
    if route_type is Host:
        return False
    return False


def _canonical_route_shape(
    routes: tuple[object, ...], *, variables: bool, health: bool,
) -> bool:
    observed = tuple(
        (route.name, next(iter(route.methods)), route.path)
        for route in routes
    )
    declarations = NODE_CONTROL_ROUTES.routes if variables else NODE_CONTROL_ROUTES.routes[:2]
    if health:
        declarations = (*declarations, *NODE_HEALTH_ROUTES.routes)
    expected = tuple(
        (route.name, route.method.value, route.path)
        for route in declarations
    )
    return observed == expected


def _prepare_installation(
    app: object,
    target: object,
    declaration: object,
    variables: object,
    command_verifier: object,
    surface_read_verifier: object,
    health_dispatcher: object,
) -> tuple[list[object], tuple[object, ...]]:
    if (
        type(app) is not fastapi.FastAPI
        or type(app.router) is not APIRouter
        or type(app.router.routes) is not list
        or app.middleware_stack is not None
        or type(target) is not NodeControlTarget
        or type(declaration) is not WorkloadNodeControlSurfaceDeclaration
        or type(variables) is not tuple
        or type(surface_read_verifier)
        is not Ed25519WorkloadNodeControlSurfaceReadVerifier
        or target.provider_socket_name != declaration.surface.provider_socket_name
    ):
        raise ValueError

    has_health = declaration.profile is WorkloadNodeControlSurfaceDeclarationProfile.V2
    has_variables = not has_health or bool(declaration.surface.variables)
    if has_health:
        if (
            type(health_dispatcher) is not WorkloadNodeHealthReadDispatcher
            or health_dispatcher.target != target
            or health_dispatcher.declaration != declaration
        ):
            raise ValueError
    elif health_dispatcher is not None:
        raise ValueError
    if has_variables:
        if type(command_verifier) is not Ed25519WorkloadNodeControlVerifier:
            raise ValueError
    elif command_verifier is not None or variables:
        raise ValueError

    prior_routes = app.router.routes
    if any(
        getattr(route, _MARKER_ATTRIBUTE, None) is _MARKER
        for route in prior_routes
    ):
        raise _AlreadyInstalled
    if any(not _route_is_disjoint(route) for route in prior_routes):
        raise _RouteCollision

    registry = _build_variable_registry(
        declaration=declaration,
        variables=variables,
    )
    surface_routes = _build_surface_routes(
        target=target,
        declaration=declaration,
        registry=registry,
        verifier=surface_read_verifier,
    )
    variable_routes = ()
    if has_variables:
        variable_routes = _build_variable_routes_from_registry(
            target=target, registry=registry, verifier=command_verifier,
            replay=_ProcessLocalNodeControlReplay(),
        )
    health_routes = _build_health_routes(dispatcher=health_dispatcher) if has_health else ()
    routes = (*surface_routes, *variable_routes, *health_routes)
    if not _canonical_route_shape(routes, variables=has_variables, health=has_health):
        raise ValueError
    for route in routes:
        setattr(route, _MARKER_ATTRIBUTE, _MARKER)
    return prior_routes, routes


def install_cpk_control_routes(
    app: fastapi.FastAPI,
    *,
    target: NodeControlTarget,
    declaration: WorkloadNodeControlSurfaceDeclaration,
    variables: tuple[object, ...] = (),
    command_verifier: Ed25519WorkloadNodeControlVerifier | None = None,
    surface_read_verifier: Ed25519WorkloadNodeControlSurfaceReadVerifier,
    health_dispatcher: WorkloadNodeHealthReadDispatcher | None = None,
) -> None:
    """Install the exact CPK route family with one host-app mutation."""

    outcome: tuple[list[object], tuple[object, ...]] | None = None
    category = "invalid"
    try:
        outcome = _prepare_installation(
            app,
            target,
            declaration,
            variables,
            command_verifier,
            surface_read_verifier,
            health_dispatcher,
        )
    except _AlreadyInstalled:
        category = "installed"
    except _RouteCollision:
        category = "collision"
    except Exception:
        pass
    if outcome is None:
        if category == "installed":
            raise ValueError("FastAPI control routes are already installed")
        if category == "collision":
            raise ValueError("FastAPI host route collides with CPK control routes")
        raise ValueError("FastAPI control route installation is invalid")

    prior_routes, routes = outcome
    app.router.routes = [*prior_routes, *routes]


__all__ = ["install_cpk_control_routes"]
