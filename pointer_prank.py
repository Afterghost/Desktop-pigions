"""Short-lived mouse-shake detection and reversible Windows cursor hiding."""

from collections import deque
import math
import sys


class MouseShake:
    def __init__(self, duration=1.0, distance=120, reversals=2):
        self.duration = duration
        self.distance = distance
        self.reversal_limit = reversals
        self.reset()

    def reset(self):
        self.points = deque()

    def move(self, x, y, now):
        while self.points and now - self.points[0][2] > self.duration:
            self.points.popleft()
        if self.points and now <= self.points[-1][2]:
            self.reset()
        if self.points:
            self.points.append((x, y, now))
            path_length = 0
            reversals = 0
            last_direction = None
            last_motion = None
            previous = self.points[0]
            for point in list(self.points)[1:]:
                dx, dy = point[0] - previous[0], point[1] - previous[1]
                distance = math.hypot(dx, dy)
                previous = point
                if distance < 8:
                    continue
                direction = (dx / distance, dy / distance)
                if (last_direction is not None
                        and direction[0] * last_direction[0]
                        + direction[1] * last_direction[1] < -0.5):
                    reversals += 1
                last_direction = direction
                path_length += distance
                last_motion = (dx, dy)
            if path_length >= self.distance and reversals >= self.reversal_limit:
                self.reset()
                self.points.append((x, y, now))
                return last_motion
        else:
            self.points.append((x, y, now))
        return None


class TemporaryCursorHide:
    """Hide the system cursor briefly and reverse only this instance's ShowCursor calls."""

    CURSOR_SHOWING = 0x00000001

    def __init__(self):
        self._user32 = None
        self._hide_calls = 0
        if sys.platform == "win32":
            import ctypes

            self._ctypes = ctypes
            self._user32 = ctypes.windll.user32

    @property
    def supported(self):
        return self._user32 is not None

    def _cursor_visible(self):
        class CursorInfo(self._ctypes.Structure):
            _fields_ = (
                ("cbSize", self._ctypes.c_uint),
                ("flags", self._ctypes.c_uint),
                ("cursor", self._ctypes.c_void_p),
                ("x", self._ctypes.c_long),
                ("y", self._ctypes.c_long),
            )

        info = CursorInfo()
        info.cbSize = self._ctypes.sizeof(info)
        return bool(self._user32.GetCursorInfo(self._ctypes.byref(info))
                    and info.flags & self.CURSOR_SHOWING)

    def hide(self):
        if not self.supported or self._hide_calls or not self._cursor_visible():
            return False
        for _ in range(16):
            self._user32.ShowCursor(False)
            self._hide_calls += 1
            if not self._cursor_visible():
                return True
        self.show()
        return False

    def show(self):
        if self._user32 is None:
            return
        for _ in range(self._hide_calls):
            self._user32.ShowCursor(True)
        self._hide_calls = 0
