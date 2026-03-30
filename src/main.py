from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import uvicorn
from api.routes import auth, student, tutor

app = FastAPI()
app.include_router(auth.router)
app.include_router(tutor.router)
app.include_router(student.router)

uploads_dir = Path("uploads")
uploads_dir.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")


if __name__ == "__main__":
    uvicorn.run("main:app")
