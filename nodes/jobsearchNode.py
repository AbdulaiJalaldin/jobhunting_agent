import os
import json
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from state import StateClass
from db import get_user

from tools.searchtool import search_jobs as execute_search

load_dotenv() 

SEARCH_SYSTEM_PROMPT = """You are an expert job search query builder.
Your ONLY job is to call the search_jobs_tool with the best possible queries.

CRITICAL RULES:
1. QUERIES MUST BE SHORT (2-4 words MAX). 
   - GOOD EXAMPLES: "AI Engineer", "Python Developer", "Backend Engineer"
   - BAD EXAMPLES: "AI Engineer Python LangChain LangGraph LLM" (This will return 0 jobs!)
2. Make EXACTLY 2 or 3 separate tool calls with different short job titles.
3. Factor in their location preference from USER_PREFERENCES.
4. ONCE YOU HAVE MADE 3 TOOL CALLS, YOU MUST STOP. Do not make any more tool calls.
"""
# 🌟 CLEANER APPROACH: Define the tool schema as a dictionary.
# This tells the LLM the tool exists, but we handle the execution manually in the loop.
JOB_SEARCH_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "search_jobs",
        "description": "Search for live job listings based on a short query and optional location.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Job title or keywords (MAX 2-3 words). Example: 'AI Engineer'"
                },
                "location": {
                    "type": "string",
                    "description": "Location filter. Example: 'USA, Remote'"
                }
            },
            "required": ["query"]
        }
    }
}

def get_llm():
    llm = ChatGroq(
        model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        temperature=0,
        api_key=os.getenv("GROQ_API_KEY")
    )
    return llm.bind_tools([JOB_SEARCH_TOOL_SCHEMA])

# 🆕 HELPER FUNCTION: Translates user text into API enums
def get_api_filters(user_answers: dict):
    """Maps user's raw text input to OpenWeb Ninja API enum values."""
    # Map Job Type
    raw_job_type = user_answers.get("job_type", "").lower()
    employment_type = ""
    if "full" in raw_job_type: employment_type = "FULLTIME"
    elif "part" in raw_job_type: employment_type = "PARTTIME"
    elif "intern" in raw_job_type: employment_type = "INTERN"
    elif "contract" in raw_job_type: employment_type = "CONTRACTOR"
    
    # Map Date Posted
    raw_duration = user_answers.get("job_posting_duration", "").lower()
    date_posted = "all"
    if "24" in raw_duration or "today" in raw_duration or "1 day" in raw_duration: date_posted = "today"
    elif "7" in raw_duration or "week" in raw_duration: date_posted = "week"
    elif "30" in raw_duration or "month" in raw_duration: date_posted = "month"
    elif "3" in raw_duration: date_posted = "3days"
    
    return employment_type, date_posted

def job_search_node(state: StateClass):
    print(f"🔍 Searching jobs for user: {state['user_id']}")

    user_data = get_user(state["user_id"])
    if not user_data:
        raise RuntimeError(f"User {state['user_id']} not found in DB.")

    structured_profile = user_data["structured_profile"]
    user_answers = user_data["user_answers"]

    user_message = f"""
USER_PROFILE:
{json.dumps(structured_profile, indent=2)}

USER_PREFERENCES:
{json.dumps(user_answers, indent=2)}

Search for relevant jobs for this user using the tool. Make 2-3 varied, SHORT queries.
"""

    messages = [
        SystemMessage(content=SEARCH_SYSTEM_PROMPT),
        HumanMessage(content=user_message)
    ]

    llm_with_tools = get_llm()
    all_jobs = []
    
    total_tool_calls = 0
    MAX_TOOL_CALLS = 3

    while True:
        response = llm_with_tools.invoke(messages)
        messages.append(response)

        if total_tool_calls >= MAX_TOOL_CALLS or not response.tool_calls:
            break

        for tool_call in response.tool_calls:
            if total_tool_calls >= MAX_TOOL_CALLS:
                break
                
            tool_name = tool_call['name']
            tool_args = tool_call['args']
            tool_id = tool_call['id']

            if tool_name == 'search_jobs':
                # 🚀 STATE INJECTION: Get the user's strict preferences from the state
                emp_type, date_filter = get_api_filters(user_answers)
                
                # 🚀 Call the raw API function directly, injecting the filters!
                full_jobs = execute_search(
                    query=tool_args['query'], 
                    location=tool_args.get('location', ''),
                    employment_type=emp_type,
                    date_posted=date_filter
                )
                
                if full_jobs:
                    all_jobs.extend(full_jobs)
                    
                    # Create truncated version for the LLM to prevent 413 errors
                    llm_friendly_jobs = [{
                        "title": j.get("title"),
                        "company": j.get("company"),
                        "location": j.get("location"),
                        "employment_type": j.get("employment_type"),
                        "description_snippet": j.get("description", "")[:200] + "...",
                        "apply_url": j.get("apply_url")
                    } for j in full_jobs]
                    
                    tool_result_str = json.dumps(llm_friendly_jobs)
                else:
                    tool_result_str = "No jobs found. Try a broader query."

                total_tool_calls += 1
                
                messages.append(ToolMessage(
                    content=tool_result_str,
                    tool_call_id=tool_id
                ))

    # Deduplicate by apply_url
    seen = set()
    unique_jobs = []
    for job in all_jobs:
        if job.get("apply_url") and job["apply_url"] not in seen:
            seen.add(job["apply_url"])
            unique_jobs.append(job)

    print(f"\n✅ Total unique jobs found: {len(unique_jobs)}")

    # 🎉 TERMINAL DISPLAY FOR SUPERVISOR
    print("\n" + "="*80)
    print("📋 EXTRACTED JOB LISTINGS:")
    print("="*80)
    
    for i, job in enumerate(unique_jobs, 1):
        print(f"\n[{i}] {job.get('title', 'N/A')} @ {job.get('company', 'N/A')}")
        print(f"    📍 Location: {job.get('location', 'N/A')} {'(Remote)' if job.get('is_remote') else ''}")
        print(f"    💼 Type: {job.get('employment_type', 'N/A')}")
        print(f"    📝 Description: {job.get('description', '')[:250]}...")
        print(f"    🔗 Apply: {job.get('apply_url', 'N/A')}")
        
        skills = job.get('required_skills', [])
        if skills:
            print(f"    🛠 Skills: {', '.join(skills[:5])}")
            
    print("\n" + "="*80 + "\n")

    return {
        "raw_job_listings": unique_jobs,
        "job_search_complete": True
    }