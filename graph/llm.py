"""Thin wrapper around the OpenAI SDK shared by all three LLM-backed
agents (briefing, query answering, retirement question generation).

MODEL is a single constant so swapping ids is a one-line change — pick
whatever model id your OpenAI account has access to.

Every call site that uses this module must have a non-LLM fallback path.
No live call may be a single point of failure for the demo.
"""
import os

MODEL = "gpt-4o"

_client = None
_client_checked = False


def get_client():
    global _client, _client_checked
    if _client_checked:
        return _client
    _client_checked = True
    if not os.environ.get("OPENAI_API_KEY"):
        return None
    try:
        import openai
        _client = openai.OpenAI()
    except Exception:
        _client = None
    return _client


def call_llm(system_prompt: str, user_message: str, max_tokens: int = 400) -> str | None:
    """Returns the model's text response, or None if no key is configured
    or the call fails for any reason. Callers must have a fallback."""
    client = get_client()
    if client is None:
        return None
    try:
        response = client.chat.completions.create(
            model=MODEL,
            max_completion_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        )
        return (response.choices[0].message.content or "").strip()
    except Exception as e:
        print(f"[llm] call failed, falling back: {e}")
        return None
