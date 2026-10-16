"""Optional: render an album through the LiveDreams Partner API (shot 1, then the pages in parallel).
Most integrations call the API from their own pipeline; this is for testing and small runs."""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Optional

import httpx

from .config import RenderConfig

TERMINAL = {"succeeded", "failed", "canceled"}


class Renderer:
    def __init__(self, cfg: RenderConfig, api_key: Optional[str] = None, log: Callable[[str], None] = print):
        key = api_key or cfg.api_key()
        if not key:
            raise RuntimeError(f"set {cfg.api_key_env} to render")
        self.cfg, self.log = cfg, log
        # the API closes idle connections after 5 s: reusing one at that moment gave "Server disconnected"
        # (24 times in 720 pages); drop idle connections earlier
        self.http = httpx.Client(base_url=cfg.base_url, timeout=60,
                                 limits=httpx.Limits(keepalive_expiry=2.0),
                                 headers={"Authorization": f"Bearer {key}", "User-Agent": "albumgen/1.0"})
        self.workers = self._workers()
        self.log(f"{self.workers} pages in flight")

    def _workers(self) -> int:
        """Pages in flight: `max_inflight`, capped by the key's own limits and the canvas pool (GET /limits, free).
        More would only wait in the queue, and the wait counts toward a page's deadline."""
        n = self.cfg.max_inflight
        r = self._call("GET", "/limits")
        if r is not None and r.status_code == 200:
            lim = r.json()
            caps = [(lim.get(k) or {}).get("max") for k in ("inflight", "canvas_inflight")]
            n = min([n] + [c for c in caps if isinstance(c, int) and c > 0])
        return max(1, n)

    def _call(self, method: str, url: str, **kw) -> httpx.Response | None:
        """Retries network errors (dropped connections, timeouts). Same Idempotency-Key = same job, so a repeated
        POST never creates or bills a second job."""
        for attempt in range(6):
            try:
                return self.http.request(method, url, **kw)
            except httpx.TransportError as e:
                self.log(f"network error ({type(e).__name__}), retrying")
                time.sleep(min(30, 2 ** attempt))
        return None

    def _post(self, body: dict, idem: str) -> dict:
        for attempt in range(6):
            r = self._call("POST", "/images/generations", json=body, headers={"Idempotency-Key": idem})
            if r is None:
                return {"status": "failed", "error": {"code": "network_error"}}
            if r.status_code in (429, 503):
                time.sleep(float(r.headers.get("retry-after", 5)))
                continue
            if r.status_code >= 400:
                return {"status": "failed", "error": r.json().get("error", {"code": str(r.status_code)})}
            return r.json()
        return {"status": "failed", "error": {"code": "rate_limited"}}

    def _wait(self, job: dict) -> dict:
        t0 = time.time()
        while job.get("status") not in TERMINAL and time.time() - t0 < self.cfg.job_timeout_s:
            time.sleep(self.cfg.poll_s)
            r = self._call("GET", f"/jobs/{job['id']}")
            if r is not None and r.status_code == 200:
                job = r.json()
        return job

    def _one(self, album_id: str, req: dict, shot1_id: Optional[str], out: Path, attempt: int = 1) -> dict:
        try:
            return self._one_inner(album_id, req, shot1_id, out, attempt)
        except Exception as e:  # one broken page never stops the album
            self.log(f"shot {req['shot']}: error {e!r}")
            return {"shot": req["shot"], "id": None, "status": "error", "error": repr(e)}

    def _one_inner(self, album_id: str, req: dict, shot1_id: Optional[str], out: Path, attempt: int = 1) -> dict:
        body = {"model": req["model"], "prompt": req["prompt"], **req["params"], "external_id": f"{album_id}/{req['shot']}"}
        if shot1_id:
            body["images"] = [{"job_id": shot1_id}]
        job = self._post(body, f"{album_id}-s{req['shot']}-a{attempt}")
        if job.get("id"):
            job = self._wait(job)
        res = {"shot": req["shot"], "id": job.get("id"), "status": job.get("status"), "error": job.get("error")}
        if job.get("status") == "succeeded" and job.get("images"):
            img = self._call("GET", job["images"][0]["url"])
            if img is not None and img.status_code == 200:
                path = out / f"{int(req['shot']):02d}.jpg"
                path.write_bytes(img.content)
                res["file"] = str(path)
        self.log(f"shot {req['shot']}: {res['status']}" + (f" ({res['error']})" if res.get("error") else ""))
        return res

    def render(self, album_dir: Path) -> list[dict]:
        """Renders the album, or finishes an interrupted one: pages with an image are kept, the same
        Idempotency-Key returns a job that already exists (no new charge), a failed page gets a new key."""
        requests = json.loads((album_dir / "album.json").read_text())
        album_id = album_dir.name
        out = album_dir / "images"
        out.mkdir(exist_ok=True)
        prev_file = album_dir / "render.json"
        prev = {int(r["shot"]): r for r in json.loads(prev_file.read_text())} if prev_file.exists() else {}

        def run(req: dict, shot1_id: Optional[str]) -> dict:
            shot = int(req["shot"])
            old = prev.get(shot, {})
            image = out / f"{shot:02d}.jpg"
            if image.exists() and (shot > 1 or old.get("id")):
                return {**old, "shot": shot, "status": "succeeded", "file": str(image)}
            attempt = int(old.get("attempt", 1)) + (1 if old.get("status") in ("failed", "error") else 0)
            return {**self._one(album_id, req, shot1_id, out, attempt), "attempt": attempt}

        first = run(requests[0], None)
        results = [first]
        if first["status"] == "succeeded" and first.get("id"):
            with ThreadPoolExecutor(max_workers=self.workers) as pool:
                results += list(pool.map(lambda r: run(r, first["id"]), requests[1:]))
            # one more try for pages that timed out or failed on the provider side (a new Idempotency-Key)
            def code(r: dict) -> str:
                err = r.get("error")
                return str(err.get("code", "")) if isinstance(err, dict) else ""
            retry = [r for r in results[1:] if r.get("status") in ("failed", "error")
                     and code(r) not in ("content_rejected", "invalid_request")]
            if retry:
                prev.update({int(r["shot"]): r for r in retry})
                by_shot = {int(q["shot"]): q for q in requests}
                with ThreadPoolExecutor(max_workers=self.workers) as pool:
                    again = {r["shot"]: r for r in pool.map(lambda r: run(by_shot[int(r["shot"])], first["id"]), retry)}
                results = [again.get(r["shot"], r) for r in results]
        prev_file.write_text(json.dumps(results, indent=2))
        return results
