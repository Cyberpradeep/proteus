"""Valid python file in the same malformed repository."""

from openai import OpenAI

client = OpenAI()
response = client.models.list()
