from state import StateClass
from db import upsert_user

def save_to_db_node(state: StateClass):
    print(f"💾 Saving data for user: {state['user_id']}")
    
    upsert_user(
        user_id=state["user_id"],
        structured_profile=state["structured_profile"],
        full_resume_text=state["full_resume_text"],
        user_answers=state["user_answers"]
    )
    
    return {}