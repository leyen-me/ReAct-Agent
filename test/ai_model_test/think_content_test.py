import openai
import os

client = openai.OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url="https://integrate.api.nvidia.com/v1",
)

response = client.chat.completions.create(
    model="openai/gpt-oss-120b",
    messages=[
        {"role": "system", "content": "You are a helpful assistant. 始终使用中文回答 "},
        {"role": "user", "content": "i have may tools, example: [ print_tree, search, open_file, read_file, write_file, list_files, run, shell, git ...], 还有哪些, 包括详细的参数"},
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
