Source: [src/control_plane_kit_server_sdk/_fastapi_surface_routes.py](../../../../src/control_plane_kit_server_sdk/_fastapi_surface_routes.py).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

This private adapter builds authenticated GET capabilities/status routes for the
public [installer](fastapi.py.md). It captures sorted installed variable names
from the prepared registry and trusted target/declaration references. Status is
registry coverage, not workload health; neither route calls variable.read/apply
or refreshes live descriptors.

Raw path/query checks, a single Bearer credential and streamed bodylessness come
before admission. Shared transport limits are owned by
[_fastapi_variable_routes.py](_fastapi_variable_routes.py.md). One explicit
threadpool call then performs synchronous signature admission, exact receiving
target/declaration comparison and result construction. Failed admission is 401;
a valid credential for another target/declaration is 403 before disclosure.
Other interpretation failures return a fixed 500 body.

The actual Core 0ee72c3 NodeControlSurfaceReadResultCodec binds request and
declaration and creates canonical capabilities/status values with Core-owned
aggregate bounds. This adapter returns those canonical bytes rather than
inventing an application status schema. Repeated valid reads are stateless;
command replay is not applied. Exact candidate=None is supplied only after the
HTTP body check. Routes are hidden from OpenAPI, not from the network.

No graph membership, key issuance, provider read, persistence, transaction or
application health proof is added. Helpers catch ordinary exceptions into fixed
HTTP categories; process-control exceptions are outside that normalization.
See the selected surface assertions in
[control-route tests](../../tests/test_fastapi_control_routes.py.md).
