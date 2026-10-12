"""Run with `py main.py` on Windows, or `python3 main.py` elsewhere."""

import sys


def main() -> int:
    try:
        import tkinter as tk
        from app import DesktopPigeonApp
    except ImportError as exc:
        print(f"Desktop Pigeon requires Python with Tkinter: {exc}\n"
              "Windows: install Python from python.org with Tcl/Tk enabled.\n"
              "Ubuntu/Debian: install python3-tk.", file=sys.stderr)
        return 1
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        print(f"Cannot open desktop display: {exc}", file=sys.stderr)
        return 1
    app = DesktopPigeonApp(root)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        app.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
