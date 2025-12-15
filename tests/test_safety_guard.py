import pytest
from llm.safety_guard import (
    guard_text,
    EMERGENCY_GUIDANCE,
)

# PHI masking
def test_phi_masking_ssn():
    text = "My SSN is 123-45-6789."
    result = guard_text(text)

    assert result.allowed is True
    assert "[PHI_SSN]" in result.masked_text
    assert "123-45-6789" not in result.masked_text
    assert "mask_phi" in result.actions
    assert result.severity == "medium"
    assert any(r["type"] == "PHI" for r in result.reasons)


def test_phi_masking_email_and_name():
    text = "John Doe can be reached at john.doe@example.com."
    result = guard_text(text)

    assert "[PHI_NAME]" in result.masked_text
    assert "[PHI_EMAIL]" in result.masked_text
    assert result.allowed is True
    assert result.severity == "medium"
    assert "mask_phi" in result.actions

# Diagnosis blocking
def test_block_diagnosis_language():
    text = "You have diabetes based on these symptoms."
    result = guard_text(text)

    assert result.allowed is False
    assert "block_diagnosis" in result.actions
    assert result.severity == "high"

    reasons = [r["type"] for r in result.reasons]
    assert "MEDICAL_DIAGNOSIS" in reasons

# Prescription blocking
def test_block_prescription_language():
    text = "You should take 20 mg of this medication daily."
    result = guard_text(text)

    assert result.allowed is False
    assert "block_prescription" in result.actions
    assert result.severity == "high"

    reasons = [r["type"] for r in result.reasons]
    assert "MEDICAL_PRESCRIPTION" in reasons

# Emergency crisis handling 
def test_emergency_guidance_added():
    text = "I have severe chest pain and trouble breathing."
    result = guard_text(text)

    assert result.allowed is True  # still allowed, but guided
    assert "add_emergency_guidance" in result.actions
    assert EMERGENCY_GUIDANCE in result.masked_text
    assert result.severity == "high"

    reasons = [r["type"] for r in result.reasons]
    assert "EMERGENCY" in reasons


def test_suicidal_language_triggers_emergency():
    text = "I feel like I want to kill myself."
    result = guard_text(text)

    assert "add_emergency_guidance" in result.actions
    assert EMERGENCY_GUIDANCE in result.masked_text
    assert result.severity == "high"

# Combined cases
def test_phi_and_emergency_combined():
    text = "John Doe has chest pain. Call me at 0912345678."
    result = guard_text(text)

    # PHI masked
    assert "[PHI_NAME]" in result.masked_text
    assert "[PHI_PHONE]" in result.masked_text

    # Emergency handled
    assert "add_emergency_guidance" in result.actions
    assert EMERGENCY_GUIDANCE in result.masked_text

    # Severity escalates to high
    assert result.severity == "high"

# Safe content 
def test_safe_wellness_content_passes():
    text = "Staying hydrated and resting may help you feel better."
    result = guard_text(text)

    assert result.allowed is True
    assert result.actions == []
    assert result.reasons == []
    assert result.severity == "low"
    assert result.masked_text == text
