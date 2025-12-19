"""Unit tests for Gemini usage extraction utilities."""

import pytest
from types import SimpleNamespace

from src.services.gemini_usage import extract_gemini_usage


@pytest.mark.unit
def test_extract_gemini_usage_from_usage_metadata():
    obj = SimpleNamespace(
        usage_metadata=SimpleNamespace(
            prompt_token_count=11,
            response_token_count=22,
            total_token_count=33,
        )
    )

    result = extract_gemini_usage(obj)

    assert result.prompt_tokens == 11
    assert result.output_tokens == 22
    assert result.total_tokens == 33
    assert result.cost is None


@pytest.mark.unit
def test_extract_gemini_usage_derives_total_when_missing():
    obj = SimpleNamespace(
        usage_metadata=SimpleNamespace(
            prompt_token_count=4,
            response_token_count=6,
            total_token_count=None,
        )
    )

    result = extract_gemini_usage(obj)

    assert result.prompt_tokens == 4
    assert result.output_tokens == 6
    assert result.total_tokens == 10


@pytest.mark.unit
def test_extract_gemini_usage_empty_when_no_metadata():
    obj = SimpleNamespace(usage_metadata=None)

    result = extract_gemini_usage(obj)

    assert result.prompt_tokens is None
    assert result.output_tokens is None
    assert result.total_tokens is None
    assert result.cost is None
