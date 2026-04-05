"""AI Agent chat page — connects to the BioForge REST API for multi-turn conversations."""

import os

import httpx
import streamlit as st

API_BASE = os.getenv("BIOFORGE_API_URL", "http://localhost:8000")


def _api_url(path: str) -> str:
    return f"{API_BASE}/api/v1/agents{path}"


def show():
    st.title("BioForge AI Agent")
    st.markdown(
        "Chat with an AI assistant about DNA assembly, variant analysis, "
        "structure prediction, and more."
    )

    # Sidebar configuration
    with st.sidebar:
        st.subheader("Agent Settings")
        api_key = st.text_input(
            "Anthropic API Key",
            value=os.getenv("BIOFORGE_ANTHROPIC_API_KEY", ""),
            type="password",
            help="Set BIOFORGE_ANTHROPIC_API_KEY env var or enter here",
        )
        if api_key:
            os.environ["BIOFORGE_ANTHROPIC_API_KEY"] = api_key

        st.divider()
        st.caption("Capabilities: Assembly, Evo 2, Structure, Alignment, Variants, Experiments, SBOL")

    # Initialize session state
    if "agent_session_id" not in st.session_state:
        st.session_state.agent_session_id = None
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "session_error" not in st.session_state:
        st.session_state.session_error = None

    # Display chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("tool_calls"):
                with st.expander(f"Tool calls ({len(msg['tool_calls'])})"):
                    for tc in msg["tool_calls"]:
                        st.code(
                            f"Tool: {tc.get('tool', 'unknown')}\n"
                            f"Input: {tc.get('input', {})}\n"
                            f"Output: {str(tc.get('output', ''))[:500]}",
                            language="yaml",
                        )

    # New session button
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("New Session", use_container_width=True):
            st.session_state.agent_session_id = None
            st.session_state.messages = []
            st.session_state.session_error = None
            st.rerun()

    # Chat input
    prompt = st.chat_input("Ask about DNA assembly, variant analysis, structure prediction...")

    if prompt:
        # Add user message to display
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = _send_message(prompt)

            if response.get("error"):
                st.error(response["error"])
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": f"Error: {response['error']}",
                })
            else:
                text = response.get("text", response.get("response", "No response"))
                st.markdown(text)
                tool_calls = response.get("tool_calls", [])

                msg = {"role": "assistant", "content": text}
                if tool_calls:
                    msg["tool_calls"] = tool_calls
                    with st.expander(f"Tool calls ({len(tool_calls)})"):
                        for tc in tool_calls:
                            st.code(
                                f"Tool: {tc.get('tool', 'unknown')}\n"
                                f"Input: {tc.get('input', {})}\n"
                                f"Output: {str(tc.get('output', ''))[:500]}",
                                language="yaml",
                            )

                turns = response.get("turns_used", response.get("turns", 0))
                if turns:
                    st.caption(f"Completed in {turns} turn(s)")

                st.session_state.messages.append(msg)


def _send_message(prompt: str) -> dict:
    """Send a message to the BioForge agent API."""
    try:
        # If we have a session, use multi-turn endpoint
        if st.session_state.agent_session_id:
            resp = httpx.post(
                _api_url(f"/sessions/{st.session_state.agent_session_id}/messages"),
                json={"prompt": prompt},
                timeout=120.0,
            )
            if resp.status_code == 404:
                # Session expired, create new one
                st.session_state.agent_session_id = None
                return _send_message(prompt)
            if resp.status_code != 200:
                return {"error": f"API error: {resp.status_code} - {resp.text[:200]}"}
            return resp.json()

        # Create new session first
        session_resp = httpx.post(
            _api_url("/sessions"),
            json={
                "workspace_id": "00000000-0000-0000-0000-000000000001",
                "project_id": "00000000-0000-0000-0000-000000000001",
            },
            timeout=30.0,
        )
        if session_resp.status_code != 200:
            # Fall back to single-turn query
            return _single_turn_query(prompt)

        session_data = session_resp.json()
        st.session_state.agent_session_id = session_data["session_id"]

        # Now send the message
        resp = httpx.post(
            _api_url(f"/sessions/{st.session_state.agent_session_id}/messages"),
            json={"prompt": prompt},
            timeout=120.0,
        )
        if resp.status_code != 200:
            return {"error": f"API error: {resp.status_code} - {resp.text[:200]}"}
        return resp.json()

    except httpx.ConnectError:
        # API not running — provide helpful offline message
        return _offline_response(prompt)
    except httpx.TimeoutException:
        return {"error": "Request timed out. The agent may be processing a complex query."}
    except Exception as e:
        return {"error": str(e)}


def _single_turn_query(prompt: str) -> dict:
    """Fallback to single-turn query endpoint."""
    try:
        resp = httpx.post(
            _api_url("/query"),
            json={
                "prompt": prompt,
                "workspace_id": "00000000-0000-0000-0000-000000000001",
                "project_id": "00000000-0000-0000-0000-000000000001",
            },
            timeout=120.0,
        )
        if resp.status_code != 200:
            return {"error": f"API error: {resp.status_code} - {resp.text[:200]}"}
        return resp.json()
    except Exception as e:
        return {"error": str(e)}


def _offline_response(prompt: str) -> dict:
    """Provide helpful guidance when the API server is not running."""
    return {
        "text": (
            "The BioForge API server is not running. To start it:\n\n"
            "```bash\n"
            "# Start infrastructure\n"
            "docker compose up -d\n\n"
            "# Start the API server\n"
            "uvicorn bioforge.api.app:create_app --factory --reload\n"
            "```\n\n"
            "Make sure `BIOFORGE_ANTHROPIC_API_KEY` is set in your `.env` file.\n\n"
            "**Your question:** " + prompt
        ),
    }
