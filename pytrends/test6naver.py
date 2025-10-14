import google.generativeai as genai
import json
import warnings
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta
import urllib.request

# 경고 및 로그 숨기기
warnings.filterwarnings("ignore")
os.environ['GRPC_VERBOSITY'] = 'ERROR'
os.environ['GLOG_minloglevel'] = '2'

# .env 파일 로드
load_dotenv()
google_api_key = os.getenv("GOOGLE_API_KEY")
naver_client_id = os.getenv("NAVER_CLIENT_ID")
naver_client_secret = os.getenv("NAVER_CLIENT_SECRET")

# API 키 확인
if not google_api_key:
    print("❌ GOOGLE_API_KEY가 .env 파일에 없습니다!")
    exit(1)
if not naver_client_id or not naver_client_secret:
    print("❌ 네이버 API 키가 .env 파일에 없습니다!")
    print("💡 네이버 개발자 센터에서 발급받으세요: https://developers.naver.com/apps/#/register")
    exit(1)

# Gemini 설정
genai.configure(api_key=google_api_key)
model = genai.GenerativeModel("gemini-2.5-flash")

# 1) Gemini에서 키워드 30개 추천
def get_keywords_from_gemini(industry="중식 딤섬"):
    prompt = f"""
    업종: {industry}
    조건:
    - 최근 3개월 한국 {industry} 업계 트렌드를 반영
    - 브랜드명 제외
    - 신메뉴/재료/맛/운영컨셉 위주 키워드
    - 검색 인기도가 높을 가능성이 있는 순서대로 정확히 30개 나열
    - 각 키워드는 2-4단어 이내로 구체적이고 명확하게
    - 반드시 JSON 배열 형식으로만 출력: ["키워드1", "키워드2", ...]
    """
    
    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        text = text.replace("```json", "").replace("```", "").strip()
        keywords = json.loads(text)
        
        if not isinstance(keywords, list):
            raise ValueError("응답이 리스트 형식이 아닙니다")
        
        return keywords[:30]
        
    except Exception as e:
        print(f"⚠️  Gemini 응답 파싱 오류: {e}")
        print(f"원본 응답: {text[:200]}...")
        keywords = [kw.strip(" \"',[]") for kw in text.split("\n") if kw.strip()]
        return [kw for kw in keywords if kw][:30]

# 2) 네이버 Search Trend API로 검색량 확인
def get_naver_search_trend(keywords_list, client_id, client_secret):
    """
    네이버 Search Trend API로 최대 5개 키워드의 검색 트렌드 조회
    """
    try:
        # 최대 5개까지만 조회 가능
        keywords_batch = keywords_list[:5]
        
        # 날짜 설정 (최근 3개월)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=90)
        
        # API 요청 바디 (네이버 공식 예제 형식)
        body_dict = {
            "startDate": start_date.strftime("%Y-%m-%d"),
            "endDate": end_date.strftime("%Y-%m-%d"),
            "timeUnit": "month",
            "keywordGroups": [
                {"groupName": kw, "keywords": [kw]} 
                for kw in keywords_batch
            ]
        }
        body = json.dumps(body_dict)
        
        # API 호출 (urllib 방식)
        url = "https://openapi.naver.com/v1/datalab/search"
        request = urllib.request.Request(url)
        request.add_header("X-Naver-Client-Id", client_id)
        request.add_header("X-Naver-Client-Secret", client_secret)
        request.add_header("Content-Type", "application/json")
        
        response = urllib.request.urlopen(request, data=body.encode("utf-8"))
        rescode = response.getcode()
        
        if rescode == 200:
            response_body = response.read()
            data = json.loads(response_body.decode('utf-8'))
            results = []
            
            for item in data.get("results", []):
                keyword = item.get("title", "")
                ratios = [point["ratio"] for point in item.get("data", [])]
                
                if ratios:
                    avg_ratio = round(sum(ratios) / len(ratios), 2)
                    max_ratio = max(ratios)
                    last_ratio = ratios[-1]
                    
                    results.append({
                        "keyword": keyword,
                        "평균검색비율": avg_ratio,
                        "최고검색비율": max_ratio,
                        "최근검색비율": last_ratio
                    })
            
            return results
        else:
            print(f"⚠️  API 오류 (Error Code: {rescode})")
            return []
            
    except Exception as e:
        print(f"⚠️  네이버 API 호출 실패: {str(e)}")
        return []

# 메인 실행
if __name__ == "__main__":
    industry = "중식 딤섬"

    print("🔎 STEP 1: Gemini에서 키워드 30개 추천 중...")
    keywords = get_keywords_from_gemini(industry)
    print(f"✅ Gemini 추천 키워드: 총 {len(keywords)}개")
    print(f"   상위 10개: {', '.join(keywords[:10])}")
    
    if len(keywords) != 30:
        print(f"⚠️  예상과 다른 개수: {len(keywords)}개 (목표: 30개)")

    print(f"\n📊 STEP 2: 네이버 Search Trend로 실제 검색량 확인 중...")
    print(f"   💡 네이버 API는 최대 5개씩 조회 가능 (총 6번 요청)")
    print(f"   ⏳ 예상 소요 시간: 약 10-20초")
    
    all_results = []
    
    # 30개를 5개씩 6번 나눠서 조회
    batch_size = 5
    total_batches = (len(keywords) + batch_size - 1) // batch_size
    
    for batch_idx in range(total_batches):
        start_idx = batch_idx * batch_size
        end_idx = min(start_idx + batch_size, len(keywords))
        batch = keywords[start_idx:end_idx]
        
        print(f"\n   [배치 {batch_idx + 1}/{total_batches}] {len(batch)}개 키워드 조회 중...")
        print(f"   키워드: {', '.join(batch)}")
        
        batch_results = get_naver_search_trend(
            batch, 
            naver_client_id, 
            naver_client_secret
        )
        
        if batch_results:
            all_results.extend(batch_results)
            print(f"   ✓ 성공: {len(batch_results)}개 데이터 수집")
            for r in batch_results:
                print(f"      - {r['keyword']}: 평균 {r['평균검색비율']}")
        else:
            print(f"   ✗ 실패: 데이터 없음")
    
    # 결과 확인
    if not all_results:
        print("\n❌ 검색량 데이터를 가져올 수 없습니다.")
        print("💡 해결 방법:")
        print("   1. 네이버 API 키가 올바른지 확인")
        print("   2. 네이버 개발자센터에서 'DataLab(검색어 트렌드)' API 신청 확인")
        exit(1)

    print(f"\n✅ 총 {len(all_results)}개 키워드 데이터 수집 완료")

    # STEP 3: 평균 검색 비율 기준 정렬 → 상위 10개만 선택
    final_top10 = sorted(all_results, key=lambda x: x["평균검색비율"], reverse=True)[:10]
    
    print(f"\n🔍 STEP 3: 실제 검색량 기준 상위 10개 선택")
    print(f"   → 네이버 검색 트렌드 평균 비율 높은 순으로 정렬")

    # 출력
    output = {
        "업종": industry,
        "분석_기간": "최근 3개월",
        "분석_방법": "네이버 Search Trend API",
        "총_분석_키워드": len(keywords),
        "검색량_확인": len(all_results),
        "최종_키워드_TOP10": final_top10
    }

    print("\n" + "="*60)
    print("📈 최종 결과")
    print("="*60)
    print(json.dumps(output, ensure_ascii=False, indent=2))
    
    # 간단한 요약 출력
    print("\n🏆 TOP 10 키워드:")
    for i, item in enumerate(final_top10, 1):
        print(f"   {i}. {item['keyword']} - 평균 {item['평균검색비율']} (최고 {item['최고검색비율']})")
    
    # 결과를 JSON 파일로 저장
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"keyword_analysis_naver_{timestamp}.json"
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"\n💾 결과 저장 완료: {filename}")
    except Exception as e:
        print(f"\n❌ 파일 저장 실패: {e}")
    
    print("\n" + "="*60)
    print("✨ 분석 요약")
    print("="*60)
    print(f"📊 방법: 네이버 Search Trend API (공식)")
    print(f"⚡ 장점: 안정적, 429 에러 없음, 한국 시장 특화")
    print(f"🎯 결과: 네이버 실제 검색 데이터 기반 TOP 10 키워드")
    print(f"💡 업종 변경: 코드 맨 아래 'industry = \"중식 딤섬\"' 부분 수정")