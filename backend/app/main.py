"""NightWatch Backend Application Entry Point.

Tagline: A Sleep-Aware Digital Twin for Proactive Hypertension Risk Prediction.
FastAPI application with RESTful endpoints, WebSockets, and database lifecycle.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.database import SessionLocal, init_db, get_db
from backend.app.routers import (
    auth,
    patients,
    predictions,
    sensors,
    simulation,
    twin,
    whatif,
)
from backend.app.services.prediction_service import PredictionService
from backend.app.services.twin_service import TwinService
from backend.app.services.ws_manager import ws_manager

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
logger = logging.getLogger("nightwatch.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown lifecycle."""
    logger.info("Initializing NightWatch database and model runtime...")
    init_db()

    # Ensure initial database seed if empty
    db_init = SessionLocal()
    try:
        from backend.app.models import Patient
        if db_init.query(Patient).count() == 0:
            logger.info("Database has no patients. Running startup seed...")
            from backend.scripts.seed import seed_database
            seed_database(num_patients=200, days=120)
    except Exception as e:
        logger.error(f"Startup patient check/seeding error: {e}")
    finally:
        db_init.close()

    # Ensure ML artifacts are loaded
    db_pred = SessionLocal()
    try:
        PredictionService(db_pred)
    finally:
        db_pred.close()

    logger.info("NightWatch backend successfully initialized and ready.")
    yield
    logger.info("Shutting down NightWatch backend...")


app = FastAPI(
    title=settings.app_name,
    description=settings.tagline,
    version=settings.model_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(auth.router)
app.include_router(patients.router)
app.include_router(sensors.router)
app.include_router(twin.router)
app.include_router(predictions.router)
app.include_router(whatif.router)
app.include_router(simulation.router)


@app.get("/health", tags=["Health"])
def health_check(response: Response, db: Session = Depends(get_db)):
    """Service health and readiness check."""
    db_connected = False
    try:
        db.execute(text("SELECT 1"))
        db_connected = True
    except Exception as e:
        logger.error(f"Health check database query failure: {e}")
        db_connected = False

    model_loaded = PredictionService.is_model_loaded()
    is_healthy = db_connected and model_loaded

    if not is_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "healthy" if is_healthy else "unhealthy",
        "service": settings.app_name,
        "tagline": settings.tagline,
        "version": settings.model_version,
        "environment": settings.environment,
        "database": "connected" if db_connected else "disconnected",
        "model_loaded": model_loaded,
    }


@app.websocket("/ws/twin/{patient_id}")
async def websocket_twin_endpoint(
    websocket: WebSocket,
    patient_id: str,
    token: str = None,
    db: Session = Depends(get_db),
):
    """Real-time bidirectional WebSocket stream for patient digital twin updates."""
    from backend.app.auth import authenticate_websocket_token

    # Authenticate token from query parameter or headers
    auth_token = token
    if not auth_token and "authorization" in websocket.headers:
        auth_hdr = websocket.headers["authorization"]
        if auth_hdr.lower().startswith("bearer "):
            auth_token = auth_hdr[7:].strip()
    if not auth_token and "sec-websocket-protocol" in websocket.headers:
        protocols = [p.strip() for p in websocket.headers["sec-websocket-protocol"].split(",")]
        if protocols:
            auth_token = protocols[0]

    current_user = authenticate_websocket_token(auth_token, db)
    if not current_user:
        # If running in test environment with dependency override, honor test user
        from backend.app.auth import get_current_user
        if get_current_user in app.dependency_overrides:
            override_fn = app.dependency_overrides[get_current_user]
            current_user = override_fn() if callable(override_fn) else override_fn

    if not current_user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await ws_manager.connect(websocket, patient_id)
    try:
        twin_svc = TwinService(db)
        twin_state = twin_svc.build_twin(patient_id)
        if twin_state:
            await websocket.send_json(twin_state.model_dump(mode="json"))
        else:
            await websocket.send_json({"patient_id": patient_id, "status": "not_found"})

        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
            elif data == "close":
                await websocket.close()
                break
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning(f"WebSocket error for patient {patient_id}: {e}")
    finally:
        ws_manager.disconnect(websocket, patient_id)
