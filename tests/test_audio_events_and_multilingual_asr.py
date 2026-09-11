"""Comprehensive test suite for non-speech audio events, Hindi/Hinglish understanding, ASR configuration, and command preservation in NOVA Voice V2."""

from __future__ import annotations

import numpy as np
import pytest

from config.settings import settings
from intent.models import CanonicalIntent
from intent.engine import NaturalLanguageIntentEngine
from voice.audio_events import AudioEventDetector, AudioEventType
from voice.speaker import clean_text_for_speech
from voice.transcriber import (
    ASSISTANT_DOMAIN_PROMPT,
    ASSISTANT_HOTWORDS,
    FasterWhisperTranscriber,
    TranscriptionManager,
)


def test_cough_detection_and_text_cleaning() -> None:
    res1 = AudioEventDetector.analyze('[cough]')
    assert res1.event_type == AudioEventType.COUGH
    assert res1.is_isolated_event is True
    assert res1.clean_text == ''

    res2 = AudioEventDetector.analyze('Nova *cough*')
    assert res2.event_type == AudioEventType.COUGH
    assert res2.is_isolated_event is True

    res3 = AudioEventDetector.analyze('Nova aaj bahut thak gaya hoon [cough]')
    assert res3.event_type == AudioEventType.COUGH
    assert res3.is_isolated_event is False
    assert res3.clean_text == 'Nova aaj bahut thak gaya hoon'

    res4 = AudioEventDetector.analyze('Nova, open Telegram *cough*')
    assert res4.event_type == AudioEventType.COUGH
    assert res4.is_isolated_event is False
    assert res4.clean_text == 'Nova, open Telegram'


def test_laughter_detection_and_text_cleaning() -> None:
    res1 = AudioEventDetector.analyze('[laughter]')
    assert res1.event_type == AudioEventType.LAUGHTER
    assert res1.is_isolated_event is True
    assert res1.clean_text == ''

    res2 = AudioEventDetector.analyze('haha')
    assert res2.event_type == AudioEventType.LAUGHTER
    assert res2.is_isolated_event is True

    res3 = AudioEventDetector.analyze('Nova I finally solved that bug! [laughter]')
    assert res3.event_type == AudioEventType.LAUGHTER
    assert res3.is_isolated_event is False
    assert res3.clean_text == 'Nova I finally solved that bug!'

    res4 = AudioEventDetector.analyze('Nova guess what happened today haha')
    assert res4.event_type == AudioEventType.LAUGHTER
    assert res4.is_isolated_event is False
    assert res4.clean_text == 'Nova guess what happened today'


def test_sneeze_detection_and_text_cleaning() -> None:
    res1 = AudioEventDetector.analyze('[sneeze]')
    assert res1.event_type == AudioEventType.SNEEZE
    assert res1.is_isolated_event is True
    assert res1.clean_text == ''

    res2 = AudioEventDetector.analyze('achoo')
    assert res2.event_type == AudioEventType.SNEEZE
    assert res2.is_isolated_event is True

    res3 = AudioEventDetector.analyze("Nova what's the weather today [sneeze]")
    assert res3.event_type == AudioEventType.SNEEZE
    assert res3.is_isolated_event is False
    assert res3.clean_text == "Nova what's the weather today"


def test_sigh_and_throat_clear_detection() -> None:
    res_sigh = AudioEventDetector.analyze('This code is still not working *sigh*')
    assert res_sigh.event_type == AudioEventType.SIGH
    assert res_sigh.is_isolated_event is False
    assert res_sigh.clean_text == 'This code is still not working'

    res_iso_sigh = AudioEventDetector.analyze('[sigh]')
    assert res_iso_sigh.event_type == AudioEventType.SIGH
    assert res_iso_sigh.is_isolated_event is True

    res_tc = AudioEventDetector.analyze('*clears throat* Nova open Telegram')
    assert res_tc.event_type == AudioEventType.THROAT_CLEAR
    assert res_tc.is_isolated_event is False
    assert res_tc.clean_text == 'Nova open Telegram'


def test_acoustic_silence_detection() -> None:
    sample_rate = 16000
    silent_audio = np.zeros(sample_rate, dtype=np.float32)
    res = AudioEventDetector.analyze('', silent_audio, sample_rate=sample_rate)
    assert res.event_type == AudioEventType.SILENCE


def test_acoustic_cough_burst_detection() -> None:
    sample_rate = 16000
    dur = 0.3
    t = np.linspace(0, dur, int(sample_rate * dur), endpoint=False)
    audio = np.random.normal(0, 0.02, len(t)).astype(np.float32)
    spike_idx = int(sample_rate * 0.05)
    audio[spike_idx : spike_idx + 200] = 0.75
    res = AudioEventDetector.analyze('', audio, sample_rate=sample_rate)
    assert res.event_type in (AudioEventType.COUGH, AudioEventType.SNEEZE)
    assert res.is_isolated_event is True


def test_acoustic_laughter_envelope_modulation() -> None:
    sample_rate = 16000
    dur = 1.0
    t = np.linspace(0, dur, int(sample_rate * dur), endpoint=False)
    modulation = 0.5 * (1.0 + np.sin(2 * np.pi * 5 * t))
    carrier = np.sin(2 * np.pi * 350 * t) * 0.25
    audio = (carrier * modulation).astype(np.float32)

    res = AudioEventDetector.analyze('', audio, sample_rate=sample_rate)
    assert res.event_type == AudioEventType.LAUGHTER
    assert res.is_isolated_event is True


def test_acoustic_sigh_detection() -> None:
    sample_rate = 16000
    dur = 0.9
    t = np.linspace(0, dur, int(sample_rate * dur), endpoint=False)
    envelope = np.exp(-2.5 * t)
    noise = np.random.normal(0, 0.02, len(t))
    audio = (noise * envelope).astype(np.float32)

    res = AudioEventDetector.analyze('', audio, sample_rate=sample_rate)
    assert res.event_type == AudioEventType.SIGH
    assert res.is_isolated_event is True


def test_isolated_events_never_trigger_commands() -> None:
    engine = NaturalLanguageIntentEngine()

    for event_text in ['[cough]', '*cough*', '[sneeze]', '[laughter]', 'haha', '*sigh*', '[throat clearing]']:
        res = AudioEventDetector.analyze(event_text)
        assert res.is_isolated_event is True
        action = engine.parse(res.clean_text)
        assert action.intent == CanonicalIntent.GENERAL_CONVERSATION


def test_command_plus_cough_preserves_command() -> None:
    engine = NaturalLanguageIntentEngine()

    res = AudioEventDetector.analyze('Nova, open Telegram [cough]')
    assert res.event_type == AudioEventType.COUGH
    assert res.clean_text == 'Nova, open Telegram'

    action = engine.parse(res.clean_text)
    assert action.intent == CanonicalIntent.LAUNCH_APP
    assert action.parameters.get('app_name', '').lower() == 'telegram'


def test_command_plus_laughter_preserves_command() -> None:
    engine = NaturalLanguageIntentEngine()

    res = AudioEventDetector.analyze('Nova Telegram open kar do [laughter]')
    assert res.event_type == AudioEventType.LAUGHTER
    assert res.clean_text == 'Nova Telegram open kar do'

    action = engine.parse(res.clean_text)
    assert action.intent == CanonicalIntent.LAUNCH_APP
    assert action.parameters.get('app_name', '').lower() == 'telegram'


def test_volume_command_plus_cough() -> None:
    engine = NaturalLanguageIntentEngine()

    res = AudioEventDetector.analyze('Nova volume thoda badha do *cough*')
    assert res.event_type == AudioEventType.COUGH
    assert res.clean_text == 'Nova volume thoda badha do'

    action = engine.parse(res.clean_text)
    assert action.intent == CanonicalIntent.CONTROL_VOLUME
    assert action.parameters.get('action') == 'increase'


def test_screenshot_command_preserved() -> None:
    engine = NaturalLanguageIntentEngine()

    action = engine.parse('Nova take a screenshot')
    assert action.intent == CanonicalIntent.SCREEN_CAPTURE


def test_hinglish_conversations_classified_as_conversation() -> None:
    engine = NaturalLanguageIntentEngine()

    hinglish_queries = [
        'Nova aaj college mein bahut thak gaya hoon.',
        'Nova main abhi college se aaya hoon.',
        'Nova ye recursion samajh nahi aa rahi.',
        'Nova yaar ye bug solve nahi ho raha.',
        'Nova mujhe ye code samjha do.',
        'Nova I was studying DSA aur ye topic samajh nahi aa raha.',
        'Nova kal mera exam hai and I am not prepared.',
        'Nova mujhe kal college jaana hai.',
        'Nova ye kya ho raha hai?',
        'Nova mera code run nahi ho raha.',
        'Nova mujhe batao Bluetooth kyun nahi chal raha.',
        'Nova aaj college mein pura din class thi.',
        'Nova yaar ye bug bahut irritate kar raha hai.',
        'Nova kal exam hai and mujhe kuch bhi yaad nahi hai.',
    ]

    for q in hinglish_queries:
        action = engine.parse(q)
        assert action.intent == CanonicalIntent.GENERAL_CONVERSATION, f'Failed for "{q}": got {action.intent}'


def test_english_conversations_and_commands() -> None:
    engine = NaturalLanguageIntentEngine()

    assert engine.parse('Nova how are you?').intent == CanonicalIntent.GENERAL_CONVERSATION
    assert engine.parse('Nova explain binary search.').intent == CanonicalIntent.GENERAL_CONVERSATION
    assert engine.parse('Nova I finally solved the bug.').intent == CanonicalIntent.GENERAL_CONVERSATION

    act_tg = engine.parse('Nova open Telegram.')
    assert act_tg.intent == CanonicalIntent.LAUNCH_APP
    assert act_tg.parameters.get('app_name', '').lower() == 'telegram'

    act_vol = engine.parse('Nova increase the volume.')
    assert act_vol.intent == CanonicalIntent.CONTROL_VOLUME
    assert act_vol.parameters.get('action') == 'increase'


def test_stt_language_defaults_to_auto() -> None:
    assert settings.stt_language == 'auto'


def test_transcription_manager_defaults_to_auto_language() -> None:
    manager = TranscriptionManager()
    assert manager.language == 'auto'


def test_domain_prompt_contains_rich_hinglish_terms() -> None:
    for term in ['college', 'exam', 'thak gaya', 'recursion', 'dsa', 'samjha do', 'kar do', 'kholo', 'Telegram']:
        assert term.lower() in ASSISTANT_DOMAIN_PROMPT.lower(), f'Term "{term}" missing from ASSISTANT_DOMAIN_PROMPT'

    for hotword in ['telegram', 'recursion', 'dsa', 'thak gaya', 'college', 'exam', 'samjha do']:
        assert hotword in ASSISTANT_HOTWORDS, f'Hotword "{hotword}" missing from ASSISTANT_HOTWORDS'


def test_tts_emoji_sanitization_integrity() -> None:
    cleaned1 = clean_text_for_speech('Yesss 😂 finally!')
    assert cleaned1 == 'Yesss, finally!'

    cleaned2 = clean_text_for_speech('Haha 😂 what happened?')
    assert cleaned2 == 'Haha, what happened?'

    cleaned3 = clean_text_for_speech('That was crazy ❤️')
    assert cleaned3 == 'That was crazy'

    assert '😂' not in cleaned1
    assert 'haha' not in cleaned1.lower()


def test_turn_sequence_state_isolation() -> None:
    """Verify Section 31 State Isolation:

    1. 'Nova, play some music.' -> PLAY_MEDIA
    2. Then laugh/cough -> Isolated event (care, no action)
    3. Then 'Nova, how are you?' -> GENERAL_CONVERSATION
    4. Then 'Nova, open Telegram.' -> LAUNCH_APP (Telegram)
    Verify no stale intent or cross-turn inheritance.
    """
    engine = NaturalLanguageIntentEngine()

    # Turn 1: Music command
    act1 = engine.parse("Nova, play some music.")
    assert act1.intent == CanonicalIntent.PLAY_MEDIA

    # Turn 2: Non-speech event alone
    res2 = AudioEventDetector.analyze("[laughter]")
    assert res2.is_isolated_event is True
    # Isolated non-speech yields empty clean_text -> GENERAL_CONVERSATION, not music
    act2 = engine.parse(res2.clean_text)
    assert act2.intent == CanonicalIntent.GENERAL_CONVERSATION
    assert act2.intent != CanonicalIntent.PLAY_MEDIA

    # Turn 3: Casual conversational query
    act3 = engine.parse("Nova, how are you?")
    assert act3.intent == CanonicalIntent.GENERAL_CONVERSATION

    # Turn 4: App launch
    act4 = engine.parse("Nova, open Telegram.")
    assert act4.intent == CanonicalIntent.LAUNCH_APP
    assert act4.parameters.get("app_name", "").lower() == "telegram"

