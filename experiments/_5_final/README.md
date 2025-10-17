# reee 패키지 사용 안내

가맹점 코드를 입력하면 `reee/data/store_status.json`과
`reee/data/marketing_posts.json`에 담긴 정보를 손쉽게 조회할 수 있는 모듈입니다.

## 구성

| 파일 | 설명 |
| --- | --- |
| `data_loader.py` | JSON을 불러와 가맹점 코드 기준으로 인덱싱합니다. |
| `formatter.py` | 조회 결과를 서비스용 포맷으로 정리합니다. |
| `store_lookup.py` | CLI 및 `fetch_store_status` / `fetch_store_marketing` 함수를 제공합니다. |

## 준비

`reee/data` 디렉터리에 아래 두 파일이 존재해야 합니다.

* `store_status.json`
* `marketing_posts.json`

(`05_reports/generate_reports.py` 실행 후 최신 파일을 복사하여 사용하면 됩니다.)

## CLI 사용법

```bash
# 매장 요약(status)
python -m reee.store_lookup 086AA2377D --mode status

# 마케팅 카피(marketing)
python -m reee.store_lookup 086AA2377D --mode marketing
```

## 코드 사용 예시

```python
from reee.store_lookup import fetch_store_status, fetch_store_marketing

status = fetch_store_status("086AA2377D")
marketing = fetch_store_marketing("086AA2377D")
```

## 반환 형식 (`mode=status`)

```json
{
  "store_code": "086AA2377D",
  "store_name": "갑부***",
  "store_type": null,
  "district": "옥수동",
  "area": null,
  "emoji": "🏪",
  "success_prob": null,
  "fail_prob": null,
  "status": "재방문율이 높은 편입니다 · 거주 고객 비중이 두드러집니다. / 재방문 고객 34% / 신규 고객 8% / …",
  "message": "재방문율이 높은 편입니다 · 거주 고객 비중이 두드러집니다. / …",
  "recommendation": "",
  "reasons": ["재방문 고객 34%", "신규 고객 8%", …],
  "interpret_text": "재방문율이 높은 편입니다 · …",
  "metrics": {
    "revisit_ratio": 34,
    "new_ratio": 8,
    "resident_ratio": 66,
    "office_ratio": 3,
    "floating_ratio": 32,
    "delivery_ratio": 7,
    "loyalty_score": 25.9
  }
}
```

## 반환 형식 (`mode=marketing`)

```json
{
  "store_code": "086AA2377D",
  "store_name": "갑부***",
  "district": "옥수동",
  "marketing_posts": [
    {
      "channel": "인스타그램",
      "title": "갑부*** 인스타그램 추천",
      "copy": "게시글 본문 …",
      "call_to_actions": { "고객을 부르는 한마디": "…", "마무리 문장": "…" },
      "insights": [...],
      "assets": {
        "photo_ideas": [...],
        "hashtags": [...],
        "location_tag": "..."
      }
    },
    …
  ]
}
```

## 오류 응답

데이터가 없거나 입력이 잘못된 경우 `{"error": "…"}`
형식의 메시지를 반환합니다.
