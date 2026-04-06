from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from pydantic import BaseModel, Field
import os

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "No API Key Found")

class CybersecurityEntity(BaseModel):
    vendors: list[str] = Field(default_factory=list)
    products: list[str] = Field(default_factory=list)
    services: list[str] = Field(default_factory=list)
    vulnerabilities: list[str] = Field(default_factory=list)
    attack_type: str = Field(default="")

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.5, api_key=OPENAI_API_KEY)

llm_with_entities = llm.with_structured_output(CybersecurityEntity)

async def extract_entities(text):
    prompt = f"""
        Extract cybersecurity entities from the following text:
        
        {text}
        
        Return a valid JSON:
        - Vendors: List of affected vendors
        - Products: List of affected products
        - Services: List of affected services
        - Vulnerabilities: List of mentioned vulnerabilities (e.g. CVE IDs)
        - Attack Type: Type of attack (e.g. Ransomware, Phishing)
    """
    
    response = await llm_with_entities.ainvoke(prompt)
    return response.model_dump()