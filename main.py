import os, asyncio
from rich.console import Console
from rich.markdown import Markdown
from rich.live import Live
from graphiti_core import Graphiti
from graphiti_core.driver.neo4j_driver import Neo4jDriver
from ingestion.fetch_cve_rss_data import fetch_critical_cve_data, fetch_security_rss_feeds
from ingestion.graph_ingestion import ingest_cve_data, ingest_rss_feed
from ingestion.rag_ingestion import build_rag_pipeline
from graphiti_rag_agent import AgentDependencies, agent

async def main():
    console = Console()
    
    # Initialize with explicit Neo4jDriver to handle Aura's routing issues
    driver = Neo4jDriver(
        uri=os.getenv("NEO4J_URI"),
        user=os.getenv("NEO4J_USER"),
        password=os.getenv("NEO4J_PASSWORD"),
        database=os.getenv("NEO4J_DATABASE", "neo4j")
    )
    graphiti = Graphiti(graph_driver=driver)
    
    try:
        await graphiti.build_indices_and_constraints()
    except Exception as e:
        pass # Ignore duplicate index/constraint errors if they already exist

    # Check if graph already has data — skip ingestion if so
    from datetime import datetime, timezone
    existing_episodes = await graphiti.retrieve_episodes(
        reference_time=datetime.now(timezone.utc), last_n=1
    )
    
    if existing_episodes:
        console.print(f"[green]Graph database already populated — skipping ingestion.[/green]")
    else:
        console.print("[cyan]Empty graph detected. Fetching and ingesting data...[/cyan]")
        
        cve_df = fetch_critical_cve_data(limit=50)
        news_df = fetch_security_rss_feeds()
    
        try:
            await ingest_cve_data(graphiti, cve_df)
            await ingest_rss_feed(graphiti, news_df)
            console.print("[green]Graph Data ingestion complete[/green]")
        except Exception as e:  
            console.print(f"[red]Ingestion error: {str(e)}[/red]")

    # Build RAG pipeline
    console.print("[cyan]Building RAG pipeline...[/cyan]")
    rag_chain = await build_rag_pipeline(graphiti_client=graphiti)
    console.print("[green]RAG pipeline built[/green]")
    
    dependencies = AgentDependencies(
        graphiti_client=graphiti,
        rag_chain=rag_chain
    )
    
    console.print("[bold green]Cybersecurity Threat Intelligence Agent is ready![/bold green]")
    
    messages = []
    
    # Sliding window to prevent context overflow
    MAX_HISTORY = 30
    
    while True:
        user_input = console.input("[bold blue]Ask a cybersecurity question (or 'exit' to quit): [/bold blue]")
        
        if user_input.lower() in ["exit", "quit"]:
            console.print("[bold red]Exiting...[/bold red]")
            break
        
        try:
            with Live("", console=console, refresh_per_second=5) as live:
                response = ""
                
                async with agent.run_stream(user_input, message_history=messages, deps=dependencies) as result:
                    async for delta in result.stream_text(delta=True):
                        response += delta
                        live.update(Markdown(response))
                        
                # Update message history
                messages = list(result.all_messages())
                
                # Trim to sliding window so long sessions never exceed model context
                if len(messages) > MAX_HISTORY:
                    messages = messages[-MAX_HISTORY:]
        except Exception as e:
            console.print(f"[red]Agent error: {str(e)}[/red]")
            
    # Clean up
    await graphiti.close()
    
if __name__ == "__main__":
    asyncio.run(main())
    