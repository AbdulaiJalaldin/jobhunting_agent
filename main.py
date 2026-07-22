from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from state import StateClass
from nodes.resumeparserNode import parse_resume_node
from nodes.ProfileNode import profile_node
from nodes.savetodb import save_to_db_node
from nodes.jobsearchNode import job_search_node
from nodes.jobmatchnode import job_match_node
from nodes.askForNetworking import ask_networking_prompt
from nodes.networkingNode import networking_node
from db import init_db, get_user
import asyncio
import json


def check_db_router(state: StateClass) -> str:
    user_data = get_user(state["user_id"])
    if user_data:
        print(f"✅ User {state['user_id']} found in DB. Skipping to job search.")
        return "search_jobs"
    print(f"🆕 User {state['user_id']} not found. Starting from resume parsing.")
    return "parse_resume"


def route_networking(state: StateClass):
    if state.get("trigger_networking"):
        return "networking"
    return "end"


def build_graph():
    init_db()

    builder = StateGraph(StateClass)

    builder.add_node("parse_resume", parse_resume_node)
    builder.add_node("ask_profile", profile_node)
    builder.add_node("save_to_db", save_to_db_node)
    builder.add_node("search_jobs", job_search_node)
    builder.add_node("match_jobs", job_match_node)
    builder.add_node("ask_networking", ask_networking_prompt)
    builder.add_node("networking", networking_node)

    builder.add_conditional_edges(
        START,
        check_db_router,
        {
            "parse_resume": "parse_resume",
            "search_jobs": "search_jobs",
        },
    )

    builder.add_edge("parse_resume", "ask_profile")
    builder.add_edge("ask_profile", "save_to_db")
    builder.add_edge("save_to_db", "search_jobs")
    builder.add_edge("search_jobs", "match_jobs")
    builder.add_edge("match_jobs", "ask_networking")
    builder.add_conditional_edges(
        "ask_networking",
        route_networking,
        {
            "networking": "networking",
            "end": END,
        },
    )
    builder.add_edge("networking", END)

    checkpointer = InMemorySaver()
    return builder.compile(checkpointer=checkpointer)


graph = build_graph()


def make_initial_state(user_id: str, resume_file_path: str) -> dict:
    return {
        "user_id": user_id,
        "resume_file_path": resume_file_path,
        "resume_parsed": False,
        "profile_complete": False,
        "structured_profile": {},
        "full_resume_text": "",
        "user_answers": {},
        "job_search_complete": False,
        "raw_job_listings": [],
        "matched_jobs": [],
        "job_results": "",
        "job_match_complete": False,
        "trigger_networking": False,
        "recommended_companies": [],
        "networking_results": [],
        "networking_complete": False,
    }


async def run_until_pause_or_done(initial_state: dict, thread_id: str) -> dict:
    config = {"configurable": {"thread_id": thread_id}}
    result = await graph.ainvoke(initial_state, config)
    return result


async def resume_graph(thread_id: str, response) -> dict:
    config = {"configurable": {"thread_id": thread_id}}
    return await graph.ainvoke(Command(resume=response), config)


def get_graph_state(thread_id: str) -> dict | None:
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = graph.get_state(config)
    if snapshot and snapshot.values:
        return snapshot.values
    return None


if __name__ == "__main__":
    initial_state = make_initial_state(
        "test_user_001",
        "./resume_applied_ai_engineer.pdf",
    )
    thread_id = "cli-test-thread"

    async def cli_main():
        print("▶️ Starting LangGraph execution...\n")
        result = await run_until_pause_or_done(initial_state, thread_id)

        while result.get("__interrupt__"):
            interrupt_obj = result["__interrupt__"][0]
            payload = interrupt_obj.value
            print(f"\n⏸ Paused: {payload.get('message', payload)}\n")

            if payload.get("type") == "profile_questions":
                answers = {}
                for field in payload.get("fields", []):
                    answers[field["id"]] = input(f"{field['label']}\n> ").strip()
                result = await resume_graph(thread_id, answers)
            elif payload.get("type") == "networking_prompt":
                companies = ", ".join(payload.get("companies", []))
                print(f"Companies: {companies}")
                ans = input("Find decision-makers? (yes/no)\n> ").strip().lower()
                result = await resume_graph(thread_id, {"accept": ans in {"yes", "y", "yeah", "sure"}})
            else:
                ans = input("Your response:\n> ").strip()
                result = await resume_graph(thread_id, ans)

        print("\n✅ Graph Finished!")

        structured_profile = result.get("structured_profile")
        if not structured_profile:
            user_data = get_user(initial_state["user_id"])
            if user_data:
                structured_profile = user_data.get("structured_profile", {})

        print("\n" + "=" * 80)
        print("📄 EXTRACTED STRUCTURED PROFILE (JSON):")
        print("=" * 80)
        if structured_profile:
            print(json.dumps(structured_profile, indent=2))
        else:
            print("⚠️ No structured profile found.")
        print("=" * 80)

        print("\n--- JOB RECOMMENDATIONS ---")
        print(result.get("job_results", ""))

        if result.get("networking_complete") and result.get("networking_results"):
            print("\n--- NETWORKING CONTACTS ---")
            print(f"Successfully found {len(result['networking_results'])} decision-makers!")

    asyncio.run(cli_main())
