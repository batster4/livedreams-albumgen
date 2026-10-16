"""Command line: `albumgen new`, `themes`, `arcs`, `list`, `show`, `check`, `render`, `fix`, `export`, `feedback`, `stats`,
`forget`, `audit`, `doctor`."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Optional

import typer

from .config import Config
from .library import STATUS_WEIGHT, Library
from .memory import Memory

app = typer.Typer(add_completion=False, help="Story and prompt generator for 1+15 canvas albums.")
CONFIG = typer.Option("config.yaml", "--config", "-c", help="Path to config.yaml")


def _ctx(config: str) -> tuple[Config, Library, Memory]:
    cfg = Config.load(config)
    return cfg, Library.load(cfg.path(cfg.data_dir)), Memory(cfg.path(cfg.memory.db_path))


@app.command()
def new(
    count: int = typer.Option(1, "--count", "-n", help="How many albums"),
    theme: Optional[str] = typer.Option(None, help="Theme id (see `albumgen themes`); random if omitted"),
    arc: Optional[str] = typer.Option(None, help="Arc id; picked from the theme if omitted"),
    mode: Optional[str] = typer.Option(None, help="Shot 1: solo | couple (overrides the theme; two-women themes stay ff)"),
    family: Optional[list[str]] = typer.Option(None, "--family", "-f", help="Only these theme families (repeat the option)"),
    seed: Optional[int] = typer.Option(None, help="Reproducible sampling (one album)"),
    model: Optional[str] = typer.Option(None, help="Override llm.model"),
    temp_story: Optional[float] = typer.Option(None, help="Override llm.outline.temperature"),
    temp_writer: Optional[float] = typer.Option(None, help="Override llm.writer.temperature"),
    dry_run: bool = typer.Option(False, "--dry-run", help="No LLM: recipe-only prompts (for testing)"),
    no_save: bool = typer.Option(False, "--no-save", help="Do not write files or memory"),
    config: str = CONFIG,
):
    """Generate album(s): out/<album_id>/album.json + story.md + plan.json, and remember them."""
    from .pipeline import make_album

    cfg, lib, mem = _ctx(config)
    if family:
        cfg.album.only_families = list(family)
    if model:
        cfg.llm.model = model
    if temp_story is not None:
        cfg.llm.outline.temperature = temp_story
    if temp_writer is not None:
        cfg.llm.writer.temperature = temp_writer
    llm = None
    if not dry_run:
        from .llm import make_llm

        llm = make_llm(cfg.llm)
        if llm is None:
            typer.echo(f"No LLM configured (llm.model / {cfg.llm.api_key_env}): albums are written from the tested "
                       "recipes. Add an LLM for more varied stories, see README.")
    for i in range(count):
        res = make_album(cfg, theme=theme, arc=arc, mode=mode, seed=seed if count == 1 else None, llm=llm,
                         dry_run=dry_run, save=not no_save, library=lib, memory=mem)
        made = Counter(s.split(" ")[0] for s in res.sources.values())
        typer.echo(f"[{i + 1}/{count}] {res.album_id}  “{res.outline.get('title')}”  pages: {dict(made)}"
                   + (f"  ISSUES: {res.issues}" if res.issues else "") + (f"  → {res.dir}" if not no_save else ""))
    if llm is not None:
        typer.echo(f"LLM calls: {llm.calls}")


@app.command()
def themes(family: Optional[str] = typer.Option(None, help="Only this family"), config: str = CONFIG):
    """List themes with family, status and suggested arcs."""
    cfg, lib, mem = _ctx(config)
    used = mem.counts("theme_id")
    for t in lib.themes:
        if family and t["family"] != family:
            continue
        typer.echo(f"{t['family']:<22} {t['id']:<28} {t.get('status', ''):<6} used {used.get(t['id'], 0):<3} "
                   f"{','.join(t.get('arcs', []))}  {t['title']}")


@app.command()
def arcs(config: str = CONFIG):
    """List story arcs."""
    _, lib, _ = _ctx(config)
    for a in lib.arcs.values():
        typer.echo(f"{a['id']:<16} {a['label']}")


@app.command("list")
def list_albums(n: int = typer.Option(20, "-n"), config: str = CONFIG):
    """Recent albums from memory."""
    _, _, mem = _ctx(config)
    for r in mem.list(n):
        typer.echo(f"{r['created_at']}  {r['album_id']:<48} {r['status']:<10} {r['theme_id']:<26} {r['title'] or ''}")


@app.command()
def show(album_id: str, config: str = CONFIG):
    """Print an album's story.md."""
    cfg, _, _ = _ctx(config)
    typer.echo((cfg.path(cfg.out_dir) / album_id / "story.md").read_text())


@app.command()
def check(path: str, config: str = CONFIG):
    """Validate any album.json (yours or ours) against the prompting rules."""
    from .validate import check_file

    cfg, lib, _ = _ctx(config)
    issues = check_file(lib, path, cfg.album.min_age)
    if not issues:
        typer.echo("OK: no issues")
        return
    for shot, items in sorted(issues.items()):
        typer.echo(f"shot {shot}: " + "; ".join(items))
    raise typer.Exit(1)


def _album_dirs(cfg: Config, album_ids: list[str]) -> list[Path]:
    root = cfg.path(cfg.out_dir)
    if not album_ids:
        found = sorted(d for d in root.iterdir() if (d / "album.json").exists()) if root.is_dir() else []
        if not found:
            typer.echo(f"no albums in {root}: run `albumgen new` first")
        return found
    dirs = []
    for a in album_ids:
        try:
            d = Path(a) if Path(a).is_dir() else root / a
            found = (d / "album.json").exists()
        except OSError:  # e.g. several paths passed as one argument
            found = False
            d = Path(a[:80] + "...")
        if not found:
            raise typer.BadParameter(f"no album.json in {d}")
        dirs.append(d)
    return dirs


def _renderer(cfg: Config):
    from .render import Renderer

    try:
        return Renderer(cfg.render, log=lambda s: typer.echo(f"  {s}"))
    except RuntimeError as e:  # no API key
        typer.echo(f"{e}: put it in .env next to config.yaml (see README → Quick start)")
        raise typer.Exit(1)


@app.command()
def render(album_ids: list[str] = typer.Argument(None, help="Album ids or folders; all albums in out_dir if omitted"),
           config: str = CONFIG):
    """Render albums through the LiveDreams API, one album at a time (needs LIVEDREAMS_API_KEY). Safe to re-run:
    pages with an image are kept, unfinished jobs are picked up again, failed pages get one new try."""
    cfg, _, mem = _ctx(config)
    renderer = _renderer(cfg)
    for d in _album_dirs(cfg, album_ids or []):
        results = renderer.render(d)
        ok = sum(r["status"] == "succeeded" for r in results)
        typer.echo(f"{d.name}: {ok}/{len(results)} succeeded → {d / 'images'}")
        if ok == len(results):
            mem.set_status(d.name, "rendered")


@app.command()
def fix(album_id: str,
        pages: str = typer.Option(..., "--pages", "-p", help="Pages to rebuild, e.g. 4,9,16"),
        pose: Optional[list[str]] = typer.Option(None, "--pose", help="Force a pose for a page: 9=reverse_cowgirl"),
        no_render: bool = typer.Option(False, "--no-render", help="Only rewrite the prompts"),
        config: str = CONFIG):
    """Rebuild pages of a rendered album with the current rules and render only them again. Use it for pages a
    review rejected (a smile during sex, clothes back on, no penetration, his face in a solo album, ...). The page
    keeps its pose unless that pose is retired or does not fit; `--pose` forces another one."""
    from .fix import prepare

    cfg, lib, mem = _ctx(config)
    d = _album_dirs(cfg, [album_id])[0]
    shots: dict[int, Optional[str]] = {int(s): None for s in pages.split(",") if s.strip()}
    for item in pose or []:
        shot, pid = item.split("=", 1)
        if pid not in lib.positions:
            raise typer.BadParameter(f"unknown pose {pid}")
        shots[int(shot)] = pid
    if 1 in shots:
        raise typer.BadParameter("shot 1 is the reference of every page: generate a new album instead")
    renderer = None if no_render else _renderer(cfg)  # before anything changes on disk
    prepare(d, lib, shots, log=lambda s: typer.echo(f"  {s}"), memory=mem)
    if renderer is not None:
        results = renderer.render(d)
        ok = sum(r["status"] == "succeeded" for r in results)
        typer.echo(f"{d.name}: {ok}/{len(results)} succeeded")


@app.command()
def export(album_ids: list[str] = typer.Argument(None, help="Album ids or folders; all rendered albums if omitted"),
           out: str = typer.Option("albums-export", "--out", "-o", help="Target folder (replaced)"),
           no_zip: bool = typer.Option(False, "--no-zip"),
           config: str = CONFIG):
    """Collect complete albums into one folder: images, a 4x4 collage, prompts and story per album, INDEX.md,
    index.html with every collage, and a zip."""
    from .export import export as run

    cfg, _, _ = _ctx(config)
    rows = run(_album_dirs(cfg, album_ids or []), Path(out), zip_it=not no_zip, log=lambda s: typer.echo(f"  {s}"))
    typer.echo(f"{len(rows)} albums → {out}" + ("" if no_zip else f" (+ {out}.zip)"))


@app.command()
def feedback(album_id: str,
             bad: str = typer.Option("", help="Comma-separated shots that failed, e.g. 9,12"),
             good: str = typer.Option("", help="Comma-separated shots that were fine, or 'rest'"),
             reason: str = typer.Option("", help="What went wrong"),
             config: str = CONFIG):
    """Teach the sampler: failed positions get a lower weight next time."""
    _, _, mem = _ctx(config)
    bad_shots = [int(x) for x in bad.split(",") if x.strip()]
    if good.strip() == "rest":
        good_shots = [s for s in range(2, 17) if s not in bad_shots]
    else:
        good_shots = [int(x) for x in good.split(",") if x.strip()]
    n = mem.add_feedback(album_id, bad_shots, "bad", reason) + mem.add_feedback(album_id, good_shots, "good")
    typer.echo(f"recorded {n} verdicts")


@app.command()
def stats(config: str = CONFIG):
    """Positions with feedback and their current weight."""
    _, lib, mem = _ctx(config)
    st = mem.position_stats()
    typer.echo(f"albums in memory: {mem.total()}")
    for pid, (g, b) in sorted(st.items(), key=lambda kv: -kv[1][1]):
        pos = lib.positions.get(pid, {})
        base = STATUS_WEIGHT.get(pos.get("status", "ok"), 0.6)
        typer.echo(f"{pid:<30} {pos.get('status', '?'):<6} good {g:<3} bad {b:<3} weight {base * max(0.1, (g + 2) / (g + b + 2)):.2f}")


@app.command()
def forget(album_id: str, config: str = CONFIG):
    """Remove an album (and its feedback) from memory; files stay."""
    _, _, mem = _ctx(config)
    mem.forget(album_id)
    typer.echo("forgotten")


@app.command()
def audit(n: int = typer.Option(300, "-n", help="How many albums to sample"), config: str = CONFIG):
    """Sample albums without the LLM and check every prompt for contradictions (bed without a bed, dressed while
    naked, smiles during sex, his face in solo albums, poses marked avoid, ...)."""
    from .audit import audit as run

    cfg, lib, _ = _ctx(config)
    counts, examples = run(cfg, lib, n=n)
    typer.echo(f"{n} albums, {sum(counts.values())} problems")
    for k, c in counts.most_common():
        typer.echo(f"  {c:4d}  {k}")
    for e in examples[:15]:
        typer.echo(f"    {e}")


@app.command()
def doctor(ping: bool = typer.Option(False, help="Also check the API key (free request) and the LLM connection"),
           config: str = CONFIG):
    """Check config, library references, the API key and (optionally) the connections."""
    cfg, lib, mem = _ctx(config)
    errs = lib.check()
    poses = [p for p in lib.positions.values() if not p.get("beat")]
    typer.echo(f"library: {len(lib.themes)} themes, {len(poses)} poses "
               f"({sum(p.get('status') != 'avoid' for p in poses)} in use) + {len(lib.positions) - len(poses)} story beats, "
               f"{len(lib.locations)} locations — "
               + ("OK" if not errs else f"{len(errs)} errors: {errs[:5]}"))
    typer.echo(f"memory: {cfg.path(cfg.memory.db_path)} ({mem.total()} albums)")
    rkey = cfg.render.api_key()
    typer.echo(f"api: {cfg.render.base_url} " + (f"MISSING {cfg.render.api_key_env} (needed for `albumgen render`)" if not rkey
               else "sandbox key (placeholder images)" if rkey.startswith("ldk_test_") else "key set"))
    llm_on = bool(cfg.llm.model and cfg.llm.api_key())
    typer.echo(f"llm: provider={cfg.llm.provider} model={cfg.llm.model or '(unset)'} key={'set' if cfg.llm.api_key() else 'MISSING ' + cfg.llm.api_key_env}"
               + ("" if llm_on else "  → optional: albums use the tested recipe texts"))
    if ping:
        if rkey:
            import httpx

            try:
                r = httpx.get(cfg.render.base_url.rstrip("/") + "/limits", timeout=20,
                              headers={"Authorization": f"Bearer {rkey}", "User-Agent": "albumgen/1.0"})
                body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
                typer.echo(f"api ping: OK, key accepted (up to {body['inflight']['max']} jobs in flight)" if r.status_code == 200
                           else f"api ping: HTTP {r.status_code} {body.get('error', {}).get('message', '')}")
            except (httpx.HTTPError, KeyError, ValueError) as e:
                typer.echo(f"api ping: failed ({type(e).__name__}: {e})")
        if llm_on:
            from .config import StageParams
            from .llm import LLM

            out = LLM(cfg.llm).json("Reply with JSON only.", json.dumps({"say": "ok"}), StageParams(temperature=0, max_tokens=50), "ping")
            typer.echo(f"llm ping: {out}")
    if errs:
        raise typer.Exit(1)


def main():
    app()


if __name__ == "__main__":
    main()
