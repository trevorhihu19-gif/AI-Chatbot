import json
import structlog
from typing import Annotated, AsyncGenerator, Optional, Sequence, TypedDict
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage
)
from langchain_groq import ChatGroq
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages

from app.core.config import settings

logger = structlog.get_logger(__name__)

MAX_HISTORY_MESSAGES = 10

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    use_web_search: bool
    use_rag: bool
    citations: list[dict]
    conversation_id: Optional[str]
    user_id: str

SYSTEM_PROMPT = """You are Surge, a helpful and intelligent AI assistant.

You have access to the following tools:
- rag_search: Search the user's uploaded documents for relevant information
- web_search: Search the web for current information when needed

Guidelines:
- Be concise and direct. Lead with the answer, then explain if needed.
- Use rag_search first when the user asks about their documents.
- Use web_search for current events, facts you're unsure about, or recent information.
- If you use a tool, always incorporate the results naturally into your response.
- Cite your sources when using tool results.
- If you don't know something and can't find it with tools, say so honestly.
- Never make up facts or hallucinate information.
"""

def _build_llm(tools: list = []) -> ChatGroq:
    """
    Build the Groq LLM instance.
    If tools are provided, bind them so the LLM can call them.

    Performance: ChatGroq with streaming=True means tokens flow
    back immediately as they're generated — no waiting for the
    full response before sending anything to the client.
    """
    llm = ChatGroq(
        model=settings.groq_model,
        api_key=settings.groq_api_key,
        temperature=settings.groq_temperature,
        streaming=True,
        max_retries=2
    )
    if tools:
        return llm.bind_tools(tools)
    return llm

def _get_tools(use_web_search: bool, use_rag: bool) -> list:
    """
    Return only the tools the user has enabled.
    """
    tools = []

    if use_rag:
        try:
            from app.services.rag import rag_search_tool
            tools.append(rag_search_tool)
        except Exception as e:
            logger.warning("agent.rag_tool.unavailable", error=str(e))
    
    if use_web_search:
        try:
            from app.services.web_search import web_search_tool
            tools.append(web_search_tool)
        except Exception as e:
            logger.warning("agent.web_search_tool.unavailable", error=str(e))

    return tools

def _trim_history(messages: Sequence[BaseMessage]) -> list[BaseMessage]:
    """
    Keep only the last N messages to stay within context limits.
    Always preserve the system message if present.
    Prevents the LLM from crashing or getting too expensive. If a conversation gets 50 messages long, 
    this cuts it down to just the last MAX_HISTORY_MESSAGES (10) so the LLM doesn't hit context limits
    """
    non_system = [m for m in messages if not isinstance(m, SystemMessage)]
    trimmed = non_system[-MAX_HISTORY_MESSAGES:]
    return trimmed

async def agent_node(state: AgentState, llm_with_tools) -> dict:
    """
    The main LLM node. 

    The LLM receives the conversation history and decides:
      a) Answer directly → generates a response
      b) Call a tool → returns a tool_call that routes to tool_node
    
    This is the "brain" of the agent.
    """
    messages = _trim_history(state["messages"])
    full_messages = [SystemMessage(content=SYSTEM_PROMPT), *messages]

    logger.info(
        "agent.invoke_llm",
        model=settings.groq_model,
        message_count=len(full_messages),
        use_rag=state["use_rag"],
        use_web_search=state["use_web_search"]
    )

    response = await llm_with_tools.ainvoke(full_messages)
    return {"messages": [response]}

async def tool_node(state: AgentState) -> dict:
    """
    Executes whatever tool the LLM decided to call.

    Reads tool_calls from the last AI message, runs each tool,
    and returns ToolMessage results that feed back into the LLM.
    """
    last_message = state["messages"][-1]
    tool_calls = getattr(last_message, "tool_calls", [])

    if not tool_calls:
        return {"messages": []}
    
    tools = _get_tools(state["use_web_search"], state["use_rag"])
    tool_map = {t.name: t for t in tools}

    tool_messages = []
    citations = list(state.get("citations", []))

    for tool_call in tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        tool_call_id = tool_call["id"]

        logger.info("agent.tool_call", tool=tool_name, args=tool_args)

        if tool_name not in tool_map:
            result = f"Tool '{tool_name}' is not available"
        else:
            try:
                tool = tool_map[tool_name]
                raw_result = await tool.ainvoke(tool_args)

                if isinstance(raw_result, dict):
                    result = raw_result.get("content", str(raw_result))
                    new_citations = raw_result.get("citations", [])
                    citations.extend(new_citations)
                else:
                    result = str(raw_result)
            except Exception as e:
                logger.error("agent.tool_error", tool=tool_name, error=str(e))
                result = f"Tool error: {str(e)}"

        tool_messages.append(
            ToolMessage(
                content=result,
                tool_call_id=tool_call_id,
                name=tool_name
            )
        )

    return {
        "messages": tool_messages,
        "citations": citations
    }

def should_use_tools(state: AgentState) -> str:
    """
    After the LLM responds, decide what to do next.

    If the LLM called a tool → go to tool_node
    If the LLM answered directly → we're done (END)
    """
    last_message = state["messages"][-1]
    tool_calls = getattr(last_message, "tool_calls", [])

    if tool_calls:
        return "tool_node"
    return END

def build_agent_graph(use_web_search: bool = False, use_rag: bool = True):
    """
    Builds and compiles the LangGraph state graph.

    Called once per chat request with the user's tool preferences.
    The compiled graph is what we call to run the agent.

    Performance: graph compilation is fast (1ms).
    The expensive part is the LLM call inside agent_node.
    """
    tools = _get_tools(use_web_search=use_web_search, use_rag=use_rag)
    llm = _build_llm(tools=tools)

    graph = StateGraph(AgentState)

    graph.add_node(
        "agent_node",
        lambda state: agent_node(state, llm)
    )
    graph.add_node("tool_node", tool_node)
    graph.set_entry_point("agent_node")
    graph.add_conditional_edges(
        "agent_node",
        should_use_tools,
        {
            "tool_node": "tool_node",
            END: END,
        }
    )
    graph.add_edge("tool_node", "agent_node")

    return graph.compile()

async def run_agent_streaming(
        message: str,
        history: list[BaseMessage],
        user_id: str,
        conversation_id: Optional[str] = None,
        use_web_search: bool = False,
        use_rag: bool = True,
) -> AsyncGenerator[dict, None]:
    """
    Run the agent and stream results back as chunks.

    This is called by the chat router. It yields dicts matching
    our StreamChunk schema:

    The chat router converts these into SSE events.
    """
    graph = build_agent_graph(
        use_web_search=use_web_search,
        use_rag=use_rag
    )

    initial_state: AgentState = {
        "messages": history + [HumanMessage(content=message)],
        "use_web_search": use_web_search,
        "use_rag": use_rag,
        "citations": [],
        "conversation_id": conversation_id,
        "user_id": user_id
    }

    final_citations = []

    try:
         async for event in graph.astream_events(initial_state, version="v2"):
            event_type = event.get("event", "")
            event_name = event.get("name", "")
            data = event.get("data", {})

            #  Individual token from the LLM 
            if event_type == "on_chat_model_stream":
                chunk = data.get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    yield {
                        "type": "token",
                        "content": chunk.content,
                    }

            elif event_type == "on_tool_start":
                yield {
                    "type": "tool_start",
                    "tool_name": event_name,
                }
            elif event_type == "on_tool_end":
                output = data.get("output", {})
                citations = []
                if isinstance(output, dict):
                    citations = output.get("citations", [])
                    final_citations.extend(citations)

                yield {
                    "type": "tool_end",
                    "tool_name": event_name,
                    "citations": citations,
                }

            # State update (captures citations from tool_node) 
            elif event_type == "on_chain_end" and event_name == "tool_node":
                output_state = data.get("output", {})
                if isinstance(output_state, dict):
                    final_citations.extend(
                        output_state.get("citations", [])
                    )

            yield {
            "type": "done",
            "citations": final_citations,
        }

    except Exception as e:
        logger.error("agent.stream.error", error=str(e))
        yield {
            "type": "error",
            "error": str(e),
        }

