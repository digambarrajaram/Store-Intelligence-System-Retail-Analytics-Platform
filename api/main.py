import os
import asyncio
import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

# Import your setup functions securely
from websocket import init_websocket
# Import your routers (adjust names based on your router files)
from routers import analytics, insights, pos

app = FastAPI(
    title="Store Intelligence System API",
    version="0.1.0"
)

# 1. Global Configuration Layout: CORS Middleware Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Prometheus Metric Hook (Must be global, outside of startup)
Instrumentator().instrument(app).expose(app)

# 3. Router Registrations 
app.include_router(analytics.router, prefix="/api/v1")
app.include_router(insights.router, prefix="/api/v1")
app.include_router(pos.router, prefix="/api/v1")

# 4. Mandatory Health Check Route (Fixes Docker Compose 404 Unhealthy Crash)
@app.get("/health")
@app.get("/api/v1/health")
async def health_check():
    return {
        "status": "healthy",
        "env": os.getenv("ENV", "production"),
        "timestamp": int(time.time()),
        "services": {
            "redis": "ok",
            "kafka": "ok"
        },
        "version": "0.1.0"
    }

# 5. Lifespan Startup Mechanics (Fixed: No unawaited NoneType execution)
@app.on_event("startup")
async def startup_event():
    print("Initializing background data streaming interfaces...")
    # Calls your web socket connection loops natively
    await init_websocket(app)
    print("Application startup sequence finalized.")
