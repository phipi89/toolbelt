# Toolbelt

A collection of productivity tools that make the terminal the default entry point to my computer.

## Principles

* A single place for keyboard-based workflows CLI tools and my config.
* Shareable across my devices; deliberately not hidden behind .dotfiles.
* Hackable, with now aspiration for completeness or polish.

### Keyboard shortcuts

Super key = <kbd>right cmd</kbd>.

- <kbd>super</kbd>+<kbd>space</kbd>: iTerm hotkey window
- <kbd>super</kbd>+<kbd>char</kbd>: run apps and tools
- <kbd>super</kbd>+<kbd>,</kbd>/ <kbd>.</kbd> / <kbd>l</kbd> / <kbd>-</kbd> / <kbd>ö</kbd> / <kbd>ü</kbd>: move/resize/arange windows
- <kbd>super</kbd>+<kbd>number</kbd>: switch spaces

### Window management

#### Launch and focus
If the app is on the current space: focus it. If its not running: launch it.
If it exists on another space, behavior depends on the app:

- **spawn new**: open a fresh window (e.g. browser)
- **go to**: jump to the existing window (e.g. messenger)
- **select**: show app exposé to pick the right window (e.g. IDE)

This mapping is configured per app in `config/window_management/setup.yaml`.

#### Tiling
- <kbd>super</kbd>+<kbd>,</kbd>/<kbd>.</kbd>: tile left/right (cycles 50:50 ↔ 65:35)
- <kbd>super</kbd>+<kbd>l</kbd>: almost maximise (cycles 90% → 100% → 60%)
- <kbd>super</kbd>+<kbd>-</kbd>: almost minimise to lower left
- <kbd>super</kbd>+<kbd>ö</kbd>: shift windows to minimise overlap
- <kbd>super</kbd>+<kbd>ü</kbd>: split or quad-tile windows.
- <kbd>caps lock</kbd>: cycle focus between frontmost windows

### Tools
Approach: When a pain point shows up, build a small tool and integrate it into the workflow.

- **essentials**: currently zsh, app launcher, calculator, snippets and search; live in their own hotkey window
- **regulars**: used often; short names (3–4 chars), sourced into zsh (e.g. `ten`, `clk`, `grab`)
- **occasionals**: longer descriptive names (e.g. `pytemp`, `compose_mail`)

## Setup

This project builds on *iTerm2* as the main interface, *Karabiner* for custom keyboard shortcuts and *Hammerspoon* for window management.
- iTerm2
	- settings > "Load preferences from a custom folder or URL" > `~/toolbelt/config/iTerm2/`
	- source `~/toolbelt/aliases.sh` in your `zshrc`.
- Karabiner Elements
	- symlink config into this repo (see below)
- Hammerspoon
	- set config from `~/toolbelt/config/hammerspoon/init.lua`
- MacOS
	- deactivate: Settings > Schreibtisch & Dock > Beim Programmwechsel Space auswählen, der geöffnete Fenster des Programms enthält

```sh
## link Karabiner config
#  backup the original config
mv ~/.config/karabiner ~/.config/karabiner.backup.$(date +%Y%m%d%H%M%S)

#  link so that toolbelt config becomes the authorative location
ln -s "$HOME/toolbelt/config/karabiner" "$HOME/.config/karabiner"

```

## List of tools

- essentials
	- iTerm (<kbd>super</kbd>+<kbd>space</kbd>) open *iTerm* in a hotkey window.
	- `run` (<kbd>super</kbd>+<kbd>a</kbd>) open apps.
	- `calc` (<kbd>super</kbd>+<kbd>c</kbd>) iPython with NumPy namespace loaded.
	- `snipptes` (<kbd>super</kbd>+<kbd>v</kbd>) select and paste text snippets.
	- `buf` (<kbd>super</kbd>+<kbd>b</kbd>) open a minimal Sublime Text buffer.
- `window_managemnt` used via keyboard shortcuts
- `clk [[start|end|break]` track working hours.
- workflow helpers
	- `grab`: `cd` into the directory of the frontmost finder window.
	- `diskusage [glob|.]` list elements sorted by file size
	- `pytitle|textitle [title]`: copy a commented *figlet* into the clipboard.
	- `compose_mail`: new message in Outlook PWA
- requests
	- `ten|fen|tfr|ffr [word]`: request translation from leo.org.
	- `ask [question]` sends a one-off question to opencode.
- python
	- `pyinit|nbinit [title|.]`: uv project with(out) jupyter
	- `pytemp|nbtemp`: uv project with(out) jupyter in a temp directory
	- `snippets` contains e.g. autoreload and shebang snippets for convenience

## Adding tools

### Naming  Convention
**Regulars**
1. If a 3-letter word fits, use that (e.g. `run [app]`).
2. Else use a 4-letter word (e.g. `calc`).
3. Else use a short acronym (e.g. `ten` = to-English translation).

**Occasionals**
- Use descriptive names with underscores (e.g. `compose_mail`).

### Architecture
A *tool* is always a script somewhere in this repo that gets exposed via `aliases.sh`.

#### Approach
- Use whatever language makes sense.
- Vibe code it, if it gets the job done.
- Keep it short.
- Don’t implement edge cases until you need them.

#### Organisation
- `misc/` is for small, single-file scripts.
- For Python scripts, see `misc/textitle.py` for how to use `uv` deps in the shebang.
- If a tool grows, give it its own directory.
- All tools are wired up in `aliases.sh`.
- Configuration and data goes into `config/<tool>/`.
- Essentials get dedicated iTerm hotkey windows (duplicate an existing iTerm profile, and remap <kbd>fn≥15</kbd> with karabiner).
  Give each essential a distinct background color.
## Todo
- [ ] integrate OCR screen capture tool
