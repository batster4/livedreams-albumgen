# Instructions for the album agent

You make photo albums with `albumgen`. The script writes every prompt; your job is to run it, render, review and
deliver. Work from the repository folder with the virtual environment active (`source .venv/bin/activate`).

## Steps

1. Generate: `albumgen new -n N` (optional: `-f FAMILY` for a family, `--mode couple`, `--theme ID`).
   Each album is a folder `out/<album_id>/` with `album.json` (16 requests) and `story.md`.
2. Render: `albumgen render <album_id>` (or `albumgen render` for every album in `out/`).
   If your pipeline renders instead, send the requests from `album.json` as they are (README → "Your own pipeline"):
   body = `model` + `prompt` + `params`; shot 1 first; then `images[0].job_id` = shot 1's job id; up to 6 pages at
   a time.
3. If pages failed: run `albumgen render <album_id>` again. It keeps finished pages and retries only the rest.
4. Review every page at full size. Reject a page for: a laugh, grin or wide smile; a pained or frightened face;
   clothes back on after they came off; panties during sex; the act missing or a clothed scene instead; his face
   in a solo album; an extra person or limbs; she does not look like shot 1.
   Rebuild rejected pages: `albumgen fix <album_id> -p 4,9`. Shot 1 is wrong: make a new album instead.
5. Deliver `out/<album_id>/images/01.jpg … 16.jpg` in this order (01 is shot 1), with the title from `story.md`.

## Never

- Never rewrite, shorten, translate, merge or "improve" a prompt, not one word. Every sentence is there for a
  tested reason (PROMPT_GUIDE.md).
- Never change `model`, resolution, aspect ratio or any parameter, and never drop `images` from a page.
- Never write your own prompts for these albums or reuse a page in another album.
- Never send `shot` or `changes` to the API: they are not API fields.
- Never keep more than 6 pages in flight in total, across all albums: canvas renders 6 at a time, extra pages wait
  in the queue, and the wait counts toward a page's ~5 min deadline (`job_timeout`).

PROMPT_GUIDE.md and POSES.md explain the rules behind the prompts. Read them only as reference; the script already
applies them. If you are asked to write an album yourself, follow PROMPT_GUIDE.md exactly and run `albumgen check`
on it before rendering.
