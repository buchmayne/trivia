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

# SHOW ALL AVAILABLE GAMES TO CHOOSE FROM
@app.get("/game_ids/")
async def get_game_ids(request: Request):
    query = """SELECT distinct(game_id) FROM questions"""
    game_ids = await database.fetch_all(query)
    return templates.TemplateResponse("game_ids.html", {"request": request, "games": game_ids})

# FOR A SPECIFIC GAME, RETURN ALL OF THE QUESTIONS IN THAT GAME
@app.get("/game/{game_id}")
async def get_game_questions(request: Request, game_id: str):
    query = f"SELECT * FROM questions where game_id = '{game_id}'"
    questions = await database.fetch_all(query)
    return templates.TemplateResponse("questions.html", {"request": request, "questions": questions})

# FOR A SPECIFIC GAME, RETURN A SPECIFIC QUESTION
@app.get("/game/{game_id}/{question_number}")
async def get_question_from_game(request: Request, game_id: str, question_number: int):
    query = f"SELECT * FROM questions where game_id = '{game_id}' and question_number = {question_number}"
    question = await database.fetch_one(query)

    question_type = question["question_type"]
    
    if question_type == 'Single Slide Multiple Choice No Answer Bank':
        query_question_detail = f"""
            SELECT 
                * 
            FROM 
                choices_single_slide_multiple_choice_no_answer_bank
            WHERE
                game_id = '{game_id}' and question_number = {question_number}
        """
        question_detail = await database.fetch_all(query_question_detail)
        
        return templates.TemplateResponse("single_slide_multiple_choice_no_answer_bank.html", {"request": request, "question_detail": question_detail})
    else:
        return templates.TemplateResponse("question.html", {"request": request, "question": question})


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)