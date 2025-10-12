from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
OUTPUTS_DIR = BASE_DIR / "outputs"
LOGS_DIR = OUTPUTS_DIR / "logs"

RAW_DATA_FILENAME = "cafe_features_engineered.csv"
PROCESSED_DATA_FILENAME = "cafe_features_processed.csv"
MODEL_FILENAME = "saved_model.pkl"

DEFAULT_CLUSTER_COUNT = 4
DEFAULT_RANDOM_STATE = 42
DEFAULT_TEST_SIZE = 0.2
DEFAULT_VAL_SIZE = 0.1
DEFAULT_LOG_LEVEL = logging.INFO


def ensure_base_directories() -> None:
    for path in (RAW_DATA_DIR, PROCESSED_DATA_DIR, OUTPUTS_DIR, LOGS_DIR):
        path.mkdir(parents=True, exist_ok=True)


def _resolve_with_fallback(directory: Path, filename: str) -> Path:
    ensure_base_directories()
    candidate = directory / filename
    if candidate.exists():
        return candidate
    legacy = DATA_DIR / filename
    return legacy if legacy.exists() else candidate


def get_raw_dataset_path() -> Path:
    return _resolve_with_fallback(RAW_DATA_DIR, RAW_DATA_FILENAME)


def get_processed_dataset_path() -> Path:
    return _resolve_with_fallback(PROCESSED_DATA_DIR, PROCESSED_DATA_FILENAME)


def create_run_directory(prefix: str = "clusters") -> Path:
    ensure_base_directories()
    run_dir = OUTPUTS_DIR / f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def get_latest_run_directory(prefix: str = "clusters") -> Path:
    ensure_base_directories()
    candidates = sorted(
        (p for p in OUTPUTS_DIR.iterdir() if p.is_dir() and p.name.startswith(prefix))
    )
    if not candidates:
        raise FileNotFoundError(
            f"No run directories found under {OUTPUTS_DIR} with prefix '{prefix}'."
        )
    return candidates[-1]


def setup_run_logger(
    run_dir: Path,
    name: str = "cafe_clustering",
    level: int = DEFAULT_LOG_LEVEL,
) -> logging.Logger:
    ensure_base_directories()
    log_path = run_dir / "run.log"

    logger = logging.getLogger(name)
    logger.setLevel(level)

    for handler in list(logger.handlers):
        logger.removeHandler(handler)

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(level)
    stream_handler.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))
    logger.addHandler(stream_handler)

    return logger
