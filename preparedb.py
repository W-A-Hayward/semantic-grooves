# Add a new column to the database with a shortened review 
import sqlite3
import sqlite_vec
import 
import requests

def summarize_review(text):
    prompt = f"""
    Analyze this music review. Return ONLY a comma-separated list of:
    Genres, Emotions, and Key Instruments. The output should not be longer than 200 words.
    Review: {text[:2000]} 
    """
    response = requests.post('http://localhost:11434/api/generate', 
                             json={
                                 "model": "llama3",
                                 "prompt": prompt,
                                 "stream": False
                             })
    return response.json()['response']



