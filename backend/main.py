# TODO: Create the FastAPI application, include routers, add middleware, and register startup/shutdown events.

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

# Import database initialization
# from core.database import engine, Base, init_db


# Placeholder for database initialization
async def startup_event():
    """
    Startup event: initialize database tables if needed
    """
    print("Starting up EduTokens backend...")
    # await init_db()


async def shutdown_event():
    """
    Shutdown event: cleanup resources
    """
    print("Shutting down EduTokens backend...")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events
    """
    await startup_event()
    yield
    await shutdown_event()


# Create FastAPI application
app = FastAPI(
    title="EduTokens API",
    description="Sistema de Aplicación Web — Puntos Académicos sobre Blockchain",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import and include routers
from routers import auth, users, products, purchases, admin

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(products.router, prefix="/api/products", tags=["products"])
app.include_router(purchases.router, prefix="/api/purchases", tags=["purchases"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])


# Health check endpoint
@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": "edutoken-backend",
    }


# Root endpoint
@app.get("/api")
async def root():
    return {
        "message": "Bienvenido a EduTokens API",
        "docs": "/docs",
        "version": "1.0.0",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)