# 공유용 리포트 헬퍼

백엔드 팀에서 1번 과제(카페 방문 고객 특성 분석) 리포트를 바로 활용할 수 있도록, 필요한 코드와 데이터만 `share/` 폴더에 재구성했습니다.

## 폴더 구성

- `share/report_generator.py`: 리포트 생성 함수
- `share/data/cluster_result.csv`: 최신 군집 결과 데이터
- `share/data/cafe_features_processed.csv`: 매장 특성 데이터

## 제공 함수

- `generate_marketing_report1(store_code, cluster_path=None, features_path=None)`
- `generate_report(store_code, kind="cluster", **kwargs)` – 현재 `kind="cluster"`만 지원

모든 함수는 `dict` 형태의 리포트를 반환하므로 JSON 응답으로 직렬화하기 쉽습니다.

## 사용 예시

```python
from share.report_generator import generate_marketing_report1

result = generate_marketing_report1("003AC99735")
```

- `store_code`는 ENCODED_MCT(가맹점 코드)입니다.
- 데이터는 기본적으로 `share/data` 폴더를 사용합니다. 필요하면 `cluster_path`, `features_path` 인자로 다른 CSV 경로를 지정할 수 있습니다.

## VS Code PowerShell에서 빠르게 확인하기

```powershell
python -c "from share.report_generator import generate_marketing_report1; import json; report = generate_marketing_report1('003AC99735'); print(json.dumps(report, ensure_ascii=False, indent=2))"
```

다른 매장을 보려면 따옴표 안의 가맹점 코드를 원하는 값으로 교체하면 됩니다. 출력 구조가 기대와 다를 경우 `share/data` 폴더의 CSV가 최신인지 확인하세요.
