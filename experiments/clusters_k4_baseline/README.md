# Clusters K=4 Baseline Guide

카페 업종 매장을 4개 군집으로 구분해 프로필과 리포트를 생성하는 실험입니다. 전처리-학습-평가 파이프라인이 모두 독립적으로 구성되어 있으며, timeseries_models 프로젝트와 결합하면 "현재 군집 + 향후 예측"을 동시에 활용할 수 있습니다.

---
## 1. 폴더 구조 요약
```
experiments/clusters_k4_baseline/
├── README.md                         # 이 문서
├── data/
│   ├── cafe_features_processed.csv   # 전처리 완료 데이터셋 (훈련용)
│   ├── cafe_features_model_input.csv # 모델 입력용 (컬럼 정렬/스케일 적용)
│   └── total/total_data_final.csv    # 원천 데이터 (전처리 입력)
├── outputs/
│   └── clusters_k4_YYYYMMDD_HHMMSS/  # 실행 시각별 결과 폴더
│       ├── cluster_result.csv        # 매장별 군집 ID + 주요 KPI
│       ├── cluster_profile_mean.csv  # 군집별 평균 KPI
│       ├── cluster_profile_std.csv   # 군집별 표준편차
│       ├── cluster_size.csv          # 군집별 매장 수
│       ├── saved_model.pkl           # 학습된 KMeans 모델stription
│       └── README.txt                # 실행 설정 및 지표 요약
├── scripts/
│   ├── build_datasets_from_total.py  # 원천 → 전처리 데이터 생성
│   ├── compare_models.py             # 클러스터 개수/모델 비교 (선택)
│   ├── train_clusters.py             # KMeans(k=4) 학습
│   └── generate_personal_reports.py  # 매장별 요약 리포트 생성
└── src/
    ├── config.py                     # 공용 설정 값
    ├── data_pipeline/total_dataset.py# 데이터 로딩 및 클리닝 함수
    ├── feature_engineering.py        # 도메인 KPI 전처리
    ├── preprocess.py                 # ColumnTransformer 파이프라인
    ├── split_data.py                 # train/val/test 분할 유틸
    ├── train_model.py                # Sklearn KMeans 트레이너
    └── evaluate.py                   # Silhouette 등 평가 함수
```
각 스크립트는 독립 실행이 가능하며, 변경 사항은 해당 README나 소스 주석을 참고하세요.

---
## 2. 선행 준비
1. Python 3.11 가상환경(.venv) 활성화.
2. 필수 패키지 설치:
   ```bash
   pip install pandas numpy scikit-learn matplotlib seaborn
   ```
3. `data/total/total_data_final.csv` 경로에 최신 원천 데이터 준비.
4. (선택) `config.py`에서 기본 컬럼 목록, 스케일러 설정을 점검.

---
## 3. 데이터셋 구축
원본 데이터를 전처리하고 학습용 CSV를 생성합니다.

```bash
python experiments/clusters_k4_baseline/scripts/build_datasets_from_total.py \
  --source data/total/total_data_final.csv \
  --store-meta real_raw/big_data_set1_f.csv \
  --processed-out experiments/clusters_k4_baseline/data/cafe_features_processed.csv \
  --model-input-out experiments/clusters_k4_baseline/data/cafe_features_model_input.csv
```
### 주요 처리 단계
- 항목명 정규화 및 카페 업종 필터링 (`data_pipeline/total_dataset.py`).
- 등급형 KPI를 중앙값 스케일(0.083~0.917)로 변환.
- RobustScaler, OneHotEncoder 등 사전 정의된 ColumnTransformer 적용(`preprocess.py`).
- 12개월 이상 관측이 있는 매장만 유지, 이상치 핸들링.

> timeseries_models에서 사용하는 `cafe_timeseries_panel.csv`도 동일한 원천을 공유하므로, 두 프로젝트를 함께 업데이트할 때 build 스크립트를 동일한 타이밍에 실행하세요.

---
## 4. 군집 모델 선택 (비필수)
여러 k값이나 모델(KMeans, GMM)을 비교하고 싶을 때 사용합니다.
```bash
python experiments/clusters_k4_baseline/scripts/compare_models.py \
  --dataset experiments/clusters_k4_baseline/data/cafe_features_processed.csv \
  --out-dir experiments/clusters_k4_baseline/outputs/model_selection
```
산출물: silhouette/Calinski-Harabasz 점수, elbow 그래프 등. 기본 설정에서 K=4 KMeans가 가장 안정적인 것으로 확인되었습니다.

---
## 5. K=4 모델 학습
```bash
python experiments/clusters_k4_baseline/scripts/train_clusters.py \
  --dataset experiments/clusters_k4_baseline/data/cafe_features_processed.csv
```
- 실행 시각 기준 폴더가 `outputs/clusters_k4_YYYYMMDD_HHMMSS/`로 생성됩니다.
- 핵심 파일:
  - `cluster_result.csv`: 매장 ID, 군집 ID, 주요 KPI
  - `cluster_profile_mean.csv` / `cluster_profile_std.csv`: 각 군집의 평균·표준편차 프로필
  - `saved_model.pkl`: 재사용 가능한 KMeans 객체 (joblib)
  - `cluster_size.csv`: 군집별 매장 수

군집 해석 예시(기본 결과 기준):
- Cluster0: 방문·매출 모두 중간 이상, 안정형
- Cluster1: 매출 대비 방문이 높은 활발형
- Cluster2: 성장형 (최근 증감률이 높음)
- Cluster3: 위험형 (방문 감소, 배달 의존도 높음)

> 실제 해석은 `cluster_profile_mean.csv`를 기반으로 최신 결과에 맞게 갱신하세요.

---
## 6. 개인 리포트 생성
```bash
python experiments/clusters_k4_baseline/scripts/generate_personal_reports.py \
  --cluster outputs/clusters_k4_YYYYMMDD_HHMMSS/cluster_result.csv \
  --features data/cafe_features_processed.csv \
  --output outputs/cluster_reports.csv
```
- 결과에는 매장별 군집 ID, 현재 KPI, 군집 평균 대비 차이가 포함됩니다.
- 챗봇 또는 영업 리포트에 바로 삽입할 수 있는 텍스트 포맷을 구성하기에 적합합니다.

---
## 7. timeseries_models와의 통합 활용
1. **결합 로직**
   - 군집 결과(`cluster_result.csv`)와 Prophet/SARIMA 예측(`outputs/prophet/sarima/*.csv`)을 `ENCODED_MCT` 기준으로 조인합니다.
   - 예시:
     ```python
     import pandas as pd
     clusters = pd.read_csv('experiments/clusters_k4_baseline/outputs/.../cluster_result.csv')
     metrics = pd.read_csv('experiments/timeseries_models/outputs/prophet/prophet_metrics.csv')
     merged = clusters.merge(metrics[['ENCODED_MCT','mae','mape']], on='ENCODED_MCT', how='left')
     ```
   - 통합 결과를 기반으로 "현재 군집 프로필 + 예측 정확도/트렌드"를 한 번에 제공할 수 있습니다.
2. **시각화/챗봇**
   - Streamlit 대시보드에서 군집 필터 → 예측 차트 순으로 보여주면 서비스 담당자가 빠르게 인사이트를 확보할 수 있습니다.
   - 챗봇 응답 템플릿: `cluster_profile_mean.csv`에서 강점을 요약하고, timeseries 예측에서 다음 달 전망 및 신뢰도(MAE)를 함께 노출하세요.
3. **운영 워크플로우 권장 사항**
   1. 새로운 데이터 수집 → `build_datasets_from_total.py` 실행
   2. 군집 모델 재훈련(`train_clusters.py`) 및 리포트 업데이트
   3. timeseries_models에서 예측 갱신 → 두 결과를 통합하여 리포트/챗봇/대시보드 업데이트

---
## 8. Troubleshooting
| 증상 | 원인/대응 |
| ---- | ---------- |
| 특정 스크립트에서 컬럼 KeyError 발생 | 원천 데이터 스키마 변경 여부 확인, `config.py`에 컬럼 맵을 업데이트하세요. |
| 전처리 후 매장 수가 급감 | 최소 월 수 필터나 이상치 제거 조건을 완화하세요 (`feature_engineering.py`). |
| KMeans 학습이 느리거나 수렴 경고 | `train_model.py`에서 `n_init`, `max_iter`를 조정하거나 PCA로 차원을 줄인 후 다시 시도하세요. |
| 개인 리포트에서 NaN | 원천 데이터에 결측이 남아 있는지 확인하고 `feature_engineering.py`의 imputation 로직을 보완하세요. |

---
## 9. 자주 쓰는 명령어 정리
```bash
# 전처리 + 데이터셋 생성
python scripts/build_datasets_from_total.py --source data/total/total_data_final.csv --store-meta real_raw/big_data_set1_f.csv \
  --processed-out data/cafe_features_processed.csv --model-input-out data/cafe_features_model_input.csv

# 군집 학습
python scripts/train_clusters.py --dataset data/cafe_features_processed.csv

# 개인 리포트 생성
python scripts/generate_personal_reports.py --cluster outputs/clusters_k4_*/cluster_result.csv \
  --features data/cafe_features_processed.csv --output outputs/cluster_reports.csv
```

---
## 10. 다음 단계 아이디어
- 클러스터 수(k)를 재검토하고 결과를 비교하는 실험(`compare_models.py`) 자동화.
- timeseries_models 예측과 결합한 Streamlit/챗봇 탭 구현.
- KPI 중요도 분석(SHAP 등)을 추가해 군집 프로필을 더 해석 가능하게 만들기.
- 앙상블 리포트: 군집 결과 + 예측 결과 + 최근 실적 변동을 하나의 PDF/슬라이드로 자동 생성하는 배치 스크립트 개발.

---
## 11. 체크리스트
1. 원천 데이터 업데이트 → build 스크립트 실행 → processed CSV 재생성.
2. `train_clusters.py` 실행 후 최신 결과 폴더 확인.
3. `cluster_result.csv`와 `cluster_reports.csv`를 timeseries_models 예측과 조인해 내부 리포트/챗봇에 반영.
4. 필요 시 compare_models로 k 값을 재평가하고 README에 변경 사항 기록.

추가 아이디어나 개선 사항이 생기면 이 README와 각 모듈의 주석을 함께 업데이트해 주세요.
