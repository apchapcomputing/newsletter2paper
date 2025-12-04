from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from routers import rss, issues, publications, articles, pdf

# Verify required environment variables
required_env_vars = ['SUPABASE_URL', 'SUPABASE_KEY']
missing_vars = [var for var in required_env_vars if not os.getenv(var)]
if missing_vars:
    raise RuntimeError(f"Missing required environment variables: {', '.join(missing_vars)}")

app = FastAPI(
    title="Newsletter2Paper API",
    description="API for converting newsletters to paper format",
    version="1.0.0"
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

# Root endpoint
@app.get("/")
async def root():
    return {"message": "Welcome to Newsletter2Paper API"}

# Health check endpoint
@app.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring and deployment verification.
    Returns the service status and version.
    """
    return {
        "status": "healthy",
        "service": "newsletter2paper-api",
        "version": "1.0.0"
    }