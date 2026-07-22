import json
import os
import re
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
- JOB_LISTINGS: pre-filtered jobs fetched from a search API

Your responsibilities:
1. Read the resume carefully — note years of experience, tech stack, seniority, and career trajectory.
2. Score each job against the resume out of 10. Consider skill overlap, location/remote alignment, and role relevance.
3. Select the top 3-5 jobs only. Discard weak matches. Never return more than 5.
4. Be honest — if results are weak, say so in the summary and suggest better search terms.
5. Never hallucinate job details. Only recommend jobs that appear in JOB_LISTINGS.

RESPONSE FORMAT — return ONLY valid JSON, no markdown, no code fences, no extra text:
{
  "summary": "1-2 sentence overview of search quality and overall fit",
  "recommendations": [
    {
      "apply_url": "exact apply_url from JOB_LISTINGS",
      "score": 8,
      "why_it_fits": "2-3 sentences explaining why this job fits this specific user"
    }
  ]
}

Rules for recommendations:
- Each apply_url MUST exactly match one job in JOB_LISTINGS.
- Include score as an integer from 1-10.
- Do NOT include apply links, caveats sections, or markdown formatting in why_it_fits.
- Do NOT mention missing information as a separate caveats block — fold honest notes briefly into why_it_fits if needed.
"""


def _parse_llm_json(content: str) -> dict:
    text = content.strip()
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if fence_match:
        text = fence_match.group(1).strip()
    return json.loads(text)


def _resolve_matched_jobs(recommendations: list, shortlisted: list) -> list:
    jobs_by_url = {
        job.get("apply_url"): job
        for job in shortlisted
        if job.get("apply_url")
    }

    matched = []
    seen_urls = set()
    for rec in recommendations[:5]:
        url = rec.get("apply_url")
        if not url or url in seen_urls:
            continue
        job = jobs_by_url.get(url)
        if not job:
            continue
        seen_urls.add(url)
        enriched = job.copy()
        enriched["match_score"] = rec.get("score")
        enriched["why_it_fits"] = rec.get("why_it_fits", "")
        matched.append(enriched)

    return matched


def job_match_node(state: StateClass):
    print(f"Matching jobs for user: {state['user_id']}")

    user_data = get_user(state["user_id"])
    if not user_data:
        raise RuntimeError(f"User {state['user_id']} not found in DB.")

    full_resume_text = user_data["full_resume_text"]
    user_answers = user_data["user_answers"]
    raw_job_listings = state["raw_job_listings"]

    if not raw_job_listings:
        return {
            "job_results": "No job listings were found to match against. Try refining your search.",
            "matched_jobs": [],
            "job_match_complete": True,
        }

    structured_profile = user_data["structured_profile"]
    shortlisted = shortlist_jobs(raw_job_listings, structured_profile)

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

Return JSON with your top 3-5 recommendations only.
"""

    messages = [
        SystemMessage(content=MATCH_SYSTEM_PROMPT),
        HumanMessage(content=user_message),
    ]

    llm = ChatGroq(
        model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        temperature=0.2,
        api_key=os.getenv("GROQ_API_KEY"),
    )

    response = llm.invoke(messages)
    try:
        parsed = _parse_llm_json(response.content)
    except (json.JSONDecodeError, TypeError):
        matched_jobs = shortlisted[:5]
        summary = "Here are your top job matches based on your profile."
        recommended_companies = list({
            job.get("company", "")
            for job in matched_jobs
            if job.get("company")
        })
        return {
            "job_results": summary,
            "matched_jobs": matched_jobs,
            "recommended_companies": recommended_companies,
            "job_match_complete": True,
        }

    summary = parsed.get("summary", "Here are your top job matches.")
    recommendations = parsed.get("recommendations", [])
    matched_jobs = _resolve_matched_jobs(recommendations, shortlisted)

    if not matched_jobs and shortlisted:
        matched_jobs = shortlisted[:5]

    print("Job matching complete.")
    print("\n" + "=" * 80)
    print("AI JOB COACH RECOMMENDATIONS:")
    print("=" * 80)
    print(summary)
    for job in matched_jobs:
        print(f"- {job.get('title')} @ {job.get('company')} ({job.get('match_score', '?')}/10)")
    print("=" * 80 + "\n")

    recommended_companies = list({
        job.get("company", "")
        for job in matched_jobs
        if job.get("company")
    })

    return {
        "job_results": summary,
        "matched_jobs": matched_jobs,
        "recommended_companies": recommended_companies,
        "job_match_complete": True,
    }
