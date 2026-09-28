# spill2source Frontend Demo — Session Handoff

**Purpose of this document:** Complete context transfer so a fresh Claude session (on another account) can pick up this work with zero prior knowledge. Read this top to bottom before doing anything.

---

## 1. What this project is

`spill2source` is an oil-spill backtracking pipeline built by a team for what appears to be a hackathon/prototype (SIH — Smart India Hackathon backend). The frontend is a React app that visualizes the pipeline end-to-end. This session's job is to make the frontend **demo-ready for a recorded prototype video**.

**The demo story (what the video must show, in order):**
1. Submit SAR (satellite radar) images
2. A fake, configurable ~10–13 second "processing" timer illusion
3. Red oil-spill area appears on a map + 3D globe
4. Animated wind + water flow near the spill (showing direction + speed)
5. Forecast + backtrack views
6. Suspects revealed (culprit vessels that may have caused the spill)

**Key intent:** *Everything the backend can do must be visible and usable on the frontend.* Faking data/timing for the demo is explicitly approved by the user. It must work **without the ML model running**.

---

## 2. The working relationship / hard constraints (CRITICAL — read carefully)

These are standing rules from the user. They override normal behavior.

- **PROMPT-ONLY ROLE.** I (Claude) do **NOT** edit code myself. The user has a separate live "workhorse" agent that does the actual editing. My job is to:
  1. Read the codebase (read-only), and
  2. Author ready-to-run **prompts** that the user pastes into the workhorse agent.
  Verbatim from user: *"you are just gonna gimme the prompt you will not edit any code yourself only read the codebase keep that in mind."*

- **GEOGRAPHY DECISION (locked in):** Keep the demo near the **USA / Gulf of Mexico**, near the suspect-vessel cluster. Reason: the teammate built the pipeline around a real US incident, and the suspect vessels are real AIS data in the Gulf of Mexico. So the spill/corridor/origin were relocated to match the suspects — not the other way around.

- **FROZEN FILES — never touch these** (backend logic the team owns):
  - `attribution/score.py`
  - `attribution/candidates.py`
  - `attribution/behavior.py`
  - `/api/forecast` endpoint
  - `/api/backtrack` endpoint

- Confirm any irreversible/destructive action before doing it.

- The working directory was changed to `D:\krushnasindhu` during the session. Frontend lives at `D:\krushnasindhu\spill2source\frontend`.

---

## 3. Tech stack

- React 18.3 + Vite 5.4 (vite v5.4.21), ESM modules, `@vitejs/plugin-react`
- Dependencies: `maplibre-gl ^6.7.0`, `leaflet ^1.9.4`, `three ^0.185.1`, `playwright ^1.63.0`
- Map: **MapLibre GL** with globe projection; flow animation is gated on `flowOn && flowOrigin` inside `MapView`
- Demo data: inline JS constants in `src/data/demoData.js`, loaded synchronously via `loadDemoData()`
- Server for the demo: **uvicorn serves the built `dist/` folder statically** at `http://127.0.0.1:8000`. It uses `FileResponse` (reads disk per request), so a fresh `vite build` is served immediately **without restarting the server**.
- Vite dev server default port: 5173 (but demo uses the built dist on :8000)

---

## 4. The demo flow / stage machine

Lives in `src/App.jsx`, driven by nested `setTimeout` calls in `handleOpenDemo`.

**Stages:** `idle → processing → detected → flow → forecast → backtrack → suspects`

**Pacing constants (`App.jsx` ~lines 13–14):**
```js
const PROCESSING_MS = 11000  // ~10-13s processing timer
const STAGE_GAP_MS = 3000    // gap between each visible stage
```

**Timeline windows:**
| Stage | Time window |
|-------|-------------|
| processing | 0–11s |
| detected | 11–14s |
| flow | 14–17s |
| forecast | 17–20s |
| backtrack | 20–23s |
| suspects | 23s+ |

**Colors:** spill red `#EF4444`, cyan `#38BDF8`, amber `#F59E0B`

**Login flow:** `LoginPage` component → click `LOAD_DEMO_CREDENTIALS` button → click `AUTHENTICATE`. localStorage keys: `krishnasindhu_session`, `krishnasindhu_theme`.

**Header controls (all wired in App.jsx):** DEMO button (`onOpenDemo={handleOpenDemo}`), 3D GLOBE projection toggle (globe↔flat), FLOW, VESSELS, RISK.

---

## 5. Files that matter

- **`src/App.jsx`** — core file. Holds all state, the stage machine, WebSocket live-update handling, and `handleOpenDemo`. This is where the two big fixes landed (see §6).

- **`src/data/demoData.js`** — demo GeoJSON constants. This is the one that was relocated to the Gulf of Mexico. Exports: `demoDetection`, `demoCorridor`, `demoOrigin`, `demoSuspects`, and `loadDemoData()`.

- **`src/demoData.js`** — STALE orphan duplicate (note: `src/` root, not `src/data/`). Deletion candidate. **Not yet deleted** — confirm with user before removing.

- **`src/components/DemoSubmit.jsx`** — exists but is NOT imported in App.jsx. The processing illusion is likely the SCANNING progress bar component instead.

- **`src/components/MapView.jsx`** — renders map/globe; flow animation gated on `flowOn && flowOrigin`.

- **`dist/`** — build output. Was rebuilt green (vite v5.4.21, exit 0) after the last edits.

---

## 6. Fixes already completed and verified (build green)

### Fix 1 — Flow animation was a silent no-op on the demo path (FIXED)
**Bug:** `handleOpenDemo` set `flowOn = true` but never set `flowOrigin`. The render gate is `flowOn && flowOrigin`, so flow never rendered during the demo.
**Fix:** derive `flowOrigin` from the detection polygon centroid at the flow beat. Current code in `App.jsx`:
```js
setTimeout(() => {
  setFlowOn(true)
  setDemoStage('flow')
  const ring = data.detection?.geometry?.coordinates?.[0]
  if (ring?.length) {
    const sum = ring.reduce((a, c) => [a[0] + c[0], a[1] + c[1]], [0, 0])
    setFlowOrigin({ lon: sum[0] / ring.length, lat: sum[1] / ring.length, orientation_deg: null })
  }
}, STAGE_GAP_MS)
```

### Fix 2 — Spill/suspect geography mismatch (FIXED)
**Bug:** suspects were in the Gulf of Mexico but the spill/corridor/origin were in the Gulf of Finland (opposite side of the planet).
**Fix:** relocated detection/corridor/origin into the Gulf of Mexico near the suspect cluster. Suspects left byte-identical (real pipeline data).

**Current `src/data/demoData.js` geometry (verified on disk):**
- `demoDetection.geometry.coordinates`: `[[-88.958,29.093],[-88.943,29.093],[-88.943,29.107],[-88.958,29.107],[-88.958,29.093]]` (~2.3 km², centroid ≈ `[-88.9505, 29.100]`). Also: confidence 0.94, area_km2 2.3, sensor Sentinel-1A, wind_speed 12.5, wind_direction 245, current_speed 0.8, current_direction 200.
- `demoCorridor` LineString: `[-88.9505,29.100] → [-88.970,29.080] → [-88.990,29.060] → [-89.010,29.040] → [-89.030,29.010]`
- `demoOrigin.location`: `[-89.030, 29.010]`; confidence 0.87, method particle_backtrack, particles 10000, match_quality high.
- `demoSuspects`: 15 real Gulf-of-Mexico vessels, **UNTOUCHED / byte-identical** (CG WALNUT `[-88.9492,29.00984]`, KARLA F `[-89.03597,29.01349]`, MATTERHORN TLP `[-88.82565,28.74262]`, etc.). Cluster spans lon −89.21…−88.77, lat 28.74…29.15, center ≈ `[-89.0, 29.0]`.

**Geometry sanity check passed:** slick centroid → corridor runs SW → origin → suspect cluster are all co-located on the same Mississippi-delta patch.

### Fix 3 — Timings (FIXED earlier)
`PROCESSING_MS = 11000`, `STAGE_GAP_MS = 3000` (was too fast before).

---

## 7. The one unresolved thing: stuck workhorse

**Status:** The workhorse agent got stuck in a loop for 33+ minutes executing an **optional** on-camera Playwright verification prompt I authored.

**Root cause (my read):** my verification prompt was too open-ended ("confirm it actually animates, not blank"). The workhorse went down a rabbit hole — pixel-diff canvas sampling, timing math, contact sheets — cycling `preview_navigate / preview_snapshot / preview_evaluate / preview_screenshot / preview_wait / preview_click / preview_press(F5) / preview_resize` against preview tab `0de3a8db-5342-49bf-9c18-5de0cf6312c9` without ever terminating.

**Important:** this was purely optional verification. The mandatory build fixes (§6) are all done and build-verified. Nothing is broken in the app because of this loop — only the verification hung.

**The fix I proposed (pending user choice):** Either
- (a) Stop the workhorse and re-run verification as a **dead-simple** pass: click DEMO, then six `sleep`+`screenshot` cycles, one-line report per shot, no JS evaluation, no pixel math, no files. OR
- (b) Skip automation entirely — for a recorded video the user clicks DEMO on camera anyway, so a manual click-through IS the verification. If the manual run shows red spill + flow + suspects in the Gulf, ship it.

My recommendation: **(b)** — manual click-through is enough. Kill the stuck agent.

---

## 8. What to do next (for the fresh session)

1. Confirm with the user: kill the stuck workhorse? (Almost certainly yes.)
2. Confirm verification path: manual click-through (recommended) vs. the lean six-screenshot automated pass.
3. If the user wants it: author the lean verification prompt for the workhorse (see §7a shape).
4. Optional cleanup (confirm first): delete stale `src/demoData.js` orphan.
5. Remember: **you author prompts, you do not edit code.** Read-only + prompt-authoring only.

---

## 9. Behavioral modes active in the original session (informational)

The original session ran with `caveman-full` (terse compressed prose) + `ponytail-full` (minimal-diff, YAGNI engineering) style modes, plus a `remember` history buffer. These are personal style layers — not project requirements. The fresh session doesn't need them unless the user re-enables them. **File content like this doc is always written in normal English regardless of caveman mode.**
