import openai
import os

client = openai.OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url="https://open.bigmodel.cn/api/paas/v4",
)

response = client.chat.completions.create(
    model="glm-4.7-flash",
    messages=[{"role": "user", "content": "Hello, how are you?"}],
    extra_body={"thinking": {"type": "disabled"}},
)

print(response.choices[0].message)