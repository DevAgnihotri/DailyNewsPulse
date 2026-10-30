import pytest
from unittest.mock import patch
from graph.state import PipelineState
from agents.persona_interpreter import persona_interpreter_node

def test_persona_interpreter_node_success(tmp_path):
    mock_raw_state: PipelineState = {
        "persona_raw": {
            "name": "Alex",
            "interests": ["AI", "Robotics"],
            "exclude": ["Gossip"],
            "reading_level": "intermediate",
            "preferred_tone": "concise",
            "depth": "summary"
        }
    }

    mock_llm_response = """
    {
      "topics": ["Artificial Intelligence", "Robotics"],
      "exclude_topics": ["Gossip"],
      "tone": "concise",
      "reading_level": "intermediate",
      "depth": "summary"
    }
    """

    with patch("agents.persona_interpreter.get_llm_for_agent") as mock_get_llm, \
         patch("agents.persona_interpreter.INTERMEDIATE_DIR", tmp_path):
        
        # Mock LLM callable return
        mock_get_llm.return_value = lambda sys_p, usr_p: mock_llm_response
        
        result = persona_interpreter_node(mock_raw_state)

        assert "persona_profile" in result
        profile = result["persona_profile"]
        assert profile["topics"] == ["Artificial Intelligence", "Robotics"]
        assert profile["exclude_topics"] == ["Gossip"]
        assert (tmp_path / "persona_profile.json").exists()

def test_persona_interpreter_node_empty_state():
    empty_state: PipelineState = {"persona_raw": {}}
    with pytest.raises(ValueError):
        persona_interpreter_node(empty_state)
