from fastapi import FastAPI
from api.routes import auth
import uvicorn

app = FastAPI()
app.include_router(auth.router)
uvicorn.run(app=app)
