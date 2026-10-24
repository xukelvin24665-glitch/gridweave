"""Small local-only dashboard server; no keys, cloud services, or JS dependencies."""

from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
from urllib.parse import parse_qs, urlparse

from .experiment import frontier, run_experiment
from .models import Scenario
from .optimizer import SchedulingError
from .scenarios import SCENARIOS, generate_scenario

WEB = Path(__file__).with_name("web")
SOLVE_LOCK = threading.Lock()


@lru_cache(maxsize=32)
def cached_experiment(kind, seed, carbon_price, battery):
    return run_experiment(generate_scenario(kind, seed, battery), carbon_price)


class Handler(BaseHTTPRequestHandler):
    server_version = "GridWeave/1.0"

    def _send(self, status, body, content_type="application/json; charset=utf-8"):
        if not isinstance(body, bytes):
            body = json.dumps(body, allow_nan=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def _host_ok(self):
        hostname = urlparse("http://" + self.headers.get("Host", "")).hostname
        return hostname in ("127.0.0.1", "localhost", "::1")

    def _parameters(self, query):
        kind = query.get("scenario", ["balanced"])[0]
        seed = int(query.get("seed", ["42"])[0])
        carbon_price = float(query.get("carbon_price", ["80"])[0])
        battery = float(query.get("battery", ["2.4"])[0])
        if not 0 <= carbon_price <= 2000 or not 0 <= battery <= 10:
            raise ValueError("Carbon price must be 0-2000 and battery capacity 0-10")
        return kind, seed, carbon_price, battery

    def _solve(self, callback):
        if not SOLVE_LOCK.acquire(blocking=False):
            self._send(503, {"error": "Another experiment is running. Try again shortly."})
            return
        try:
            self._send(200, callback())
        finally:
            SOLVE_LOCK.release()

    def do_GET(self):
        if not self._host_ok():
            return self._send(403, {"error": "Only local dashboard hosts are allowed"})
        request = urlparse(self.path)
        try:
            if request.path == "/api/health":
                return self._send(200, {"status": "ok", "version": "1.0.0"})
            if request.path == "/api/scenarios":
                return self._send(200, SCENARIOS)
            if request.path in ("/api/experiment", "/api/frontier"):
                kind, seed, weight, battery = self._parameters(parse_qs(request.query))
                if request.path == "/api/experiment":
                    return self._solve(lambda: cached_experiment(kind, seed, weight, battery))
                return self._solve(lambda: {"points": frontier(generate_scenario(kind, seed, battery)),
                                            "scope": "Perfect-forecast model"})
            files = {"/": ("index.html", "text/html; charset=utf-8"),
                     "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                     "/styles.css": ("styles.css", "text/css; charset=utf-8"),
                     "/evidence.json": ("evidence.json", "application/json; charset=utf-8"),
                     "/favicon.svg": ("favicon.svg", "image/svg+xml")}
            if request.path in files:
                filename, mime = files[request.path]
                if not (WEB / filename).is_file():
                    return self._send(404, {"error": "Evidence snapshot has not been generated"})
                return self._send(200, (WEB / filename).read_bytes(), mime)
            self._send(404, {"error": "Not found"})
        except (ValueError, TypeError, OverflowError) as exc:
            self._send(400, {"error": str(exc)})
        except SchedulingError as exc:
            self._send(422, {"error": str(exc), "solver_status": exc.status})

    def do_POST(self):
        if not self._host_ok():
            return self._send(403, {"error": "Only local dashboard hosts are allowed"})
        origin = self.headers.get("Origin")
        if origin and origin != "http://" + self.headers.get("Host"):
            return self._send(403, {"error": "Cross-origin requests are not allowed"})
        if self.path != "/api/solve":
            return self._send(404, {"error": "Not found"})
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            return self._send(415, {"error": "Use application/json"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 262144:
                return self._send(413, {"error": "Input must contain 1-262144 bytes"})
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError("Request must be a JSON object")
            scenario = Scenario.from_dict(data["scenario"])
            weight = float(data.get("carbon_price", 80))
            if not 0 <= weight <= 2000:
                raise ValueError("Carbon price must be 0-2000")
            self._solve(lambda: run_experiment(scenario, weight))
        except (ValueError, KeyError, TypeError, OverflowError) as exc:
            self._send(400, {"error": str(exc)})
        except SchedulingError as exc:
            self._send(422, {"error": str(exc)})

    def log_message(self, fmt, *args):
        # Keep normal requests quiet; stderr still receives actual HTTP errors.
        if args and str(args[1] if len(args) > 1 else "").startswith(("4", "5")):
            super().log_message(fmt, *args)


def serve(port: int = 8765):
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"GridWeave is ready at http://127.0.0.1:{server.server_port}", flush=True)
    print("Press Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
