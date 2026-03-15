from fastapi import FastAPI
from api.routes import auth, tutor
import uvicorn

app = FastAPI()
app.include_router(auth.router)
app.include_router(tutor.router)
uvicorn.run(app=app)
