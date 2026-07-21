"""Thin wrapper around the Anthropic SDK shared by all three LLM-backed
agents (briefing, query answering, retirement question generation).

MODEL is a single constant so swapping ids is a one-line change — the
master build prompt specified `claude-sonnet-4-6`, which is not a real
model id on this account; defaulting to `claude-sonnet-5`.

Every call site that uses this module must have a non-LLM fallback path.
No live call may be a single point of failure for the demo.
"""
import os

MODEL = "claude-sonnet-5"

_client = None
_client_checked = False


def get_client():
    global _client, _client_checked
    if _client_checked:
        return _client
    _client_checked = True
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic
        _client = anthropic.Anthropic()
    except Exception:
        _client = None
    return _client


def call_claude(system_prompt: str, user_message: str, max_tokens: int = 400) -> str | None:
    """Returns the model's text response, or None if no key is configured
    or the call fails for any reason. Callers must have a fallback."""
    client = get_client()
    if client is None:
        return None
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        return "".join(block.text for block in response.content if block.type == "text").strip()
    except Exception as e:
        print(f"[llm] call failed, falling back: {e}")
        return None
