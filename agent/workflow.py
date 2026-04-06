from langgraph.graph import StateGraph, START, END
from typing import TypedDict
from agent.tools import graph_search, rag_search

class State(TypedDict):
    query: str
    context: str
    answer: str
    
def build_agent(graphiti, vector_store):
    
    async def graph_node(state):
        context = await graph_search(graphiti, state["query"])
        return {"context": context}
    
    def rag_node(state):
        context = rag_search(vector_store, state["query"])
        return {"context": context}
    
    def decide(state):
        if "latest" in state["query"].lower() or "trend" in state["query"].lower() or "recent" in state["query"].lower():
            return "graph"
        return "rag"
    
    def generate(state):
        return {"answer": f"\n{state['context']}"}
    
    graph = StateGraph()
    
    graph.add_node("graph", graph_node)
    graph.add_node("rag", rag_node)
    graph.add_node("generate", generate)
    
    graph.add_edge(START, "graph")
    graph.add_conditional_edges("graph", decide, {
        "graph": "graph",
        "rag": "rag"
    })
    
    graph.add_edge("graph", "generate")
    graph.add_edge("rag", "generate")
    graph.add_edge("generate", END)
    
    workflow = graph.compile()
    return workflow