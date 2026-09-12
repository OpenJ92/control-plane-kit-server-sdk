"""Private bounded reservation and synchronous stdlib request interpretation."""
from __future__ import annotations

from http import HTTPStatus
import re
from urllib.parse import unquote_to_bytes

from control_plane_kit_core import (
    NodeControlGraphReference, NodeControlGraphReferenceRole, NodeControlOperation,
    NodeControlSurfaceReadKind, NodeHealthReadKind,
)
from control_plane_kit_server_sdk._control_dispatch import (
    _PreparedControlDispatch, _interpret_surface_read, _interpret_variable,
)
from control_plane_kit_server_sdk._http_framing import (
    _ERROR_BODIES, _MAX_BODY_BYTES, _MAX_PATH_BYTES,
    _RequestInvalid, _RequestTooLarge, _credential,
)
from control_plane_kit_server_sdk.verification import (
    WorkloadNodeControlVerificationError, WorkloadNodeHealthReadVerificationError,
)


_ESCAPE = re.compile(br"%[0-9a-fA-F]{2}")
_LENGTH = re.compile(br"(?:0|[1-9][0-9]*)")
_MAX_TARGET_BYTES = 65_536
_MAX_ALIAS_PASSES = 16


def _reserved(path: bytes) -> bool:
    return path == b"/__control" or path.startswith(b"/__control/")


def _owns_path(path: bytes) -> bool:
    if _reserved(path):
        return True
    if not path.startswith(b"/"):
        return False
    segments = [segment for segment in path.split(b"/") if segment]
    if segments and segments[0] == b"__control":
        return True
    reduced: list[bytes] = []
    for segment in segments:
        if segment == b"..":
            if reduced:
                reduced.pop()
        elif segment != b".":
            reduced.append(segment)
    return bool(reduced) and reduced[0] == b"__control"


def _control_target(target: bytes) -> bool:
    """True means terminal SDK ownership/ambiguity, never normalized acceptance."""
    if len(target) > _MAX_TARGET_BYTES:
        return True
    path = target.split(b"?", 1)[0].split(b"#", 1)[0]
    for scheme in (b"http://", b"https://"):
        if path[:len(scheme)].lower() == scheme:
            _authority, separator, tail = path[len(scheme):].partition(b"/")
            path = b"/" + tail if separator else b"/"
            break
    for _ in range(_MAX_ALIAS_PASSES):
        if _owns_path(path):
            return True
        if _ESCAPE.search(path) is None:
            return False
        path = unquote_to_bytes(path)
    return _owns_path(path) or _ESCAPE.search(path) is not None


def _finish(handler: object, status: int, body: bytes) -> None:
    """Write fixed framing without stdlib's request logging or 0.9 suppression."""
    handler.close_connection = True
    frame = (
        f"HTTP/1.0 {status} {HTTPStatus(status).phrase}\r\n"
        "Content-Type: application/json\r\n"
        f"Content-Length: {len(body)}\r\n"
        "Cache-Control: no-store\r\nConnection: close\r\n\r\n"
    ).encode("ascii")
    if getattr(handler, "_cpk_method", b"") != b"HEAD":
        frame += body
    try:
        handler.wfile.write(frame)
        handler.wfile.flush()
    except OSError:
        # A completed callback is not retried after a lost response.
        pass


def _error(handler: object, status: int) -> None:
    if status == 405:
        body = b'{"code":"node-control.method-not-allowed"}'
    elif status == 404:
        body = b'{"code":"node-control.route-not-found"}'
    else:
        body = _ERROR_BODIES[status]
    _finish(handler, status, body)


def _request_input(handler: object, *, read: bool) -> tuple[bytes, bytes | None]:
    try:
        headers = [(name.encode("latin-1"), value.encode("latin-1"))
                   for name, value in handler.headers.raw_items()]
        credential = _credential(headers)
        if any(name.lower() in (b"transfer-encoding", b"expect") for name, _ in headers):
            raise _RequestInvalid
        lengths = [value for name, value in headers if name.lower() == b"content-length"]
        if len(lengths) > 1:
            raise _RequestInvalid
        value = lengths[0] if lengths else b"0"
        if _LENGTH.fullmatch(value) is None:
            raise _RequestInvalid
        if len(value) > 5 or int(value) > _MAX_BODY_BYTES:
            raise _RequestTooLarge
        length = int(value)
        if read:
            if length:
                raise _RequestInvalid
            return credential, None
        candidate = handler.rfile.read(length) if length else b""
        if type(candidate) is not bytes or len(candidate) != length:
            raise _RequestInvalid
        return credential, candidate
    except (_RequestInvalid, _RequestTooLarge, WorkloadNodeControlVerificationError):
        raise
    except Exception:
        raise _RequestInvalid from None


def _dispatch(handler: object, control: _PreparedControlDispatch) -> None:
    target = handler._cpk_target
    if len(target) > _MAX_PATH_BYTES:
        _error(handler, 413)
        return
    if b"?" in target or b"#" in target or b"%" in target:
        _error(handler, 400)
        return
    method = handler._cpk_method
    static_paths = {
        b"/__control/capabilities": NodeControlSurfaceReadKind.CAPABILITIES,
        b"/__control/status": NodeControlSurfaceReadKind.STATUS,
    }
    kind = static_paths.get(target)
    health_kind = None
    operation = None
    variable = None
    if kind is not None:
        expected_method = b"GET"
    elif target in (b"/__control/health/liveness", b"/__control/health/readiness"):
        if control.health_dispatcher is None:
            _error(handler, 404)
            return
        health_kind = NodeHealthReadKind(target.rsplit(b"/", 1)[1].decode("ascii"))
        expected_method = b"GET"
    else:
        parts = target.split(b"/")
        if (control.replay is None or len(parts) not in (4, 5)
                or parts[:3] != [b"", b"__control", b"variables"]
                or (len(parts) == 5 and parts[4] != b"commands")):
            _error(handler, 404)
            return
        try:
            variable = NodeControlGraphReference(NodeControlGraphReferenceRole.VARIABLE,
                                                 parts[3].decode("ascii"))
        except Exception:
            _error(handler, 400)
            return
        operation = (NodeControlOperation.READ_STATE if len(parts) == 4
                     else NodeControlOperation.APPLY_COMMAND)
        expected_method = b"GET" if len(parts) == 4 else b"POST"
    if method != expected_method:
        _error(handler, 405)
        return
    try:
        credential, candidate = _request_input(handler, read=expected_method == b"GET")
    except _RequestTooLarge:
        _error(handler, 413)
        return
    except WorkloadNodeControlVerificationError:
        _error(handler, 401)
        return
    except Exception:
        _error(handler, 400)
        return
    try:
        if kind is not None:
            status, body = _interpret_surface_read(
                credential=credential, route_kind=kind, target=control.target,
                declaration=control.declaration, installed_variable_names=control.installed_variable_names,
                verifier=control.surface_read_verifier,
            )
        elif health_kind is not None:
            result = control.health_dispatcher.read(credential, route_kind=health_kind, candidate=None)
            status, body = 200, result.canonical_bytes()
        else:
            status, body = _interpret_variable(
                credential=credential, candidate=candidate, route_operation=operation,
                route_variable=variable, target=control.target, registry=control.registry,
                verifier=control.command_verifier, replay=control.replay,
            )
    except WorkloadNodeHealthReadVerificationError:
        _error(handler, 401)
        return
    except Exception:
        _error(handler, 500)
        return
    _finish(handler, status, body)


__all__: list[str] = []
