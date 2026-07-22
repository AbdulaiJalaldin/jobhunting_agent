from typing import TypedDict,Dict,Any



class StateClass(TypedDict):
    user_id: str
    resume_file_path: str
    resume_parsed: bool
    profile_complete: bool
    structured_profile: dict
    full_resume_text: str
    user_answers: dict
    job_search_complete: bool
    raw_job_listings: list
    matched_jobs: list
    job_results: str
    job_match_complete: bool
    trigger_networking: bool
    recommended_companies: list
    networking_results: list
    networking_complete: bool

