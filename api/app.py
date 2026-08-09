"""
FastAPI Application Factory
===========================
Wires up middleware, all route routers, the lifespan-managed
SystemController, and the React SPA fallback (when frontend/dist exists).
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from config.logging_config import get_logger
from config.settings import settings

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from database.connection import init_db
    from core.event_bus import event_bus
    from core.controller import controller
    from api.routes.websocket import broadcast_alert, set_main_loop
    import asyncio

    # Capture the main event loop so sync route handlers (running in the
    # FastAPI threadpool) can dispatch WebSocket coroutines back onto it
    # via api.routes.websocket.broadcast_from_thread().
    set_main_loop(asyncio.get_running_loop())

    init_db()
    controller.start()

    # Hydrate the face recognition cache from the DB. The cache otherwise stays
    # empty after a server restart, so every previously-enrolled guest reads as
    # "unknown" until the next enrollment kicks off load_guest_embeddings().
    try:
        from database.connection import SessionLocal
        from modules.recognition import face_engine
        # Load MTCNN/FaceNet weights now (blocking, ~10s) rather than on the
        # first real recognition request — moves the cold-start cost to boot
        # time, before uvicorn starts accepting traffic.
        face_engine.warm_up()
        with SessionLocal() as db:
            n = face_engine.load_guest_embeddings(db)
        logger.info(f"Face engine cache hydrated: {n} guests loaded")
    except Exception as e:
        logger.error(f"Face embedding cache hydration failed: {e}", exc_info=True)

    def _on_alert(alert_type: str = "", title: str = "", **kwargs):
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                asyncio.ensure_future(
                    broadcast_alert(
                        {
                            "event": "alert_created",
                            "alert_type": alert_type,
                            "title": title,
                            **{
                                k: v
                                for k, v in kwargs.items()
                                if isinstance(v, (str, int, float, bool, type(None)))
                            },
                        }
                    )
                )
        except RuntimeError:
            # No running event loop available (e.g. during shutdown)
            pass

    event_bus.subscribe("alert_created", _on_alert)
    logger.info("Application started")

    try:
        yield
    finally:
        controller.stop()
        event_bus.clear()
        logger.info("Application shutting down")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Smart Reception Assistant",
        description="AI-Powered hotel reception system API",
        version="1.0.0",
        lifespan=lifespan,
    )

    allowed_origins = getattr(settings, "cors_allowed_origins", None) or [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from api.routes import health, guests, staff, alerts
    from api.routes import websocket
    from api.routes import visits, reservations, services, recommendations, edge, exports
    from api.routes import enrollment, system as system_routes, monitoring

    app.include_router(health.router, prefix="/api", tags=["health"])
    app.include_router(guests.router, prefix="/api/guests", tags=["guests"])
    app.include_router(staff.router, prefix="/api/staff", tags=["staff"])
    app.include_router(alerts.router, prefix="/api/alerts", tags=["alerts"])
    app.include_router(websocket.router, prefix="/api/ws", tags=["websocket"])
    app.include_router(websocket.ws_router, tags=["websocket"])  # canonical /ws
    app.include_router(visits.router, prefix="/api/visits", tags=["visits"])
    app.include_router(reservations.router, prefix="/api/reservations", tags=["reservations"])
    app.include_router(services.router, prefix="/api/services", tags=["services"])
    app.include_router(recommendations.router, prefix="/api/recommendations", tags=["recommendations"])
    app.include_router(edge.router, prefix="/api/edge", tags=["edge"])
    from api.routes import audio as audio_routes
    app.include_router(audio_routes.router, prefix="/api/audio", tags=["audio"])
    app.include_router(exports.router, prefix="/api/exports", tags=["exports"])
    app.include_router(enrollment.router, prefix="/api/enrollment", tags=["enrollment"])
    app.include_router(system_routes.router, prefix="/api/system", tags=["system"])
    app.include_router(monitoring.router, prefix="/api/monitoring", tags=["monitoring"])

    dist_dir = Path(settings.project_root) / "frontend" / "dist"
    if dist_dir.is_dir():
        assets_dir = dist_dir / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        index_file = dist_dir / "index.html"

        @app.get("/", include_in_schema=False)
        async def serve_index():
            return FileResponse(str(index_file))

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa_fallback(full_path: str):
            if full_path.startswith("api"):
                return FileResponse(str(index_file), status_code=404)
            candidate = dist_dir / full_path
            if candidate.is_file():
                return FileResponse(str(candidate))
            return FileResponse(str(index_file))
    else:
        logger.info("frontend/dist not found: static SPA serving disabled")

    return app


app = create_app()
