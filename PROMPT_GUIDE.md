# Prompt guide: story albums on canvas

How to write an album by hand: one reference photo (shot 1) and 15 pages that keep the same people. `albumgen`
applies every rule here in code; use this guide when you write prompts yourself. The exact wording of every pose is
in [POSES.md](POSES.md); full sample albums are in [examples/](examples).

## 1. Requests

| | Shot 1 | Pages 2–16 |
|---|---|---|
| `model` | `qwen-image-3` | `canvas` |
| params | `aspect_ratio: "2:3"`, `resolution: "2k"`, `output_format: "jpeg"`, `enhance_prompt: false` | `aspect_ratio: "2:3"`, `resolution: "1k"`, `output_format: "jpeg"`, `images: [{"job_id": "<shot 1 job id>"}]` |

- `POST https://api.livedreams.ai/v1/images/generations` with body = `model` + `prompt` + params, header
  `Idempotency-Key` (unique per page and attempt). Poll `GET /jobs/{id}`; the image is `images[0].url`.
- Render shot 1 and look at it before you write or send the pages. Then send the pages, up to 6 in flight.
- Check your album before rendering: save it as a JSON list of `{shot, model, params, prompt}` and run
  `albumgen check my_album.json`.

## 2. Plan the album first

Decide everything before writing a single page; every page repeats these words exactly.

- **Story**: who they are and how they meet (a delivery at the door, a massage, a photo shoot, a minor
  fender-bender). Adults who both want it; nothing owed, nobody asleep, drunk, a patient, a student or family.
- **Mode**: `solo` (shot 1 is her alone; the album is seen through his eyes and his head stays out of frame), `couple`
  (shot 1 shows them meeting with both faces), or `two women`.
- **Place**: one place for the whole album, with its light (`bright daylight`, `warm lamplight`). Note whether it has
  a bed; if not, name the surface: sofa, massage table, car hood, sun lounger, gym bench, a towel on the floor.
- **Her**: age as a number (23 or older; 56–66 for mature albums), ethnicity, skin, hair colour and cut, eye colour,
  figure, makeup, one optional extra (a small tattoo, glasses). For fuller or older women write `a defined waist`;
  belly words can read as pregnant.
- **Her outfit** as an ordered list of parts, outer to inner: `a fitted red blazer, a white silk blouse, a black
  pencil skirt, a black lace bra and a black lace thong`, plus footwear. Clothes come off in this order.
- **Him**: age phrase (`in his early thirties`), build, skin; in couple albums also hair and face. His outfit. In
  couple albums he is in shot 1, in solo albums he never shows his face.
- **Pages**: give each of the 15 pages a slot, her clothing stage and his state. A structure that works:

| Pages | Slot | Her clothing | Him |
|---|---|---|---|
| 2 | intro: the story continues, flirting | outfit | dressed |
| 3–5 | tease: undressing, a kiss on the neck, a striptease, one solo page of her alone (solo albums) | outfit → partial → underwear → topless | dressed or shirtless |
| 6–7 | oral | nude | nude |
| 8–13 | sex: a different position on each page | nude | nude |
| 14 | the finish (one per album) | nude | nude |
| 15–16 | afterglow: lying, spent | nude | out of frame |

Rules for the plan:
- Clothes only come off: outfit → partial (first part off) → underwear → topless → nude. A removed piece never
  comes back, for her and for him. The album never ends dressed.
- Exactly one finish. Pages after it show its result (semen still there) and end with her naked, messy, tired and
  lying down.
- Use the poses in POSES.md. At most one `weak` pose per album, never as the finish. Never a pose from "Do not use".
- Vary the poses; when a pose repeats, use its other camera.

## 3. Shot 1

One paragraph, in this order. Full body, everyone's face visible, nothing explicit.

```
A full-body vertical photograph of one adult woman alone in <place>. She is <age> years old and <ethnicity>, with
<skin> skin, <hair>, <eye colour> eyes, defined brows and <makeup>. She has <figure>. She wears <outfit>, <in
footwear | barefoot>. <What she does in the story's first moment, with a calm, inviting or confident look>. Her whole
face is clearly visible and evenly lit. The camera is at her eye level, about two metres away, 50 mm lens, her whole
body in frame, natural adult proportions. <Light>, a little stronger from the front left, with soft natural shadows;
<two or three props> around her. Unretouched realistic photo, natural skin texture with visible pores. No text, no
logos, no watermark. She is the only person in the photo.
```

- Couple: `… of one adult woman and one adult man in <place>.` After her description: `The man is in his <age
  phrase>, with <build>, <hair and face> and <skin> skin; he wears <his outfit>.` Show them meeting (she opens the
  door, they shake hands). Camera: `three-quarter view at chest height, about three metres away, 50 mm lens, both
  whole bodies in frame from head to feet, both faces clearly visible and evenly lit, natural adult proportions.`
  Drop the last sentence.
- Two women: `… of two adult women in <place>.` Describe each woman the same way, each in her own outfit, with
  clearly different hair colours. Camera: `at their chest height, about two and a half metres away, 50 mm lens, both
  whole bodies in frame, both faces clearly visible and evenly lit, natural adult proportions.` End with `Exactly two
  women in the photo.`
- Shot 1 fixes faces, bodies, hair and the outfit for every page. If anything is wrong in it (a wrong outfit, a
  belly that reads as pregnant, the wrong number of people), write a new shot 1. Pages cannot repair it.

## 4. A page

Sentences in this order. Leave out what does not apply. Under 4,000 characters.

1. **Identity**:
   - solo: `The reference photo shows only the woman. Keep her exactly as in the reference: the same face, <hair>,
     <skin> skin, <extra>, <figure> and <makeup>; she is <age> years old.`
   - couple: `The reference photo shows the woman and the man of this album. Keep both exactly as in the reference:
     she has <hair>, <skin> skin, <figure> and <makeup> and is <age> years old; he has <hair and face>, <build> and
     <skin> skin.`
   - two women: `The reference photo shows the two women of this album. Keep both exactly as in the reference: <A> is
     <age>, <ethnicity>, with <skin> skin, <hair>, <figure> and <makeup>; <B> is … They are two different women.`
2. `Camera, pose and clothing follow the text below.`
3. **Camera**: `Camera: <one sentence from POSES.md>.`
4. **Alone**, when he is not on the page: `She is alone in this shot.` (couple: `She is alone in this shot; he is
   outside the frame.`)
5. **Clothing**, see section 5.
6. **After sex** (every nude page after the first oral or sex page): `Her look shows what happened: her hair messy
   and tangled, her makeup slightly smudged, her skin flushed and glistening with sweat.`
7. **Semen** (pages after the finish, only where the camera sees it): `White semen from earlier still glistens on her
   <breasts | stomach | lower back>.`
8. **Her pose and hands**: `She <pose from POSES.md>.` Say where each hand is.
9. **The act** with exact mechanics, from POSES.md: `Vaginal sex in the cowgirl position: his erect penis is deep
   inside her vagina.`
10. **Her face**, see section 6.
11. **The man**, see section 7.
12. **Closing line**: `Same <place> and <light>; unretouched realistic photo, natural skin texture.`

**Action-first pages.** Calm pages tend to copy shot 1: afterglow, oral from the side, lying poses. Open them with the
action, then name her: `Afterglow: she lies naked and spent on her stomach across the rumpled bed after sex. The woman
is the woman from the reference photo: the same face, <hair>, <skin> skin, <figure> and <makeup>; she is <age> years
old.` Then camera, alone sentence, clothing, after-sex look, pose, face, closing line. POSES.md lists the opening for
every pose that needs it.

**Story pages** (the meeting continues, the first touch): identity, `Camera, pose and clothing follow the text
below.`, a camera such as `three-quarter view at face height, both of them from the waist up` (solo albums add `the
frame cuts him at the shoulders, his head outside the frame`), clothing, one sentence of what happens, her face, him,
closing line.

**Never on pages 2–16**: negations (`not`, `no`, `without`, `never`, `instead`, `nothing`). Say what is there, not what
is missing. Shot 1 may end with `No text, no logos, no watermark.`

## 5. Clothing

One sentence per page that says what she wears and what is off. Use the part names from your plan.

| Stage | Sentence |
|---|---|
| outfit | `She wears <outfit>, in <footwear>.` |
| partial | `Her <first part> is off; she still wears the <remaining parts>, in <footwear>.` |
| underwear | `She is in only the <bra> and <panties>; the <outer parts> are off, in <footwear>.` |
| topless | `She is topless, in <footwear>, wearing only the <panties>; the <other parts> and <bra> are off.` |
| nude | `She is completely naked and barefoot: her <all parts> lie on the floor nearby, her breasts and body bare.` |
| nude, penetration | `… lie on the floor nearby, her breasts, waist, hips, vulva and buttocks fully bare.` |

- Saying where the clothes are (`lie on the floor nearby`) keeps panties and dresses from coming back.
- Heels may stay on when nude: `completely naked except for her black heels: …`.
- Feet poses (soles, toes): shoes and stockings come off: `…, her stockings off, barefoot`. Never write that she
  wears stockings and is barefoot.
- A kiss in the middle of sex: frame it from the head to the chest. From the waist down the model puts panties
  back on.
- His state: `He is dressed in <his outfit>.` / `He is shirtless.` / `He is fully nude, with <chest and leg hair>.`
  His outfit decides his actions: no `unbuttoning his shirt` on a t-shirt, no `pulls his trousers down` on a robe.

## 6. Her face

One sentence. It decides more defects than anything else.

| Slot | Use |
|---|---|
| intro, tease | `She gives him a slow, flirtatious look, her lips slightly parted.` / `She looks into the camera with heavy-lidded, sultry eyes, her lips parted.` A faint half-smile at most. |
| oral | `She looks up at him with hungry, heavy-lidded eyes.` / `Her eyes are half-closed in concentration and pleasure, her cheeks flushed.` |
| sex | `Her mouth is open in a moan, her eyes half-closed with pleasure, her skin flushed.` / `Her eyes are nearly closed, her face relaxed and flushed with pleasure, her lips parted in a gasp.` |
| finish | `She looks up with dazed, heavy-lidded, satisfied eyes, her lips parted.` |
| afterglow | `She looks into the camera with tired, heavy-lidded, satisfied eyes, her lips slightly parted.` |

- Never anywhere: laugh, giggle, grin, a wide or big smile, `cheerful`, `beaming`.
- Never: `brows knitted`, `eyebrows drawn together`, frown, grimace, wince, `wide-eyed`: they read as pain or fear.
- Never during oral, sex, the finish or the afterglow: any smile, `bites her lip` (renders as a smirk).
- Write `eyes nearly closed`, never `eyes closed` (closed eyes lose the likeness).

## 7. The man

- On every page he is in: `He is a separate adult man in his <age phrase> with <build> and <skin> skin.` (couple:
  `… with <build>, <hair and face> and <skin> skin.`), then his state, then his place, hands and framing from
  POSES.md.
- Solo albums: his head is always outside the frame: `shown from the chest down, his head outside the frame`, or a
  POV camera from his eyes with `only his stomach and hands are visible`.
- Couple albums: his face may show; give his hair and face on every page.
- Place him exactly: `kneels upright directly behind her, his thighs against the backs of her thighs`. Vague places
  get drawn lying or crouching.
- Never more than two people in a frame.

## 8. The finish and after

- Cumshot: `He has just pulled out: his erect penis is outside her body, held near her breasts, and thick strands of
  white semen lie across her breasts and drip down her cleavage.` Without `pulled out` / `outside her body` the penis
  stays inside.
- Facial, back, stomach and feet finishes: wording in POSES.md (`climax`).
- After the finish, keep the semen on the pages where that part of her is visible (back, front or face).
- The last two pages: naked, messy, lying on the bed or under a sheet, tired. No shower, no dressing, no coffee.

## 9. Places

- Name the real surface when there is no bed, and replace `bed`, `pillow`, `sheet`, `headboard` and `mattress` in
  every sentence, including pose sentences from POSES.md.
- Outdoors: `ground` or `sand`, never `floor`.
- The closing line repeats the same place and light on every page.

## 10. Two women

- Name them by hair: `the dark-haired woman`, `the blonde woman`. Each has her own outfit.
- Every page ends with `Exactly two women in the photo, the dark-haired woman and the blonde woman.`
- Faces: `Both …` or `The woman receiving …` (section 6 lines, written for both).
- Nude: `Both women are completely naked and barefoot, their clothes on the floor.`
- Use the two-women poses in POSES.md (kissing, breast kiss, cunnilingus, fingering, facesitting, undressing each
  other, afterglow cuddle). Never sixty-nine or scissoring.

## 11. Words

- Never: girl, teen, young, petite, tiny, innocent, school, student, college, sleepy, asleep, drunk, forced, patient,
  any family word (mother, sister, step-…), any animal word (also inside compounds: `downward-dog`, `kitten heels`),
  real names, brands. The full list is `never_words` in `data/policy.yaml`.
- Swaps: `baby oil` → `body oil`, `kitten heels` → `low heels`, `cat ears` → `satin ear headband`, `dog collar` →
  `leather choker`.
- Age as a number on shot 1 and in every identity sentence.

## 12. Review and fix

Look at every page at full size. Fix by cause:

| You see | Do |
|---|---|
| a clothed scene instead of the act | send the same prompt again with a new Idempotency-Key |
| `content_rejected` | never resend it unchanged: replace the one word that could read off-policy (section 11) once; refused again → a different page |
| a smile, grin or laugh during sex | use a sex face from section 6; remove every smile and lip-biting word |
| a pained or frightened face | use a pleasure face; remove brow, frown and wide-eye words |
| panties or clothes back on | name where the clothes lie and list the bare body parts; a kiss: chest-up camera |
| no penetration, or the act is wrong | write the mechanics exactly; switch to a `best` pose of the same slot |
| his face in a solo album | `shown from the chest down, his head outside the frame`, or a POV camera |
| the page copies shot 1 | open the page with the action |
| a bed in a place without one | replace every bed, pillow and sheet word |
| an extra person or extra limbs | send again with a new key; if it repeats, a different pose |
| `job_timeout` | send again with a new key; keep fewer pages in flight |
| shot 1 is wrong | a new shot 1 and all 15 pages again |

## 13. A full page

Solo album, sex page:

```text
The reference photo shows only the woman. Keep her exactly as in the reference: the same face, long straight dark
brown hair falling past her shoulders, olive skin, a small rose tattoo on her shoulder, athletic, toned figure with
medium breasts and a firm round butt and smoky eye makeup; she is 41 years old. Camera, pose and clothing follow the
text below. Camera: low-angle point-of-view shot from the eyes of a man lying on his back, looking up at her face and
body. She is completely naked and barefoot: her chemise and black thong lie on the floor nearby, her breasts, waist,
hips, vulva and buttocks fully bare. Her look shows what happened: her hair messy and tangled, her makeup slightly
smudged, her skin flushed and glistening with sweat. She sits upright astride him, her knees on the blanket on either
side of his hips, both hands flat on his chest. Vaginal sex in the cowgirl position: his erect penis is deep inside
her vagina. Her mouth is open in a moan, her eyes half-closed with pleasure, her skin flushed. He is a separate adult
man in his late twenties with a stocky, strong build and medium-brown skin. He is fully nude. He lies on his back
under her; only his chest, stomach and thighs are visible at the bottom of the frame, his head below the bottom edge
of the frame. Same photo studio and bright studio light; unretouched realistic photo, natural skin texture.
```
