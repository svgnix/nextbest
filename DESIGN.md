# DESIGN.md — NextBest frontend direction

Source of truth for **look and feel**. Follow this exactly; derive every color, type, and spacing choice
from the tokens here. If something isn't specified, choose in the *spirit* of the concept below rather
than reaching for a default. The brief is explicit: this must **not** look generic or vibe-coded.

---

## Concept: "The Morning Dispatch"

NextBest is the briefing an RM reads with their first coffee — a curated intelligence dispatch, not a CRM
grid. The feeling to hit: a **precision instrument** meets an **editorial morning brief**. Calm,
authoritative, fast to scan under time pressure, and — because it's an *agent* making calls a human will
act on — it earns trust by **showing its reasoning**, framed as a designed feature, not a debug dump.

Audience: a busy professional advisor. Page's single job: in 30 seconds, know who to call first and why.

Anchor the aesthetic in the subject's world: financial instruments, tickers, ledgers, tabular figures,
the idea of a *ranked* list where position is meaning. That's where the distinctive choices come from.

---

## Signature element (the one memorable thing): the Priority Rail

A continuous vertical **rail** runs down the left of the feed — a spine the whole dispatch hangs from.
Each client is a **notch** on the rail: a mono rank numeral (`01`, `02`, …), a signal dot colored by
`action_type`, and a short tick whose length encodes the leading score. It doubles as a scroll mini-map:
the shape of the RM's morning is legible at a glance before reading a single card. Position on the rail =
priority — structure that encodes something true, not decoration.

Spend the boldness here. Everything else stays quiet and disciplined so the rail is the thing people
remember. Do **not** add a second competing "hero" flourish.

Second, quieter designed feature: the **reasoning trace** — when a card expands, the agent's tool calls
animate in as a stepped vertical timeline ("saw a 94-day gap → pulled the education-fund note → drafted a
re-engagement"). This turns the audit trail into the trust-builder and is the visible payoff of "agentic."

---

## Color tokens

A deep ink instrument frame around a cool paper reading surface, with a **two-pole signal system**:
warm = a client cooling off / at risk (alarm), cool = growth / opportunity (calm). This maps color to
meaning across the whole app. Reserve saturated color for signal only; keep chrome and text neutral.

```
/* Ink chrome — rail, top bar, expanded panels */
--ink-900:  #0E1116;   /* deepest — rail base, header            */
--ink-800:  #171B22;   /* raised ink surfaces                    */
--ink-700:  #232833;   /* ink hairlines / dividers on dark       */

/* Paper — the reading surface / cards */
--paper-0:  #F6F7F9;   /* app background (cool, not cream)        */
--paper-50: #FFFFFF;   /* card surface                           */
--line:     #E4E7EC;   /* hairline dividers on paper             */

/* Text */
--text-900: #10141B;   /* primary on paper                       */
--text-600: #545B67;   /* secondary                              */
--text-400: #8A909B;   /* muted / captions                       */
--text-inv: #EDEFF3;   /* primary on ink                         */

/* Signal — WARM pole = attrition / urgent */
--warm-600: #C9522C;   /* URGENT badge/text                      */
--warm-500: #E8873A;   /* signature amber — rail dots, accents   */
--warm-100: #FBE5D8;   /* warm tint fills                        */

/* Signal — COOL pole = upsell / opportunity */
--cool-600: #0E7C6B;   /* OPPORTUNITY text                       */
--cool-500: #12A594;   /* teal accent, confidence arc            */
--cool-100: #D6F0EB;   /* cool tint fills                        */

/* Neutral signal = watchlist */
--slate-500: #64707E;
--slate-100: #E9ECF0;
```

Dominance: ink + paper neutrals carry ~70% of the surface; amber is the single sharp accent; teal
supports. Never let warm and cool compete at equal weight on one screen — the rail sets the tone.
Watchlist stays neutral so it recedes below the two active poles. This is **not** a green/red status
grid — it's a warm↔cool temperature scale; honor that framing (e.g. gradients and arcs move along the
warm→cool axis, statuses aren't little colored pills scattered everywhere).

---

## Typography

Deliberately not the Inter/Roboto default, and not the high-contrast-serif-on-cream default. A technical
grotesque display + a humanist body + a mono for all figures and labels (the mono reinforces the
"instrument/ledger" motif and makes scores align in tabular columns). All on Google Fonts.

```
--font-display: "Space Grotesk", sans-serif;   /* headlines, client names, big numerals */
--font-body:    "IBM Plex Sans", sans-serif;    /* rationale, drafts, running text       */
--font-mono:    "IBM Plex Mono", monospace;      /* rank, scores, eyebrows, timestamps    */
```

Use `IBM Plex Sans` / `Mono` with **tabular figures** (`font-variant-numeric: tabular-nums`) everywhere a
number appears, so scores don't jitter.

Type scale (desktop):

| Role | Font | Size / weight | Notes |
|---|---|---|---|
| Dispatch title | display | 30px / 600 | e.g. "Today's dispatch" |
| Client name | display | 20px / 600 | card headline |
| Big metric | mono | 34px / 500, tabular | e.g. `78%` |
| Section headline | display | 16px / 600 | |
| Body / rationale | body | 15px / 400, line-height 1.6 | |
| Eyebrow / label | mono | 11px / 500, `letter-spacing .08em`, UPPERCASE, `--text-400` | the only uppercase in the app |
| Rank numeral | mono | 13px / 500 | on the rail |
| Caption / timestamp | mono | 12px / 400, `--text-400` | |

Eyebrows in mono-uppercase are the recurring typographic tell that ties the system together — use them for
section labels ("WHY NOW", "DRAFT", "SEGMENT"), sparingly.

---

## Spacing, radius, elevation

```
--space: 4px base;  use 8 / 12 / 16 / 24 / 32 / 48   (pick from this set, don't freestyle)
--radius-card: 14px;
--radius-chip: 8px;
--radius-pill: 999px;   /* only for the signal dots and the confidence arc cap */
--shadow-card: 0 1px 2px rgba(16,20,27,.04), 0 8px 24px rgba(16,20,27,.06);  /* soft, single, not stacked */
```

Generous whitespace — this is a calm brief, not a dense terminal. 24px between cards, 24–32px card
padding. One soft shadow on cards; no neumorphism, no stacked glows.

---

## Layout

```
┌───────────────────────────────────────────────────────────────┐
│  ▎ NEXTBEST            Tuesday, 1 July · 5 clients need you     │  ← ink top bar, mono meta
├──────┬────────────────────────────────────────────────────────┤
│      │                                                          │
│  01● │   ┌── Priya Mehta ─────────── URGENT ── 78% ──┐          │
│  ▏   │   │  Reconnect before she moves the fund       │          │
│  02● │   │  Not contacted 94 days · education-fund note│          │
│  ▏   │   │  [ draft opener … ]        Accept  Edit  Skip│         │
│  03● │   └────────────────────────────────────────────┘          │
│  ▏   │   ┌── Arjun Rao ───────── OPPORTUNITY ── 61% ──┐          │
│ rail │   │  …                                          │          │
│      │   └─────────────────────────────────────────────┘         │
└──────┴────────────────────────────────────────────────────────┘
```

- **Top bar** (ink): wordmark left, live meta right in mono ("5 clients need you today"). No nav menu —
  this app does one thing.
- **Priority rail** (ink, ~72px): the signature element, sticky, scroll mini-map.
- **Feed** (paper): single column of client cards, max content width ~760px, centered in the remaining
  space. Single-column beats a grid here — it reads as a *briefing*, and it keeps the demo linear.
- **Expand in place**: clicking a card expands it downward to reveal the reasoning trace, confidence, full
  rationale, and the full draft editor. (A right-side detail drawer is an acceptable alternative if it
  reads cleaner — pick one and be consistent.)

Responsive: below ~720px the rail collapses to a slim gutter showing just rank + dot; cards go full width.

---

## Component anatomy

### Client card (collapsed)
Rank + signal dot live on the rail, aligned to the card. Card shows: **name** (display), **action badge**,
the **leading metric** big in mono with a tiny inline temperature bar (warm or cool fill), the **headline**
(display 16), a one-line rationale (body, `--text-600`), a `revenue_impact` chip (mono, e.g. `$6.6M upside`),
and the **draft** in a bordered editable field with **Accept · Edit · Skip** beneath. Hover: card lifts 2px,
rail tick brightens.

### Action badge
Small mono-uppercase pill. `URGENT` = warm text on `--warm-100`; `OPPORTUNITY` = cool text on `--cool-100`;
`WATCHLIST` = slate text on `--slate-100`. Text uses the 600 stop of its family (never black on tint).

### Confidence indicator
A thin **arc gauge** (SVG), 0–100, stroke along the warm→cool axis (low confidence warmer, high cooler),
with the number in mono at center. Reads as an instrument dial — reinforces the concept. Animates from 0
to value once on reveal.

### Reasoning trace (the payoff)
Vertical stepped timeline in the expanded panel, on ink or a tinted panel. Each `ReasoningStep`: a small
node, the tool name as a mono eyebrow, and the `finding` in body text. Steps stagger in (40ms apart) so it
*looks* like the agent thinking, then settles. Header eyebrow: `WHY NOW`.

### Draft editor
`textarea` styled as paper with a hairline; mono caption shows char/tone hint. Accept → the card collapses
with a mono "ACCEPTED · ready to send" stamp and a toast; Edit → focuses the textarea; Skip → card fades
and drops to the bottom, rail re-numbers.

---

## Motion (disciplined — motion is easy to overdo)

- **Load:** rail draws top-to-bottom (~500ms), then cards rise + fade in *in rank order*, 60ms stagger.
  One orchestrated entrance, then stillness.
- **Expand:** height + opacity, 240ms ease; reasoning steps stagger in after.
- **Confidence arc:** sweeps to value once on reveal.
- **Hover:** 2px lift, 120ms.
- Everything wrapped in `@media (prefers-reduced-motion: no-preference)`; with reduced motion, content is
  simply present. Use `framer-motion` but keep it to `transform`/`opacity`.

---

## Microcopy (write from the RM's side of the screen)

- Top-bar meta: "5 clients need you today" — not "5 records".
- Badges: `URGENT` / `OPPORTUNITY` / `WATCHLIST`.
- Buttons keep their name through the flow: **Accept** → toast "Accepted"; **Skip** → "Skipped";
  **Edit** focuses the field. Active voice, sentence case.
- Empty state (all handled): a calm line, not a shrug — "You're clear for today. New signals arrive
  overnight." with a small rail-and-checkmark motif.
- Headlines are human and specific: "Reconnect before she moves the education fund", not "High attrition
  risk detected". The `headline`/`rationale` come from the agent — the UI just frames them well.
- Never surface internal metric names; show "78% attrition risk", never `attrition_risk: 78`.

---

## Anti-generic checklist (do NOT ship if any are true)

- [ ] It uses a component library's default look (MUI/Chakra/Ant/unstyled shadcn). → hand-build components.
- [ ] Body font is Inter or Roboto. → use IBM Plex Sans.
- [ ] There's a purple/blue SaaS gradient hero or a generic sidebar-+-topbar admin shell.
- [ ] Statuses are scattered red/green/yellow pills instead of the warm↔cool temperature system.
- [ ] Numbers are proportional (jittering) instead of tabular mono.
- [ ] Emoji anywhere in the UI.
- [ ] More than one "hero" flourish competing with the priority rail.
- [ ] Stacked drop-shadows / glow / neumorphism.
- [ ] Cream/beige background (`#F5F5DC` family). → cool paper `--paper-0`.
- [ ] Text overflows its container, or contrast is weak (light text on light).

Quality floor (ship these quietly): responsive to mobile, visible keyboard focus rings, reduced-motion
respected, all interactive elements reachable by tab. Then take one look and remove one thing that isn't
earning its place.
