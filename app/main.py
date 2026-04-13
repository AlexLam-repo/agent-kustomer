import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Log exact DB config being used
    db_url = os.environ.get("DATABASE_URL", "")
    db_host = os.environ.get("DB_HOST", "localhost")
    logger.info(f"DATABASE_URL present: {bool(db_url)}")
    logger.info(f"DB_HOST: {db_host}")

    try:
        import app.agents.models  # noqa
        import app.sessions.models  # noqa
        from app.db import init_db, init_session_local
        init_session_local()
        await init_db()
        from app.db import AsyncSessionLocal
        from app.agents.service import seed_default_agent
        async with AsyncSessionLocal() as db:
            await seed_default_agent(db)
        logger.info("✓ Base de datos inicializada correctamente")
    except Exception as e:
        logger.error(f"✗ Error BD: {e}")

    logger.info("Startup completo")
    yield


app = FastAPI(title="Agent Kustomer", version="1.0.0", lifespan=lifespan, docs_url="/docs", redoc_url=None)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

from app.kustomer.router import router as kustomer_router  # noqa
from app.admin.router import router as admin_router  # noqa

app.include_router(kustomer_router)
app.include_router(admin_router)


@app.get("/_/health")
async def health():
    return {"status": "ok"}


@app.get("/")
async def root():
    path = os.path.join(os.path.dirname(__file__), "..", "frontend", "index.html")
    if os.path.exists(path):
        return FileResponse(path)
    return {"name": "agent-kustomer", "version": "1.0.0"}


frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_dir):
    app.mount("/frontend", StaticFiles(directory=frontend_dir), name="frontend")
