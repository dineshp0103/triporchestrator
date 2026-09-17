import os
import sys
import asyncio
import concurrent.futures
import streamlit as st

def friendly_error(exc: Exception) -> str:
    """Return a clean one-line reason from an exception (no stack trace)."""
    # Walk the exception chain to get the root cause
    cause = exc
    while cause.__cause__ is not None:
        cause = cause.__cause__
    msg = str(cause).strip()
    # Trim very long messages to one sentence
    first_line = msg.split('\n')[0].strip()
    return first_line if first_line else repr(exc)

# ── Path setup ────────────────────────────────────────────────────────────────
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
AGENTS_DIR   = os.path.join(PROJECT_ROOT, "agents")

for p in (PROJECT_ROOT, AGENTS_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# ── Async helper ──────────────────────────────────────────────────────────────
def run_async_coro(coro):
    """Run an async coroutine in an isolated thread (avoids Streamlit loop collision)."""
    def _worker():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        return ex.submit(_worker).result()

# ── Cached Agent Imports ──────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False, ttl=60)  # Cache for 60 seconds to allow updates
def load_agent_suite():
    """Cache heavy agent imports and LLM workflow graphs in memory to eliminate rerun latency."""
    try:
        from agents.orchestra import build_orchestrator_graph, HumanMessage, booking_module, transport_module
        from agents.weather_agent import weather_agent
        from agents.guide import tour_guide_agent
        from agents.llm_convo import needs_orchestration, stream_normal_convo
        return {
            "available": True,
            "error": None,
            "build_orchestrator_graph": build_orchestrator_graph,
            "HumanMessage": HumanMessage,
            "booking_module": booking_module,
            "transport_module": transport_module,
            "weather_agent": weather_agent,
            "tour_guide_agent": tour_guide_agent,
            "needs_orchestration": needs_orchestration,
            "stream_normal_convo": stream_normal_convo,
        }
    except Exception as exc:
        return {"available": False, "error": str(exc)}

suite = load_agent_suite()
ORCHESTRATOR_AVAILABLE = suite["available"]
IMPORT_ERROR = suite["error"]

if ORCHESTRATOR_AVAILABLE:
    build_orchestrator_graph = suite["build_orchestrator_graph"]
    HumanMessage = suite["HumanMessage"]
    booking_module = suite["booking_module"]
    transport_module = suite["transport_module"]
    weather_agent = suite["weather_agent"]
    tour_guide_agent = suite["tour_guide_agent"]
    needs_orchestration = suite["needs_orchestration"]
    stream_normal_convo = suite["stream_normal_convo"]

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="TripOrchestrator – AI Travel Agent",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS & Animations ──────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.main .block-container {
    padding-top: 1rem;
    padding-bottom: 1rem;
    max-width: 1100px;
}

/* Animations */
@keyframes glowPulse {
    0% { box-shadow: 0 0 4px rgba(56, 189, 248, 0.2); border-color: rgba(56, 189, 248, 0.3); }
    50% { box-shadow: 0 0 16px rgba(56, 189, 248, 0.6); border-color: rgba(56, 189, 248, 0.8); }
    100% { box-shadow: 0 0 4px rgba(56, 189, 248, 0.2); border-color: rgba(56, 189, 248, 0.3); }
}

@keyframes rotateRing {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}

@keyframes fadeInUp {
    from { opacity: 0; transform: translateY(6px); }
    to { opacity: 1; transform: translateY(0); }
}

.agent-loading-badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: rgba(30, 41, 59, 0.8);
    border: 1px solid rgba(56, 189, 248, 0.4);
    color: #38BDF8;
    padding: 0.45rem 0.85rem;
    border-radius: 8px;
    font-size: 0.88rem;
    font-weight: 500;
    margin-bottom: 0.4rem;
    animation: glowPulse 2s infinite ease-in-out, fadeInUp 0.3s ease-out;
}

.agent-done-badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: rgba(15, 23, 42, 0.7);
    border: 1px solid rgba(74, 222, 128, 0.3);
    color: #4ADE80;
    padding: 0.45rem 0.85rem;
    border-radius: 8px;
    font-size: 0.88rem;
    font-weight: 500;
    margin-bottom: 0.4rem;
    animation: fadeInUp 0.3s ease-out;
}

.spinner-ring {
    width: 14px;
    height: 14px;
    border: 2px solid rgba(56, 189, 248, 0.3);
    border-top-color: #38BDF8;
    border-radius: 50%;
    animation: rotateRing 0.7s linear infinite;
}

/* Hero header */
.hero-header {
    background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
    padding: 1.4rem 2rem;
    border-radius: 14px;
    margin-bottom: 1rem;
    border: 1px solid rgba(255,255,255,0.08);
    box-shadow: 0 8px 24px rgba(0,0,0,0.35);
}
.hero-title {
    font-size: 1.75rem;
    font-weight: 800;
    background: linear-gradient(90deg, #38BDF8, #818CF8);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 0;
}
.hero-sub { color: #94A3B8; font-size: 0.9rem; margin-top: 0.3rem; }

/* Badges */
.badge {
    display: inline-block;
    padding: 0.25rem 0.65rem;
    border-radius: 20px;
    font-size: 0.78rem;
    font-weight: 600;
    margin: 0.2rem;
}
.b-weather  { background:rgba(56,189,248,.15); color:#38BDF8; border:1px solid rgba(56,189,248,.3); }
.b-guide    { background:rgba(251,146,60,.15);  color:#FB923C; border:1px solid rgba(251,146,60,.3); }
.b-booking  { background:rgba(168,85,247,.15);  color:#A855F7; border:1px solid rgba(168,85,247,.3); }
.b-transport{ background:rgba(74,222,128,.15);  color:#4ADE80; border:1px solid rgba(74,222,128,.3); }

/* Info card */
.info-card {
    background: #1E293B;
    border-radius: 10px;
    padding: 1.1rem;
    border: 1px solid rgba(255,255,255,0.07);
    margin-top: 0.75rem;
}

/* Chat bubbles extra spacing */
[data-testid="stChatMessage"] { margin-bottom: 0.4rem; }
</style>
""", unsafe_allow_html=True)

# ── Session state init ────────────────────────────────────────────────────────
# MUST be at the top level before any widget that might trigger a rerun.
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": (
                "👋 Hello! I am your **Master Travel Orchestrator**.\n\n"
                "I coordinate a team of AI agents to plan your entire trip:\n"
                "- 🌦️ **Weather** – Live forecasts for any destination\n"
                "- 🗺️ **Tour Guide (Trippy)** – Itineraries & local attractions\n"
                "- 🏨 **Booking** – Hotel search on Booking.com\n"
                "- 🚆 **Transport** – IRCTC train availability\n\n"
                "Tell me about your trip and I'll get started! "
                "*(e.g. 'Plan a 2-day trip to Tirupati from Vizag on Nov 10–12 for 2 guests')*"
            ),
        }
    ]

if "trip_info" not in st.session_state:
    st.session_state.trip_info = {
        "destination": None,
        "origin":      None,
        "checkin_date":  None,
        "checkout_date": None,
        "guests": None,
    }

if "active_page" not in st.session_state:
    st.session_state.active_page = "chat"

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://img.icons8.com/isometric/96/compass.png", width=60)
    st.title("TripOrchestrator")
    st.caption("AI Autonomous Travel Planner")
    st.markdown("---")

    # Navigation
    st.subheader("🧭 Navigate")
    pages = {
        "chat":      "💬 Chat (Orchestrator)",
        "weather":   "🌦️ Weather Agent",
        "guide":     "🗺️ Tour Guide (Trippy)",
        "booking":   "🏨 Booking Agent",
        "transport": "🚆 Transport Agent",
    }
    for key, label in pages.items():
        if st.button(label, key=f"nav_{key}", use_container_width=True):
            st.session_state.active_page = key
            st.rerun()

    st.markdown("---")
    st.subheader("🤖 Agent Suite")
    st.markdown('<span class="badge b-weather">🌦️ Weather</span>', unsafe_allow_html=True)
    st.markdown('<span class="badge b-guide">🗺️ Tour Guide</span>', unsafe_allow_html=True)
    st.markdown('<span class="badge b-booking">🏨 Booking</span>', unsafe_allow_html=True)
    st.markdown('<span class="badge b-transport">🚆 Transport</span>', unsafe_allow_html=True)

    st.markdown("---")
    st.subheader("⚙️ Status")
    if not ORCHESTRATOR_AVAILABLE:
        st.error(f"Import error:\n{IMPORT_ERROR}")
    elif os.getenv("GROQ_API_KEY"):
        st.success("✅ Groq LLM Engine")
    elif os.getenv("OPENAI_API_KEY"):
        st.success("✅ OpenAI Engine")
    elif os.getenv("GOOGLE_API_KEY"):
        st.success("✅ Gemini Engine")
    else:
        st.warning("⚠️ No API key in .env")

    if st.button("🗑️ Reset Chat", use_container_width=True):
        st.session_state.messages = [
            {"role": "assistant", "content": "👋 Chat reset. Where would you like to travel?"}
        ]
        st.session_state.trip_info = {k: None for k in st.session_state.trip_info}
        st.rerun()
    
    if st.button("🔄 Clear Cache", use_container_width=True, help="Clear agent cache to reload updates"):
        st.cache_resource.clear()
        st.success("Cache cleared! Reloading...")
        st.rerun()

# ── Hero header ───────────────────────────────────────────────────────────────
page = st.session_state.active_page

titles = {
    "chat":      ("✈️ Master Travel Orchestrator", "Chat with your AI agent team"),
    "weather":   ("🌦️ Weather Agent", "Live weather forecasts for any destination"),
    "guide":     ("🗺️ Tour Guide – Trippy", "Personalised itineraries & local tips"),
    "booking":   ("🏨 Accommodation Agent", "Real-time hotel search on Booking.com"),
    "transport": ("🚆 Transport Agent", "IRCTC train seat availability"),
}
title, subtitle = titles.get(page, ("TripOrchestrator", ""))
st.markdown(f"""
<div class="hero-header">
  <div class="hero-title">{title}</div>
  <div class="hero-sub">{subtitle}</div>
</div>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
# PAGE: CHAT  (st.chat_input lives here at the TOP LEVEL – not inside a tab)
# ════════════════════════════════════════════════════════════════════════════
if page == "chat":

    # ── Sample prompt buttons ──────────────────────────────────────────────
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("📍 Tirupati 2-Day Trip", use_container_width=True):
            st.session_state["_inject_prompt"] = (
                "Plan a 2-day trip to Tirupati from Visakhapatnam, "
                "check-in Nov 10 check-out Nov 12 2026, 2 guests. "
                "Check weather, suggest top sights, and search hotels."
            )
            st.rerun()
    with c2:
        if st.button("🗺️ Kyoto 3-Day Sightseeing", use_container_width=True):
            st.session_state["_inject_prompt"] = (
                "Plan a 3-day sightseeing trip to Kyoto. "
                "What are the top attractions and current weather?"
            )
            st.rerun()
    with c3:
        if st.button("🚆 Vizag → Tirupati Train", use_container_width=True):
            st.session_state["_inject_prompt"] = (
                "Check sleeper class train availability from "
                "Visakhapatnam to Tirupati on 15/10/2026 for Dinesh."
            )
            st.rerun()

    st.markdown("---")

    # ── Render chat history ────────────────────────────────────────────────
    for msg in st.session_state.messages:
        avatar = "👤" if msg["role"] == "user" else "🤖"
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])

    # ── Chat input  ────────────────────────────────────────────────────────
    # st.chat_input MUST be at the top level (not inside any tab/container).
    # Because we switched to a single-page navigation model, this is safe.
    user_input = st.chat_input("Describe your trip or ask a travel question…")

    # Merge typed input or injected quick-prompt
    prompt = user_input
    if "_inject_prompt" in st.session_state:
        prompt = st.session_state.pop("_inject_prompt")

    if prompt:
        # 1. Show user bubble & save
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user", avatar="👤"):
            st.markdown(prompt)

        # 2. Heuristic trip-info extraction
        pl = prompt.lower()
        for kw, val in [("tirupati", "Tirupati"), ("kyoto", "Kyoto"),
                        ("goa", "Goa"), ("delhi", "Delhi"), ("mumbai", "Mumbai")]:
            if kw in pl:
                st.session_state.trip_info["destination"] = val
        if "visakhapatnam" in pl or "vizag" in pl:
            st.session_state.trip_info["origin"] = "Visakhapatnam"
        for g in ["1 guest", "2 guests", "3 guests", "4 guests",
                  "1 person", "2 people", "3 people", "4 people"]:
            if g in pl:
                st.session_state.trip_info["guests"] = g.split()[0]

        # 3. Handle prompt via Normal LLM Convo vs Multi-Agent Orchestrator
        if not ORCHESTRATOR_AVAILABLE:
            with st.chat_message("assistant", avatar="🤖"):
                st.error(f"Agents unavailable – import failed:\n```\n{IMPORT_ERROR}\n```")
        elif not needs_orchestration(prompt):
            # Normal conversation prompt (e.g. "Hi", "Hello, What can you do", chit-chat)
            with st.chat_message("assistant", avatar="🤖"):
                # Snapshot history excluding the latest user message just added
                history_snapshot = st.session_state.messages[:-1]
                reply_stream = stream_normal_convo(history_snapshot, prompt)
                full_reply = st.write_stream(reply_stream)
                st.session_state.messages.append({"role": "assistant", "content": full_reply})
        else:
            # Travel planning query -> Run Multi-Agent Orchestrator
            msgs_snapshot = [
                m["content"]
                for m in st.session_state.messages
                if m["role"] == "user"
            ]

            AGENT_CONNECT_LOGS = {
                "Weather": "Connected with weather agent for weather report",
                "TourGuide": "Connected with tour guide agent for itinerary recommendations",
                "Booking": "Connected with booking agent for hotel search",
                "Transport": "Connected with transport agent to see the transport availability",
            }

            AGENT_COMPLETE_LOGS = {
                "Weather": "Weather report Generated",
                "TourGuide": "Tour guide itinerary Generated",
                "Booking": "Hotel booking options Generated",
                "Transport": "Transport Availability Report Generated",
            }

            with st.chat_message("assistant", avatar="🤖"):
                status_container = st.status("🤖 Orchestrating agents…", expanded=True)
                
                # Agent icons mapping
                agent_icons = {
                    "Weather": "🌦️",
                    "TourGuide": "🗺️",
                    "Booking": "🏨",
                    "Transport": "🚆",
                    "FINISH": "✅"
                }
                
                import time
                start_time = time.time()
                displayed_steps = set()
                responses = []

                async def _run_and_collect():
                    """Collect all updates from the graph stream."""
                    graph = build_orchestrator_graph()
                    hm = [HumanMessage(content=c) for c in msgs_snapshot]
                    
                    updates_list = []
                    agent_flow = []
                    
                    print(f"\n[DEBUG] Starting graph execution")
                    
                    async for chunk in graph.astream({"messages": hm}):
                        for node, update in chunk.items():
                            print(f"[DEBUG] Node: {node}, Keys: {list(update.keys())}")
                            
                            # Collect Supervisor reasoning
                            if node == "Supervisor":
                                if "reasoning" in update:
                                    step = update.get("current_step", 0)
                                    next_agent = update.get("next")
                                    reasoning = update["reasoning"]
                                    
                                    if step not in displayed_steps:
                                        elapsed = time.time() - start_time
                                        icon = agent_icons.get(next_agent, "🤖")
                                        
                                        updates_list.append({
                                            "type": "reasoning",
                                            "step": step,
                                            "agent": next_agent,
                                            "reasoning": reasoning,
                                            "elapsed": elapsed,
                                            "icon": icon
                                        })
                                        displayed_steps.add(step)
                                        print(f"[DEBUG] ✓ Reasoning collected: {reasoning[:50]}...")
                                    
                                if "agent_flow" in update:
                                    agent_flow = update["agent_flow"]
                            
                            # Collect agent execution status
                            elif node in ["Weather", "TourGuide", "Booking", "Transport"]:
                                # Agent started
                                updates_list.append({
                                    "type": "agent_start",
                                    "agent": node
                                })
                                print(f"[DEBUG] ✓ {node} started")
                                
                                # Agent completed
                                if "messages" in update:
                                    updates_list.append({
                                        "type": "agent_complete",
                                        "agent": node
                                    })
                                    
                                    responses.append({
                                        "agent": node,
                                        "content": update["messages"][-1].content,
                                    })
                                    print(f"[DEBUG] ✓ {node} completed")
                    
                    return updates_list, agent_flow

                try:
                    # Collect all updates
                    updates_list, agent_flow = run_async_coro(_run_and_collect())
                    
                    # Now render all updates on the main thread (with Streamlit context)
                    for update_item in updates_list:
                        if update_item["type"] == "reasoning":
                            status_container.write(
                                f"**Step {update_item['step']}** ({update_item['elapsed']:.1f}s) → "
                                f"{update_item['icon']} **{update_item['agent']}**  \n"
                                f"_{update_item['reasoning']}_"
                            )
                        elif update_item["type"] == "agent_start":
                            badge_html = f'''
                            <div class="agent-loading-badge">
                                <div class="spinner-ring"></div>
                                <span>{update_item['agent']} agent is working...</span>
                            </div>
                            '''
                            status_container.markdown(badge_html, unsafe_allow_html=True)
                        elif update_item["type"] == "agent_complete":
                            badge_html = f'''
                            <div class="agent-done-badge">
                                <span>✓</span>
                                <span>{update_item['agent']} agent completed</span>
                            </div>
                            '''
                            status_container.markdown(badge_html, unsafe_allow_html=True)
                    
                    # Display timeline summary
                    if agent_flow:
                        total_time = time.time() - start_time
                        status_container.write(f"\n**Total orchestration time:** {total_time:.2f}s")
                        
                        status_container.write("**Agent execution times:**")
                        for entry in agent_flow:
                            duration = entry.get("end_time", time.time()) - entry["start_time"]
                            status_container.write(f"  - {entry['agent']}: {duration:.2f}s")
                    
                    status_container.update(label="🎉 Orchestration Complete!", state="complete", expanded=False)

                    if responses:
                        parts = [
                            f"**[{r['agent']}]**\n\n{r['content']}"
                            for r in responses
                        ]
                        reply = "\n\n---\n\n".join(parts)
                    else:
                        reply = (
                            "✅ I've processed your request. "
                            "Anything else about your trip?"
                        )

                    st.markdown(reply)
                    st.session_state.messages.append(
                        {"role": "assistant", "content": reply}
                    )

                except Exception as exc:
                    # Show error in the status container
                    status_container.update(label="❌ Error", state="error")
                    st.error(f"⚠️ {friendly_error(exc)}")
                    import traceback
                    print(f"[ERROR] Orchestration failed:")
                    traceback.print_exc()


# ════════════════════════════════════════════════════════════════════════════
# PAGE: WEATHER
# ════════════════════════════════════════════════════════════════════════════
elif page == "weather":
    city_col, btn_col = st.columns([3, 1])
    with city_col:
        city = st.text_input("Destination city:", value="Tirupati", key="w_city")
    with btn_col:
        st.write("")
        st.write("")
        go = st.button("Check Weather ⛅", use_container_width=True)

    if go and city:
        with st.spinner(f"Fetching weather for **{city}**…"):
            try:
                agent = weather_agent()
                res   = agent.invoke({"input": f"Check weather in {city}"})
                st.markdown('<div class="info-card">', unsafe_allow_html=True)
                st.markdown(f"### 🌡️ Weather Report – {city}")
                st.write(res["output"])
                st.markdown('</div>', unsafe_allow_html=True)
            except Exception as exc:
                st.error(f"⚠️ {friendly_error(exc)}")


# ════════════════════════════════════════════════════════════════════════════
# PAGE: TOUR GUIDE  (streaming – tokens flush to UI as they are generated)
# ════════════════════════════════════════════════════════════════════════════
elif page == "guide":
    import queue, threading

    query = st.text_area(
        "Ask Trippy:",
        value="I am visiting Kyoto for 2 days. What are the top 3 places to visit?",
        height=90,
        key="g_text",
    )
    if st.button("Ask Tour Guide 🗺️", type="primary"):
        st.markdown("### 🎒 Trippy's Recommendations")
        st.caption("_Streaming live – words appear as Trippy generates them…_")

        # ------------------------------------------------------------------
        # Bridge: async astream_events → sync queue → st.write_stream
        #
        # Why a queue?  st.write_stream() needs a *sync* generator.
        # astream_events() is *async*.  We spin a daemon thread to run the
        # async loop, put each token into a queue.Queue, and yield from it
        # synchronously on the main thread.
        # ------------------------------------------------------------------
        token_q: queue.Queue = queue.Queue()

        def _stream_worker(user_query: str):
            """Runs the async agent in a background thread; pushes tokens into queue."""
            async def _run():
                try:
                    async for event in tour_guide_agent.astream_events(
                        {"messages": [HumanMessage(content=user_query)]},
                        version="v2",
                    ):
                        kind = event.get("event", "")
                        # on_chat_model_stream fires for every LLM token
                        if kind == "on_chat_model_stream":
                            chunk = event["data"].get("chunk")
                            if chunk and hasattr(chunk, "content") and chunk.content:
                                token_q.put(chunk.content)
                except Exception as exc:
                    token_q.put(f"\n\n⚠️ {friendly_error(exc)}")
                finally:
                    token_q.put(None)  # sentinel – signals end of stream

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(_run())
            finally:
                loop.close()

        # Start background thread BEFORE calling write_stream so tokens arrive promptly
        t = threading.Thread(target=_stream_worker, args=(query,), daemon=True)
        t.start()

        def _token_generator():
            """Sync generator that drains the queue for st.write_stream."""
            while True:
                token = token_q.get()   # blocks until next token or sentinel
                if token is None:
                    break
                yield token

        # st.write_stream flushes each yielded string to the browser immediately
        try:
            st.write_stream(_token_generator())
        except Exception as exc:
            st.error(f"⚠️ {friendly_error(exc)}")
        finally:
            t.join(timeout=5)  # clean up thread


# ════════════════════════════════════════════════════════════════════════════
# PAGE: BOOKING
# ════════════════════════════════════════════════════════════════════════════
elif page == "booking":
    c1, c2, c3 = st.columns(3)
    with c1:
        hotel_loc   = st.text_input("Destination:", value="Tirupati", key="h_loc")
    with c2:
        checkin_d   = st.date_input("Check-in:", key="h_in")
    with c3:
        checkout_d  = st.date_input("Check-out:", key="h_out")

    c4, c5, c6, c7 = st.columns(4)
    with c4:
        num_guests  = st.number_input("Guests:", min_value=1, value=2, key="h_g")
    with c5:
        num_rooms   = st.number_input("Rooms:", min_value=1, value=1, key="h_r")
    with c6:
        guest_name  = st.text_input("Lead Name:", value="Dinesh", key="h_n")
    with c7:
        guest_email = st.text_input("Email:", value="dinesh@example.com", key="h_e")

    if st.button("Search & Generate Checkout Link 🏨", type="primary", use_container_width=True):
        with st.spinner("Launching Playwright & searching Booking.com…"):
            try:
                async def _book():
                    return await booking_module.run_orchestrated_booking(
                        location=hotel_loc,
                        checkin_date=str(checkin_d),
                        checkout_date=str(checkout_d),
                        guests=int(num_guests),
                        rooms=int(num_rooms),
                        lead_guest_name=guest_name,
                        lead_guest_email=guest_email,
                    )
                res = run_async_coro(_book())
                st.markdown('<div class="info-card">', unsafe_allow_html=True)
                st.markdown("### 🏨 Booking Result")
                st.write(res.get("output", res))
                st.markdown('</div>', unsafe_allow_html=True)
            except Exception as exc:
                st.error(f"⚠️ {friendly_error(exc)}")


# ════════════════════════════════════════════════════════════════════════════
# PAGE: TRANSPORT
# ════════════════════════════════════════════════════════════════════════════
elif page == "transport":
    c1, c2, c3 = st.columns(3)
    with c1:
        t_orig = st.text_input("Origin:", value="Visakhapatnam", key="t_orig")
    with c2:
        t_dest = st.text_input("Destination:", value="Tirupati", key="t_dest")
    with c3:
        t_date = st.text_input("Date (DD/MM/YYYY):", value="15/10/2026", key="t_date")

    c4, c5 = st.columns(2)
    with c4:
        t_class = st.selectbox("Class:", ["SL", "3A", "2A", "1A"], key="t_class")
    with c5:
        t_pass  = st.text_input("Passenger:", value="Dinesh Polamarasetty", key="t_pass")

    if st.button("Search Train Availability 🚆", type="primary", use_container_width=True):
        with st.spinner("Launching IRCTC Selenium browser…"):
            try:
                res = transport_module.run_orchestrated_booking(
                    origin=t_orig,
                    destination=t_dest,
                    journey_date=t_date,
                    journey_time="Flex",
                    passenger_name=t_pass,
                    travel_class=t_class,
                )
                st.markdown('<div class="info-card">', unsafe_allow_html=True)
                st.markdown("### 🚆 Transport Result")
                st.write(res.get("output", res))
                st.markdown('</div>', unsafe_allow_html=True)
            except Exception as exc:
                st.error(f"⚠️ {friendly_error(exc)}")


# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    "<div style='text-align:center;color:#475569;font-size:0.82rem;'>"
    "TripOrchestrator · LangGraph · LangChain · Playwright · Selenium · Streamlit"
    "</div>",
    unsafe_allow_html=True,
)
