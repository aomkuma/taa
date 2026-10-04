"""``POST /api/v1/ingest/batch``: the engine's replication batches (PLAN §A13; TAA-703).

Authenticated by the paired engine's HMAC signature (``SignedEngine``), not by a web session. The body is the
gzipped batch of :func:`app.sync.outbox.encode_batch`; :class:`app.sync.ingest.IngestService` applies it.

Responses (the engine's sender reacts to them, see ``app/sync/outbox.py``):

- 200 ``{"accepted", "duplicates", "rejected": [{"event_id", "code", "detail"}]}``: rejected events are
  refused for good (the engine parks them as DEAD); everything else is stored
- 401 ``signature_invalid``: the signature check failed (the reason is logged, never returned)
- 413 ``request_too_large``; 415 ``unsupported_media_type``: the body is not marked gzip
- 400 ``invalid_batch``: not gzip or not JSON
- 422 ``invalid_batch``: an invalid envelope, or a batch naming another engine
- 503 ``sync_disabled``: no engine is paired
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from starlette.concurrency import run_in_threadpool

from app.sync.ingest import BatchError, decode_body
from app.web.deps import SignedEngine
from app.web.errors import ApiProblem

router = APIRouter(prefix="/ingest", tags=["sync"])

# Compressed limit; the decompressed batch is capped separately (app.sync.ingest.MAX_DECOMPRESSED_BYTES).
INGEST_MAX_BODY_BYTES = 8 * 1024 * 1024
INGEST_PATH = "/api/v1/ingest/batch"


@router.post("/batch")
async def ingest_batch(request: Request, engine: SignedEngine) -> dict[str, Any]:
    if request.headers.get("content-encoding", "").lower() != "gzip":
        raise ApiProblem(415, "unsupported_media_type", "The batch must be gzip-encoded")
    try:
        doc = await run_in_threadpool(decode_body, engine.body)
    except BatchError as exc:
        raise ApiProblem(400, "invalid_batch", str(exc)) from exc
    try:
        result = await run_in_threadpool(engine.link.ingest.ingest, engine.verified.engine_id, doc)
    except BatchError as exc:
        raise ApiProblem(422, "invalid_batch", str(exc)) from exc
    return result.to_dict()
