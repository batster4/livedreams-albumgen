# Album prompting: what 45 rendered albums taught us

Facts from 5 batches (45 albums kept, 720 pages, every page reviewed at full size, 241 pages re-rendered after review).
For an agent that writes or reviews album prompts. `albumgen` applies all of this in code.

## Setup
- Shot 1: `qwen-image-3`, 2:3, 2k. Pages 2–16: `canvas`, 1k, `images: [{"job_id": <shot 1>}]`.
- Shot 1 fixes her face, body and hair for the whole album; in couple albums also his. A flaw in shot 1 (a belly
  that reads as pregnant, a wrong outfit) repeats on every page and cannot be fixed later: make a new album.
- One finish per album. Last 2 pages: naked, messy, tired, lying or under a sheet.

## Page text, in this order
1. Identity: `The reference photo shows only the woman. Keep her exactly as in the reference: <hair>, <skin>, <figure>,
   <makeup>; she is N years old.` Couple: `… shows the woman and the man of this album. Keep both …; he has <hair and
   face>, <build>, <skin>.` Two women: describe both and end with `They are two different women.`
2. `Camera, pose and clothing follow the text below.` then `Camera: …` (one camera sentence).
3. `She is alone in this shot.` when he is not on the page (couple: `…; he is outside the frame.`).
4. Clothing (see below). 5. After sex: `Her look shows what happened: hair messy and tangled, makeup slightly
   smudged, skin flushed and glistening with sweat.` 6. Her pose and hands. 7. The act, with exact mechanics.
8. Her face. 9. The man: fixed sentence, state, place, hands, framing. 10. `Same <place> and <light>; unretouched
   realistic photo, natural skin texture.`
- Pages that tend to copy shot 1 (calm lying pages, afterglow, oral from the side) open with the action:
  `Afterglow: she lies naked and spent on her stomach across the rumpled bed after sex.`
- No negations on canvas pages (not, no, without, never). Under 4,000 characters. Numeric adult age.
- Never words: girl, teen, young, petite, school, student, college, sleepy, asleep, drunk, forced, patient, any family
  or animal word (also inside compounds: `downward-dog`, `sleepy-eyed`), real names, brands.

## Clothing
- Clothes only come off. Name what is still on at every stage; never let a removed piece come back.
- Penetration: `She is completely naked and barefoot: her <list> lie on the floor nearby, her breasts, waist, hips,
  vulva and buttocks fully bare.` Saying where the clothes are stopped panties and dresses from reappearing at the
  waist (5 cases before).
- Feet poses (soles, toes): shoes and stockings off, say so. Stockings and `barefoot` never in one sentence.
- A kiss in the middle of sex: frame it from the head to the chest; from the waist up the model put panties back
  on (3 of 3).
- His clothes decide his poses: no `unbuttoning his shirt` on a t-shirt, no `pulls his trousers down` on a robe.

## Faces (the most frequent defect)
- Flirt and tease: desire, a slow heavy-lidded look; a faint half-smile at most.
- Oral, sex, finish: `Her mouth is open in a moan, her eyes half-closed with pleasure, her skin flushed.`
  / `Her eyes are nearly closed, her face relaxed and flushed with pleasure, her lips parted in a gasp.`
- After: tired, heavy-lidded, satisfied, lips softly parted. No smile here either: a "faint satisfied smile"
  came out wide.
- Never: laugh, grin, big or wide smile (anywhere); any smile during oral, sex or the finish.
- Never: `brows knitted`, `eyebrows drawn together`, frown, grimace, `wide-eyed` → renders as pain or fright.
- Never during sex: `bites her lower lip` → renders as a smirk (4 of 4).
- `eyes nearly closed`, not `eyes closed` (closed eyes lose the likeness).

## The man
- Solo albums: his head stays outside the frame (`shown from the chest down, his head outside the frame`; POV:
  `only his stomach and hands are visible`). Cowgirl from below still shows his chin or forehead at the bottom edge
  now and then.
- Couple albums: shot 1 shows both faces meeting (pizza at the door, a fender-bender, a key card for the same
  room); give his hair, face, build and skin every page; his face may be in frame.
- Write his height and place exactly: `kneels upright directly behind her, his thighs against the backs of her
  thighs`, `its base hidden between her buttocks`. Vague placement drew him lying or crouching.

## Finish and continuity
- Cumshot: `He has finished and pulled out: his erect penis is held in his hand above her lower back, fully outside
  her body, and thick strands of white semen lie across …` Without "pulled out / outside" the penis stayed inside.
- Semen stays on the next pages, named only where the camera sees it (back vs front vs face).

## Places
- Name the real surface when there is no bed: sofa, car hood, massage table, sun lounger, gym bench, towel on the
  floor. Replace bed / pillow / sheet / headboard words in every sentence, including the ones an LLM writes
  (a bed appeared in an office and a kitchen).
- Outdoors: `ground` or `sand`, never `floor`.

## Two women
- Name them by hair: `the dark-haired woman`, `the blonde woman` (different hair colours), each in her own outfit.
- End every page with `Exactly two women in the photo, A and B.` Faces: `Both … / The woman receiving …`.
- Reliable: kiss standing or lying, breast kiss, cunnilingus from the foot of the bed or on the edge, fingering,
  spoon fingering, facesitting, undressing each other, afterglow cuddle. Do not use: sixty-nine (1/4), scissoring (0/3).

## Poses
- Reliable: cowgirl POV from below, cowgirl leaning forward, missionary POV, bed-edge missionary POV, reverse cowgirl
  POV, standing from behind POV, riding in an armchair POV, feet on his chest, oral kneeling side view, oral POV from
  above, oral lying on her stomach at the bed edge, cumshot on breasts / face / back / stomach, the lying afterglows,
  solo poses, striptease, POV tease from a chair, neck kiss from behind.
- Couple albums: cowgirl and missionary with both faces, from behind seen from the side; doggy POV is weaker here
  (2 of 3 without penetration).
- Weak (max one per album, never the finish): against the wall, over his shoulder at the bed edge, handjob, oral to a
  seated man, kissing her toes, lotus.
- Do not use (and what to use instead): titjob, sixty-nine, scissoring, standing carry, legs on his shoulders, lap
  dance, anal (renders as vaginal), doggy from the side and standing side view (no penetration), bed-edge POV oral
  (1/3), spooning, more than two people, dressed again at the end, shower at the end.

## Rendering
- About 1% of pages come back as a harmless clothed scene instead of the act (silent swap); about 0.2% are blocked by
  the prompt screen although clean. Both pass on a re-render with a new Idempotency-Key.
- A page's deadline (~5 min) counts queue time: keep few pages in flight per key; a page that timed out gets one new
  try with a new key.
- Review at full size, not on contact sheets: 67 of the defects (smiles, his face at the edge, a thong string) were
  invisible at 500 px.

## Results
| Batch | Pages without defect (first render) | What changed before it |
|---|---|---|
| 1 | 91 % | — |
| 2 | 95 % | code writes act, clothing and the man; penis outside on cumshots |
| 3 | 89 % | new modes (couple, two women, mature, feet) and story places |
| 4 | 95 % | place words in LLM text, afterglow opens with the action, shirt rule |
| 5 | 94 % | new poses, clothes on the floor, retired failing poses |
| final | 720 / 720 after review | 241 pages re-rendered in 5 rounds |
