from langgraph.types import interrupt
from state import StateClass


def ask_networking_prompt(state: StateClass):
    """Asks the user if they want to find decision-makers and extracts company names."""
    print("\n" + "=" * 80)
    print("🤔 NEXT STEPS")
    print("=" * 80)

    companies = state.get("recommended_companies", [])

    if not companies:
        print("⚠️ No companies found in the job listings to network with.")
        return {"trigger_networking": False, "recommended_companies": []}

    response = interrupt({
        "type": "networking_prompt",
        "message": (
            "Would you like me to find decision-makers and recruiters at these "
            "companies to help you network?"
        ),
        "companies": companies,
    })

    if isinstance(response, dict):
        trigger = response.get("accept", False)
    else:
        trigger = str(response).strip().lower() in {"yes", "y", "yeah", "sure"}

    if trigger:
        print(f"🚀 Great! I will search for contacts at: {', '.join(companies)}")
    else:
        print("👍 No problem! Wrapping up the session.")

    return {
        "trigger_networking": trigger,
        "recommended_companies": companies,
    }
