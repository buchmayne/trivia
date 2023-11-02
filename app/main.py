from typing import Union
import os

from fastapi import FastAPI
from dotenv import load_dotenv
from databases import Database

load_dotenv()

POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
POSTGRES_DB = os.getenv("POSTGRES_DB")

DATABASE_URL = f"postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@db/{POSTGRES_DB}"

database = Database(DATABASE_URL)



app = FastAPI()

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
async def read_questions():
    query = "SELECT * FROM questions"
    results = await database.fetch_all(query)
    return results