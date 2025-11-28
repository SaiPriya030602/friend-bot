from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import google.generativeai as genai
from dotenv import load_dotenv
from fastapi import UploadFile, File
from io import BytesIO
from docx import Document
import base64
import markdown2
import os
# Load environment variables
load_dotenv()
# Configure Gemini
api_key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=api_key)
generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 8192,
    "response_mime_type": "text/plain",
}
# Initialize model
model = genai.GenerativeModel(
    model_name="gemini-2.5-flash",
    generation_config=generation_config,
    system_instruction="You're a friendly and conversational AI assistant who gives engaging, natural suggestions "
        "and advice on any topic (like a close friend). "
        "For example, if the user types 'vacation', suggest great travel ideas, destinations, and tips. "
        "If they ask about 'career' or 'movies', respond with useful, kind suggestions. "
        "Keep your tone upbeat, modern, and human-like."
)
# Start a chat session
chat_session = model.start_chat(history=[])
# FastAPI app setup
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
# Keep all conversations here
chat_history = []
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        "home.html",
        {"request": request, "chats": chat_history}
    )
@app.post("/chatter-bot", response_class=HTMLResponse)
async def chatter_response(
    request: Request,
    prompt: str = Form(""),
    file: UploadFile = File(None)
):
    try:
        messages = []
        # This will store the HTML for the user's part of the chat
        question_html = "" 
        # Add prompt (if typed)
        if prompt.strip():
            messages.append({"text": prompt})
            # Use <p> tag for consistent HTML formatting
            question_html += f"<p>{prompt}</p>" 
        # Process uploaded file (if any)
        if file is not None and file.filename != "":
            file_bytes = await file.read()
            b64_data = base64.b64encode(file_bytes).decode("utf-8")
            # IMAGE files (jpg, png, jpeg)
            if file.content_type.startswith("image/"):
                question_html += f'<img src="data:{file.content_type};base64,{b64_data}" class="uploaded-img" />'
                messages.append({
                    "inline_data": {
                        "mime_type": file.content_type,
                        "data": b64_data
                    }
                })
            # PDF files
            elif file.filename.lower().endswith(".pdf"):
                question_html += f"📄 Uploaded PDF: {file.filename}"
                messages.append({
                    "inline_data": {
                        "mime_type": "application/pdf",
                        "data": b64_data
                    }
                })
            # Text files
            elif file.filename.lower().endswith(".txt"):
                text_content = file_bytes.decode("utf-8")
                question_html += f"📄 Uploaded Text File: {file.filename}"
                messages.append({"text": text_content})
            # DOCX files
            elif file.filename.lower().endswith(".docx"):
                doc = Document(BytesIO(file_bytes))
                full_text = "\n".join([p.text for p in doc.paragraphs])
                question_html += f"📄 Uploaded Document: {file.filename}"
                messages.append({"text": full_text})
            # Unsupported file
            else:
                unsupported_msg = f"Unsupported file type: {file.filename}"
                question_html += unsupported_msg
                messages.append({"text": unsupported_msg})
        # === BUG FIX: Step 1 ===
        # Add a *single* entry to the history for this entire turn.
        # It will hold both the question and the (future) answer.
        chat_history.append({
            "question": question_html,
            "answer": "" # Start with an empty answer
        })
        # Send to Gemini
        response = chat_session.send_message(messages)
        text = response.text
        html_response = markdown2.markdown(
            text,
            extras=["break-on-newline", "fenced-code-blocks", "tables"]
        )
        # === BUG FIX: Step 2 ===
        # Update the 'answer' key of the *last* (most recent) history item.
        chat_history[-1]["answer"] = html_response
        # Return the template response, reloading the whole page (original behavior)
        return templates.TemplateResponse(
            "home.html",
            {"request": request, "chats": chat_history}
        )
    except Exception as e:
        # Updated error handling to be more consistent
        # Add the error as the "answer" to the last question
        error_msg = f"<b>Error:</b> {e}"
        if chat_history:
             # Add error as the answer to the last question
            chat_history[-1]["answer"] = error_msg
        else:
            # If history is empty, add a new entry for the error
            chat_history.append({
                "question": "Error",
                "answer": error_msg
            })
        return templates.TemplateResponse(
            "home.html",
            {"request": request, "chats": chat_history}
        )