async def graph_search(graphiti, query):
    results = await graphiti.search(query)
    return "\n".join([res.fact for res in results])

def rag_search(rag_chain, query):
    return rag_chain.invoke({"query": query})