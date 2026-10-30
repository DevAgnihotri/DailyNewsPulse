import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, List, Union

logger = logging.getLogger(__name__)


def load_json(filepath: Union[str, Path]) -> Any:
    """Load JSON data from a file path.

    Args:
        filepath: Path to the JSON file.

    Returns:
        Parsed JSON data (dict or list).

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If JSON is invalid or malformed.
        PermissionError: If access is denied.
    """
    path = Path(filepath)
    if not path.is_file():
        logger.error(f"JSON file not found: {path}")
        raise FileNotFoundError(f"JSON file not found: {path}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            logger.info(f"Successfully loaded JSON from {path}")
            return data
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON file {path}: {e}")
        raise ValueError(f"Malformed JSON in file {path}: {e}") from e
    except PermissionError as e:
        logger.error(f"Permission denied reading file {path}: {e}")
        raise PermissionError(f"Permission denied reading file {path}: {e}") from e
    except Exception as e:
        logger.error(f"Unexpected error loading JSON from {path}: {e}")
        raise


def save_json(data: Any, filepath: Union[str, Path], indent: int = 2) -> Path:
    """Save data as formatted JSON to a file path. Creates parent directories if needed.

    Args:
        data: Dict or list data to serialize.
        filepath: Target file path.
        indent: JSON indentation spacing (default 2).

    Returns:
        Path object of the saved file.

    Raises:
        PermissionError: If write permission is denied.
        TypeError: If data is not JSON-serializable.
    """
    path = Path(filepath)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
        logger.info(f"Successfully saved JSON to {path}")
        return path
    except TypeError as e:
        logger.error(f"Data for {path} is not JSON serializable: {e}")
        raise TypeError(f"Data for {path} is not JSON serializable: {e}") from e
    except PermissionError as e:
        logger.error(f"Permission denied writing to file {path}: {e}")
        raise PermissionError(f"Permission denied writing to file {path}: {e}") from e
    except Exception as e:
        logger.error(f"Unexpected error saving JSON to {path}: {e}")
        raise


def validate_schema(data: dict, required_keys: List[str]) -> bool:
    """Check if all required keys are present in a dictionary.

    Args:
        data: Dictionary to validate.
        required_keys: List of key names that must be present.

    Returns:
        True if all required keys exist, False otherwise.
    """
    if not isinstance(data, dict):
        logger.warning("Schema validation failed: data is not a dict")
        return False

    missing = [key for key in required_keys if key not in data]
    if missing:
        logger.warning(f"Schema validation failed. Missing keys: {missing}")
        return False
    return True


def timestamp_filename(filename: str) -> str:
    """Appends a timestamp suffix to a filename before its extension.

    Example: "persona_profile.json" -> "persona_profile_20260916_135000.json"
    """
    path = Path(filename)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{path.stem}_{timestamp}{path.suffix}"
