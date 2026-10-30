"""
Unit tests for persona_loader utility
"""

import os
import pytest
from utils.persona_loader import load_personas, get_persona_by_id


def test_load_personas():
    """Test loading all personas from static file."""
    personas = load_personas()
    assert isinstance(personas, list)
    assert len(personas) == 10

    # Ensure all have required keys
    for p in personas:
        assert "persona_id" in p
        assert "name" in p
        assert "topics" in p
        assert isinstance(p["topics"], list)
        assert len(p["topics"]) > 0


def test_get_persona_by_id():
    """Test looking up persona by unique ID."""
    tech_p = get_persona_by_id("tech_professional")
    assert tech_p is not None
    assert tech_p["name"] == "Tech Professional"
    assert tech_p["persona_id"] == "tech_professional"

    # Non-existent persona returns None
    missing = get_persona_by_id("non_existent_id_xyz")
    assert missing is None
