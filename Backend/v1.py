import json

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import os
import uuid
import shutil

app = FastAPI()

# Allow the frontend to call the API when opened directly from disk
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "Frontend",
    "index.html",
)

# ==========================================
# CONFIG
# ==========================================

HAKIM_API_KEY = os.getenv("HAKIM_API_KEY")
HEADERS = {
    "Authorization": f"Bearer {HAKIM_API_KEY}"
}

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:4b")

AUDIO_FOLDER = "audio"
os.makedirs(AUDIO_FOLDER, exist_ok=True)

# ==========================================
# PREDEFINED VOICES
# ==========================================

AVAILABLE_VOICES = [
    
    
    {
        "id": "cmok1nvqa000f10ar8rpvncj4",
        "name": "Khaled - Arabic"
    },
    {
        "id": "cmokbc1rj0005vu3915vh4ehn",
        "name": "Layan-Saudi-arabic"
    },
    {
        "id": "edward-en-gb",
        "name": "Britsh English - Edward"
    },
    {
        "id": "cmok1nvnw000710arovur4fzz",
        "name": "American English - Sarah"
    }
    
]

# ==========================================
# REQUEST MODEL
# ==========================================

class TTSRequest(BaseModel):
    text: str
    voice: str

# ==========================================
# HOME
# ==========================================

@app.get("/")
def home():
    return {
        "message": "Hakim AI FastAPI Backend",
        "routes": [
            "/app",
            "/voices",
            "/tts",
            "/stt",
            "/lesson"
        ]
    }

# ==========================================
# SERVE FRONTEND
# ==========================================

@app.get("/app")
def frontend():
    return FileResponse(FRONTEND_FILE, media_type="text/html")

# ==========================================
# GET AVAILABLE VOICES
# ==========================================

@app.get("/voices")
def get_voices():
    return {
        "voices": AVAILABLE_VOICES
    }

# ==========================================
# TEXT TO SPEECH
# ==========================================

@app.post("/tts")
def text_to_speech(data: TTSRequest):

    # ==========================
    # VALIDATE VOICE
    # ==========================

    valid_voice_ids = [v["id"] for v in AVAILABLE_VOICES]

    if data.voice not in valid_voice_ids:
        raise HTTPException(
            status_code=400,
            detail="Invalid voice selected"
        )

    # ==========================
    # PAYLOAD
    # ==========================

    payload = {
        "model": "hakim-fast-v1",
        "voice": data.voice,
        "input": data.text
    }

    # ==========================
    # CALL HAKIM API
    # ==========================

    response = requests.post(
        "https://api.tryhakim.ai/v1/audio/speech",
        headers={
            **HEADERS,
            "Content-Type": "application/json"
        },
        json=payload
    )

    content_type = response.headers.get("Content-Type", "")

    # ==========================
    # HANDLE API ERROR
    # ==========================

    if "application/json" in content_type:
        return JSONResponse(
            status_code=response.status_code,
            content=response.json()
        )

    # ==========================
    # SAVE AUDIO
    # ==========================

    filename = f"{uuid.uuid4()}.mp3"
    filepath = os.path.join(AUDIO_FOLDER, filename)

    with open(filepath, "wb") as f:
        f.write(response.content)

    # ==========================
    # RETURN AUDIO
    # ==========================

    return FileResponse(
        path=filepath,
        media_type="audio/mpeg",
        filename="speech.mp3"
    )

# ==========================================
# SPEECH TO TEXT
# ==========================================

@app.post("/stt")
async def speech_to_text(file: UploadFile = File(...)):

    temp_path = f"{AUDIO_FOLDER}/{file.filename}"

    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    response = requests.post(
        "https://api.tryhakim.ai/v1/audio/transcriptions",
        headers=HEADERS,
        files={
            "file": (
                file.filename,
                open(temp_path, "rb"),
                file.content_type
            )
        },
        data={
            "model": "hakim-arab-v2"
        }
    )

    try:
        return response.json()

    except:
        raise HTTPException(
            status_code=500,
            detail="Invalid response from Hakim API"
        )
    
# ==========================================
# GENERATE LESSON with LLM
# ==========================================
class LessonRequest(BaseModel):
    topic: str
    language: str = "english"
    native_language: str = "english"
    level: str = "beginner"

def generate_lesson(topic: str, language: str, native_language: str, level: str):

    prompt = f"""
You are an expert {language} teacher.

STUDENT PROFILE

- Language to learn: {language}
- Native language (for explanations): {native_language}
- Level: {level}
- Topic: {topic}

TEACHING GOAL

Apply the Pareto Principle:
Teach the 20% of vocabulary and expressions that provide 80% of real-world communication for this topic.

RULES

- Write every "meaning" and "usage" field in {native_language} so the student understands.
- Keep every "word", "example", "expression", dialogue "text" and "question" in {language}.
- Focus on practical spoken language.
- Use natural, everyday conversations.
- Avoid academic, literary, technical, or rare vocabulary.
- Adapt explanations to the student's level.
- Every example must sound natural.
- Every dialogue must be realistic.
- Keep the lesson concise.
- Return ONLY valid JSON.
- No markdown.
- No explanations outside JSON.

LEVEL ADAPTATION

If level = beginner:
- Very simple words
- Very short sentences
- Basic vocabulary

If level = intermediate:
- More natural expressions
- Slightly longer examples
- Common everyday conversations

If level = advanced:
- Nuanced vocabulary
- Idiomatic expressions
- Natural native-level conversations

OUTPUT FORMAT

{{
  "topic": "",
  "language": "",
  "native_language": "",
  "level": "",

  "words": [
    {{
      "word": "",
      "part_of_speech": "",
      "meaning": "",
      "example": ""
    }}
  ],

  "expressions": [
    {{
      "expression": "",
      "usage": ""
    }}
  ],

  "dialogue": [
    {{
      "speaker": "A",
      "text": ""
    }},
    {{
      "speaker": "B",
      "text": ""
    }}
  ],

  "question": ""
}}

CONSTRAINTS

- Generate EXACTLY 7 words.
- Generate EXACTLY 5 expressions.
- Generate a dialogue with 4 to 6 exchanges.
- Use lesson vocabulary inside the dialogue.
- Question must be answerable using the lesson.
- Keep total output under 400 words.

IMPORTANT:
Return valid JSON only.
Do not use markdown.
Do not wrap JSON inside ```json blocks.
Do not add any text before or after the JSON.
"""
    try:

        response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "format": "json"
            },
            timeout=300
        )

        response.raise_for_status()

        result = response.json()

        lesson_text = result["response"].strip()

        # supprimer éventuels blocs markdown
        lesson_text = lesson_text.replace("```json", "")
        lesson_text = lesson_text.replace("```", "")
        lesson_text = lesson_text.strip()

        # garder uniquement l'objet JSON (le modèle ajoute parfois du texte autour)
        start = lesson_text.find("{")
        end = lesson_text.rfind("}")
        if start != -1 and end > start:
            lesson_text = lesson_text[start:end + 1]

        return json.loads(lesson_text)

    except json.JSONDecodeError:

        raise HTTPException(
            status_code=500,
            detail="LLM returned invalid JSON"
        )

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"Ollama error: {str(e)}"
        )

@app.post("/lesson")
def create_lesson(data: LessonRequest):

    lesson = generate_lesson(
        topic=data.topic,
        language=data.language,
        native_language=data.native_language,
        level=data.level
    )

    return lesson



