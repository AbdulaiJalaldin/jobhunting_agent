import os
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from main import get_graph_state, graph, make_initial_state, resume_graph, run_until_pause_or_done

load_dotenv()

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="MatchAI API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = Path(__file__).parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


class ResumeRequest(BaseModel):
    thread_id: str
    response: dict | str | bool


def _serialize_interrupt(result: dict) -> dict | None:
    interrupts = result.get("__interrupt__")
    if not interrupts:
        return None
    interrupt_obj = interrupts[0]
    payload = interrupt_obj.value
    if not isinstance(payload, dict):
        payload = {"type": "text", "message": str(payload)}
    return {
        "id": interrupt_obj.id,
        **payload,
    }


def _serialize_state(state: dict) -> dict:
    structured_profile = state.get("structured_profile") or {}
    if not structured_profile and state.get("user_id"):
        from db import get_user

        user_data = get_user(state["user_id"])
        if user_data:
            structured_profile = user_data.get("structured_profile") or {}

    return {
        "structured_profile": structured_profile,
        "user_answers": state.get("user_answers") or {},
        "job_results": state.get("job_results") or "",
        "matched_jobs": state.get("matched_jobs") or [],
        "networking_results": state.get("networking_results") or [],
        "networking_complete": state.get("networking_complete", False),
        "job_match_complete": state.get("job_match_complete", False),
        "resume_parsed": state.get("resume_parsed", False),
        "profile_complete": state.get("profile_complete", False),
    }


def _build_response(result: dict, thread_id: str) -> dict:
    interrupt = _serialize_interrupt(result)
    if interrupt:
        state = get_graph_state(thread_id) or {}
        return {
            "status": "interrupted",
            "thread_id": thread_id,
            "interrupt": interrupt,
            **_serialize_state(state),
        }

    return {
        "status": "completed",
        "thread_id": thread_id,
        "interrupt": None,
        **_serialize_state(result),
    }


@app.get("/")
async def serve_frontend():
    index_path = FRONTEND_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Frontend not found")
    return FileResponse(index_path)


@app.post("/api/start")
async def start_session(
    user_id: str = Form(...),
    resume: UploadFile = File(...),
):
    if not resume.filename:
        raise HTTPException(status_code=400, detail="Resume file is required")

    suffix = Path(resume.filename).suffix.lower()
    if suffix not in {".pdf", ".doc", ".docx", ".txt"}:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    thread_id = str(uuid.uuid4())
    safe_name = f"{thread_id}{suffix}"
    file_path = UPLOAD_DIR / safe_name

    content = await resume.read()
    file_path.write_bytes(content)

    initial_state = make_initial_state(user_id, str(file_path))
    try:
        result = await run_until_pause_or_done(initial_state, thread_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return _build_response(result, thread_id)


@app.post("/api/resume")
async def resume_session(body: ResumeRequest):
    config = {"configurable": {"thread_id": body.thread_id}}
    snapshot = graph.get_state(config)
    if not snapshot or not snapshot.values:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        result = await resume_graph(body.thread_id, body.response)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return _build_response(result, body.thread_id)


@app.get("/api/state/{thread_id}")
async def get_session_state(thread_id: str):
    state = get_graph_state(thread_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "ok", "thread_id": thread_id, **_serialize_state(state)}


if __name__ == "__main__":
    import uvicorn

    host = "127.0.0.1"
    port = 8000
    print(f"\n  MatchAI running at http://localhost:{port}\n")
    uvicorn.run("app:app", host=host, port=port, reload=True)
