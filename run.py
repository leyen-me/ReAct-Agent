# -*- coding: utf-8 -*-
"""独立运行脚本"""

import sys
from pathlib import Path

# 将当前目录添加到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from main import main

if __name__ == "__main__":
    main()

