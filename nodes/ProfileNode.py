from langgraph.types import interrupt
from state import StateClass


def profile_node(state: StateClass):
    print(f"\n🚀 Getting profile info for user: {state['user_id']}")

    if state.get("user_answers", {}).get("location_preference"):
        print("✅ Profile already complete, skipping.")
        return {"profile_complete": True}

    answers = interrupt({
        "type": "profile_questions",
        "message": "Tell us about your job preferences so we can find the best matches.",
        "fields": [
            {
                "id": "location_preference",
                "label": "Preferred location & remote",
                "placeholder": "e.g. New York, open to remote",
            },
            {
                "id": "job_type",
                "label": "Job type",
                "placeholder": "Full-time, Part-time, Internship, Contract",
            },
            {
                "id": "job_posting_duration",
                "label": "How recent should postings be?",
                "placeholder": "24 hours, 7 days, or 30 days",
            },
        ],
    })

    if not isinstance(answers, dict):
        answers = {}

    return {
        "user_answers": {
            "location_preference": answers.get("location_preference", "").strip(),
            "job_type": answers.get("job_type", "").strip(),
            "job_posting_duration": answers.get("job_posting_duration", "").strip(),
        },
        "profile_complete": True,
    }
