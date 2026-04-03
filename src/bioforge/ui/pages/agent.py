"""AI Agent chat page."""

import streamlit as st


def show():
    st.title("BioForge AI Agent")
    st.markdown("Chat with an AI assistant about bioinformatics problems.")

    # Chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    prompt = st.chat_input("Ask about DNA assembly, sequence analysis, or pipelines...")

    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            st.markdown(
                "The AI agent requires an Anthropic API key. "
                "Set `BIOFORGE_ANTHROPIC_API_KEY` in your `.env` file, "
                "then use the REST API at `POST /api/v1/agents/query` "
                "for full agent capabilities with tool use.\n\n"
                "For now, try the **Assembly Designer** page for interactive design."
            )
            st.session_state.messages.append({
                "role": "assistant",
                "content": "Configure your API key to enable the agent.",
            })
