from pathlib import Path
from tools.search_tools import SearchInFilesTool

search_tool = SearchInFilesTool(Path("C:\\Users\\67222\\Desktop\\ReAct-Agent"))
print(search_tool.run({"search_text": "chat_start_time", "directory": "C:\\Users\\67222\\Desktop\\ReAct-Agent"}))