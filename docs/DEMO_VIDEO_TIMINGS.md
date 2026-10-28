# Demo Video — Assembly Timings

Total ≈ **2:39** (under the 3:00 cap). Timings use the real Polly voiceover beat
durations (`docs/voiceover/*.mp3`).

| # | Segment | Start | End | Dur | VO file | On screen |
|---|---------|-------|-----|-----|---------|-----------|
| 1 | Title intro | 0:00 | 0:32 | 32.0s | `00_hook` (in `intro_title.mp4`) | story deck title slide |
| 2 | FNOL | 0:32 | 0:49 | 17.5s | `01_fnol` | phone photo upload → FNOL_CAPTURED + Nova vision triage |
| 3 | Fan-out | 0:49 | 1:12 | 22.4s | `02_fanout` | dashboard parties + fan-out event → PARTIES_ENGAGED |
| 4 | Gate (twist) | 1:12 | 1:39 | 27.0s | `03_gate` | gate CLOSED → rental re-plan → parts COMMITTED (HOLD) |
| 5 | Approval + continuity | 1:39 | 2:02 | 23.6s | `04_approval` | gate OPEN → Approve/Hold → RCS→SMS |
| 6 | Settlement + proof | 2:02 | 2:23 | 21.0s | `05_settlement` | SETTLED → cut to 3 Gmail emails |
| 7 | Close | 2:23 | 2:39 | 15.7s | `06_close` | architecture diagram (`architecture.png`) |

## Record vs. supplied
- **Record (you):** segments 2–6 — the live UI journey (~1:50). Cut the 3 email
  screenshots in at ~2:02.
- **Supplied:** segment 1 = `docs/intro_title.mp4`; segment 7 = `docs/architecture.png`.

## Cut points to hit while recording
- ~1:12 — reach parts back-ordered; let **gate CLOSED** sit on screen (the money shot; 27s VO covers it).
- ~2:02 — journey hits **SETTLED** → switch to email screenshots.

## Assets
- Single voiceover: `docs/one_touch_resolve_voiceover.mp3` (2:41, all beats)
- Per-beat VO: `docs/voiceover/0X_*.mp3`
- Intro clip: `docs/intro_title.mp4`
- Deck: `docs/story.html` (press F = fullscreen, →/Space = next)
- Close still: `docs/architecture.png`
- Email screenshots: your Gmail (summary + lienholder + parts)

## Final assembly (once `docs/demo_raw.mp4` exists)
1. Prepend `intro_title.mp4`.
2. Lay VO beats 01–06 over the UI recording at the timestamps above.
3. Cut email screenshots in at ~2:02.
4. End on `architecture.png`.
5. Normalize audio, export 1080p `one_touch_resolve_final.mp4`.
