# Toolbelt

A collection of small productivity tools that make the terminal the default entry point to my computer.

## Principles

A single place for config, shareable across my devices. Keyboard-first workflow with a *super key* and a handful of small CLI tools to solve everyday.

This is my personal setup; intentionally raw and hackable.

### Keyboard shortcuts

Super key = <kbd>right cmd</kbd>.

- <kbd>super</kbd>+<kbd>space</kbd>: open iTerm hotkey window
- <kbd>super</kbd>+<kbd>letter</kbd>: run apps and tools
- <kbd>super</kbd>+<kbd>,</kbd>/<kbd>.</kbd>/<kbd>l</kbd>: move/resize windows
- <kbd>super</kbd>+<kbd>number</kbd>: switch spaces

### Window management

#### Launch and focus
If the app is on the current space: focus it. If its not running: launch it.
If it exists on another space, behavior depends on the app:

- **spawn new**: open a fresh window (e.g. browser)
- **go to**: jump to the existing window (e.g. messenger)
- **select**: show app exposé to pick the right window (e.g. IDE)

This mapping is configured manually per app.

#### Tiling
- <kbd>super</kbd>+<kbd>,</kbd>/<kbd>.</kbd>: tile left/right (cycles 50:50 ↔ 65:35)
- <kbd>super</kbd>+<kbd>l</kbd>: almost maximize (cycles 90% ↔ 100%)

### Tools
Whenever a pain point shows up, I build a small tool and wire it into the workflow.

- **essentials**: launcher & calculator, live in their own hotkey window
- **regulars**: used often; short names (3–4 chars), sourced into zsh (e.g. `ten`, `clk`, `grab`)
- **occasionals**: longer descriptive names (e.g. `pytemp`, `compose_mail`)

## Setup

This project builds on *iTerm2* as the main interface, *Karabiner* for custom keyboard shortcuts and *Hammerspoon* for more complex window management.
- iTerm2
	- settings > "Load preferences from a custom folder or URL" > `~/toolbelt/config/iTerm2/`
	- source `~/toolbelt/aliases.sh` in your `zshrc`.
- Karabiner Elements
	- symlink config into this repo (see below)
- Hammerspoon
	- set config from `~/toolbelt/config/hammerspoon/init.lua`
- MacOS
	- deactiveate: Settings > Schreibtisch & Dock > Beim Programmwechsel Space auswählen, der geöffnete Fenster des Programms enthält

```sh
## link Karabiner config
#  backup the original config
mv ~/.config/karabiner ~/.config/karabiner.backup.$(date +%Y%m%d%H%M%S)

#  link so that toolbelt config becomes the authorative location
ln -s "$HOME/toolbelt/config/karabiner" "$HOME/.config/karabiner"

```

## Examples

### Miscellaneous

- `grab` `cd`s into the directory of the frontmost finder window.
- `pytitle|textitle [title] ` copies a commented out *figlet* into the clipboard.
- `ask [question]` sends a one-off question to gemini.
- `calc` launches into iPython with the NumPy namespace loaded.
### clk

`clk [[start|end|break]`  tracks my working hours into `~/clk_log.json`.

The tool is how far you get with a couple of prompts. I keep it deliberately simple, I'm sure there's overkill versions doing the same.

## Adding tools

### Naming
**Regulars**
1. If a 3-letter word fits, use that (e.g. `run [app]`).
2. Else use a 4-letter word (e.g. `calc`).
3. Else use a short acronym (e.g. `ten` = to-English translation).

**Occasionals**
- Use descriptive names with underscores (e.g. `compose_mail`).

### Architecture
A *tool* is always a script somewhere in this repo that gets exposed via `aliases.sh`
(even if it *could* be done another way).

#### Approach
- Use whatever language makes sense.
- Keep it short.
- Don’t implement edge cases until you need them.

#### Organisation
- `misc/` is for small, single-file scripts.
- For Python scripts, see `misc/textitle.py` for how to use `uv` deps in the shebang.
- If a tool grows, give it its own directory.
- All tools are wired up in `aliases.sh`.
- Configuration and data goes into `config/<tool>`.
- Essentials get dedicated iTerm hotkey windows (duplicate an existing iTerm profile, and remap <kbd>fn≥15</kbd> with karabiner).
  Give each essential a distinct background color.
## Todo
- [ ] find files
- [ ] integrate OCR screen capture tool