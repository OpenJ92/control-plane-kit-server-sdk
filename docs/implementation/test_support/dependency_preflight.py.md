Source: [test_support/dependency_preflight.py](../../../test_support/dependency_preflight.py).
Maintain this document alongside its source file. When the source or relevant imported contracts change, verify and update this companion in the same change.

The guard parses trusted pyproject.toml and requires one exact Core dependency at 95452249d0340707a5cdffe737e34669e9d53165 plus the unchanged ordered direct verification/FastAPI extras. Wrong repositories, mutable/other commits, spellings, missing subdirectory or extras fail closed; this update changes the accepted coordinate, not equality semantics.

The owning test.sh invokes the guard before package build/install in either dependency mode. Local-core still passes metadata preflight first and is separately classified composition evidence. Read/TOML errors are normalized to the CLI's fixed failure and exit2; success reports the coordinate. This does not fetch or authenticate artifact bytes, verify Core provenance or perform signing/credential access.
