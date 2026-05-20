from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import blueprints

app = FastAPI(title="Blueprint Extractor API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(blueprints.router, prefix="/api")
