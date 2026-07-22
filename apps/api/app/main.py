from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import chat_router

app = FastAPI(
    title="LiveOS API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    chat_router,
    prefix="/api"
)


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