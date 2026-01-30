#!/usr/bin/env -S uv run
# /// script
# dependencies = ["pyperclip", "pyyaml", "prompt_toolkit"]
# ///

import pathlib

import pyperclip
import yaml
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.document import Document
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.shortcuts import CompleteStyle
from prompt_toolkit.styles import Style


def interactive(items):
    items = list(items)
    # Add trailing padding for the menu
    display_dict = {item: f"{item} " for item in items}
    completer = WordCompleter(
        items, display_dict=display_dict, ignore_case=True, match_middle=True
    )
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

    return session.prompt("Snippet > ")


def main():
    yaml_path = (
        pathlib.Path(__file__).parents[1] / "config" / "snippets" / "snippets.yaml"
    )

    if not yaml_path.exists():
        print(f"❌ File not found: {yaml_path}")
        return

    with open(yaml_path, "r") as f:
        data = yaml.safe_load(f)

    # Flatten the nested YAML: {"py": {"init": "..."}} -> {"py: init": "..."}
    snippets = {}
    if data:
        for category, items in data.items():
            if isinstance(items, dict):
                for name, content in items.items():
                    snippets[f"{category}: {name}"] = content
            else:
                # Fallback if a top-level item isn't a category dict
                snippets[category] = items

    if not snippets:
        print("⚠️ No snippets found in YAML.")
        return

    selection = interactive(snippets.keys())

    if selection in snippets:
        content = snippets[selection].strip()
        pyperclip.copy(content)
        print(f"✨ Copied to clipboard!")

        # Optional: Hide iTerm hotkey window after copying
        # import os
        # os.system('osascript -e "tell application \\"iTerm2\\" to hide (every window whose name contains \\"Hotkey\\")"')
    else:
        print("❌ Selection not found.")


if __name__ == "__main__":
    main()
