from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
MARKETING_PATH = DATA_DIR / "marketing_posts.json"
STATUS_PATH = DATA_DIR / "store_status.json"


class StoreDataProvider:
    """marketing_posts.json과 store_status.json을 가맹점 코드 기준으로 제공합니다."""

    def __init__(
        self,
        marketing_path: Path = MARKETING_PATH,
        status_path: Path = STATUS_PATH,
    ) -> None:
        self.marketing_path = marketing_path
        self.status_path = status_path
        self._marketing_index: Dict[str, List[Dict[str, Any]]] | None = None
        self._status_index: Dict[str, Dict[str, Any]] | None = None

    def refresh(self) -> None:
        self._marketing_index = self._build_marketing_index(self._load_json(self.marketing_path))
        self._status_index = self._build_status_index(self._load_json(self.status_path))

    def get_store_records(self, store_code: str) -> Tuple[Dict[str, Any] | None, List[Dict[str, Any]]]:
        self._ensure_loaded()
        code = store_code.strip()
        status = self._status_index.get(code) if self._status_index else None  # type: ignore[arg-type]
        posts = (self._marketing_index or {}).get(code, [])
        return status, posts

    def _ensure_loaded(self) -> None:
        if self._marketing_index is None or self._status_index is None:
            self.refresh()

    @staticmethod
    def _load_json(path: Path) -> Any:
        if not path.exists():
            raise FileNotFoundError(f"데이터 파일을 찾을 수 없습니다: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _build_marketing_index(raw: Any) -> Dict[str, List[Dict[str, Any]]]:
        index: Dict[str, List[Dict[str, Any]]] = {}
        if not isinstance(raw, list):
            return index
        for item in raw:
            if not isinstance(item, dict):
                continue
            code = str(item.get("가맹점코드") or "").strip()
            if not code:
                continue
            index.setdefault(code, []).append(item)
        return index

    @staticmethod
    def _build_status_index(raw: Any) -> Dict[str, Dict[str, Any]]:
        index: Dict[str, Dict[str, Any]] = {}
        if not isinstance(raw, list):
            return index
        for item in raw:
            if not isinstance(item, dict):
                continue
            code = str(item.get("가맹점코드") or "").strip()
            if not code:
                continue
            index[code] = item
        return index


__all__ = ["StoreDataProvider"]
