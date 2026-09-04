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
- **move here**: bring the app to current space (e.g. DeepL)

This mapping is configured per app in `config/display/setup.yaml`.

#### Tiling
- <kbd>super</kbd>+<kbd>,</kbd>/<kbd>.</kbd>: tile left/right (cycles 50:50 ↔ 65:35)
- <kbd>super</kbd>+<kbd>l</kbd>: grow centered size by 10% up to 100%; add <kbd>shift</kbd> to shrink down to 10%
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

This project builds on *iTerm2* as the main interface, *Karabiner* for custom keyboard shortcuts and *yabai* for window management.
- iTerm2
	- settings > "Load preferences from a custom folder or URL" > `~/toolbelt/config/iTerm2/`
	- source `~/toolbelt/aliases.sh` in your `zshrc`.
- Karabiner Elements (`brew install karabiner-elements`)
	- symlink config into this repo (see below)
- yabai (`brew install asmvik/formulae/yabai`)
		- MacOS
	- deactivate: Settings > Schreibtisch & Dock > Beim Programmwechsel Space auswählen, der geöffnete Fenster des Programms enthält

```sh
## link Karabiner config
#  backup the original config
mv ~/.config/karabiner ~/.config/karabiner.backup.$(date +%Y%m%d%H%M%S)

#  link so that toolbelt config becomes the authorative location
ln -s "$HOME/toolbelt/config/karabiner" "$HOME/.config/karabiner"

```

## Most important tools

- essentials
	- iTerm (<kbd>super</kbd>+<kbd>space</kbd>) open *iTerm* in a hotkey window.
	- `run` (<kbd>super</kbd>+<kbd>a</kbd>) open apps.
	- `calc` (<kbd>super</kbd>+<kbd>c</kbd>) iPython with NumPy namespace loaded.
	- `snipptes` (<kbd>super</kbd>+<kbd>v</kbd>) select and paste text snippets.
	- `buf` opens CotEditor as a text buffer.
	- `prose` (<kbd>super</kbd>+<kbd>t</kbd>) opens a minimal autosaving serif text editor; `prose --recent` reopens recently closed documents.
	- `search` (<kbd>super</kbd>+<kbd>b</kbd>) Search through spotlight indexed files.
- `displayctl` used via keyboard shortcuts
- `finderctl` provides Finder paths, file snapshots and cross-window checks through workflow helpers.
- `setup save|open|list|suggest-name|edit`: save and restore current-screen window setups.
- `clk [[start|end|break]` track working hours.
- workflow helpers
	- `grab`: `cd` into the directory of the frontmost finder window.
	- `gsnap`: snapshot the selected Finder file into `snapshots/`.
	- `check_left_in_right`: check that each filename in the left Finder folder exists in the right one.
	- `diskusage [glob|.]` list elements sorted by file size
	- `pytitle|textitle [title]`: copy a commented *figlet* into the clipboard.
	- `qrcode <text> --out <file>` creates a transparent PNG; `pbqr <text>` copies one to the clipboard.
- requests
	- `ten|fen|tfr|ffr|tit|fit [word]`: request translation via PONS.
	- `ask [question]` sends a one-off question to opencode.
- python
	- `pyinit|nbinit [title|.]`: uv project with(out) jupyter
	- `pytemp|nbtemp`: uv project with(out) jupyter in a temp directory
	- `snippets --edit` opens shared snippets; `snippets --edit --local` opens machine-local snippets.

## Adding tools

### Naming  Convention
**Regulars**
1. If a 3-letter word fits, use that (e.g. `run [app]`).
2. Else use a 4-letter word (e.g. `calc`).
3. Else use a short acronym (e.g. `ten` = to-English translation).

**Occasionals**
- Use descriptive names with underscores (e.g. `compose_mail`).

### Architecture
A *tool* is a script somewhere in this repo, exposed or directly defined in `aliases.sh`.

#### Approach
- Use whatever language makes sense.
- Vibe code it, if it gets the job done.
- Keep it short.
- Don’t implement edge cases until you need them.

#### Organisation
- `misc/` is for small, single-file scripts.
- For Python scripts, see `misc/textitle.py` for how to use `uv` and dependencies with shebangs.
- If a tool grows, give it its own directory.
- All tools are wired up in `aliases.sh`.
- Configuration and data goes into `config/<tool>/`. Where appropriate, local configuration that should not be shared goes into `~/.toolbelt-local`.
- Essentials get dedicated iTerm hotkey windows (duplicate an existing iTerm profile, and remap <kbd>fn≥15</kbd> with karabiner).
  Give each essential a distinct background color.


## All tools

| Tool           | Trigger                           | Description                                |
| -------------- | --------------------------------- | ------------------------------------------ |
| `iTerm`        | <kbd>super</kbd>+<kbd>space</kbd> | Hotkey window terminal                     |
| `run`          | <kbd>super</kbd>+<kbd>a</kbd>     | App launcher                               |
| `calc`         | <kbd>super</kbd>+<kbd>c</kbd>     | iPython with NumPy loaded                  |
| `search`       | <kbd>super</kbd>+<kbd>b</kbd>     | Fuzzy file search through mdfind           |
| `snippets`     | <kbd>super</kbd>+<kbd>v</kbd>     | Paste text snippets                        |
| `buf`          | `buf`                             | Cot editor text scratch buffer             |
| `prose`        | <kbd>super</kbd>+<kbd>t</kbd>     | Minimal autosaving serif text editor       |
| `setup`        | `setup ...`                       | Save/restore/edit window setups            |
| `finderctl`    | `finderctl ...`                   | Finder integration used by workflow tools  |
| `clk`          | `clk ...`                         | Time tracking                              |
| `pbdiff`       | `pbdiff`                          | Diff the clipboard entry                   |
| `qrcode`       | `qrcode <text> --out <file>`      | Save a transparent QR code PNG             |
| `pbqr`         | `pbqr <text>`                     | Copy a QR code image to the clipboard       |
| `timer`        | `timer`                           | Timer                                      |
| `grab`         | `grab`                            | `cd` into the frontmost Finder directory   |
| `gsnap`        | `gsnap`                           | Snapshot selected Finder file              |
| `gtouch`       | `gtouch <fname>`                  | Create file in frontmost Finder directory  |
| `check_left_in_right` | `check_left_in_right [--depth N]` | Verify left Finder files exist on right |
| `diskusage`    | `diskusage`                       | List directory contents sorted by size     |
| `textitle`     | `textitle <text>`                 | Comment-prefixed figlet title to clipboard |
| `pytitle`      | `pytitle <text>`                  | Same with `#` prefix                       |
| `compose_mail` | <kbd>super</kbd>+<kbd>m</kbd>     | New Outlook message                        |
| `ten`          | `ten <word>`                      | German→English translation                 |
| `fen`          | `fen <word>`                      | English→German translation                 |
| `tfr`          | `tfr <word>`                      | German→French translation                  |
| `ffr`          | `ffr <word>`                      | French→German translation                  |
| `tit`          | `tit <word>`                      | German→Italian translation                 |
| `fit`          | `fit <word>`                      | Italian→German translation                 |
| `ask`          | `ask <question>`                  | Ask a one-off question, via opencode       |
| `oc`           | `oc`                              | Shortcut for `opencode -c`                 |
| `pyinit`       | `pyinit`                          | Create uv Python project                   |
| `nbinit`       | `nbinit`                          | Create uv Jupyter project                  |
| `pytemp`       | `pytemp`                          | uv Python project in temp directory        |
| `nbtemp`       | `nbtemp`                          | uv Jupyter project in temp directory       |

## Todo
- [ ] integrate OCR screen capture tool
