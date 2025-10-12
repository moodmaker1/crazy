# analyzer/utils.py
import pandas as pd

def df_row_as_dict(df: pd.DataFrame, idx) -> dict:
    row = df.loc[idx]
    if hasattr(row, "to_dict"):
        return row.to_dict()
    # Series → dict
    return dict(row)

def summarize_report(record: dict) -> dict:
    """
    리포트 dict에서 카드용 요약 필드 몇 개 뽑아보기(플레이스홀더).
    실제 모델 바꿀 때 이 함수만 커스터마이즈해도 됨.
    """
    out = {}
    # 가벼운 추론 규칙(예: cluster_id 기반 추천 문구)
    cluster = record.get("cluster", record.get("CLUSTER", record.get("cluster_id")))
    out["클러스터"] = cluster

    # 매출/객단가/재방문율 비슷한 컬럼을 유연하게 집계
    for key in ["sales_trend", "매출추세", "sales_index", "매출지수"]:
        if key in record:
            out["매출추세"] = record[key]
            break

    for key in ["main_age", "주요고객층", "dominant_age", "age_segment"]:
        if key in record:
            out["주요고객층"] = record[key]
            break

    # 기본 추천 문구(플레이스홀더)
    out.setdefault("추천전략", "SNS 프로모션 + 인근 오피스 타겟 쿠폰 이벤트")
    out.setdefault("예상효과", "재방문율 +10~15%")
    return out
