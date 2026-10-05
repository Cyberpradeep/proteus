"""Sample AI client service."""

import os


def generate_summary(prompt: str) -> str:
    # Dummy mock client call for testing discovery AST patterns
    api_key = os.environ.get("GEMINI_API_KEY", "MOCK_TOKEN")
    if not api_key:
        raise ValueError("Missing API key")
    return f"Response for {prompt}"
