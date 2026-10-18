"""Wake engine for HAROID.

Handles:
1. 2-Clap transient detection with dynamic noise-floor tracking.
2. Wake phrase ("Hey HAROID", "Hay Haroid", "Haroid", "Hey Jarvis") and voice detection.
3. State machine transitioning between STANDBY, AWAITING_WAKE_PHRASE, and ACTIVE.
4. Activation audio cues and greeting synthesizers.
"""

import math
import os
import sys
import struct
import threading
import time
from enum import Enum
from pathlib import Path
from typing import Callable, Optional

import numpy as np

CHANNELS = 1
SAMPLE_RATE = 16000
CHUNK_SIZE = 1024

CLAP_REQUIRED_COUNT = 2
CLAP_MAX_GAP_SECONDS = 4.0
CLAP_COOLDOWN_SECONDS = 0.22
WAKE_PHRASE_WINDOW_SECONDS = 6.5

WAKE_PHRASES = {
    "hey haroid", "hay haroid", "haroid", "hey horoid", "hay horoid",
    "hey jarvis", "jarvis", "hello haroid", "hi haroid", "ok haroid",
    "okay haroid", "yo haroid", "wake up haroid", "wake up",
}

SLEEP_PHRASES = {
    "go to sleep", "standby", "haroid sleep", "sleep haroid", "minimize to tray",
    "enter standby", "sleep mode", "goodnight haroid",
}


class WakeState(Enum):
    STANDBY = "STANDBY"
    AWAITING_WAKE_PHRASE = "AWAITING_WAKE_PHRASE"
    ACTIVE = "ACTIVE"


def play_wake_chime(sample_rate: int = 24000):
    """Play a short high-tech futuristic 2-tone chime to signal wake cue."""
    try:
        import sounddevice as sd
        duration1, duration2 = 0.09, 0.14
        freq1, freq2 = 880.0, 1320.0  # A5 -> E6
        
        t1 = np.linspace(0, duration1, int(sample_rate * duration1), False)
        t2 = np.linspace(0, duration2, int(sample_rate * duration2), False)
        
        # Smooth envelopes
        env1 = np.sin(np.pi * np.linspace(0, 1, len(t1)))
        env2 = np.sin(np.pi * np.linspace(0, 1, len(t2)))
        
        tone1 = (0.28 * np.sin(2 * np.pi * freq1 * t1) * env1).astype(np.float32)
        tone2 = (0.35 * np.sin(2 * np.pi * freq2 * t2) * env2).astype(np.float32)
        
        gap = np.zeros(int(sample_rate * 0.02), dtype=np.float32)
        chime = np.concatenate([tone1, gap, tone2])
        
        sd.play(chime, samplerate=sample_rate, blocking=False)
    except Exception:
        # Fallback for Windows standard beep if sounddevice is busy
        if sys.platform == "win32":
            try:
                import winsound
                winsound.Beep(880, 100)
                winsound.Beep(1320, 150)
            except Exception:
                pass


def play_sleep_chime(sample_rate: int = 24000):
    """Play a subtle downward tone signaling return to standby."""
    try:
        import sounddevice as sd
        duration = 0.18
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        env = np.cos(np.pi * 0.5 * np.linspace(0, 1, len(t)))
        # Frequency ramp 1100Hz down to 550Hz
        freq = np.linspace(1100, 550, len(t))
        tone = (0.25 * np.sin(2 * np.pi * freq * t) * env).astype(np.float32)
        sd.play(tone, samplerate=sample_rate, blocking=False)
    except Exception:
        pass


class WakeEngine:
    """Manages continuous background standby, 2-clap gate, and voice wake word activation."""

    def __init__(
        self,
        on_wake: Optional[Callable[[], None]] = None,
        on_claps: Optional[Callable[[int], None]] = None,
        on_standby: Optional[Callable[[], None]] = None,
        on_state_change: Optional[Callable[[WakeState], None]] = None,
    ):
        self.on_wake = on_wake
        self.on_claps = on_claps
        self.on_standby = on_standby
        self.on_state_change = on_state_change

        self.state = WakeState.STANDBY
        self._lock = threading.Lock()
        self._clap_times: list[float] = []
        self._last_clap_at: float = 0.0
        self._noise_floor: float = 0.008
        self._awaiting_started_at: float = 0.0
        self._running = False
        self._stream = None

    def set_state(self, new_state: WakeState):
        with self._lock:
            old_state = self.state
            self.state = new_state
        if old_state != new_state and self.on_state_change:
            try:
                self.on_state_change(new_state)
            except Exception:
                pass

    def is_standby(self) -> bool:
        with self._lock:
            return self.state == WakeState.STANDBY

    def is_awaiting_phrase(self) -> bool:
        with self._lock:
            return self.state == WakeState.AWAITING_WAKE_PHRASE

    def is_active(self) -> bool:
        with self._lock:
            return self.state == WakeState.ACTIVE

    def enter_standby(self, notify: bool = True):
        """Put HAROID into background standby mode."""
        self.set_state(WakeState.STANDBY)
        with self._lock:
            self._clap_times = []
            self._last_clap_at = 0.0
        if notify:
            threading.Thread(target=play_sleep_chime, daemon=True).start()
        if self.on_standby:
            try:
                self.on_standby()
            except Exception:
                pass

    def trigger_wake(self, greeting_text: str = "Online and ready, sir. How can I assist you?"):
        """Fully wake HAROID and activate live interaction."""
        self.set_state(WakeState.ACTIVE)
        with self._lock:
            self._clap_times = []
        if self.on_wake:
            try:
                self.on_wake()
            except Exception:
                pass

    def process_audio_frame(self, indata: np.ndarray) -> tuple[bool, Optional[str]]:
        """Process an incoming PCM audio frame.

        Returns (wake_triggered: bool, event_type: str | None).
        """
        now = time.monotonic()
        samples = np.asarray(indata, dtype=np.float32).reshape(-1)
        if samples.size == 0:
            return False, None

        magnitude = np.abs(samples)
        rms = float(np.sqrt(np.mean(samples * samples)))
        peak = float(np.max(magnitude))

        with self._lock:
            current_state = self.state

        # Check timeout for AWAITING_WAKE_PHRASE
        if current_state == WakeState.AWAITING_WAKE_PHRASE:
            if now - self._awaiting_started_at > WAKE_PHRASE_WINDOW_SECONDS:
                self.enter_standby(notify=False)
                return False, "awaiting_timeout"

            # In awaiting state: detect if voice speech is present (RMS above speech threshold)
            speech_threshold = max(0.04, self._noise_floor * 3.5)
            if rms >= speech_threshold:
                # User is speaking immediately after 2 claps! Trigger full wake
                self.trigger_wake()
                return True, "voice_after_claps"

        # Update noise floor during low energy frames
        if rms < max(0.08, self._noise_floor * 6.0):
            self._noise_floor = (self._noise_floor * 0.96) + (rms * 0.04)

        if current_state == WakeState.STANDBY:
            # Clap transient detection
            threshold = max(0.100, self._noise_floor * 6.5)
            peak_threshold = max(0.35, self._noise_floor * 15.0)
            crest_factor = peak / max(rms, 1e-6)

            is_transient = crest_factor >= 2.20 and rms >= threshold
            is_loud = rms >= max(0.28, self._noise_floor * 15.0)

            if (
                peak >= peak_threshold
                and (is_transient or is_loud)
                and (now - self._last_clap_at >= CLAP_COOLDOWN_SECONDS)
            ):
                if self._clap_times and (now - self._clap_times[-1] > CLAP_MAX_GAP_SECONDS):
                    self._clap_times = []

                self._clap_times.append(now)
                self._last_clap_at = now
                clap_count = len(self._clap_times)

                if self.on_claps:
                    try:
                        self.on_claps(clap_count)
                    except Exception:
                        pass

                if clap_count >= CLAP_REQUIRED_COUNT:
                    self._clap_times = []
                    self._awaiting_started_at = now
                    self.set_state(WakeState.AWAITING_WAKE_PHRASE)
                    threading.Thread(target=play_wake_chime, daemon=True).start()
                    return False, "two_claps_detected"

        return False, None

    def check_transcript_for_wake(self, text: str) -> bool:
        """Check if incoming transcript text contains wake or sleep phrases."""
        if not text:
            return False
        clean = " ".join(text.lower().strip().split())

        # Check sleep phrases
        for phrase in SLEEP_PHRASES:
            if phrase in clean:
                self.enter_standby(notify=True)
                return False

        # Check wake phrases
        for phrase in WAKE_PHRASES:
            if phrase in clean:
                self.trigger_wake()
                return True

        # If we are currently awaiting wake phrase, any substantial spoken text wakes HAROID
        if self.is_awaiting_phrase() and len(clean.split()) >= 1:
            self.trigger_wake()
            return True

        return False
