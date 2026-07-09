"""
FastAPI Backend for Drug Compatibility Checker
Main application entry point
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from app.routers import (
    drugs_router, compatibility_router, chat_router, athero_router,
    passkey_router, coadministration_router,
)
from app.services.drug_service import get_drug_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler - initialize services on startup"""
    # Initialize the drug service (loads database)
    print("Initializing drug database...")
    service = get_drug_service()
    info = service.get_database_info()
    print(f"Database loaded: {info['total_drugs']} drugs, {info['drugs_with_dosing']} with dosing data")
    yield
    # Cleanup if needed
    print("Shutting down...")


# Create FastAPI application
app = FastAPI(
    title="Drug Compatibility API",
    description="""
    API for checking drug compatibility for 3D printing applications.
    
    ## Features
    - Search drugs by name or category
    - Get detailed drug information
    - Check compatibility between two or more drugs
    - AI-powered drug assistant for 3D printing questions
    
    ## Note
    This API is for research and 3D printing compatibility assessment only.
    It does not provide medical advice.
    """,
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS for frontend
# In production, replace "*" with specific origins
origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:8080",
    "http://localhost:8081",
    "http://localhost:8082",
    "http://localhost:8083",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "http://127.0.0.1:8080",
    "http://127.0.0.1:8081",
    "http://127.0.0.1:8082",
    "http://127.0.0.1:8083",
    # Production (Render)
    #"https://threedpharma-app-frontend.onrender.com",
    "https://threedpharma-frontend.onrender.com"
]

# Also allow from environment variable
extra_origins = os.getenv("CORS_ORIGINS", "")
if extra_origins:
    origins.extend(extra_origins.split(","))

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global exception handler — ensures CORS headers are present even on 500 errors.
# Without this, Starlette's CORS middleware may omit headers when the origin is
# not yet in the allow-list (e.g. during a partial deploy), causing the browser
# to report "Failed to fetch" instead of the real error.
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    origin = request.headers.get("origin", "")
    headers = {}
    if origin in origins:
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"
    print(f"[ERROR] Unhandled exception on {request.method} {request.url.path}: "
          f"{type(exc).__name__}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": f"{type(exc).__name__}: {str(exc)}"},
        headers=headers,
    )


# Include routers
app.include_router(passkey_router)
app.include_router(drugs_router)
app.include_router(compatibility_router)
app.include_router(chat_router)
app.include_router(athero_router)
app.include_router(coadministration_router)


@app.get("/")
async def root():
    """Root endpoint - API information"""
    return {
        "name": "Drug Compatibility API",
        "version": "1.0.0",
        "documentation": "/docs",
        "endpoints": {
            "drugs": "/drugs",
            "compatibility": "/compatibility",
            "coadministration": "/coadministration",
            "chat": "/chat",
            "athero": "/athero"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    service = get_drug_service()
    info = service.get_database_info()
    
    return {
        "status": "healthy",
        "database": {
            "loaded": info['total_drugs'] > 0,
            "total_drugs": info['total_drugs'],
            "drugs_with_dosing": info['drugs_with_dosing']
        }
    }


if __name__ == "__main__":
    import uvicorn
    
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=False
    )
