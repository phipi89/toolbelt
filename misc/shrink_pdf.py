#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pikepdf>=10,<11", "pillow>=11,<14", "pymupdf>=1.26,<2"]
# ///
"""Balanced PDF compression: replace image streams, preserve page content."""

import argparse
import io
import math
import os
import shutil
import sys
import tempfile
from collections import Counter
from pathlib import Path

import pikepdf
import pymupdf
from PIL import Image


def image_resolutions(source):
    """Use the lowest DPI (largest placement) of each shared image."""
    resolutions = {}
    with pymupdf.open(source) as doc:
        for page in doc:
            for info in page.get_image_info(xrefs=True):
                xref = info["xref"]
                a, b, c, d, _, _ = info["transform"]
                width, height = math.hypot(a, b), math.hypot(c, d)
                if xref and width and height:
                    dpi = min(info["width"] * 72 / width, info["height"] * 72 / height)
                    resolutions[xref] = min(resolutions.get(xref, dpi), dpi)
    return resolutions


def supported_color(obj):
    color = obj.get("/ColorSpace")
    if color in (pikepdf.Name.DeviceRGB, pikepdf.Name.DeviceGray):
        return True
    return (
        isinstance(color, pikepdf.Array)
        and len(color) == 2
        and color[0] == "/ICCBased"
        and color[1].get("/N") in (1, 3)
    )


def compress_images(pdf, resolutions):
    masks = Counter()
    for obj in pdf.objects:
        if isinstance(obj, pikepdf.Stream) and obj.get("/Subtype") == "/Image":
            for key in ("/SMask", "/Mask"):
                mask = obj.get(key)
                if isinstance(mask, pikepdf.Stream):
                    masks[mask.objgen] += 1

    for obj in pdf.objects:
        if not isinstance(obj, pikepdf.Stream) or obj.get("/Subtype") != "/Image":
            continue
        if (
            obj.objgen in masks
            or obj.get("/ImageMask", False)
            or obj.get("/BitsPerComponent") != 8
            or not supported_color(obj)
            or any(key in obj for key in ("/Decode", "/Mask", "/SMaskInData"))
        ):
            continue
        old_size = len(obj.read_raw_bytes())
        if old_size < 80_000:
            continue
        scale = min(1, 144 / resolutions.get(obj.objgen[0], 144))
        resize = scale < 0.8
        mask = obj.get("/SMask")
        # A shared mask must not be resized underneath another image.
        if (
            resize
            and mask is not None
            and (
                masks[mask.objgen] != 1
                or mask.get("/BitsPerComponent") != 8
                or "/Decode" in mask
                or mask.get("/ColorSpace") != "/DeviceGray"
                or (mask.Width, mask.Height) != (obj.Width, obj.Height)
            )
        ):
            resize = False
        if obj.get("/Filter") == "/DCTDecode" and not resize:
            continue
        try:
            image = pikepdf.PdfImage(obj).as_pil_image()
            if image.mode == "RGBA":
                image = image.convert("RGB")  # Alpha stays in the PDF's /SMask.
            elif image.mode == "LA":
                image = image.getchannel("L")
            if image.mode not in ("RGB", "L"):
                continue
            # Flat-colour artwork and indexed graphics should remain lossless.
            if (
                image.getcolors(maxcolors=256 if image.mode == "RGB" else 32)
                is not None
            ):
                continue
            if resize:
                size = (
                    max(1, round(image.width * scale)),
                    max(1, round(image.height * scale)),
                )
                image = image.resize(size, Image.Resampling.LANCZOS)
            encoded = io.BytesIO()
            image.save(encoded, format="JPEG", quality=78, subsampling=2, optimize=True)
            data = encoded.getvalue()
            if len(data) >= old_size * 0.9:
                continue
            alpha = None
            if resize and mask is not None:
                alpha = (
                    pikepdf.PdfImage(mask)
                    .as_pil_image()
                    .resize(size, Image.Resampling.LANCZOS)
                )
            obj.write(data, filter=pikepdf.Name.DCTDecode)
            if resize:
                obj.Width, obj.Height = size
                if alpha is not None:
                    mask.write(alpha.tobytes())
                    mask.Width, mask.Height = size
        except (NotImplementedError, pikepdf.PdfError, OSError, ValueError):
            # Unsupported image encodings remain as originally embedded.
            continue


def compress(source: Path, output: Path):
    if output.exists():
        raise FileExistsError(f"output already exists: {output}")
    resolutions = image_resolutions(source)
    with tempfile.TemporaryDirectory(prefix=".shrink-", dir=output.parent) as temp:
        candidate = Path(temp) / "compressed.pdf"
        with pikepdf.open(source) as pdf:
            compress_images(pdf, resolutions)
            pdf.save(
                candidate,
                compress_streams=True,
                object_stream_mode=pikepdf.ObjectStreamMode.generate,
            )
        if candidate.stat().st_size >= source.stat().st_size:
            shutil.copyfile(source, candidate)
        # Publish only a complete file, without replacing an existing output.
        os.link(candidate, output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        compress(args.input, args.output)
    except (OSError, pikepdf.PdfError, RuntimeError, ValueError) as error:
        print(f"shrink: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
