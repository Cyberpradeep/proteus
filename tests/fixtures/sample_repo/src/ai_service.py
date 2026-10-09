"""Sample AI client service using multiple provider SDKs with secret-bearing initialization."""

from google import genai
from openai import OpenAI

# Client instantiations with API keys (must be redacted during discovery)
gemini_client = genai.Client(api_key="AIzaSyB123456789012345678901234567890")
openai_client = OpenAI(
    api_key="sk-1234567890abcdef1234567890abcdef",
    base_url="https://api.openai.com/v1",
)


def generate_gemini_summary(prompt: str) -> str:
    """Generate content via Google Gemini SDK."""
    response = gemini_client.models.generate_content(
        model="gemini-1.5-pro",
        contents=prompt,
    )
    return str(response.text)


def generate_openai_response(prompt: str) -> str:
    """Generate completion via OpenAI SDK."""
    completion = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
    )
    return str(completion.choices[0].message.content)
