# DEO GLORIA

"""Punto de entrada de la API de eduTockens."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.database import init_db
from routers import admin, auth, products, purchases, relay, students, users


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="eduTockens API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(products.router, prefix="/api")
app.include_router(purchases.router, prefix="/api")
app.include_router(relay.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(students.router, prefix="/api")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}