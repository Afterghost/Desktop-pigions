"""Desktop Pigeon: python interaction_app.py [--preview].

Windows uses a transparent, always-on-top, non-activating desktop overlay.
Other platforms (or unavailable transparency) use a normal windowed preview.
Drag food or a feather from the soft edge tray onto the desktop. Click the
edge tab or pigeon to open the tray; Escape cancels a drag or closes the tray.
In preview, Escape with the tray closed exits. The tray also has a Quit button.
Paper tears are temporary cosmetic drawings: no wallpaper, screenshots, files
or desktop settings are read or changed. "Smooth it out" clears them instantly.
State is in memory only. Food costs in config are not charged: no economy yet.
"""

import argparse
import ctypes
from ctypes import wintypes
import math
import sys
import time
try:
    import tkinter as tk
except ImportError:
    tk = None

import config
from interaction_pigeon import Pigeon, EAT_DURATION, PLAY_DURATION, TEAR_LIFETIME, MAX_ITEMS


KEY_COLOR = "#ff00ff"
PANEL = "#ecf1eb"
INK = "#253a3e"
TRAY_WIDTH = 286
LABELS = {
    "seed_mix": "Seed mix",
    "sunflower_seeds": "Sunflower seeds",
    "french_fries": "French fries",
    "mystery_crumbs": "Mystery crumbs",
    "golden_corn": "Golden corn",
    "feather": "Play feather",
}


class WindowsOverlay:
    """Pointer-sized Win32 bindings; switch click-through from global pointer."""

    def __init__(self, root):
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.user32 = user32
        pointer = ctypes.c_ssize_t
        if ctypes.sizeof(ctypes.c_void_p) == 8:
            get_style = user32.GetWindowLongPtrW
            set_style = user32.SetWindowLongPtrW
        else:
            get_style = user32.GetWindowLongW
            set_style = user32.SetWindowLongW
        get_style.argtypes = [wintypes.HWND, ctypes.c_int]
        get_style.restype = pointer
        set_style.argtypes = [wintypes.HWND, ctypes.c_int, pointer]
        set_style.restype = pointer
        self.get_style, self.set_style = get_style, set_style
        user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
        user32.GetAncestor.restype = wintypes.HWND
        user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
        user32.GetCursorPos.restype = wintypes.BOOL
        user32.ScreenToClient.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
        user32.ScreenToClient.restype = wintypes.BOOL
        user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
        user32.GetAsyncKeyState.restype = ctypes.c_short
        user32.SetLayeredWindowAttributes.argtypes = [
            wintypes.HWND, wintypes.DWORD, wintypes.BYTE, wintypes.DWORD]
        user32.SetLayeredWindowAttributes.restype = wintypes.BOOL
        user32.SetWindowPos.argtypes = [
            wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
            ctypes.c_int, ctypes.c_int, wintypes.UINT]
        user32.SetWindowPos.restype = wintypes.BOOL
        self.hwnd = user32.GetAncestor(root.winfo_id(), 2)
        if not self.hwnd:
            raise OSError("Could not locate overlay window")
        # Tk can explicitly activate its first mapped window, even with the
        # NOACTIVATE style. A thread-local CBT hook prevents that and Tk's
        # mouse-focus handling without touching any other application's focus.
        hook_proc = ctypes.WINFUNCTYPE(pointer, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
        user32.SetWindowsHookExW.argtypes = [ctypes.c_int, hook_proc, wintypes.HINSTANCE, wintypes.DWORD]
        user32.SetWindowsHookExW.restype = wintypes.HANDLE
        user32.CallNextHookEx.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
        user32.CallNextHookEx.restype = pointer
        user32.UnhookWindowsHookEx.argtypes = [wintypes.HANDLE]
        user32.UnhookWindowsHookEx.restype = wintypes.BOOL
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetCurrentThreadId.argtypes = []
        kernel32.GetCurrentThreadId.restype = wintypes.DWORD

        def no_activate(code, wparam, lparam):
            if code in (5, 9):  # HCBT_ACTIVATE / HCBT_SETFOCUS
                return 1
            return user32.CallNextHookEx(None, code, wparam, lparam)

        self.activation_proc = hook_proc(no_activate)
        self.activation_hook = user32.SetWindowsHookExW(
            5, self.activation_proc, None, kernel32.GetCurrentThreadId())
        if not self.activation_hook:
            raise ctypes.WinError(ctypes.get_last_error())
        self.original_style = get_style(self.hwnd, -20)
        self.style = self.original_style | 0x80000 | 0x08000000 | 0x80
        try:
            self._set_style(self.style)
            # COLORREF is 0x00bbggrr: magenta canvas pixels genuinely disappear.
            if not user32.SetLayeredWindowAttributes(self.hwnd, 0x00FF00FF, 255, 1):
                raise ctypes.WinError(ctypes.get_last_error())
            if not user32.SetWindowPos(self.hwnd, wintypes.HWND(-1), 0, 0, 0, 0, 0x13):
                raise ctypes.WinError(ctypes.get_last_error())
            self.click_through = False
            self.escape_down = False
            self.set_interactive(False)
        except OSError:
            self.restore()
            raise

    def _set_style(self, style):
        ctypes.set_last_error(0)
        previous = self.set_style(self.hwnd, -20, style)
        error = ctypes.get_last_error()
        if not previous and error:
            raise ctypes.WinError(error)

    def restore(self):
        try:
            self._set_style(self.original_style)
        finally:
            if self.activation_hook:
                self.user32.UnhookWindowsHookEx(self.activation_hook)
                self.activation_hook = None

    def refresh_window(self, root):
        """Tk may replace its native wrapper during the first mapping."""
        hwnd = self.user32.GetAncestor(root.winfo_id(), 2)
        if not hwnd:
            raise OSError("Could not locate mapped overlay window")
        if hwnd != self.hwnd:
            self.hwnd = hwnd
            self.original_style = self.get_style(hwnd, -20)
            self.style = self.original_style | 0x80000 | 0x08000000 | 0x80
        self._set_style(self.style | (0x20 if self.click_through else 0))
        if not self.user32.SetLayeredWindowAttributes(self.hwnd, 0x00FF00FF, 255, 1):
            raise ctypes.WinError(ctypes.get_last_error())
        if not self.user32.SetWindowPos(self.hwnd, wintypes.HWND(-1), 0, 0, 0, 0, 0x13):
            raise ctypes.WinError(ctypes.get_last_error())

    def set_interactive(self, interactive):
        click_through = not interactive
        if click_through != self.click_through:
            self._set_style(self.style | (0x20 if click_through else 0))
            self.click_through = click_through

    def pointer(self):
        point = wintypes.POINT()
        if (self.user32.GetCursorPos(ctypes.byref(point))
                and self.user32.ScreenToClient(self.hwnd, ctypes.byref(point))):
            return point.x, point.y
        return -1, -1

    def escape_pressed(self):
        down = bool(self.user32.GetAsyncKeyState(0x1B) & 0x8000)
        pressed = down and not self.escape_down
        self.escape_down = down
        return pressed


class App:
    def __init__(self, root, preview=False):
        self.root = root
        root.withdraw()
        self.preview = preview or sys.platform != "win32"
        self.native = None
        self.closed = False
        self.tray_open = True
        self.slide = 0.0
        self.drag = None
        self.pointer = (0, 0)
        self.regions = []
        self.notice = ""
        self.notice_until = 0.0
        root.title("Desktop Pigeon — preview" if self.preview else "Desktop Pigeon")
        root.protocol("WM_DELETE_WINDOW", self.close)
        if self.preview:
            root.geometry("960x640")
            root.minsize(400, 500)
        else:
            root.overrideredirect(True)
            root.geometry(f"{root.winfo_screenwidth()}x{root.winfo_screenheight()}+0+0")
            root.attributes("-topmost", True)
        self.canvas = tk.Canvas(root, bg="#b7c9c8" if self.preview else KEY_COLOR,
                                highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        root.update_idletasks()
        self.width, self.height = self.canvas.winfo_width(), self.canvas.winfo_height()
        self.bird = Pigeon(self.width, self.height)
        self.canvas.bind("<Configure>", self.resize)
        self.canvas.bind("<ButtonPress-1>", self.press)
        self.canvas.bind("<B1-Motion>", self.motion)
        self.canvas.bind("<ButtonRelease-1>", self.release)
        root.bind("<Escape>", self.escape)
        if not self.preview:
            try:
                root.attributes("-transparentcolor", KEY_COLOR)
                self.native = WindowsOverlay(root)
            except (OSError, tk.TclError, AttributeError) as error:
                self.fallback_preview(error)
        self.last_time = time.monotonic()
        self.draw()
        root.deiconify()
        root.update_idletasks()
        if self.native:
            try:
                self.native.refresh_window(root)
            except OSError as error:
                self.fallback_preview(error)
        self.timer = root.after(16, self.tick)

    def fallback_preview(self, error):
        print(f"Desktop transparency unavailable; using windowed preview: {error}", file=sys.stderr)
        if self.native:
            self.native.restore()
            self.native = None
        try:
            self.root.attributes("-transparentcolor", "")
        except tk.TclError:
            pass  # Unsupported transparency must not prevent the preview.
        self.root.overrideredirect(False)
        self.root.attributes("-topmost", False)
        self.preview = True
        self.root.title("Desktop Pigeon — preview")
        self.root.geometry("960x640")
        self.root.minsize(400, 500)
        self.canvas.configure(bg="#b7c9c8")

    def resize(self, event):
        self.width, self.height = event.width, event.height
        self.bird.resize(self.width, self.height)

    def close(self):
        if self.closed:
            return
        self.closed = True
        if hasattr(self, "timer"):
            self.root.after_cancel(self.timer)
        if self.native:
            self.native.restore()
        self.root.destroy()

    def escape(self, event=None):
        if self.drag:
            self.drag = None
        elif self.tray_open:
            self.tray_open = False
        elif self.preview:
            self.close()
        return "break"

    def hit(self, x, y):
        for name, rect in reversed(self.regions):
            left, top, right, bottom = rect
            if left <= x <= right and top <= y <= bottom:
                return name
        return None

    def press(self, event):
        name = self.hit(event.x, event.y)
        if name == "tab":
            self.tray_open = not self.tray_open
        elif name == "bird":
            self.tray_open = True
        elif name == "quit":
            self.close()
        elif name == "clear":
            self.bird.clear_effects()
        elif name in LABELS:
            self.drag = name
            self.pointer = (event.x, event.y)

    def motion(self, event):
        self.pointer = (event.x, event.y)

    def release(self, event):
        if not self.drag:
            return
        kind, self.drag = self.drag, None
        if (0 <= event.x < self.width and 0 <= event.y < self.height
                and self.hit(event.x, event.y) not in ("panel", "tab", "clear", "quit")
                and self.hit(event.x, event.y) not in LABELS):
            if not self.bird.place(kind, event.x, event.y):
                self.notice = f"Only {MAX_ITEMS} treats at a time — let the pigeon catch up!"
                self.notice_until = self.bird.clock + 4

    def tick(self):
        if self.closed:
            return
        now = time.monotonic()
        # Avoid teleporting after suspend or a stalled event loop.
        seconds = min(now - self.last_time, 0.1)
        self.last_time = now
        self.slide += ((1.0 if self.tray_open else 0.0) - self.slide) * min(1, seconds * 12)
        if abs(self.slide - (1 if self.tray_open else 0)) < 0.002:
            self.slide = float(self.tray_open)
        self.bird.update(seconds)
        self.draw()
        if self.native:
            try:
                self.pointer = self.native.pointer()
                self.native.set_interactive(bool(self.drag) or self.hit(*self.pointer) is not None)
                if self.native.escape_pressed() and (self.drag or self.tray_open):
                    self.escape()
            except OSError as error:
                self.fallback_preview(error)
        self.timer = self.root.after(16, self.tick)

    def text(self, x, y, text, **kwargs):
        self.canvas.create_text(x, y, text=text, fill=INK,
                                font=("Segoe UI", 10), **kwargs)

    def item(self, kind, x, y, ghost=False):
        c = self.canvas
        if kind == "feather":
            c.create_oval(x - 6, y - 17, x + 8, y + 9, fill="#c8a2d4", outline="#876094")
            c.create_line(x + 4, y - 12, x - 5, y + 18, fill="#785785", width=2)
        elif kind == "french_fries":
            for dx, dy in ((-8, -3), (0, 1), (8, -1)):
                c.create_rectangle(x + dx - 2, y + dy - 9, x + dx + 2, y + dy + 8,
                                   fill="#f3cb58", outline="#ac7a39")
        else:
            color = {"seed_mix": "#c5a773", "sunflower_seeds": "#585050",
                     "mystery_crumbs": "#c98e5a", "golden_corn": "#efca45"}[kind]
            for dx, dy in ((-8, 3), (0, -3), (7, 5), (-2, 8)):
                c.create_oval(x + dx - 3, y + dy - 2, x + dx + 3, y + dy + 2,
                              fill=color, outline="#8c744b")
        if ghost:
            c.create_oval(x - 24, y - 24, x + 24, y + 24, outline="#607b6c", dash=(3, 4))

    def draw_tears(self):
        c = self.canvas
        for tear in self.bird.tears:
            progress = min(1, tear.age / 2)
            fade = min(1, (TEAR_LIFETIME - tear.age) / 2)
            size = 35 * progress * fade
            x, y = tear.x, tear.y
            # A folded paper illustration, not a sampled or modified wallpaper.
            c.create_polygon(x - size, y, x - size / 3, y - 5, x, y + 3,
                             x + size / 2, y - 4, x + size, y,
                             x + size * 0.6, y + size * 0.7,
                             fill="#65757a", outline="#4b595e")
            c.create_polygon(x - size, y, x + size, y, x + size * 0.25,
                             y - size * (0.7 + math.sin(tear.age * 3) * 0.15),
                             fill="#f3ecd9", outline="#b7ac94")
            for index in range(3):
                sx = x + math.sin(tear.angle + index * 2) * tear.age * 12
                sy = y + progress * (15 + index * 6) + math.sin(tear.age * 2 + index) * 4
                small = 4 * fade
                c.create_polygon(sx - small, sy, sx + small, sy - small,
                                 sx + small / 2, sy + small, fill="#e2d6ba", outline="")

    def draw_bird(self):
        b, c = self.bird, self.canvas
        x, y, facing = b.x, b.y, b.facing
        bob = math.sin(b.clock * 10) * 2 if b.state == "walking" else math.sin(b.clock * 3)
        peck = abs(math.sin(b.action_time * 12)) * 10 if b.state in ("eating", "tearing") else 0
        play = math.sin(b.action_time / PLAY_DURATION * math.pi) * 14 if b.state == "playing" else 0
        y += bob - play
        c.create_oval(x - 23, y + 20, x + 23, y + 26, fill="#7f9293", outline="")
        c.create_line(x - 8, y + 17, x - 10, y + 24, x - 16, y + 24, fill="#ce8671", width=3)
        c.create_line(x + 7, y + 17, x + 9, y + 24, x + 15, y + 24, fill="#ce8671", width=3)
        c.create_polygon(x - facing * 12, y + 1, x - facing * 34, y + 13,
                         x - facing * 16, y + 17, fill="#606a7d", outline="")
        c.create_oval(x - 23, y - 12, x + 22, y + 20, fill="#8b96a6", outline="#596577")
        c.create_oval(x - 18, y - 6 - play / 2, x + 9, y + 14, fill="#727e92", outline="#5e697b")
        hx, hy = x + facing * 14, y - 18 + peck
        c.create_oval(hx - 11, hy - 2, hx + 9, hy + 18, fill="#588c83", outline="")
        c.create_oval(hx - 13, hy - 13, hx + 13, hy + 10, fill="#9ca7b6", outline="#596577")
        c.create_polygon(hx + facing * 10, hy - 1, hx + facing * 23, hy + 3,
                         hx + facing * 10, hy + 6, fill="#d5ad66", outline="#8a704b")
        ex = hx + facing * 5
        c.create_oval(ex - 3, hy - 6, ex + 3, hy, fill="#edb768", outline="")
        c.create_oval(ex - 1.5, hy - 5, ex + 1.5, hy - 2, fill="#26303d", outline="")
        self.regions.append(("bird", (x - 35, y - 35, x + 39, y + 26)))
        if b.state == "eating":
            fraction = min(1, b.action_time / EAT_DURATION)
            c.create_line(x - 18, y - 43, x + 18, y - 43, fill="#c1cec1", width=4)
            c.create_line(x - 18, y - 43, x - 18 + fraction * 36, y - 43, fill="#629b6f", width=4)

    def draw_tray(self):
        c = self.canvas
        left = self.width - TRAY_WIDTH * self.slide
        tab_y = min(110, self.height / 4)
        tab = (left - 39, tab_y, left, tab_y + 82)
        c.create_rectangle(*tab, fill="#d7e3d9", outline="#a6bbaf", width=1)
        self.text(left - 20, tab_y + 25, "‹" if not self.tray_open else "›")
        self.text(left - 20, tab_y + 56, "Feed", angle=90)
        self.regions.append(("tab", tab))
        if self.slide == 0:
            return
        c.create_rectangle(left, 0, self.width, self.height, fill=PANEL, outline="#c2d1c4")
        self.regions.append(("panel", (left, 0, self.width, self.height)))
        self.text(left + 20, 27, "Pigeon pantry", anchor="w")
        self.text(left + 20, 55, f"Hunger {self.bird.hunger}/{config.HUNGER_MAX}  ·  Friendship {self.bird.friendship}",
                  anchor="w")
        self.text(left + 20, 85, "Drag a treat onto the desktop.\nEscape cancels. Food is free for now.",
                  anchor="w")
        # Compress spacing on smaller displays; all controls remain in one tray.
        row_height = min(48, max(28, (self.height - 255) / len(LABELS)))
        for index, (kind, label) in enumerate(LABELS.items()):
            top = 112 + index * row_height
            rect = (left + 14, top, left + TRAY_WIDTH - 14, top + row_height - 5)
            c.create_rectangle(*rect, fill="#dde7da", outline="#c4d3c0")
            self.item(kind, left + 39, top + (row_height - 5) / 2)
            self.text(left + 67, top + (row_height - 5) / 2, label, anchor="w")
            self.regions.append((kind, rect))
        footer = 112 + len(LABELS) * row_height
        self.text(left + 20, footer + 10, f"{len(self.bird.items)}/{MAX_ITEMS} placed · {self.bird.state}", anchor="w")
        for name, label, top in (("clear", "Smooth it out", footer + 32),
                                 ("quit", "Quit pigeon", footer + 69)):
            rect = (left + 14, top, left + TRAY_WIDTH - 14, top + 30)
            c.create_rectangle(*rect, fill="#d5e1df", outline="#bdceca")
            self.text(left + TRAY_WIDTH / 2, top + 15, label)
            self.regions.append((name, rect))
        if self.notice and self.bird.clock < self.notice_until:
            self.text(left + 20, self.height - 21, self.notice, anchor="w", width=245)

    def draw(self):
        self.canvas.delete("all")
        self.regions = []
        if self.preview:
            self.text(18, 22, "Windowed preview · tears are cosmetic and disappear automatically", anchor="w")
        self.draw_tears()
        for item in self.bird.items:
            self.item(item.kind, item.x, item.y)
        self.draw_bird()
        self.draw_tray()
        if self.drag:
            self.item(self.drag, *self.pointer, ghost=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--preview", action="store_true", help="Use a normal window, even on Windows.")
    args = parser.parse_args()
    if tk is None:
        parser.exit(1, "Tk support is missing. Install Python with Tcl/Tk (on Debian/Ubuntu: python3-tk).\n")
    try:
        root = tk.Tk()
    except tk.TclError as error:
        parser.exit(1, f"Cannot open a graphical display: {error}\nRun on a desktop with Tk support.\n")
    App(root, args.preview)
    root.mainloop()


if __name__ == "__main__":
    main()
