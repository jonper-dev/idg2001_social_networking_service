from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from app.db import get_db
from app.routes import users, posts, auth_routes ## Importing our route modules

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    ## Allowed origins, frontend during development, more when deploying.
    allow_origins=[
        "http://127.0.0.1:5500",
        "https://idg2001-o1-social-networking-service.onrender.com"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Server is running"}

## Including the routers from other files.
app.include_router(users.router)
app.include_router(posts.router, prefix="/posts", tags=["Posts"])
app.include_router(auth_routes.router)
