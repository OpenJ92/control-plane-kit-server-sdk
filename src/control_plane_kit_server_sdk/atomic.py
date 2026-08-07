"""Process-local atomic implementation of the control-plane variable protocol."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock

from control_plane_kit_core import (
    ControlPlaneStateCodec,
    ControlPlaneVariableDescriptor,
    MapControlState,
    NodeControlCommandRequest,
    NodeControlEvidence,
    NodeControlEvidenceCode,
    NodeControlFailed,
    NodeControlOperation,
    NodeControlReadStateSucceeded,
    NodeControlRejected,
    NodeControlTransitionSucceeded,
    ScalarControlState,
    WeightedRoutingControlState,
)
from control_plane_kit_server_sdk.context import ControlPlaneInvocationContext


_MAX_SAFE_VERSION = 2**53 - 1
_STATE_TYPES = (
    ScalarControlState,
    MapControlState,
    WeightedRoutingControlState,
)
_STATE_CODEC_TYPES = {
    ControlPlaneStateCodec.SCALAR_V1: ScalarControlState,
    ControlPlaneStateCodec.MAP_V1: MapControlState,
    ControlPlaneStateCodec.WEIGHTED_ROUTING_V1: WeightedRoutingControlState,
}


@dataclass(frozen=True, slots=True)
class _AtomicSnapshot:
    state: ScalarControlState | MapControlState | WeightedRoutingControlState
    version: int


class AtomicControlPlaneVariable:
    """One process-local atomic variable over exact core contract values."""

    __slots__ = ("_descriptor", "_lock", "_snapshot")

    def __init__(
        self,
        descriptor: ControlPlaneVariableDescriptor,
        initial_state: (
            ScalarControlState | MapControlState | WeightedRoutingControlState
        ),
        *,
        initial_version: int = 0,
    ) -> None:
        if type(descriptor) is not ControlPlaneVariableDescriptor:
            raise TypeError(
                "atomic variable descriptor must be ControlPlaneVariableDescriptor"
            )
        if type(initial_state) not in _STATE_TYPES:
            raise TypeError("atomic variable state must be an exact control state")
        if type(initial_state) is not _STATE_CODEC_TYPES[descriptor.state_codec]:
            raise TypeError(
                "atomic variable state does not match descriptor state codec"
            )
        if (
            type(initial_version) is not int
            or initial_version < 0
            or initial_version > _MAX_SAFE_VERSION
        ):
            raise ValueError(
                "atomic variable initial_version must be a bounded "
                "nonnegative integer"
            )
        self._descriptor = descriptor
        self._lock = Lock()
        self._snapshot = _AtomicSnapshot(initial_state, initial_version)

    def descriptor(self) -> ControlPlaneVariableDescriptor:
        return self._descriptor

    def read(
        self,
        context: ControlPlaneInvocationContext,
    ) -> NodeControlReadStateSucceeded | NodeControlFailed:
        request = context.request
        try:
            matches_variable = bool(
                request.variable_name == self._descriptor.variable_name
            )
        except Exception:
            matches_variable = False
        if (
            request.operation is not NodeControlOperation.READ_STATE
            or not matches_variable
        ):
            return NodeControlFailed(
                request_id=request.request_id,
                operation=NodeControlOperation.READ_STATE,
            )
        with self._lock:
            snapshot = self._snapshot
        return NodeControlReadStateSucceeded(
            request_id=request.request_id,
            state_codec=self._descriptor.state_codec,
            version=snapshot.version,
            state=snapshot.state,
        )

    def apply(
        self,
        command: NodeControlCommandRequest,
        context: ControlPlaneInvocationContext,
    ) -> NodeControlTransitionSucceeded | NodeControlRejected | NodeControlFailed:
        request = context.request
        if command is not request:
            return NodeControlRejected(
                request_id=request.request_id,
                operation=NodeControlOperation.APPLY_COMMAND,
                evidence=NodeControlEvidence(NodeControlEvidenceCode.INVALID_COMMAND),
            )

        try:
            matches_variable = bool(
                request.variable_name == self._descriptor.variable_name
            )
        except Exception:
            matches_variable = False
        apply_contract = self._descriptor.contract_for(
            NodeControlOperation.APPLY_COMMAND
        )
        expected_state_type = _STATE_CODEC_TYPES[self._descriptor.state_codec]
        if (
            request.operation is not NodeControlOperation.APPLY_COMMAND
            or not matches_variable
            or request.command_codec is not apply_contract.command_codec
            or request.payload is None
            or request.payload.codec is not apply_contract.command_codec
            or type(request.payload.state) is not expected_state_type
            or request.precondition is None
        ):
            return NodeControlRejected(
                request_id=request.request_id,
                operation=NodeControlOperation.APPLY_COMMAND,
                evidence=NodeControlEvidence(NodeControlEvidenceCode.INVALID_COMMAND),
            )

        candidate_state = request.payload.state
        with self._lock:
            captured_snapshot = self._snapshot
            precondition_is_stale = (
                request.precondition.expected_version != captured_snapshot.version
            )
        if precondition_is_stale:
            return NodeControlRejected(
                request_id=request.request_id,
                operation=NodeControlOperation.APPLY_COMMAND,
                evidence=NodeControlEvidence(
                    NodeControlEvidenceCode.PRECONDITION_FAILED
                ),
            )

        try:
            states_are_equal = bool(candidate_state == captured_snapshot.state)
        except Exception:
            return NodeControlFailed(
                request_id=request.request_id,
                operation=NodeControlOperation.APPLY_COMMAND,
            )

        next_snapshot: _AtomicSnapshot | None = None
        if states_are_equal:
            result: NodeControlTransitionSucceeded | NodeControlFailed = (
                NodeControlTransitionSucceeded(
                    request_id=request.request_id,
                    version=captured_snapshot.version,
                    evidence=NodeControlEvidence(NodeControlEvidenceCode.NO_CHANGE),
                )
            )
        elif captured_snapshot.version == _MAX_SAFE_VERSION:
            result = NodeControlFailed(
                request_id=request.request_id,
                operation=NodeControlOperation.APPLY_COMMAND,
            )
        else:
            next_snapshot = _AtomicSnapshot(
                candidate_state,
                captured_snapshot.version + 1,
            )
            result = NodeControlTransitionSucceeded(
                request_id=request.request_id,
                version=next_snapshot.version,
                evidence=NodeControlEvidence(NodeControlEvidenceCode.APPLIED),
            )

        with self._lock:
            snapshot_changed = self._snapshot is not captured_snapshot
            if not snapshot_changed and next_snapshot is not None:
                self._snapshot = next_snapshot
        if snapshot_changed:
            return NodeControlRejected(
                request_id=request.request_id,
                operation=NodeControlOperation.APPLY_COMMAND,
                evidence=NodeControlEvidence(
                    NodeControlEvidenceCode.PRECONDITION_FAILED
                ),
            )
        return result


__all__ = ["AtomicControlPlaneVariable"]
