import os
import json
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from state import StateClass
from db import get_user
from nodes.filterjobs import shortlist_jobs

load_dotenv()

MATCH_SYSTEM_PROMPT = """You are a highly detail-oriented AI job coach and career advisor.
Your goal is to match and rank job listings against a user's full resume and preferences.

You will receive:
- USER_RESUME: full resume text for deep skill and experience matching
- USER_PREFERENCES: location, remote preference, and other answers
- JOB_LISTINGS: raw jobs fetched from a search API

Your responsibilities:
1. Read the resume carefully — note years of experience, tech stack, seniority, and career trajectory.
2. Score each job against the resume over 10. Consider:
   - Skill overlap (required skills vs user skills)
   - Location/remote alignment with preferences
   - Growth potential and role relevance
3. Select the top 3-5 jobs only. Discard weak matches.
4. For each recommended job provide:
   - Job title and company
   - Location (remote/hybrid/on-site)
   - Why it fits this specific user (brief summary)
   - Any honest caveats if the match isn't perfect
   - Apply URL
5. Start with a 1-2 sentence summary of the overall search quality.
6. Be honest — if results are weak, say so and suggest better search terms.
7. Never hallucinate job details. Only use what is in JOB_LISTINGS.

Tone: supportive, practical, and clear. You are on the user's side.
"""

def job_match_node(state: StateClass):
    print(f"🎯 Matching jobs for user: {state['user_id']}")

    user_data = get_user(state["user_id"])
    if not user_data:
        raise RuntimeError(f"User {state['user_id']} not found in DB.")

    full_resume_text = user_data["full_resume_text"]
    user_answers = user_data["user_answers"]
    raw_job_listings = state["raw_job_listings"]

    if not raw_job_listings:
        return {
            "job_results": "No job listings were found to match against. Try refining your search.",
            "job_match_complete": True
        }

    # Pre-filter to top 8 most relevant jobs (no truncation needed — quality over quantity)
    user_data = get_user(state["user_id"])
    structured_profile = user_data["structured_profile"]
    shortlisted = shortlist_jobs(raw_job_listings, structured_profile)

    # Now you can afford 800 chars per description since you only have 8 jobs
    jobs_for_llm = []
    for job in shortlisted:
        job_copy = job.copy()
        job_copy["description"] = job.get("description", "")[:800]
        jobs_for_llm.append(job_copy)

    user_message = f"""
USER_RESUME:
{full_resume_text}

USER_PREFERENCES:
{json.dumps(user_answers, indent=2)}

JOB_LISTINGS:
{json.dumps(jobs_for_llm, indent=2)}

Please match, score, and recommend the best jobs for this user.
"""

    messages = [
        SystemMessage(content=MATCH_SYSTEM_PROMPT),
        HumanMessage(content=user_message)
    ]

    # 🚀 Initialize ChatGroq (No more raw HTTP requests!)
    llm = ChatGroq(
        model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        temperature=0.3, # Slightly higher temperature for a better coaching tone
        api_key=os.getenv("GROQ_API_KEY")
    )

    # Invoke the LLM
    response = llm.invoke(messages)
    final_response = response.content

    print("✅ Job matching complete.")
    
    # 🎉 TERMINAL DISPLAY FOR SUPERVISOR
    print("\n" + "="*80)
    print("🏆 AI JOB COACH RECOMMENDATIONS:")
    print("="*80)
    print(final_response)
    print("="*80 + "\n")

    return {
        "job_results": final_response,
        "job_match_complete": True
    }