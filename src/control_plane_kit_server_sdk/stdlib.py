"""Passive installation into a supported, product-owned stdlib HTTP server."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
import socket
from typing import Literal

from control_plane_kit_core import NodeControlTarget, WorkloadNodeControlSurfaceDeclaration
from control_plane_kit_server_sdk._control_dispatch import (
    _prepare_control_dispatch, _validate_control_configuration,
)
from control_plane_kit_server_sdk._stdlib_control import _control_target, _dispatch, _error
from control_plane_kit_server_sdk.health import WorkloadNodeHealthReadDispatcher
from control_plane_kit_server_sdk.verification import (
    Ed25519WorkloadNodeControlSurfaceReadVerifier, Ed25519WorkloadNodeControlVerifier,
)


_MARKER = object()
_MARKER_ATTRIBUTE = "_cpk_stdlib_control_marker"
_STANDARD_HOOKS = (
    "__init__", "setup", "finish", "handle", "handle_one_request", "parse_request",
    "handle_expect_100", "send_error", "send_response", "send_response_only",
    "send_header", "end_headers", "flush_headers",
)


def _validate_host(server: object, reserve_control_namespace: object) -> type[BaseHTTPRequestHandler]:
    if type(server) not in (HTTPServer, ThreadingHTTPServer) or reserve_control_namespace is not True:
        raise ValueError
    connection = server.socket
    if (type(connection) is not socket.socket or connection.fileno() < 0
            or connection.family != socket.AF_INET or connection.type != socket.SOCK_STREAM
            or connection.getsockname()[1] != 0
            or connection.getsockopt(socket.SOL_SOCKET, socket.SO_ACCEPTCONN)):
        raise ValueError
    application_handler = server.RequestHandlerClass
    if (not isinstance(application_handler, type)
            or not issubclass(application_handler, BaseHTTPRequestHandler)
            or getattr(application_handler, _MARKER_ATTRIBUTE, None) is _MARKER
            or application_handler.MessageClass is not BaseHTTPRequestHandler.MessageClass
            or application_handler.protocol_version not in ("HTTP/1.0", "HTTP/1.1")
            or any(getattr(application_handler, name) is not getattr(BaseHTTPRequestHandler, name)
                   for name in _STANDARD_HOOKS)):
        raise ValueError
    return application_handler


def install_cpk_control_routes(
    server: HTTPServer | ThreadingHTTPServer, *, reserve_control_namespace: Literal[True],
    target: NodeControlTarget, declaration: WorkloadNodeControlSurfaceDeclaration,
    variables: tuple[object, ...] = (),
    command_verifier: Ed25519WorkloadNodeControlVerifier | None = None,
    surface_read_verifier: Ed25519WorkloadNodeControlSurfaceReadVerifier,
    health_dispatcher: WorkloadNodeHealthReadDispatcher | None = None,
) -> None:
    """Reserve the control namespace before the product binds/starts its server."""
    prepared_handler = None
    try:
        application_handler = _validate_host(server, reserve_control_namespace)
        _validate_control_configuration(
            target=target, declaration=declaration, variables=variables,
            command_verifier=command_verifier, surface_read_verifier=surface_read_verifier,
            health_dispatcher=health_dispatcher,
        )
        control = _prepare_control_dispatch(
            target=target, declaration=declaration, variables=variables,
            command_verifier=command_verifier, surface_read_verifier=surface_read_verifier,
            health_dispatcher=health_dispatcher,
        )

        class ControlHandler(application_handler):
            def parse_request(self) -> bool:
                self._cpk_owned = False
                # Match the host's Latin-1 word boundaries before it can route
                # a target hidden behind non-ASCII whitespace to application code.
                words = [word.encode("latin-1") for word in
                         self.raw_requestline.decode("latin-1").rstrip("\r\n").split()]
                self._cpk_method = words[0] if words else b""
                self._cpk_target = words[1] if len(words) >= 2 else b""
                if not _control_target(self._cpk_target):
                    return super().parse_request()
                self._cpk_owned = True
                self.close_connection = True
                if len(words) != 3 or words[2] not in (b"HTTP/1.0", b"HTTP/1.1"):
                    _error(self, 400)
                    return False
                if self.server is not server:
                    _error(self, 403)
                    return False
                if not super().parse_request():
                    return False
                _dispatch(self, control)
                return False

            def handle_expect_100(self) -> bool:
                if getattr(self, "_cpk_owned", False):
                    _error(self, 400)
                    return False
                return super().handle_expect_100()

            def send_error(self, code, message=None, explain=None) -> None:
                if getattr(self, "_cpk_owned", False):
                    _error(self, 413 if code in (413, 414, 431) else 400)
                    return
                super().send_error(code, message, explain)

        setattr(ControlHandler, _MARKER_ATTRIBUTE, _MARKER)
        prepared_handler = ControlHandler
    except Exception:
        pass
    if prepared_handler is None:
        raise ValueError("stdlib control route installation is invalid")
    server.RequestHandlerClass = prepared_handler


__all__ = ["install_cpk_control_routes"]
