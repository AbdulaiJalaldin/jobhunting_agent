def shortlist_jobs(raw_job_listings: list, structured_profile: dict) -> list:
    """
    Simple keyword pre-filter before sending to LLM.
    Reduces jobs → top 8 relevant ones so LLM gets better context per job.
    """
    # 🛡️ FIX: Use 'or []' to safely handle cases where the AI returned None instead of a list
    user_skills = set(s.lower() for s in (structured_profile.get("skills") or []))
    target_roles = [r.lower() for r in (structured_profile.get("target_roles") or [])]
    
    scored = []
    for job in raw_job_listings:
        score = 0
        description = job.get("description", "").lower()
        title = job.get("title", "").lower()
        
        # 🛡️ FIX: Same safety check for job skills
        required_skills = [s.lower() for s in (job.get("required_skills") or [])]
        
        # Title match
        for role in target_roles:
            if any(word in title for word in role.split()):
                score += 3
        
        # Skill overlap in description and required_skills
        for skill in user_skills:
            if skill in description or skill in required_skills:
                score += 1
                
        scored.append((score, job))
    
    # Sort by score, take top 8
    scored.sort(key=lambda x: x[0], reverse=True)
    return [job for _, job in scored[:8]]