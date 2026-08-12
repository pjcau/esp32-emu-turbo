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

## Hard facts from the 2026-08-12 investigation (do not re-derive)

- The site is a Nuxt SPA; the real API sits behind the same-origin gateway
  `https://jlcdfm.com/api` with service base `/overseas-dfm-service`.
- **Anonymous API upload does not work**: `pcbDfm/uploadGerber` returns a
  raw Spring `500` before multipart binding for non-browser sessions, and
  the frontend has an explicit `code 460 → open login modal` path on this
  endpoint. A logged-in JLCPCB browser session is required — which is why
  this skill drives Chrome instead of curl.
- Gerber upload form: single multipart field **`gerberFile`** (zip/rar,
  max 50 MB). Success envelope: `{code: 200, message: <dfmRecordKeyId>}`.
  The SPA stores the id as `pcbUploadFileId` and every later call keys on
  `dfmRecordKeyId=<that id>`.
- BOM/CPL upload form: multipart field **`bomCplFile`** + `multiSheetCheckFlag`,
  max 2 MB, endpoint `smtDfm/uploadBomCpl?fileType=<type>&dfmRecordKeyId=…`.
  `code 4003` = multi-sheet workbook warning (confirm dialog re-uploads with
  `multiSheetCheckFlag=false`).
- Full endpoint map in the appendix below — use it to *read* results from
  network traffic, not to bypass the browser.

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

### 3. Upload the gerbers

1. Locate the file input: `input[type=file][name=file][accept=".zip,.rar"]`
   (the visible "Upload file" button on the right of the hero section wraps
   it). Use `find` / `read_page` to get its ref — **never click it** (native
   picker would block the session).
2. `file_upload` with the ref and the absolute path of
   `release_jlcpcb/gerbers.zip`.
   - If `file_upload` rejects the path (session-share restriction), fall
     back to asking the user to drag the file onto the page; do NOT try to
     re-implement the upload in curl.
3. Watch `read_network_requests` filtered on `pcbDfm/`:
   - `uploadGerber` → `code 200`: note the `message` value = **dfmRecordKeyId**.
   - `code 460` or a login modal: ask the user to sign in to JLCPCB in the
     tab, then re-upload.
   - The SPA then polls `pcbDfm/getParseStatus` — wait (parse of our
     ~270 KB set takes well under a minute) until the analysis screen opens.

### 4. Capture the PCB DFM analysis

The post-upload screen offers the analyses the user described: the PCB DFM
result and the SMT (assembly) analysis entry.

1. Wait for the DFM view to render, then pull the machine-readable result
   from network traffic: response of `pcbDfm/getDfmFile?dfmRecordKeyId=…`
   (JSON with every check + severity). `get_page_text` as backup.
2. Record for the report: every item JLC ranks worse than "pass"
   (danger/warning), with layer, location and JLC's measured value.
3. Screenshot the summary view (`save_to_disk: true`) for the report.

### 5. SMT assembly analysis (`full` argument only)

1. Open the SMT/assembly analysis section and its BOM/CPL upload modal.
2. Upload `release_jlcpcb/bom.csv` then `release_jlcpcb/cpl.csv` into their
   respective inputs (field `bomCplFile`; same no-click / `file_upload` rule).
   On the `4003` multi-sheet dialog choose re-upload without sheet check.
3. Trigger the analysis; the SPA calls `smtDfm/analyzeFile` then polls
   `smtDfm/getAnalyzeStatus`. Read the final `smtDfm/getAnalyzeResult`
   response from network traffic.
4. Record part-matching problems, unrecognized designators, rotation or
   polarity flags. Cross-check any rotation finding against
   `/first-article-check` conventions before believing it — JLC's viewer
   has mis-ranked rotations before (v4.3.1 lesson).

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
| `/smtDfm/uploadBomCpl?fileType=&dfmRecordKeyId=` | POST | multipart `bomCplFile` + `multiSheetCheckFlag`; 4003 = multi-sheet warning |
| `/smtDfm/analyzeFile?dfmRecordKeyId=` | POST | start SMT analysis |
| `/smtDfm/getAnalyzeStatus?dfmRecordKeyId=` | POST | poll |
| `/smtDfm/getAnalyzeResult?dfmRecordKeyId=` | POST | SMT findings JSON |
| `/smtDfm/getSmtDfmInfo?dfmRecordKeyId=` | GET | SMT session info |
| `/smtDfm/checkIp` | GET | works anonymously (sanity probe) |

## Key Files

- `release_jlcpcb/gerbers.zip` — the ONLY artifact ever uploaded (memory rule)
- `release_jlcpcb/bom.csv`, `release_jlcpcb/cpl.csv` — SMT analysis inputs
- `release_jlcpcb/jlcdfm/` — dated reports from this skill
- `.claude/skills/first-article-check/SKILL.md` — the pre-payment protocol this feeds
- `.claude/skills/external-dfm/SKILL.md` — local third-party DFM (KiBot); complementary, not overlapping
