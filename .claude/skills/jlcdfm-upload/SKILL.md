---
name: jlcdfm-upload
description: Upload release_jlcpcb/gerbers.zip to https://jlcdfm.com/ (JLCPCB's official DFM tool) via browser automation, run the PCB DFM analysis, optionally upload bom.csv/cpl.csv for the SMT assembly analysis, then capture the findings into a dated report. Use before paying a JLC order, or on explicit /jlcdfm-upload.
disable-model-invocation: true
argument-hint: [pcb | full]
---

# JLCDFM Upload — official JLC DFM verdict on the release set

Uploads the release gerbers to **jlcdfm.com** and captures JLC's own DFM
analysis — the same engine that flagged the 5 danger classes fixed in the
2026-08-03 cycle and the round-2 findings in R32. Our internal gates are
fast but JLC's analyzer is the ground truth for what *their* CAM engineers
will flag: every finding it reports that our gates missed is a candidate
new gate (project convention since the JLCDFM fix cycle).

`pcb` (default) = gerber upload + PCB DFM analysis only.
`full` = also upload `bom.csv` + `cpl.csv` and run the SMT assembly analysis.

## Hard facts (2026-08-12 investigation + 2026-08-13 first full live run)

- The site is a Nuxt SPA; the real API sits behind the same-origin gateway
  `https://jlcdfm.com/api` with service base `/overseas-dfm-service`.
- **Anonymous API upload does not work**: `pcbDfm/uploadGerber` returns a
  raw Spring `500` before multipart binding for non-browser sessions, and
  the frontend has an explicit `code 460 → open login modal` path. A
  logged-in JLCPCB browser session is required — this skill drives Chrome.
- **Login is per-Chrome-profile**: a fresh Chrome hits
  `passport.jlcpcb.com` on first navigate. The USER signs in (credentials/
  Google — never Claude); after that the session cookie persists. There
  may be a reCAPTCHA — user handles it.
- **Gerber upload IS reliably automatable** end to end: `find` the hero
  `input[type=file][accept=".zip,.rar"]` → `file_upload` `gerbers.zip` into
  its ref. Field name is `gerberFile`. Success = `uploadGerber` 200, and
  the SPA opens `/viewer?pcbUploadFileId=<id>` and polls
  `pcbDfm/getParseStatus` until parsed. That `<id>` = **dfmRecordKeyId**.
- **PCB DFM IS reliably automatable**: on the viewer, left tab **PCB DFM**
  is default; click **DFM check** (top-left blue button, ~x77,y51). Results
  fill the left table in ~15 s: three numbers per row = **Danger / Warning
  / Good** (red/orange/green). 0 in the Danger column across all rows = PCB
  clean. `getDfmFile?dfmRecordKeyId=` carries the JSON.
- **SMT DFM (BOM/CPL) is the automation-fragile part — expect to hand off
  to the user.** Observed 2026-08-13: clicking the **BOM match** button
  (SMT DFM tab) under automation did NOT open the "BOM Matching" modal —
  it stayed `display:none`, fired no `smtDfm/*`/`bomMatch*` request, logged
  no console error. A dormant **"Account Restriction Notice"** dialog sits
  in the DOM, consistent with an app-side guard on the automated session.
  **Do not burn turns retrying the click.** Ask the user to drive the SMT
  upload manually (steps in §5b) while you read results — the viewer stays
  in your controlled tab, so once they finish you resume automatically.
- BOM/CPL upload form (when the modal is open, manual or automated):
  multipart field **`bomCplFile`** + `multiSheetCheckFlag`, max 2 MB. The
  real SMT pipeline observed live is `smtDfm/updateJsonMergeFile` →
  `smtDfm/parseDfm` → poll `smtDfm/getParseStatus` (NOT the
  `analyzeFile/getAnalyzeResult` guessed in the old appendix). `code 4003`
  = multi-sheet workbook warning (re-upload with `multiSheetCheckFlag=false`).
- **The viewer is a full inspection tool, not just a scorecard** — use it:
  - Each finding row has a **Details** button (grey if 0, coloured if hits).
    Click it → a dialog lists every instance: `No. | severity | Value |
    Object1 | Object2`, a mini-render, and First/Prev/Next/Last/All nav.
    This is how you enumerate a Danger class point-by-point and see WHICH
    refs it hits (e.g. Pin-inner-edge 50× all `Object1=J4`; Lead-to-hole
    `Object1=U2, Object2=hole`).
  - After a successful BOM match the viewer renders the **3D component
    bodies**. Toggle **Top layer / Bottom layer** and **2D / 3D** (top
    centre) and zoom to do orientation/alignment checks — this is where you
    confirm the LED cathode-side marks, SOT-23 2+1 lead sides, IC pin-1,
    connector keying, the same families `/first-article-check` phase A
    covers. The order-preview viewer showed placeholders; THIS one shows
    real bodies once BOM is matched.

## Steps

### 1. Preconditions (all local, before touching the browser)

```bash
cd /home/pjonny/Documents/myProjects/esp32-emu-turbo
ls -la release_jlcpcb/gerbers.zip release_jlcpcb/bom.csv release_jlcpcb/cpl.csv
make open-issues
```

- Any red gate → STOP. Fix first (`make dispatch`); uploading a known-bad
  set to JLC wastes the round-trip.
- `gerbers.zip` must be newer than the last generator/routing commit —
  if `git log -1 --format=%ci -- hardware/` postdates the zip's mtime,
  regenerate via `/release` (memory rule: **upload only from
  `release_jlcpcb/`**, never ad-hoc exports).
- Confirm sizes: gerber zip < 50 MB, bom/cpl < 2 MB each (site limits).

### 2. Connect the browser

Load the Chrome tools in ONE ToolSearch call (core set + `file_upload`,
`read_network_requests`, `get_page_text`, `find`, `javascript_tool`).

- `tabs_context_mcp` first. If the extension is not connected, STOP and
  ask the user to enable the Claude Chrome extension and retry — there is
  no curl fallback (see hard facts).
- Create a NEW tab, navigate to `https://jlcdfm.com/`.
- Decline non-essential cookie banners if one appears.

Prefer `browser_batch` for every multi-step sequence below (click → wait →
screenshot in one round trip). The CDP click can occasionally time out
("renderer frozen") — if it does, re-screenshot and retry once; it usually
recovers on its own.

### 3. Upload the gerbers  (reliable, fully automated)

1. `find` "file upload input accepting zip rar" → get the hero input's ref
   (`input[type=file][accept=".zip,.rar"]`). **Never click it** (native
   picker blocks the session).
2. `file_upload` the ref with the absolute path of
   `release_jlcpcb/gerbers.zip`.
   - If a login page appears first (`passport.jlcpcb.com`): STOP, ask the
     user to sign in, wait for "done", then re-`find` the ref (it changes
     after reload) and re-upload.
   - If `file_upload` rejects the path: ask the user to drag the file in.
     Never fall back to curl.
3. `read_network_requests` filtered on `pcbDfm`: `uploadGerber` 200 →
   the SPA navigates to `/viewer?pcbUploadFileId=<id>`; `<id>` is the
   **dfmRecordKeyId** every later call uses. It then polls
   `pcbDfm/getParseStatus` (several 200s) — `wait` ~14 s, screenshot, and
   the gerber renders in the viewer.

### 4. PCB DFM check  (reliable, fully automated)

1. Left panel, top: click **DFM check** (the blue button under the PCB DFM
   tab, ~x77,y51). `wait` ~12 s, screenshot.
2. Read the left table: each row shows **Danger / Warning / Good** (red /
   orange / green). Machine JSON is in `pcbDfm/getDfmFile?dfmRecordKeyId=`.
3. `save_to_disk:true` screenshot of the table for the report. Record every
   row whose Danger or Warning column is non-zero.

### 5. SMT assembly analysis (`full` only) — plan to hand the upload to the user

The **BOM match** modal has not opened under automation (see hard facts).
Do NOT loop on it. Flow:

1. Click **SMT DFM** tab (top-left, ~x217,y30). The "Component assembly
   analysis" table appears (all rows 0 until BOM is matched).
2. Try **BOM match** once (~x219,y51). Screenshot + check
   `read_network_requests` for any `smtDfm`/`bomMatch` call and whether a
   visible modal appeared. If nothing opened → go to §5b.

**§5b — user-assisted SMT upload (the reliable path).** Tell the user, in
their controlled viewer tab, to:
  1. On the **SMT DFM** tab press **BOM match**.
  2. In the modal, **Add BOM** → `release_jlcpcb/bom.csv`;
     **Add CPL/coordinate** → `release_jlcpcb/cpl.csv`.
  3. **Process BOM**, then **Save and Close**.
  4. Press **DFM check**.
  Then have them say "done". They will hit the same benign confirmations
  the JLC order flow shows (SW17 not assembled; duplicate-LCSC-part rows
  LED2/LED3-6, R1,R2/R28,29, R17,18,33/R30,31) — all expected, confirm.
  You keep the same tab, so once they finish you resume reading it.

3. When they're done: `read_network_requests` for `smtDfm` should show
   `updateJsonMergeFile` → `parseDfm` → `getParseStatus` 200s. Screenshot
   the "Component assembly analysis" table (D/W/G per row). The board now
   renders **3D component bodies**.

### 5c. Drill down every Danger/Warning point-by-point (the real value)

For each row with a non-zero Danger (and material Warnings), click its
**Details** button (coloured when it has hits):
  - The dialog lists each instance: `No. | severity | Value | Object1 |
    Object2`, with a mini-render and First/Prev/Next/Last/All nav. Zoom the
    header+table region to read Object1/Object2 exactly.
  - Record what the class actually hits. Known-artifact signatures to match
    against the accepted table (2026-08-13 values):
      * **Pin inner edge** → N× all `Object1=J4` (FPC), value ~0.16 mm
        (drifts 0.03→0.08→0.16 across reports). Artifact.
      * **Lead to hole distance** → 1× `Object1=U2` (ESOP-8 thermal-EP GND
        lead vs a GND via — same-net, benign) or `Object1=J1` (plastic
        pegs) on a PCB-only pass. Same one count either way.
      * **Lead area overlapping pad / Component clipped by outline** →
        castellated/fine-pitch + edge-mount parts. Artifact.
  - **Any Danger whose Object1 is a LED, a passive, or an IC pin that is
    NOT the above signatures is a REAL finding** — do not wave it through.
    Verify the geometry locally against `esp32-emu-turbo.kicad_pcb` (e.g.
    is the flagged via same-net as the pad?) before deciding.

### 5d. Alignment / orientation check on the 3D render

With bodies rendered, toggle **Top layer / Bottom layer** and **2D / 3D**
(top centre) and zoom the families `/first-article-check` phase A covers —
this is the independent cross-check on rotation/polarity:
  - **LEDs (LED1-6)**: cathode mark on the **GND** pad side (board-left for
    the top-side row). This is the exact check that caught the R33-MED-2
    reversed-LED bug; re-confirm it here for any set that changed the CPL.
  - **SOT-23 (Q1/Q2/D1)**: 2-pin vs 1-pin side matches the pads.
  - **ICs (U2/U3/U5)**: pin-1 marker corner matches; connectors: keying.
Screenshot anything ambiguous with `save_to_disk:true`.

### 6. Write the report and dispatch findings

```bash
mkdir -p release_jlcpcb/jlcdfm
```

Write `release_jlcpcb/jlcdfm/JLCDFM-report-<YYYY-MM-DD>.md`:

- Header: date, git SHA of the release set, dfmRecordKeyId, analysis type
  (pcb|full).
- Table of findings: severity | area | JLC message | our matching gate
  (or **NO GATE** if none covers it).
- Verdict line: CLEAN / findings to fix.

Then:
- Every **danger**-class finding → open `/dfm-fix` (or `/fix-rotation` for
  rotations); the fix lands in the generator, never in JLC's online editor.
- Every finding with **NO GATE** → note it as a candidate gate in the
  report and tell the user (this is how the 4 gates of the 2026-08-03
  cycle were born).
- CLEAN on both analyses → the set is ready for the `/first-article-check`
  phase A pre-payment protocol.

### 7. Cleanup

Close the tab you created (leave it open only if the user wants to
continue to the order flow manually).

## API appendix (read-side reference, reverse-engineered 2026-08-12)

Gateway: `https://jlcdfm.com/api` — all paths below relative to
`/overseas-dfm-service`. Requests carry a `secretkey: <keyId>` header from
`POST /api/overseas-core-platform/secret/update` (SM2 handshake; only
fields prefixed `{secret}` are ever encrypted — file uploads are plain
multipart). `x-jlc-platform: desktop`, cookies `JLCPCB_SESSION_ID` + login
session.

| Endpoint | Method | Notes |
|----------|--------|-------|
| `/pcbDfm/uploadGerber` | POST | multipart `gerberFile`; 200 → `message` = dfmRecordKeyId; 460 = login required |
| `/pcbDfm/getParseStatus?dfmRecordKeyId=` | GET | poll until parsed |
| `/pcbDfm/getDfmFile?dfmRecordKeyId=` | GET | full PCB DFM result JSON |
| `/smtDfm/updateJsonMergeFile?dfmRecordKeyId=` | POST | **observed live** — fires after BOM match save |
| `/smtDfm/parseDfm` | POST | **observed live** — starts the SMT analysis |
| `/smtDfm/getParseStatus?dfmRecordKeyId=` | GET | **observed live** — poll SMT until parsed |
| `/smtDfm/checkIp` | GET | works anonymously (sanity probe) |
| `/smtDfm/analyzeFile` · `/getAnalyzeResult` | POST | listed in the bundle but NOT the path the live SMT run used — prefer the three rows above |

## Key Files

- `release_jlcpcb/gerbers.zip` — the ONLY artifact ever uploaded (memory rule)
- `release_jlcpcb/bom.csv`, `release_jlcpcb/cpl.csv` — SMT analysis inputs
- `release_jlcpcb/jlcdfm/` — dated reports from this skill
- `.claude/skills/first-article-check/SKILL.md` — the pre-payment protocol this feeds
- `.claude/skills/external-dfm/SKILL.md` — local third-party DFM (KiBot); complementary, not overlapping
