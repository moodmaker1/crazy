from __future__ import annotations

from typing import Any, Dict, List


def _collect_reasons(status_info: Dict[str, Any]) -> List[str]:
    fields = [
        "재방문고객비율설명",
        "신규고객비율설명",
        "거주고객비율설명",
        "직장고객비율설명",
        "유동고객비율설명",
        "배달매출비율설명",
        "충성도점수설명",
    ]
    reasons = [status_info.get(field) for field in fields]
    return [reason for reason in reasons if isinstance(reason, str) and reason.strip()]


def _extract_metrics(status_info: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "revisit_ratio": status_info.get("재방문고객비율"),
        "new_ratio": status_info.get("신규고객비율"),
        "resident_ratio": status_info.get("거주고객비율"),
        "office_ratio": status_info.get("직장고객비율"),
        "floating_ratio": status_info.get("유동고객비율"),
        "delivery_ratio": status_info.get("배달매출비율"),
        "loyalty_score": status_info.get("충성도점수"),
    }


def _format_marketing_posts(posts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    formatted: List[Dict[str, Any]] = []
    for post in posts:
        formatted.append(
            {
                "channel": post.get("채널"),
                "title": post.get("제목"),
                "copy": post.get("게시글"),
                "call_to_actions": post.get("행동문장추천"),
                "insights": post.get("추가인사이트"),
                "assets": {
                    "photo_ideas": post.get("추천사진아이디어"),
                    "hashtags": post.get("해시태그"),
                    "location_tag": post.get("위치태그안내"),
                },
            }
        )
    return formatted


def format_store_status(store_code: str, status_info: Dict[str, Any]) -> Dict[str, Any]:
    metrics = _extract_metrics(status_info)
    reasons = _collect_reasons(status_info)

    return {
        "store_code": store_code,
        "store_name": status_info.get("가맹점명"),
        "store_type": None,
        "district": status_info.get("법정동"),
        "area": None,
        "emoji": "🏪",
        "success_prob": None,
        "fail_prob": None,
        "status": status_info.get("가게분석"),
        "message": status_info.get("가게분석"),
        "recommendation": "",
        "reasons": reasons,
        "interpret_text": status_info.get("가게분석"),
        "metrics": metrics,
    }


def format_store_marketing(
    store_code: str,
    status_info: Dict[str, Any],
    marketing_posts: List[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "store_code": store_code,
        "store_name": status_info.get("가맹점명"),
        "district": status_info.get("법정동"),
        "marketing_posts": _format_marketing_posts(marketing_posts),
    }


def format_error(message: str) -> Dict[str, str]:
    return {"error": message}


__all__ = ["format_store_status", "format_store_marketing", "format_error"]
