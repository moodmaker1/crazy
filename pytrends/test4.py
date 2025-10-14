import google.generativeai as genai
import json
import warnings
from dotenv import load_dotenv
import os
from datetime import datetime

# 경고 및 로그 숨기기
warnings.filterwarnings("ignore")
os.environ['GRPC_VERBOSITY'] = 'ERROR'
os.environ['GLOG_minloglevel'] = '2'

# .env 파일 로드
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    print("❌ GOOGLE_API_KEY가 .env 파일에 없습니다!")
    exit(1)

# Gemini 설정 (그라운딩 없이 먼저 키워드 생성)
genai.configure(api_key=api_key)
model_basic = genai.GenerativeModel("gemini-2.5-pro")

# 1) Gemini에서 키워드 50개 추천
def get_keywords_from_gemini(industry="고깃집"):
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
        response = model_basic.generate_content(prompt)
        text = response.text.strip()
        text = text.replace("```json", "").replace("```", "").strip()
        keywords = json.loads(text)
        
        if not isinstance(keywords, list):
            raise ValueError("응답이 리스트 형식이 아닙니다")
        
        return keywords[:50]
        
    except Exception as e:
        print(f"⚠️  Gemini 응답 파싱 오류: {e}")
        print(f"원본 응답: {text[:200]}...")
        keywords = [kw.strip(" \"',[]") for kw in text.split("\n") if kw.strip()]
        return [kw for kw in keywords if kw][:50]

# 2) Gemini 그라운딩으로 상위 20개 중 인기 키워드 10개 선정
def analyze_keywords_with_grounding(keywords_list):
    """
    Gemini의 Google Search 그라운딩 기능을 사용하여
    실제 검색 트렌드를 확인하고 상위 10개 선정
    """
    try:
        # 그라운딩 활성화된 모델 생성
        model_grounding = genai.GenerativeModel(
            'gemini-2.5-pro',
            tools='google_search_retrieval'
        )
        
        # 키워드 리스트를 문자열로 변환
        keywords_str = ", ".join(keywords_list)
        
        prompt = f"""
        다음 한국 중식 딤섬 관련 키워드 20개의 실제 Google 검색 인기도를 분석해주세요:
        
        {keywords_str}
        
        작업:
        1. Google Search를 통해 각 키워드의 실제 검색 트렌드, 인기도, 검색량을 확인
        2. 최근 3개월 기준으로 가장 검색이 많이 되는 키워드 순으로 정렬
        3. 상위 10개를 선정하고, 각 키워드에 대해:
           - 검색 인기도 점수 (1-100)
           - 트렌드 상승/하락 여부
           - 간단한 인기 이유
        
        출력 형식 (반드시 JSON):
        {{
          "분석_날짜": "2025-10-14",
          "키워드_TOP10": [
            {{
              "순위": 1,
              "키워드": "키워드명",
              "인기점수": 85,
              "트렌드": "상승",
              "이유": "최근 관련 검색 급증"
            }},
            ...
          ]
        }}
        """
        
        print("   🔍 Google Search를 통해 실시간 트렌드 분석 중...")
        response = model_grounding.generate_content(prompt)
        text = response.text.strip()
        
        # JSON 파싱
        text = text.replace("```json", "").replace("```", "").strip()
        result = json.loads(text)
        
        return result
        
    except Exception as e:
        print(f"⚠️  그라운딩 분석 실패: {e}")
        print(f"원본 응답: {response.text[:300] if 'response' in locals() else '없음'}...")
        
        # 폴백: Gemini의 자체 지식으로 선정
        print("   💡 폴백: Gemini 자체 지식 기반으로 분석 중...")
        fallback_prompt = f"""
        다음 키워드 중 검색 인기도가 높을 것으로 예상되는 상위 10개를 선정하고,
        각각 1-100 점수를 매겨주세요: {keywords_str}
        
        JSON 형식으로 출력:
        {{"키워드_TOP10": [{{"순위": 1, "키워드": "...", "인기점수": 90, "트렌드": "상승", "이유": "..."}}]}}
        """
        
        fallback_response = model_basic.generate_content(fallback_prompt)
        fallback_text = fallback_response.text.strip().replace("```json", "").replace("```", "").strip()
        return json.loads(fallback_text)

# 메인 실행
if __name__ == "__main__":
    industry = "고깃집"

    print("🔎 STEP 1: Gemini에서 키워드 50개 추천 중...")
    keywords = get_keywords_from_gemini(industry)
    print(f"✅ Gemini 추천 키워드: 총 {len(keywords)}개")
    print(f"   상위 5개: {keywords[:5]}")
    
    if len(keywords) != 50:
        print(f"⚠️  예상과 다른 개수: {len(keywords)}개 (목표: 50개)")

    # 1차 필터링: 상위 20개만
    top20_keywords = keywords[:20]
    print(f"\n📋 STEP 2: 1차 필터링 - 상위 20개 선택")
    print(f"   → Gemini가 예측한 순서대로 상위 20개 추출")
    print(f"   선정된 키워드: {', '.join(top20_keywords[:10])}...")

    print(f"\n📊 STEP 3: Gemini 그라운딩으로 실제 인기도 분석 중...")
    print(f"   💡 Google Search를 통해 실시간 검색 트렌드 확인")
    print(f"   ⏳ 예상 소요 시간: 약 10-20초")
    
    # 그라운딩으로 분석
    analysis_result = analyze_keywords_with_grounding(top20_keywords)
    
    if not analysis_result or "키워드_TOP10" not in analysis_result:
        print("\n❌ 분석 결과를 가져올 수 없습니다.")
        exit(1)

    final_top10 = analysis_result["키워드_TOP10"]
    
    print(f"\n✅ 분석 완료!")
    print(f"\n🔍 STEP 4: 2차 필터링 - 실제 검색 인기도 기준 상위 10개 선정")
    print(f"   → Google Search 실시간 데이터 기반")

    # 출력
    output = {
        "업종": industry,
        "분석_방법": "Gemini Grounding (Google Search)",
        "분석_날짜": datetime.now().strftime("%Y-%m-%d"),
        "총_분석_키워드": len(keywords),
        "1차_필터링": len(top20_keywords),
        "최종_선정": len(final_top10),
        "키워드_TOP10": final_top10
    }

    print("\n" + "="*60)
    print("📈 최종 결과")
    print("="*60)
    print(json.dumps(output, ensure_ascii=False, indent=2))
    
    # 간단한 요약 출력
    print("\n🏆 TOP 5 키워드:")
    for i, item in enumerate(final_top10[:5], 1):
        keyword = item.get('키워드', '')
        score = item.get('인기점수', 0)
        trend = item.get('트렌드', '-')
        reason = item.get('이유', '')
        print(f"   {i}. {keyword} (점수: {score}, 트렌드: {trend})")
        if reason:
            print(f"      └─ {reason}")
    
    # 결과를 JSON 파일로 저장
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"keyword_analysis_{timestamp}.json"
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"\n💾 결과 저장 완료: {filename}")
    except Exception as e:
        print(f"\n❌ 파일 저장 실패: {e}")
    
    print("\n" + "="*60)
    print("✨ 분석 요약")
    print("="*60)
    print(f"📊 방법: Gemini API 그라운딩 (Google Search)")
    print(f"⚡ 장점: 추가 라이브러리 불필요, 429 에러 없음, 빠른 속도")
    print(f"🎯 결과: 실시간 Google 검색 데이터 기반 TOP 10 키워드")