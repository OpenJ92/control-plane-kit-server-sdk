# Decision 0017: Private shared control preparation and interpretation

Status: Implemented for SDK #26; owning gate and independent review evidence
belong in its PR before acceptance. Base893b99e consumes completed #23;
Core remains95452249d0340707a5cdffe737e34669e9d53165.

The private `_control_dispatch` module now owns the existing variable registry,
result compaction, synchronous static/variable interpretation and one prepared
receiving value per installation. Those interpretation functions are moved,
not reimplemented. `_http_framing` owns the unchanged shared byte limits,
credential/query validation and fixed control error bodies. Neither imports
FastAPI, Starlette or AnyIO. Optional crypto stays outside the SDK root.

`_validate_control_configuration(...)` performs only the accepted type/profile/
authority checks. FastAPI calls it before host collision checks, so invalid
configuration retains its previous precedence and invokes no descriptor.
After collision checks, `_prepare_control_dispatch(...)` revalidates the same
pure conditions and snapshots descriptors once, creates sorted installed names,
and allocates command replay only for legacy/mixed declarations. Its frozen,
redacted `_PreparedControlDispatch` captures target, declaration, registry,
names, verifiers, optional health dispatcher and optional replay. The private
registry remains conventional trusted state, not a hostile-object sandbox.

The existing public FastAPI signature and route shapes are unchanged. Static
routes consume the prepared value; variable routes use its exact registry and
replay, and health routes use its accepted dispatcher. Host validation,
collision classification, route construction/marking, one publication and each
off-loop admission/effect boundary remain FastAPI-owned. The existing private
variable-only builder remains an adapter over the single extracted registry
owner; it is not a public alternative installer or compatibility implementation.

Chosen shape: one private preparation value and fixed existing operations,
rather than a public generic HTTP request algebra, handler registry, second
verifier or duplicated interpretation. Health dispatch and the replay state
machine are unchanged. Static status still reports registry coverage, not
workload health. No new authority, listener, process, provider, credential
custody, durable history or transaction is introduced. Existing callbacks and
APPLY semantics remain workload-owned; representations and HTTP errors stay
bounded and redacted. No health cache or freshness state is added.

Validation preserves the full inherited FastAPI/verification/replay laws. One
focused preparation test protects descriptor timing/single snapshots, per-host
state, redacted/frozen capture and absent health-only command replay. The
existing codec-location assertion follows its moved source owner; behavior is
unchanged. The installed verification-only probe imports the shared owner and
continues to reject framework imports, with its nominal policy fixture updated
accordingly. The authoritative normal pinned Docker test.sh remains unchanged.

Handoff: SDK #27 may consume this private prepared value, static/variable
interpretation and framing together with the accepted neutral health dispatcher.
It owns the separately reviewed stdlib namespace, framing and listener tests;
none of that adapter is implemented here. Product/native/provider/image/live
adoption remains downstream. Touched companions preserve relevant PR19 context
and supersede stale ownership claims with current source truth.
