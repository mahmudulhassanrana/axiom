"""WebSocket fan-out for job progress (Redis pub/sub)."""

from __future__ import annotations

import asyncio
import os
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from axiom_api.core.security import decode_access_token
from axiom_api.db.models.job import Job
from axiom_api.db.session import async_session_factory

router = APIRouter(tags=["realtime"])


def _redis_url() -> str | None:
    u = (os.environ.get("REDIS_URL") or os.environ.get("CELERY_BROKER_URL") or "").strip()
    if u.startswith("redis://") or u.startswith("rediss://"):
        return u
    return None


async def _next_pub_message(pubsub: object) -> dict | None:
    while True:
        m = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
        if m and m.get("type") == "message":
            return m


@router.websocket("/ws/jobs/{job_id}")
async def websocket_job_updates(websocket: WebSocket, job_id: UUID) -> None:
    token = websocket.query_params.get("token") or ""
    if not token.strip():
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:
        claims = decode_access_token(token.strip())
    except Exception:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:
        org_id = UUID(str(claims.get("org_id")))
    except (TypeError, ValueError):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    factory = async_session_factory()
    async with factory() as session:
        job = (
            await session.execute(select(Job).where(Job.id == job_id, Job.organization_id == org_id))
        ).scalar_one_or_none()
        if job is None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

    redis_url = _redis_url()
    if not redis_url or redis_url.startswith("memory://"):
        await websocket.accept()
        await websocket.send_json(
            {
                "type": "error",
                "message": "Redis not configured; real-time job updates unavailable.",
            },
        )
        await websocket.close()
        return

    await websocket.accept()
    try:
        from redis import asyncio as aioredis
    except ImportError:
        await websocket.send_json({"type": "error", "message": "redis asyncio client missing"})
        await websocket.close()
        return

    r = aioredis.from_url(redis_url, decode_responses=True)
    pubsub = r.pubsub()
    await pubsub.subscribe(f"axiom:job:{job_id}")

    try:
        while True:
            t_recv = asyncio.create_task(websocket.receive())
            t_pub = asyncio.create_task(_next_pub_message(pubsub))
            done, pending = await asyncio.wait(
                {t_recv, t_pub},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for p in pending:
                p.cancel()
            finished = next(iter(done))
            if finished == t_recv:
                try:
                    finished.result()
                except WebSocketDisconnect:
                    break
                continue
            msg = t_pub.result()
            if msg and isinstance(msg.get("data"), str):
                await websocket.send_text(msg["data"])
    finally:
        await pubsub.unsubscribe(f"axiom:job:{job_id}")
        await pubsub.close()
        await r.aclose()
