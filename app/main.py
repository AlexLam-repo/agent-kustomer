import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Arrancando agent-kustomer [{settings.environment}]")
    logger.info(f"DB host: {settings.db_host}:{settings.db_port}/{settings.db_name}")

    try:
        # Importar modelos para que SQLModel los registre
        import app.agents.models  # noqa
        import app.sessions.models  # noqa

        from app.db import init_db, AsyncSessionLocal
        from app.agents.service import seed_default_agent

        await init_db()
        async with AsyncSessionLocal() as db:
            await seed_default_agent(db)
        logger.info("Base de datos inicializada correctamente")
    except Exception as e:
        logger.error(f"Error inicializando BD (la app sigue corriendo): {e}")

    logger.info("Startup completo")
    yield
    logger.info("Apagando servidor")


app = FastAPI(
    title="Agent Kustomer",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check — siempre retorna 200, sin depender de la BD
# Railway hace el healthcheck a este endpoint
@app.get("/_/health")
async def health():
    return {"status": "ok", "environment": settings.environment}


@app.get("/")
async def root():
    return {"name": "agent-kustomer", "version": "1.0.0", "docs": "/docs"}


# Routers — importados aquí para evitar circular imports
from app.kustomer.router import router as kustomer_router  # noqa
from app.admin.router import router as admin_router  # noqa

app.include_router(kustomer_router)
app.include_router(admin_router)
