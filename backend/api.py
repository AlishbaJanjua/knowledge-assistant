import base64
import logging
import os
import time
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr

from fastapi.responses import FileResponse
from agents.chunking_agent import analyze_and_chunk
from agents.memory_agent import delete_memory, invoke_config, load_memory
from agents.voice_agent import speech_to_text, text_to_speech
from backend.config import CARTESIA_API_KEY
from backend.otp import (
    OTP_REQUEST_COOLDOWN_SECONDS,
    clear_otp,
    cooldown_remaining,
    create_and_store_otp,
    send_otp_email,
    verify_otp,
)
from graph.workflow import app as agent_graph
from loaders.loader import load_document
from utils.helpers import (
    create_tenant_folder,
    delete_upload,
    get_document,
    list_uploads,
    register_upload,
    save_file_bytes,
    sync_registry_from_folder,
)
from vectorstore.chroma_db import create_vectorstore, delete_vectorstore, load_vectorstore

AUDIO_MIME = "audio/wav"

logger = logging.getLogger(__name__)

FRONTEND_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "frontend",
)

EMBED_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "embed",
)

ALLOWED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".txt",
    ".csv",
    ".pptx",
    ".md",
    ".html",
    ".htm",
}

api = FastAPI(title="Knowledge Assistant API")

api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    email: EmailStr
    document_id: str
    question: str


class EmailRequest(BaseModel):
    email: EmailStr


class DeleteDocumentRequest(BaseModel):
    email: EmailStr
    document_id: str


class SpeakRequest(BaseModel):
    text: str


class OtpRequest(BaseModel):
    email: EmailStr


class OtpVerifyRequest(BaseModel):
    email: EmailStr
    otp: str


def _tenant_from_email(email: str):

    tenant_id, folder = create_tenant_folder(email)
    sync_registry_from_folder(tenant_id, folder)
    return tenant_id, folder


def _speech_payload(text: str) -> dict:

    if not CARTESIA_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="CARTESIA_API_KEY is not configured.",
        )

    try:
        audio = text_to_speech(text)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Voice generation failed: {exc}",
        ) from exc

    return {
        "audio": base64.b64encode(audio).decode("ascii"),
        "audio_type": AUDIO_MIME,
    }


@api.get("/api/health")
def health():

    return {
        "status": "ok",
        "voice": bool(CARTESIA_API_KEY),
    }


@api.post("/api/auth/request-otp")
def request_otp(body: OtpRequest):
    """Send a 6-digit OTP to the email used by the existing login gate."""

    email = str(body.email)
    wait = cooldown_remaining(email)

    if wait > 0:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Please wait {wait} seconds before requesting another code."
            ),
        )

    otp, expires_in = create_and_store_otp(email)

    try:
        send_otp_email(email, otp)
    except Exception as exc:
        clear_otp(email)
        logger.exception("Failed to send OTP email")
        raise HTTPException(
            status_code=502,
            detail="Could not send verification email. Try again shortly.",
        ) from exc

    return {
        "status": "sent",
        "expires_in": expires_in,
        "cooldown": OTP_REQUEST_COOLDOWN_SECONDS,
    }


@api.post("/api/auth/verify-otp")
def verify_otp_endpoint(body: OtpVerifyRequest):
    """Verify the OTP for the email-gate login. Code is single-use."""

    ok, reason = verify_otp(str(body.email), body.otp)

    if ok:
        return {
            "status": "verified",
            "email": str(body.email).strip().lower(),
        }

    if reason == "expired":
        raise HTTPException(
            status_code=400,
            detail="Code expired or not found. Request a new one.",
        )

    if reason == "locked":
        raise HTTPException(
            status_code=400,
            detail="Too many invalid attempts. Request a new code.",
        )

    raise HTTPException(
        status_code=400,
        detail="Invalid verification code.",
    )


@api.get("/widget")
def chatbot_widget():

    return FileResponse(
        os.path.join(FRONTEND_DIR, "widget.html")
    )

@api.post("/api/documents")
def get_documents(body: EmailRequest):

    tenant_id, folder = _tenant_from_email(body.email)
    uploads = list_uploads(tenant_id)

    return {
        "documents": [
            {
                "document_id": item["document_id"],
                "filename": item["filename"],
                "uploaded_at": item["uploaded_at"],
                "strategy": item.get("chunking_strategy"),
                "reason": item.get("chunking_reason"),
            }
            for item in uploads
        ]
    }


@api.delete("/api/documents")
def remove_document(body: DeleteDocumentRequest):

    tenant_id, _ = _tenant_from_email(body.email)
    deleted = delete_upload(tenant_id, body.document_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found.")

    delete_memory(body.email, body.document_id)
    delete_vectorstore(tenant_id, body.document_id)

    return {
        "status": "deleted",
        "document_id": body.document_id,
        "filename": deleted.get("filename"),
    }


@api.get("/api/history")
def get_history(
    email: EmailStr = Query(...),
    document_id: str = Query(...),
):

    tenant_id, _ = _tenant_from_email(email)
    history = load_memory(email, document_id)
    doc = get_document(tenant_id, document_id)

    return {
        "history": history,
        "strategy": doc.get("chunking_strategy") if doc else None,
        "reason": doc.get("chunking_reason") if doc else None,
    }


@api.post("/api/upload")
async def upload_document(
    email: EmailStr = Form(...),
    file: UploadFile = File(...),
):

    extension = os.path.splitext(file.filename or "")[1].lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {extension}",
        )

    tenant_id, folder = _tenant_from_email(email)
    content = await file.read()

    if not content:
        raise HTTPException(status_code=400, detail="Empty file.")

    path = save_file_bytes(content, file.filename, folder)

    upload_started = time.perf_counter()

    step_started = time.perf_counter()
    docs = load_document(path)
    load_elapsed = time.perf_counter() - step_started

    step_started = time.perf_counter()
    result = analyze_and_chunk(docs, path)
    analyze_elapsed = time.perf_counter() - step_started

    document_id = register_upload(
        tenant_id,
        file.filename,
        path,
        strategy=result["applied_strategy"],
        reason=result["reason"],
    )

    step_started = time.perf_counter()
    create_vectorstore(result["chunks"], tenant_id, document_id)
    vectorstore_elapsed = time.perf_counter() - step_started

    total_elapsed = time.perf_counter() - upload_started
    summary = (
        f"[timing] upload_pipeline total={total_elapsed:.3f}s | "
        f"load_document={load_elapsed:.3f}s | "
        f"analyze_and_chunk={analyze_elapsed:.3f}s | "
        f"create_vectorstore={vectorstore_elapsed:.3f}s | "
        f"file={file.filename} chunks={result['chunk_count']} "
        f"strategy={result['applied_strategy']}"
    )
    logger.info(summary)
    print(summary, flush=True)

    return {
        "document_id": document_id,
        "filename": file.filename,
        # `strategy` = applied (honest / backward-compatible for existing UI)
        "strategy": result["applied_strategy"],
        "recommended_strategy": result["recommended_strategy"],
        "applied_strategy": result["applied_strategy"],
        "reason": result["reason"],
        "chunk_count": result["chunk_count"],
        "fallback": result.get("fallback", False),
    }


@api.post("/api/chat")
def chat(body: ChatRequest):

    tenant_id, _ = _tenant_from_email(body.email)
    db = load_vectorstore(tenant_id, body.document_id)

    if not db:
        raise HTTPException(
            status_code=404,
            detail="Document knowledge base not found.",
        )

    # Same thread_id across turns for this email+document (short-term memory).
    # db is loaded inside the graph (not passed) so checkpoints stay serializable.
    result = agent_graph.invoke(
        {
            "question": body.question,
            "email": body.email,
            "document_id": body.document_id,
        },
        config=invoke_config(body.email, body.document_id),
    )

    answer = result["answer"]

    speech = _speech_payload(answer)

    return {
        "answer": answer,
        **speech,
    }


@api.post("/api/speak")
def speak(body: SpeakRequest):

    text = body.text.strip()

    if not text:
        raise HTTPException(status_code=400, detail="Empty text.")

    speech = _speech_payload(text)
    audio = base64.b64decode(speech["audio"])

    return Response(content=audio, media_type=AUDIO_MIME)


@api.post("/api/transcribe")
async def transcribe(file: UploadFile = File(...)):

    audio_bytes = await file.read()

    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file.")

    try:
        text = speech_to_text(audio_bytes)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"text": text}


if os.path.isdir(EMBED_DIR):
    api.mount(
        "/embed",
        StaticFiles(directory=EMBED_DIR),
        name="embed",
    )

if os.path.isdir(FRONTEND_DIR):
    api.mount(
        "/",
        StaticFiles(directory=FRONTEND_DIR, html=True),
        name="frontend",
    )
