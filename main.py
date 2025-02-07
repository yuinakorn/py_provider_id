from fastapi import FastAPI
from routers import router

app = FastAPI(docs_url="/docs-api", redoc_url=None)

app.include_router(router)


