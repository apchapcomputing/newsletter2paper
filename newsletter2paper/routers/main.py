from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import rss

app = FastAPI(
    title="Newsletter2Paper API",
    description="API for converting newsletters to paper format",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(rss.router)

# Optional: Add a root endpoint
@app.get("/")
async def root():
    return {"message": "Welcome to Newsletter2Paper API"}