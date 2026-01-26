import openai
import os

client = openai.OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url="https://integrate.api.nvidia.com/v1",
)

response = client.chat.completions.create(
    model="openai/gpt-oss-120b",
    messages=[
        {"role": "system", "content": "You are a helpful assistant. 在思考结束时，必须添加两个单词 'thinking over.' 表示思考结束。"},
        {"role": "user", "content": "Hello, how are you?"},
    ],
    temperature=0.3,
    top_p=1,
    frequency_penalty=0,
    presence_penalty=0,
    max_tokens=8192,
    extra_body={"reasoning_effort": "medium"},
)

print("="*100)
print("reasoning_content: ", response.choices[0].message.reasoning_content)
print("="*100)
print("content: ", response.choices[0].message.content)
print("="*100)
