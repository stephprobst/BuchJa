"""Gemini usage tracking utilities.

This module only extracts usage information that is explicitly provided by the
Gemini API (via the Google Gen AI SDK). It does not estimate costs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class GeminiUsage:
    """Usage numbers for a single Gemini API call."""

    model: Optional[str] = None

    prompt_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None

    # Optional token breakdown by modality (when provided by the API).
    prompt_text_tokens: Optional[int] = None
    prompt_image_tokens: Optional[int] = None
    output_text_tokens: Optional[int] = None
    output_image_tokens: Optional[int] = None
    thoughts_tokens: Optional[int] = None

    # Monetary values are only included if the API returns them.
    cost: Any | None = None


def _get_attr(obj: Any, name: str) -> Any:
    if obj is None:
        return None
    return getattr(obj, name, None)


def _modality_key(modality: Any) -> Optional[str]:
    """Normalize a modality value from the SDK into 'text'/'image'/..."""
    if modality is None:
        return None
    if isinstance(modality, str):
        value = modality
    else:
        value = getattr(modality, 'name', None) or str(modality)
    value = value.lower()
    # Common forms: 'TEXT', 'IMAGE', 'Modality.TEXT', 'MODALITY_TEXT'
    if 'text' in value:
        return 'text'
    if 'image' in value:
        return 'image'
    return None


def _sum_tokens_details(tokens_details: Any) -> dict[str, int]:
    """Sum a list of ModalityTokenCount-like objects into a dict."""
    totals: dict[str, int] = {}
    if not tokens_details:
        return totals
    for item in tokens_details:
        modality = _modality_key(_get_attr(item, 'modality'))
        token_count = _get_attr(item, 'token_count')
        if modality is None or token_count is None:
            continue
        try:
            totals[modality] = totals.get(modality, 0) + int(token_count)
        except (TypeError, ValueError):
            continue
    return totals


def extract_gemini_usage(response_or_chunk: Any, *, model: Optional[str] = None) -> GeminiUsage:
    """Extract token usage (and cost if available) from a Gemini SDK object.

    The Google Gen AI SDK exposes token counts on `usage_metadata`.

    This function is intentionally defensive because streaming chunks and
    full responses may have slightly different shapes.
    """

    usage = _get_attr(response_or_chunk, "usage_metadata")
    if usage is None:
        # Some SDK objects might use a different field name.
        usage = _get_attr(response_or_chunk, "usageMetadata")

    prompt_tokens = _get_attr(usage, "prompt_token_count")

    # SDK may use `response_token_count` (UsageMetadata) or `candidates_token_count`
    # (GenerateContentResponseUsageMetadata).
    output_tokens = _get_attr(usage, "response_token_count")
    if output_tokens is None:
        output_tokens = _get_attr(usage, "candidates_token_count")

    total_tokens = _get_attr(usage, "total_token_count")

    thoughts_tokens = _get_attr(usage, 'thoughts_token_count')

    prompt_details = _get_attr(usage, 'prompt_tokens_details')
    # Output tokens details can be named differently.
    output_details = (
        _get_attr(usage, 'response_tokens_details')
        or _get_attr(usage, 'candidates_tokens_details')
    )
    prompt_modality_totals = _sum_tokens_details(prompt_details)
    output_modality_totals = _sum_tokens_details(output_details)

    # Monetary amounts are not documented as part of usage metadata for the
    # Gemini Developer API, but we support displaying them verbatim if the SDK
    # ever exposes such a field.
    cost = _get_attr(response_or_chunk, "cost")
    if cost is None:
        cost = _get_attr(usage, "cost")

    # Coerce token values to int if they are numeric-like.
    def as_int(value: Any) -> Optional[int]:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    prompt_tokens_i = as_int(prompt_tokens)
    output_tokens_i = as_int(output_tokens)
    total_tokens_i = as_int(total_tokens)
    thoughts_tokens_i = as_int(thoughts_tokens)

    # If total tokens isn't provided but prompt/output are, we can derive a total
    # without guessing any monetary amounts.
    if total_tokens_i is None and prompt_tokens_i is not None and output_tokens_i is not None:
        total_tokens_i = prompt_tokens_i + output_tokens_i

    if prompt_tokens_i is None and output_tokens_i is None and total_tokens_i is None and cost is None:
        # Still return modality/thinking if present.
        if not prompt_modality_totals and not output_modality_totals and thoughts_tokens_i is None:
            return GeminiUsage(model=model)

    return GeminiUsage(
        model=model,
        prompt_tokens=prompt_tokens_i,
        output_tokens=output_tokens_i,
        total_tokens=total_tokens_i,
        prompt_text_tokens=prompt_modality_totals.get('text'),
        prompt_image_tokens=prompt_modality_totals.get('image'),
        output_text_tokens=output_modality_totals.get('text'),
        output_image_tokens=output_modality_totals.get('image'),
        thoughts_tokens=thoughts_tokens_i,
        cost=cost,
    )
