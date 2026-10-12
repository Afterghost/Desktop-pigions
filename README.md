# Desktop Pigeon — flock interactions and family stories

A local-only pigeon flock for your desktop. Each bird walks, rests, pecks at
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

## Separate session-local interaction prototype

Run `python interaction_app.py` (or `py interaction_app.py` on Windows) for the
alternative drag-food/feather and cosmetic paper-tear prototype. Add `--preview`
for a normal window; non-Windows platforms use that preview automatically.
Drag treats from the edge tray, or use **Smooth it out** to clear temporary tears.
This alternative keeps everything in memory, resets on exit, and does not read,
write, or share the flock app's saves. The default `py main.py` remains the
persistent flock companion described below.

## Controls and gameplay

- **Left-click a pigeon** to select it and open the nest panel; **double-click** to give it
  a gentle head scratch; click the nest to open it.
  Feeding, protection, intervention, games, and item returns affect the selected bird.
  The family/history list also selects active birds. Changing birds cancels unfinished games
  and cooperative collections without a reward.
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
  seconds. Departed birds keep their identity and history and can be invited back. **Pause freezes movement,
  collection, hunger, pet cooldowns, gifts, and minigames**; feeding still works. Time while closed/asleep does
  not cause offline hunger.
- Closing the nest panel hides only the panel. **Quit** in the panel/menu stops
  the companion and saves; Escape while the pigeon is focused also quits.

## Phase 2: relationships, personality, gifts, and play

- Feeding a pigeon that is not already full increases friendship by the food's
  configured reward. Petting adds 2–4 points, with a 15-active-second cooldown.
  The nest shows friendship (0–100) and relationship stages: New acquaintance,
  Familiar (20), Friend (40), and Best friend (75).
- Each new pigeon has persistent curiosity, calm, and sociability traits, generated
  once. Care raises calm, collecting raises curiosity, and successful play raises
  sociability (each bounded at 100). Curiosity changes shiny-seeking frequency, calm changes rest duration,
  and sociability changes petting rewards. The nest displays a dominant-trait
  personality initially: Shiny explorer, Laid-back lounger, or Sociable companion.
  Five care/collect/play actions unlock Gentle Soul/Treasure Seeker/Playful Acrobat.
  Combining these milestones produces a visible **Hybrid** title.
- At 20 friendship, your pigeon brings a generated feather, coin, pebble,
  ribbon bouquet, polished bottle cap, or friendship twig
  every two active minutes. These appear as **Gift** entries in the nest and a
  visible notification; they never come from real desktop files.
- Open **Play minigames** from the nest or pigeon menu and choose a game:
  - **Shiny Sorting**: sort five items:
  buttons/marbles are Treasures; foil/paper are Fragments. At least three correct
  earns two sunflower-seed portions and friendship equal to the score. A perfect
  score also earns a golden-corn portion. Rewards are granted once per completed
  game; failed games can be replayed.
  - **Peck Finder**: peck the numbered edible crumb among stones in a 3×3 patch.
  - **Follow Crumb Trail**: select successive crumbs in a five-step trail.
  - **Pigeon Memory**: study five colors, hide them, then recall the order.
  - **Rooftop Dash**: choose Jump/Duck/Run for gaps/wires/clear sections.
  - **Human Inspection**: Approach a seed offer, Wait near a busy human,
    Retreat from a broom. These scenes are text, not real desktop observations.
  - **Daily Foraging**: Search spends two energy; Rest restores three. Searching
    exhausted or resting unnecessarily misses the turn. Attempts have a persisted
    300-active-second cooldown, including cancelled/failed attempts. “Daily” is a
    local gameplay name, not a wall-clock calendar or network event.
  All games are untimed, five-turn MVPs with on-screen instructions and the same
  3+ correct reward rule. Pause disables all answers and memory hiding.
  Closing/Escape/cancelling a game discards the round **without rewards**.
  Unfinished games reset on app exit. The other minigames intentionally use small
  turn-based mechanics rather than real-time arcade simulations.
- Select a nest gift/treasure/fragment, then **Return selected** to consume that
  synthetic item once for friendship (gifts +4, other items +2), personality
  evolution, and reconciliation. Nothing is returned to or removed from user files.
  Food cannot be purchased; nest treasury is earned locally, not bought.

## Phase 3 core: reputation, governing, and forgiveness

- Reputation awards ten points **once per milestone**, not per repeatable click:
  first/5th/20th care, collection, play, governing, and item-return actions; first
  win of each game; and the reconciliation journal entry. Finite achievement
  history and bounded counters prevent unbounded save growth.
- This core uses local MVP reputation titles: Unknown Pigeon (0), Neighborhood
  Regular (30), Trusted Companion (80), Rooftop Legend (150). A complete GDD
  reputation ladder and its exact titles are not supplied in this repository;
  these titles are not presented as a full implementation of that ladder.
- While a synthetic target is active, **Shoo / catch**, **Seed bribe / trade**,
  or **Laser distraction** cancels it, including during escape/storage. Trade
  consumes one sunflower portion and feeds the pigeon; the other actions use no
  food. All record calm/governing progress and have a shared persisted ten-active-
  second cooldown. No action/reward is available without a target or while paused.
  A cancelled target can never subsequently enter the nest.
- **Protect Treasure/Fragment** toggles persisted protection for that synthetic
  type and immediately cancels any matching active target. Protected targets are
  refused without rewards; removing protection does not recover the cancelled item.
- At hunger 90+, active neglect accumulates: Grumpy immediately, Bitter at 60
  seconds, Resentful at 120, Preparing to Leave at 180, and **Last Chance Coo**
  at 240. The nest opens with a persistent visible notice at Last Chance.
  There are then **120 active seconds** of grace, with a visible countdown,
  before the bird leaves the active flock. Pause freezes neglect and grace;
  closed/asleep time is not counted. Feeding while hungry, a cooldown-eligible
  pet, a successful game, seed trade, or returning a nest item reconciles the pigeon. This
  resets neglect and permanently records **The Day We Made Up** and **Forgiven**.
  Automatic collection, gifts, cooperative coos, protection, shooing and laser
  distraction do **not** reconcile neglect. A departed bird's target and unfinished
  game are cancelled without rewards. Feathers/sticks appear briefly as drawings only.

## Phase 4 core: nests, generations, and permanent legacy

- Begin with the existing single bird. **Small** nests hold 1 bird; **Expanded** 2,
  **Large** 3, **Grand** 5. Each collected non-gift synthetic item earns one treasury
  unit, credited regardless of which bird collected it. Click **Upgrade** to spend
  5, then 10, then 20 units. No real money, microtransactions, or external economy.
- **Lay egg** uses the selected active parent; **Adopt egg** creates a founding
  generation without a parent (also available with an empty flock). Eggs reserve
  capacity and hatch after **60 active seconds**; pause, sleep and closed time
  do not hatch them. An egg cannot hatch past nest capacity.
- Each hatch has a unique permanent ID, name, parent ID and generation. Inherited
  traits are halfway between the parent's traits when laid and neutral 50;
  friendship, food, hunger and progression start fresh. Eggs snapshot traits.
- Up to five birds have separate small topmost windows, hunger, traits, synthetic
  targets, and profile rewards, with a shared nest inventory and treasury.
- **Family / permanent history** lists name, generation, parent, reputation and
  status. Select a record to view its ID and lifetime. Departures permanently keep
  the first departure's name, personality, reputation, active lifetime and reason.
  **Invite departed bird back** requires a free slot (reserved eggs count), restores
  the same identity/profile, and reconciles grace without removing the legacy.
  Active IDs cannot be duplicated. Parent generation validation forbids cycles.
- Every **30 active seconds** with two or more birds, mutual flock bonds change.
  Affinity is **−100 to +100**, separate from friendship with the human:
  **Friendship at +20**, **Rivalry at −20**, otherwise Acquaintance. Similar traits
  build affinity; incompatible traits erode it; low-calm birds occasionally clash.
  The nest shows selected-bird bonds; the stories window lists all mutual bonds.
- Available friends begin **shared foraging/cooperative collection**: one bird owns
  the generated target while its friend visibly follows within the work area.
  One stored item earns exactly **one treasury unit and one collector reward**,
  not a second item/reward for the helper. Cooperation improves the pair's affinity.
  Overlays show “Shared forage” and “Following friend”. Attempts expire after
  30 active seconds; selection changes, protection, intervention, target cancellation,
  or either participant's departure abort unfinished cooperation without rewards.
  Both participants' protected Treasure/Fragment types are respected.
- When an available friend's ordinary two-minute gift timer pays out, a friend can
  escort them home for five active seconds: “Shared gift” / “Gift escort”.
  This is **one gift**, no extra treasury or food, and a small mutual affinity gain.
  Busy birds deliver alone. Rivals give space for five active seconds; this never
  removes nest items, changes hunger, or blocks feeding. Elders (longer active
  lifetimes) mentor younger birds with +1 calm per meeting, not human friendship,
  and cannot reconcile neglect. Pause freezes all social movement and cadence.
- Pair bonds survive departure and return, never duplicate, and inactive pairs do
  not meet. At **200 permanent pairs**, new pairs are refused; old bonds are never
  pruned. Existing identities can still hatch/return, but pairs beyond the cap have
  no simulated social relationship.
- **Family stories / activity** opens a separate scrollable small window.
  Select a family/history record as its anchor, then filter **All**, **Ancestors**,
  **Descendants** (including the anchor), or **Lineage** (the founding ancestor's
  descendants). Parent names, generation counts, bonds and stories remain available
  even when all birds have departed.
- Structured local facts produce deterministic prose for founding, incubation,
  hatching (snapshotted inherited traits and parent), first recorded care, treasure,
  gift, game and win, friendships, rivalries, reconciliation, elder mentorship,
  departure legacy and return. Family facts and first milestones are permanent;
  repeated interactions occupy a separate **latest-60 activity feed**, whose oldest
  entries are explicitly pruned. The core has a validated **4,000-event ceiling**
  (the 100 identities / 200 pairs bound keeps reachable unique core facts below it).
  Migration records family origins only, not previously unobserved achievements;
  “first recorded” milestones describe observations since stories were enabled.
- Permanent identities (birds plus eggs) are limited to **100** so saves stay bounded.
  At that explicit limit new eggs are refused; departed history is **never pruned**.
- **Intentional limits:** this is a modular core, not full GDD Phase 4. No breeding
  pairs, egg artwork, obstacle-aware flock pathfinding, aging/death, heir succession,
  custom names, or language-model-generated fiction is implemented. Social routines
  are bounded local model behaviors, not desktop observation or a giant social simulation.

## Local data and privacy

Only the app’s own `nest_data.json` is read/written:

- Windows: `%LOCALAPPDATA%\DesktopPigeon\nest_data.json`
- Linux: `${XDG_DATA_HOME:-~/.local/share}/DesktopPigeon/nest_data.json`

The versioned save contains hunger, friendship, traits, food portions, cooldowns,
game win count, bounded achievements/action counts, neglect/cooldown timers,
forgiveness, protected synthetic types, and generated item names/types/IDs/times.
Existing version 1/2/3/4 saves are read without rewriting and upgrade to **version 5**
on the next successful save, preserving hunger, items, and all existing version 2
traits/food/friendship/timers/wins. Version 1 has no traits, so migration supplies
deterministic neutral traits rather than rerolling them. Version 3 preserves
evolved traits exactly across reloads. Version 4 adds per-bird hunger/lifetime,
identities, parentage, permanent departure legacy, grace, eggs, nest level/treasury,
selected ID and social timers. Version 5 adds bounded mutual bonds and structured
permanent/recent chronicles, retaining every earlier profile, egg, item and legacy.
All saved fields, counters, finite timers and cross-record references are validated.
Unsupported/corrupt saves remain intact.
Downgrading to earlier phases cannot read version 5 saves; keep a
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
- `minigames.py`: shared UI-independent local game rounds and one-time reward claims.
- `progression.py`: bounded reputation milestones, active neglect, and forgiveness.
- `flock.py`: identities, capacity/treasury, eggs, legacy, mentoring and validation.
- `social.py`: mutual affinity, compatibility, cooperation, gift escorts and yielding.
- `chronicle.py`: validated local facts, deterministic prose and family filters.
- `storage.py`: local, versioned, atomic persistence.
- `app.py`: simulation/UI coordination and save lifecycle.
- `ui/`: procedural pigeon sprite, small overlays, and nest controls.
- `config.py`: tunable values; `main.py`: startup.

The core modules do not import Tkinter. Future arcade expansion, full GDD reputation,
additional flock routines and generation narratives can extend the model and treasure provider
without needing desktop-content access.

Run the standard-library tests from the repository root:

```powershell
py -m unittest discover -s tests -v
```

GUI tests skip without Tkinter/a display. On Linux with Xvfb installed, run
`xvfb-run -a python3 -m unittest discover -s tests -v` to exercise real Tk widgets
as well. No separate lint/build tooling or CI existed in the starting repository.

### Windows manual checklist (not verified natively in the Linux environment)

- Run `py main.py`; confirm transparent, topmost bird/nest/target tiles and taskbar
  exclusion, including primary-monitor DPI scaling. Click unrelated desktop icons
  outside tiles to check they remain usable. Multi-monitor roaming is unsupported.
- Feed, pet, play each game, return an item, protect and intervene; verify selected
  bird effects. Earn upgrades and hatch/adopt up to five; verify each window moves
  within the work area and switching birds cancels unfinished games.
- Leave a hungry bird neglected: check the Last Chance countdown and departure
  after two more active minutes, cancelled targets/games, and transient feathers.
  Pause/resume, sleep/wake, and quit/relaunch during grace and egg incubation:
  paused, suspended and closed intervals must not consume timers.
- Invite the departed bird back from history, check its ID, traits and legacy;
  confirm rejoin is refused at capacity and cannot duplicate a bird.
- Observe friendships, follow/escort overlays, and rivalry yielding. Protect either
  participant's target type or switch selection during cooperation: no stale collection
  should appear. Pause midway and verify the helper freezes too. Open family stories,
  filter an ancestor/descendant/lineage, and reopen after all birds depart.
- Quit/relaunch a five-bird flock; verify per-bird hunger, selected ID, eggs and
  history. Back up the app save before testing migration/corruption: old saves
  should migrate on save; malformed/unsupported saves must remain unchanged.
- Test Escape, panel close, Quit, and a read-only app-data directory. No orphan
  windows or stale game rewards should remain after Quit.
