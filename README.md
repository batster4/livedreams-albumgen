# albumgen

Generates complete adult photo albums for the LiveDreams API: a fresh story and 16 ready requests per album
(shot 1 on `qwen-image-3`, then 15 `canvas` pages that use shot 1 as the reference). Every album is different,
follows the prompting rules that tested best on `canvas`, and stays away from what the model cannot draw.

Everything is pre-configured for the LiveDreams API (endpoint, models, resolutions, parameters, load limits).
The only thing you add is your API key.

- **[AGENT.md](AGENT.md)**: the short instruction for an AI agent that runs albumgen. Give it to your agent.
- **[GUIDE.md](GUIDE.md)**: why the prompts look the way they do (facts from 45 rendered albums). Reference only.
- **[examples/](examples)**: two generated albums (requests + story), to see the format before installing.

## Quick start

You need Python 3.10 or newer (`python3 --version`). macOS: `brew install python@3.12`. Ubuntu/Debian:
`sudo apt install python3 python3-venv`.

```bash
git clone <this repository> albumgen && cd albumgen
./setup.sh                      # creates .venv, installs albumgen, creates .env, runs a check
```

Open `.env` and paste your API key (LiveDreams partner dashboard → API → keys):

```bash
LIVEDREAMS_API_KEY=ldk_live_...
```

A sandbox key (`ldk_test_...`) works with the same endpoints and returns placeholder images in a few seconds at no
cost: use it to try the whole flow first.

```bash
source .venv/bin/activate       # once per terminal; or call .venv/bin/albumgen directly
albumgen doctor --ping          # checks the library and that the API accepts your key (free request)
albumgen new -n 3               # 3 albums → out/<album_id>/album.json + story.md
albumgen render                 # renders every album in out/, one at a time → out/<album_id>/images/01.jpg … 16.jpg
albumgen export -o albums       # optional: per album a 4×4 collage + images + prompts; albums/index.html; albums.zip
```

Without `setup.sh`:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env            # then paste the key
albumgen doctor --ping
```

Run every command from the repository folder: `config.yaml`, `.env`, `out/` and the memory file `albumgen.db` are
read from there (or pass `-c path/to/config.yaml`).

## Two ways to render

**1. `albumgen render`** (simplest). Renders the albums in `out/` one at a time, 2 pages in flight. Safe to stop and
re-run: finished pages are kept, unfinished jobs are picked up again by their Idempotency-Key (no second charge),
a page that failed or timed out gets one new try. Images land in `out/<album_id>/images/NN.jpg`.

**2. Your own pipeline.** `out/<album_id>/album.json` is a list of 16 requests:

```json
[
  {"shot": 1, "model": "qwen-image-3",
   "params": {"aspect_ratio": "2:3", "resolution": "2k", "output_format": "jpeg", "enhance_prompt": false},
   "prompt": "A full-body vertical photograph of one adult woman ...", "changes": []},
  {"shot": 2, "model": "canvas",
   "params": {"aspect_ratio": "2:3", "resolution": "1k", "output_format": "jpeg",
              "images": [{"job_id": "<shot 1 job id>"}]},
   "prompt": "The reference photo shows only the woman. Keep her exactly as in the reference: ...", "changes": []}
]
```

For each request the API body is `model` + `prompt` + everything in `params`, unchanged. `shot` and `changes` are
for you, not for the API (the API rejects unknown fields). Render shot 1 first; when it has succeeded, put its job
id into `images[0].job_id` of pages 2–16 and render them, at most 2 at a time.

```python
import json, time, httpx

API, KEY = "https://api.livedreams.ai/v1", "<your key>"
H = {"Authorization": f"Bearer {KEY}"}

def render(req, album_id, shot1_id=None, attempt=1):
    body = {"model": req["model"], "prompt": req["prompt"], **req["params"]}
    if shot1_id:
        body["images"] = [{"job_id": shot1_id}]
    key = f"{album_id}-s{req['shot']}-a{attempt}"          # same key = same job, never billed twice
    job = httpx.post(f"{API}/images/generations", json=body, headers={**H, "Idempotency-Key": key}, timeout=60).json()
    while job.get("status") not in ("succeeded", "failed", "canceled"):
        time.sleep(3.5)
        job = httpx.get(f"{API}/jobs/{job['id']}", headers=H, timeout=60).json()
    return job                                             # job["images"][0]["url"]: download it, the link expires

album_id = "20261016-121359-open-house-3031"
reqs = json.load(open(f"out/{album_id}/album.json"))
shot1 = render(reqs[0], album_id)
pages = [render(r, album_id, shot1["id"]) for r in reqs[1:]]   # run 2 at a time in production
```

A page that failed with `job_timeout` or a provider error: send it again with a new Idempotency-Key (`-a2`).
`content_rejected`: see [Review and fix](#review-and-fix).

## What is pre-configured

| Setting (`config.yaml → render`) | Value | Why |
|---|---|---|
| `base_url` | `https://api.livedreams.ai/v1` | the LiveDreams API |
| `shot1_model`, `shot1_resolution` | `qwen-image-3`, `2k` | shot 1 fixes her face, body and outfit for the whole album |
| `page_model`, `page_resolution` | `canvas`, `1k` | pages keep the people from shot 1 |
| `aspect_ratio`, `output_format` | `2:3`, `jpeg` | |
| `enhance_prompt` (shot 1) | `false` | the prompt is already complete; a rewrite loses details |
| `max_inflight` | `2` | a page's deadline (~5 min) includes its time in the queue |
| `poll_s`, `job_timeout_s` | `3.5`, `900` | |

The prompts were tuned for exactly these models and parameters. Do not change them, and do not edit prompts.

## Commands

| Command | What it does |
|---|---|
| `albumgen new [-n N] [-f FAMILY ...] [--theme ID] [--mode solo\|couple] [--seed N]` | Generate albums into `out/`. Themes rotate so the least-used come first. |
| `albumgen render [ALBUM ...]` | Render through the API (all albums in `out/` if none given). Safe to re-run. |
| `albumgen fix ALBUM -p 4,9 [--pose 9=ID] [--no-render]` | Rebuild pages a review rejected and render only them. |
| `albumgen export [ALBUM ...] -o DIR [--no-zip]` | Complete albums into one folder: images, 4×4 collage, prompts, story; `index.html`; zip. |
| `albumgen show ALBUM` / `list` | An album's story and prompts / recent albums. |
| `albumgen themes [--family F]` / `arcs` | Browse the 60 themes and 12 page structures. |
| `albumgen check out/ALBUM/album.json` | Check any album against the prompting rules (exit code 1 on issues). |
| `albumgen feedback ALBUM --bad 9,12 --reason "..."` | Poses that failed get a lower weight in later albums (`stats` shows weights). |
| `albumgen forget ALBUM` | Remove an album from memory (files stay). |
| `albumgen audit [-n 300]` | Sample albums offline and check every prompt for contradictions. |
| `albumgen doctor [--ping]` | Health check; `--ping` also checks the API key (free) and the LLM. |

`albumgen <command> --help` lists every option.

**Families** (`-f`, repeatable): `service_visit`, `chance_meeting`, `workplace`, `relationships`, `travel`,
`nightlife`, `fitness_and_wellness`, `pov`, `mature` (she is 56–66), `busty`, `feet`, `two_women`.

**Modes**: each theme sets its own; `--mode` switches between solo and couple.
- `solo`: shot 1 is her alone (best likeness); the album is seen through his eyes, his head stays out of frame.
- `couple`: shot 1 shows them meeting with both faces; his face may appear on later pages.
- `ff` (the `two_women` family): two women named by hair colour, each in her own outfit.

## Review and fix

Look at every page at full size before you publish (contact sheets hide smiles, a face at the frame edge, thin
straps). Reject a page when:
- she laughs, grins or smiles widely, or looks in pain or frightened;
- a piece of clothing is back on after it came off, or panties are on during sex;
- the act described is missing (for example no penetration), or a clothed scene came back instead of the act;
- his face is visible in a solo album; an extra person, extra limbs, or she does not look like shot 1.

Then:

```bash
albumgen fix 20261016-121359-open-house-3031 -p 4,9                          # rebuild pages 4 and 9, render only them
albumgen fix 20261016-121359-open-house-3031 -p 9 --pose 9=reverse_cowgirl   # force another pose
albumgen feedback 20261016-121359-open-house-3031 --bad 9 --reason "no penetration"   # optional
```

`fix` keeps the page's pose unless it is retired or does not fit, keeps the clothing order (later pages are rebuilt
too if a piece would come back) and moves old images to `_replaced/`. It never touches shot 1: if shot 1 is wrong
(a wrong outfit, a body that reads as pregnant), every page inherits it; generate a new album instead.

What to expect: about 93 % of pages were fine on the first render in our tests. About 1 % come back as a harmless
clothed scene instead of the act and about 0.2 % are blocked by the prompt screen although clean; both pass with
`fix`.

## Optional: an LLM for more varied stories

albumgen works without any LLM. Then every page uses the tested recipe text of its pose, and albums still differ by
theme, page structure, place, outfits, her and his look and poses. Image quality is the same (every page rebuilt by
`fix` uses recipe text too).

With an LLM the story gets its own title and logline, and her pose and expression are worded freshly on every page.
The code still writes everything that decides the picture (camera, clothing, the act, the man, framing), checks the
LLM's text, sends failing fields back once and otherwise uses the recipe. A refusing or failing LLM never breaks an
album.

The LLM must allow explicit adult text (mainstream assistants refuse; albumgen then falls back to recipe text). Any
OpenAI-compatible chat endpoint works:

```yaml
# config.yaml
llm:
  provider: openrouter          # or: openai | custom (any OpenAI-compatible server, set base_url)
  model: "<model id>"           # a model whose policy allows explicit adult text
  fallback_model: null          # tried when the main model refuses or returns no JSON
```

```bash
# .env
LLM_API_KEY=...
```

Check: `albumgen doctor --ping`, then `albumgen new -n 1` and look at the last column of the page table in
`out/<album_id>/story.md` (`llm`, `llm repair` or `recipe`). Cost: two calls per album, about 10–15k tokens.

## Files per album (`out/<album_id>/`)

| File | Content |
|---|---|
| `album.json` | the 16 requests |
| `story.md` | the story, her and his look, a table of pages (pose, beat, who wrote the text) and every prompt |
| `plan.json` | every choice, the seed and the LLM calls, for debugging |
| `images/NN.jpg`, `render.json` | after `render`: the images; job id, status and attempt per page |
| `_replaced/` | after `fix`: the images that were replaced |

## Settings (`config.yaml`)

All keys are optional and commented in the file.
- `album`: `min_age` / `max_age` (23–52), `only_families`, `exclude_families`, `exclude_themes`, `exclude_kinks`,
  `untested: light | off` (`off` never uses the few poses that work only most of the time), `allow_his_face`.
- `memory`: `albumgen.db` (SQLite) remembers every album. A theme does not repeat within 5 albums, a place + outfit
  pair within 20, her look never; recently used poses get a lower weight. Keep the file to keep albums different;
  delete it to start fresh; use one file per brand (`memory.db_path`).
- `llm`: see above. `render`: see [What is pre-configured](#what-is-pre-configured).
- From Python: `from albumgen import Config, make_album; res = make_album(Config.load("config.yaml"))`.

## How it works

```
1. Pick (code)       theme → page structure → place + outfits → her look → his look → a pose for each of 15 pages,
                     weighted by how well the model draws it and by novelty (memory)
2. Story (LLM)       title, logline, a beat and an emotion per page                    (optional)
3. Pages (LLM)       her pose and her expression, two short fields per page            (optional)
4. Assemble + check  code writes camera, clothing, the act, the man and framing, then checks every rule;
                     failing text is repaired once or replaced by the recipe → the output is always valid
```

The code guarantees on every page: the same identity sentence (she is N years old, an adult); the act with exact
mechanics; she is fully naked on penetration pages with her clothes "on the floor nearby"; clothes only come off;
exactly one finish, and the album ends naked, messy and lying down; his head out of frame in solo albums; place
words that fit the place; no negations, no banned words, under 4,000 characters. The library is plain YAML in
`data/` (`themes`, `arcs`, `positions`, `locations`, `outfits`, `appearance`, `emotions`, `policy`); `albumgen
doctor` checks it after edits. Details in [GUIDE.md](GUIDE.md).

## Troubleshooting

| Symptom | Fix |
|---|---|
| `setup.sh`: Python 3.10+ is required | install a newer Python (see Quick start) and run it again |
| `albumgen: command not found` | `source .venv/bin/activate` in this terminal, or run `.venv/bin/albumgen` |
| `set LIVEDREAMS_API_KEY to render` | put the key in `.env` next to `config.yaml`, no quotes or spaces |
| `api ping: HTTP 401` | the key is wrong, revoked or from another environment |
| `rate_limited` / HTTP 429 | albumgen waits and retries; in your own pipeline honour `Retry-After` |
| a page `failed` with `job_timeout` | run `albumgen render` again: it retries only that page |
| a page `failed` with `content_rejected` | `albumgen fix ALBUM -p N` |
| `No LLM configured` | expected without an LLM; albums use the recipe texts |
| `no albums in …/out` | run `albumgen new` first, or run the command from the repository folder |

Updates: `git pull` (run `pip install -e .` again only if `pyproject.toml` changed). Your `.env`, `out/` and
`albumgen.db` are not touched.

Tests: `pip install -e ".[dev]" && pytest` (offline, no keys needed).
