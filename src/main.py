from fastapi import FastAPI
import uvicorn
from src.api.routes import auth, student, tutor

app = FastAPI()
app.include_router(auth.router)
app.include_router(tutor.router)
app.include_router(student.router)


if __name__ == "__main__":
    uvicorn.run("src.main:app")
