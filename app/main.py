"""FastAPI Application entry point for OpenDocs Voice & Learning Engine."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.documents import router as documents_router
from app.api.learning import router as learning_router
from app.api.monitor import router as monitor_router
from app.api.proof import router as proof_router
from app.api.qa import router as qa_router
from app.api.sandbox import router as sandbox_router
from app.api.speech import router as speech_router

app = FastAPI(
    title="OpenDocs Voice & Learning Engine",
    description=(
        "High-assurance, code-safe, multimodal open-source documentation assistant "
        "and AI-powered personalized learning platform."
    ),
    version="0.4.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Enable CORS for external frontends and dashboards
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(documents_router)
app.include_router(learning_router)
app.include_router(proof_router)
app.include_router(sandbox_router)
app.include_router(monitor_router)
app.include_router(speech_router)
app.include_router(qa_router)




@app.get("/", tags=["Health & Info"])
async def root():
    return {
        "service": "OpenDocs Voice & Learning Engine Backend",
        "status": "healthy",
        "version": "0.2.0",
        "docs": "/docs",
    }


@app.get("/healthz", tags=["Health & Info"])
async def health_check():
    return {"status": "ok"}
