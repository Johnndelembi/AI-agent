from typing import Annotated, List
from typing_extensions import TypedDict
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command, interrupt

from app.config import settings, MODEL_PROVIDER
from app.services.model_service import model_service
from app.tools.chat_tools import (
    human_assistance, browse_web_page, generate_literature_review,
    generate_research_methodology, generate_study_plan, generate_audio_response,
    search_news, send_daily_news_email, setup_daily_news_schedule
)
from app.utils.logger import setup_logger

logger = setup_logger(__name__)

# State definition
class State(TypedDict):
    messages: Annotated[List, add_messages]

class ConversationalAgent:
    """Main conversational agent with LangGraph integration"""

    def __init__(self):
        self.memory = MemorySaver()
        self.graph = self._build_graph()
        logger.info("Conversational agent initialized successfully")

    def _build_graph(self):
        """Build the conversation graph with tools and system prompt"""
        graph_builder = StateGraph(State)

        # Set up tools
        from langchain_tavily import TavilySearch
        tavily_search = TavilySearch(max_results=2)
        
        tools = [
            tavily_search,
            human_assistance,
            browse_web_page,
            generate_literature_review,
            generate_research_methodology,
            generate_study_plan,
            generate_audio_response,
            search_news,
            send_daily_news_email,
            setup_daily_news_schedule
        ]

        # Initialize LLM with tools
        try:
            llm = model_service.get_default_model()
            llm_with_tools = llm.bind_tools(tools)
        except Exception as e:
            logger.error(f"Failed to initialize LLM: {e}")
            raise

        # Create system prompt
        system_prompt = (
            "You are a super intelligent AI assistant with access to multiple tools and capabilities. "
            "You can help with a wide range of tasks including research, analysis, content creation, and information gathering. "
            "You have access to:\n"
            "1. 'tavily_search' - search the web for current information, research, and data\n"
            "2. 'browse_web_page' - read and analyze web pages, articles, social media posts (Instagram, LinkedIn, Twitter/X), and online content\n"
            "3. 'generate_literature_review' - create comprehensive literature reviews on any topic\n"
            "4. 'generate_research_methodology' - suggest research methodologies for various topics\n"
            "5. 'generate_study_plan' - create detailed study plans for any subject\n"
            "6. 'generate_audio_response' - convert text responses to audio using TTS\n"
            "7. 'search_news' - search for news headlines and updates across locations and topics\n"
            "8. 'send_daily_news_email' - send flexible daily news digest email with custom topics or content\n"
            "9. 'setup_daily_news_schedule' - setup daily news email schedule\n"
            "10. 'human_assistance' - request human help when needed\n\n"
            "You are capable of handling diverse topics and providing intelligent, well-researched responses.\n\n"
            "- If the user provides a URL to any webpage or social media post (Instagram, LinkedIn, Twitter/X), use the 'browse_web_page' tool to analyze it.\n"
            "- If the user asks you to browse a page without providing a URL, you MUST ask for one.\n"
            "- For research questions and information gathering, use the 'tavily_search' tool to find current information and sources.\n"
            "- For comprehensive topic analysis, use the 'generate_literature_review' tool for detailed reviews.\n"
            "- For research methodology questions, use the 'generate_research_methodology' tool.\n"
            "- For learning and study planning, use the 'generate_study_plan' tool for structured approaches.\n"
            "- Provide detailed explanations with examples and practical applications.\n"
            "- Always cite sources when possible and suggest additional resources.\n"
            "- Focus on accuracy, critical thinking, and evidence-based responses.\n"
            "- When users ask for audio versions of responses or say 'speak this', 'read aloud', or 'audio', use the 'generate_audio_response' tool.\n"
            "- When users ask for news, headlines, current events, or any news-related queries, ALWAYS use the 'search_news' tool.\n"
            "- For general news requests, use 'search_news' with topic='latest news' and location='global'.\n"
            "- For specific topic news (like AI, technology, business, etc.), use 'search_news' with the appropriate topic.\n"
            "- For AI trends, AI news, or technology trends, use 'search_news' with topic='AI trends' or 'technology trends'.\n"
            "- For location-specific news, use 'search_news' with the appropriate location parameter.\n"
            "- When users ask to send news via email, use the 'send_daily_news_email' tool with custom topics or content.\n"
            "- For email scheduling, use the 'setup_daily_news_schedule' tool.\n"
            "- If the user asks for 'expert guidance', 'human help', or explicitly asks you to 'request assistance', "
            "you MUST use the 'human_assistance' tool. Do not try to answer these queries yourself.\n"
            "- IMPORTANT: When users ask for news, trends, or current events, ALWAYS use the 'search_news' tool instead of providing manual summaries or responses."
        )

        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content=system_prompt),
            ("placeholder", "{messages}"),
        ])

        # Create agent chain
        agent_chain = prompt | llm_with_tools

        # Define chatbot node
        def chatbot_node(state: State):
            try:
                filtered_messages = self._filter_messages(state["messages"])
                if not filtered_messages:
                    logger.warning("No valid messages found in state")
                    return {"messages": []}
                
                message = agent_chain.invoke({"messages": filtered_messages})
                if hasattr(message, "tool_calls") and len(message.tool_calls) > 1:
                    logger.warning(f"Multiple tool calls detected: {len(message.tool_calls)}")
                
                return {"messages": [message]}
            except Exception as e:
                logger.error(f"Error in chatbot node: {e}")
                error_msg = {"role": "assistant", "content": "I encountered an error processing your request. Please try again."}
                return {"messages": [error_msg]}

        # Build graph
        graph_builder.add_node("chatbot", chatbot_node)
        
        tool_node = ToolNode(tools=tools)
        graph_builder.add_node("tools", tool_node)
        
        # Add edges
        graph_builder.add_conditional_edges("chatbot", tools_condition)
        graph_builder.add_edge("tools", "chatbot")
        graph_builder.add_edge(START, "chatbot")
        
        return graph_builder.compile(checkpointer=self.memory)

    def _filter_messages(self, messages):
        """Filter messages to keep only valid ones"""
        filtered_messages = []
        
        for msg in messages:
            # Handle different message types
            if hasattr(msg, "tool_calls") and getattr(msg, "tool_calls", None):
                # Keep tool call messages
                filtered_messages.append(msg)
            elif hasattr(msg, "content") and msg.content is not None:
                # Handle LCEL message objects
                content = str(msg.content).strip()
                if content:
                    filtered_messages.append(msg)
            elif isinstance(msg, dict):
                # Handle dict-style messages
                content = str(msg.get("content", "")).strip()
                if content:
                    filtered_messages.append(msg)
            else:
                logger.debug(f"Skipping message of unknown type or with None content: {type(msg)}")
        
        return filtered_messages

    def _is_json(self, text):
        """Check if text is valid JSON"""
        try:
            import json
            json.loads(text)
            return True
        except (ValueError, TypeError):
            return False

    def _handle_interrupt(self, command_exception):
        """Handle human-in-the-loop interrupts"""
        try:
            query = command_exception.data.get('query', 'Assistance needed')
            response = f"\n[🤝 Human Assistance Needed] {query}\nPlease provide your response:"
            print(response)
            
            human_input = input("Your response: ").strip()
            if not human_input:
                human_input = "No response provided"
            
            command_exception.resume({"data": human_input})
            logger.info("Human assistance provided, resuming conversation")
        except Exception as e:
            logger.error(f"Error handling interrupt: {e}")
            try:
                error_msg = "Unable to get human assistance"
                print(error_msg)
                command_exception.resume({"data": error_msg})
            except:
                pass

    def _process_event_value(self, value):
        """Process event values and extract assistant responses"""
        if isinstance(value, tuple) and len(value) == 2:
            value = value[1]
        
        if isinstance(value, dict) and "messages" in value and value["messages"]:
            last_msg = value["messages"][-1]
            
            content = getattr(last_msg, "content", None)
            if content is None and isinstance(last_msg, dict):
                content = last_msg.get("content", "")
            
            if content and not self._is_json(str(content)):
                return content
        return None

    def stream_conversation(self, user_input: str, thread_id: str = "default-thread"):
        """Stream conversation updates with improved error handling"""
        config = {"configurable": {"thread_id": thread_id}}
        response = ""
        
        try:
            for event in self.graph.stream(
                {"messages": [{"role": "user", "content": user_input}]},
                config
            ):
                for value in event.values():
                    content = self._process_event_value(value)
                    if content and not self._is_json(str(content)):
                        response = content
            
            return response
        except Command as cmd:
            self._handle_interrupt(cmd)
            return "Human assistance was requested and handled."
        except Exception as e:
            logger.error(f"Error in stream_conversation: {e}")
            return f"❌ Error: {e}"

    def get_state_snapshot(self, thread_id: str = "default-thread"):
        """Get detailed state information for debugging"""
        config = {"configurable": {"thread_id": thread_id}}
        
        try:
            snapshot = self.graph.get_state(config)
            return {
                "values": snapshot.values,
                "next": snapshot.next,
                "created_at": snapshot.created_at,
                "tasks_count": len(snapshot.tasks) if snapshot.tasks else 0
            }
        except Exception as e:
            logger.error(f"Error getting state snapshot: {e}")
            return {"error": str(e)}

# Global agent instance
agent = ConversationalAgent() 