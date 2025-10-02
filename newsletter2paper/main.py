from fastapi import FastAPI
import os
from routers import rss, issues, publications, articles

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

# Include routers
app.include_router(rss.router)
app.include_router(issues.router)
app.include_router(publications.router)
app.include_router(articles.router)

# Optional: Add a root endpoint
@app.get("/")
async def root():
    return {"message": "Welcome to Newsletter2Paper API"}