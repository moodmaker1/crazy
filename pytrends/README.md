# 📊 업종별 키워드 트렌드 분석기

## 🚀 개요
이 프로젝트는 Gemini API와 Google Trends (pytrends)를 활용하여,
특정 업종(예: 카페)에 대한 실제 인기 키워드 TOP 10을 뽑아내는 프로그램입니다.

- Gemini → 업종 기반 최신 트렌드 키워드 후보 추천
- Pytrends → 실제 구글 검색 데이터를 기반으로 인기 검증
- 최종적으로 최근 3개월 기준 검색량 상위 10개 키워드를 출력

---

## 📂 프로젝트 구조
```
.
├── .env                # 환경 변수 (Gemini API Key 저장)
├── testtest.py         # 메인 실행 스크립트
├── requirements.txt    # 의존성 패키지
└── README.md           # 프로젝트 설명서
```

---

## 🔑 환경 변수 설정
1. 루트 폴더에 `.env` 파일 생성
2. 아래 내용을 입력
```
GOOGLE_API_KEY=your_api_key_here
```

---

## 📦 설치 방법

### 1. 가상환경 생성 및 실행
```bash
python -m venv venv
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate     # Windows
```

### 2. 필수 패키지 설치
```bash
pip install -r requirements.txt
```

```
google-generativeai
pytrends
python-dotenv
```

---

## ▶️ 실행 방법
```bash
python testtest.py
```

---

## ⚙️ 동작 방식
1. Gemini 단계
   - 업종을 입력하면 Gemini가 최근 3개월 한국 트렌드를 기반으로
     브랜드명을 제외한 50개 키워드 후보를 추천합니다.
   - 예: `"피스타치오라떼", "말차샷라떼", "소금빵", ...`

2. Pytrends 단계
   - 추천된 키워드 중 일부를 추려서(15개) Google Trends 검색량을 확인합니다.
   - 분석 지표:
     - `평균(3개월)` : 최근 3개월 평균 검색량
     - `최고치` : 3개월 중 최대 검색량
     - `최근값` : 가장 최근 시점 검색량

3. 최종 정리
   - 평균 검색량 기준으로 내림차순 정렬
   - TOP 10 키워드를 JSON으로 출력

---

## 📊 출력 예시
```json
{
  "업종": "카페",
  "최종_키워드_TOP10": [
    {
      "keyword": "소금빵",
      "평균(3개월)": 57.3,
      "최고치": 100,
      "최근값": 82
    },
    {
      "keyword": "피스타치오라떼",
      "평균(3개월)": 43.1,
      "최고치": 88,
      "최근값": 76
    }
  ]
}
```

---

## 🛠️ 주의사항
- 현재 시간이 너무 오래 걸리는 문제가 있음.
- `429 TooManyRequests` 오류가 발생할 수 있음 → 요청 간격(`time.sleep`) 조정 필요
- Gemini의 키워드 추천은 참고용이며, 최종 근거는 Google Trends 실제 검색량 데이터임
- 업종 이름(`industry`)을 바꿔 실행하면 다른 업종도 분석 가능

---

## 📌 활용 예시
- 카페 사장님 → 신메뉴 기획 시 최근 트렌드 파악
- 마케팅 담당자 → 광고 문구 & 해시태그 선정