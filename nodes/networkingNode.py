import os
import json
from state import StateClass
from db import get_user
from tools.exasearch import search_decision_makers
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from dotenv import load_dotenv
import time
load_dotenv()

NETWORKING_SYSTEM_PROMPT = """You are a professional networking assistant.
Your job is to find decision makers at specific companies that are relevant to the user's field.

You will receive:
- TARGET_COMPANIES: companies where the user has matched jobs
- USER_TARGET_ROLES: the user's target job roles (used to infer their industry/field)

Your responsibilities:
1. Based on the user's target roles, infer what kind of decision makers are relevant.
   - Software engineer → Engineering Manager, CTO, Tech Recruiter, Head of Engineering
   - Social media manager → Marketing Director, Head of Content, HR Manager, CMO
   - Data scientist → Head of Data, Chief Data Officer, Analytics Manager, Tech Recruiter
   - Always include: CEO,Recruiter, HR Manager/hiring manager (relevant for ALL fields)
2. For each company, call the search tool to find 3-4 relevant decision makers.
3. When calling the tool, format the query as natural language.
   - GOOD: "CTO at Sentara" or "Technical Recruiter at CloudWave"
   - BAD: '"CTO" "Sentara" site:linkedin.com'
4. Search for each relevant role at each company separately.
5. Stop once you have covered all companies.
"""

def networking_node(state: StateClass):
    print(f"🤝 Finding decision makers for user: {state['user_id']}")

    recommended_companies = state.get("recommended_companies", [])
    if not recommended_companies:
        print("⚠️ No recommended companies found. Skipping.")
        return {"networking_results": [], "networking_complete": True}

    user_data = get_user(state["user_id"])
    structured_profile = user_data["structured_profile"]
    target_roles = structured_profile.get("target_roles", [])

    user_message = f"""
TARGET_COMPANIES:
{json.dumps(recommended_companies, indent=2)}

USER_TARGET_ROLES:
{json.dumps(target_roles, indent=2)}

Please search for relevant decision makers at each company using the tool.
For each company search for 2-3 different relevant roles.
"""

    llm = ChatGroq(
        model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        temperature=0,
        api_key=os.getenv("GROQ_API_KEY")
    ).bind_tools([search_decision_makers])

    messages = [
        SystemMessage(content=NETWORKING_SYSTEM_PROMPT),
        HumanMessage(content=user_message)
    ]

    all_contacts = []

    # Agentic loop
    while True:
        response = llm.invoke(messages)
        messages.append(response)

        if not response.tool_calls:
            break

        for tool_call in response.tool_calls:
            tool_args = tool_call["args"]
            tool_id = tool_call["id"]

            print(f"🛠 Searching: {tool_args.get('query')}")

            results = search_decision_makers.invoke(tool_args)

            time.sleep(0.2) 

            # Add company context to each contact
            for contact in results:
                # Extract company name from query (e.g. "recruiter at Google" → "Google")
                query = tool_args.get("query", "")
                company = query.split(" at ")[-1] if " at " in query else "Unknown"
                contact["company"] = company
                contact["role_searched"] = query.split(" at ")[0] if " at " in query else query
                all_contacts.append(contact)

            messages.append(ToolMessage(
                content=json.dumps(results),
                tool_call_id=tool_id
            ))

    # Deduplicate by linkedin_url
    seen = set()
    unique_contacts = []
    for contact in all_contacts:
        if contact["linkedin_url"] not in seen:
            seen.add(contact["linkedin_url"])
            unique_contacts.append(contact)

    # Display
    print("\n" + "="*80)
    print("🤝 NETWORKING OPPORTUNITIES:")
    print("="*80)

    current_company = None
    for contact in unique_contacts:
        if contact["company"] != current_company:
            current_company = contact["company"]
            print(f"\n🏢 {current_company}")
            print("-" * 40)
        print(f"  👤 {contact['name']}")
        print(f"     Role: {contact.get('role_searched', 'N/A')}")
        print(f"     LinkedIn: {contact['linkedin_url']}")

    print("\n" + "="*80 + "\n")

    return {
        "networking_results": unique_contacts,
        "networking_complete": True
    }