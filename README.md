# Desktop Pigeon — Phase 2 core

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
  automatically after about six seconds, then every 21–39 seconds depending on
  curiosity, when available.
- Watch **Investigating → Approaching → Theft attempt → Escaping → Nest storage**.
  A pulsing diamond and carried fragment are *only drawings*: nothing is taken
  from a real desktop icon or file.
- The nest lists stored **treasures and fragments**, newest first. It keeps the
  latest 500 items, including their collection times.
- Feed any of five foods. **Seed mix is always free**; other foods start with
  three portions each. Food lowers the visible
  hunger meter and prompts a “Coo! Thank you!” response.
- Hunger rises from 0 (Full) to 100 (Angry), by one point every five active
  seconds. There are no departures in this MVP. **Pause freezes movement,
  collection, hunger, pet cooldowns, gifts, and minigames**; feeding still works. Time while closed/asleep does
  not cause offline hunger.
- Closing the nest panel hides only the panel. **Quit** in the panel/menu stops
  the companion and saves; Escape while the pigeon is focused also quits.

## Phase 2: relationships, personality, gifts, and play

- Feeding a pigeon that is not already full increases friendship by the food's
  configured reward. Petting adds 2–4 points, with a 15-active-second cooldown.
  The nest shows friendship (0–100) and relationship stages: New acquaintance,
  Familiar (20), Friend (40), and Best friend (75).
- Each pigeon has persistent curiosity, calm, and sociability traits, generated
  once. Curiosity changes shiny-seeking frequency, calm changes rest duration,
  and sociability changes petting rewards. The nest displays a dominant-trait
  personality: Shiny explorer, Laid-back lounger, or Sociable companion.
- At 20 friendship, your pigeon brings a generated feather, coin, or pebble
  every two active minutes. These appear as **Gift** entries in the nest and a
  visible notification; they never come from real desktop files.
- Open **Play Shiny Sorting** from the nest or pigeon menu. Sort five items:
  buttons/marbles are Treasures; foil/paper are Fragments. At least three correct
  earns two sunflower-seed portions and friendship equal to the score. A perfect
  score also earns a golden-corn portion. Rewards are granted once per completed
  game; failed games can be replayed. Games are untimed and freeze during pause.
  Closing the game hides it without discarding the current round. Unfinished
  games reset on app exit.
- Other GDD minigames, personality mutations, and gift-return interactions remain
  future extensions. Food costs/currency are not implemented.

## Local data and privacy

Only the app’s own `nest_data.json` is read/written:

- Windows: `%LOCALAPPDATA%\DesktopPigeon\nest_data.json`
- Linux: `${XDG_DATA_HOME:-~/.local/share}/DesktopPigeon/nest_data.json`

The versioned save contains hunger, friendship, traits, food portions, cooldowns,
game win count, and generated item names/types/IDs/times. Existing Phase 1 saves
load unchanged and upgrade to version 2 on the next successful save, preserving
hunger and treasures. Downgrading to Phase 1 cannot read version 2 saves; keep a
manual backup of the app's own save before downgrading.
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
- `nest.py`: bounded treasure/fragment/gift inventory and companion profile.
- `companion.py`: relationships, personality traits, gift timers, and earned food.
- `minigames.py`: UI-independent Shiny Sorting rounds and one-time reward claims.
- `storage.py`: local, versioned, atomic persistence.
- `app.py`: simulation/UI coordination and save lifecycle.
- `ui/`: procedural pigeon sprite, small overlays, and nest controls.
- `config.py`: tunable values; `main.py`: startup.

The core modules do not import Tkinter. Future minigames, personality mutations,
flocking, and generations can extend the model and treasure provider
without needing desktop-content access.

Run the standard-library tests from the repository root:

```powershell
py -m unittest discover -s tests -v
```

GUI tests skip without Tkinter/a display. On Linux with Xvfb installed, run
`xvfb-run -a python3 -m unittest discover -s tests -v` to exercise real Tk widgets
as well. No separate lint/build tooling or CI existed in the starting repository.
