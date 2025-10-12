# SARIMA 모델 가이드

`run_sarima.py`는 `pmdarima.auto_arima`를 활용해 매장별 SARIMA 모델을 학습하고 예측합니다.

## 실행
```bash
python experiments/timeseries_models/scripts/run_sarima.py \
  --panel experiments/timeseries_models/outputs/cafe_timeseries_panel.csv \
  --out-dir experiments/timeseries_models/outputs/sarima \
  --min-history 12 --horizon 3 --eval-window 3
```

## 출력
- `sarima_forecast.csv`: 미래 월 예측값(yhat)
- `sarima_metrics.csv`: 검증 MAE/RMSE/MAPE 등

## 의존성
```bash
pip install pmdarima
```

## 참고
- `auto_arima` 기본 설정(계절성 m=12)을 사용합니다.
- 더 긴 히스토리 또는 특정 매장만 대상으로 하고 싶다면 스크립트에서 `min_history`나 `auto_arima` 파라미터를 조정하세요.
