from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routers import fill, preview, template, upload

app = FastAPI(title="PDF Filler")

app.include_router(upload.router)
app.include_router(preview.router)
app.include_router(template.router)
app.include_router(fill.router)

app.mount("/", StaticFiles(directory="app/static", html=True), name="static")
