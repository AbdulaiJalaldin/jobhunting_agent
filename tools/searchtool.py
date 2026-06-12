import requests
import os

def search_jobs(query: str, location: str = "") -> list[dict]:
    """Call OpenWeb Ninja JSearch API and return cleaned job listings."""
    
    url = "https://api.openwebninja.com/jsearch/search-v2"
    
    params = {
        "query": f"{query} in {location}" if location else query,
    }
    
    headers = {
        "x-api-key": os.getenv("OPENWEBNINJA_API_KEY") 
    }
    
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    
    response_data = response.json()
    
    # Extract the 'jobs' list from inside the 'data' dictionary
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
            # 🚨 CRITICAL FIX: Truncate description to 200 chars to prevent Groq 413 error!
            "description": job.get("job_description", ""),
            "apply_url": job.get("job_apply_link", ""),
            "posted_at": job.get("job_posted_at_datetime_utc", ""),
            "employment_type": job.get("job_employment_type", ""),
            "required_skills": job.get("required_technologies") or job.get("job_required_skills") or []
        })
    
    print(f"✅ OpenWeb Ninja returned {len(cleaned)} jobs for query: '{query}'")
    return cleaned