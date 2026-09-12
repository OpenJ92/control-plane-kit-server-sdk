"""Private prepared receiving context and existing synchronous interpretation."""
from __future__ import annotations

from dataclasses import dataclass, field
import json

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
    WorkloadNodeControlSurfaceDeclarationProfile,
    NodeControlSurfaceReadKind,
    NodeControlSurfaceReadResultCodec,
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
    Ed25519WorkloadNodeControlSurfaceReadVerifier,
    WorkloadNodeControlSurfaceReadVerificationError,
    WorkloadNodeControlVerificationError,
)
from control_plane_kit_server_sdk._http_framing import _ERROR_BODIES
from control_plane_kit_server_sdk.health import WorkloadNodeHealthReadDispatcher

_READ_RESULTS = (NodeControlReadStateSucceeded, NodeControlRejected, NodeControlFailed)
_APPLY_RESULTS = (NodeControlTransitionSucceeded, NodeControlRejected, NodeControlFailed)


@dataclass(frozen=True, slots=True)
class _PreparedControlDispatch:
    """One installation's trusted receiving context; not a public protocol."""

    target: NodeControlTarget = field(repr=False)
    declaration: WorkloadNodeControlSurfaceDeclaration = field(repr=False)
    registry: dict[str, tuple[object, ControlPlaneVariableDescriptor, NodeControlResultCodec]] = field(repr=False)
    installed_variable_names: tuple[NodeControlGraphReference, ...] = field(repr=False)
    command_verifier: Ed25519WorkloadNodeControlVerifier | None = field(repr=False)
    surface_read_verifier: Ed25519WorkloadNodeControlSurfaceReadVerifier = field(repr=False)
    health_dispatcher: WorkloadNodeHealthReadDispatcher | None = field(repr=False)
    replay: _ProcessLocalNodeControlReplay | None = field(repr=False)


def _validate_control_configuration(
    *, target: object, declaration: object, variables: object,
    command_verifier: object, surface_read_verifier: object, health_dispatcher: object,
) -> tuple[bool, bool]:
    """Validate without invoking descriptors, before host collision checks."""
    if (
        type(target) is not NodeControlTarget
        or type(declaration) is not WorkloadNodeControlSurfaceDeclaration
        or type(variables) is not tuple
        or type(surface_read_verifier) is not Ed25519WorkloadNodeControlSurfaceReadVerifier
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
    return has_variables, has_health


def _prepare_control_dispatch(
    *, target: NodeControlTarget, declaration: WorkloadNodeControlSurfaceDeclaration,
    variables: tuple[object, ...], command_verifier: Ed25519WorkloadNodeControlVerifier | None,
    surface_read_verifier: Ed25519WorkloadNodeControlSurfaceReadVerifier,
    health_dispatcher: WorkloadNodeHealthReadDispatcher | None,
) -> _PreparedControlDispatch:
    has_variables, _ = _validate_control_configuration(
        target=target, declaration=declaration, variables=variables,
        command_verifier=command_verifier, surface_read_verifier=surface_read_verifier,
        health_dispatcher=health_dispatcher,
    )
    registry = _build_variable_registry(declaration=declaration, variables=variables)
    installed_variable_names = tuple(
        NodeControlGraphReference(NodeControlGraphReferenceRole.VARIABLE, name)
        for name in sorted(registry)
    )
    return _PreparedControlDispatch(
        target, declaration, registry, installed_variable_names,
        command_verifier, surface_read_verifier, health_dispatcher,
        _ProcessLocalNodeControlReplay() if has_variables else None,
    )


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


def _interpret_variable(
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


__all__: list[str] = []
