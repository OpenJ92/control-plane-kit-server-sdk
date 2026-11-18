"""Private bodyless fixed-route HTTP sample adapter."""
from fastapi import APIRouter, Request, Response
from fastapi.concurrency import run_in_threadpool

from control_plane_kit_core.control_routes import HTTP_VERIFICATION_SAMPLE_ROUTES
from control_plane_kit_server_sdk._http_framing import (
    _credential, _query_status, _RequestInvalid, _RequestTooLarge,
)
from control_plane_kit_server_sdk.verification import WorkloadNodeControlVerificationError
from control_plane_kit_server_sdk.http_samples import HttpVerificationSampleCredentialError

_ERRORS = {400: b'{"code":"http-sample.request-invalid"}',
           401: b'{"code":"http-sample.credential-rejected"}',
           413: b'{"code":"http-sample.request-too-large"}',
           500: b'{"code":"http-sample.internal-failure"}'}


def _response(status, body=None):
    return Response(_ERRORS[status] if body is None else body, status_code=status,
                    media_type="application/json", headers={"Cache-Control": "no-store"})


def _interpret(receiver, credential):
    try:
        return 200, receiver.read(credential)
    except HttpVerificationSampleCredentialError:
        return 401, _ERRORS[401]
    except Exception:
        return 500, _ERRORS[500]


def _build_http_sample_routes(receiver):
    router = APIRouter()
    route = HTTP_VERIFICATION_SAMPLE_ROUTES.routes[0]

    async def read(request: Request):
        if request.scope.get("raw_path") != route.path.encode("ascii") or request.method != "GET":
            return _response(400)
        query = _query_status(request.scope.get("query_string"))
        if query is not None:
            return _response(query)
        try:
            headers = request.scope.get("headers")
            credential = _credential(headers)
            lengths = [value for name, value in headers if name.lower() == b"content-length"]
            if (any(name.lower() in (b"transfer-encoding", b"expect") for name, _ in headers)
                    or len(lengths) > 1 or lengths and lengths != [b"0"]):
                raise _RequestInvalid
            async for chunk in request.stream():
                if type(chunk) is not bytes or chunk:
                    raise _RequestInvalid
        except _RequestTooLarge:
            return _response(413)
        except WorkloadNodeControlVerificationError:
            return _response(401)
        except Exception:
            return _response(400)
        status, body = await run_in_threadpool(_interpret, receiver, credential)
        return _response(status, body)

    router.add_api_route(route.path, read, methods=[route.method.value],
                         name=route.name, include_in_schema=False)
    return tuple(router.routes)
