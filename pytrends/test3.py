import google.generativeai as genai
import json
import warnings
import time
from serpapi import GoogleSearch
from dotenv import load_dotenv
import os
from datetime import datetime

# 경고 및 로그 숨기기
warnings.filterwarnings("ignore")
os.environ['GRPC_VERBOSITY'] = 'ERROR'
os.environ['GLOG_minloglevel'] = '2'

# .env 파일 로드
load_dotenv()
google_api_key = os.getenv("GOOGLE_API_KEY")
serpapi_key = os.getenv("SERPAPI_KEY")

# API 키 확인
if not google_api_key:
    print("❌ GOOGLE_API_KEY가 .env 파일에 없습니다!")
    exit(1)
if not serpapi_key:
    print("❌ SERPAPI_KEY가 .env 파일에 없습니다!")
    exit(1)

# Gemini 설정
genai.configure(api_key=google_api_key)
model = genai.GenerativeModel("gemini-2.5-flash")

# 1) Gemini에서 키워드 50개 추천
def get_keywords_from_gemini(industry="중식 딤섬"):
    prompt = f"""
    업종: {industry}
    조건:
    - 최근 3개월 한국 {industry} 업계 트렌드를 반영
    - 브랜드명 제외
    - 신메뉴/재료/맛/운영컨셉 위주 키워드
    - 검색 인기도가 높을 가능성이 있는 순서대로 정확히 50개 나열
    - 각 키워드는 2-4단어 이내로 구체적이고 명확하게
    - 반드시 JSON 배열 형식으로만 출력: ["키워드1", "키워드2", ...]
    """
    
    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        
        # JSON 코드 블록 제거
        text = text.replace("```json", "").replace("```", "").strip()
        
        # JSON 파싱 시도
        keywords = json.loads(text)
        
        # 리스트인지 확인
        if not isinstance(keywords, list):
            raise ValueError("응답이 리스트 형식이 아닙니다")
        
        # 정확히 50개로 제한
        return keywords[:50]
        
    except Exception as e:
        print(f"⚠️  Gemini 응답 파싱 오류: {e}")
        print(f"원본 응답: {text[:200]}...")
        
        # 폴백: 줄바꿈으로 분리
        keywords = [kw.strip(" \"',[]") for kw in text.split("\n") if kw.strip()]
        return [kw for kw in keywords if kw][:50]

# 2) SerpAPI로 Google 자동완성 인기도 점수 계산
def get_popularity_score_serpapi(keyword, api_key):
    """
    SerpAPI를 통해 Google 자동완성에서 인기도 확인
    """
    try:
        params = {
            "engine": "google_autocomplete",
            "q": keyword,
            "gl": "kr",  # 한국
            "hl": "ko",  # 한국어
            "api_key": api_key
        }
        
        search = GoogleSearch(params)
        results = search.get_dict()
        
        # 자동완성 결과 가져오기
        suggestions = results.get("suggestions", [])
        
        if not suggestions or len(suggestions) == 0:
            return {"keyword": keyword, "인기점수": 0, "자동완성개수": 0, "샘플": []}
        
        # 자동완성 결과 개수 = 인기도 지표
        autocomplete_count = len(suggestions)
        
        # 키워드가 자동완성 결과에 포함되는지 확인
        keyword_appears = sum(1 for s in suggestions if keyword.lower() in s.get("value", "").lower())
        
        # 점수 계산: 자동완성 개수 + 포함 횟수 (×2 가중치)
        score = autocomplete_count + (keyword_appears * 2)
        
        # 샘플 데이터 추출
        sample = [s.get("value", "") for s in suggestions[:3]]
        
        return {
            "keyword": keyword,
            "인기점수": score,
            "자동완성개수": autocomplete_count,
            "샘플": sample
        }
        
    except Exception as e:
        print(f"⚠️  '{keyword}' 조회 실패: {str(e)[:70]}")
        return {"keyword": keyword, "인기점수": 0, "자동완성개수": 0, "샘플": []}

# 메인 실행
if __name__ == "__main__":
    industry = "중식 딤섬"

    print("🔎 Gemini에서 키워드 50개 추천 중...")
    keywords = get_keywords_from_gemini(industry)
    print(f"✅ Gemini 추천 키워드: 총 {len(keywords)}개")
    print(f"   상위 20개: {keywords[:20]}")
    
    # 정확히 50개가 아닐 경우 경고
    if len(keywords) != 50:
        print(f"⚠️  예상과 다른 개수: {len(keywords)}개 (목표: 50개)")

    # 1차 필터링: 상위 20개만
    top20_keywords = keywords[:20]
    print(f"\n📋 1차 필터링: 상위 20개 선택")
    print(f"   → Gemini가 검색 인기도 예측 기준으로 정렬한 순서대로 상위 20개 추출")

    print("\n📊 SerpAPI로 Google 자동완성 인기도 확인 중...")
    print(f"   ⚠️  예상 소요 시간: 약 30초 (무료 플랜: 월 100회 / 현재 사용: 20회)")
    results = []
    
    for idx, kw in enumerate(top20_keywords, 1):
        print(f"   [{idx}/20] {kw} 조회 중... ", end="")
        score_data = get_popularity_score_serpapi(kw, serpapi_key)
        
        if score_data["인기점수"] > 0:
            results.append(score_data)
            print(f"✓ (점수: {score_data['인기점수']}, 자동완성: {score_data['자동완성개수']}개)")
        else:
            results.append(score_data)
            print("✗ (자동완성 없음)")
        
        # API 호출 제한 방지 (SerpAPI는 제한이 느슨하지만 안전하게)
        if idx < len(top20_keywords):
            time.sleep(0.5)

    # 결과가 없을 경우 처리
    if not results:
        print("\n❌ 인기도 데이터를 가져올 수 없습니다.")
        exit(1)

    # 2차: 인기점수 기준 정렬 → 상위 15개만 선택
    final_top10 = sorted(results, key=lambda x: x["인기점수"], reverse=True)[:15]
    
    print(f"\n🔍 2차 필터링: 실제 인기도 기준 상위 10개 선택")
    print(f"   → Google 자동완성 점수 높은 순으로 정렬 (SerpAPI 사용)")

    # 출력
    output = {
        "업종": industry,
        "분석_방법": "SerpAPI - Google 자동완성",
        "총_분석_키워드": len(keywords),
        "인기도_확인": len(results),
        "최종_키워드_TOP10": final_top10
    }

    print("\n" + "="*60)
    print("📈 최종 결과")
    print("="*60)
    print(json.dumps(output, ensure_ascii=False, indent=2))
    
    # 간단한 요약 출력
    print("\n🏆 TOP 10 키워드:")
    for i, item in enumerate(final_top10[:10], 1):
        print(f"   {i}. {item['keyword']} - 인기점수 {item['인기점수']} (자동완성 {item['자동완성개수']}개)")
        if item['샘플']:
            print(f"      예시: {', '.join(item['샘플'][:2])}")
    
    # 결과를 JSON 파일로 저장
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"keyword_analysis_{timestamp}.json"
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"\n💾 결과 저장 완료: {filename}")
    except Exception as e:
        print(f"\n❌ 파일 저장 실패: {e}")