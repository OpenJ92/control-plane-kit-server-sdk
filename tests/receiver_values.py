"""Small pure receiver premises shared by translated SDK laws."""
import control_plane_kit_core as core


def receiver_context():
    return core.NodeControlAuthorityContext("revision-7", "projection-7")


def receiver_declaration(*, variable="routing", socket="control"):
    ref = core.NodeControlGraphReference
    role = core.NodeControlGraphReferenceRole
    descriptor = core.ControlPlaneVariableDescriptor(
        ref(role.VARIABLE, variable), core.ControlPlaneVariableKind.SCALAR,
        core.ControlPlaneStateCodec.SCALAR_V1,
        (core.ControlPlaneVariableOperationContract(core.NodeControlOperation.READ_STATE, None,
            core.ControlPlaneResultCodec.STATE_V1),
         core.ControlPlaneVariableOperationContract(core.NodeControlOperation.APPLY_COMMAND,
            core.ControlPlaneCommandCodec.REPLACE_SCALAR_V1, core.ControlPlaneResultCodec.TRANSITION_V1)))
    return core.WorkloadNodeControlSurfaceDeclaration(core.WorkloadNodeControlSurfaceDescriptor(
        ref(role.PROVIDER_SOCKET, socket), (descriptor,)))
