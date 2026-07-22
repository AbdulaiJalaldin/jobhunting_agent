import os
from exa_py import Exa
from langchain_core.tools import tool

@tool
def search_decision_makers(query: str) -> list[dict]:
    """
    Search for decision makers and recruiters at a company using Exa People Search.
    Query format: Natural language like "CTO at Sentara" or "Technical Recruiter at CloudWave".
    """
    exa = Exa(api_key=os.getenv("EXA_API_KEY"))
    
    try:
        # 🚀 STRICTLY FOLLOWING OFFICIAL EXA DOCS:
        # - category MUST be "people"
        # - include_domains is REMOVED (forbidden for people search)
        # - type="auto" is recommended by Exa
        # - contents={"highlights": True} is recommended for agents
        results = exa.search(
            query,
            category="people",
            type="auto", 
            num_results=2,
            contents={"highlights": True}
        )
        
        contacts = []
        for result in results.results:
            # 🚀 EXTRACTING STRUCTURED DATA AS PER DOCS:
            # The docs state names are in results[].entities[].properties.name
            name = result.title.split(" - ")[0] if result.title else "Unknown"
            
            if hasattr(result, 'entities') and result.entities:
                try:
                    entity = result.entities[0]
                    props = entity.properties
                    
                    # Handle both dict and object returns from the SDK
                    if isinstance(props, dict):
                        name = props.get('name', name)
                    else:
                        name = getattr(props, 'name', name)
                except Exception:
                    pass # Fallback to the cleaned-up title if entities fail
            
            contacts.append({
                "name": name,
                "linkedin_url": result.url
            })
            
        return contacts
    
    except Exception as e:
        print(f"⚠️ Exa search failed for query '{query}': {e}")
        return []