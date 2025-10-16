# analyzer/__init__.py
import os, sys

# 프로젝트 루트 기준으로 experiments 경로를 import 가능하게 추가
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXP_DIR = os.path.join(ROOT, "experiments")
if EXP_DIR not in sys.path:
    sys.path.insert(0, EXP_DIR)

from .report_generator import generate_marketing_report  # 외부에 노출할 유일 API
