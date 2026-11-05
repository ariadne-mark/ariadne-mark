"""CPU video presets. Cadence is an engineering setting, not a legal threshold."""
from fractions import Fraction

DEFAULT_PROFILE = "economy_5s"
PROFILES = ("economy_5s", "economy_2s", "resilient")
LEGACY_PROFILES = ("fast",)
WINDOW = Fraction(1, 8)


def validate_profile(profile):
    if not isinstance(profile, str) or profile not in PROFILES + LEGACY_PROFILES:
        raise ValueError("video_profile must be economy_5s, economy_2s or resilient (fast is legacy)")
    return profile


def period_for(profile):
    validate_profile(profile)
    return {"economy_5s": 5, "economy_2s": 2}.get(profile)


class WindowSelector:
    """Select 125ms PTS windows, relative to the first presented frame.

    Always include the first observed frame in each occupied period: VFR/low
    FPS can otherwise step completely over a nominal 125ms window. No frames
    or timestamps are inserted, and gaps with no frames are not invented.
    """

    def __init__(self, profile):
        self.period = period_for(profile)
        self.origin = None
        self.last_window = None

    def select(self, timestamp):
        timestamp = Fraction(timestamp)
        if self.origin is None:
            self.origin = timestamp
        relative = timestamp - self.origin
        if relative < 0:
            raise ValueError("Video timeline precedes its first frame")
        if self.period is None:
            return True, None
        window = int(relative // self.period)
        selected = window != self.last_window or relative % self.period < WINDOW
        self.last_window = window
        return selected, window
