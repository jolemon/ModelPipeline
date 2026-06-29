"""Entry point for python -m model_report."""
import sys
from pathlib import Path

# 将 monorepo 根目录加入路径（访问 shared/）
_root = Path(__file__).parent.parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from model_report.cli import main

main()
