import os
import json
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from state import StateClass
from db import get_user

# Import your existing function that fetches the FULL job data
from tools.searchtool import search_jobs as execute_search

load_dotenv() 

SEARCH_SYSTEM_PROMPT = """You are an expert job search query builder.
Your ONLY job is to call the search_jobs tool with the best possible queries.

CRITICAL RULES:
1. QUERIES MUST BE SHORT (2-4 words MAX). 
   - GOOD: "AI Engineer", "Python Developer", "Backend Engineer"
   - BAD: "AI Engineer Python LangChain LangGraph LLM" (This will return 0 jobs!)
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
    # Bind the schema dictionary instead of a @tool function
    return llm.bind_tools([JOB_SEARCH_TOOL_SCHEMA])

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
    all_jobs = [] # This will hold the FULL job data for the matching node
    
    total_tool_calls = 0
    MAX_TOOL_CALLS = 3

    while True:
        response = llm_with_tools.invoke(messages)
        messages.append(response)

        # Break if we hit the limit or the AI decides to stop
        if total_tool_calls >= MAX_TOOL_CALLS or not response.tool_calls:
            break

        for tool_call in response.tool_calls:
            if total_tool_calls >= MAX_TOOL_CALLS:
                break
                
            tool_name = tool_call['name']
            tool_args = tool_call['args']
            tool_id = tool_call['id']

            if tool_name == 'search_jobs':
                # 🌟 STEP 1: Fetch the FULL jobs from the API (1500-char descriptions)
                full_jobs = execute_search(query=tool_args['query'], location=tool_args.get('location', ''))
                
                if full_jobs:
                    # 🌟 STEP 2: Save FULL jobs to our accumulator (for the matching node)
                    all_jobs.extend(full_jobs)
                    
                    # 🌟 STEP 3: Create a TRUNCATED version for the LLM (prevents 413 error)
                    llm_friendly_jobs = [{
                        "title": j.get("title"),
                        "company": j.get("company"),
                        "location": j.get("location"),
                        "employment_type": j.get("employment_type"),
                        "description_snippet": j.get("description", "")[:200] + "...", # Truncated!
                        "apply_url": j.get("apply_url")
                    } for j in full_jobs]
                    
                    tool_result_str = json.dumps(llm_friendly_jobs)
                else:
                    tool_result_str = "No jobs found. Try a broader query."

                total_tool_calls += 1
                
                # 🌟 STEP 4: Send only the TRUNCATED string to the LLM
                messages.append(ToolMessage(
                    content=tool_result_str,
                    tool_call_id=tool_id
                ))

    # Deduplicate by apply_url (using the FULL job data)
    seen = set()
    unique_jobs = []
    for job in all_jobs:
        if job.get("apply_url") and job["apply_url"] not in seen:
            seen.add(job["apply_url"])
            unique_jobs.append(job)

    print(f"\n✅ Total unique jobs found: {len(unique_jobs)}")

    # 🎉 TERMINAL DISPLAY FOR SUPERVISOR (Using full data)
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
        "raw_job_listings": unique_jobs, # <-- This contains the FULL descriptions for the next node!
        "job_search_complete": True
    }