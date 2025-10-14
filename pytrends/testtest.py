import google.generativeai as genai
import json
import warnings
import os
from datetime import datetime
from dotenv import load_dotenv

# --- PyTrends 라이브러리 추가 ---
try:
    from pytrends.request import TrendReq
except ImportError:
    # PyTrends 설치가 안 되어 있을 경우를 대비한 안내
    print("❌ pytrends 라이브러리가 설치되지 않았습니다.")
    print("➡️ 다음 명령어를 실행하여 설치해주세요: pip install pytrends")
    exit(1)
# -------------------------------

# 경고 및 로그 숨기기 설정 (이전과 동일)
warnings.filterwarnings("ignore")
os.environ['GRPC_VERBOSITY'] = 'ERROR'
os.environ['GLOG_minloglevel'] = '2'

# .env 파일 로드
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    print("❌ GOOGLE_API_KEY가 .env 파일에 없습니다!")
    exit(1)

# Gemini 설정: Gemini 2.5 Flash 사용 요청에 따라 수정
genai.configure(api_key=api_key)
# 이제 키워드 생성 및 분석 모두 flash 모델 사용
MODEL_NAME = "gemini-2.5-flash"
model_basic = genai.GenerativeModel(MODEL_NAME)


# 1) Gemini에서 키워드 50개 추천 (트렌드 반영은 모델의 지식 기반)
def get_keywords_from_gemini(industry="고깃집"):
    """Gemini의 자체 지식을 기반으로 잠재적 인기 키워드 50개를 추천합니다."""
    prompt = f"""
    업종: {industry}
    조건:
    - 최근 3개월 한국 {industry} 업계 트렌드를 반영 (브랜드명 제외)
    - 신메뉴/재료/맛/운영컨셉 위주 키워드
    - 검색 인기도가 높을 가능성이 있는 순서대로 정확히 50개 나열
    - 각 키워드는 2-4단어 이내로 구체적이고 명확하게
    - 반드시 JSON 배열 형식으로만 출력: ["키워드1", "키워드2", ...]
    """
    
    try:
        # 응답이 길어지면 pro 모델이 더 안정적이지만, flash 사용 요청에 따름
        response = model_basic.generate_content(prompt)
        text = response.text.strip()
        text = text.replace("```json", "").replace("```", "").strip()
        keywords = json.loads(text)
        
        if not isinstance(keywords, list):
            raise ValueError("응답이 리스트 형식이 아닙니다")
        
        return keywords[:50]
        
    except Exception as e:
        print(f"⚠️  Gemini 응답 파싱 오류 발생: {e}")
        # 오류 발생 시 텍스트를 줄 단위로 분리하여 리스트로 복구 시도
        keywords = [kw.strip(" \"',[]") for kw in text.split("\n") if kw.strip()]
        return [kw for kw in keywords if kw][:50]


# 2) PyTrends를 사용하여 실제 실시간 인기 검색어 10개 가져오기
def get_realtime_trending_keywords(country_code='KR', max_keywords=10):
    """pytrends를 사용하여 한국의 실시간 인기 검색어(Trending Now)를 가져옵니다."""
    print("   🌐 PyTrends로 한국 실시간 인기 검색어 데이터 수집 중...")
    try:
        # hl: 언어 코드 (ko), tz: 표준 시간대 (360 = UTC+6, 한국은 UTC+9이지만 pytrends는 이 값을 선호하지 않음, 기본값 유지)
        pytrends = TrendReq(hl='ko-KR', tz=540) # tz=540 is UTC+9 (KST)
        
        # 'realtime_trending_searches' 메서드를 사용 (국가 코드: 'KR' 한국)
        df = pytrends.realtime_trending_searches(pn=country_code)
        
        if df.empty:
            print("   ⚠️ PyTrends에서 데이터를 가져오는 데 실패했거나 결과가 비어있습니다.")
            return []

        # 상위 N개의 키워드 추출
        trending_list = df['title'].head(max_keywords).tolist()
        return trending_list
        
    except Exception as e:
        print(f"❌ PyTrends 데이터 수집 실패: {e}")
        print("   ⚠️ PyTrends는 비공식 라이브러리이므로, 가끔 연결 오류가 발생할 수 있습니다.")
        return []


# 3) Gemini에게 최종 분석 및 이유 생성 요청
def finalize_analysis_with_gemini(realtime_keywords, industry):
    """실제 검색 데이터를 바탕으로 Gemini에게 분석 및 상세 이유 생성을 요청합니다."""
    
    keywords_str = "\n".join([f"- {kw}" for kw in realtime_keywords])
    
    prompt = f"""
    업종: {industry}
    다음은 현재 한국 Google에서 가장 인기 있는 실시간 인기 검색어(Trending Now) 목록입니다:

    {keywords_str}
    
    작업:
    1. 이 키워드들을 {industry}와 관련하여 분석합니다.
    2. 각 키워드에 대해 실제 검색 트렌드를 기반으로 다음 정보를 제공합니다:
        - 검색 인기도 점수 (1-100): Gemini가 인기도를 추론합니다.
        - 트렌드 상승/하락 여부: 실시간 트렌드는 보통 '상승' 또는 '급상승'을 의미합니다.
        - 간단한 인기 이유: 이 키워드가 갑자기 인기 있는 이유를 설명합니다.
    3. 목록은 순위 1위부터 10위까지 그대로 유지합니다.
    
    출력 형식 (반드시 JSON):
    {{
      "분석_방법": "PyTrends 실제 순위 + Gemini 추론",
      "분석_날짜": "{datetime.now().strftime('%Y-%m-%d')}",
      "업종": "{industry}",
      "키워드_TOP10": [
        {{
          "순위": 1,
          "키워드": "키워드명",
          "인기점수": 98,
          "트렌드": "급상승",
          "이유": "최근 유명 TV 프로그램에 소개되어 검색량 폭발"
        }},
        // ... (총 10개)
      ]
    }}
    """
    
    print("   🧠 Gemini에게 실제 트렌드 기반 분석 및 상세 이유 추론 요청 중...")
    try:
        # Gemini 2.5 Flash 모델 사용
        response = model_basic.generate_content(prompt)
        text = response.text.strip()
        
        # JSON 파싱
        text = text.replace("```json", "").replace("```", "").strip()
        result = json.loads(text)
        
        return result
    
    except Exception as e:
        print(f"❌ 최종 분석 실패: {e}")
        return None

# 메인 실행
if __name__ == "__main__":
    industry = "고깃집" # 이제 이 업종은 Gemini의 추론에만 사용

    print("============================================================")
    print("📈 한국 실시간 인기 키워드 분석 (PyTrends + Gemini)")
    print("============================================================")

    print("\n🔎 STEP 1: PyTrends로 한국 Google 실시간 트렌드 10개 수집")
    realtime_keywords = get_realtime_trending_keywords(country_code='KR', max_keywords=10)

    if not realtime_keywords:
        print("\n❌ PyTrends에서 실시간 트렌드를 가져올 수 없어 분석을 중단합니다.")
        # 만약 PyTrends가 실패하면, 기존 코드를 활용하여 Gemini 지식 기반으로 키워드를 생성하는 로직을 폴백으로 사용할 수 있습니다.
        print("💡 대안: Gemini 지식 기반 키워드 생성을 시도합니다.")
        print("🔎 STEP 1-A: Gemini에서 고깃집 키워드 50개 추천 중...")
        keywords_from_gemini = get_keywords_from_gemini(industry)
        if keywords_from_gemini:
             print(f"✅ Gemini 추천 키워드: 총 {len(keywords_from_gemini)}개")
             print(f"   상위 10개: {keywords_from_gemini[:10]}")
        else:
             print("❌ 폴백 키워드 생성도 실패했습니다.")
        exit(1)
    
    print(f"✅ 수집된 실시간 인기 검색어: 총 {len(realtime_keywords)}개")
    print(f"   → {', '.join(realtime_keywords)}")

    print(f"\n📊 STEP 2: Gemini ({MODEL_NAME})에게 트렌드 상세 분석 요청")
    print(f"   💡 모델의 추론 능력으로 '인기 이유'와 '점수'를 생성합니다.")
    
    # Gemini에게 분석 요청
    analysis_result = finalize_analysis_with_gemini(realtime_keywords, industry)
    
    if not analysis_result or "키워드_TOP10" not in analysis_result:
        print("\n❌ 최종 분석 결과를 가져올 수 없습니다.")
        exit(1)

    final_top10 = analysis_result["키워드_TOP10"]
    
    print(f"\n✅ 분석 완료!")
    print(f"\n🔍 STEP 3: 최종 결과 출력")

    # 출력
    output = {
        "업종": industry,
        "분석_방법": analysis_result.get("분석_방법", "PyTrends + Gemini 추론"),
        "분석_날짜": analysis_result.get("분석_날짜", datetime.now().strftime("%Y-%m-%d")),
        "총_수집_키워드": len(realtime_keywords),
        "최종_선정": len(final_top10),
        "키워드_TOP10": final_top10
    }

    print("\n" + "="*60)
    print("📈 최종 분석 결과 (PyTrends 실시간 데이터 기반)")
    print("="*60)
    print(json.dumps(output, ensure_ascii=False, indent=2))
    
    # 간단한 요약 출력
    print("\n🏆 TOP 5 실시간 인기 키워드:")
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
    filename = f"realtime_keyword_analysis_{timestamp}.json"
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"\n💾 결과 저장 완료: {filename}")
    except Exception as e:
        print(f"\n❌ 파일 저장 실패: {e}")
    
    print("\n" + "="*60)
    print("✨ 분석 요약")
    print("="*60)
    print(f"📊 방법: PyTrends로 실시간 데이터 수집 후 Gemini ({MODEL_NAME})로 분석")
    print(f"⚡ 장점: 실제 Google 트렌드 기반의 최신 인기 키워드 확보")
    print(f"🎯 결과: 현재 한국에서 가장 뜨거운 인기 키워드 TOP 10 상세 분석")
    print("============================================================")
