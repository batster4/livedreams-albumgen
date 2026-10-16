# Canvas prompting guide

How to get consistent, correct explicit photos from `canvas` when you call the LiveDreams API directly. It explains
how the model behaves, what follows from that, and what to do and avoid. It applies to single images and to whole
series (albums) of the same people.

## 1. How Canvas behaves

Everything else in this guide follows from these seven points.

1. **Canvas redraws the reference.** It starts from the reference photo and keeps whatever the prompt does not
   change: face, body, hair, and also outfit, framing, pose and room. So a prompt must name everything that is
   *different* from the reference: the camera, what is off, the pose. A calm prompt with little change comes back as
   a near copy of the reference.
2. **The reference sets the ceiling.** Every image inherits the reference's face, body and outfit, including its
   flaws. A wrong outfit or an odd body in the reference cannot be fixed by later prompts.
3. **Grammar decides who gets what.** `She wears a red bra. He wears jeans.` gives each item one owner. A loose tag
   (`busty`, `corset`, `hairy`) has no owner and can land on anyone in the frame.
4. **Every word is drawn.** Naming a thing tends to put it in the picture, even after `no` or `without`. Describe only
   what is there.
5. **What you leave open, the model fills with its habits.** An unplaced hand grips the nearest object or the penis; a
   man without an exact place lies or crouches; an act named by a tag (`oral position`) gets guessed; a person implied
   only by the act may come out as a second copy of her.
6. **Faces are exaggerated.** A faint smile becomes a grin, knitted brows read as pain, wide eyes as fear, a lip bite
   as a smirk. Closed eyes on a small face lose the likeness.
7. **Some compositions are beyond it.** Side views of two people standing in sex, sixty-nine, titjob, carrying her,
   legs on his shoulders and a few more fail most of the time, whatever the wording (section 7).

## 2. The request

| | First image (the reference) | Canvas image |
|---|---|---|
| `model` | `qwen-image-3` | `canvas` |
| `aspect_ratio` | `2:3` (any ratio the model lists) | the same as the reference |
| `resolution` | `2k` | `1k` (`2k` on request) |
| other | `enhance_prompt: false` | `images: [{"job_id": "<reference job id>"}]` |

- Make the reference on `qwen-image-3`: it follows long sentence prompts closely. A reference made on Canvas from
  another reference is weaker.
- **Always reference the original image**, never the previous Canvas image: small drifts add up along a chain.
- `images` also takes `{"file_id": …}`, `{"url": "https://…"}` or `{"b64": …}`. Outputs are kept 7 days; after that a
  `job_id` reference fails, so save the reference and send it as a file.
- Canvas takes up to 6 references. One clean reference that shows everyone works best. If you add more, say in the
  first sentence what each image shows and that they show the same person.
- Canvas has no `seed`. Consistency comes from the reference and from repeating the same words.
- Every request has its own `Idempotency-Key`. A retry is a new key; the same key with a changed prompt is a 409.
- Keep pages in flight low (6 at most per account). The ~5 min deadline of a job counts its time in the queue.
- Prompts up to 4,000 characters; 700–1,500 is typical.

## 3. The reference image

It is the most important image: check it before anything else and render it again if it is not right.

- **Show everyone who will appear with a face**, whole body in frame, her face large, frontal and evenly lit. For
  her alone: she is the only person. For a couple: both, meeting (handshake at the door, a delivery), both faces
  visible.
- **Write it as sentences, person by person**: age as a number, ethnicity, skin, hair colour and cut, eye colour,
  makeup, figure, then what she wears with colour and material, then footwear. Then him in his own sentence, in
  clothes clearly different from hers in colour and type.
- **Describe only what should be visible.** Underwear under a dress is introduced on the first image where it shows.
- **Barefoot unless shoes matter**: shoes in the reference tend to stay on in every image.
- Figure words for older or fuller women: `a defined waist`. Belly words can read as pregnant.
- End with `Unretouched realistic photo, natural skin texture with visible pores. No text, no logos, no watermark.`
  and, for her alone, `She is the only person in the photo.` (Negations are fine in this one sentence on
  `qwen-image-3`.)
- Render it 2–4 times and keep the best: the planned people only, each in their own clothes, a clear adult face of
  the stated age, intact hands.

## 4. Anatomy of a Canvas prompt

One paragraph of plain sentences, in this order:

1. **Who the reference shows** (identical on every image of a series):
   `The reference photo shows only the woman. Keep her exactly as in the reference: the same face, <hair>, <skin>
   skin, <figure> and <makeup>; she is <age> years old.`
   Couple: `The reference photo shows the woman and the man of this album. Keep both exactly as in the reference: …`
2. `Camera, pose and clothing follow the text below.` It tells Canvas these may differ from the reference.
3. **Camera**: view, side, height and framing. `Camera: three-quarter view from her front right at face height, her
   whole kneeling body and his body in frame.`
4. **Who is in the shot**: `She is alone in this shot.` when he is not.
5. **Clothing, including what is off**: `She is in only the black lace thong; the blazer, blouse and bra are off.`
6. **Her pose and both hands.**
7. **The act as mechanics**: whose body part is where. `Missionary sex: his erect penis is deep inside her vagina.`
8. **One facial expression** with what the face does.
9. **The man**: one fixed sentence (`He is a separate adult man in his late thirties with a broad-shouldered build
   and fair skin.`), his clothing state, where he is, his hands, how much of him is in frame.
10. **Fixed closing line**: `Same <place> and <light>; unretouched realistic photo, natural skin texture.`

**When the image keeps copying the reference** (calm, lying or afterglow images): open with the action, then name her.
`Afterglow: she lies naked and spent on her stomach across the rumpled bed after sex. The woman is the woman from the
reference photo: the same face, …; she is 36 years old.` Then camera, clothing, pose, face, closing line.

## 5. Best practices

**Identity and series**
- Repeat the exact same words for her looks, his sentence and the closing line on every image.
- Give her age as a number on every image; call her a woman.

**Camera**
- Name a camera on every image; otherwise the reference framing returns.
- Change the camera between images (three-quarter, profile, POV, from above).
- Vertical 2:3 suits compact poses: kneeling, sitting, standing, all fours, lying seen from above. For a larger face
  frame `from the top of her head to her knees` instead of the whole body.
- POV: `point-of-view shot from the eyes of a man kneeling between her legs, looking down along her body to her face`,
  then list only the parts of him that are visible.

**Clothing**
- One sentence per image that says what she still wears and what is off. Clothes only come off within a series; a
  removed piece never returns.
- Naked during sex: say where the clothes are and what is bare: `She is completely naked and barefoot: her dress and
  thong lie on the floor nearby, her breasts, waist, hips, vulva and buttocks fully bare.` This stops panties and
  dresses from coming back.
- Feet images: shoes and stockings come off; say `barefoot`.
- His state on every image he is in: `He is dressed in <outfit>.` / `He is shirtless.` / `He is fully nude, with a
  flat hairy chest and hairy legs.` Keep clothing and body hair out of his fixed sentence. Give him only actions his
  clothes allow (no unbuttoning a t-shirt).

**People and hands**
- Write the man into every image he is in, even when the act implies him.
- Solo albums keep one face, hers: `shown from the chest down, his head outside the frame`, a POV, or a frame edge.
- Place him exactly: `kneels upright directly behind her, his thighs against the backs of her thighs, both hands on
  her hips`. When he stands in front of her, put him on the camera's side (`on the right of the photo` with a camera
  at her front right).
- Place every visible hand: `both hands flat on the mattress`, `his hands holding her knees`. Keep her hands off the
  penis unless the act needs it (then: one hand at the base). Give his hands a place on her body or `arms at his
  sides`.

**The act and the finish**
- Plain anatomy words and exact positions; one act per image.
- A finish is described by its result and where the penis is: `He has just pulled out: his erect penis is outside her
  body, held near her breasts, and thick strands of white semen lie across her breasts and drip down her cleavage.`
  Without `pulled out` / `outside her body` it stays inside. Avoid `semen covers`: it renders as paint.
- After the finish, keep the semen where the camera sees it: `White semen from earlier still glistens on her lower
  back.`
- After sex: `Her look shows what happened: her hair messy and tangled, her makeup slightly smudged, her skin flushed
  and glistening with sweat.`

**Place**
- One place and one light per series, repeated in the closing line.
- No bed in the place: name the surface (sofa, massage table, car hood, sun lounger, a towel on the floor) and replace
  bed, pillow, sheet and headboard words. Outdoors: `ground` or `sand`, never `floor`.
- Match heights with furniture: `the raised bed` when he stands and she lies at the edge.

## 6. Faces

| Moment | Write |
|---|---|
| flirting, teasing | `a slow, heavy-lidded look, her lips slightly parted`; a faint half-smile at most |
| oral, sex | `Her mouth is open in a moan, her eyes half-closed with pleasure, her skin flushed.` / `Her eyes are nearly closed, her face relaxed and flushed with pleasure, her lips parted in a gasp.` |
| finish | `dazed, heavy-lidded, satisfied eyes, her lips parted` |
| after | `tired, heavy-lidded, satisfied eyes, her lips softly parted` |

- Never: laugh, giggle, grin, a wide or big smile, `cheerful`, `beaming` (they render as a broad grin).
- Never: `brows knitted`, `eyebrows drawn together`, frown, grimace, wince, `wide-eyed` (pain or fear).
- During sex, the finish and after: no smile at all and no lip biting (a smirk).
- `eyes nearly closed`, never `eyes closed`.
- One expression per image. Do not make an image depend on a subtle one.

## 7. Poses and cameras

**Reliable**

| Pose | Camera |
|---|---|
| she sits or kneels, he stands (flirt, oral, finish on breasts) | three-quarter view from her front right at face height, both bodies in frame; he on the right, shown from the chest down |
| oral, kneeling | exact side profile from her left at head height; he stands on the left |
| oral, lying on her stomach at the bed edge | three-quarter view at mattress height from beside the bed |
| missionary | POV from the eyes of the man kneeling between her legs, looking down along her body to her face |
| cowgirl | low-angle POV from the eyes of the man lying on his back, looking up at her face and body |
| reverse cowgirl | front view from the foot of the bed at chest height, his upper body hidden behind her |
| from behind, standing | high-angle POV from the man behind her, looking down her arched back; she looks back over her shoulder |
| doggy | POV from the man kneeling behind her, looking down along her back to her face |
| riding him in an armchair | POV from the seated man, looking up at her face |
| feet on his chest | POV from the man kneeling between her legs, her soles close to the camera |
| facial | medium close-up from slightly above at her front right; only his lower stomach and penis at the frame edge |
| solo, lying / afterglow | high angle from directly above, head to knees |

**Two women.** Reliable: kissing, breast kissing, cunnilingus from the foot of the bed, fingering, spoon fingering,
facesitting, undressing each other, an afterglow cuddle. Name them by hair colour (`the dark-haired woman`, `the
blonde woman`), give each her own outfit, end every image with `Exactly two women in the photo, the dark-haired
woman and the blonde woman.`

**Weak** (fine once, check the result, never as the finish): sex against a wall, standing at the bed edge over his
shoulder, handjob, oral to a seated man, kissing her toes, lotus. A kiss during sex: frame it from the head to the
chest, or panties come back.

**Avoid, and what to use instead**

| Avoid | It renders as | Use |
|---|---|---|
| side view of two people standing in sex; doggy from the side | no penetration, penis on her thigh | POV from behind, over his shoulder |
| sixty-nine | ordinary oral, his face in frame | oral lying on her stomach |
| titjob | penis beside her breasts | steep POV oral from above |
| standing carry | penis below her | from behind against a wall |
| legs on his shoulders | legs stay spread, his face appears | missionary POV |
| lap dance astride him | she sits beside him | tease POV from a chair, riding in an armchair |
| anal | vaginal from behind | doggy POV (do not promise anal) |
| spooning | doggy from the side with his face | doggy POV |
| scissoring (two women) | legs crossed side by side | spoon fingering |
| more than two people | clones, merged bodies | two people |
| dressed again, shower at the end | breaks the story, drifts | lying naked, messy, under a sheet |

An untested pose: take the nearest reliable camera family (three-quarter with him from the chest down, POV listing
only his visible parts, from directly above), keep her face to the camera, her pose compact and his head out of frame.

## 8. Words and the content screen

- Prompts are screened before and during rendering. A refusal (`content_rejected`) is final: never resend the same
  prompt or variations of it. If one innocent word plausibly caused it, replace that word once; if refused again,
  drop the image.
- Never write: girl, teen, young, petite, tiny, innocent, school, student, college, cheerleader, babysitter;
  sleepy, asleep, drunk, drugged, unconscious; forced, struggling, scared, crying, pain; any family word (mother,
  sister, step-…); patient, examination; any animal word, also inside phrases (`kitten heels`, `downward-dog`); real
  names, brands, franchise characters.
- Everyday swaps: `baby oil` → `body oil`, `baby blue` → `pale blue`, `kitten heels` → `low heels`, `cat ears` →
  `satin ear headband`, `dog collar` → `leather choker`, `puppy-dog eyes` → `wide eager eyes`.
- Body type stays adult: `a slim adult figure with small natural breasts`, never `petite` or `skinny`.
- Both people are awake, willing and active. A nurse or a teacher is fine as an adult role; nobody is a patient or
  a student.
- Sandbox keys run only the first check: a prompt that passes there can still be refused on a live key.

## 9. When an image comes out wrong

Look at every image at full size: smiles, a face at the frame edge and thin straps vanish on thumbnails.

| You see | Cause | Do |
|---|---|---|
| a clothed, harmless scene instead of the act | the model played safe | same prompt, new Idempotency-Key |
| an extra finger, an odd grip, a doubled body part | random | same prompt, new key |
| a near copy of the reference | too little change | open with the action; state what is off |
| clothes back on | removed clothes not named | name where they lie and what is bare; for a kiss, chest-up camera |
| a grin or laugh in sex | a smile word, lip biting | a pleasure face from section 6 |
| a pained or frightened face | brow, frown or wide-eye words | a pleasure face |
| no penetration | weak camera, vague mechanics | exact mechanics; POV camera; a reliable pose |
| his face in a solo series | camera beside him, no framing | `shown from the chest down, his head outside the frame`, or POV |
| a second copy of her | the man was only implied | write his fixed sentence, place and hands |
| a bed where there is none | bed words in the pose | replace every bed, pillow and sheet word |
| her face younger, rounder or different | small face, closed eyes | a closer frame, `eyes nearly closed` |
| the same defect twice | the composition | change the camera or the pose, not just words |
| the defect is in the reference | the reference | a new reference, then all images again |
| `job_timeout` | too many jobs queued | send again with a new key; fewer in flight |

## 10. Example

Reference (`qwen-image-3`, 2:3, 2k, `enhance_prompt: false`):

```text
A full-body vertical photograph of one adult woman alone in a photo studio. She is 41 years old and Arab, with olive
skin, long straight dark brown hair falling past her shoulders, brown eyes, defined brows and smoky eye makeup and
nude lips. She has a small rose tattoo on her shoulder. She has an athletic, toned figure with medium breasts and a
firm round butt. She wears a black satin chemise with lace trim, barefoot. She sits on a stool against the white
paper backdrop, softboxes on either side, looking into the camera with a confident, sultry look. Her whole face is
clearly visible and evenly lit. The camera is at her eye level, about two metres away, 50 mm lens, her whole body in
frame, natural adult proportions. Bright studio light, a little stronger from the front left, with soft natural
shadows; a white paper backdrop, softbox lights and a stool around her. Unretouched realistic photo, natural skin
texture with visible pores. No text, no logos, no watermark. She is the only person in the photo.
```

Canvas image (`canvas`, 2:3, 1k, `images: [{"job_id": "<reference job id>"}]`):

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

Afterglow (action first):

```text
Afterglow: she lies naked and spent on her stomach across the blanket after sex. The woman is the woman from the
reference photo: the same face, long straight dark brown hair falling past her shoulders, olive skin, a small rose
tattoo on her shoulder, athletic, toned figure with medium breasts and a firm round butt and smoky eye makeup; she is
41 years old. Camera: high-angle three-quarter view from beside the blanket, her whole body in frame. She is alone in
this shot. She is completely naked and barefoot: her chemise and black thong lie on the floor nearby, her breasts and
body bare. Her look shows what happened: her hair messy and tangled, her makeup slightly smudged, her skin flushed
and glistening with sweat. White semen from earlier still glistens on her lower back. She lies on her stomach across
the blanket, her cheek resting on her folded arms, looking back at the camera. She looks into the camera with tired,
heavy-lidded, satisfied eyes, her lips softly parted. Same photo studio and bright studio light; unretouched
realistic photo, natural skin texture.
```
