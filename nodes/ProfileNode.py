from state import StateClass

# 1. Remove 'async' to prevent terminal input blocking issues
def profile_node(state: StateClass):
    print(f"\n🚀 Getting profile info for user: {state['user_id']}")
    
    # 2. Check if we already have the answer
    if state.get("user_answers", {}).get("location_preference"):
        print("✅ Profile already complete, skipping.")
        return {"profile_complete": True}
    
    # 3. Use standard Python input() for local terminal scripts
    print("\n" + "="*60)
    location_answer = input("❓ What is your preferred location and are you open to remote jobs? \n> ")
    print("="*60 + "\n")
    
    # 4. Return the updated state
    return {
        "user_answers": {
            "location_preference": location_answer.strip()
        },
        "profile_complete": True
    }