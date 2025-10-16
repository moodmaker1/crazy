# 📊 마케팅 전략 생성 API

클러스터 기반 가맹점 맞춤 마케팅 전략 생성 모듈

---

## 🚀 사용 방법

### 1. 모듈 import

```python
from report_generator2 import generate_marketing_report2
```

### 2. 함수 호출

```python
# 가맹점 코드만 넘겨주면 됩니다
result = generate_marketing_report2("00BC189C4B")
```

### 3. 결과 확인

```python
print(result['store_name'])      # 가맹점명
print(result['market_type'])     # 상권 유형
print(result['strategies'])      # 추천 전략 리스트
```

---

## 📥 입력 (Input)

| 파라미터 | 타입 | 설명 |
|---------|------|------|
| `store_code` | str | 가맹점 코드 (예: "00BC189C4B") |

---

## 📤 출력 (Output)

### 반환 타입
- `dict` (JSON 형태)

### 주요 필드

```json
{
  "store_code": "00BC189C4B",
  "store_name": "땅끝******",
  "market_type": "거주형",
  "revisit_rate": 17.19,
  "status": "개선 필요",
  "current_status": {
    "재방문율": "17.19%",
    "충성도": "4.69",
    "객단가": "1.00",
    "배달비율": "0.00%",
    "운영개월": 264
  },
  "cluster_info": {
    "cluster_name": "거주형 장기 부진 매장",
    "cluster_description": "재방문율 매우 낮음 / ...",
    "cluster_size": 4727,
    "success_count": 254,
    "success_rate": "5.4%"
  },
  "benchmark": {
    "재방문율": 34.21,
    "객단가": 1.44,
    "배달비율": 1.45,
    "충성도": -11.21
  },
  "gaps": {
    "배달비율": {
      "current": 0.0,
      "benchmark": 1.45,
      "gap": 1.45
    },
    "객단가": {...},
    "충성도": {...}
  },
  "gap_summary": "주요 개선 필요: 객단가 0.44 부족, 충성도 11.7점 초과",
  "strategies": [
    {
      "priority": "높음",
      "category": "배달 서비스",
      "action": "배달 서비스 도입 또는 확대",
      "detail": "성공 사례는 배달비율이 평균 36.6%입니다...",
      "tactics": [
        "배달 플랫폼 입점",
        "배달 전용 메뉴 개발",
        "포장 품질 개선",
        "배달비 프로모션"
      ],
      "expected_impact": "재방문율 3-5%p 향상 및 매출 증대"
    }
  ],
  "strategy_count": 3
}
```

### 에러 응답

```json
{
  "error": "가맹점 코드 'XXXXX'를 찾을 수 없습니다."
}
```

---

## 💡 사용 예제

### 예제 1: 기본 사용

```python
from report_generator2 import generate_marketing_report2

result = generate_marketing_report2("00BC189C4B")

if 'error' in result:
    print(f"오류: {result['error']}")
else:
    print(f"가맹점: {result['store_name']}")
    print(f"상권: {result['market_type']}")
    print(f"전략 개수: {result['strategy_count']}")
```

### 예제 2: JSON으로 변환

```python
import json
from report_generator2 import generate_marketing_report2

result = generate_marketing_report2("00BC189C4B")

# JSON 문자열로 변환
json_string = json.dumps(result, ensure_ascii=False, indent=2)
print(json_string)
```

### 예제 3: FastAPI 연동

```python
from fastapi import FastAPI, HTTPException
from report_generator2 import generate_marketing_report2

app = FastAPI()

@app.get("/marketing-strategy/{store_code}")
async def get_marketing_strategy(store_code: str):
    result = generate_marketing_report2(store_code)

    if 'error' in result:
        raise HTTPException(status_code=404, detail=result['error'])

    return result
```

### 예제 4: Flask 연동

```python
from flask import Flask, jsonify
from report_generator2 import generate_marketing_report2

app = Flask(__name__)

@app.route('/api/marketing-strategy/<store_code>')
def get_marketing_strategy(store_code):
    result = generate_marketing_report2(store_code)

    if 'error' in result:
        return jsonify(result), 404

    return jsonify(result)
```

---

## 📂 필요한 파일

모듈이 정상 작동하려면 같은 디렉토리에 다음 파일들이 필요합니다:

```
2_final_2/
├── report_generator2.py          # 메인 모듈
├── cluster_profiles.json         # 클러스터 프로파일
├── data_with_market_type.csv     # 전체 데이터
├── 거주형_clustered.csv           # 거주형 클러스터 데이터
├── 직장형_clustered.csv           # 직장형 클러스터 데이터
├── resident_kmeans.pkl           # 거주형 모델
├── resident_scaler.pkl           # 거주형 스케일러
├── resident_features.pkl         # 거주형 피처
├── office_kmeans.pkl             # 직장형 모델
├── office_scaler.pkl             # 직장형 스케일러
└── office_features.pkl           # 직장형 피처
```

---

## 🔍 주요 특징

1. **상권 유형별 분석**: 유동형, 거주형, 직장형 각각 다른 전략 제시
2. **클러스터 기반 벤치마킹**: 같은 클러스터 내 성공 사례와 비교
3. **맞춤형 전략**: 가게 상황에 따라 2-5개 전략 선별
4. **구체적인 실행 방안**: 각 전략마다 tactics 리스트 제공
5. **우선순위 표시**: 높음/보통으로 중요도 구분

---

## ⚠️ 주의사항

- 가맹점 코드가 존재하지 않으면 `{"error": "..."}` 반환
- 모듈 로딩 시 자동으로 모델과 데이터를 메모리에 로드 (최초 1회)
- 유동형 상권은 클러스터 분석 없이 벤치마크 기반 전략 제공
- 재방문율 30% 이상인 가게는 개선 전략 없이 "양호" 상태 반환

---

## 🛠️ 의존성

```txt
pandas
numpy
scikit-learn
joblib
```

---

## 📞 문의

문제가 발생하면 데이터 분석팀에 문의하세요.
