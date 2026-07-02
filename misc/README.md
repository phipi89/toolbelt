## Miscellaneous

A collection of smaller, miscellaneous snippets.
Shell helpers here are generally simple functions intended to be sourced.
For python based tools, we might skip building dedicated envs and use a shebang with metadata block to define dependencies:

```sh
#!/usr/bin/env -S uv run
# /// script
# dependencies = ["pyperclip", "pyfiglet"]
# ///
```
