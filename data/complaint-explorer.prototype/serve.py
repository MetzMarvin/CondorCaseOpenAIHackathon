"""THROWAWAY: run `python3 data/complaint-explorer.prototype/serve.py`."""

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import urlparse, parse_qs

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def snapshot(folder):
    data = {name: rows(folder / "runtime" / f"{name}.jsonl") for name in
            ["cases", "contacts", "bookings", "flights", "messages", "attachments", "events"]}
    data.update({name: rows(folder / "evaluation" / f"{name}.jsonl") for name in ["labels", "provenance", "simulator"]})
    data["manifest"] = json.loads((folder / "manifest.json").read_text())
    data["validation"] = json.loads((folder / "validation.json").read_text())
    data["source"] = str(folder.relative_to(ROOT)) if folder.is_relative_to(ROOT) else str(folder)
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--data", type=Path, default=ROOT / "data/processed/complaints")
    args = parser.parse_args()
    folder = args.data.resolve()
    if not (folder / "manifest.json").exists():
        parser.error("Build the data first: python3 -m pipeline build")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            url = urlparse(self.path)
            if url.path == "/api/snapshot":
                body = json.dumps(snapshot(folder), ensure_ascii=False).encode()
                media = "application/json; charset=utf-8"
            elif url.path == "/api/evidence":
                aid = parse_qs(url.query).get("id", [""])[0]
                evidence = next((r for r in rows(folder / "runtime/attachments.jsonl") if r["id"] == aid), None)
                scope = "runtime"
                if evidence is None:
                    future = [a for reply in rows(folder / "evaluation/simulator.jsonl") for a in reply.get("attachments", [])]
                    evidence = next((r for r in future if r["id"] == aid), None)
                    scope = "evaluation"
                if evidence is None:
                    self.send_error(404)
                    return
                path = (folder / scope / evidence["path"]).resolve()
                if not path.is_relative_to(folder / scope / "attachments"):
                    self.send_error(403)
                    return
                body = path.read_bytes()
                media = evidence["media_type"]
            elif url.path in ("/", "/index.html", "/app.js", "/style.css"):
                filename = "index.html" if url.path == "/" else url.path[1:]
                body = (HERE / filename).read_bytes()
                media = {"index.html": "text/html", "app.js": "text/javascript", "style.css": "text/css"}[filename] + "; charset=utf-8"
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", media)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Complaint explorer prototype: http://localhost:{args.port}/?variant=A", flush=True)
    print("Read-only local data inspector. Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
