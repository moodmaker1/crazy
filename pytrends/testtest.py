import google.generativeai as genai
import json
import warnings
import time
from pytrends.request import TrendReq
from dotenv import load_dotenv
import os

# 경고 숨기기
warnings.filterwarnings("ignore")

# .env 파일 로드
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

# Gemini 설정
genai.configure(api_key=api_key)
model = genai.GenerativeModel("gemini-2.5-flash")

# Pytrends 설정
pytrends = TrendReq(hl="ko", tz=540)

# 1) Gemini에서 키워드 50개 추천
def get_keywords_from_gemini(industry="카페"):
    prompt = f"""
    업종: {industry}
    조건:
    - 최근 3개월 한국 카페 업계 트렌드를 반영
    - 브랜드명(스타벅스, 메가커피 등) 제외
    - 신메뉴/재료/맛/운영컨셉 위주 키워드
    - 검색 인기도가 높을 가능성이 있는 순서대로 50개 나열
    - 출력은 JSON 배열만! (예: ["로제라떼","말차크림","콜드브루바닐라"])
    """
    response = model.generate_content(prompt)
    text = response.text.strip()
    text = text.replace("```json", "").replace("```", "")

    try:
        keywords = json.loads(text)
    except:
        keywords = [kw.strip("\" ,[]") for kw in text.split("\n") if kw.strip()]
    return keywords

# 2) Pytrends로 실제 검색량 확인
def get_trend_score(keyword, timeframe="today 3-m", geo="KR"):
    try:
        pytrends.build_payload([keyword], timeframe=timeframe, geo=geo)
        df = pytrends.interest_over_time()
        if df.empty:
            return None
        mean_val = round(df[keyword].mean(), 2)
        max_val = int(df[keyword].max())
        last_val = int(df[keyword].iloc[-1])
        return {"keyword": keyword, "평균(3개월)": mean_val, "최고치": max_val, "최근값": last_val}
    except Exception:
        return None

# 메인 실행
if __name__ == "__main__":
    industry = "카페"

    print("🔎 Gemini에서 키워드 50개 추천 중...")
    keywords = get_keywords_from_gemini(industry)
    print(f"Gemini 추천 키워드 (50개): {keywords[:50]} ... 총 {len(keywords)}개")

    # 1차 필터링: 상위 15개만
    top15_keywords = keywords[:15]

    print("📊 Pytrends에서 실제 검색량 확인 중...")
    results = []
    for kw in top15_keywords:
        score = get_trend_score(kw)
        if score:
            results.append(score)
        time.sleep(1.5)  # TooManyRequests 방지 (429 오류 방지)

    # 2차: 평균(3개월) 기준 정렬 → 상위 10개만 선택
    final_top10 = sorted(results, key=lambda x: x["평균(3개월)"], reverse=True)[:10]

    # 출력
    output = {
        "업종": industry,
        "최종_키워드_TOP10": final_top10
    }

    print(json.dumps(output, ensure_ascii=False, indent=2))
