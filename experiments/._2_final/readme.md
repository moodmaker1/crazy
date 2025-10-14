네, 알겠습니다. 백엔드 개발자가 이해하기 쉽도록 `readme.md` 파일 형식으로 작성해 드리겠습니다. 이 내용을 그대로 복사하여 `readme.md` 파일에 저장하시면 됩니다.

-----

# AI 기반 가맹점별 맞춤 마케팅 전략 추천 모듈

## 1\. 개요 (Overview)

본 모듈은 가맹점 코드를 입력받아 해당 매장의 현재 상태를 데이터 기반으로 진단하고, 재방문율 상승을 위한 최적의 마케팅 전략을 자동으로 추천하는 AI 시스템입니다.

  - **입력:** 가맹점 코드 (문자열)
  - **판단 기준:** 재방문율 30% 미만인 매장을 '개선 필요'로 판단
  - **핵심 기능:**
    1.  상권 유형(단골 중심/유동 중심) 자동 판별
    2.  업종별 성공 사례(벤치마크)와 비교하여 개인화된 약점 진단
    3.  진단 결과에 따른 1, 2순위 마케팅 액션 아이템 추천
  - **출력:** 진단 및 추천 결과가 담긴 JSON 객체

## 2\. 필수 파일 구조 (Required File Structure)

프로젝트 내에 아래와 같은 파일 구조를 유지해야 합니다. `assets` 폴더의 위치나 내부 파일명이 변경되면 모듈이 작동하지 않습니다.

```
your_project/
├── ...
├── report_generator2.py   # ⬅️ (1) 메인 파이썬 모듈
└── assets/                  # ⬅️ (2) AI 모델 및 데이터 자산 폴더
    ├── 2.csv
    ├── benchmarks_by_industry.json
    ├── loyalty_model.pkl
    ├── loyalty_model_columns.pkl
    ├── traffic_model.pkl
    └── traffic_model_columns.pkl
```

  - **`report_generator2.py`**: 호출할 메인 함수가 들어있는 파일입니다.
  - **`assets` 폴더**: 모델, 원본 데이터, 벤치마크 등 모든 자산 파일이 들어있습니다.

## 3\. 설치 (Prerequisites)

모듈을 사용하기 위해 아래 라이브러리가 설치되어 있어야 합니다.

```bash
pip install pandas scikit-learn joblib
```

## 4\. 사용 방법 (How to Use)

`report_generator2` 모듈에서 `generate_marketing_report2` 함수를 import하여 \*\*가맹점 코드(문자열)\*\*만 인자로 넘겨주시면 됩니다.

```python
from report_generator2 import generate_marketing_report2

# 1. 분석하고 싶은 가맹점 코드를 변수에 담습니다.
store_code = "00BC189C4B" 

# 2. 함수를 호출하여 결과를 받습니다.
result = generate_marketing_report2(store_code)

# 3. 반환된 JSON(파이썬 딕셔너리) 결과를 활용합니다.
# 이 결과를 그대로 API 응답으로 사용하시거나 필요한 형태로 가공하여 사용하시면 됩니다.
import json
print(json.dumps(result, indent=4, ensure_ascii=False))
```

## 5\. 반환 값 상세 안내 (API Response Guide)

함수는 두 가지 경우의 JSON(딕셔너리)을 반환합니다.

### A) 마케팅 개선이 필요한 경우 (`status: "개선 필요"`)

재방문율이 30% 미만인 경우, 상세한 진단 정보와 추천 전략을 반환합니다.

```json
{
    "store_code": "00BC189C4B",
    "store_name": "땅끝******",
    "status": "개선 필요",
    "analysis": {
        "type": "단골 중심 상권 / 한식-해물/생선",
        "revisit_rate": "17.19%",
        "benchmark_type": "업종별 맞춤",
        "diagnosis": [
            {
                "factor": "배달매출비율",
                "store_value": "1.00",
                "benchmark_value": "15.50",
                "gap": "+14.50"
            },
            {
                "factor": "최근1개월_거주고객비율",
                "store_value": "28.00",
                "benchmark_value": "45.30",
                "gap": "+17.30"
            }
        ]
    },
    "recommendations": [
        "배달 채널 강화",
        "지역 주민 타겟팅"
    ]
}
```

  - **`diagnosis`**: 가장 시급하게 개선해야 할 요인 2개에 대한 상세 진단
      - `factor`: 약점 요인
      - `store_value`: 현재 매장의 수치
      - `benchmark_value`: 성공 그룹의 평균 수치
      - `gap`: 성공 그룹과의 격차 (이 값이 클수록 시급한 약점)
  - **`recommendations`**: 진단된 약점을 개선하기 위한 마케팅 전략 1, 2순위

### B) 성과가 양호한 경우 (`status: "양호"`)

재방문율이 30% 이상인 경우, 별도의 추천 없이 현재 상태 메시지를 반환합니다.

```json
{
    "store_code": "00DA1813DE",
    "store_name": "망고***",
    "status": "양호",
    "message": "현재 재방문율(33.66%)이 30% 이상으로 성과가 양호합니다."
}
```

## 6\. 모델 상세 정보 (Model Details)

  - **알고리즘:** 랜덤 포레스트 (Random Forest)
  - **접근 방식 (Two-Track):**
    1.  **`loyalty_model.pkl`**: '단골 중심 상권'(주거, 직장 등)의 **재방문율** 성공 요인을 학습한 모델.
    2.  **`traffic_model.pkl`**: '유동 중심 상권'(역세권 등)의 **매출** 성공 요인을 학습한 모델.
  - **개인화 방식 (Tiered-Benchmark):**
      - `benchmarks_by_industry.json` 파일을 사용하여, 각 매장을 **동일 상권 그룹 및 동일 업종**의 성공 사례 평균과 비교하여 상대적 약점을 정밀하게 진단합니다.
