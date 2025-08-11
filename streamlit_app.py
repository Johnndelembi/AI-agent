import streamlit as st
import os
from basic_chatbot import ConversationalAgent

# Import ConversationalAgent first, as it's less likely to fail
from basic_chatbot import ConversationalAgent

# Conditionally import TTS-related components
try:
    from basic_chatbot import TTS_AVAILABLE, generate_tts_audio
except ImportError as e:
    st.warning(f"TTS components unavailable: {e}. Audio features will be disabled.")
    TTS_AVAILABLE = False
    generate_tts_audio = None 

# Initialize chatbot
if 'agent' not in st.session_state:
    st.session_state.agent = ConversationalAgent()

# Set page config
st.set_page_config(
    page_title="Artemis AI",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS to hide Streamlit UI elements
st.markdown("""
<style>
    /* Hide the top-right corner elements (Fork, GitHub, etc.) */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Hide the account menu at bottom */
    .stDeployButton {display: none;}
    
    /* Hide Streamlit logo in header */
    .stApp > header {display: none;}
    
    /* Hide the hamburger menu */
    .stApp > div[data-testid="stToolbar"] {display: none;}
    
    /* Hide the "made with streamlit" footer */
    .stApp > footer {display: none;}
    
    /* Additional hiding for deployment elements */
    .stApp > div[data-testid="stDecoration"] {display: none;}
    
    /* Ensure clean layout */
    .main .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hello! I'm your AI Research & Study Assistant. I can help you with academic research, literature reviews, data analysis, study planning, and scholarly writing. What would you like to research or study today?"}
    ]

# Track last generated audio file for direct playback
if "last_audio_file" not in st.session_state:
    st.session_state.last_audio_file = None

# Initialize awaiting_response flag
if "awaiting_response" not in st.session_state:
    st.session_state.awaiting_response = False

# Sidebar
with st.sidebar:
    st.title("📚 Research & Study Assistant")
    st.success(
        "A powerful AI assistant for academic research, literature reviews, study planning, and scholarly writing."
    )
    
    
    # Quick actions
    
    
    def sidebar_quick_actions():
        # Research topic input
        with st.expander("🔬 Research Tools", expanded=False):
            research_topic = st.text_input("Research Topic:", placeholder="Enter your research topic...")
            
            # Academic research tools
            if st.button("📖 Literature Review"):
                if research_topic:
                    st.session_state.messages.append({"role": "user", "content": f"Help me conduct a literature review on {research_topic}. Include recent studies, key findings, and research gaps."})
                    st.session_state.awaiting_response = True
                    st.rerun()
            
            if st.button("📊 Research Methodology"):
                if research_topic:
                    st.session_state.messages.append({"role": "user", "content": f"Suggest appropriate research methodologies for studying {research_topic}. Include quantitative and qualitative approaches."})
                    st.session_state.awaiting_response = True
                    st.rerun()
            
            if st.button("📝 Academic Writing"):
                if research_topic:
                    st.session_state.messages.append({"role": "user", "content": f"Help me write an academic paper introduction about {research_topic}. Include background, problem statement, and objectives."})
                    st.session_state.awaiting_response = True
                    st.rerun()
        
        # Study assistance tools
        with st.expander("📚 Study Assistance", expanded=False):
            study_subject = st.text_input("Study Subject:", placeholder="What are you studying?")
            
            if st.button("🎯 Study Plan"):
                if study_subject:
                    st.session_state.messages.append({"role": "user", "content": f"Create a comprehensive study plan for {study_subject}. Include learning objectives, timeline, and study strategies."})
                    st.session_state.awaiting_response = True
                    st.rerun()
            
            if st.button("❓ Practice Questions"):
                if study_subject:
                    st.session_state.messages.append({"role": "user", "content": f"Generate practice questions and problems for {study_subject} to test my understanding."})
                    st.session_state.awaiting_response = True
                    st.rerun()
            
            if st.button("📋 Summary & Notes"):
                if study_subject:
                    st.session_state.messages.append({"role": "user", "content": f"Create a comprehensive summary and study notes for {study_subject} with key concepts and examples."})
                    st.session_state.awaiting_response = True
                    st.rerun()

        # Audio Tools
        st.header("🎵 Generate Audio")
        if TTS_AVAILABLE:
            if st.button("🔊 Speak Last Response"):
                # Directly generate audio from the last assistant message
                assistant_messages = [m for m in st.session_state.messages if m["role"] == "assistant"]
                if assistant_messages:
                    last_response = assistant_messages[-1]["content"]
                    files = generate_tts_audio(last_response)
                    if files:
                        st.session_state.last_audio_file = files[0]
                        st.success(f"Audio generated: {os.path.basename(files[0])}")
                    else:
                        st.error("Failed to generate audio.")
                else:
                    st.warning("No assistant response to convert to audio.")
        else:
            st.info("Install kokoro and soundfile to enable audio features.")

        # Creator credit below input field
        st.markdown("""
        <div style="text-align: center; margin-top: 1rem; margin-bottom: 2rem;">
            <p style="color: #666; font-size: 0.9rem;">
                Built with ❤️ by <a href="https://johnny-dev.onrender.com/" target="_blank" style="color: #667eea; text-decoration: none; font-weight: bold;">John Ndelembi</a>
            </p>
        </div>
        """, unsafe_allow_html=True)

    sidebar_quick_actions()

# Chat input with improved styling (must be before chat history rendering)
prompt = st.chat_input("Type your message here...")
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    # Clear last audio when starting a new turn
    st.session_state.last_audio_file = None
    st.session_state.awaiting_response = True
    st.rerun()

# If awaiting_response, generate assistant response and rerun
if st.session_state.awaiting_response:
    # Find the last user message without a following assistant message
    user_msgs = [i for i, m in enumerate(st.session_state.messages) if m["role"] == "user"]
    assistant_msgs = [i for i, m in enumerate(st.session_state.messages) if m["role"] == "assistant"]
    if user_msgs and (not assistant_msgs or user_msgs[-1] > assistant_msgs[-1]):
        last_user_msg = st.session_state.messages[user_msgs[-1]]["content"]
        try:
            response = st.session_state.agent.stream_conversation(
                last_user_msg,
                thread_id="streamlit-chat",
                streamlit_output=None
            )
            st.session_state.messages.append({"role": "assistant", "content": response})
        except Exception as e:
            st.session_state.messages.append({"role": "assistant", "content": f"Error: {e}"})
    # Response completed; clear any previous audio until user regenerates for this response
    st.session_state.last_audio_file = None
    st.session_state.awaiting_response = False
    st.rerun()

# Main content
st.title("📚 Artemis")

# Display chat messages in a more chat-like format
st_idx_last_asst = None
for idx, msg in enumerate(st.session_state.messages):
    if msg["role"] == "assistant":
        st_idx_last_asst = idx

for idx, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        if message["role"] == "assistant":
            # Render assistant message as Markdown
            st.markdown(message["content"])
            
            # Show audio ONLY for the latest assistant message
            if idx == st_idx_last_asst:
                # 1) If a file was just generated directly, show it
                if TTS_AVAILABLE and st.session_state.get("last_audio_file"):
                    st.audio(st.session_state.last_audio_file, format="audio/wav")
                # 2) Fallback: If the message text contains a referenced audio file, render it
                elif TTS_AVAILABLE and "audio_output" in message["content"] and "response_" in message["content"]:
                    import re
                    match = re.search(r'response_(\d+)\.wav', message["content"])
                    if match:
                        timestamp = match.group(1)
                        audio_file = f"audio_output/response_{timestamp}.wav"
                        st.audio(audio_file, format="audio/wav")
        else:
            st.markdown("<div style='display: flex; align-items: center;'>\U0001F464 <div style='margin-left: 8px; font-weight: bold; color: #0066cc;'>" + message["content"] + "</div></div>", unsafe_allow_html=True)