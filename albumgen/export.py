"""Hand rendered albums over in one folder: per album the 16 images, a 4x4 collage, the prompts and the story, plus an
INDEX.md, an index.html with every collage on one page, and a zip of it all."""

from __future__ import annotations

import html
import json
import re
import shutil
from pathlib import Path
from typing import Callable, Iterable

from PIL import Image, ImageDraw, ImageFont


def collage(images: list[Path], out: Path, cols: int = 4, tile_w: int = 360, labels: Iterable[str] | None = None) -> Path:
    """A grid of 2:3 tiles with a small label in the corner of each."""
    tile_h = tile_w * 3 // 2
    labels = list(labels) if labels is not None else [f"{i + 1:02d}" for i in range(len(images))]
    rows = (len(images) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tile_w, rows * tile_h), (34, 34, 34))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.load_default(size=20)
    except TypeError:  # Pillow < 10.1
        font = ImageFont.load_default()
    for i, path in enumerate(images):
        with Image.open(path) as im:
            im = im.convert("RGB")
            scale = max(tile_w / im.width, tile_h / im.height)  # cover, centred
            im = im.resize((round(im.width * scale), round(im.height * scale)))
            left, top = (im.width - tile_w) // 2, (im.height - tile_h) // 2
            tile = im.crop((left, top, left + tile_w, top + tile_h))
        x, y = (i % cols) * tile_w, (i // cols) * tile_h
        sheet.paste(tile, (x, y))
        draw.rectangle((x, y, x + 14 + 12 * len(labels[i]), y + 28), fill=(0, 0, 0))
        draw.text((x + 7, y + 4), labels[i], fill=(255, 212, 0), font=font)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, "JPEG", quality=82)
    return out


def _complete(album: Path, n: int) -> list[Path]:
    imgs = sorted((album / "images").glob("*.jpg"))
    return imgs if len(imgs) == n else []


def export(albums: list[Path], out: Path, zip_it: bool = True, log: Callable[[str], None] = print) -> list[dict]:
    """Copies complete albums (all requests have an image) to `out`; returns one row per exported album."""
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    rows = []
    for album in albums:
        requests = json.loads((album / "album.json").read_text())
        imgs = _complete(album, len(requests))
        if not imgs:
            log(f"skip {album.name}: {len(list((album / 'images').glob('*.jpg')))}/{len(requests)} images")
            continue
        data = json.loads((album / "plan.json").read_text())
        plan, outline = data.get("plan", data), data.get("outline", {})
        slug = f"{len(rows) + 1:02d}-{re.sub(r'^[0-9-]+', '', album.name)}"
        dst = out / slug
        (dst / "images").mkdir(parents=True)
        for im in imgs:
            shutil.copy(im, dst / "images" / im.name)
        shutil.copy(album / "album.json", dst / "prompts.json")
        if (album / "story.md").exists():
            shutil.copy(album / "story.md", dst / "story.md")
        collage(imgs, dst / "collage.jpg")
        c = plan["character"]
        rows.append({"slug": slug, "title": outline.get("title") or plan["theme"].get("title", album.name),
                     "theme": plan["theme"].get("id", ""), "mode": plan.get("reference_mode", "solo"),
                     "her": f"{c['age']}, {c['ethnicity']}", "place": plan["location"]["phrase"]})
        log(f"{slug}")
    md = ["# Albums (shot 1 + 15 pages each)", "", "| # | Album | Story | Mode | Her | Place |", "|---|---|---|---|---|---|"]
    md += [f"| {i + 1} | [{r['slug']}]({r['slug']}/collage.jpg) | {r['title']} | {r['mode']} | {r['her']} | {r['place']} |"
           for i, r in enumerate(rows)]
    (out / "INDEX.md").write_text("\n".join(md) + "\n")
    cards = "\n".join(
        f'<section><h2>{i + 1}. {html.escape(r["title"])} <small>{r["mode"]} · {html.escape(r["her"])} · '
        f'{html.escape(r["place"])}</small></h2><a href="{r["slug"]}/collage.jpg"><img loading="lazy" '
        f'src="{r["slug"]}/collage.jpg" alt="{r["slug"]}"></a></section>' for i, r in enumerate(rows))
    (out / "index.html").write_text(
        '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Albums</title>'
        "<style>body{background:#111;color:#eee;font:15px system-ui;margin:16px}section{margin:0 0 32px}"
        "h2{font-size:17px}small{color:#999;font-weight:400}img{width:100%;max-width:1440px;height:auto;display:block}"
        f"</style><h1>{len(rows)} albums</h1>{cards}")
    if zip_it:
        shutil.make_archive(str(out), "zip", out.parent, out.name)
    return rows
