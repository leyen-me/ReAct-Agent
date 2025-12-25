#!/usr/bin/env python3
import sys
import os
from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url="https://api.siliconflow.cn/v1",
)

stream_response = client.chat.completions.create(
    model="deepseek-ai/DeepSeek-R1-0528-Qwen3-8B",
    messages=[{"role": "user", "content": "你好，请介绍一下你自己"}],
    stream=True
)

for chunk in stream_response:
    if chunk.choices[0].delta.reasoning_content:
        print(chunk.choices[0].delta.reasoning_content, end="", flush=True)
    
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)