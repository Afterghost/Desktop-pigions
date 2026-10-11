# Desktop Pigeon — Phase 1

A single, local-only pigeon companion for your desktop. It walks, rests, pecks at
generated shinies, carries them home, and gets hungry. No account, service,
network connection, assets, or third-party Python packages are required.

## Run on Windows

1. Install **Python 3.10 or newer** from [python.org](https://www.python.org/downloads/windows/).
   Keep the installer’s **Tcl/Tk and IDLE** option enabled.
2. Open a terminal in this repository and run:

   ```powershell
   py main.py
   ```

One pigeon and a small nest appear on the primary monitor, above other windows.
The Windows work area excludes the taskbar. Use `pyw main.py` after confirming
startup if you prefer not to keep a console open. No administrator access needed.

Linux: install your distribution’s Tkinter package (e.g. `python3-tk`) and use
`python3 main.py` in a graphical desktop session. Windows has transparent
backgrounds; other platforms use small opaque tiles as a preview fallback.
Windows is the intended desktop target; multi-monitor roaming is not implemented.

## Controls and gameplay

- **Left-click the pigeon or nest** to open the nest panel.
- **Right-click either** for feeding, nest, pause/resume, or quit.
- **Offer a shiny** starts a collection immediately. The pigeon also finds one
  automatically after about six seconds, then every thirty seconds when available.
- Watch **Investigating → Approaching → Theft attempt → Escaping → Nest storage**.
  A pulsing diamond and carried fragment are *only drawings*: nothing is taken
  from a real desktop icon or file.
- The nest lists stored **treasures and fragments**, newest first. It keeps the
  latest 500 items, including their collection times.
- Feed any of five foods. All are **free in Phase 1**; inventory, costs, and
  friendship rewards are reserved for later phases. Food lowers the visible
  hunger meter and prompts a “Coo! Thank you!” response.
- Hunger rises from 0 (Full) to 100 (Angry), by one point every five active
  seconds. There are no departures in this MVP. **Pause freezes movement,
  collection, and hunger**; feeding still works. Time while closed/asleep does
  not cause offline hunger.
- Closing the nest panel hides only the panel. **Quit** in the panel/menu stops
  the companion and saves; Escape while the pigeon is focused also quits.

## Local data and privacy

Only the app’s own `nest_data.json` is read/written:

- Windows: `%LOCALAPPDATA%\DesktopPigeon\nest_data.json`
- Linux: `${XDG_DATA_HOME:-~/.local/share}/DesktopPigeon/nest_data.json`

The versioned save contains hunger and generated item names/types/IDs/times.
Saves occur on feeding, collection, every ten active seconds, and exit, using
atomic replacement. Position and unfinished thefts are not persisted. If a save
is malformed or from an unsupported version, it is kept intact, a warning
appears, and saving is disabled for that session. Write failures are displayed
in the nest; quitting without saving requires confirmation.

To reset, **quit first**, then remove the app’s own data folder manually.
Do not run multiple instances simultaneously: they share one save, and the last
writer wins.

**No cloud, telemetry, OCR, screenshots, screen capture, file enumeration,
icon extraction, usage tracking, or modification of user documents.** Phase 1
uses synthetic treasures rather than desktop awareness. The only Windows API
query obtains the primary monitor’s usable work-area rectangle. Some constants
in the original `config.py` describe future detection/social features; those
features are not enabled by this MVP.

## Structure and validation

- `pigeon.py`: time-based behavior state machine and single pigeon state.
- `desktop.py`: bounded movement and synthetic treasure provider.
- `feeding.py`: hunger progression and food effects.
- `nest.py`: bounded treasure/fragment inventory.
- `storage.py`: local, versioned, atomic persistence.
- `app.py`: simulation/UI coordination and save lifecycle.
- `ui/`: procedural pigeon sprite, small overlays, and nest controls.
- `config.py`: tunable values; `main.py`: startup.

The core modules do not import Tkinter. Future personality, friendship,
minigames, flocking, and generations can extend the model and treasure provider
without needing desktop-content access.

Run the standard-library tests from the repository root:

```powershell
py -m unittest discover -s tests -v
```

GUI tests skip without Tkinter/a display. On Linux with Xvfb installed, run
`xvfb-run -a python3 -m unittest discover -s tests -v` to exercise real Tk widgets
as well. No separate lint/build tooling or CI existed in the starting repository.
