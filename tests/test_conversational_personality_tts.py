"""Unit tests for NOVA's friend-like conversation, natural language adaptation, and TTS-safe emoji sanitization."""

from __future__ import annotations

from personality.system_prompt import (
    LanguageMode,
    ProfileName,
    PromptBuildContext,
    SystemPromptManager,
)
from voice.speaker import clean_text_for_speech

# ==============================================================================
# TTS Sanitization Tests
# ==============================================================================

def test_tts_emoji_sanitization_user_cases() -> None:
    """Verify that all user-requested emoji cases are sanitized for TTS without speaking emojis."""
    cases = [
        ("Yesss 😂 finally!", "Yesss, finally!"),
        ("Wait 😂 what happened?", "Wait, what happened?"),
        ("That was crazy ❤️", "That was crazy"),
        ("Three hours straight? 😭 What topic are you fighting with now?", "Three hours straight? What topic are you fighting with now?"),
        ("LET'S GOOO 😂", "LET'S GOOO"),
        ("Yeah, you sound tired 😅 Long day?", "Yeah, you sound tired, Long day?"),
        ("Arre 😂 kya hua?", "Arre, kya hua?"),
        ("Niceee 😭 What finally made it click?", "Niceee, What finally made it click?"),
    ]

    for raw, expected in cases:
        result = clean_text_for_speech(raw)
        assert result == expected, f"Failed for {raw!r}: got {result!r}, expected {expected!r}"
        # Ensure no emoji remains
        assert not any(ord(char) > 0x2000 and ord(char) not in (0x2018, 0x2019, 0x201C, 0x201D, 0x2014, 0x2026) for char in result)
        # Ensure emojis are NOT converted to spoken words
        assert "hahaha" not in result.lower()
        assert "crying" not in result.lower()
        assert "heart" not in result.lower()
        assert "nervous laugh" not in result.lower()


def test_tts_preserves_punctuation_and_words() -> None:
    """Verify that normal punctuation, numbers, and technical words are safely preserved."""
    raw = "Okay! Binary search runs in O(log n) time, right? What's left?"
    cleaned = clean_text_for_speech(raw)
    assert cleaned == "Okay! Binary search runs in O(log n) time, right? What's left?"


def test_tts_strips_markdown_and_symbols() -> None:
    """Verify markdown code blocks, links, headers, and asterisks are stripped."""
    raw = "Check this [doc](https://example.com) for #1: `git status` **now**! ⭐ 🚀"
    cleaned = clean_text_for_speech(raw)
    assert "https" not in cleaned
    assert "*" not in cleaned
    assert "⭐" not in cleaned
    assert "🚀" not in cleaned
    assert "doc for 1: now!" in cleaned


# ==============================================================================
# Personality & System Prompt Tests
# ==============================================================================

def test_system_prompt_includes_friend_like_rules() -> None:
    """Verify that the generated system prompt instructs friend-like engagement and dynamic length."""
    mgr = SystemPromptManager()
    mgr.initialize()

    context = PromptBuildContext(voice_mode=True, preferred_language=LanguageMode.AUTO)
    prompt = mgr.build_prompt(profile=ProfileName.DEFAULT.value, context=context)

    # Must contain friend-like engagement and dynamic length rules
    assert "Dynamic Conversational Length" in prompt
    assert "attentive, genuine personal companion and close friend" in prompt
    assert "How may I assist you?" in prompt  # In the banned list
    assert "Strictly ban generic robotic customer-support clichés" in prompt
    assert "Do not fake physical human experiences" in prompt


def test_system_prompt_language_mirroring() -> None:
    """Verify that language section handles English, Hindi, and Hinglish mirroring without forcing Hindi on tech."""
    mgr = SystemPromptManager()
    mgr.initialize()

    context = PromptBuildContext(preferred_language=LanguageMode.AUTO)
    prompt = mgr.build_prompt(profile=ProfileName.DEFAULT.value, context=context)

    assert "mirror their natural style" in prompt
    assert "Never force Hindi onto an English query" in prompt
    assert "never force Hinglish into pure technical explanations" in prompt


def test_system_prompt_continuity_and_emoji_rules() -> None:
    """Verify that conversation continuity rules and display emoji rules are present."""
    mgr = SystemPromptManager()
    mgr.initialize()

    context = PromptBuildContext(voice_mode=True)
    prompt = mgr.build_prompt(profile=ProfileName.DEFAULT.value, context=context)

    assert "Conversation Context & Continuity" in prompt
    assert "Never say meta phrases like 'According to my memory'" in prompt
    assert "Occasional, tasteful visual emoji use" in prompt
    assert "Never spell out emojis phonetically" in prompt
