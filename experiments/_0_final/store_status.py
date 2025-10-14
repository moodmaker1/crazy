"""
매장 현황 조회 모듈
---------------------------------
가맹점 코드를 입력받아 total_data_final.csv에서 가장 최근 데이터를 조회하고,
사용자에게 의미있는 핵심 지표와 해석을 반환합니다.

사용 예시 (백엔드 개발자용):
---------------------------------
from experiments._0_final.store_status import get_store_status_with_insights

# 가맹점 코드로 조회 (해석 포함)
result = get_store_status_with_insights("00CEAAD71A")

if "error" in result:
    print(result['error'])
else:
    # 원본 데이터
    print(result['가맹점명'])
    print(result['최근1개월_매출액등급'])

    # 해석 데이터
    print(result['매출등급_해석'])  # "중간 매출 구간입니다. 보통 수준입니다."
    print(result['종합평가'])  # "⚠️ 보통 수준입니다. 개선이 필요한 부분이 있습니다."

# JSON으로 변환해서 API 응답으로 사용
import json
json_response = json.dumps(result, ensure_ascii=False)
"""

import os
import pandas as pd
from typing import Dict, Any


def get_total_data_path() -> str:
    """total_data_final.csv 경로 반환"""
    
    ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(ROOT, "experiments", "_3_final", "assets3", "total_data_final.csv")


def get_store_status(mct_id: str) -> Dict[str, Any]:
    """
    가맹점 코드로 매장의 최신 현황을 조회합니다.

    Args:
        mct_id: 가맹점 코드

    Returns:
        dict: 매장 현황 정보 (error 키가 있으면 에러 발생)
    """
    try:
        # CSV 파일 읽기
        csv_path = get_total_data_path()
        if not os.path.exists(csv_path):
            return {"error": f"데이터 파일을 찾을 수 없습니다: {csv_path}"}

        df = pd.read_csv(csv_path)

        # 가맹점 코드로 필터링
        store_data = df[df['가맹점코드'] == mct_id]

        if store_data.empty:
            return {"error": f"가맹점 코드 '{mct_id}'를 찾을 수 없습니다."}

        # 가장 최근 데이터 선택 (분석기준일자로 정렬)
        store_data = store_data.sort_values('분석기준일자', ascending=False).iloc[0]

        # 사용자에게 보여줄 핵심 지표만 선택
        status = {
            # 기본 정보
            "가맹점코드": store_data['가맹점코드'],
            "가맹점명": store_data['가맹점명'],
            "주소": store_data['가맹점기준면적(주소)'],
            "시군구": store_data['가맹점시군구명'],
            "업종분류": store_data['업종분류'],
            "상권": store_data['상권'],
            "분석기준일자": store_data['분석기준일자'],

            # 운영 정보
            "운영개월수": int(store_data['운영개월수']) if pd.notna(store_data['운영개월수']) else 0,
            "운영구간": int(store_data['운영개월구간(1~6)']) if pd.notna(store_data['운영개월구간(1~6)']) else 0,

            # 매출 및 고객 지표
            "최근1개월_매출액등급": int(store_data['최근1개월_매출액_등급(1~6)']) if pd.notna(store_data['최근1개월_매출액_등급(1~6)']) else 0,
            "재방문고객비율": round(float(store_data['재방문고객비율']), 2) if pd.notna(store_data['재방문고객비율']) else 0.0,
            "신규고객비율": round(float(store_data['신규고객비율']), 2) if pd.notna(store_data['신규고객비율']) else 0.0,
            "객단가비율": round(float(store_data['객단가비율']), 2) if pd.notna(store_data['객단가비율']) else 0.0,

            # 배달 정보
            "배달여부": bool(store_data['배달여부']) if pd.notna(store_data['배달여부']) else False,
            "배달매출비율": round(float(store_data['배달매출비율']), 2) if pd.notna(store_data['배달매출비율']) else 0.0,

            # 성장성 지표
            "업종매출증감률": round(float(store_data['최근12개월_업종매출증감률']), 2) if pd.notna(store_data['최근12개월_업종매출증감률']) else 0.0,
            "상권매출증감률": round(float(store_data['최근12개월_상권_매출증감률']), 2) if pd.notna(store_data['최근12개월_상권_매출증감률']) else 0.0,

            # 고객 거주지 분포
            "거주고객비율": round(float(store_data['최근1개월_거주고객비율']), 2) if pd.notna(store_data['최근1개월_거주고객비율']) else 0.0,
            "직장고객비율": round(float(store_data['최근1개월_직장고객비율']), 2) if pd.notna(store_data['최근1개월_직장고객비율']) else 0.0,
            "유동고객비율": round(float(store_data['최근1개월_유동고객비율']), 2) if pd.notna(store_data['최근1개월_유동고객비율']) else 0.0,
        }

        return status

    except Exception as e:
        return {"error": f"데이터 조회 중 오류 발생: {str(e)}"}


def get_store_status_with_insights(mct_id: str) -> Dict[str, Any]:
    """
    가맹점 코드로 매장 현황을 조회하고 사용자 친화적인 해석까지 한 번에 반환합니다.

    Args:
        mct_id: 가맹점 코드

    Returns:
        dict: 원본 데이터 + 해석 메시지 (error 키가 있으면 에러 발생)

    Example:
        result = get_store_status_with_insights("00CEAAD71A")
        print(result['종합평가'])  # "⚠️ 보통 수준입니다..."
        print(result['매출등급_해석'])  # "중간 매출 구간입니다..."
    """
    # 기본 데이터 조회
    status = get_store_status(mct_id)

    # 에러가 있으면 그대로 반환
    if "error" in status:
        return status

    # 해석 추가
    return get_user_friendly_status(status)


def get_user_friendly_status(status: Dict[str, Any]) -> Dict[str, Any]:
    """
    매장 현황을 사용자가 이해하기 쉬운 해석과 함께 반환합니다.

    Args:
        status: get_store_status()의 반환값

    Returns:
        dict: 원본 데이터 + 해석된 메시지
    """
    if "error" in status:
        return status

    friendly = status.copy()

    # 운영 기간 해석
    months = status['운영개월수']
    years = months // 12
    if years >= 10:
        friendly['운영기간_해석'] = f"약 {years}년 운영 중인 오래된 매장입니다. 안정적인 운영 노하우를 갖추고 있을 가능성이 높습니다."
    elif years >= 5:
        friendly['운영기간_해석'] = f"약 {years}년 운영 중인 안정적인 매장입니다."
    elif years >= 2:
        friendly['운영기간_해석'] = f"약 {years}년 운영 중입니다. 어느 정도 자리를 잡아가는 단계입니다."
    else:
        friendly['운영기간_해석'] = f"{months}개월 운영 중입니다. 초기 정착 단계입니다."

    # 매출 등급 해석 (1등급이 최고, 6등급이 최하)
    grade = status['최근1개월_매출액등급']
    if grade == 1:
        friendly['매출등급_해석'] = "최상위 매출 구간입니다! 매우 성공적으로 운영되고 있습니다."
    elif grade == 2:
        friendly['매출등급_해석'] = "상위 매출 구간입니다. 좋은 성과를 내고 있습니다."
    elif grade == 3:
        friendly['매출등급_해석'] = "중상위 매출 구간입니다. 양호한 편입니다."
    elif grade == 4:
        friendly['매출등급_해석'] = "중간 매출 구간입니다. 보통 수준입니다."
    elif grade == 5:
        friendly['매출등급_해석'] = "중하위 매출 구간입니다. 개선이 필요합니다."
    else:
        friendly['매출등급_해석'] = "하위 매출 구간입니다. 매출 증대 전략이 필요합니다."

    # 재방문율 해석
    revisit = status['재방문고객비율']
    if revisit >= 40:
        friendly['재방문율_해석'] = "재방문율이 매우 높습니다! 고객 충성도가 우수합니다."
    elif revisit >= 30:
        friendly['재방문율_해석'] = "재방문율이 높은 편입니다. 고객들이 만족하고 있습니다."
    elif revisit >= 20:
        friendly['재방문율_해석'] = "재방문율이 보통입니다."
    else:
        friendly['재방문율_해석'] = "재방문율이 낮은 편입니다. 고객 만족도 개선이 필요합니다."

    # 신규고객비율 해석
    new_customer = status['신규고객비율']
    if new_customer >= 15:
        friendly['신규고객_해석'] = "신규 고객 유입이 활발합니다. 성장 가능성이 높습니다."
    elif new_customer >= 10:
        friendly['신규고객_해석'] = "신규 고객 유입이 양호한 편입니다."
    elif new_customer >= 5:
        friendly['신규고객_해석'] = "신규 고객 유입이 보통입니다."
    else:
        friendly['신규고객_해석'] = "신규 고객 유입이 적습니다. 마케팅 강화가 필요합니다."

    # 배달 운영 해석
    if status['배달여부']:
        delivery_ratio = status['배달매출비율']
        if delivery_ratio >= 50:
            friendly['배달_해석'] = f"배달 운영 중입니다. 전체 매출의 {delivery_ratio:.0f}%를 배달이 차지합니다. 배달 의존도가 높습니다."
        elif delivery_ratio >= 30:
            friendly['배달_해석'] = f"배달 운영 중입니다. 전체 매출의 {delivery_ratio:.0f}%를 배달이 차지합니다. 배달이 중요한 수익원입니다."
        else:
            friendly['배달_해석'] = f"배달 운영 중입니다. 배달 매출 비중은 {delivery_ratio:.0f}%로 보조적입니다."
    else:
        friendly['배달_해석'] = "배달을 운영하지 않습니다. 매장 내 고객만 응대합니다."

    # 성장성 해석
    sales_growth = status['업종매출증감률']
    market_growth = status['상권매출증감률']

    if sales_growth > 0 and market_growth > 0:
        friendly['성장성_해석'] = f"업종과 상권 모두 성장 중입니다. (업종 {sales_growth:+.1f}%, 상권 {market_growth:+.1f}%) 좋은 환경입니다."
    elif sales_growth > 0:
        friendly['성장성_해석'] = f"업종은 성장 중이지만 ({sales_growth:+.1f}%), 상권은 감소세입니다 ({market_growth:+.1f}%)."
    elif market_growth > 0:
        friendly['성장성_해석'] = f"상권은 성장 중이지만 ({market_growth:+.1f}%), 업종은 감소세입니다 ({sales_growth:+.1f}%)."
    else:
        friendly['성장성_해석'] = f"업종과 상권 모두 감소세입니다. (업종 {sales_growth:+.1f}%, 상권 {market_growth:+.1f}%) 어려운 환경입니다."

    # 고객 거주지 분포 해석
    resident = status['거주고객비율']
    worker = status['직장고객비율']
    floating = status['유동고객비율']

    max_type = max([resident, worker, floating])
    if max_type == resident:
        friendly['고객분포_해석'] = f"거주 고객이 {resident:.0f}%로 가장 많습니다. 주거지역 상권의 특성을 보입니다."
    elif max_type == worker:
        friendly['고객분포_해석'] = f"직장 고객이 {worker:.0f}%로 가장 많습니다. 업무지역 상권의 특성을 보입니다."
    else:
        friendly['고객분포_해석'] = f"유동 고객이 {floating:.0f}%로 가장 많습니다. 유동인구가 많은 지역입니다."

    # 종합 평가
    score = 0
    if grade <= 2: score += 3
    elif grade <= 3: score += 2
    elif grade <= 4: score += 1

    if revisit >= 30: score += 2
    elif revisit >= 20: score += 1

    if new_customer >= 10: score += 1

    if sales_growth > 0 and market_growth > 0: score += 2
    elif sales_growth > 0 or market_growth > 0: score += 1

    if score >= 7:
        friendly['종합평가'] = "✅ 매우 우수한 매장입니다. 현재 운영 방식을 유지하세요."
    elif score >= 5:
        friendly['종합평가'] = "👍 양호한 매장입니다. 일부 개선점을 보완하면 더 좋습니다."
    elif score >= 3:
        friendly['종합평가'] = "⚠️ 보통 수준입니다. 개선이 필요한 부분이 있습니다."
    else:
        friendly['종합평가'] = "🔴 개선이 시급합니다. 전략적 변화가 필요합니다."

    return friendly


def format_status_for_display(status: Dict[str, Any]) -> str:
    """
    매장 현황을 사용자에게 보여주기 좋은 포맷으로 변환

    Args:
        status: get_store_status()의 반환값

    Returns:
        str: HTML 마크업 문자열
    """
    if "error" in status:
        return f"<div class='card' style='border-left:4px solid #f44336;'><p>{status['error']}</p></div>"

    배달상태 = "✅ 배달 중" if status['배달여부'] else "❌ 배달 없음"

    html = f"""
    <div class="card" style="background:#f8f9fa;border-left:4px solid #4CAF50;padding:1rem;margin-bottom:1rem;">
        <h4>🏪 {status['가맹점명']} ({status['가맹점코드']})</h4>
        <hr>

        <h5>📍 기본 정보</h5>
        <ul>
            <li><b>주소:</b> {status['주소']}</li>
            <li><b>시군구:</b> {status['시군구']}</li>
            <li><b>업종:</b> {status['업종분류']}</li>
            <li><b>상권:</b> {status['상권']}</li>
            <li><b>분석기준일:</b> {status['분석기준일자']}</li>
        </ul>

        <h5>📊 운영 현황</h5>
        <ul>
            <li><b>운영개월수:</b> {status['운영개월수']}개월 (구간 {status['운영구간']})</li>
            <li><b>최근1개월 매출등급:</b> {status['최근1개월_매출액등급']}등급 (1~6)</li>
        </ul>

        <h5>👥 고객 지표</h5>
        <ul>
            <li><b>재방문율:</b> {status['재방문고객비율']}%</li>
            <li><b>신규고객비율:</b> {status['신규고객비율']}%</li>
            <li><b>객단가비율:</b> {status['객단가비율']}</li>
        </ul>

        <h5>🚚 배달 정보</h5>
        <ul>
            <li><b>배달상태:</b> {배달상태}</li>
            <li><b>배달매출비율:</b> {status['배달매출비율']}%</li>
        </ul>

        <h5>📈 성장성</h5>
        <ul>
            <li><b>업종 매출증감률:</b> {status['업종매출증감률']}%</li>
            <li><b>상권 매출증감률:</b> {status['상권매출증감률']}%</li>
        </ul>

        <h5>🗺️ 고객 거주지 분포</h5>
        <ul>
            <li><b>거주고객:</b> {status['거주고객비율']}%</li>
            <li><b>직장고객:</b> {status['직장고객비율']}%</li>
            <li><b>유동고객:</b> {status['유동고객비율']}%</li>
        </ul>
    </div>
    """

    return html


if __name__ == "__main__":
    import sys

    # 커맨드라인 인자 확인
    if len(sys.argv) < 2:
        print("사용법: python store_status.py <가맹점코드>")
        print("예시: python store_status.py 00CEAAD71A")
        sys.exit(1)

    mct_id = sys.argv[1]
    print(f"가맹점 코드 '{mct_id}' 조회 중...\n")

    # 매장 현황 조회 (해석 포함)
    friendly = get_store_status_with_insights(mct_id)

    # 결과 출력
    if "error" in friendly:
        print(f"❌ 에러: {friendly['error']}")
    else:

        print("=" * 70)
        print(f"🏪 {friendly['가맹점명']} ({friendly['가맹점코드']})")
        print("=" * 70)

        print(f"\n📍 기본 정보")
        print(f"  주소: {friendly['주소']}")
        print(f"  시군구: {friendly['시군구']}")
        print(f"  업종: {friendly['업종분류']}")
        print(f"  상권: {friendly['상권']}")
        print(f"  분석기준일: {friendly['분석기준일자']}")

        print(f"\n📊 운영 현황")
        print(f"  운영: {friendly['운영개월수']}개월 (구간 {friendly['운영구간']})")
        print(f"  💬 {friendly['운영기간_해석']}")
        print(f"\n  매출등급: {friendly['최근1개월_매출액등급']}등급")
        print(f"  💬 {friendly['매출등급_해석']}")

        print(f"\n👥 고객 지표")
        print(f"  재방문율: {friendly['재방문고객비율']}%")
        print(f"  💬 {friendly['재방문율_해석']}")
        print(f"\n  신규고객: {friendly['신규고객비율']}%")
        print(f"  💬 {friendly['신규고객_해석']}")
        print(f"\n  객단가비율: {friendly['객단가비율']}")

        print(f"\n🚚 배달 정보")
        배달상태 = "✅ 운영 중" if friendly['배달여부'] else "❌ 미운영"
        print(f"  상태: {배달상태} (매출 비중: {friendly['배달매출비율']}%)")
        print(f"  💬 {friendly['배달_해석']}")

        print(f"\n📈 성장성")
        print(f"  업종 매출증감률: {friendly['업종매출증감률']:+.1f}%")
        print(f"  상권 매출증감률: {friendly['상권매출증감률']:+.1f}%")
        print(f"  💬 {friendly['성장성_해석']}")

        print(f"\n🗺️ 고객 거주지 분포")
        print(f"  거주: {friendly['거주고객비율']:.0f}% | 직장: {friendly['직장고객비율']:.0f}% | 유동: {friendly['유동고객비율']:.0f}%")
        print(f"  💬 {friendly['고객분포_해석']}")

        print(f"\n{'='*70}")
        print(f"📋 종합 평가")
        print(f"  {friendly['종합평가']}")
        print("=" * 70)
