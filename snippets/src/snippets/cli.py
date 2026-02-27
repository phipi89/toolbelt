import argparse
import pathlib
import re
import subprocess
import time
from difflib import SequenceMatcher

import pyperclip
import yaml
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion, WordCompleter
from prompt_toolkit.document import Document
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.shortcuts import CompleteStyle
from prompt_toolkit.styles import Style


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
        display_dict = {item: f"{alias_to_key[item]} " for item in alias_items}
        self.alias_to_key = alias_to_key
        self.base = WordCompleter(
            alias_items, display_dict=display_dict, ignore_case=True, match_middle=True
        )

    def get_completions(self, document, complete_event):
        seen = set()
        for completion in self.base.get_completions(document, complete_event):
            canonical = self.alias_to_key.get(completion.text, completion.text)
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
    return parser.parse_args()


def main():
    args = parse_args()

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

    root = pathlib.Path(__file__).parents[3]
    shared_yaml_path = root / "config" / "snippets" / "snippets.yaml"
    private_yaml_path = root / "config" / "private" / "snippets.yaml"

    if not shared_yaml_path.exists():
        print(f"❌ File not found: {shared_yaml_path}")
        return

    def load_yaml_dict(path):
        if not path.exists():
            return {}
        with open(path, "r") as f:
            data = yaml.safe_load(f)
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
    private_data = load_yaml_dict(private_yaml_path)

    categories = list(dict.fromkeys([*shared_data.keys(), *private_data.keys()]))

    # Private snippets override shared on key conflicts.
    snippets = flatten(shared_data)
    snippets.update(flatten(private_data))

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
    resolved = completion_to_key.get(selection) or resolve_selection(
        selection, snippets
    )

    if resolved == "edit":
        subprocess.run(["open", str(shared_yaml_path)])
        return

    if resolved in snippets:
        content = snippets[resolved].strip()
        pyperclip.copy(content)
        print(f"Copied to clipboard!")

        if args.close:
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
        return

    print("❌ Selection not found.")


if __name__ == "__main__":
    main()
