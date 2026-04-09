from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
from src.api.routes import auth, student, tutor
from src.config import cfg, setup_environment

setup_environment()

app = FastAPI(title=cfg.app.name, version=cfg.app.version, debug=cfg.app.debug)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cfg.app.cors_origins,
    allow_origin_regex=(
        r"https?://(localhost|127\.0\.0\.1)(:\d+)?$" if cfg.is_development else None
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router)
app.include_router(tutor.router)
app.include_router(student.router)

uploads_dir = Path("uploads")
uploads_dir.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")


if __name__ == "__main__":
    uvicorn.run("src.main:app")
