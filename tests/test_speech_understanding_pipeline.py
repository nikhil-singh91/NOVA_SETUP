"""Comprehensive test suite for NOVA's robust context-aware speech understanding pipeline."""

import unittest

from intent.engine import NaturalLanguageIntentEngine
from intent.matcher import LinguisticIntentMatcher
from intent.models import CanonicalIntent
from intent.normalizer import TextNormalizer
from ui.health_checker import DashboardStatsManager
from voice.state import TranscriptionResult


class TestSpeechUnderstandingPipeline(unittest.TestCase):
    """Verifies that speech recognition mishearings and natural command variations are accurately resolved."""

    def setUp(self):
        self.normalizer = TextNormalizer()
        self.engine = NaturalLanguageIntentEngine()
        self.matcher = LinguisticIntentMatcher()
        DashboardStatsManager.clear_logs()

    # -------------------------------------------------------------------------
    # 1. Disambiguation Tests: 'Right' vs 'Write'
    # -------------------------------------------------------------------------

    def test_write_icpc_with_answer_direct(self):
        """User says: 'write what is ICPC with answer' -> matches WRITE intent."""
        phrase = "write what is ICPC with answer"
        action = self.engine.parse(phrase)
        self.assertEqual(action.intent, CanonicalIntent.GENERATE_AND_WRITE_DOCUMENT)
        self.assertIn("what is icpc with answer", action.parameters["topic"].lower())

    def test_asr_mishearing_right_what_is_icpc(self):
        """ASR produces: 'Right? What is ICPC with Answers?' -> Disambiguated to WRITE."""
        phrase = "Right? What is ICPC with Answers?"
        norm = self.normalizer.normalize(phrase)
        self.assertEqual(norm.raw, phrase)
        self.assertTrue(norm.disambiguated.startswith("write"))
        self.assertIn("icpc", norm.disambiguated.lower())

        action = self.engine.parse(phrase)
        self.assertEqual(action.intent, CanonicalIntent.GENERATE_AND_WRITE_DOCUMENT)
        self.assertIn("icpc", action.parameters["topic"].lower())

    def test_asr_mishearing_right_bubble_sort_code(self):
        """ASR produces: 'Right bubble sort code in notepad' -> Disambiguated to WRITE with NOTEPAD."""
        phrase = "Right bubble sort code in notepad"
        action = self.engine.parse(phrase)
        self.assertEqual(action.intent, CanonicalIntent.GENERATE_AND_WRITE_DOCUMENT)
        self.assertIn(action.parameters.get("destination"), ("NOTEPAD", "Notepad/TextEdit"))

    def test_conversational_right_is_never_converted(self):
        """User says: 'what is right and wrong?' -> Must NOT convert 'right' to 'write'."""
        phrase = "what is right and wrong?"
        norm = self.normalizer.normalize(phrase)
        self.assertNotIn("write", norm.cleaned_lower)
        self.assertIn("right and wrong", norm.cleaned_lower)

        action = self.engine.parse(phrase)
        self.assertEqual(action.intent, CanonicalIntent.GENERAL_CONVERSATION)

    def test_conversational_right_now_is_never_converted(self):
        """User says: 'right now' -> Must NOT convert 'right' to 'write'."""
        phrase = "right now"
        norm = self.normalizer.normalize(phrase)
        self.assertNotIn("write", norm.cleaned_lower)
        self.assertEqual(norm.cleaned_lower, "right now")

        action = self.engine.parse(phrase)
        self.assertEqual(action.intent, CanonicalIntent.GENERAL_CONVERSATION)

    def test_conversational_what_is_love(self):
        """User says: 'what is love?' -> Must remain general conversation."""
        phrase = "what is love?"
        action = self.engine.parse(phrase)
        self.assertEqual(action.intent, CanonicalIntent.GENERAL_CONVERSATION)

    # -------------------------------------------------------------------------
    # 2. Proper Noun & Entity Resolution in Media: 'Le Parwati' -> 'Parvati'
    # -------------------------------------------------------------------------

    def test_play_parvati_song_direct(self):
        """User says: 'play Parvati song' -> PLAY_SPECIFIC_SONG / PLAY_MEDIA with query 'Parvati song'."""
        phrase = "play Parvati song"
        action = self.engine.parse(phrase)
        self.assertIn(action.intent, (CanonicalIntent.PLAY_MEDIA, CanonicalIntent.PLAY_SPECIFIC_SONG))
        self.assertIn("parvati", action.parameters.get("query", "").lower())

    def test_asr_mishearing_le_parwati_song(self):
        """ASR produces: 'Le Parwati Song' -> Disambiguated to PLAY_SPECIFIC_SONG / PLAY_MEDIA with Parvati entity."""
        phrase = "Le Parwati Song"
        action = self.engine.parse(phrase)
        self.assertIn(action.intent, (CanonicalIntent.PLAY_MEDIA, CanonicalIntent.PLAY_SPECIFIC_SONG))
        self.assertTrue("parvati" in action.parameters.get("query", "").lower() or "parwati" in action.parameters.get("query", "").lower())

    def test_play_a_song(self):
        """User says: 'play a song' -> LISTEN_TO_MUSIC / PLAY_MEDIA."""
        phrase = "play a song"
        action = self.engine.parse(phrase)
        self.assertIn(action.intent, (CanonicalIntent.LISTEN_TO_MUSIC, CanonicalIntent.PLAY_MEDIA))

    # -------------------------------------------------------------------------
    # 3. Core System & Mac Control Regressions
    # -------------------------------------------------------------------------

    def test_open_telegram(self):
        """User says: 'open Telegram' -> LAUNCH_APP with Telegram."""
        phrase = "open Telegram"
        action = self.engine.parse(phrase)
        self.assertEqual(action.intent, CanonicalIntent.LAUNCH_APP)
        self.assertEqual(action.parameters["app_name"], "Telegram")

    def test_open_youtube(self):
        """User says: 'open YouTube' -> Navigation/Website."""
        phrase = "open YouTube"
        action = self.engine.parse(phrase)
        self.assertIn(action.intent, (CanonicalIntent.OPEN_WEBSITE, CanonicalIntent.LAUNCH_APP))

    def test_volume_commands(self):
        """Volume adjustment commands parse correctly with numeric targets."""
        # increase volume
        a1 = self.engine.parse("increase volume")
        self.assertEqual(a1.intent, CanonicalIntent.CONTROL_VOLUME)
        self.assertEqual(a1.parameters.get("action"), "increase")

        # increase volume to 70 percent
        a2 = self.engine.parse("increase volume to 70 percent")
        self.assertEqual(a2.intent, CanonicalIntent.CONTROL_VOLUME)
        self.assertEqual(a2.parameters.get("value"), 70)

        # set volume to 100 percent
        a3 = self.engine.parse("set volume to 100 percent")
        self.assertEqual(a3.intent, CanonicalIntent.CONTROL_VOLUME)
        self.assertEqual(a3.parameters.get("action"), "set")
        self.assertEqual(a3.parameters.get("value"), 100)

    def test_brightness_commands(self):
        """Brightness commands parse correctly with numeric targets."""
        # increase brightness
        a1 = self.engine.parse("increase brightness")
        self.assertEqual(a1.intent, CanonicalIntent.CONTROL_BRIGHTNESS)
        self.assertEqual(a1.parameters.get("action"), "increase")

        # set brightness to 80 percent
        a2 = self.engine.parse("set brightness to 80 percent")
        self.assertEqual(a2.intent, CanonicalIntent.CONTROL_BRIGHTNESS)
        self.assertEqual(a2.parameters.get("action"), "set")
        self.assertEqual(a2.parameters.get("value"), 80)

    def test_scroll_commands(self):
        """Scroll navigation commands."""
        a1 = self.engine.parse("scroll down")
        self.assertEqual(a1.intent, CanonicalIntent.SCROLL_DOWN)

        a2 = self.engine.parse("scroll to the bottom")
        self.assertEqual(a2.intent, CanonicalIntent.SCROLL_TO_BOTTOM)

        a3 = self.engine.parse("scroll to the top")
        self.assertEqual(a3.intent, CanonicalIntent.SCROLL_TO_TOP)

    def test_wifi_commands(self):
        """Wi-Fi status and network queries."""
        a1 = self.engine.parse("check wifi")
        self.assertEqual(a1.intent, CanonicalIntent.CONTROL_WIFI)

        a2 = self.engine.parse("which wifi am i connected to")
        self.assertEqual(a2.intent, CanonicalIntent.CONTROL_WIFI)

    # -------------------------------------------------------------------------
    # 4. Activity Feed Step Sequence: YOU -> HEARD -> UNDERSTOOD -> ACTION -> VERIFY -> NOVA
    # -------------------------------------------------------------------------

    def test_activity_feed_step_sequence(self):
        """Verify the complete interactive logging sequence."""
        user_query = "write what is ICPC with answer"
        raw_heard = "Right? What is ICPC with Answers?"

        inter = DashboardStatsManager.start_interaction(user_query, source="voice", interaction_id="turn_test_123")
        DashboardStatsManager.record_heard(raw_heard)
        DashboardStatsManager.record_understood(
            "WRITE",
            details={"Destination": "NOTEPAD", "Content": '"What is ICPC with answer"', "Confidence": "92%"},
        )
        DashboardStatsManager.record_action("Writing content to Notepad")
        DashboardStatsManager.record_verify("Notepad content written successfully", success=True)
        DashboardStatsManager.record_nova("Done Boss. I wrote it in Notepad.")
        DashboardStatsManager.record_result("Written to Notepad", success=True)

        categories = [s.category for s in inter.steps]
        self.assertEqual(categories, ["YOU", "HEARD", "UNDERSTOOD", "ACTION", "VERIFY", "NOVA", "RESULT"])
        self.assertEqual(inter.raw_heard, raw_heard)
        self.assertEqual(inter.verified_state, "Notepad content written successfully")

    # -------------------------------------------------------------------------
    # 5. TranscriptionResult Multi-Level Transcript Preservation
    # -------------------------------------------------------------------------

    def test_transcription_result_preservation(self):
        """Verify raw_text, normalized_text, and alternatives are preserved."""
        res = TranscriptionResult(
            text="write bubble sort code",
            raw_text="Right bubble sort code",
            normalized_text="write bubble sort code",
            confidence=0.88,
            alternatives=["Right bubble sort code", "Write bubble sort code"],
        )
        self.assertEqual(res.raw_text, "Right bubble sort code")
        self.assertEqual(res.text, "write bubble sort code")
        self.assertEqual(len(res.alternatives), 2)
        self.assertTrue(res.success)

    def test_write_hello_world_in_notepad(self):
        """User says: 'write hello world in notepad' -> WRITE with content 'hello world' and destination 'NOTEPAD'."""
        phrase = "write hello world in notepad"
        action = self.engine.parse(phrase)
        self.assertEqual(action.intent, CanonicalIntent.GENERATE_AND_WRITE_DOCUMENT)
        self.assertEqual(action.parameters.get("content"), "hello world")
        self.assertEqual(action.parameters.get("destination"), "NOTEPAD")

    def test_multi_candidate_hypothesis_evaluation(self):
        """Engine evaluates candidate hypotheses and picks the valid command intent."""
        candidates = ["Right? What is ICPC with Answers?", "Write what is ICPC with answer"]
        action = self.engine.parse(candidates[0], candidates=candidates)
        self.assertEqual(action.intent, CanonicalIntent.GENERATE_AND_WRITE_DOCUMENT)
        self.assertIn("icpc", action.parameters["topic"].lower())

    def test_entity_resolver_apps_and_phonetics(self):
        """EntityResolver resolves app names and phonetic variations."""
        from intent.entity_resolver import EntityResolver
        res_app = EntityResolver.resolve_app_name("telegram app")
        self.assertIsNotNone(res_app)
        self.assertEqual(res_app.canonical_name, "Telegram")

        # Phonetic romanization w <-> v
        norm_song = EntityResolver.resolve_proper_noun_phonetics("Parwati")
        self.assertEqual(norm_song, "Parvati")

        # Media slot extraction
        media_q, conf = EntityResolver.extract_media_entity("play Parvati song")
        self.assertEqual(media_q, "Parvati song")
        self.assertGreaterEqual(conf, 0.85)

    def test_provider_status_classification(self):
        """classify_provider_error distinguishes QUOTA_EXCEEDED from RATE_LIMITED."""
        from providers.provider_manager import classify_provider_error

        status_quota, msg, _ = classify_provider_error(Exception("You exceeded your current quota, please check your plan"))
        self.assertEqual(status_quota, "QUOTA_EXCEEDED")

        status_rate, msg2, _ = classify_provider_error(Exception("HTTP 429 Too Many Requests: Rate limit exceeded"))
        self.assertEqual(status_rate, "RATE_LIMITED")

        status_auth, msg3, _ = classify_provider_error(Exception("HTTP 401 Unauthorized: Invalid API Key"))
        self.assertEqual(status_auth, "AUTH_ERROR")


if __name__ == "__main__":
    unittest.main()
