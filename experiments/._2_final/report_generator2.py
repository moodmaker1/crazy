import pandas as pd
import joblib
import json
import os

# --- 1. 전역 변수: 모델 및 데이터 로딩 (서버 시작 시 1회 실행) ---
# 이 파일의 위치를 기준으로 'assets' 폴더 경로를 설정합니다.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, 'assets')

try:
    print("마케팅 리포트 생성기 초기화 시작...")
    MODELS = {
        "단골 중심 상권": joblib.load(os.path.join(ASSETS_DIR, 'loyalty_model.pkl')),
        "유동 중심 상권": joblib.load(os.path.join(ASSETS_DIR, 'traffic_model.pkl'))
    }
    MODEL_COLUMNS = {
        "단골 중심 상권": joblib.load(os.path.join(ASSETS_DIR, 'loyalty_model_columns.pkl')),
        "유동 중심 상권": joblib.load(os.path.join(ASSETS_DIR, 'traffic_model_columns.pkl'))
    }
    BENCHMARKS = json.load(open(os.path.join(ASSETS_DIR, 'benchmarks_by_industry.json'), 'r', encoding='utf-8'))
    DF = pd.read_csv(os.path.join(ASSETS_DIR, '2.csv'))
    
    STRATEGY_RULEBOOK = {
      "단골 중심 상권": {"운영개월수": "신뢰도 강조 마케팅", "최근1개월_거주고객비율": "지역 주민 타겟팅", "배달매출비율": "배달 채널 강화"},
      "유동 중심 상권": {"객단가비율": "가성비 프로모션", "최근1개월_유동고객비율": "시각적 유인 및 즉각 구매 유도", "최근1개월_거주고객비율": "숨은 단골 찾기"}
    }
    print("✔️ 마케팅 리포트 생성기 초기화 완료!")

except FileNotFoundError as e:
    print(f"!!! 초기화 오류: 필수 자산 파일('{e.filename}')을 찾을 수 없습니다. 'assets' 폴더 구조를 확인해주세요.")
    MODELS, MODEL_COLUMNS, BENCHMARKS, DF, STRATEGY_RULEBOOK = [None]*5


# --- 2. 메인 함수: 백엔드 개발자가 호출할 함수 (이름 수정됨) ---
def generate_marketing_report2(store_code: str):
    """
    가맹점 코드를 입력받아, 개인화된 마케팅 진단 및 추천 결과를 반환합니다.
    """
    if not all([MODELS, DF is not None]):
        return {"error": "모듈이 정상적으로 초기화되지 않았습니다. 자산 파일을 확인해주세요."}

    # 1. 데이터 조회 및 유효성 검사
    store_data = DF[DF['가맹점코드'] == store_code].sort_values(by='분석기준일자', ascending=False).iloc[0:1]
    if len(store_data) == 0:
        return {"error": f"'{store_code}'에 해당하는 가맹점 정보를 찾을 수 없습니다."}
    store_info = store_data.iloc[0]

    # 2. 분석 필요 조건 확인
    if store_info['재방문고객비율'] >= 30:
        return {
            "store_code": store_code,
            "store_name": store_info['가맹점명'],
            "status": "양호",
            "message": f"현재 재방문율({store_info['재방문고객비율']:.2f}%)이 30% 이상으로 성과가 양호합니다."
        }

    # 3. 상권 유형에 따른 분석 준비
    analysis_type = None
    if store_info['분석_상권유형'] in ['주거밀집형', '주거중심형', '직장중심형']: analysis_type = "단골 중심 상권"
    elif store_info['분석_상권유형'] in ['유동밀집형', '유동중심형']: analysis_type = "유동 중심 상권"
    
    if not analysis_type:
        return {"error": f"'{store_info['분석_상권유형']}'은 분석 대상 상권 유형이 아닙니다."}

    # 4. 업종별 벤치마크 선택 (Fallback 로직 포함)
    store_category = store_info['업종분류']
    benchmark = BENCHMARKS[analysis_type].get(store_category, BENCHMARKS[analysis_type]['_fallback'])
    benchmark_type = "업종별 맞춤" if store_category in BENCHMARKS[analysis_type] else "상권 그룹 평균(Fallback)"

    # 5. 개인화된 약점 진단
    selected_model = MODELS[analysis_type]
    columns = MODEL_COLUMNS[analysis_type]
    importances = pd.Series(selected_model.feature_importances_, index=columns).sort_values(ascending=False)
    
    weaknesses = []
    for feature in importances.head(5).index:
        if feature in benchmark:
            weakness_score = benchmark[feature] - store_info[feature]
            weaknesses.append({'feature': feature, 'store_value': store_info[feature], 'benchmark_value': benchmark[feature], 'gap': weakness_score})

    weaknesses.sort(key=lambda x: x['gap'], reverse=True)
    
    # 6. 최종 결과 포맷팅
    top_weaknesses = weaknesses[:2]
    recommendations = []
    for weakness in top_weaknesses:
        for key, value in STRATEGY_RULEBOOK[analysis_type].items():
            if key == weakness['feature']:
                if value not in recommendations:
                    recommendations.append(value)
    
    result = {
        "store_code": store_code,
        "store_name": store_info['가맹점명'],
        "status": "개선 필요",
        "analysis": {
            "type": f"{analysis_type} / {store_category}",
            "revisit_rate": f"{store_info['재방문고객비율']:.2f}%",
            "benchmark_type": benchmark_type,
            "diagnosis": [
                {
                    "factor": w['feature'],
                    "store_value": f"{w['store_value']:.2f}",
                    "benchmark_value": f"{w['benchmark_value']:.2f}",
                    "gap": f"{w['gap']:+.2f}"
                } for w in top_weaknesses
            ]
        },
        "recommendations": recommendations
    }
    return result

# --- 3. 개발자용 테스트 코드 ---
# --- 3. 개발자용 테스트 코드 ---
# if __name__ == '__main__':
#     test_store_code = '00BC189C4B'  # '땅끝******'
#     report = generate_marketing_report2(test_store_code)
#     import json
#     print(json.dumps(report, indent=4, ensure_ascii=False))
