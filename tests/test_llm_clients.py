import pytest
from utils.llm_clients import clean_markdown_code_fences, get_llm_for_agent

def test_clean_markdown_code_fences():
    raw_json = "```json\n{\"key\": \"value\"}\n```"
    cleaned = clean_markdown_code_fences(raw_json)
    assert cleaned == "{\"key\": \"value\"}"

    raw_text = "```\nHello world\n```"
    cleaned_text = clean_markdown_code_fences(raw_text)
    assert cleaned_text == "Hello world"

    plain_text = "{\"key\": \"value\"}"
    assert clean_markdown_code_fences(plain_text) == plain_text

def test_get_llm_for_agent_routing():
    groq_agent = get_llm_for_agent("persona_interpreter")
    assert callable(groq_agent)

    gemini_agent = get_llm_for_agent("filtration_ranking")
    assert callable(gemini_agent)

    no_llm_agent = get_llm_for_agent("news_fetch")
    assert no_llm_agent is None
