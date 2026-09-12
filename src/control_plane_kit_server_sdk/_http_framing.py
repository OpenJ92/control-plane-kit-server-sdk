"""Private bounded byte framing shared by workload HTTP adapters."""
from __future__ import annotations

from control_plane_kit_server_sdk.verification import WorkloadNodeControlVerificationError

_MAX_BODY_BYTES = 16_384
_MAX_HEADER_BYTES = 32_768
_MAX_HEADER_COUNT = 64
_MAX_PATH_BYTES = 1_024
_MAX_QUERY_BYTES = 1_024
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


__all__: list[str] = []
