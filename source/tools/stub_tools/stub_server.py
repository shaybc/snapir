from __future__ import annotations

from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

from models.validation_models import StubSpec


@dataclass
class StubServerHandle:
    """Handle for a running validation stub server."""

    server: ThreadingHTTPServer
    thread: Thread
    call_log: list[dict] = field(default_factory=list)

    def stop(self) -> None:
        """Stop the HTTP server and wait for its thread to finish."""
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def get_call_log(self) -> list[dict]:
        """Return requests received by the stub server."""
        return list(self.call_log)


def start_stub_server(stub_spec: StubSpec, port: int) -> StubServerHandle:
    """Start an HTTP server that serves responses from a StubSpec."""
    call_log: list[dict] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            call_log.append({"method": "POST", "path": self.path, "body": body})
            scenario = _match_scenario(stub_spec, self.path, "POST", body)
            if scenario is None:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"")
                return
            response = scenario.get("response_body", "")
            self.send_response(200)
            self.send_header("Content-Type", "application/xml")
            self.end_headers()
            self.wfile.write(response.encode("utf-8"))

        def log_message(self, format: str, *args) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    handle = StubServerHandle(server=server, thread=thread, call_log=call_log)
    thread.start()
    return handle


def _match_scenario(stub_spec: StubSpec, path: str, method: str, body: str) -> dict | None:
    for scenario in stub_spec.scenarios:
        if scenario.get("method", "POST") != method:
            continue
        if scenario.get("endpoint") != path:
            continue
        pattern = scenario.get("request_pattern")
        if pattern and pattern not in body:
            continue
        return scenario
    return None
