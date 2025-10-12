# Timeseries Models 실험 안내

Prophet·SARIMA 등 시계열 모델을 실험하며 매장별 매출 등급(0.0~1.0 스케일)을 예측하기 위한 프로젝트입니다. 기존 클러스터링 파이프라인과 완전히 분리된 전처리/모델 실행 스크립트를 제공하며, 각 모델의 결과와 품질 지표를 한 폴더에서 관리하도록 구성했습니다.

---
## 1. 폴더 구조 개요
```
experiments/timeseries_models/
├── README.md                     # 이 문서
├── outputs/                      # 모든 결과물 저장소
│   ├── cafe_timeseries_panel.csv # 공통 패널 데이터
│   ├── prophet/                  # Prophet 결과 (forecast/metrics)
│   └── sarima/                   # SARIMA 결과 (forecast/metrics)
├── scripts/                      # 실행 스크립트 진입점
│   ├── build_timeseries_dataset.py
│   ├── run_prophet.py
│   ├── run_sarima.py
│   └── prophet_cli.py            # CLI 분석 도구
├── apps/
│   └── prophet_dashboard.py      # Streamlit 대시보드
└── models/                       # 모델별 세부 구현 및 TODO
    ├── prophet/
    ├── sarima/
    ├── panel_regression/         # 확장용 스켈레톤
    └── lstm/                     # 확장용 스켈레톤
```
각 모델 폴더에는 별도의 README와 TODO가 있으니 세부 구현 시 참고하세요.

---
## 2. 선행 준비
1. **가상환경 활성화**: `.venv` 또는 원하는 환경에서 Python 3.11 실행을 권장합니다.
2. **필수 패키지 설치**
   ```bash
   pip install pandas numpy matplotlib streamlit altair statsmodels prophet
   ```
   - `prophet` 설치는 PyStan 빌드 때문에 시간이 걸릴 수 있습니다.
   - SARIMA는 현재 statsmodels 기반으로만 동작합니다 (pmdarima 필요 없음).
3. **데이터 위치 확인**: 원본 CSV는 `data/total/total_data_final.csv`에 있어야 합니다.

---
## 3. 패널 데이터 생성 (build_timeseries_dataset.py)
단 한 번의 실행으로 모든 모델이 공통으로 사용하는 패널 CSV를 만듭니다.

```bash
python experiments/timeseries_models/scripts/build_timeseries_dataset.py
```

처리 흐름:
- 원본 총합 데이터에서 카페 업종만 필터링 (`filter_cafe_records`).
- 등급형 KPI를 0.083~0.917 사이의 중앙값 스케일로 변환 (`convert_grade_columns`).
- 날짜 컬럼을 `snapshot_date`로 정규화하고 월 단위 정렬.
- **품질 필터**
  - `drop_low_sales_grade`: 매출 등급이 0.05 미만으로 과도하게 낮은 달은 제거.
  - `remove_sales_outliers`: 매장별 IQR×3 바깥의 극단값 제거.
  - `filter_by_history`: 최소 `min_history`(기본 12개월) 이상 보유한 매장만 유지.
- 주요 KPI만 추려 `outputs/cafe_timeseries_panel.csv`에 저장.

생성된 CSV는 향후 모든 모델이 공통으로 사용합니다. 전처리 규칙을 수정할 때는 `src/preprocessing.py`를 업데이트하고 다시 스크립트를 실행하세요.

---
## 4. 실행 스크립트 공통 옵션
모든 모델 스크립트는 아래 인자를 공유합니다. 필요 시 커맨드라인에서 값만 조정하세요.

| 옵션 | 설명 | 기본값 |
| ---- | ---- | ------ |
| `--panel`      | 입력 패널 CSV 경로 | `outputs/cafe_timeseries_panel.csv` |
| `--out-dir`    | 결과 저장 디렉터리 | 모델별 폴더 (`outputs/prophet` 등) |
| `--min-history`| 학습에 필요한 최소 월 수. 부족한 매장은 스킵합니다. | 12 |
| `--horizon`    | 예측 개월 수 | 3 |
| `--eval-window`| 검증에 사용할 최근 개월 수. 해당 구간은 학습에서 제외 후 예측과 비교합니다. | 3 |

> **Tip**: 더 긴 기간으로 평가하고 싶다면 `--eval-window`를 6 또는 12로 조정하세요. 단, 데이터가 짧은 매장은 학습에서 제외될 수 있으니 `--min-history`를 함께 늘리는 것이 좋습니다.

---
## 5. Prophet 베이스라인
### 특징
- 로지스틱 성장(growth="logistic") + cap/floor(0.0~1.05)로 예측값 범위 제한.
- 연간 seasonality는 학습 데이터가 18개월 이상일 때만 자동 추가.
- 평가 지표: MAE, RMSE, MAPE (0 분모는 자동으로 제외).

### 실행
```bash
python experiments/timeseries_models/scripts/run_prophet.py \
  --panel experiments/timeseries_models/outputs/cafe_timeseries_panel.csv \
  --out-dir experiments/timeseries_models/outputs/prophet \
  --min-history 12 --horizon 3 --eval-window 3
```

### 출력
- `prophet_forecast.csv`: 매장 × 예측월에 대한 `yhat`, `yhat_lower`, `yhat_upper`.
- `prophet_metrics.csv`: 매장별 MAE/RMSE/MAPE, 학습 포인트 수, 평가 포인트 수.

Prophet은 PyStan을 사용하므로 실행 시간이 길 수 있습니다. 반복 실험 시 `--eval-window`를 키우거나 매장 subset으로 테스트하면 속도를 줄일 수 있습니다.

---
## 6. SARIMA (statsmodels 기반)
### 특징
- statsmodels `SARIMAX`를 사용하여 (p,d,q) 5종 × 계절 조합을 AIC 기준으로 탐색.
- 데이터가 짧을 때는 계절성 조합을 자동 축소.
- 모델 적합이 실패하면 마지막 값을 유지하는 naive 전략으로 fallback.
- Prophet과 동일하게 예측 범위 클리핑 및 평가 지표(MAE/RMSE/MAPE) 산출.

### 실행
```bash
python experiments/timeseries_models/scripts/run_sarima.py \
  --panel experiments/timeseries_models/outputs/cafe_timeseries_panel.csv \
  --out-dir experiments/timeseries_models/outputs/sarima \
  --min-history 12 --horizon 3 --eval-window 3
```

### 출력
- `sarima_forecast.csv`: 예측 평균과 95% 신뢰구간 (`yhat_lower`, `yhat_upper`).
- `sarima_metrics.csv`: 매장별 평가 지표 + 실제로 선택된 `(order, seasonal_order)` 정보(`model` 컬럼).

경고 메시지는 스크립트에서 대부분 억제했지만, 여전히 모델이 수렴하지 않는 매장은 fallback 전략이 적용될 수 있습니다.

---
## 7. 분석 도구
### 7.1 CLI 도구 (`prophet_cli.py`)
주요 기능:
- 아웃라이어 매장 조회: `--top-outliers N --outlier-threshold 0.15`
- 특정 매장 그래프 출력/저장: `--store-id <ENCODED_MCT> --save-dir plots`
- `--show` 옵션을 주면 GUI 환경에서 즉시 Plot 창을 띄웁니다 (로컬 개발 시 활용).

Prophet 결과를 기본값으로 읽지만, `--forecast`·`--metrics` 경로를 파라미터로 바꾸면 SARIMA 지표도 동일하게 살펴볼 수 있습니다.

### 7.2 Streamlit 대시보드 (`apps/prophet_dashboard.py`)
```bash
streamlit run experiments/timeseries_models/apps/prophet_dashboard.py
```
- 사이드바에서 MAE 임계값을 조절해 아웃라이어 필터링.
- 선택한 매장의 실제 vs 예측 추세를 Altair 차트로 표시.
- Top 10 아웃라이어 표를 제공하여 문제 매장을 빠르게 식별.
- 기본 경로는 README와 동일하며, 다른 데이터를 쓰고 싶으면 `st.secrets`에 경로를 오버라이드하세요.

---
## 8. 결과 파일 해석 가이드
| 컬럼 | 설명 |
| ---- | ---- |
| `ENCODED_MCT` | 매장 식별자 |
| `ds` | 예측 대상 월 (YYYY-MM-01) |
| `yhat` | 예측된 매출 등급 값 |
| `yhat_lower`, `yhat_upper` | Prophet/SARIMA가 제공하는 예측 구간 |
| `mae`, `rmse`, `mape` | 평가 지표 (검증 구간에서 계산) |
| `train_points` | 학습에 사용된 월 수 |
| `eval_points` | 검증에 사용된 월 수 (= `--eval-window`) |
| `model` | SARIMA에서 선택된 ARIMA 차수 정보 |

평균 MAE가 0.05 이하라면 0~1 스케일에서 상당히 정확한 편이며, MAPE는 등급 값이 0에 가까운 경우 급격히 커질 수 있으니 참고용으로만 사용하는 것이 좋습니다.

---
## 9. 이상치 및 튜닝 전략
1. **검증 창 조정**: `--eval-window`를 6 또는 12로 늘려 더 긴 기간의 안정성을 확인하세요.
2. **min-history 상향**: 평가 창을 늘리면 `--min-history`도 함께 증가시켜 학습 포인트를 확보합니다.
3. **전처리 미세 조정**: `src/preprocessing.py`의 `drop_low_sales_grade`, `remove_sales_outliers` 파라미터를 조절해 문제 매장을 줄일 수 있습니다.
4. **모델별 매장 제외**: `prophet_metrics.csv`나 `sarima_metrics.csv`에서 MAE가 큰 매장을 별도 레이블링하여 후속 모델(LSTM 등)에서 제외하거나 다른 파라미터로 재학습하세요.

---
## 10. Troubleshooting
| 증상 | 원인/대응 |
| ---- | -------- |
| Prophet 설치 실패 | Microsoft C++ Build Tools 필요. `pip install prophet` 실행 시 로그를 확인하고, PyStan 빌드 의존성 설치 후 재시도하세요. |
| Prophet 실행이 매우 느림 | PyStan 샘플링 특성. 실험 초기에는 매장 subset(예: 상위 50개)만 추려 돌리고, 파라미터 확정 후 전체 매장을 학습하세요. |
| SARIMA 경고가 계속 출력 | 스크립트에서 대부분 mute했지만, `statsmodels`의 수렴 경고가 남을 수 있습니다. 예측 결과가 NaN일 경우 fallback이 적용됐는지(`model` 컬럼) 확인하세요. |
| 평가 지표가 NaN | 검증 구간(`--eval-window`)이 0이거나, 매장의 실제값이 전부 0으로 분모가 사라진 경우입니다. 검증 창을 늘리거나 해당 매장을 제외하세요. |
| Plotly 관련 경고 | Plotly 미설치 시 발생. 시각화가 필요하면 `pip install plotly` 후 재실행하세요. |

---
## 11. 확장 로드맵
- **Panel Regression**: `models/panel_regression`에 고정효과/랜덤효과 예제를 추가하여 다중 매장 회귀를 시험해 보세요.
- **딥러닝(LSTM/TFT)**: `models/lstm` 폴더를 기반으로 `pytorch-forecasting` 또는 `pytorch-lightning`을 연동할 수 있습니다.
- **모델 비교 리포트**: `outputs/*/` 폴더의 `*_metrics.csv`를 취합해 MAE/MAPE 비교표를 만들어 README 또는 위키에 공유하면 협업이 쉬워집니다.
- **서비스 연동**: Streamlit 대시보드를 베이스로 챗봇/내부 서비스 UI에 탑재하거나, 예측 결과를 API 형태로 노출하는 스크립트를 추가하세요.

---
## 12. 클러스터 베이스라인과의 통합 활용
1. **클러스터 결과 결합**
   - `experiments/clusters_k4_baseline/outputs/.../cluster_result.csv`에는 매장당 군집 ID와 기준 KPI가 정리되어 있습니다.
   - 이 파일을 `cafe_timeseries_panel.csv` 또는 각 모델의 `*_forecast.csv`와 `ENCODED_MCT` 기준으로 병합하면 "현재 위치(클러스터) + 향후 전망(예측값)"을 한 테이블에서 다룰 수 있습니다.
   - 추천 예시:
     ```python
     import pandas as pd
     clusters = pd.read_csv('experiments/clusters_k4_baseline/outputs/.../cluster_result.csv')
     prophet = pd.read_csv('experiments/timeseries_models/outputs/prophet/prophet_forecast.csv')
     sarima = pd.read_csv('experiments/timeseries_models/outputs/sarima/sarima_forecast.csv')
     merged = (prophet.merge(sarima, on=['ENCODED_MCT','ds'], suffixes=('_prophet','_sarima'))
                       .merge(clusters[['ENCODED_MCT','cluster_id']], on='ENCODED_MCT'))
     ```
   - 이 merged 데이터를 기준으로 클러스터 프로필(강점/약점)과 월별 예측을 함께 보여 주면 챗봇이 "현재 카테고리 + 앞으로의 추세"를 한 번에 설명할 수 있습니다.
2. **Streamlit 챗봇/대시보드 시나리오**
   - 대시보드에 클러스터 결과를 캐시로 읽어와 사이드바에서 필터(클러스터, 매장 ID)를 제공한 후 예측값을 표시하세요.
   - 챗봇 응답 템플릿 예시:
     - 군집 설명: `cluster_profile_mean.csv`에서 평균 KPI를 읽어 "우리 매장은 Cluster2 (성장형)입니다" 같은 문장을 생성.
     - 예측 요약: Prophet/SARIMA `yhat` 및 신뢰구간을 비교해 "다음 달 매출 등급 0.68 예상, MAE는 0.05 수준"처럼 보고.
     - 경고 조건: `prophet_metrics.csv` 또는 `sarima_metrics.csv`에서 MAE가 0.15 이상이면 "예측 신뢰도가 낮으니 주의" 메시지 추가.
   - Streamlit 앱 구조 예시(`apps/prophet_dashboard.py` 확장):
     1. 클러스터/예측 데이터를 `st.cache_data`로 로드.
     2. 사이드바에서 클러스터 선택 → 해당 매장 목록 표시.
     3. 본문에서 (a) 클러스터 프로필 요약, (b) 예측 차트, (c) 챗봇 응답용 요약 텍스트를 보여 주고, 필요하면 `st.session_state`에 저장해 챗봇 UI와 연동.
3. **예측 모델 직렬화/서빙**
   - Prophet/SARIMA 결과만으로도 챗봇 응답이 가능하지만, 실시간 질의에 대비해 `joblib.dump`로 매장별 모델 객체를 저장해 둘 수 있습니다.
   - 챗봇에서 특정 매장을 선택했을 때 즉석에서 `joblib.load` 후 추가 시나리오(다음 분기 예측, 다른 horizon)까지 답해 주는 구조도 고려해 보세요.
4. **권장 파이프라인**
   1. `clusters_k4_baseline` 프로젝트로 군집을 최신화 (`cluster_result.csv`).
   2. `timeseries_models`로 예측 결과 업데이트.
   3. 두 결과를 통합해 챗봇/대시보드에서 "현재 진단 + 미래 전망 + 액션 가이드"를 한 번에 전달.

---
## 13. 빠른 체크리스트
1. `python scripts/build_timeseries_dataset.py` 실행 → `outputs/cafe_timeseries_panel.csv` 생성 확인.
2. Prophet 또는 SARIMA 실행 → `outputs/<model>/` 폴더에 forecast/metrics 생성 확인.
3. `prophet_cli.py --top-outliers ...`로 이상 매장 점검.
4. 필요한 경우 `streamlit run apps/prophet_dashboard.py`로 결과 공유.

위 절차만 따르면 새로운 동료도 손쉽게 실험을 재현하고 확장할 수 있습니다. 추가 개선 아이디어가 떠오르면 각 모델 폴더의 README나 이 파일에 메모를 남겨 주세요.
