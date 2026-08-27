import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.database import init_db
from app.routes.ingest import router as ingest_router
from app.routes.analytics import router as analytics_router
from app.routes.keys import router as keys_router
from app.routes.installer import router as installer_router
from app.config import settings

# Initialize database schema on startup
init_db()

app = FastAPI(
    title="Personal Telemetry & Activity API",
    description="A privacy-first personal activity tracker for GitHub, local folders, coding time, and technical metrics with zero data leakage.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Enable CORS for local dev / client integrations
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(ingest_router)
app.include_router(analytics_router)
app.include_router(keys_router)
app.include_router(installer_router)

# Mount static folder for dashboard
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/health", tags=["System"])
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "version": "1.0.0", "database": "connected"}


@app.get("/", include_in_schema=False)
@app.get("/dashboard", include_in_schema=False)
def dashboard_view():
    """Serve the local privacy & telemetry dashboard."""
    dashboard_file = os.path.join(static_dir, "index.html")
    if os.path.exists(dashboard_file):
        return FileResponse(dashboard_file)
    return {"message": "Welcome to Personal Activity API. Visit /docs for API documentation."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.API_HOST, port=settings.API_PORT, reload=True)
