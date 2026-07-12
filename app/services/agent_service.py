"""Law-focused conversational agent powered by TanzLII-first internal tools."""

from __future__ import annotations

from typing import Annotated, TypedDict

from langchain_core.messages import SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.types import Command

from app.config import CHATBOT_MODEL, MODEL_PROVIDER, logger
from app.services.tanzlii_service import TanzLIIService


class State(TypedDict):
    """Conversation state for the legal graph."""

    messages: Annotated[list, add_messages]


def init_chat_model(model_name: str, model_provider: str = "openai"):
    """Initialize the configured chat model provider."""
    normalized_name = model_name.split(":", 1)[-1]

    if model_provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=normalized_name)
    if model_provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model=normalized_name)
    if model_provider == "google_genai":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(model=normalized_name)

    logger.warning("Unknown model provider %s, falling back to OpenAI", model_provider)
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(model=normalized_name)


_tanzlii_service = TanzLIIService()


def _format_sources(results: list[dict], label: str) -> str:
    if not results:
        return f"No {label} sources were found from TanzLII."

    lines = [f"TanzLII {label.title()} Sources:"]
    for index, item in enumerate(results, start=1):
        details = []
        if item.get("court"):
            details.append(f"court={item['court']}")
        if item.get("year"):
            details.append(f"year={item['year']}")
        if item.get("document_date"):
            details.append(f"date={item['document_date']}")
        if item.get("fetch_error"):
            details.append("cached_with_fetch_error=true")

        summary = item.get("summary") or "No summary available from the search result."
        details_text = f" ({', '.join(details)})" if details else ""
        lines.append(f"{index}. {item['title']}{details_text}")
        lines.append(f"   URL: {item['url']}")
        lines.append(f"   Summary: {summary}")
    return "\n".join(lines)


@tool
def research_tanzanian_law(question: str) -> str:
    """Research a Tanzanian legal question using TanzLII-first retrieval across relevant collections."""
    try:
        research_pack = _tanzlii_service.research(question)
    except Exception as exc:
        return f"TanzLII research failed for this question: {exc}"
    sources = research_pack.get("sources", [])
    if not sources:
        return (
            "No TanzLII sources were found for this question. "
            "State that the answer could not be verified from TanzLII and ask the user to narrow the issue."
        )

    lines = [
        f"Research question: {research_pack['question']}",
        f"Collections searched: {', '.join(research_pack['collections'])}",
        "Use only the sources below for substantive legal claims unless you explicitly say you could not verify further.",
    ]
    for index, source in enumerate(sources, start=1):
        lines.append(f"{index}. {source['title']}")
        lines.append(f"   Collection: {source.get('collection')}")
        lines.append(f"   URL: {source['url']}")
        if source.get("citation"):
            lines.append(f"   Citation: {source['citation']}")
        if source.get("summary"):
            lines.append(f"   Search summary: {source['summary']}")
        if source.get("document_excerpt"):
            lines.append(f"   Document excerpt: {source['document_excerpt']}")
        if source.get("document_fetch_status"):
            lines.append(f"   Fetch status: {source['document_fetch_status']}")
    return "\n".join(lines)


@tool
def search_tanzlii_legislation(query: str, limit: int = 5) -> str:
    """Search TanzLII legislation, including Acts and subsidiary legislation."""
    try:
        return _format_sources(_tanzlii_service.search(query, collection="legislation", limit=limit), "legislation")
    except Exception as exc:
        return f"TanzLII legislation search failed: {exc}"


@tool
def search_tanzlii_judgments(query: str, limit: int = 5) -> str:
    """Search TanzLII judgments and case-law sources."""
    try:
        return _format_sources(_tanzlii_service.search(query, collection="judgments", limit=limit), "judgments")
    except Exception as exc:
        return f"TanzLII judgments search failed: {exc}"


@tool
def search_tanzlii_gazettes(query: str, limit: int = 5) -> str:
    """Search TanzLII Government Gazette materials."""
    try:
        return _format_sources(_tanzlii_service.search(query, collection="gazettes", limit=limit), "gazettes")
    except Exception as exc:
        return f"TanzLII gazette search failed: {exc}"


@tool
def search_tanzlii_secondary_sources(query: str, limit: int = 5) -> str:
    """Search TanzLII secondary sources such as journals, articles, digests, and law reform materials."""
    try:
        return _format_sources(
            _tanzlii_service.search(query, collection="secondary_sources", limit=limit),
            "secondary sources",
        )
    except Exception as exc:
        return f"TanzLII secondary-source search failed: {exc}"


@tool
def get_tanzlii_document(url: str) -> str:
    """Fetch and cache a TanzLII document page by URL, returning its text excerpt and metadata."""
    try:
        payload = _tanzlii_service.fetch_document(url)
    except Exception as exc:
        return f"TanzLII document fetch failed: {exc}"
    if payload.get("fetch_status") == "unavailable":
        return (
            f"Document fetch was unavailable for {payload['url']}.\n"
            f"Warning: {payload.get('warning', 'Unknown fetch error')}"
        )

    lines = [
        f"Title: {payload.get('title')}",
        f"Collection: {payload.get('collection')}",
        f"URL: {payload.get('url')}",
        f"Fetch status: {payload.get('fetch_status')}",
    ]
    if payload.get("citation"):
        lines.append(f"Citation: {payload['citation']}")
    if payload.get("document_date"):
        lines.append(f"Document date: {payload['document_date']}")
    if payload.get("expression_date"):
        lines.append(f"Expression date: {payload['expression_date']}")
    if payload.get("status_labels"):
        lines.append(f"Status labels: {', '.join(payload['status_labels'])}")
    if payload.get("warning"):
        lines.append(f"Warning: {payload['warning']}")
    if payload.get("excerpt"):
        lines.append(f"Excerpt: {payload['excerpt']}")
    return "\n".join(lines)


@tool
def sync_tanzlii_collection(collection: str, seed_query: str, limit: int = 5) -> str:
    """Sync and cache a TanzLII collection internally using a seed query."""
    try:
        result = _tanzlii_service.sync_collection(collection=collection, seed_query=seed_query, limit=limit)
    except Exception as exc:
        return f"TanzLII collection sync failed: {exc}"
    return (
        f"Synced collection={result['collection']} with seed_query={result['seed_query']}. "
        f"Discovered={result['discovered']}, fetched={result['fetched']}, failures={result['failures']}."
    )


@tool
def refresh_tanzlii_cache(per_collection: int = 3) -> str:
    """Refresh the internal TanzLII cache for recent judgments, legislation, and gazettes."""
    try:
        stats = _tanzlii_service.warm_cache_recent(per_collection=per_collection)
    except Exception as exc:
        return f"TanzLII cache refresh failed: {exc}"

    lines = [
        "TanzLII cache refresh completed.",
        f"Total discovered: {stats['total_discovered']}",
        f"Total fetched: {stats['total_fetched']}",
        f"Total failures: {stats['total_failures']}",
    ]
    for collection, result in stats["collections"].items():
        lines.append(
            f"- {collection}: discovered={result['discovered']}, "
            f"fetched={result['fetched']}, failures={result['failures']}"
        )
    return "\n".join(lines)


class ConversationalAgent:
    """Law-focused conversational agent wired to the existing chat interface."""

    def __init__(self):
        self.memory = MemorySaver()
        self.graph = self._build_graph()
        logger.info("Law-focused conversational agent initialized successfully")

    def _build_graph(self):
        graph_builder = StateGraph(State)

        tools = [
            research_tanzanian_law,
            search_tanzlii_legislation,
            search_tanzlii_judgments,
            search_tanzlii_gazettes,
            search_tanzlii_secondary_sources,
            get_tanzlii_document,
            sync_tanzlii_collection,
            refresh_tanzlii_cache,
        ]

        llm = init_chat_model(CHATBOT_MODEL, model_provider=MODEL_PROVIDER)
        llm_with_tools = llm.bind_tools(tools)

        system_prompt = (
            "You are Artemis Legal, a Tanzanian legal research assistant operating through TanzLII-first retrieval.\n\n"
            "Your job is to help users research Tanzanian law using source-backed answers.\n\n"
            "Rules:\n"
            "1. For any substantive legal claim, use TanzLII tools first.\n"
            "2. Prefer primary law in this order when relevant: legislation, judgments, gazettes.\n"
            "3. Clearly distinguish primary authorities from secondary sources like journals or articles.\n"
            "4. Cite exact source URLs and mention dates whenever they are available.\n"
            "5. If a source could not be fetched fully, say so plainly and avoid inventing holdings, section text, or outcomes.\n"
            "6. If the user asks for explanation in simple language, still ground the explanation in the sourced materials.\n"
            "7. Do not answer from general legal memory when TanzLII verification is needed; say you could not verify instead.\n"
            "8. Treat TanzLII as the primary corpus for this assistant.\n\n"
            "Operational behavior:\n"
            "- If the user asks to refresh, warm, reload, or update the TanzLII cache, call refresh_tanzlii_cache.\n"
            "- If the user asks to sync one specific collection with a topic or seed query, call sync_tanzlii_collection.\n\n"
            "Answer style:\n"
            "- Start with the direct answer when the sources support one.\n"
            "- Then list the legal basis briefly.\n"
            "- Then include a short Sources section with direct links.\n"
            "- If uncertainty remains, say exactly what is missing."
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessage(content=system_prompt),
                ("placeholder", "{messages}"),
            ]
        )

        agent_chain = prompt | llm_with_tools

        def chatbot_node(state: State):
            try:
                filtered_messages = self._filter_messages(state["messages"])
                if not filtered_messages:
                    return {"messages": []}
                message = agent_chain.invoke({"messages": filtered_messages})
                return {"messages": [message]}
            except Exception as exc:
                logger.error("Error in legal chatbot node: %s", exc)
                return {
                    "messages": [
                        {
                            "role": "assistant",
                            "content": (
                                "I hit an internal error while working with the TanzLII legal tools. "
                                "Please retry the request with a narrower legal question."
                            ),
                        }
                    ]
                }

        graph_builder.add_node("chatbot", chatbot_node)
        graph_builder.add_node("tools", ToolNode(tools=tools))
        graph_builder.add_conditional_edges("chatbot", tools_condition)
        graph_builder.add_edge("tools", "chatbot")
        graph_builder.add_edge(START, "chatbot")

        return graph_builder.compile(checkpointer=self.memory)

    def _filter_messages(self, messages):
        filtered_messages = []
        for msg in messages:
            if hasattr(msg, "tool_calls") and getattr(msg, "tool_calls", None):
                filtered_messages.append(msg)
            elif hasattr(msg, "content") and msg.content is not None:
                content = str(msg.content).strip()
                if content:
                    filtered_messages.append(msg)
            elif isinstance(msg, dict):
                content = str(msg.get("content", "")).strip()
                if content:
                    filtered_messages.append(msg)
        return filtered_messages

    async def stream_conversation(self, user_input: str, thread_id: str = "default-thread"):
        config = {"configurable": {"thread_id": thread_id}}
        response = ""

        try:
            async for event in self.graph.astream(
                {"messages": [{"role": "user", "content": user_input}]},
                config,
            ):
                for value in event.values():
                    if isinstance(value, dict) and "messages" in value and value["messages"]:
                        last_msg = value["messages"][-1]
                        content = getattr(last_msg, "content", None)
                        if content is None and isinstance(last_msg, dict):
                            content = last_msg.get("content", "")
                        if content:
                            response = content
            return response
        except Command:
            raise
        except Exception as exc:
            logger.error("Error in legal stream_conversation: %s", exc)
            return f"Unable to complete the TanzLII legal research flow: {exc}"
