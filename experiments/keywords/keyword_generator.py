"""
keyword_generator.py
--------------------
Gemini 2.5 Flash + Naver Search Trend API 기반 업종별 트렌드 키워드 분석 모듈
"""

import os
import json
import warnings
import urllib.request
from datetime import datetime, timedelta
from dotenv import load_dotenv
import google.generativeai as genai


# ------------------------------------------------
# 초기 설정
# ------------------------------------------------
warnings.filterwarnings("ignore")
os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["GLOG_minloglevel"] = "2"

# .env 로드
load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")

if not GOOGLE_API_KEY:
    raise EnvironmentError("❌ GOOGLE_API_KEY가 .env 파일에 없습니다.")
if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
    raise EnvironmentError("❌ 네이버 API 키가 누락되었습니다 (NAVER_CLIENT_ID / NAVER_CLIENT_SECRET).")

# Gemini 설정
genai.configure(api_key=GOOGLE_API_KEY)
GEMINI_MODEL = genai.GenerativeModel("gemini-2.5-flash")


# ------------------------------------------------
# 1️⃣ Gemini에서 키워드 추출
# ------------------------------------------------
def get_keywords_from_gemini(industry: str, limit: int = 30) -> list:
    """
    Gemini API를 사용해 업종 관련 트렌드 키워드를 추출합니다.
    Args:
        industry (str): 업종명 (예: '카페', '중식 딤섬')
        limit (int): 생성할 키워드 개수 (기본값: 30)
    Returns:
        list[str]: 키워드 리스트
    """
    prompt = f"""
    업종: {industry}
    조건:
    - 최근 3개월 한국 {industry} 업계 트렌드를 반영
    - 브랜드명 제외
    - 신메뉴/재료/맛/운영컨셉 위주 키워드
    - 검색 인기도가 높을 가능성이 있는 순서대로 정확히 {limit}개 나열
    - 각 키워드는 2~4단어로 구체적이고 명확하게
    - 반드시 JSON 배열 형식으로만 출력: ["키워드1", "키워드2", ...]
    """

    try:
        response = GEMINI_MODEL.generate_content(prompt)
        text = response.text.strip().replace("```json", "").replace("```", "").strip()
        keywords = json.loads(text)
        if not isinstance(keywords, list):
            raise ValueError("응답이 JSON 배열 형식이 아닙니다.")
        return keywords[:limit]
    except Exception as e:
        print(f"⚠️ Gemini 응답 파싱 오류: {e}")
        try:
            keywords = [kw.strip(" \"',[]") for kw in text.split("\n") if kw.strip()]
            return [kw for kw in keywords if kw][:limit]
        except Exception:
            return []


# ------------------------------------------------
# 2️⃣ 네이버 Search Trend API
# ------------------------------------------------
def get_naver_search_trend(keywords_list: list) -> list:
    """
    네이버 Search Trend API를 사용해 키워드별 검색 비율을 조회합니다.
    Args:
        keywords_list (list): 키워드 리스트
    Returns:
        list[dict]: 검색 비율 데이터
    """
    url = "https://openapi.naver.com/v1/datalab/search"
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)

    keyword_groups = [{"groupName": kw, "keywords": [kw]} for kw in keywords_list[:5]]
    body = json.dumps({
        "startDate": start_date.strftime("%Y-%m-%d"),
        "endDate": end_date.strftime("%Y-%m-%d"),
        "timeUnit": "month",
        "keywordGroups": keyword_groups,
    })

    try:
        req = urllib.request.Request(url)
        req.add_header("X-Naver-Client-Id", NAVER_CLIENT_ID)
        req.add_header("X-Naver-Client-Secret", NAVER_CLIENT_SECRET)
        req.add_header("Content-Type", "application/json")

        with urllib.request.urlopen(req, data=body.encode("utf-8")) as res:
            if res.getcode() != 200:
                print(f"⚠️ 네이버 API 오류: {res.getcode()}")
                return []

            data = json.loads(res.read().decode("utf-8"))
            results = []
            for item in data.get("results", []):
                keyword = item.get("title", "")
                ratios = [p["ratio"] for p in item.get("data", []) if "ratio" in p]
                if ratios:
                    results.append({
                        "keyword": keyword,
                        "평균검색비율": round(sum(ratios) / len(ratios), 2),
                        "최고검색비율": max(ratios),
                        "최근검색비율": ratios[-1],
                    })
            return results
    except Exception as e:
        print(f"⚠️ 네이버 API 호출 실패: {e}")
        return []


# ------------------------------------------------
# 3️⃣ 전체 트렌드 리포트 생성
# ------------------------------------------------
def generate_keyword_trend_report(industry: str) -> dict:
    """
    업종명 기반으로 Gemini + Naver Trend를 결합한 트렌드 리포트를 생성합니다.
    Returns:
        dict: 리포트 데이터
    """
    print(f"\n🔍 [KeywordGen] '{industry}' 업종 키워드 분석 시작...")
    keywords = get_keywords_from_gemini(industry)
    print(f"✅ Gemini 추천 키워드 {len(keywords)}개 수집")

    all_results = []
    batch_size = 5
    for i in range(0, len(keywords), batch_size):
        batch = keywords[i:i+batch_size]
        res = get_naver_search_trend(batch)
        all_results.extend(res)

    if not all_results:
        raise RuntimeError("❌ 네이버 트렌드 데이터를 가져오지 못했습니다.")

    top10 = sorted(all_results, key=lambda x: x["평균검색비율"], reverse=True)[:10]

    report = {
        "업종": industry,
        "분석_기간": "최근 3개월",
        "총_키워드": len(keywords),
        "총_트렌드데이터": len(all_results),
        "TOP10": top10,
        "생성일시": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    print(f"🏆 [KeywordGen] TOP10: {', '.join([r['keyword'] for r in top10])}")
    return report


# ------------------------------------------------
# 단독 실행 (테스트용)
# ------------------------------------------------
if __name__ == "__main__":
    industry = "카페"
    report = generate_keyword_trend_report(industry)
    print(json.dumps(report, ensure_ascii=False, indent=2))
