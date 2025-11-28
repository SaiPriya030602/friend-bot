# from fastapi import FastAPI
# #from gemini_api import GeminiClient
# import google.generativeai as genai
# from dotenv import load_dotenv
# import os

# load_dotenv()

# genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
# model = genai.GenerativeModel("gemini-2.5-flash")


# app = FastAPI()

# @app.get("/friend-bot")
# async def friend_bot(prompt: str):
#     #client = GeminiClient(api_key=os.getenv("GEMINI_API_KEY"))

#    #response = await client.generate_text(prompt="write a song about "+prompt)
#     response =  model.generate_content(prompt=(
#             f"You are a friendly AI assistant who gives natural and helpful "
#             f"suggestions like a close friend. Be kind, clear, and conversational. "
#             f"User asked about: {prompt}"
#         )
#     )

#     return {"response": response.text}