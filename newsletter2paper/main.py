from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
import os
from routers import rss, issues, publications, articles, pdf, deliveries
from services import analytics_service as analytics

# Verify required environment variables
required_env_vars = ['SUPABASE_URL', 'SUPABASE_KEY']
missing_vars = [var for var in required_env_vars if not os.getenv(var)]
if missing_vars:
    raise RuntimeError(f"Missing required environment variables: {', '.join(missing_vars)}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """App lifespan: start and stop background services like the scheduler."""
    try:
        app.state.scheduler = None
        app.state.scheduler_error = None
        try:
            from services.scheduler import SchedulerService
            app.state.scheduler = SchedulerService()
            app.state.scheduler.start()
        except Exception as e:
            # Non-fatal so the API keeps serving, but scheduled delivery is off: say so loudly
            # here and in /health (which fails the deploy's health check).
            import logging
            app.state.scheduler = None
            app.state.scheduler_error = str(e)
            logging.critical(f"Scheduler NOT running; scheduled delivery is disabled: {e}", exc_info=True)
            analytics.capture_exception(e, properties={'stage': 'scheduler_start'})

        yield

    finally:
        try:
            sched = getattr(app.state, 'scheduler', None)
            if sched:
                sched.shutdown()
        except Exception:
            import logging
            logging.exception("Error shutting down scheduler during lifespan")
        analytics.shutdown()


app = FastAPI(
    title="Newsletter2Paper API",
    description="API for converting newsletters to paper format",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],  # Frontend URLs
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods including OPTIONS
    allow_headers=["*"],  # Allow all headers including authorization
)

# Include routers
app.include_router(rss.router)
app.include_router(issues.router)
app.include_router(publications.router)
app.include_router(articles.router)
app.include_router(pdf.router)
app.include_router(deliveries.router)


@app.exception_handler(Exception)
async def unhandled_exception(request: Request, exc: Exception):
    # Starlette still re-raises after this, so the traceback is logged as before.
    analytics.capture_exception(exc, *analytics.request_context(request))
    return PlainTextResponse("Internal Server Error", status_code=500)

# Root endpoint
@app.get("/")
async def root():
    return {"message": "Welcome to Newsletter2Paper API"}

# Health check endpoint
@app.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring and deployment verification.
    Returns the service status and version. Status is "degraded" when the scheduler failed
    to start, so a misconfiguration can't silently stop scheduled delivery.
    """
    scheduler_error = getattr(app.state, 'scheduler_error', None)
    return {
        "status": "degraded" if scheduler_error else "healthy",
        "service": "newsletter2paper-api",
        "version": "1.0.0",
        "scheduler": f"disabled: {scheduler_error}" if scheduler_error else "running",
    }