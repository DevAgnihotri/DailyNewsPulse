import pytest
from pathlib import Path
from utils.json_io import load_json, save_json, validate_schema, timestamp_filename

def test_save_and_load_json(tmp_path: Path):
    sample_data = {
        "name": "Alex Tech Enthusiast",
        "interests": ["AI", "Robotics"],
        "reading_level": "advanced"
    }
    file_path = tmp_path / "test_persona.json"
    
    # Save
    saved_path = save_json(sample_data, file_path)
    assert saved_path.exists()
    
    # Load
    loaded_data = load_json(file_path)
    assert loaded_data == sample_data

def test_load_nonexistent_file(tmp_path: Path):
    fake_file = tmp_path / "does_not_exist.json"
    with pytest.raises(FileNotFoundError):
        load_json(fake_file)

def test_load_malformed_json(tmp_path: Path):
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("{ unquoted_key: invalid }", encoding="utf-8")
    with pytest.raises(ValueError):
        load_json(bad_file)

def test_validate_schema():
    data = {"topics": ["AI"], "tone": "casual", "reading_level": "intermediate"}
    assert validate_schema(data, ["topics", "tone"]) is True
    assert validate_schema(data, ["topics", "missing_key"]) is False

def test_timestamp_filename():
    result = timestamp_filename("persona_profile.json")
    assert result.startswith("persona_profile_")
    assert result.endswith(".json")
