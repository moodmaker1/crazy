"""
클러스터 기반 가맹점 맞춤 마케팅 전략 생성 모듈

사용 방법:
  from report_generator2 import generate_marketing_report2

  result = generate_marketing_report2('가맹점코드')
  # result는 dict 형태의 JSON 데이터
"""
import pandas as pd
import numpy as np
import joblib
import json
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
import os
import warnings

# sklearn 경고 무시
warnings.filterwarnings('ignore', category=UserWarning)

# 전역 변수: 학습된 모델 및 데이터
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 데이터 및 모델 로드
try:
    # 클러스터링된 데이터 로드
    DF_RESIDENT = pd.read_csv(os.path.join(BASE_DIR, '거주형_clustered.csv'))
    DF_OFFICE = pd.read_csv(os.path.join(BASE_DIR, '직장형_clustered.csv'))
    DF_ALL = pd.read_csv(os.path.join(BASE_DIR, 'data_with_market_type.csv'))

    # 클러스터링 모델 재학습 및 저장 (최초 1회)
    def train_and_save_models():
        """클러스터링 모델 학습 및 저장"""
        features = [
            '객단가비율',
            '배달매출비율',
            '재방문고객비율',
            '신규고객비율',
            '충성도점수',
            '운영개월수'
        ]

        # 거주형 모델
        resident_features = features + ['최근1개월_거주고객비율']
        df_r = DF_RESIDENT[resident_features].fillna(DF_RESIDENT[resident_features].mean())
        scaler_r = StandardScaler()
        X_r = scaler_r.fit_transform(df_r)

        kmeans_r = KMeans(n_clusters=4, random_state=42, n_init=20)
        kmeans_r.fit(X_r)

        joblib.dump(kmeans_r, os.path.join(BASE_DIR, 'resident_kmeans.pkl'))
        joblib.dump(scaler_r, os.path.join(BASE_DIR, 'resident_scaler.pkl'))
        joblib.dump(resident_features, os.path.join(BASE_DIR, 'resident_features.pkl'))

        # 직장형 모델
        office_features = features + ['최근1개월_직장고객비율']
        df_o = DF_OFFICE[office_features].fillna(DF_OFFICE[office_features].mean())
        scaler_o = StandardScaler()
        X_o = scaler_o.fit_transform(df_o)

        kmeans_o = KMeans(n_clusters=3, random_state=42, n_init=20)
        kmeans_o.fit(X_o)

        joblib.dump(kmeans_o, os.path.join(BASE_DIR, 'office_kmeans.pkl'))
        joblib.dump(scaler_o, os.path.join(BASE_DIR, 'office_scaler.pkl'))
        joblib.dump(office_features, os.path.join(BASE_DIR, 'office_features.pkl'))

    # 모델 파일이 없으면 학습
    if not os.path.exists(os.path.join(BASE_DIR, 'resident_kmeans.pkl')):
        train_and_save_models()

    # 모델 로드
    RESIDENT_KMEANS = joblib.load(os.path.join(BASE_DIR, 'resident_kmeans.pkl'))
    RESIDENT_SCALER = joblib.load(os.path.join(BASE_DIR, 'resident_scaler.pkl'))
    RESIDENT_FEATURES = joblib.load(os.path.join(BASE_DIR, 'resident_features.pkl'))

    OFFICE_KMEANS = joblib.load(os.path.join(BASE_DIR, 'office_kmeans.pkl'))
    OFFICE_SCALER = joblib.load(os.path.join(BASE_DIR, 'office_scaler.pkl'))
    OFFICE_FEATURES = joblib.load(os.path.join(BASE_DIR, 'office_features.pkl'))

    # 클러스터 프로파일 로드
    with open(os.path.join(BASE_DIR, 'cluster_profiles.json'), 'r', encoding='utf-8') as f:
        CLUSTER_PROFILES = json.load(f)

except Exception as e:
    DF_RESIDENT = DF_OFFICE = DF_ALL = None
    RESIDENT_KMEANS = RESIDENT_SCALER = RESIDENT_FEATURES = None
    OFFICE_KMEANS = OFFICE_SCALER = OFFICE_FEATURES = None
    CLUSTER_PROFILES = None
    raise RuntimeError(f"모델 초기화 실패: {e}")


def classify_market_type(row):
    """상권 유형 분류"""
    floating = row['최근1개월_유동고객비율']
    resident = row['최근1개월_거주고객비율']
    office = row['최근1개월_직장고객비율']

    if floating > 60:
        return '유동형'
    elif resident > 35:
        return '거주형'
    elif office > 20:
        return '직장형'
    else:
        return '혼합형'


def generate_marketing_report2(store_code: str):
    """
    가맹점 코드를 입력받아 클러스터 기반 맞춤 마케팅 전략 생성

    Parameters:
    -----------
    store_code : str
        가맹점 코드

    Returns:
    --------
    dict
        마케팅 전략 분석 결과 (JSON 형태)

    Examples:
    ---------
    >>> from report_generator2 import generate_marketing_report2
    >>> result = generate_marketing_report2("00BC189C4B")
    >>> print(result['store_name'])
    >>> print(result['strategies'])
    """
    if DF_ALL is None:
        return {"error": "데이터가 로드되지 않았습니다."}

    # 1. 가맹점 데이터 찾기
    store_data = DF_ALL[DF_ALL['가맹점코드'] == store_code]
    if len(store_data) == 0:
        return {"error": f"가맹점 코드 '{store_code}'를 찾을 수 없습니다."}

    # 최신 데이터 사용
    store = store_data.sort_values('분석기준일자', ascending=False).iloc[0]

    result = {
        "store_code": store_code,
        "store_name": store['가맹점명'],
        "current_status": {
            "재방문율": f"{store['재방문고객비율']:.2f}%",
            "충성도": f"{store['충성도점수']:.2f}",
            "객단가": f"{store['객단가비율']:.2f}",
            "배달비율": f"{store['배달매출비율']:.2f}%",
            "운영개월": int(store['운영개월수'])
        }
    }

    # 2. 상권 유형 판단
    market_type = classify_market_type(store)
    result["market_type"] = market_type

    # 3. 재방문율 체크
    revisit_rate = store['재방문고객비율']
    result["revisit_rate"] = float(revisit_rate)

    if revisit_rate >= 30:
        result["status"] = "양호"
        result["message"] = f"재방문율이 {revisit_rate:.2f}%로 양호합니다. 개선 전략이 필요하지 않습니다."
        return result

    result["status"] = "개선 필요"

    # 유동형은 별도 전략 생성
    if market_type == '유동형':
        result["message"] = "유동형 상권은 재방문율 대신 매출액, 회전율을 중심으로 평가해야 합니다."

        # 유동형 벤치마크 (상위 25% 평균)
        floating_data = DF_ALL[DF_ALL['상권유형'] == '유동형']
        top_25_floating = floating_data.nlargest(int(len(floating_data) * 0.25), '객단가비율')

        benchmark_floating = {
            "객단가": top_25_floating['객단가비율'].mean(),
            "배달비율": floating_data['배달매출비율'].mean(),
            "신규고객비율": floating_data['신규고객비율'].mean()
        }

        result["benchmark"] = {k: round(v, 2) for k, v in benchmark_floating.items()}

        # 유동형 전략 생성
        strategies = []

        # 1. 객단가 전략
        if store['객단가비율'] < 1.5:
            strategies.append({
                "priority": "높음",
                "category": "객단가 향상",
                "action": "세트 메뉴 구성 및 업셀링",
                "detail": f"현재 객단가 {store['객단가비율']:.2f}는 유동형 상위권 평균 {benchmark_floating['객단가']:.2f}보다 낮습니다. 세트 메뉴, 사이드 메뉴 추천으로 객단가를 높이세요.",
                "tactics": ["세트 메뉴 구성", "사이드 메뉴 추천", "프리미엄 메뉴 개발", "직원 업셀링 교육"],
                "expected_impact": "객단가 향상 → 동일 고객수 대비 매출 증대"
            })

        # 2. 배달 서비스 전략
        if store['배달매출비율'] < 20:
            strategies.append({
                "priority": "보통",
                "category": "배달 서비스",
                "action": "배달 채널 확대",
                "detail": f"현재 배달비율 {store['배달매출비율']:.1f}%입니다. 유동형 상권에서도 배달 서비스 확대로 추가 매출을 창출할 수 있습니다.",
                "tactics": ["배달 플랫폼 입점", "배달 전용 메뉴 개발", "포장 품질 개선", "배달비 프로모션"],
                "expected_impact": "신규 고객층 확보 및 비대면 매출 증대"
            })

        # 3. 신규 고객 유치 전략 (항상 포함)
        strategies.append({
            "priority": "높음",
            "category": "신규 고객 유치",
            "action": "가시성 및 마케팅 강화",
            "detail": "유동형 상권은 신규 고객 유입이 핵심입니다. 간판, SNS, 지역 광고를 통해 지속적인 신규 고객 유치가 필요합니다.",
            "tactics": ["간판/메뉴판 개선 (가시성 향상)", "SNS 마케팅 (인스타그램, 블로그)", "배달 플랫폼 프로모션", "지역 광고 (전단지, 현수막)"],
            "expected_impact": "신규 고객 유입 증가 → 매출 증대"
        })

        # 4. 운영 효율화 전략 (항상 포함)
        strategies.append({
            "priority": "높음",
            "category": "운영 효율화",
            "action": "회전율 및 고객 경험 개선",
            "detail": "유동형 상권은 빠른 회전율이 중요합니다. 대기 시간 단축과 주문 시스템 개선으로 더 많은 고객을 응대하세요.",
            "tactics": ["대기 시간 단축", "메뉴 단순화", "피크타임 인력 보강", "주문 시스템 개선"],
            "expected_impact": "회전율 증가 → 일 매출 증대"
        })

        # 5. 브랜드 인지도 전략 (운영 12개월 이상)
        if store['운영개월수'] > 12:
            strategies.append({
                "priority": "보통",
                "category": "브랜드 인지도",
                "action": "온라인 평판 관리",
                "detail": "유동형 상권에서는 온라인 리뷰와 평점이 신규 고객 유입에 큰 영향을 미칩니다.",
                "tactics": ["온라인 리뷰 관리", "지역 이벤트 참여", "미디어 노출", "인플루언서 협업"],
                "expected_impact": "브랜드 인지도 향상 → 신규 고객 증가"
            })

        result["strategies"] = strategies
        result["strategy_count"] = len(strategies)

        return result

    if market_type == '혼합형':
        result["message"] = "혼합형 상권은 별도 분석이 필요합니다."
        return result

    # 4. 클러스터 할당
    if market_type == '거주형':
        features = RESIDENT_FEATURES
        scaler = RESIDENT_SCALER
        kmeans = RESIDENT_KMEANS
        df_clustered = DF_RESIDENT
    elif market_type == '직장형':
        features = OFFICE_FEATURES
        scaler = OFFICE_SCALER
        kmeans = OFFICE_KMEANS
        df_clustered = DF_OFFICE
    else:
        result["message"] = "분석 대상이 아닌 상권 유형입니다."
        return result

    # 피처 추출 및 정규화
    store_features = store[features].values.reshape(1, -1)
    store_features = np.nan_to_num(store_features, nan=0)
    store_scaled = scaler.transform(store_features)

    # 클러스터 예측
    cluster_id = kmeans.predict(store_scaled)[0]
    result["cluster_id"] = int(cluster_id)

    # 5. 같은 클러스터의 성공 사례와 비교
    cluster_data = df_clustered[df_clustered['cluster'] == cluster_id]
    success_group = cluster_data[cluster_data['재방문고객비율'] >= 30]

    if len(success_group) < 10:
        result["message"] = "해당 클러스터에 충분한 성공 사례가 없습니다."
        return result

    # 클러스터 프로파일 정보 가져오기
    profile_key = "resident" if market_type == '거주형' else "office"
    cluster_profile = CLUSTER_PROFILES[profile_key][str(cluster_id)]

    result["cluster_info"] = {
        "cluster_id": int(cluster_id),
        "cluster_name": cluster_profile["name"],
        "cluster_description": cluster_profile["description"],
        "cluster_size": len(cluster_data),
        "success_count": len(success_group),
        "success_rate": f"{len(success_group) / len(cluster_data) * 100:.1f}%",
        "cluster_characteristics": cluster_profile["characteristics"]
    }

    # 벤치마크 (성공 그룹 평균)
    benchmark = {
        "재방문율": success_group['재방문고객비율'].mean(),
        "객단가": success_group['객단가비율'].mean(),
        "배달비율": success_group['배달매출비율'].mean(),
        "충성도": success_group['충성도점수'].mean(),
        "운영개월": success_group['운영개월수'].mean()
    }

    result["benchmark"] = {k: round(v, 2) for k, v in benchmark.items()}

    # 6. 차이점 분석 및 전략 도출 (거주형/직장형)
    gaps = {}
    strategies = []

    # 배달비율 차이
    delivery_gap = benchmark['배달비율'] - store['배달매출비율']
    gaps['배달비율'] = {
        "current": float(store['배달매출비율']),
        "benchmark": round(benchmark['배달비율'], 2),
        "gap": round(delivery_gap, 2)
    }

    # 객단가 차이
    price_gap = benchmark['객단가'] - store['객단가비율']
    gaps['객단가'] = {
        "current": float(store['객단가비율']),
        "benchmark": round(benchmark['객단가'], 2),
        "gap": round(price_gap, 2)
    }

    # 충성도 차이
    loyalty_gap = benchmark['충성도'] - store['충성도점수']
    gaps['충성도'] = {
        "current": float(store['충성도점수']),
        "benchmark": round(benchmark['충성도'], 2),
        "gap": round(loyalty_gap, 2)
    }

    result["gaps"] = gaps

    # 차이 분석 요약
    gap_summary = []
    if abs(delivery_gap) > 3:
        gap_summary.append(f"배달비율 {abs(delivery_gap):.1f}%p {'부족' if delivery_gap > 0 else '초과'}")
    if abs(price_gap) > 0.3:
        gap_summary.append(f"객단가 {abs(price_gap):.2f} {'부족' if price_gap > 0 else '초과'}")
    if abs(loyalty_gap) > 8:
        gap_summary.append(f"충성도 {abs(loyalty_gap):.1f}점 {'부족' if loyalty_gap > 0 else '초과'}")

    if len(gap_summary) > 0:
        result["gap_summary"] = "주요 개선 필요: " + ", ".join(gap_summary)
    else:
        result["gap_summary"] = "벤치마크와 큰 차이가 없습니다."

    # === 전략 1: 고객 충성도/재방문 전략 (최우선) ===
    if loyalty_gap > 10:
        strategies.append({
            "priority": "높음",
            "category": "고객 충성도/재방문",
            "action": "단골 고객 확보 프로그램",
            "detail": f"성공 사례는 충성도가 평균 {benchmark['충성도']:.1f}점입니다. 현재 {store['충성도점수']:.1f}점으로 단골 고객 확보가 필요합니다.",
            "tactics": ["포인트 적립 제도", "단골 우대 프로그램", "멤버십 혜택", "정기 이벤트"],
            "expected_impact": "재방문율 5-8%p 향상 예상"
        })

    # === 전략 2: 배달 서비스 전략 ===
    if delivery_gap > 5:
        strategies.append({
            "priority": "높음",
            "category": "배달 서비스",
            "action": "배달 서비스 도입 또는 확대",
            "detail": f"성공 사례는 배달비율이 평균 {benchmark['배달비율']:.1f}%입니다. 현재 {store['배달매출비율']:.1f}%에서 {delivery_gap:.1f}%p 증가 필요합니다.",
            "tactics": ["배달 플랫폼 입점", "배달 전용 메뉴 개발", "포장 품질 개선", "배달비 프로모션"],
            "expected_impact": "재방문율 3-5%p 향상 및 매출 증대"
        })

    # === 전략 3: 객단가 향상 전략 ===
    if price_gap > 0.5:
        strategies.append({
            "priority": "보통",
            "category": "객단가 향상",
            "action": "세트 메뉴 구성 및 업셀링",
            "detail": f"성공 사례는 객단가가 평균 {benchmark['객단가']:.2f}입니다. 현재 {store['객단가비율']:.2f}에서 {price_gap:.2f} 증가가 필요합니다.",
            "tactics": ["세트 메뉴 구성", "사이드 메뉴 추천", "프리미엄 메뉴 개발", "업셀링 교육"],
            "expected_impact": "수익성 개선 및 고객 만족도 향상"
        })

    # === 전략 4: 신규 고객 유치 전략 (신규 매장) ===
    if store['운영개월수'] < 24:  # 2년 미만 신규 매장
        strategies.append({
            "priority": "보통",
            "category": "신규 고객 유치",
            "action": "지역 인지도 확대",
            "detail": f"운영 {int(store['운영개월수'])}개월로 신규 매장입니다. 지역 주민에게 가게를 알리는 것이 우선입니다.",
            "tactics": ["간판/메뉴판 개선", "SNS 마케팅", "배달 플랫폼 프로모션", "지역 광고"],
            "expected_impact": "신규 고객 유입 증가 → 재방문 기회 확대"
        })

    # === 전략 5: 운영 효율화 전략 (직장형 특화) ===
    if market_type == '직장형':
        strategies.append({
            "priority": "보통",
            "category": "운영 효율화",
            "action": "점심 시간대 최적화",
            "detail": "직장형 상권은 점심 시간대 집중도가 높습니다. 빠른 서빙과 대기 시간 단축이 중요합니다.",
            "tactics": ["대기 시간 단축", "메뉴 단순화", "피크타임 인력 보강", "테이크아웃 편의성 강화"],
            "expected_impact": "회전율 증가 → 점심 매출 극대화"
        })

    # === 전략 6: 브랜드 인지도 전략 (장기 운영인데 재방문율 낮음) ===
    if store['운영개월수'] > 36 and store['재방문고객비율'] < 25:  # 3년 이상인데 재방문율 낮음
        strategies.append({
            "priority": "보통",
            "category": "브랜드 인지도",
            "action": "온라인 평판 관리 및 리브랜딩",
            "detail": f"운영 {int(store['운영개월수'])}개월이지만 재방문율이 {store['재방문고객비율']:.1f}%로 낮습니다. 온라인 평판과 이미지 개선이 필요합니다.",
            "tactics": ["온라인 리뷰 관리", "지역 이벤트 참여", "메뉴 개편", "인테리어 개선"],
            "expected_impact": "브랜드 이미지 개선 → 신규/재방문 고객 증가"
        })

    result["strategies"] = strategies
    result["strategy_count"] = len(strategies)

    # 전략이 없으면 일반 조언
    if len(strategies) == 0:
        result["strategies"].append({
            "priority": "보통",
            "category": "일반",
            "action": "기본 서비스 품질 개선",
            "detail": "벤치마크와 큰 차이가 없습니다. 맛, 청결도, 친절도 등 기본 서비스 품질 향상에 집중하세요.",
            "tactics": ["음식 품질 관리", "매장 청결 유지", "직원 친절 교육", "고객 피드백 수집"],
            "expected_impact": "고객 만족도 향상 → 재방문율 개선"
        })
        result["strategy_count"] = 1

    return result


# 테스트 코드
if __name__ == '__main__':
    # 테스트하고 싶은 가맹점 코드를 여기에 입력하세요
    test_codes = ['02FE4FD151']  # 예시: ['가맹점코드1', '가맹점코드2']

    # 또는 sys.argv로 커맨드라인에서 입력받기
    import sys
    if len(sys.argv) > 1:
        test_codes = sys.argv[1:]
        print(f"커맨드라인 입력: {test_codes}")

    print("="*80)
    print("🎯 클러스터 기반 전략 생성 테스트")
    print("="*80)

    for code in test_codes:
        print(f"\n\n{'='*80}")
        print(f"【가맹점 코드: {code}】")
        print("="*80)

        result = generate_marketing_report2(code)

        if 'error' in result:
            print(f"❌ 오류: {result['error']}")
            continue

        print(f"\n✅ 가맹점명: {result['store_name']}")
        print(f"✅ 상권 유형: {result['market_type']}")
        print(f"✅ 현재 상태:")
        for key, value in result['current_status'].items():
            print(f"    - {key}: {value}")

        if result['status'] == '양호':
            print(f"\n✅ {result['message']}")
            continue

        if 'cluster_info' in result:
            print(f"\n📊 클러스터 정보:")
            print(f"    - 클러스터: {result['cluster_info']['cluster_name']}")
            print(f"    - 특징: {result['cluster_info']['cluster_description']}")
            print(f"    - 클러스터 크기: {result['cluster_info']['cluster_size']}개")
            print(f"    - 성공 사례: {result['cluster_info']['success_count']}개 ({result['cluster_info']['success_rate']})")
            print(f"    - 클러스터 평균 특성:")
            for key, value in result['cluster_info']['cluster_characteristics'].items():
                print(f"        · {key}: {value}")

        if 'benchmark' in result:
            print(f"\n🎯 벤치마크 (성공 사례 평균):")
            for key, value in result['benchmark'].items():
                print(f"    - {key}: {value}")

        if 'gaps' in result:
            print(f"\n📉 차이 분석:")
            for key, gap_info in result['gaps'].items():
                print(f"    - {key}:")
                print(f"        현재: {gap_info['current']}")
                print(f"        벤치마크: {gap_info['benchmark']}")
                print(f"        차이: {gap_info['gap']:+.2f}")

        if 'gap_summary' in result:
            print(f"\n📌 {result['gap_summary']}")

        if 'strategies' in result and len(result['strategies']) > 0:
            print(f"\n💡 추천 전략 ({len(result['strategies'])}개):")
            for i, strategy in enumerate(result['strategies'], 1):
                print(f"\n    {i}. [{strategy['priority']}] {strategy['action']}")
                print(f"       카테고리: {strategy['category']}")
                print(f"       상세: {strategy['detail']}")
                if 'tactics' in strategy:
                    print(f"       실행 방안:")
                    for tactic in strategy['tactics']:
                        print(f"         · {tactic}")
                print(f"       기대 효과: {strategy['expected_impact']}")

    print(f"\n\n{'='*80}")
    print("🎉 테스트 완료")
    print("="*80)
