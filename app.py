import streamlit as st
import os, asyncio, threading
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

def sync_secrets():
    """
    Sync Streamlit secrets to os.environ for compatibility with libraries 
    like graphiti_core and pydantic-ai that expect environment variables.
    """
    # Check for [secrets] section
    if "secrets" in st.secrets:
        for key, value in st.secrets["secrets"].items():
            if key not in os.environ:
                os.environ[key] = str(value)
    
    # Also check top-level secrets
    for key, value in st.secrets.items():
        if key != "secrets" and key not in os.environ:
            os.environ[key] = str(value)

sync_secrets()

# Core Configuration
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Aura API configuration
AURA_CLIENT_ID = os.getenv("AURA_CLIENT_ID")
AURA_CLIENT_SECRET = os.getenv("AURA_CLIENT_SECRET")
AURA_INSTANCE_ID = os.getenv("AURA_INSTANCE_ID")

if not OPENAI_API_KEY:
    st.error("⚠️ OpenAI API Key missing. Please set it in .env or Streamlit secrets.")
    st.stop()

# Graph / Agent imports
from graphiti_core import Graphiti
from graphiti_core.driver.neo4j_driver import Neo4jDriver
from core.aura_api import ensure_aura_instance_running
from ingestion.fetch_cve_rss_data import fetch_critical_cve_data, fetch_security_rss_feeds
from ingestion.graph_ingestion import ingest_cve_data, ingest_rss_feed
from ingestion.rag_ingestion import build_rag_pipeline
from graphiti_rag_agent import AgentDependencies, agent

# Visualization imports
from pyvis.network import Network
import streamlit.components.v1 as components
from neo4j import GraphDatabase

# Configure Streamlit Page
st.set_page_config(
    page_title="CyberSec Threat Intelligence",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Adaptive Light / Dark CSS — uses CSS custom properties + prefers-color-scheme
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

/* ── Light mode tokens (default) ──────────────────────────── */
:root {
    --bg-primary: #ffffff;
    --bg-secondary: #f5f7fa;
    --bg-sidebar-start: #ffffff;
    --bg-sidebar-end: #f0f2f5;
    --text-primary: #1c1c1e;
    --text-secondary: #3c3c43;
    --text-muted: #636366;
    --accent: #0a66c2;
    --accent-light: #3385ff;
    --accent-glow: rgba(0, 123, 255, 0.12);
    --accent-border: rgba(0, 123, 255, 0.2);
    --success: #28a745;
    --card-bg: rgba(245, 247, 250, 0.9);
    --card-border: rgba(200, 200, 200, 0.7);
    --divider: rgba(200, 200, 200, 0.5);
    --code-bg: rgba(0, 123, 255, 0.07);
    --input-bg: rgba(245, 247, 250, 0.95);
    --shadow-btn: rgba(10, 102, 194, 0.25);
    --gradient-bg: linear-gradient(135deg, #f5f7fa 0%, #ffffff 50%, #f5f7fa 100%);
}

/* ── Dark mode tokens ─────────────────────────────────────── */
@media (prefers-color-scheme: dark) {
    :root {
        --bg-primary: #0d1117;
        --bg-secondary: #161b22;
        --bg-sidebar-start: #0d1117;
        --bg-sidebar-end: #161b22;
        --text-primary: #e6edf3;
        --text-secondary: #8b949e;
        --text-muted: #6e7681;
        --accent: #58a6ff;
        --accent-light: #79c0ff;
        --accent-glow: rgba(88, 166, 255, 0.12);
        --accent-border: rgba(88, 166, 255, 0.2);
        --success: #3fb950;
        --card-bg: rgba(22, 27, 34, 0.85);
        --card-border: rgba(48, 54, 61, 0.8);
        --divider: rgba(48, 54, 61, 0.6);
        --code-bg: rgba(88, 166, 255, 0.08);
        --input-bg: rgba(22, 27, 34, 0.9);
        --shadow-btn: rgba(88, 166, 255, 0.25);
        --gradient-bg: linear-gradient(135deg, #0a0e1a 0%, #0d1117 50%, #0a0e1a 100%);
    }
}

/* Streamlit also sets data-theme on its root — cover that case too */
[data-theme="dark"] {
    --bg-primary: #0d1117;
    --bg-secondary: #161b22;
    --bg-sidebar-start: #0d1117;
    --bg-sidebar-end: #161b22;
    --text-primary: #e6edf3;
    --text-secondary: #8b949e;
    --text-muted: #6e7681;
    --accent: #58a6ff;
    --accent-light: #79c0ff;
    --accent-glow: rgba(88, 166, 255, 0.12);
    --accent-border: rgba(88, 166, 255, 0.2);
    --success: #3fb950;
    --card-bg: rgba(22, 27, 34, 0.85);
    --card-border: rgba(48, 54, 61, 0.8);
    --divider: rgba(48, 54, 61, 0.6);
    --code-bg: rgba(88, 166, 255, 0.08);
    --input-bg: rgba(22, 27, 34, 0.9);
    --shadow-btn: rgba(88, 166, 255, 0.25);
    --gradient-bg: linear-gradient(135deg, #0a0e1a 0%, #0d1117 50%, #0a0e1a 100%);
}

/* ── Apply tokens ─────────────────────────────────────────── */
.stApp {
    background: var(--gradient-bg);
    color: var(--text-primary);
    font-family: 'Inter', sans-serif;
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, var(--bg-sidebar-start) 0%, var(--bg-sidebar-end) 100%);
    border-right: 1px solid var(--accent-border);
}
[data-testid="stSidebar"] .stMarkdown p {
    color: var(--text-secondary);
    font-size: 0.82rem;
    line-height: 1.6;
}

h1 {
    background: linear-gradient(90deg, var(--accent), var(--accent-light));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-weight: 700;
    letter-spacing: -0.5px;
}
h2, h3 { color: var(--accent) !important; font-weight: 600; }

[data-testid="stMetric"] {
    background: var(--card-bg);
    border: 1px solid var(--accent-border);
    border-radius: 8px;
    padding: 0.75rem 1rem;
    margin-bottom: 0.5rem;
}
[data-testid="stMetricLabel"] { color: var(--text-secondary) !important; font-size: 0.75rem !important; }
[data-testid="stMetricValue"] { color: var(--accent) !important; font-size: 1.2rem !important; }
[data-testid="stMetricDelta"] { color: var(--success) !important; }

[data-testid="stTabs"] button {
    color: var(--text-secondary);
    font-weight: 500;
    border-radius: 6px 6px 0 0;
    transition: all 0.2s;
}
[data-testid="stTabs"] button[aria-selected="true"] {
    color: var(--accent) !important;
    border-bottom: 2px solid var(--accent) !important;
    background: var(--accent-glow) !important;
}

[data-testid="stChatMessage"] {
    background: var(--card-bg);
    border: 1px solid var(--card-border);
    border-radius: 12px;
    padding: 1rem 1.25rem;
    margin-bottom: 0.75rem;
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    color: var(--text-primary);
}

[data-testid="stChatInput"] textarea {
    background: var(--input-bg) !important;
    border: 1px solid var(--accent-border) !important;
    border-radius: 10px !important;
    color: var(--text-primary) !important;
    font-family: 'Inter', sans-serif !important;
}
[data-testid="stChatInput"] textarea:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px var(--accent-glow) !important;
}

.stButton > button {
    background: linear-gradient(135deg, var(--accent), var(--accent-light));
    color: #ffffff;
    border: none;
    border-radius: 8px;
    font-weight: 500;
    padding: 0.5rem 1rem;
    transition: all 0.2s;
    box-shadow: 0 2px 8px var(--shadow-btn);
}
.stButton > button:hover {
    background: linear-gradient(135deg, var(--accent-light), var(--accent));
    box-shadow: 0 4px 16px var(--shadow-btn);
    transform: translateY(-1px);
}

.stSpinner > div { border-top-color: var(--accent) !important; }

hr { border-color: var(--divider) !important; }

code {
    font-family: 'JetBrains Mono', monospace;
    background: var(--code-bg);
    border-radius: 4px;
    padding: 0.15em 0.35em;
}
</style>
""", unsafe_allow_html=True)


# Persistent Background Event Loop
@st.cache_resource(show_spinner=False)
def get_background_loop() -> asyncio.AbstractEventLoop:
    """
    Spin up a single asyncio event loop in a daemon background thread.
    Every async call in this app is submitted into this loop, ensuring
    Graphiti and Neo4j always run on the same loop they were created on.
    """
    loop = asyncio.new_event_loop()

    def _run(loop):
        asyncio.set_event_loop(loop)
        loop.run_forever()

    t = threading.Thread(target=_run, args=(loop,), daemon=True)
    t.start()
    return loop
    

def fix_neo4j_episodes_property(uri, user, password, database):
    """
    Ensures the 'episodes' property key is registered in Neo4j metadata.
    This eliminates the 'property key does not exist' warning from graphiti-core.
    """
    cypher = """
    MERGE (n:_SchemaTouch {target: 'relationship_episodes'})
    ON CREATE SET n.episodes = []
    WITH n
    MATCH (a)-[r:RELATES_TO]->(b)
    WHERE r.episodes IS NULL
    SET r.episodes = []
    DETACH DELETE n
    """
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session(database=database if database else None) as session:
            session.run(cypher)
        driver.close()
    except Exception:
        pass # Schema fix is non-critical, don't crash the app if it fails


def run_async(coro):
    """Submit a coroutine to the background loop and block until done."""
    loop = get_background_loop()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result()  # blocks the Streamlit thread until complete

# Backend Initialization (Graphiti + RAG on the background loop)
@st.cache_resource(show_spinner=False)
def initialize_backend() -> dict:
    """
    Initialize Graphiti and RAG pipeline ONCE on the background loop.
    All Neo4j connections and asyncio objects are created in that loop,
    so every subsequent query also runs there — no cross-loop collisions.
    """
    async def _init():
        # First, ensure the 'episodes' property exists in Neo4j metadata to avoid warnings
        fix_neo4j_episodes_property(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, NEO4J_DATABASE)

        # Initialize with explicit Neo4jDriver to handle Aura's routing issues
        driver = Neo4jDriver(
            uri=NEO4J_URI,
            user=NEO4J_USER,
            password=NEO4J_PASSWORD,
            database=NEO4J_DATABASE if NEO4J_DATABASE else None
        )
        graphiti = Graphiti(graph_driver=driver)

        try:
            await graphiti.build_indices_and_constraints()
        except Exception:
            pass  # Ignore duplicate constraint errors

        # Skip ingestion if data already exists
        existing = await graphiti.retrieve_episodes(
            reference_time=datetime.now(timezone.utc), last_n=1
        )

        if not existing:
            cve_df = fetch_critical_cve_data(limit=50)
            news_df = fetch_security_rss_feeds()
            await ingest_cve_data(graphiti, cve_df)
            await ingest_rss_feed(graphiti, news_df)

        rag_chain = await build_rag_pipeline(graphiti_client=graphiti)

        return {
            "graphiti": graphiti,
            "rag_chain": rag_chain,
            "deps": AgentDependencies(graphiti_client=graphiti, rag_chain=rag_chain),
            "populated": bool(existing),
        }

    return run_async(_init())

def run_agent_query(prompt: str, history: list, deps: AgentDependencies, placeholder) -> tuple[str, list]:
    """
    Stream agent response safely across the thread boundary.

    The pydantic-ai coroutine runs on the background event loop and puts
    text chunks into a thread-safe queue.  The Streamlit main thread drains
    the queue and calls placeholder.markdown() — the ONLY thread allowed to
    touch Streamlit UI objects.  A sentinel value (None) signals completion.
    """
    import queue as _queue

    chunk_queue: _queue.Queue = _queue.Queue()

    async def _query():
        accumulated = ""
        result_holder = {}

        try:
            async with agent.run_stream(
                prompt,
                message_history=history,
                deps=deps
            ) as result:
                async for chunk in result.stream_text(delta=True):
                    accumulated += chunk
                    chunk_queue.put(chunk) # send chunk to main thread

            new_hist = list(result.all_messages())
            if len(new_hist) > 30:
                new_hist = new_hist[-30:]
            result_holder["text"] = accumulated
            result_holder["history"] = new_hist
        except Exception as e:
            result_holder["error"] = e
        finally:
            chunk_queue.put(None)               

        return result_holder

    # Submit coroutine to background loop (non-blocking from main thread)
    future = asyncio.run_coroutine_threadsafe(_query(), get_background_loop())

    # Drain queue on the MAIN Streamlit thread
    displayed = ""

    while True:
        chunk = chunk_queue.get() # blocks until next chunk or sentinel
        if chunk is None:
            break
        displayed += chunk
        placeholder.markdown(displayed + "▌")

    placeholder.markdown(displayed)

    # Now retrieve the completed coroutine result
    result_holder = future.result()
    if "error" in result_holder:
        raise result_holder["error"]

    return result_holder["text"], result_holder["history"]


# Knowledge Graph Visualization
def render_knowledge_graph():
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")
    database = os.getenv("NEO4J_DATABASE", "neo4j")

    cypher = """
    MATCH (n:Entity)-[r]->(m:Entity)
    RETURN n, r, m
    LIMIT 200
    """

    try:
        # Use sync driver here completely independent of Graphiti's async driver
        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session(database=database if database else None) as session:
            result = session.run(cypher)

            net = Network(
                height="620px", width="100%",
                bgcolor="#f8f9fa", font_color="#1c1c1e",
                directed=True
            )
            net.barnes_hut(
                gravity=-8000, central_gravity=0.3,
                spring_length=200, spring_strength=0.04
            )

            added_nodes = set()
            edge_count = 0
            for record in result:
                n1, n2, rel = record["n"], record["m"], record["r"]
                n1_id, n2_id = n1.element_id, n2.element_id

                n1_label = n1.get("name", "Entity")
                n2_label = n2.get("name", "Entity")

                if n1_id not in added_nodes:
                    net.add_node(n1_id, label=n1_label,
                                 title=str(n1.get("summary", n1_label)),
                                 color="#0a66c2", size=18,
                                 font={"size": 11, "color": "#1c1c1e"})
                    added_nodes.add(n1_id)

                if n2_id not in added_nodes:
                    net.add_node(n2_id, label=n2_label,
                                 title=str(n2.get("summary", n2_label)),
                                 color="#28a745", size=14,
                                 font={"size": 10, "color": "#1c1c1e"})
                    added_nodes.add(n2_id)

                edge_label = rel.get("name", rel.type)
                edge_title = rel.get("fact", "")
                net.add_edge(n1_id, n2_id, title=edge_title,
                             label=edge_label, color="#636366", width=1.5)
                edge_count += 1

        driver.close()

        st.caption(f"🔵 **{len(added_nodes)} nodes** · 🔗 **{edge_count} relationships** rendered")

        os.makedirs("html_files", exist_ok=True)
        path = "html_files/graph.html"
        net.save_graph(path)

        # Inject dark-mode support into the graph HTML
        dark_mode_css = """
        <style>
        @media (prefers-color-scheme: dark) {
            body, #mynetwork { background-color: #0d1117 !important; }
            .vis-network .vis-navigation .vis-button { filter: invert(1); }
        }
        </style>
        """
        with open(path, "r", encoding="utf-8") as f:
            html = f.read()
        html = html.replace("</head>", dark_mode_css + "</head>")

        components.html(html, height=640)

    except Exception as e:
        st.error(f"⚠️ Graph render failed. Ensure Neo4j is running.\n\n`{e}`")

# Boot backend
if all([AURA_CLIENT_ID, AURA_CLIENT_SECRET, AURA_INSTANCE_ID]):
    if "aura_instance_checked" not in st.session_state:
        # Perform Aura instance management on the MAIN thread to avoid NoneType errors
        with st.status("🔗 Synchronizing with Neo4j Aura Cloud...", expanded=True) as status_box:
            status_box.write("Checking database status via Aura API...")
            
            # Using a simplified status reporter to avoid thread safety issues
            def report_status(s):
                if s == "paused":
                    status_box.write("⚡ Neo4j Aura is currently **paused**. Starting it now...")
                elif s == "resuming":
                    status_box.write("🔄 Database is **resuming**... please wait (2-4 mins).")
                elif "error" in str(s).lower():
                    status_box.write(f"⚠️ **Aura API Issue**: {s}")
                else:
                    status_box.write(f"Neo4j Aura current status: **{s}**")

            success = ensure_aura_instance_running(
                AURA_CLIENT_ID, 
                AURA_CLIENT_SECRET, 
                AURA_INSTANCE_ID,
                status_callback=report_status
            )
            
            if success:
                status_box.update(label="✅ Neo4j Aura is Online", state="complete", expanded=False)
                st.session_state.aura_instance_checked = True 
            else:
                status_box.update(label="⚠️ Aura initialization taking longer than expected", state="error")

with st.spinner("🔌 Connecting to Cyber Threat Intelligence Network..."):
    backend = initialize_backend()

if not backend.get("populated"):
    st.toast("✅ Knowledge graph populated with fresh CVE & RSS data.", icon="🟢")

# Sidebar
with st.sidebar:
    st.markdown("""
    <div style='padding:0.5rem 0 1rem 0;'>
        <div style='font-size:2rem;'>🛡️</div>
        <div style='font-size:1.1rem;font-weight:700;color:#58a6ff;'>NetSec Intelligence</div>
        <div style='font-size:0.75rem;color:#8b949e;margin-top:0.25rem;'>
            Powered by Graphiti · Neo4j · GPT-4o-mini
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 📊 System Status")
    st.metric("Graph Engine", "Neo4j", delta="Live")
    st.metric("Retrieval", "RRF Hybrid", delta="Optimized")
    st.metric("LLM", "GPT-4o-mini", delta="Streaming")

    st.markdown("---")
    st.markdown("### ⚡ Quick Actions")
    if st.button("🗑️ Clear Chat History"):
        st.session_state.messages = []
        st.session_state.ui_messages = []
        st.rerun()

    st.markdown("---")
    st.markdown("""
    <div style='font-size:0.7rem;color:#8b949e;line-height:1.8;'>
    <b>Sources</b><br>
    · NVD CVE API (50 critical CVEs)<br>
    · KrebsOnSecurity RSS Feed<br>
    · Graphiti Knowledge Graph<br>
    · FAISS Vector Store (RAG)
    </div>
    """, unsafe_allow_html=True)

# Main Tabs
tab_chat, tab_graph = st.tabs(["🛡️  Threat Intel Desk", "🌐  Knowledge Graph Explorer"])

# Knowledge Graph Tab
with tab_graph:
    col_title, col_refresh = st.columns([6, 1])
    with col_title:
        st.subheader("Global Threat Intelligence Map")
        st.markdown("Interactive Neo4j topology · *Scroll to zoom · Hover for details · Drag to explore*")
    with col_refresh:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 Refresh"):
            st.rerun()

    render_knowledge_graph()

# Chat Tab
with tab_chat:
    st.header("🛡️ Threat Intelligence Desk")

    # Initialize session state
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "ui_messages" not in st.session_state:
        st.session_state.ui_messages = [
            {"role": "assistant",
             "content": "Hello. I am synchronized with the Threat Graph. Ask me anything about CVEs, threat actors, attack campaigns, or zero-days."}
        ]
    if "_pending_prompt" not in st.session_state:
        st.session_state._pending_prompt = None

    # Render all existing conversation history
    for msg in st.session_state.ui_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # If there is a pending prompt, process it HERE
    if st.session_state._pending_prompt:
        active_prompt = st.session_state._pending_prompt

        # Render new user bubble
        with st.chat_message("user"):
            st.markdown(active_prompt)

        # Stream agent response immediately below user bubble
        with st.chat_message("assistant"):
            placeholder = st.empty()
            try:
                final_text, new_history = run_agent_query(
                    prompt=active_prompt,
                    history=st.session_state.messages,
                    deps=backend["deps"],
                    placeholder=placeholder
                )
                # Save completed exchange to persistent state
                st.session_state.messages = new_history
                st.session_state.ui_messages.append({"role": "user", "content": active_prompt})
                st.session_state.ui_messages.append({"role": "assistant", "content": final_text})
            except Exception as e:
                error_msg = f"⚠️ Agent error: `{str(e)}`"
                placeholder.error(error_msg)
                st.session_state.ui_messages.append({"role": "user", "content": active_prompt})
                st.session_state.ui_messages.append({"role": "assistant", "content": error_msg})
            finally:
                # Clear pending prompt so next rerun shows clean state
                st.session_state._pending_prompt = None

    # Input box
    new_prompt = st.chat_input("Query vulnerabilities, threat actors, zero days...")

    if new_prompt:
        # Store and rerun: next pass renders new exchange ABOVE this input box
        st.session_state._pending_prompt = new_prompt
        st.rerun()


