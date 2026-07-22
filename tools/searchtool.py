import requests
import os

def search_jobs(query: str, location: str = "", employment_type: str = "", date_posted: str = "") -> list[dict]:
    """Call OpenWeb Ninja JSearch API and return cleaned job listings."""
    
    url = "https://api.openwebninja.com/jsearch/search-v2"
    
    params = {
        "query": f"{query} in {location}" if location else query,
    }
    
    # 🆕 1. Inject Employment Type Filter (e.g., "FULLTIME")
    if employment_type:
        params["employment_types"] = employment_type
        
    # 🆕 2. Inject Date Posted Filter (e.g., "week", "month")
    if date_posted and date_posted != "all":
        params["date_posted"] = date_posted
        
    # 🆕 3. Smart Remote Detection
    # If the user said "remote" in their location preference, force the API to only show remote jobs
    if "remote" in location.lower():
        params["work_from_home"] = "true"
    
    headers = {
        "x-api-key": os.getenv("OPENWEBNINJA_API_KEY") 
    }
    
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    
    response_data = response.json()
    data_dict = response_data.get("data", {})
    raw_jobs = data_dict.get("jobs", []) if isinstance(data_dict, dict) else []
    
    if not isinstance(raw_jobs, list):
        return []
    
    # Clean and normalize
    cleaned = []
    for job in raw_jobs:
        if not isinstance(job, dict):
            continue
            
        cleaned.append({
            "title": job.get("job_title", ""),
            "company": job.get("employer_name", ""),
            "location": f"{job.get('job_city', '')}, {job.get('job_country', '')}".strip(", "),
            "is_remote": job.get("job_is_remote", False),
            "description": job.get("job_description", ""), # Kept full length for the matching node
            "apply_url": job.get("job_apply_link", ""),
            "posted_at": job.get("job_posted_at_datetime_utc", ""),
            "employment_type": job.get("job_employment_type", ""),
            "required_skills": job.get("required_technologies") or job.get("job_required_skills") or []
        })
    
    print(f"✅ OpenWeb Ninja returned {len(cleaned)} jobs for query: '{query}'")
    return cleaned