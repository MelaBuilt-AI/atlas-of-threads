#!/usr/bin/env python3
"""Prepare generated Thought Archaeology relics for the Inhabit Space.

The source GLBs contain 4K embedded PBR textures. This importer keeps all
geometry, accessors, materials, and texture channels while resizing embedded
images to a chamber-appropriate 1K. Matching PNG renders become atlas cards.
"""

from __future__ import annotations

import argparse
import json
import struct
import subprocess
import tempfile
from pathlib import Path


GLB_HEADER = struct.Struct("<4sII")
CHUNK_HEADER = struct.Struct("<II")
JSON_CHUNK = 0x4E4F534A
BIN_CHUNK = 0x004E4942


def slug(name: str) -> str:
    return name.lower().replace(" ", "-")


def convert_image(source: Path, target: Path, *, size: int, quality: int) -> None:
    command = [
        "magick",
        str(source),
        "-resize",
        f"{size}x{size}>",
        "-strip",
    ]
    if target.suffix.lower() in {".jpg", ".jpeg"}:
        command.extend(["-sampling-factor", "4:2:0", "-quality", str(quality)])
    else:
        command.extend(["-define", "png:compression-level=9"])
    command.append(str(target))
    subprocess.run(command, check=True)


def read_glb(path: Path) -> tuple[dict, bytes]:
    raw = path.read_bytes()
    magic, version, total = GLB_HEADER.unpack_from(raw)
    if magic != b"glTF" or version != 2 or total != len(raw):
        raise ValueError(f"unsupported GLB: {path}")
    offset = GLB_HEADER.size
    chunks: dict[int, bytes] = {}
    while offset < len(raw):
        length, kind = CHUNK_HEADER.unpack_from(raw, offset)
        offset += CHUNK_HEADER.size
        chunks[kind] = raw[offset : offset + length]
        offset += length
    return json.loads(chunks[JSON_CHUNK]), chunks[BIN_CHUNK]


def write_glb(path: Path, document: dict, binary: bytes) -> None:
    json_bytes = json.dumps(document, separators=(",", ":")).encode("utf-8")
    json_bytes += b" " * (-len(json_bytes) % 4)
    binary += b"\0" * (-len(binary) % 4)
    total = GLB_HEADER.size + 2 * CHUNK_HEADER.size + len(json_bytes) + len(binary)
    path.write_bytes(
        GLB_HEADER.pack(b"glTF", 2, total)
        + CHUNK_HEADER.pack(len(json_bytes), JSON_CHUNK)
        + json_bytes
        + CHUNK_HEADER.pack(len(binary), BIN_CHUNK)
        + binary
    )


def optimize_glb(source: Path, target: Path, *, texture_size: int, quality: int) -> None:
    document, binary = read_glb(source)
    replacements: dict[int, bytes] = {}
    with tempfile.TemporaryDirectory(prefix="ta-relic-") as tmp_name:
        tmp = Path(tmp_name)
        for index, image in enumerate(document.get("images", [])):
            view_index = image["bufferView"]
            view = document["bufferViews"][view_index]
            start = view.get("byteOffset", 0)
            end = start + view["byteLength"]
            suffix = ".jpg" if image["mimeType"] == "image/jpeg" else ".png"
            original = tmp / f"{index}-source{suffix}"
            resized = tmp / f"{index}-runtime{suffix}"
            original.write_bytes(binary[start:end])
            convert_image(original, resized, size=texture_size, quality=quality)
            replacements[view_index] = resized.read_bytes()

    rebuilt = bytearray()
    views = document.get("bufferViews", [])
    ordered = sorted(enumerate(views), key=lambda item: item[1].get("byteOffset", 0))
    previous_end = 0
    for view_index, view in ordered:
        old_start = view.get("byteOffset", 0)
        old_end = old_start + view["byteLength"]
        if old_start < previous_end:
            raise ValueError(f"overlapping buffer views are not supported: {source}")
        rebuilt.extend(b"\0" * (-len(rebuilt) % 4))
        view["byteOffset"] = len(rebuilt)
        data = replacements.get(view_index, binary[old_start:old_end])
        view["byteLength"] = len(data)
        rebuilt.extend(data)
        previous_end = old_end

    document["buffers"][0]["byteLength"] = len(rebuilt)
    target.parent.mkdir(parents=True, exist_ok=True)
    write_glb(target, document, bytes(rebuilt))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--texture-size", type=int, default=1024)
    parser.add_argument("--preview-size", type=int, default=360)
    parser.add_argument("--jpeg-quality", type=int, default=84)
    args = parser.parse_args()

    models = args.output / "models"
    previews = args.output / "previews"
    for glb in sorted(args.source.glob("*.glb")):
        key = slug(glb.stem)
        png = glb.with_suffix(".png")
        if not png.is_file():
            raise FileNotFoundError(f"matching preview missing for {glb.name}")
        optimize_glb(
            glb,
            models / f"{key}.glb",
            texture_size=args.texture_size,
            quality=args.jpeg_quality,
        )
        previews.mkdir(parents=True, exist_ok=True)
        convert_image(
            png,
            previews / f"{key}.png",
            size=args.preview_size,
            quality=args.jpeg_quality,
        )
        print(key)


if __name__ == "__main__":
    main()
