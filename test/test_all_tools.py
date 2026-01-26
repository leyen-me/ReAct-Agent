# -*- coding: utf-8 -*-
"""所有工具的综合测试"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from test.test_file_tools import (
    test_print_tree,
    test_list_files,
    test_search,
    test_open_file,
    test_read_file,
    test_write_file,
    test_diff,
    test_checksum,
)

from test.test_code_execution_tools import (
    test_code_interpreter,
    test_python,
    test_run,
    test_execute,
    test_exec,
)

from test.test_git_tools import (
    test_git_status,
    test_git_add,
    test_git_commit,
    test_git_log,
    test_git_branch,
    test_git_diff,
)

from test.test_system_tools import (
    test_shell,
    test_terminal,
    test_env,
    test_sleep,
)

from test.test_network_tools import (
    test_browse,
    test_search as test_network_search,
    test_download,
    test_upload,
)

from test.test_other_tools import (
    test_file_upload,
    test_file_download,
    test_dalle,
    test_zip,
    test_unzip,
)


def main():
    """运行所有测试"""
    print("=" * 80)
    print("所有工具综合测试")
    print("=" * 80)
    
    # 文件操作工具
    print("\n" + "=" * 80)
    print("文件操作工具测试")
    print("=" * 80)
    test_print_tree()
    test_list_files()
    test_search()
    test_open_file()
    test_read_file()
    test_write_file()
    test_diff()
    test_checksum()
    
    # 代码执行工具
    print("\n" + "=" * 80)
    print("代码执行工具测试")
    print("=" * 80)
    test_code_interpreter()
    test_python()
    test_run()
    test_execute()
    test_exec()
    
    # Git 操作工具
    print("\n" + "=" * 80)
    print("Git 操作工具测试")
    print("=" * 80)
    test_git_status()
    test_git_add()
    test_git_commit()
    test_git_log()
    test_git_branch()
    test_git_diff()
    
    # 系统命令工具
    print("\n" + "=" * 80)
    print("系统命令工具测试")
    print("=" * 80)
    test_shell()
    test_terminal()
    test_env()
    test_sleep()
    
    # 网络工具
    print("\n" + "=" * 80)
    print("网络工具测试")
    print("=" * 80)
    test_browse()
    test_network_search()
    test_download()
    test_upload()
    
    # 其他工具
    print("\n" + "=" * 80)
    print("其他工具测试")
    print("=" * 80)
    test_file_upload()
    test_file_download()
    test_dalle()
    test_zip()
    test_unzip()
    
    print("\n" + "=" * 80)
    print("所有测试完成！")
    print("=" * 80)


if __name__ == "__main__":
    main()
