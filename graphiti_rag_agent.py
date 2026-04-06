from dataclasses import dataclass
from typing import List, Optional
from pydantic import BaseModel
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from graphiti_core import Graphiti
import os
from datetime import datetime, timezone

@dataclass
class AgentDependencies:
    graphiti_client: Graphiti
    rag_chain: object # LangCHain's RetrievalQA chain
    
class GraphitiSearchResult(BaseModel):
    uuid: str
    fact: str
    confidence_score: Optional[float] = None
    edge_type: Optional[str] = None
    valid_at: Optional[str] = None
    invalid_at: Optional[str] = None
    source_node_uuid: Optional[str] = None
    group_id: Optional[str] = None
    source: Optional[str] = None
    
def get_model() -> OpenAIChatModel:
    api_key = os.getenv("OPENAI_API_KEY", "No API Key Found")
    return OpenAIChatModel(model_name="gpt-4o-mini", provider=OpenAIProvider(api_key=api_key))

agent = Agent(
    model=get_model(),
    deps_type=AgentDependencies
)

@agent.system_prompt
def build_system_prompt() -> str:
    """Inject current date so the model never defaults to its training cutoff year."""
    now = datetime.now(timezone.utc)
    current_date = now.strftime("%A, %B %d, %Y")   # e.g. "Sunday, April 06, 2026"
    current_year = now.year

    return f"""You are an advanced cybersecurity threat intelligence assistant.

TODAY'S DATE: {current_date}
CURRENT YEAR: {current_year}

This is critical — always use {current_year} as the reference year when the user asks about:
- "this year", "current year", "2026", "recent", "latest", "now"
- Any temporal reference to the present or recent past

You have access to TWO retrieval tools:
1. search_graphiti — queries a knowledge graph for precise, structured,
   temporal facts about CVEs, threat actors, attack campaigns, and vendors.
2. query_rag — queries a vector store for broader contextual summaries.

Guidelines:
- For factual questions, call at least one tool to ground your answer.
- Prioritize data returned by the tools, but you may supplement with your
  own cybersecurity expertise to provide richer, more complete answers.
- Never fabricate specific CVE IDs, CVSS scores, or exact dates.
- When tools return limited data, clearly state what is from retrieved
  sources and what is your expert analysis.
- For conversational or general questions (greetings, opinions, advice),
  respond directly without needing to call tools.
- Keep answers concise, personalized, professional, and well-structured.
"""

from graphiti_core.search.search_config_recipes import EDGE_HYBRID_SEARCH_RRF

# RRF (Reciprocal Rank Fusion) uses BM25 + cosine similarity with a fast
# mathematical reranker instead of a neural cross-encoder, cutting latency
# from seconds to milliseconds per search.
_search_config = EDGE_HYBRID_SEARCH_RRF.model_copy(deep=True)
_search_config.limit = 5

@agent.tool
async def search_graphiti(ctx: RunContext[AgentDependencies], query: str) -> List[GraphitiSearchResult]:
    graphiti = ctx.deps.graphiti_client
    results = await graphiti.search_(
        query=query,
        config=_search_config
    )
    
    now = datetime.now(timezone.utc)
    
    formatted_results = []
    
    for res in results.edges:
        # Temporal validity check — valid_at/invalid_at are datetime objects from Graphiti
        valid = True
        valid_at_val = getattr(res, 'valid_at', None)
        invalid_at_val = getattr(res, 'invalid_at', None)
        
        if valid_at_val is not None:
            ts = valid_at_val if isinstance(valid_at_val, datetime) else datetime.fromisoformat(str(valid_at_val))
            valid = ts <= now
        if invalid_at_val is not None:
            ts = invalid_at_val if isinstance(invalid_at_val, datetime) else datetime.fromisoformat(str(invalid_at_val))
            valid = valid and ts >= now
        if not valid:
            continue
            
        # Extract Graphiti's internal contextual score (default 1.0 if not present)
        internal_score = getattr(res, 'score', 1.0)
            
        formatted_results.append(GraphitiSearchResult(
            uuid=res.uuid,
            fact=res.fact,
            confidence_score=internal_score,
            edge_type=getattr(res, 'name', None),
            valid_at=str(valid_at_val) if valid_at_val is not None else None,
            invalid_at=str(invalid_at_val) if invalid_at_val is not None else None,
            source_node_uuid=getattr(res, 'source_node_uuid', None),
            group_id=getattr(res, 'group_id', None),
            source=None
        ))
        
    formatted_results.sort(key=lambda x: x.confidence_score if x.confidence_score is not None else 0, reverse=True)
    return formatted_results[:10]

@agent.tool
async def query_rag(ctx: RunContext[AgentDependencies], query: str) -> str:
    response = ctx.deps.rag_chain.invoke({"query": query})
    text = response.get("result", str(response))
    # Truncate the response to prevent oversized tool results from consuming the context window
    if len(text) > 2000:
        text = text[:2000] + "\n... [truncated for brevity]"
    return text