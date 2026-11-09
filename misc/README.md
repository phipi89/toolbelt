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

### PDF compression

`shrink [--balanced|--minimal] INPUT.pdf [OUTPUT.pdf]` defaults to balanced
compression and an output named `INPUT_small.pdf`. `gshrink` uses the file selected
in Finder. Existing output files are never replaced.

- **Balanced:** requires `uv`, which installs the Python helper's declared
  dependencies (pikepdf, Pillow, PyMuPDF) on first use. Compresses suitable large
  image streams at JPEG quality 78 and downsamples images above 180 effective DPI
  to 144 DPI. Shared images use their largest displayed size. Preserves page
  content, text, colour profiles, and transparency; resized masks are stored
  losslessly. Indexed/flat-colour graphics, explicit image masks, unusual colour
  spaces, and unsupported encodings are left intact. Shared transparency masks
  are not resized. If the result would be larger, copies the original instead.
- **Minimal:** requires Ghostscript (`brew install ghostscript`) and uses its
  aggressive `/screen` PDF rewrite, which can change complex graphics.

Checks (from the toolbelt root):

```sh
zsh misc/test_shrink.zsh
uv run --with pikepdf --with pillow --with 'pymupdf<2' python -m unittest discover -s misc -p test_shrink_pdf.py
```
