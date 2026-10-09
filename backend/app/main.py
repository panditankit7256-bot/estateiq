"""EstateIQ API entrypoint."""
from __future__ import annotations
import logging, threading, time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from .core.config import settings
from .db.seed import init_db, seed_facility
from .api.v1 import auth, facilities, data, intelligence, live

log = logging.getLogger("estateiq")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def _warm(fid: str) -> None:
    from .services import analytics as A
    from .engine import recommendations as R
    try:
        A.overview(fid); A.scorecard(fid); R.build(fid); log.info("cache warmed for %s", fid)
    except Exception:  # warming is best-effort
        log.exception("warm-up failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    n = seed_facility(settings.default_facility)
    log.info("seeded %s readings for %s", n, settings.default_facility)
    threading.Thread(target=_warm, args=(settings.default_facility,), daemon=True).start()
    yield


app = FastAPI(title="EstateIQ API", version="1.0.0", lifespan=lifespan,
              description="Sustainable Facility and Estate Intelligence Dashboard for India. Outputs are decision-support insights from (synthetic) data, not official measurements.")
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in settings.cors_origins.split(",")], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

_hits: dict[str, deque] = defaultdict(deque)


@app.middleware("http")
async def guard(request: Request, call_next):
    ip = request.client.host if request.client else "?"
    limit = 20 if request.url.path.endswith("/auth/login") else 900
    now = time.time(); q = _hits[(ip, limit)]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= limit:
        return JSONResponse({"error": {"code": 429, "message": "Too many requests, try again in a minute"}}, status_code=429)
    q.append(now)
    start = time.time()
    resp = await call_next(request)
    log.info("%s %s -> %s (%.0f ms)", request.method, request.url.path, resp.status_code, (time.time() - start) * 1000)
    return resp


@app.exception_handler(RequestValidationError)
async def validation_handler(_, exc: RequestValidationError):
    return JSONResponse({"error": {"code": 422, "message": "Invalid request", "details": exc.errors()}}, status_code=422, )


@app.get("/healthz", tags=["health"])
def healthz(): return {"status": "ok"}


@app.get("/readyz", tags=["health"])
def readyz():
    from .db.seed import has_data
    return {"ready": has_data(settings.default_facility)}


for r in (auth.router, facilities.router, data.router, intelligence.router, live.router):
    app.include_router(r, prefix="/api/v1")
