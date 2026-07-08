import httpx
from groq import Groq

# Create a custom HTTP client that bypasses the company's proxy SSL check
custom_http_client = httpx.Client(verify=False)

# Pass this client into your Groq initialization
client = Groq(
    api_key="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",
    http_client=custom_http_client
)

# Your existing chat completion step will now work flawlessly
completion = client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    messages=[
        {"role": "system", "content": "You are a college chatbot helper."},
        {"role": "user", "content": "Test hello!"}
    ]
)

print(completion.choices[0].message.content)