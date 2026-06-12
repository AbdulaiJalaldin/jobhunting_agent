import json
import time
from pathlib import Path
import asyncio
from llama_cloud import LlamaCloud
import os
from dotenv import load_dotenv
from state import StateClass


load_dotenv()

# 1. Define a FLEXIBLE schema that captures core data + unique details
data_schema = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "Full name of the candidate"},
        "contact": {
            "type": "object",
            "properties": {
                "email": {"type": "string"},
                "phone": {"type": "string"},
                "linkedin": {"type": "string"},
                "location": {"type": "string"}
            }
        },
        "target_roles": {
            "type": "array", 
            "items": {"type": "string"}, 
            "description": "Inferred target job titles based on experience"
        },
        "skills": {
            "type": "array", 
            "items": {"type": "string"}, 
            "description": "All technical, soft, and domain skills mentioned"
        },
        "years_of_experience": {
            "type": "integer", 
            "description": "Total years of professional experience"
        },
        "education": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Degrees, certifications, and institutions"
        },
        # THE CATCH-ALL: This solves your concern about unique resume details!
        "additional_context": {
            "type": "string",
            "description": "Any unique achievements, side projects, publications, languages, or notable details that don't fit neatly into the above categories."
        }
    },
    "required": ["name", "skills", "additional_context"]
}


async def extract_and_parse_resume(file_path: str) -> dict:
    """Helper function to handle Llama Cloud API calls."""
    client = LlamaCloud(api_key=os.getenv("LLAMAPARSEAPI"))
    
    # 1. Upload the file
    file_obj =  client.files.create(file=file_path, purpose="extract")
    
    # 2. Submit Extract Job with the FULL schema
    job =  client.extract.create(
        file_input=file_obj.id,
        configuration={
            "data_schema": data_schema,
            "tier": "agentic",
            "extraction_target": "per_doc",
            "parse_tier": "agentic",
            "cite_sources": True,
            "confidence_scores": True
        }
    )
    
    # 3. Poll until complete (using asyncio.sleep for async safety)
    while job.status not in ("COMPLETED", "FAILED", "CANCELLED"):
        await asyncio.sleep(2) 
        job =  client.extract.get(job.id)
        
    if job.status != "COMPLETED":
        raise RuntimeError(f"Extract failed for {file_path}: {job.error_message}")
        
    structured_profile = job.extract_result
    
    # 4. Also get the full markdown for the Scoring Node later
    parse_result =  client.parsing.parse(
        file_id=file_obj.id,
        tier="agentic",
        version="latest",
        expand=["markdown_full"]
    )
    
    return {
        "structured_profile": structured_profile,
        "full_resume_text": parse_result.markdown_full
    }

# 5. The LangGraph Node (Clean and simple)
async def parse_resume_node(state: StateClass):
    print(f"🚀 Starting resume parsing for user: {state['user_id']}")
    
    # Call the helper function
    extracted_data = await extract_and_parse_resume(state["resume_file_path"])
    
    # Return ONLY the fields you want to update in the StateClass
    return {
        "structured_profile": extracted_data["structured_profile"],
        "full_resume_text": extracted_data["full_resume_text"],
        "resume_parsed": True
    }


