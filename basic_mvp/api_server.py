from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

from chat_backend import (
    get_latest_assistant_audio,
    get_current_session,
    get_roadmap_payload,
    process_user_message,
    start_module_session,
)
from data_paths import normalize_user_id
from user_store import create_user, get_last_active_user, initialize_user_store, list_users, set_last_active_user


class CreateUserRequest(BaseModel):
    profile_name: str


class SelectUserRequest(BaseModel):
    user_id: str


class ChatMessageRequest(BaseModel):
    user_id: str
    message: str


class StartModuleRequest(BaseModel):
    user_id: str
    module_id: str


app = FastAPI(title="Camino API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    initialize_user_store()


@app.get("/api/users")
def get_users():
    current = get_last_active_user() or initialize_user_store()
    return {"users": list_users(), "current_user_id": current}


@app.post("/api/users")
def post_user(request: CreateUserRequest):
    user = create_user(request.profile_name)
    if user is None:
        raise HTTPException(status_code=400, detail="Profile name is required.")
    return {"user": user, "current_user_id": user["user_id"]}


@app.post("/api/users/select")
def select_user(request: SelectUserRequest):
    user_id = normalize_user_id(request.user_id)
    set_last_active_user(user_id)
    return {
        "current_user_id": user_id,
        "session": get_current_session(user_id),
        "roadmap": get_roadmap_payload(user_id),
    }


@app.get("/api/roadmap")
def get_roadmap(user_id: str | None = None):
    current_user_id = normalize_user_id(user_id or get_last_active_user() or initialize_user_store())
    set_last_active_user(current_user_id)
    return get_roadmap_payload(current_user_id)


@app.get("/api/session/current")
def get_session(user_id: str | None = None):
    current_user_id = normalize_user_id(user_id or get_last_active_user() or initialize_user_store())
    set_last_active_user(current_user_id)
    return get_current_session(current_user_id)


@app.post("/api/session/start")
def post_session_start(request: StartModuleRequest):
    user_id = normalize_user_id(request.user_id)
    set_last_active_user(user_id)
    return start_module_session(user_id, request.module_id)


@app.post("/api/chat/message")
def post_chat_message(request: ChatMessageRequest):
    user_id = normalize_user_id(request.user_id)
    set_last_active_user(user_id)
    return process_user_message(user_id, request.message)


@app.get("/api/audio/latest")
def get_latest_audio(user_id: str | None = None):
    current_user_id = normalize_user_id(user_id or get_last_active_user() or initialize_user_store())
    set_last_active_user(current_user_id)
    audio_bytes = get_latest_assistant_audio(current_user_id)
    if not audio_bytes:
        raise HTTPException(status_code=404, detail="No assistant audio available.")
    return Response(content=audio_bytes, media_type="audio/wav")
