# Prophet 모델 가이드

`run_prophet.py`는 매장별 매출 등급(`sales_grade`)을 Prophet으로 예측하는 베이스라인 스크립트입니다.

## 실행
```bash
python experiments/timeseries_models/scripts/run_prophet.py \
  --panel experiments/timeseries_models/outputs/cafe_timeseries_panel.csv \
  --out-dir experiments/timeseries_models/outputs/prophet \
  --min-history 12 --horizon 3 --eval-window 3
```

## 출력
- `prophet_forecast.csv`: 예측 결과 (매장, 예측 월, yhat 등)
- `prophet_metrics.csv`: MAE/RMSE/MAPE 및 학습 포인트 수

## 의존성
```bash
pip install prophet
```

## 참고
- 연간 seasonality만 추가한 기본 설정입니다.
- 필요 시 `run_prophet.py`의 `build_prophet()`에서 트렌드, changepoint, holiday 등을 조정하세요.
