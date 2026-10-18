import unittest
import time
import numpy as np
from unittest.mock import MagicMock

from core.wake_engine import WakeEngine, WakeState, CLAP_COOLDOWN_SECONDS


class WakeEngineTests(unittest.TestCase):

    def test_initial_state_is_standby(self):
        engine = WakeEngine()
        self.assertEqual(engine.state, WakeState.STANDBY)
        self.assertTrue(engine.is_standby())

    def test_two_claps_transition_to_awaiting_wake_phrase(self):
        wake_called = MagicMock()
        claps_called = MagicMock()
        engine = WakeEngine(on_wake=wake_called, on_claps=claps_called)

        # Generate sharp transient clap frame (peak = 0.8, crest factor high)
        clap_frame = np.zeros((512, 1), dtype=np.float32)
        clap_frame[10:20] = 0.85

        # First clap
        triggered, event = engine.process_audio_frame(clap_frame)
        self.assertFalse(triggered)
        self.assertEqual(engine.state, WakeState.STANDBY)
        claps_called.assert_called_with(1)

        # Wait past cooldown
        time.sleep(CLAP_COOLDOWN_SECONDS + 0.05)

        # Second clap
        triggered, event = engine.process_audio_frame(clap_frame)
        self.assertFalse(triggered)
        self.assertEqual(event, "two_claps_detected")
        self.assertEqual(engine.state, WakeState.AWAITING_WAKE_PHRASE)
        claps_called.assert_called_with(2)
        wake_called.assert_not_called()

    def test_voice_in_awaiting_state_triggers_wake(self):
        wake_called = MagicMock()
        engine = WakeEngine(on_wake=wake_called)

        # Set state to AWAITING_WAKE_PHRASE
        engine.set_state(WakeState.AWAITING_WAKE_PHRASE)
        engine._awaiting_started_at = time.monotonic()

        # Speech frame (sustained RMS)
        speech_frame = np.full((512, 1), 0.12, dtype=np.float32)
        triggered, event = engine.process_audio_frame(speech_frame)

        self.assertTrue(triggered)
        self.assertEqual(event, "voice_after_claps")
        self.assertEqual(engine.state, WakeState.ACTIVE)
        wake_called.assert_called_once()

    def test_transcript_wake_phrases(self):
        wake_called = MagicMock()
        engine = WakeEngine(on_wake=wake_called)

        self.assertTrue(engine.check_transcript_for_wake("Hey Haroid"))
        self.assertEqual(engine.state, WakeState.ACTIVE)
        wake_called.assert_called_once()

        self.assertTrue(engine.check_transcript_for_wake("hay haroid can you help me"))
        self.assertTrue(engine.check_transcript_for_wake("Hey Jarvis what is the weather"))

    def test_transcript_sleep_phrases(self):
        standby_called = MagicMock()
        engine = WakeEngine(on_standby=standby_called)
        engine.set_state(WakeState.ACTIVE)

        self.assertFalse(engine.check_transcript_for_wake("Please go to sleep now"))
        self.assertEqual(engine.state, WakeState.STANDBY)
        standby_called.assert_called_once()

    def test_awaiting_state_times_out_back_to_standby(self):
        engine = WakeEngine()
        engine.set_state(WakeState.AWAITING_WAKE_PHRASE)
        # Simulate started 10 seconds ago (window is 6.5s)
        engine._awaiting_started_at = time.monotonic() - 10.0

        silent_frame = np.zeros((512, 1), dtype=np.float32)
        triggered, event = engine.process_audio_frame(silent_frame)

        self.assertFalse(triggered)
        self.assertEqual(event, "awaiting_timeout")
        self.assertEqual(engine.state, WakeState.STANDBY)


if __name__ == "__main__":
    unittest.main()
