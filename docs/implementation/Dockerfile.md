Source: [Dockerfile](../../Dockerfile).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

The package stage uses python:3.14-slim by default, copies package metadata,
governance/docs and src into /app, then installs the SDK with --no-deps. The
derived test stage adds tests and two installed-extra probes. Its default CMD
discovers unittest tests, but the [authoritative gate](test.sh.md) overrides that
command with installation/probe phases and runs the behavioral suite only in
the FastAPI-extra container.

The initial --no-deps install does not provide Core or either optional extra.
Invoking the image's default CMD alone is therefore not equivalent to the gate.
The build may still resolve setuptools/build requirements; --no-deps is not a
network-isolation switch. Python's base tag and build requirements do not make
the image reproducible by digest.

This is a package-validation image with source/tests present, not a deployed
workload server. It defines no USER override, listener, credential provisioning
or publication destination. Read-only support mounts and final container/image
cleanup belong to the gate, while [.dockerignore](.dockerignore.md) determines
which local files can enter the build context.

[Gate-contract tests](test_support/tests/test_gate_contract.py.md) inspect stages,
COPY statements, install command and ignore rules. They protect textual build
shape; a successful build/install requires a separate Docker-backed run.
