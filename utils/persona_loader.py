"""
Persona Loader Utility

Loads and validates static pre-normalized personas from data/personas/personas.json.
Provides helper functions to retrieve all personas or look up a single persona by its stable persona_id.
"""

import os
from typing import List, Dict, Any, Optional
from config.settings import DATA_DIR
from utils.json_io import load_json

PERSONAS_FILE_PATH = os.path.join(DATA_DIR, "personas", "personas.json")


def load_personas(file_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Load all personas from the static personas JSON file.

    Args:
        file_path (Optional[str]): Custom path to personas.json file. Defaults to standard location.

    Returns:
        List[Dict[str, Any]]: List of persona dictionaries.
    """
    target_path = file_path or PERSONAS_FILE_PATH
    data = load_json(target_path)
    if not isinstance(data, dict) or "personas" not in data:
        raise ValueError(f"Invalid personas file format at {target_path}. Expected object with 'personas' list.")

    personas = data["personas"]
    if not isinstance(personas, list):
        raise ValueError("'personas' key must be a list.")

    # Validate unique IDs
    seen_ids = set()
    for persona in personas:
        pid = persona.get("persona_id")
        if not pid:
            raise ValueError(f"Persona missing required 'persona_id': {persona}")
        if pid in seen_ids:
            raise ValueError(f"Duplicate persona_id detected: '{pid}'")
        seen_ids.add(pid)

    return personas


def get_persona_by_id(persona_id: str, file_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Find and return a single persona by its unique persona_id.

    Args:
        persona_id (str): The unique identifier of the persona (e.g. 'tech_professional').
        file_path (Optional[str]): Custom path to personas.json file.

    Returns:
        Optional[Dict[str, Any]]: The persona dictionary if found, or None.
    """
    personas = load_personas(file_path)
    for persona in personas:
        if persona.get("persona_id") == persona_id:
            return persona
    return None
