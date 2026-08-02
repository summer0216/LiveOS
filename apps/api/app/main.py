from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import chat_router
from app.api.conversation import router as conversation_router
from app.api.decision_history import router as decision_history_router
from app.api.decisions import router as decisions_router
from app.api.memories import router as memories_router
from app.api.profile import router as profile_router
from app.api.properties import router as properties_router
from app.core.config import settings

app = FastAPI(
    title="LiveOS API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router, prefix="/api")
app.include_router(conversation_router, prefix="/api")
app.include_router(profile_router, prefix="/api")
app.include_router(properties_router, prefix="/api")
app.include_router(decisions_router, prefix="/api")
app.include_router(decision_history_router, prefix="/api")
app.include_router(memories_router, prefix="/api")


@app.get("/")
async def root():
    return {
        "project": "LiveOS",
        "version": "0.1.0",
    }


@app.get("/health")
async def health():
    return {
        "status": "ok",
    }
