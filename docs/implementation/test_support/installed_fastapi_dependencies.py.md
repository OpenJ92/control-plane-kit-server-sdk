Source: [installed_fastapi_dependencies.py](../../../test_support/installed_fastapi_dependencies.py).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

After importing the SDK root, this probe requires FastAPI, Starlette, AnyIO,
jwt and cryptography to remain unloaded. It checks distribution metadata for
PyJWT 2.13.0, cryptography 50.0.0, FastAPI 0.141.1 and Starlette 1.6.0, then
imports the public SDK FastAPI adapter and requires its sole __all__ entry to be
install_cpk_control_routes. AnyIO laziness is checked, but its version is not
pinned or checked here.

Successful import establishes availability of the optional adapter surface. It
does not install routes, create an application/listener, exercise authentication
or prove network health. Version strings are not artifact hashes or publisher
attestations. Ordinary exceptions in import/metadata stages and explicit
mismatches return 2 with a fixed rejection line; BaseExceptions and arbitrary
output/effects of trusted imported code are not universally contained.

The [gate](../test.sh.md) runs this from /tmp after the FastAPI installation and
behavioral suite. [Gate-contract tests](tests/test_gate_contract.py.md) substitute
local modules/metadata to test version rejection before optional imports and
bounded probe-emitted diagnostics. Those fixtures do not establish real package
resolution or route behavior; see [the installer](../src/control_plane_kit_server_sdk/fastapi.py.md).
