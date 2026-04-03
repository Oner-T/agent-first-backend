from typing import TypedDict
from celery import shared_task
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, END
from .models import ChatSession, Message
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

# 1. Define the "Memory" of the graph
class AgentState(TypedDict):
    session_id: str
    prompt: str
    archival_context: str
    final_synthesis: str

# 2. Update the Archival Agent
def archival_node(state: AgentState):
    print("-> [Archival Agent] Retrieving physical history...")
    
    # Broadcast to the React Frontend
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"chat_{state['session_id']}",
        {'type': 'agent_message', 'status': 'thinking', 'message': '> Archival Agent: Scanning floor plans and spatial records...'}
    )
    
    simulated_document = (
        "The ground floor corridor served as the primary triage and waiting area. "
        "It was characterized by rigid, outward-facing seating designed to maximize "
        "visibility from the central nursing station. The architecture enforced "
        "silence and passive observation."
    )
    
    return {"archival_context": simulated_document}

# 3. Update the Theorist Agent

# 3. Update the Theorist Agent
def theorist_node(state: AgentState):
    print("-> [Theorist Agent] Applying philosophical framework...")
    
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"chat_{state['session_id']}",
        {'type': 'agent_message', 'status': 'thinking', 'message': '> Theorist Agent: Applying Foucault framework and synthesizing critique...'}
    )
    
    # --- SWAP THE ENGINE HERE ---
    llm = ChatOllama(model="llama3")
    # ----------------------------
    
    system_prompt = f"""
    You are a contemporary art theorist developing the conceptual framework for an 
    exhibition titled 'Operasyon Sonrası' (Post-Op), situated in a former hospital.
    
    User Request: {state['prompt']}
    
    Historical Context of the Space: 
    {state['archival_context']}
    
    Task: Synthesize the user's request using the historical context. Apply the 
    concepts of Michel Foucault (specifically biopolitics, the clinical gaze, and 
    spatial discipline) to analyze how the architecture of the space controlled bodies.
    Format the output in clear, readable Markdown.
    """
    
    response_content = ""
    for chunk in llm.stream(system_prompt):
        response_content += chunk.content
        
        async_to_sync(channel_layer.group_send)(
            f"chat_{state['session_id']}",
            {
                'type': 'agent_message', 
                'status': 'streaming', 
                'message': chunk.content
            }
        )
    
    return {"final_synthesis": response_content}

# 4. WIRE THE GRAPH TOGETHER (This is what was missing!)
# =====================================================================
workflow = StateGraph(AgentState)
workflow.add_node("archival_agent", archival_node)
workflow.add_node("theorist_agent", theorist_node)

workflow.set_entry_point("archival_agent")
workflow.add_edge("archival_agent", "theorist_agent")
workflow.add_edge("theorist_agent", END)

# This compiles the graph into the 'app' variable!
app = workflow.compile()
# =====================================================================


# 5. The Celery Task (The entry point)
@shared_task
def test_background_worker(session_id: str, prompt: str):
    print(f"\n--- Starting Orchestration for Session: {session_id} ---")
    
    # Initialize the starting state
    inputs = {
        "session_id": session_id, 
        "prompt": prompt, 
        "archival_context": "", 
        "final_synthesis": ""
    }
    
    # Run the LangGraph machine
    result = app.invoke(inputs)
    final_text = result["final_synthesis"]
    
    # Save the AI's final synthesis permanently to PostgreSQL
    session = ChatSession.objects.get(id=session_id)
    Message.objects.create(
        session=session,
        role='assistant',
        content=final_text
    )
    
    print(f"--- Workflow Complete & Saved to Database ---\n")
    
    # --- WEBSOCKET BROADCAST ---
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'chat_{session_id}',
        {
            'type': 'agent_message', 
            'status': 'complete', 
            'message': final_text
        }
    )
    
    return "Success"