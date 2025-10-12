import pandas as pd
import numpy as np
import joblib
import json
import os

# --- 1. 전역 변수: 모델 및 데이터 로딩 (서버 시작 시 1회 실행) ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, 'assets3') 

try:
    print("약점 진단 리포트 생성기(v3-Hybrid) 초기화 시작...")
    MODEL = joblib.load(os.path.join(ASSETS_DIR, 'weakness_model_improved.pkl'))
    SCALER = joblib.load(os.path.join(ASSETS_DIR, 'weakness_scaler.pkl'))
    FEATURE_NAMES = joblib.load(os.path.join(ASSETS_DIR, 'feature_names_improved.pkl'))
    WEAKNESS_NAMES = joblib.load(os.path.join(ASSETS_DIR, 'weakness_names.pkl'))
    
    # 시계열 분석을 위한 원본 데이터
    DF_TIMESERIES = pd.read_csv(os.path.join(ASSETS_DIR, 'total_data_final.csv'))
    # 상권 유형 조회를 위한 분석 데이터
    DF_ANALYSIS = pd.read_csv(os.path.join(ASSETS_DIR, '2.csv'))
    
    WEAKNESS_MAP = {
        "재방문율_심각도": {"name": "재방문율 저조", "solution": "충성 고객 확보를 위한 쿠폰/스탬프 제도 도입"},
        "신규고객_심각도": {"name": "신규고객 유입 부족", "solution": "신규 고객 타겟 배달앱 할인 또는 첫 방문 이벤트"},
        "객단가_심각도": {"name": "객단가 하락", "solution": "가치 상승을 위한 세트 메뉴 개발 또는 메뉴 고급화"},
        "충성도_심각도": {"name": "충성도 하락", "solution": "단골 고객 대상 특별 혜택 또는 재방문 감사 프로모션"},
        "매출변동성_심각도": {"name": "매출 변동성 심화", "solution": "안정적 매출 확보를 위한 점심 구독 서비스 또는 정기 이벤트 기획"},
        "이탈율_심각도": {"name": "고객 이탈 심화", "solution": "고객 피드백 채널 마련 및 서비스 만족도 개선 캠페인"},
        "경쟁력_심각도": {"name": "상권 내 경쟁 심화", "solution": "경쟁점과 차별화되는 우리 가게만의 시그니처 메뉴 개발"},
        "유동의존도_심각도": {"name": "유동고객 의존도 심화", "solution": "주변 거주/직장인 대상 로컬 마케팅 강화"},
        "배달효율_심각도": {"name": "배달 효율 저하", "solution": "배달 주문 전용 메뉴 개발 또는 최소주문금액 조정"},
        "고객편중_심각도": {"name": "특정고객 쏠림 심화", "solution": "새로운 고객층 유입을 위한 타겟 프로모션 (예: 1020세대 이벤트)"},
        "매출규모_심각도": {"name": "매출 규모 감소", "solution": "매출 증대를 위한 피크타임 세트 메뉴 출시 또는 배달 활성화"},
        "이용빈도_심각도": {"name": "고객 방문 빈도 감소", "solution": "재방문 유도를 위한 마일리지 제도 또는 요일별 이벤트"}
    }
    print("✔️ 약점 진단 리포트 생성기(v3-Hybrid) 초기화 완료!")

except Exception as e:
    print(f"!!! 초기화 오류: 필수 자산 파일을 'assets3' 폴더에서 찾을 수 없습니다. 오류: {e}")
    MODEL = None

# --- 2. 헬퍼 함수: 시계열 특징 생성 (기존과 동일) ---
def create_timeseries_features(df):
    store_df = df.sort_values('분석기준일자')
    if len(store_df) < 2: return None
    latest = store_df.iloc[-1]
    features = {'가맹점코드': latest['가맹점코드'], '가맹점명': latest['가맹점명']}
    # ... (이하 로직은 길어서 생략, 이전 코드와 동일합니다)
    for T in [3, 6]:
        if len(store_df) > T:
            past = store_df.iloc[-T-1]
            features[f'재방문율_{T}M변화'] = latest['재방문고객비율'] - past['재방문고객비율']
            features[f'신규고객율_{T}M변화'] = latest['신규고객비율'] - past['신규고객비율']
            features[f'충성도_{T}M변화'] = latest['충성도점수'] - past['충성도점수']
    if len(store_df) >= 3:
        last_3m = store_df.iloc[-3:]
        features.update({'재방문율_3M평균': last_3m['재방문고객비율'].mean(), '재방문율_3M변동': last_3m['재방문고객비율'].std(), '신규고객율_3M평균': last_3m['신규고객비율'].mean(), '매출등급_3M평균': last_3m['최근1개월_매출액_등급(1~6)'].mean()})
    features.update({'현재_거주고객비율': latest['최근1개월_거주고객비율'], '현재_직장고객비율': latest['최근1개월_직장고객비율'], '현재_유동고객비율': latest['최근1개월_유동고객비율'], '업종매출대비': latest['업종매출대비비율_정규화'], '업종건수대비': latest['업종건수대비비율_정규화'], '운영개월수': latest['운영개월수'], '현재_배달여부': latest['배달여부']})
    return pd.DataFrame([features])

# --- 3. 메인 함수 ---
def generate_marketing_report3(store_code: str):
    if MODEL is None: return {"error": "모듈이 정상적으로 초기화되지 않았습니다."}

    store_history_df = DF_TIMESERIES[DF_TIMESERIES['가맹점코드'] == store_code]
    if len(store_history_df) < 2: return {"error": f"'{store_code}'는 분석에 필요한 최소 2개월치 데이터가 없습니다."}
    
    latest_info = store_history_df.sort_values(by='분석기준일자', ascending=False).iloc[0]

    df_features = create_timeseries_features(store_history_df)
    if df_features is None: return {"error": "시계열 특징 생성에 실패했습니다."}
    
    X_raw = pd.concat([df_features.drop(['가맹점코드', '가맹점명'], axis=1), 
                       pd.get_dummies(latest_info[['업종분류', '상권']].to_frame().T)], axis=1)
    
    X_aligned = X_raw.reindex(columns=FEATURE_NAMES, fill_value=0)
    X_scaled = SCALER.transform(X_aligned)
    weakness_scores = MODEL.predict(X_scaled)[0]
    
    weakness_list = []
    for raw_name, score in zip(WEAKNESS_NAMES, weakness_scores):
        if raw_name in WEAKNESS_MAP:
            weakness_list.append({'약점_raw': raw_name, '약점': WEAKNESS_MAP[raw_name]['name'], '심각도': round(score * 100)})
    
    weakness_list.sort(key=lambda x: x['심각도'], reverse=True)
    
    # [최종 수정] 2.csv에서 상권 유형을 정확히 찾아 필터 적용
    try:
        market_type = DF_ANALYSIS[DF_ANALYSIS['가맹점코드'] == store_code].iloc[0]['분석_상권유형']
    except IndexError:
        market_type = "정보 없음"

    filtered_weakness_list = weakness_list
    filter_applied = False

    if market_type in ['유동밀집형', '유동중심형']:
        deprioritized = ["재방문율 저조", "충성도 하락", "유동고객 의존도 심화"]
        filtered_weakness_list = [w for w in weakness_list if w['약점'] not in deprioritized]
        filter_applied = True
    
    top_3_weaknesses = filtered_weakness_list[:3]
    
    diagnosis_top3_display = [{'약점': w['약점'], '심각도': w['심각도']} for w in top_3_weaknesses]
    recommendations = [WEAKNESS_MAP[w['약점_raw']]['solution'] for w in top_3_weaknesses]
    
    result = {
        "store_code": store_code, "store_name": latest_info['가맹점명'], "status": "진단 완료",
        "analysis": {
            "type": "시계열 기반 하이브리드 진단",
            "market_type_context": f"'{market_type}' 특성 반영됨 (필터 적용: {filter_applied})",
            "diagnosis_top3": diagnosis_top3_display
        },
        "recommendations": recommendations
    }
    return result

# --- 4. 개발자용 테스트 코드 ---
if __name__ == '__main__':
    test_store_code = '00803E9174'
    report = generate_marketing_report3(test_store_code)
    print(json.dumps(report, indent=4, ensure_ascii=False))