import argparse
import os
import pathlib
import re
import subprocess
import time
from difflib import SequenceMatcher

import pyperclip
import yaml
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.shortcuts import CompleteStyle
from prompt_toolkit.styles import Style

RESTART_ENV = "SNIPPETS_RESTART_FILE"
HIDE_HOTKEY_WINDOW = """
tell application "iTerm2"
  tell current window
    hide hotkey window
  end tell
end tell
"""


def _hide_hotkey_window():
    if RESTART_ENV not in os.environ:
        return
    subprocess.run(
        ["/usr/bin/osascript", "-e", HIDE_HOTKEY_WINDOW], check=False
    )


def _request_restart():
    restart_file = os.environ.get(RESTART_ENV)
    if restart_file:
        pathlib.Path(restart_file).touch()


def normalize(text):
    return "".join(ch for ch in text.lower() if ch.isalnum())


def tokenize(text):
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def resolve_selection(selection, snippets):
    if selection in snippets:
        return selection

    normalized_input = normalize(selection)
    if not normalized_input:
        return None

    keys = list(snippets.keys())
    normalized_keys = {key: normalize(key) for key in keys}

    exact_norm = [key for key in keys if normalized_keys[key] == normalized_input]
    if exact_norm:
        return exact_norm[0]

    scored = []
    for key in keys:
        norm_key = normalized_keys[key]
        if not norm_key:
            continue

        score = SequenceMatcher(None, normalized_input, norm_key).ratio()
        if norm_key.startswith(normalized_input):
            score += 0.35
        elif normalized_input in norm_key:
            score += 0.2
        scored.append((score, key))

    if not scored:
        return None

    scored.sort(reverse=True)
    best_score, best_key = scored[0]
    return best_key if best_score >= 0.55 else None


class DedupAliasCompleter(Completer):
    def __init__(self, alias_items, alias_to_key):
        self.alias_items = alias_items
        self.alias_to_key = alias_to_key

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        normalized_input = normalize(text)
        seen = set()
        scored = []
        for item in self.alias_items:
            canonical = self.alias_to_key.get(item, item)
            if not normalized_input:
                score = 0
            else:
                normalized_item = normalize(item)
                normalized_canonical = normalize(canonical)
                score = max(
                    SequenceMatcher(None, normalized_input, normalized_item).ratio(),
                    SequenceMatcher(None, normalized_input, normalized_canonical).ratio(),
                )
                if normalized_item.startswith(normalized_input):
                    score += 0.35
                elif normalized_input in normalized_item:
                    score += 0.2
                if normalized_canonical.startswith(normalized_input):
                    score += 0.35
                elif normalized_input in normalized_canonical:
                    score += 0.2
            if score >= 0.55 or not normalized_input:
                scored.append((score, item, canonical))

        scored.sort(reverse=True)
        for _score, _item, canonical in scored:
            if canonical in seen:
                continue
            seen.add(canonical)
            yield Completion(
                text=canonical,
                start_position=-len(document.text_before_cursor),
                display=f"{canonical} ",
            )


def interactive(completer):
    kb = KeyBindings()

    style = Style.from_dict(
        {
            "completion-menu": "bg:#222222 #dddddd",
            "completion-menu.completion.current": "bg:#00afff #000000",
            "completion-menu.meta": "bg:#222222 #888888",
            "scrollbar.background": "bg:#444444",
            "scrollbar.button": "bg:#888888",
        }
    )

    session = PromptSession(
        completer=completer,
        complete_while_typing=True,
        key_bindings=kb,
        complete_style=CompleteStyle.MULTI_COLUMN,
        style=style,
    )

    @kb.add("enter")
    def _(event):
        buf = event.app.current_buffer
        if buf.text.strip() == "closing":
            event.app.exit(result="closing")
            return
        if not buf.text.strip():
            buf.validate_and_handle()
            return
        cs = buf.complete_state
        if cs and cs.current_completion:
            buf.apply_completion(cs.current_completion)
        else:
            doc = Document(text=buf.text, cursor_position=buf.cursor_position)
            comps = list(completer.get_completions(doc, None))
            if comps:
                buf.apply_completion(comps[0])
        buf.validate_and_handle()

    # Numeric selection (1-9)
    @kb.add("1")
    @kb.add("2")
    @kb.add("3")
    @kb.add("4")
    @kb.add("5")
    @kb.add("6")
    @kb.add("7")
    @kb.add("8")
    @kb.add("9")
    def _(event):
        buf = event.app.current_buffer
        if buf.complete_state and buf.complete_state.completions:
            index = int(event.data) - 1
            if index < len(buf.complete_state.completions):
                buf.apply_completion(buf.complete_state.completions[index])
                buf.validate_and_handle()
                return
        buf.insert_text(event.data)

    return session.prompt("select > ")


def parse_args():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--hide",
        action="store_true",
        help="Hide iTerm2 after selecting a snippet (default).",
    )
    group.add_argument(
        "--close",
        action="store_true",
        help="Close the current window/tab (Cmd+W) after selecting a snippet.",
    )
    parser.add_argument(
        "--edit",
        "--add",
        action="store_true",
        help="Open the snippets config file.",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="With --edit, open the local snippets config file.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    if args.local and not args.edit:
        raise SystemExit("snippets: --local only applies with --edit")

    root = pathlib.Path(__file__).parents[3]
    local_root = pathlib.Path(os.environ.get("TOOLBELT_LOCAL", pathlib.Path.home() / ".toolbelt-local"))
    shared_yaml_path = root / "config" / "snippets" / "snippets.yaml"
    local_yaml_path = local_root / "snippets" / "snippets.yaml"

    if not shared_yaml_path.exists():
        print(f"❌ File not found: {shared_yaml_path}")
        return

    if args.edit:
        edit_path = local_yaml_path if args.local else shared_yaml_path
        if args.local and not edit_path.exists():
            edit_path.parent.mkdir(parents=True, exist_ok=True)
            edit_path.write_text("{}\n")
        subprocess.run(["open", str(edit_path)])
        return

    # toilet Snippets -f pagga
    title = [
        "░█▀▀░█▀█░▀█▀░█▀█░█▀█░█▀▀░▀█▀░█▀▀",
        "░▀▀█░█░█░░█░░█▀▀░█▀▀░█▀▀░░█░░▀▀█",
        "░▀▀▀░▀░▀░▀▀▀░▀░░░▀░░░▀▀▀░░▀░░▀▀▀",
    ]
    print()
    for line in title:
        pad = (70 - len(line)) // 2
        print(pad * " " + line)
    print()

    def load_yaml_dict(path):
        if not path.exists():
            return {}
        try:
            with open(path, "r") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            print(f"❌ Invalid YAML in {path}:")
            print(e)
            input("Press Enter to edit.")
            subprocess.run(["open", str(path)])
            return None
        return data if isinstance(data, dict) else {}

    def flatten(data):
        flattened = {}
        for category, items in data.items():
            if isinstance(items, dict):
                for name, content in items.items():
                    flattened[f"{category}: {name}"] = content
            else:
                flattened[category] = items
        return flattened

    shared_data = load_yaml_dict(shared_yaml_path)
    local_data = load_yaml_dict(local_yaml_path)
    if shared_data is None or local_data is None:
        return

    categories = list(dict.fromkeys([*shared_data.keys(), *local_data.keys()]))

    # Local snippets override shared on key conflicts.
    snippets = flatten(shared_data)
    snippets.update(flatten(local_data))

    if not snippets:
        print("No snippets found in YAML.")
        return

    if categories:
        hint = "available categories: " + ", ".join(categories)
        pad = (70 - len(hint)) // 2
        print(pad * " " + hint)
        print()

    completion_to_key = {}
    for key in snippets.keys():
        completion_to_key[key] = key

        compact = normalize(key)
        if compact and compact not in completion_to_key:
            completion_to_key[compact] = key

        tokenized = tokenize(key)
        if tokenized and tokenized not in completion_to_key:
            completion_to_key[tokenized] = key

    completion_to_key["edit"] = "edit"

    completer = DedupAliasCompleter(list(completion_to_key.keys()), completion_to_key)
    selection = interactive(completer)
    if selection == "closing":
        _hide_hotkey_window()
        _request_restart()
        return

    resolved = completion_to_key.get(selection) or resolve_selection(
        selection, snippets
    )

    if resolved == "edit":
        _hide_hotkey_window()
        subprocess.run(["open", str(shared_yaml_path)])
        _request_restart()
        return

    if resolved in snippets:
        content = snippets[resolved].strip()
        pyperclip.copy(content)
        print(f"Copied to clipboard!")

        if RESTART_ENV in os.environ:
            _hide_hotkey_window()
        elif args.close:
            close_cmd = (
                'tell application "System Events" to keystroke "w" using {command down}'
            )
            subprocess.run(["osascript", "-e", close_cmd])
        else:
            hide_cmd = 'tell application "System Events" to set visible of process "iTerm2" to false'
            subprocess.run(["osascript", "-e", hide_cmd])

        time.sleep(0.15)

        paste_cmd = (
            'tell application "System Events" to keystroke "v" using {command down}'
        )
        subprocess.run(["osascript", "-e", paste_cmd])
        _request_restart()
        return

    print("❌ Selection not found.")


if __name__ == "__main__":
    main()
