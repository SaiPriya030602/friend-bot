from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import google.generativeai as genai
from dotenv import load_dotenv
from io import BytesIO
from docx import Document
import base64
import markdown2
import json
import uuid
import requests
import os
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware import Middleware
from fastapi.responses import Response



# LOAD ENV & CONFIG

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=api_key)

generation_config = {
    "temperature": 0.8,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 8192,
}

# ENABLE REAL-TIME SEARCH
safety_settings = {
    "google_search": {"enable": True}
}



# MODEL WITH SEARCH + FRIENDLY PERSONALITY

model = genai.GenerativeModel(
    
    model_name="gemini-2.5-flash",
    
    generation_config=generation_config,
    system_instruction=
    """
You are ChatterBot — a friendly, modern, conversational AI buddy.

Your personality:
- Warm, supportive, humorous when appropriate.
- Speak like a close, helpful friend.
- Keep responses natural, simple, and human-like.
- Be positive, engaging, and easy to talk to.

Your main goals:
1. Answer the user's question clearly.
2. Give helpful tips or suggestions related to their topic.
3. ALWAYS ask follow-up questions at the end to continue the conversation.

Follow-up question rules:
- If the topic is casual or simple (e.g., “hi”, greetings, small talk):
  → Ask **1–2** simple follow-up questions like:
    - “How can I help you today?”
    - “Is there anything you want to talk about?”

- If the topic is medium or practical (travel, movies, career advice, cooking, study tips):
  → Ask **2–3** helpful follow-up questions such as:
    - “Do you want suggestions?”
    - “Should I explain more?”
    - “Want me to recommend something else?”

- If the topic is complex (coding, debugging, documents, analysis, creative tasks):
  → Ask **3–5** meaningful follow-up questions like:
    - “Do you want this in another language?”
    - “Should I break this down step-by-step?”
    - “Do you want the optimized version?”
    - “Want me to generate more examples?”
    - “Do you want the explanation simplified?”

Important behavior:
- DO NOT give very long essays.
- Use short paragraphs and quick clarity.
- Add friendly transitions like “By the way…” or “If you’d like…”
- Maintain a smooth conversational flow.
- Adapt tone to the mood of the user (happy, confused, learning, etc.)
- If user uploads a file (PDF, image, docx, txt) explain the file clearly and ask related follow-up questions.

Your ultimate goal:
→ Be the user’s friendly AI partner who solves problems AND keeps the conversation going naturally.
    """
)

chat_session = model.start_chat(history=[])

# FASTAPI APP SETUP

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")



CHAT_FILE = "chat_history.json"

# HELPER FUNCTIONS

def load_chats():
    if not os.path.exists(CHAT_FILE):
        save_chats({})
        return {}

    try:
        with open(CHAT_FILE, "r", encoding="utf-8") as f:
            data = f.read().strip()
            if not data:
                save_chats({})
                return {}
            return json.loads(data)
    except:
        save_chats({})
        return {}

def save_chats(chats):
    with open(CHAT_FILE, "w", encoding="utf-8") as f:
        json.dump(chats, f, indent=4, ensure_ascii=False)

def create_new_chat(chats):
    chat_id = str(uuid.uuid4())[:8]
    chats[chat_id] = {"name": "New Chat", "messages": []}
    return chat_id

def generate_title_with_ai(prompt: str):
    try:
        title_model = genai.GenerativeModel("gemini-2.5-flash")
        result = title_model.generate_content(prompt)
        title = result.text.strip()

        # keep short
        if len(title) > 40:
            title = title[:40]

        return title if title else "New Chat"

    except Exception as e:
        print("Error generating title:", e)
        return "New Chat"
    
@app.middleware("http")
async def no_cache(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


# 1. Landing screen

@app.get("/welcome")
def welcome(request: Request):
    return templates.TemplateResponse("landing.html", {"request": request})

@app.get("/")
def root_redirect():
    return RedirectResponse("/welcome")

# PAGE ROUTES

@app.get("/chat", response_class=HTMLResponse)
async def home(request: Request, chat_id: str | None = None):
    chats = load_chats()

    if not chats:
        chat_id = create_new_chat(chats)
        save_chats(chats)

    if chat_id is None:
        chat_id = list(chats.keys())[-1]

    return templates.TemplateResponse(
        "home.html",
        {"request": request, "chats": chats, "current_chat_id": chat_id, "current_chat": chats.get(chat_id)}
    )


@app.get("/new")
async def new_chat():
    chats = load_chats()
    chat_id = create_new_chat(chats)
    save_chats(chats)
    return RedirectResponse(f"/chat?chat_id={chat_id}", status_code=303)



# DELETE CHAT

@app.api_route("/delete-chat", methods=["GET", "POST"])
async def delete_chat(chat_id: str = None):
    chats = load_chats()
    if chat_id in chats:
        del chats[chat_id]
        save_chats(chats)
    return RedirectResponse(f"/chat?chat_id={chat_id}", status_code=303)



# RENAME CHAT

@app.api_route("/rename-chat", methods=["POST"])
async def rename_chat(chat_id: str = Form(...), new_name: str = Form(...)):
    chats = load_chats()
    if chat_id in chats:
        chats[chat_id]["name"] = new_name.strip()
        save_chats(chats)
    return RedirectResponse(f"/chat?chat_id={chat_id}", status_code=303)



# MAIN CHAT HANDLER (TEXT + FILE)

@app.post("/chatter-bot")
async def chatter_response(
    request: Request,
    chat_id: str = Form(...),
    prompt: str = Form(""),
    file: UploadFile = File(None)
):
    chats = load_chats()
    if chat_id not in chats:
        chat_id = create_new_chat(chats)

    session = chats[chat_id]
    messages_for_model = []

    # USER PROMPT
    if prompt.strip():
        session["messages"].append({"role": "user", "html": prompt})
        messages_for_model.append({"text": prompt})

    # FILE HANDLING
    if file and file.filename:
        file_bytes = await file.read()
        filename = file.filename
        content_type = file.content_type or ""

        if content_type.startswith("image/"):
            b64 = base64.b64encode(file_bytes).decode()
            html = f'<img src="data:{content_type};base64,{b64}" class="uploaded-img" />'
            session["messages"].append({"role": "user", "html": html})
            messages_for_model.append({"inline_data": {"mime_type": content_type, "data": b64}})

        elif filename.lower().endswith(".pdf"):
            b64 = base64.b64encode(file_bytes).decode()
            session["messages"].append({"role": "user", "html": f"📄 {filename}"})
            messages_for_model.append({"inline_data": {"mime_type": "application/pdf", "data": b64}})

        elif filename.lower().endswith(".txt"):
            text = file_bytes.decode("utf-8", errors="ignore")
            session["messages"].append({"role": "user", "html": f"📄 {filename}"})
            messages_for_model.append({"text": text})

        elif filename.lower().endswith(".docx"):
            doc = Document(BytesIO(file_bytes))
            text = "\n".join(p.text for p in doc.paragraphs)
            session["messages"].append({"role": "user", "html": f"📄 {filename}"})
            messages_for_model.append({"text": text})

        else:
            session["messages"].append({"role": "user", "html": f"Unsupported file: {filename}"})


   
        
    # CALL GEMINI WITH SEARCH ENABLED
    if messages_for_model:
        response = chat_session.send_message(
            messages_for_model,
            
        )

        html_response = markdown2.markdown(
            response.text,
            extras=["break-on-newline", "fenced-code-blocks"],
            safe_mode=False
        )
        session["messages"].append({"role": "bot", "html": html_response})

        current_title = session.get("name", "").strip().lower()
        if (current_title == "new chat" or current_title.startswith("chat")) and len(session["messages"]) >= 2:

            first_user_message = session["messages"][0]["html"]

            title_prompt = (
                "Generate a short, descriptive 3-5 word title based ONLY on the user's message. "
                "Do NOT include phrases like 'here are a few options' or follow-up content.\n\n"
                f"User message: {first_user_message}"
            )
            new_title = generate_title_with_ai(title_prompt)
            session["name"] = new_title
        
    save_chats(chats)
    return RedirectResponse(f"/chat?chat_id={chat_id}", status_code=303)
