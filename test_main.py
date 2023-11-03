from typing import Union
import os

from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
from databases import Database
import uvicorn

# DB CONNECTION
load_dotenv()

POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
POSTGRES_DB = os.getenv("POSTGRES_DB")

DATABASE_URL = f"postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@localhost/{POSTGRES_DB}"
database = Database(DATABASE_URL)

# APP
app = FastAPI()

templates = Jinja2Templates(directory="templates")

@app.on_event("startup")
async def startup():
    await database.connect()

@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()

@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/questions/")
async def read_questions(request: Request):
    query = "SELECT * FROM questions"
    questions = await database.fetch_all(query)
    return templates.TemplateResponse("questions.html", {"request": request, "questions": questions})


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)