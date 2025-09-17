from fastapi import FastAPI
from routers import rss

app = FastAPI(
    title="Newsletter2Paper API",
    description="API for converting newsletters to paper format",
    version="1.0.0"
)

# Include routers
app.include_router(rss.router)

# Optional: Add a root endpoint
@app.get("/")
async def root():
    return {"message": "Welcome to Newsletter2Paper API"}