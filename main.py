from langgraph.graph import StateGraph, START, END
from state import StateClass
from nodes.resumeparserNode import parse_resume_node
from nodes.ProfileNode import profile_node
from nodes.savetodb import save_to_db_node
from nodes.jobsearchNode import job_search_node
from nodes.jobmatchnode import job_match_node
from db import init_db, get_user
import asyncio
import json

# ── routing logic ──────────────────────────────────────────────
def check_db_router(state: StateClass) -> str:
    """Check if user already exists in DB. If yes, skip to job search."""
    user_data = get_user(state["user_id"])
    if user_data:
        print(f"✅ User {state['user_id']} found in DB. Skipping to job search.")
        return "search_jobs"
    print(f"🆕 User {state['user_id']} not found. Starting from resume parsing.")
    return "parse_resume"

# ── build graph ────────────────────────────────────────────────
init_db()

builder = StateGraph(StateClass)

builder.add_node("parse_resume", parse_resume_node)
builder.add_node("ask_profile", profile_node)
builder.add_node("save_to_db", save_to_db_node)
builder.add_node("search_jobs", job_search_node)
builder.add_node("match_jobs", job_match_node)

# START → router decides which node to go to
builder.add_conditional_edges(
    START,
    check_db_router,
    {
        "parse_resume": "parse_resume",
        "search_jobs": "search_jobs"
    }
)

# New user path
builder.add_edge("parse_resume", "ask_profile")
builder.add_edge("ask_profile", "save_to_db")
builder.add_edge("save_to_db", "search_jobs")

# Shared path (both new and returning users)
builder.add_edge("search_jobs", "match_jobs")
builder.add_edge("match_jobs", END)

graph = builder.compile()

# ── run ────────────────────────────────────────────────────────
if __name__ == "__main__":
    initial_state = {
        "user_id": "test_user_001",
        "resume_file_path": "./resume_applied_ai_engineer.pdf",
        "resume_parsed": False,
        "profile_complete": False,
        "structured_profile": {},
        "full_resume_text": "",
        "user_answers": {},
        "job_search_complete": False,
        "raw_job_listings": [],
        "job_results": "",
        "job_match_complete": False
    }

    print("▶️ Starting LangGraph execution...\n")
    final_state = asyncio.run(graph.ainvoke(initial_state))

    print("\n✅ Graph Finished!")
    
    # 🎯 NEW: Print the structured profile in clean JSON format for your supervisor
    print("\n" + "="*80)
    print("📄 EXTRACTED STRUCTURED PROFILE (JSON):")
    print("="*80)
    
    # Try to get it from the final state first
    structured_profile = final_state.get("structured_profile")
    
    # If it's not in the final state (e.g., returning user who skipped parsing), fetch from DB
    if not structured_profile:
        user_data = get_user(initial_state["user_id"])
        if user_data:
            structured_profile = user_data.get("structured_profile", {})
            
    if structured_profile:
        # Pretty-print the JSON with an indent of 2 spaces
        print(json.dumps(structured_profile, indent=2))
    else:
        print("⚠️ No structured profile found.")
        
    print("="*80)

    print("\n--- JOB RECOMMENDATIONS ---")
    print(final_state["job_results"])