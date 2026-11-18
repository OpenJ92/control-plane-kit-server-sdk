# Decision 0018: Passive standard-library control host

Status: Implemented for SDK #27; owning evidence and independent review belong
in the PR before acceptance. Base73883b4 consumes #26; Core95452249 is unchanged.

The optional `stdlib.install_cpk_control_routes` requires explicit
`reserve_control_namespace=True` and the same receiving target/declaration/
variable/verifier/health arguments as FastAPI. It accepts exact HTTPServer or
ThreadingHTTPServer with an open unbound, nonlistening IPv4 stream socket and
a supported BaseHTTPRequestHandler subclass. It rejects custom servers/TLS,
bound/closed sockets, reinstallation and overridden low-level parser/lifecycle/
response hooks. Application do_* methods, helpers, log_message and ordinary
HTTP/1.0 or 1.1 handler protocol configuration remain owned by the application.

All host/configuration checks precede descriptor preparation. The accepted
shared owner snapshots once and holds private receiving state; a derived
handler captures it and the exact server identity in closures. One
RequestHandlerClass assignment publishes the result, without editing the
application class, opening a listener or starting a thread/callback. Copying
that handler to another server cannot reuse protected authority. Product code
alone owns bind, activation, serving, deadlines, shutdown and server_close.

Reservation happens in the supported parse hook before normalizing or invoking
application methods. Lexical classification follows the host's Latin-1 word
splitting, including its non-ASCII whitespace, so alternate separators cannot
hide a parsed control target. Canonical control requests must contain exactly
three words with HTTP/1.0 or HTTP/1.1. Legacy/invalid versions get a fixed direct
HTTP/1.0 error frame, bypassing the base handler's HTTP/0.9 header suppression;
non-control legacy behavior is unchanged. Parser/Expect rejection on the
reserved branch is fixed and does not invoke application request logging.

The private classifier never supplies a normalized accepted path. It projects
literal query/fragment-free absolute HTTP(S) targets to their paths, checks
raw namespace ownership before slash folding and after dot-segment reduction,
and repeats these checks after each percent-decode pass. Ownership cannot be
erased by later normalization. At most 16 non-growing linear passes operate
within the host's 65536-byte target bound. Remaining valid escapes at the
budget limit reject terminally, even if the eventual path would be non-control;
this explicit ambiguity exception limits application compatibility. Stable
disjoint targets and prefix lookalikes go unchanged to the application.

Only raw canonical control routes are dispatched. Unknown paths, aliases,
query/fragment delimiters (including an empty query delimiter), wrong methods
and framing/admission failures are terminal; none falls through to forwarding.
Duplicate headers are preserved. Existing byte limits and Bearer extraction
are reused. Transfer-Encoding and Expect reject. Content-Length must be absent
or one canonical bounded decimal; reads require zero and never wait for a
forbidden body. APPLY reads exactly its bounded candidate; premature EOF
rejects before admission. Host header buffering and elapsed input/callback
time are separate from these byte admission limits and remain host concerns.

All control responses use fixed HTTP/1.0 status/JSON/length/no-store/close
framing, with no body for HEAD. Adapter framing/route/auth/handler errors use
fixed node-control codes; they are not Core semantic health outcomes. Static
and variable interpretation reuse their existing exact result/error bytes;
health uses the accepted neutral dispatcher and canonical correlated Core
bytes. No health cache, extra verifier, retry or new replay state machine is
introduced. The response closes its connection so unread bytes cannot become
an application request. Ordinary response headers, payloads, Expect and
keepalive stay with the original handler.

Ordinary callback exceptions become fixed failures. BaseException is outside
that normalization. Lost response writes close without retry; an admitted
callback may finish after disconnect. HTTPServer is synchronous and the
standard threaded server supplies concurrency. No SDK cancellation, timeout,
threadpool, listener manager or native supervisor is promised.

Nine proportional test cases run solely inside the ordinary Docker test.sh
suite using ephemeral loopback sockets, with no published port or separate
harness. They exercise real signed admission/results, body/protocol/alias
denials, mixed replay, isolation, application preservation and lifecycle.
Test hosts deliberately use non-daemon request workers so server_close joins
them after bounded callbacks are released; shutdown runs outside serve_forever.
Bind-failure cleanup remains explicit and product-owned. The verification-only
installed probe imports stdlib without FastAPI/Starlette/AnyIO.

Security/history: local application code and configuration are trusted, not
sandboxed. Inbound credentials are checked by caller-supplied verifiers; the
adapter does not load keys or credentials from files or providers. No graph/provider
authority, durable SDK history, key custody, product adoption, native process,
image publication or live acceptance exists here. Native lifecycle gates remain
with Servers #187/#188 after Python product adoption; custom router/multiplexer
host replacement requires their own compatibility tests. SDK #21 closes only
after owning tests, independent review and North's acceptance.
