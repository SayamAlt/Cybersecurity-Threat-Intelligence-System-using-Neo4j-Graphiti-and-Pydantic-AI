from langchain_core.documents import Document
from langchain_classic.chains.retrieval_qa.base import RetrievalQA
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.caches import InMemoryCache
from dotenv import load_dotenv
import os
import streamlit as st

load_dotenv()

if "OPENAI_API_KEY" in st.secrets["secrets"]:
    OPENAI_API_KEY = st.secrets["secrets"].get("OPENAI_API_KEY", "No OpenAI API key found.")
else:
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "No API Key Found")

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.5, api_key=OPENAI_API_KEY, cache=InMemoryCache())
embeddings = OpenAIEmbeddings(model="text-embedding-3-small", api_key=OPENAI_API_KEY)

from datetime import datetime, timezone

async def build_rag_pipeline(graphiti_client) -> RetrievalQA:
    """ Creates a Retrieval-based QA chain that builds on top of the Graphiti knowledge graph. """
    episodes = await graphiti_client.retrieve_episodes(reference_time=datetime.now(timezone.utc), last_n=150)
    
    if not episodes:
        documents = [Document(page_content="No entries found in the database. Wait for data to be populated.")]
    else:
        documents = [Document(page_content=eps.content) for eps in episodes]
        
    vector_store = FAISS.from_documents(documents, embedding=embeddings)
    retriever = vector_store.as_retriever(search_kwargs={"k": 5})
    return RetrievalQA.from_chain_type(llm=llm, chain_type="stuff", retriever=retriever)