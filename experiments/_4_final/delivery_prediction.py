#!/usr/bin/env python3
"""
배달 도입 적합성 평가 시스템 (AI 리포트 + Import용 함수 포함)
- import 시: from experiments._4_final.delivery_prediction import predict_delivery
- CLI 실행 시: python delivery_prediction.py [가맹점코드]
"""

import pandas as pd
import numpy as np
import pickle
import sys
import os

# ============================================================================
# 📦 메인 클래스
# ============================================================================
class DeliveryPredictor:
    """배달 도입 적합성 평가 클래스"""

    def __init__(self):
        """모델 및 데이터 로드"""
        self.base_path = os.path.dirname(os.path.abspath(__file__))

        # 모델 로드
        with open(f'{self.base_path}/best_model.pkl', 'rb') as f:
            model_data = pickle.load(f)
            self.model = model_data['model']
            self.model_name = model_data['model_name']
            self.feature_columns = model_data['feature_columns']

        # 예측용 데이터
        with open(f'{self.base_path}/prediction_data.pkl', 'rb') as f:
            pred_data = pickle.load(f)
            self.X_pred = pred_data['X']
            self.pred_df = pred_data['pred_df']

        # 학습 데이터 통계
        with open(f'{self.base_path}/train_data.pkl', 'rb') as f:
            train_data = pickle.load(f)
            df = train_data['train_df']
            self.train_stats = {
                'success': df[df['그룹'] == 'success'],
                'failure': df[df['그룹'] == 'failure'],
            }

    # ----------------------------------------------------------------------
    def predict(self, store_code):
        """가맹점 코드로 배달 도입 적합성 평가"""
        store_idx = self.pred_df[self.pred_df['가맹점코드'] == store_code].index
        if len(store_idx) == 0:
            return None

        store_idx = store_idx[0]
        store_info = self.pred_df.loc[store_idx]

        # 모델 예측
        X_store = self.X_pred.loc[store_idx:store_idx]
        proba = self.model.predict_proba(X_store)[0]
        success_prob = proba[1] * 100
        display_prob = np.clip(success_prob * 8, 5, 95)

        # 근거 분석
        reasons = self._analyze_features(store_info)

        # 판단 구간
        if display_prob >= 60:
            level, emoji = "적합", "✅"
            summary = "배달 도입에 적합한 매장입니다. 운영 안정성과 고객 구조 모두 긍정적으로 평가됩니다."
            recommendation = "단계별 배달 채널 확장을 추천합니다. 리뷰 관리와 광고 효율화로 빠른 정착이 가능합니다."
        elif display_prob >= 30:
            level, emoji = "부분적 적합", "⚠️"
            summary = "배달 도입이 가능하지만, 일부 리스크 요인이 존재합니다. 상권 특성에 맞춘 시범 운영이 필요합니다."
            recommendation = "시범 도입(테스트 배달)을 통해 데이터 확보 후 확장 여부를 결정하세요. 오프라인 고객을 배달로 전환하는 마케팅이 효과적입니다."
        else:
            level, emoji = "비적합", "🚨"
            summary = "현재 구조에서는 배달 도입 시 효율이 낮을 가능성이 큽니다. 오프라인 리브랜딩이나 제품력 강화가 우선 필요합니다."
            recommendation = "배달보다는 기존 고객 재방문 유도와 매장 경험 개선에 집중하세요. 향후 상권 변화 시 재검토를 권장합니다."

        interpret_text = f"모델 기준 '{level}' ({display_prob:.1f}%)으로 평가되었습니다. 운영, 매출, 고객층 요인을 종합한 결과입니다."

        return {
            'store_code': store_code,
            'store_name': store_info['가맹점명'],
            'store_type': store_info['업종분류'],
            'area': store_info['상권'],
            'district': store_info['가맹점시군구명'],
            'success_prob': display_prob,
            'level': level,
            'emoji': emoji,
            'summary': summary,
            'recommendation': recommendation,
            'interpret_text': interpret_text,
            'reasons': reasons,
        }

    # ----------------------------------------------------------------------
    def _analyze_features(self, store_info):
        """요인별 적합성 분석"""
        reasons = []

        # ✅ 1. 운영 경험 (평균 ± 표준편차 기반)
        op_months = store_info['운영개월수']
        s = self.train_stats['success']['운영개월수']
        avg, std = s.mean(), s.std()
        if op_months < avg - 0.5 * std:
            reasons.append({
                'factor': '운영 경험',
                'value': f'{op_months:.0f}개월',
                'status': 'negative',
                'message': f'운영 기간이 성공 매장 평균({avg:.0f}개월)보다 부족합니다. 배달 운영 프로세스 정착에 시간이 필요합니다.',
            })
        elif op_months < avg:
            reasons.append({
                'factor': '운영 경험',
                'value': f'{op_months:.0f}개월',
                'status': 'neutral',
                'message': f'운영 기간이 평균({avg:.0f}개월)보다 다소 짧습니다. 테스트 도입으로 경험을 쌓는 것이 좋습니다.',
            })
        elif op_months <= avg + std:
            reasons.append({
                'factor': '운영 경험',
                'value': f'{op_months:.0f}개월',
                'status': 'positive',
                'message': f'성공 매장 평균({avg:.0f}개월)과 유사한 구간입니다. 안정적 운영 기반 위에서 확장이 가능합니다.',
            })
        else:
            reasons.append({
                'factor': '운영 경험',
                'value': f'{op_months:.0f}개월',
                'status': 'warning',
                'message': f'운영 기간이 매우 길어 기존 방식에 익숙합니다 (성공 매장 평균 {avg:.0f}개월). 변화 대응 속도가 느릴 수 있습니다.',
            })

        # ✅ 2. 매출 등급 (1등급이 높음, 6등급이 낮음)
        sales_grade = store_info['도입전_매출등급']
        s = self.train_stats['success']['도입전_매출등급']
        avg, std = s.mean(), s.std()
        if sales_grade <= 2:
            status, msg = ('positive', f'상위 매출 구간입니다 (성공 매장 평균 {avg:.1f}등급). 안정적인 기반에서 배달 확장이 가능합니다.')
        elif 3 <= sales_grade <= 4:
            status, msg = ('neutral', f'중간 수준의 매출입니다 (성공 매장 평균 {avg:.1f}등급). 배달을 통한 성장 여력이 있습니다.')
        else:
            status, msg = ('warning', f'하위 매출 구간입니다 (성공 매장 평균 {avg:.1f}등급). 배달보다는 메뉴/브랜딩 개선이 우선입니다.')
        reasons.append({'factor': '매출 등급', 'value': f'{sales_grade:.1f}등급', 'status': status, 'message': msg})

        # ✅ 3. 젊은 고객층 비율 (평균 ± 표준편차)
        young_ratio = store_info['남성_10_20대'] + store_info['여성_10_20대']
        s_m = self.train_stats['success']['남성_10_20대']
        s_f = self.train_stats['success']['여성_10_20대']
        avg = (s_m.mean() + s_f.mean())
        std = (s_m.std() + s_f.std()) / 2
        if young_ratio >= avg + std:
            reasons.append({
                'factor': '젊은 고객층 비율',
                'value': f'{young_ratio:.1f}%',
                'status': 'positive',
                'message': f'젊은 고객층이 풍부한 지역입니다 (성공 매장 평균 {avg:.1f}%). 배달 플랫폼 반응이 빠릅니다.',
            })
        elif young_ratio >= avg - 0.5 * std:
            reasons.append({
                'factor': '젊은 고객층 비율',
                'value': f'{young_ratio:.1f}%',
                'status': 'neutral',
                'message': f'젊은 고객층이 평균 수준입니다 (성공 매장 평균 {avg:.1f}%). 30~40대 중심 홍보가 효과적입니다.',
            })
        else:
            reasons.append({
                'factor': '젊은 고객층 비율',
                'value': f'{young_ratio:.1f}%',
                'status': 'warning',
                'message': f'젊은 고객층 비중이 낮습니다 (성공 매장 평균 {avg:.1f}%). 오프라인 단골층 중심 전략이 유리합니다.',
            })

        # ✅ 4. 상권 구조 (혼합형/유동형/거주형 자동 해석)
        flow_ratio = store_info['도입전_유동고객비율']
        s = self.train_stats['success']['도입전_유동고객비율']
        avg, std = s.mean(), s.std()
        if flow_ratio < 30:
            area_type = "거주형"
            desc = "거주 고객 중심 상권으로, 반복 주문형 배달 전략에 유리합니다."
        elif flow_ratio < 60:
            area_type = "혼합형"
            desc = "유동과 단골 고객이 공존하는 상권입니다. 지역 기반 홍보와 유지 전략이 효과적입니다."
        else:
            area_type = "유동형"
            desc = "유동 고객 중심 상권으로, 즉시 소비형 트렌드에 적합하지만 재방문은 낮을 수 있습니다."

        if flow_ratio >= avg + std:
            status = 'warning'
            msg = f'유동 고객이 많습니다 (성공 매장 평균 {avg:.1f}%). {desc}'
        elif flow_ratio >= avg - 0.3 * std:
            status = 'neutral'
            msg = f'유동 고객 비중이 평균 수준입니다 (성공 매장 평균 {avg:.1f}%). {desc}'
        else:
            status = 'positive'
            msg = f'거주/직장 고객 중심 상권입니다 (유동 {flow_ratio:.1f}%). {desc}'
        reasons.append({'factor': f'상권 구조 ({area_type})', 'value': f'유동 {flow_ratio:.1f}%', 'status': status, 'message': msg})

        return reasons

    # ----------------------------------------------------------------------
    def print_prediction(self, result):
        """리포트 출력"""
        print("=" * 80)
        print("📦 배달 도입 적합성 진단 리포트")
        print("=" * 80)
        print(f"\n📍 가맹점 정보:")
        print(f"   • 코드: {result['store_code']}")
        print(f"   • 상호명: {result['store_name']}")
        print(f"   • 업종: {result['store_type']}")
        print(f"   • 위치: {result['district']} {result['area']}")
        print(f"\n📊 모델 평가:")
        print(f"   {result['emoji']} 적합성 등급: {result['level']} ({result['success_prob']:.1f}%)")
        print(f"      → {result['interpret_text']}")
        print(f"\n🧩 근거별 요인 분석:")
        icons = {'positive': '✅', 'neutral': '📊', 'warning': '⚠️', 'negative': '❌'}
        for r in result['reasons']:
            print(f"   {icons.get(r['status'], '📊')} {r['factor']}: {r['value']}")
            print(f"      → {r['message']}")
        print(f"\n💬 종합 진단:\n   {result['summary']}")
        print(f"\n💡 권장 전략:\n   {result['recommendation']}")
        print("\n" + "=" * 80)


# ============================================================================
# 🌐 외부 import용 함수
# ============================================================================
_predictor_instance = None

def predict_delivery(store_code: str, verbose: bool = False):
    """외부 모듈에서 호출 가능한 배달 적합성 평가 함수"""
    global _predictor_instance
    if _predictor_instance is None:
        _predictor_instance = DeliveryPredictor()

    result = _predictor_instance.predict(store_code)
    if verbose and result:
        _predictor_instance.print_prediction(result)
    return result


# ============================================================================
# 🧩 CLI 실행 모드 (테스트용)
# ============================================================================
if __name__ == "__main__":
    code = sys.argv[1] if len(sys.argv) > 1 else "8BA83008CB"
    res = predict_delivery(code, verbose=True)