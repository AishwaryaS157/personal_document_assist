import os
import pathlib

from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.auth import get_current_user, COOKIE_NAME
from app.services.auth_service import (
    register_user,
    authenticate_user,
    create_access_token,
    DuplicateEmailError,
    InvalidCredentialsError,
)
from app.services.document_service import (
    ingest_document,
    list_documents,
    delete_document,
    search_documents,
)
from app.services.llm_service import stream_chat

app = FastAPI(title="Personal Document Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.environ.get("FRONTEND_URL", "http://localhost:5173")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md", ".markdown"}

COOKIE_KWARGS = dict(
    key=COOKIE_NAME,
    httponly=True,
    samesite="lax",
    secure=os.environ.get("ENVIRONMENT") == "production",
    path="/",
    max_age=60 * 60 * 24 * 7,
)


class RegisterRequest(BaseModel):
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


@app.post("/auth/register")
def register(body: RegisterRequest, response: Response):
    try:
        user = register_user(body.email, body.password)
    except DuplicateEmailError as e:
        raise HTTPException(409, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    token = create_access_token(user["id"], user["email"])
    response.set_cookie(value=token, **COOKIE_KWARGS)
    return {"email": user["email"]}


@app.post("/auth/login")
def login(body: LoginRequest, response: Response):
    try:
        user = authenticate_user(body.email, body.password)
    except InvalidCredentialsError as e:
        raise HTTPException(401, str(e))
    token = create_access_token(user["id"], user["email"])
    response.set_cookie(value=token, **COOKIE_KWARGS)
    return {"email": user["email"]}


@app.post("/auth/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@app.get("/auth/me")
def me(current_user: dict = Depends(get_current_user)):
    return {"email": current_user["email"]}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    ext = pathlib.Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")

    file_bytes = await file.read()
    try:
        metadata = ingest_document(file_bytes, file.filename, current_user["id"])
    except ValueError as e:
        raise HTTPException(422, str(e))
    return metadata


@app.get("/documents")
def get_documents(current_user: dict = Depends(get_current_user)):
    return list_documents(current_user["id"])


@app.delete("/documents/{doc_id}")
def remove_document(doc_id: str, current_user: dict = Depends(get_current_user)):
    deleted = delete_document(doc_id, current_user["id"])
    if not deleted:
        raise HTTPException(404, "Document not found")
    return {"deleted": doc_id}


class ChatRequest(BaseModel):
    message: str
    n_sources: int = 5


@app.post("/chat")
async def chat(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user),
):
    sources = search_documents(request.message, current_user["id"], n_results=request.n_sources)
    chunks = []
    async for chunk in stream_chat(request.message, sources):
        chunks.append(chunk)
    return StreamingResponse(iter(chunks), media_type="text/plain")
