from pathlib import Path
from tools.search_tools import SearchInFilesTool
from tools.file_tools import ListFilesTool, TreeFilesTool

work_dir = Path("C:\\Users\\67222\\Desktop\\ReAct-Agent")

print("=" * 80)
print("测试 SearchInFilesTool")
print("=" * 80)
search_tool = SearchInFilesTool(work_dir)
result = search_tool.run({"search_text": "chat_start_time", "directory": str(work_dir)})
print(result)

print("\n" + "=" * 80)
print("测试 ListFilesTool（应该自动忽略 node_modules、__pycache__ 等）")
print("=" * 80)
list_tool = ListFilesTool(work_dir)
result = list_tool.run({"path": str(work_dir)})
print(result)

print("\n" + "=" * 80)
print("测试 TreeFilesTool（应该自动忽略 node_modules、__pycache__ 等）")
print("=" * 80)
tree_tool = TreeFilesTool(work_dir)
result = tree_tool.run({"path": str(work_dir), "max_depth": 3})
print(result)

print("\n" + "=" * 80)
print("测试 ListFilesTool（列出 tools 目录）")
print("=" * 80)
result = list_tool.run({"path": str(work_dir / "tools")})
print(result)

print("\n" + "=" * 80)
print("测试 TreeFilesTool（显示 tools 目录树，深度 2）")
print("=" * 80)
result = tree_tool.run({"path": str(work_dir / "tools"), "max_depth": 2})
print(result)