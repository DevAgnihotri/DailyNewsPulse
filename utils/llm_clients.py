import logging
import re
import time
from typing import Callable, Optional, Any
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI

from config.settings import (
    GROQ_API_KEY,
    GROQ_MODEL,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    AGENT_TEMPERATURES,
    get_provider_for_agent,
)

logger = logging.getLogger(__name__)


def clean_markdown_code_fences(text: str) -> str:
    """Removes markdown code block formatting (e.g. ```json ... ```) from LLM outputs."""
    text = text.strip()
    # Match pattern ```json ... ``` or ``` ... ```
    pattern = r"^```(?:json)?\s*\n?(.*?)\n?```$"
    match = re.match(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text


def _call_with_retry(
    fn: Callable[[], str],
    max_retries: int = 3,
    initial_delay: float = 1.5,
    max_delay: float = 30.0
) -> str:
    """
    Helper function executing an LLM API call with robust exponential retry backoff.
    Detects rate limits (429 / RESOURCE_EXHAUSTED) and respects server-requested retry delays.
    """
    delay = initial_delay
    last_exc = None

    for attempt in range(1, max_retries + 1):
        try:
            return fn()
        except Exception as e:
            last_exc = e
            err_str = str(e)
            logger.warning(f"LLM call attempt {attempt}/{max_retries} failed: {e}")

            if attempt == max_retries:
                logger.error(f"All {max_retries} retry attempts failed for LLM call.")
                raise e

            # Check if error message contains a specific retry delay directive (e.g. 'retry in 25.5s' or 'retryDelay': '25s')
            sleep_time = delay
            match_retry = re.search(r"retry\s+in\s+([\d\.]+)\s*s", err_str, re.IGNORECASE)
            if match_retry:
                try:
                    suggested_wait = float(match_retry.group(1))
                    # Cap suggested wait to max_delay to prevent hanging
                    sleep_time = min(max_delay, max(suggested_wait + 1.0, delay))
                except (ValueError, TypeError):
                    pass
            elif "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                # Give a slightly longer pause for quota replenishment
                sleep_time = min(max_delay, delay * 2.0)

            logger.info(f"Retrying in {sleep_time:.1f}s (attempt {attempt + 1}/{max_retries})...")
            time.sleep(sleep_time)
            delay = min(max_delay, delay * 2.0)

    if last_exc:
        raise last_exc
    raise RuntimeError("LLM call failed after retries.")


def _extract_response_text(content: Any) -> str:
    """Extracts raw text string from LLM response.content (handles both str and list of dicts)."""
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        pieces = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                pieces.append(str(item["text"]))
            elif isinstance(item, str):
                pieces.append(item)
        return "".join(pieces)
    return str(content)


def call_groq(system_prompt: str, user_prompt: str, temperature: float = 0.1) -> str:
    """
    Calls Groq LLM (groq/compound-mini with automatic fallback models) via langchain_groq.
    
    Args:
        system_prompt: Instruction for the system role.
        user_prompt: User input content.
        temperature: Sampling temperature.
        
    Returns:
        Cleaned plain text string response.
    """
    candidate_groq_models = [
        GROQ_MODEL,
        "groq/compound-mini",
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant"
    ]
    # Deduplicate while preserving order
    models_to_try = list(dict.fromkeys(candidate_groq_models))

    last_error = None
    for model_name in models_to_try:
        def _invoke():
            llm = ChatGroq(
                groq_api_key=GROQ_API_KEY,
                model_name=model_name,
                temperature=temperature,
            )
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]
            response = llm.invoke(messages)
            text = _extract_response_text(response.content)
            return clean_markdown_code_fences(text)

        try:
            return _call_with_retry(_invoke, max_retries=3, initial_delay=1.0)
        except Exception as e:
            logger.warning(f"Groq model '{model_name}' failed: {e}. Trying fallback model if available...")
            last_error = e

    if last_error:
        raise last_error
    raise RuntimeError("All Groq candidate models failed.")


def call_gemini(system_prompt: str, user_prompt: str, temperature: float = 0.1) -> str:
    """
    Calls Gemini LLM (gemini-3.6-flash with automatic fallback to gemini-3.5-flash) via langchain_google_genai.
    Ensures modern production models are used, with zero deprecated 2.x or 2.5 series models.
    
    Args:
        system_prompt: Instruction for the system role.
        user_prompt: User input content.
        temperature: Sampling temperature.
        
    Returns:
        Cleaned plain text string response.
    """
    # Use modern official production models: Gemini 3.6 Flash and 3.5 Flash
    candidate_models = [
        GEMINI_MODEL,
        "gemini-3.6-flash",
        "gemini-3.5-flash"
    ]
    # Deduplicate while preserving order
    models_to_try = list(dict.fromkeys(candidate_models))

    last_error = None
    for model_name in models_to_try:
        def _invoke():
            llm = ChatGoogleGenerativeAI(
                google_api_key=GEMINI_API_KEY,
                model=model_name,
                temperature=temperature,
            )
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]
            response = llm.invoke(messages)
            text = _extract_response_text(response.content)
            return clean_markdown_code_fences(text)

        try:
            return _call_with_retry(_invoke, max_retries=3, initial_delay=1.5)
        except Exception as e:
            logger.warning(f"Gemini model '{model_name}' failed: {e}. Trying fallback model if available...")
            last_error = e

    if last_error:
        raise last_error
    raise RuntimeError("All Gemini candidate models failed.")


def get_llm_for_agent(agent_name: str) -> Optional[Callable[[str, str], str]]:
    """
    Returns a configured wrapped LLM callable function `(system_prompt, user_prompt) -> str`
    for the specified agent name based on central config settings.
    
    Returns None if the agent doesn't require an LLM (e.g. news_fetch or presentation_formatter).
    """
    provider = get_provider_for_agent(agent_name)
    temperature = AGENT_TEMPERATURES.get(agent_name, 0.1)

    if provider == "groq":
        return lambda sys_p, usr_p: call_groq(sys_p, usr_p, temperature=temperature)
    elif provider == "gemini":
        return lambda sys_p, usr_p: call_gemini(sys_p, usr_p, temperature=temperature)
    elif provider is None:
        return None
    else:
        raise ValueError(f"Unknown LLM provider '{provider}' configured for agent '{agent_name}'")
