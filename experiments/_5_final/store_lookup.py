from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict

from .data_loader import StoreDataProvider
from .formatter import (
    format_error,
    format_store_marketing,
    format_store_status,
)

__all__ = ["fetch_store_status", "fetch_store_marketing"]


def fetch_store_status(store_code: str, provider: StoreDataProvider | None = None) -> Dict[str, Any]:
    if not store_code or not store_code.strip():
        return format_error("가맹점 코드를 입력해주세요.")

    provider = provider or StoreDataProvider()
    status_info, _ = provider.get_store_records(store_code.strip())

    if status_info is None:
        return format_error(f"가맹점 코드를 찾을 수 없습니다: {store_code}")

    return format_store_status(store_code.strip(), status_info)


def fetch_store_marketing(store_code: str, provider: StoreDataProvider | None = None) -> Dict[str, Any]:
    if not store_code or not store_code.strip():
        return format_error("가맹점 코드를 입력해주세요.")

    provider = provider or StoreDataProvider()
    status_info, marketing_posts = provider.get_store_records(store_code.strip())

    if status_info is None:
        return format_error(f"가맹점 코드를 찾을 수 없습니다: {store_code}")

    if not marketing_posts:
        return format_error("해당 가맹점에 대한 마케팅 포스트를 찾을 수 없습니다.")

    return format_store_marketing(store_code.strip(), status_info, marketing_posts)


def main() -> None:
    parser = argparse.ArgumentParser(description="가맹점 코드로 저장된 리포트 데이터를 조회합니다.")
    parser.add_argument("store_code", help="조회할 가맹점 코드")
    parser.add_argument(
        "--mode",
        choices=["status", "marketing"],
        default="status",
        help="status=매장 요약, marketing=마케팅 카피",
    )
    args = parser.parse_args()

    provider = StoreDataProvider()
    if args.mode == "marketing":
        result = fetch_store_marketing(args.store_code, provider=provider)
    else:
        result = fetch_store_status(args.store_code, provider=provider)

    output = json.dumps(result, ensure_ascii=False, indent=2)
    sys.stdout.buffer.write(output.encode("utf-8"))
    sys.stdout.buffer.write(b"\n")


if __name__ == "__main__":
    main()
