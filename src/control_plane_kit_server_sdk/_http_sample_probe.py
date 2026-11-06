"""One bounded numeric-loopback exchange; no credentials, redirects or retries."""
from __future__ import annotations

import re
import socket
import time

from control_plane_kit_core.verification import HttpVerificationEvidence, VerificationOutcome

_TOKEN = re.compile(rb"[!#$%&'*+.^_`|~0-9A-Za-z-]+")
_PATH = re.compile(r"/(?:[A-Za-z0-9._~!$&'()*+,;=:@/-]|%[0-9A-Fa-f]{2})*")
_MAX_HEADERS = 32768
_MAX_LINE = 4096
_MAX_FIELDS = 64


def _safe_path(path: str) -> bytes:
    if type(path) is not str or _PATH.fullmatch(path) is None or path.startswith("//"):
        raise ValueError("HTTP sample path is invalid")
    return path.encode("ascii")


class _Exchange:
    def __init__(self, connection, deadline):
        self.connection, self.deadline = connection, deadline
        self.buffer = bytearray()

    def remaining(self):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError
        self.connection.settimeout(remaining)
        return remaining

    def receive(self, maximum):
        self.remaining()
        if self.buffer:
            chunk = bytes(self.buffer[:maximum])
            del self.buffer[:maximum]
            return chunk
        return self.connection.recv(maximum)

    def line(self):
        while True:
            self.remaining()
            position = self.buffer.find(b"\r\n")
            if position >= 0:
                if position > _MAX_LINE:
                    raise ValueError
                line = bytes(self.buffer[:position])
                del self.buffer[:position + 2]
                return line
            if len(self.buffer) > _MAX_LINE:
                raise ValueError
            chunk = self.connection.recv(min(4096, _MAX_LINE + 2 - len(self.buffer)))
            if not chunk:
                raise ValueError
            self.buffer.extend(chunk)

    def exact(self, count):
        result = bytearray()
        while len(result) < count:
            chunk = self.receive(min(4096, count - len(result)))
            if not chunk:
                raise ValueError
            result.extend(chunk)
        return bytes(result)

    def headers(self):
        fields = []
        size = 0
        while True:
            line = self.line()
            size += len(line) + 2
            if size > _MAX_HEADERS:
                raise ValueError
            if not line:
                return fields
            name, separator, value = line.partition(b":")
            if (not separator or _TOKEN.fullmatch(name) is None or len(fields) >= _MAX_FIELDS
                    or any(byte < 32 and byte != 9 or byte == 127 for byte in value)):
                raise ValueError
            fields.append((name.lower(), value.strip(b" \t")))

    def body_size(self, status, fields, cap):
        lengths = [value for name, value in fields if name == b"content-length"]
        transfers = [value for name, value in fields if name == b"transfer-encoding"]
        if len(lengths) > 1 or len(transfers) > 1 or lengths and transfers:
            raise ValueError
        if lengths and (len(lengths[0]) > 20 or re.fullmatch(rb"[0-9]+", lengths[0]) is None):
            raise ValueError
        if transfers and transfers[0].lower() != b"chunked":
            raise ValueError
        if status in (204, 304):
            if transfers or status == 204 and lengths and int(lengths[0]) != 0:
                raise ValueError
            return 0
        if lengths:
            count = min(int(lengths[0]), cap + 1)
            return len(self.exact(count))
        if transfers:
            total = 0
            # A framing-byte budget also bounds tiny chunks and their extensions.
            framing = 0
            while True:
                line = self.line()
                framing += len(line) + 2
                if framing > _MAX_HEADERS or len(line) > 16 or re.fullmatch(rb"[0-9A-Fa-f]+", line) is None:
                    raise ValueError
                size = int(line, 16)
                if size == 0:
                    trailers = self.headers()
                    if any(name in (b"content-length", b"transfer-encoding") for name, _ in trailers):
                        raise ValueError
                    return total
                total += len(self.exact(min(size, cap + 1 - total)))
                if total > cap:
                    return total
                if self.exact(2) != b"\r\n":
                    raise ValueError
                framing += 2
        total = 0
        while total <= cap:
            chunk = self.receive(min(4096, cap + 1 - total))
            if not chunk:
                return total
            total += len(chunk)
        return total


def _probe(entry, deadline):
    """Return evidence only after complete framing or an observed cap+1 byte."""
    connection = None
    try:
        path = _safe_path(entry.check.path)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError
        connection = socket.create_connection(("127.0.0.1", entry.container_port), timeout=remaining)
        exchange = _Exchange(connection, deadline)
        exchange.remaining()
        connection.sendall(b"GET " + path + b" HTTP/1.1\r\nHost: 127.0.0.1:" +
            str(entry.container_port).encode("ascii") + b"\r\nConnection: close\r\n\r\n")
        line = exchange.line()
        match = re.fullmatch(rb"HTTP/1\.[01] ([2-5][0-9]{2}) [\t\x20-\x7e]*", line)
        if match is None:
            raise ValueError
        status = int(match[1])
        fields = exchange.headers()
        cap = entry.check.policy.maximum_evidence_bytes
        count = exchange.body_size(status, fields, cap)
        exchange.remaining()
        outcome = (VerificationOutcome.MALFORMED if count > cap else
                   VerificationOutcome.PASSED if status in entry.check.expected_statuses else
                   VerificationOutcome.FAILED)
        return outcome, HttpVerificationEvidence(status, min(count, cap))
    except TimeoutError:
        return VerificationOutcome.TIMED_OUT, None
    except (OSError, ValueError):
        return VerificationOutcome.FAILED, None
    finally:
        if connection is not None:
            connection.close()
