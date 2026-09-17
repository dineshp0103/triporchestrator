# Orchestra Agent Thought Process Visualization

## Overview

The Orchestra agent now displays its thought process in real-time, showing how it analyzes user requests and coordinates the multi-agent workflow. This feature provides transparency into the AI orchestration process.

## Features

### 1. Step-by-Step Reasoning

When you submit a travel planning query, the Orchestra agent shows:
- **Step number** and **elapsed time** for each decision
- **Which agent** is being invoked (Weather 🌦️, TourGuide 🗺️, Booking 🏨, Transport 🚆)
- **Why** that agent was chosen (reasoning explanation)

Example:
```
Step 1 (0.2s) → 🌦️ Weather
User requested weather information for Tirupati, routing to Weather agent for real-time forecast data.
```

### 2. Agent Status Indicators

Visual badges show the current state of each agent:
- **Loading badge** (animated): Agent is actively working
- **Completed badge** (green checkmark): Agent finished successfully

### 3. Execution Timeline

After orchestration completes, see:
- **Total orchestration time**: Overall time from start to finish
- **Per-agent execution times**: How long each agent took

Example:
```
Total orchestration time: 5.42s

Agent execution times:
  - Weather: 1.23s
  - TourGuide: 2.15s
  - Booking: 2.04s
```

## How It Works

### Architecture

1. **Enhanced State Tracking**: The `OrchestratorState` now includes:
   - `reasoning`: LLM's explanation for routing decisions
   - `current_step`: Step counter for the orchestration
   - `step_timestamps`: Timing data for each step
   - `agent_flow`: List of agent invocations with status

2. **LLM Reasoning Capture**: The `supervisor_node` requests reasoning from the LLM when making routing decisions using structured output.

3. **Real-Time Streaming**: As the LangGraph executes, reasoning and status updates stream to the UI through the async `astream()` API.

4. **UI Visualization**: The Streamlit app collects all updates and renders them in the status widget.

### Code Flow

```
User Query
    ↓
Supervisor Node (analyzes request)
    ↓
LLM returns RouteResponse with reasoning
    ↓
State updated with reasoning + timestamps
    ↓
Stream chunk sent to UI
    ↓
UI renders reasoning in status widget
    ↓
Sub-agent executes
    ↓
Agent flow updated to "completed"
    ↓
Timeline displayed
```

## Usage Examples

### Example 1: Simple Weather Query

**User Input:**
```
Check the current weather in Tirupati
```

**Thought Process Display:**
```
Step 1 (0.1s) → 🌦️ Weather
User explicitly requested weather information for Tirupati location.

🌦️ Weather agent is working...
✓ Weather agent completed

Total orchestration time: 1.85s
Agent execution times:
  - Weather: 1.85s
```

### Example 2: Multi-Agent Trip Planning

**User Input:**
```
Plan a 2-day trip to Tirupati from Visakhapatnam, check-in Nov 10 
check-out Nov 12 2026, 2 guests. Check weather, suggest top sights, 
and search hotels.
```

**Thought Process Display:**
```
Step 1 (0.2s) → 🌦️ Weather
Detected weather request for Tirupati destination.

🌦️ Weather agent is working...
✓ Weather agent completed

Step 2 (2.3s) → 🗺️ TourGuide
User requested sightseeing suggestions for 2-day itinerary.

🗺️ TourGuide agent is working...
✓ TourGuide agent completed

Step 3 (4.5s) → 🏨 Booking
Accommodation search needed for Nov 10-12 with 2 guests.

🏨 Booking agent is working...
✓ Booking agent completed

Total orchestration time: 8.72s
Agent execution times:
  - Weather: 1.85s
  - TourGuide: 2.15s
  - Booking: 4.32s
```

### Example 3: Non-Travel Query

**User Input:**
```
Hello, how are you?
```

**Thought Process Display:**
```
Step 1 (0.1s) → ✅ FINISH
Non-travel query detected. Providing direct conversational response.

Total orchestration time: 0.34s
```

## Implementation Details

### Modified Files

1. **`agents/orchestra.py`**
   - Enhanced `OrchestratorState` TypedDict with new fields
   - Modified `RouteResponse` to include `reasoning` field
   - Updated `supervisor_node` to capture and return reasoning
   - Enhanced all sub-agent nodes to update agent flow status

2. **`src/triporchestrator/app.py`**
   - Modified orchestration handler to collect reasoning updates
   - Added agent status tracking logic
   - Implemented timeline visualization rendering
   - Enhanced status widget display with reasoning and badges

### Key Data Structures

**RouteResponse:**
```python
class RouteResponse(BaseModel):
    next: Literal["Weather", "TourGuide", "Booking", "Transport", "FINISH"]
    direct_reply: Optional[str] = None
    reasoning: str = ""  # NEW: Explanation of routing decision
```

**OrchestratorState:**
```python
class OrchestratorState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    next: str
    direct_reply: Optional[str]
    reasoning: Optional[str]           # NEW
    current_step: int                  # NEW
    step_timestamps: dict              # NEW
    agent_flow: list                   # NEW
```

**Agent Flow Entry:**
```python
{
    "step": 1,
    "agent": "Weather",
    "status": "completed",  # "pending", "active", "completed"
    "reasoning": "User requested weather check",
    "start_time": 1701234567.89,
    "end_time": 1701234570.12
}
```

## CSS Styling

The feature uses custom CSS animations for visual appeal:

- **`.agent-loading-badge`**: Animated pulsing glow effect for active agents
- **`.agent-done-badge`**: Green checkmark badge for completed agents
- **`.spinner-ring`**: Rotating ring animation for loading state

These styles are defined in the main CSS block in `app.py` and integrate seamlessly with the existing design system.

## Benefits

1. **Transparency**: Users see exactly how the Orchestra agent interprets their requests
2. **Debugging**: Developers can verify routing logic is working correctly
3. **User Confidence**: Clear explanations build trust in the AI system
4. **Performance Insights**: Timeline data helps identify bottlenecks
5. **Educational**: Users learn how multi-agent orchestration works

## Future Enhancements

Potential improvements for future versions:

1. **Interactive Timeline**: Click on agent steps to see detailed execution logs
2. **Reasoning Quality Metrics**: Score and display confidence in routing decisions
3. **Alternative Routing Suggestions**: Show other agents that were considered
4. **Export Timeline**: Download orchestration trace for analysis
5. **Replay Mode**: Step through the orchestration process backwards/forwards

## Troubleshooting

### Issue: Reasoning not showing

**Possible causes:**
- LLM may not be returning reasoning in structured output
- Check that the LLM supports structured output with Pydantic models

**Solution:**
- Fallback reasoning is generated automatically: "Routing to {agent} agent to handle the request"

### Issue: Timing looks incorrect

**Possible causes:**
- Async execution timing may include waiting time
- Network latency affects browser-based agents

**Solution:**
- Times reflect actual execution including all I/O operations
- This is expected behavior and represents real-world latency

### Issue: Status widget auto-collapses too quickly

**Solution:**
- The 2-second delay is configurable
- Manually expand the widget to review full details

## Related Specifications

- **Requirements**: `.kiro/specs/orchestra-thought-process-visualization/requirements.md`
- **Design**: `.kiro/specs/orchestra-thought-process-visualization/design.md`
- **Tasks**: `.kiro/specs/orchestra-thought-process-visualization/tasks.md`
