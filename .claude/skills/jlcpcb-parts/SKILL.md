---
name: jlcpcb-parts
model: claude-opus-4-7
description: Search JLCPCB/LCSC parts catalog and check BOM component availability
disable-model-invocation: true
allowed-tools: Bash, Read, Grep, Glob, WebFetch, WebSearch
argument-hint: [check | search <query> | footprint <LCSC_PART> | <LCSC_PART>]
---

# JLCPCB Parts Search and BOM Check

Search the JLCPCB/LCSC parts catalog, verify BOM component availability, and check stock/pricing for PCB assembly orders.

## Mode 1: `check` -- BOM Stock Verification

**Argument:** `/jlcpcb-parts check`

Parses the project BOM and checks every component against the JLCPCB catalog.

### Steps

1. Read the BOM file at `release_jlcpcb/bom.csv` or `hardware/kicad/jlcpcb/bom.csv`
2. Run `python3 scripts/jlcpcb_parts.py check` to parse BOM and list all parts
3. For each unique LCSC part number, use WebSearch to query `site:jlcpcb.com <LCSC_PART>`
4. Extract: stock status, basic/extended category, unit price
5. Flag: out-of-stock parts, extended parts (higher assembly fee), expensive parts (>$1/pc)
6. Output summary table

## Mode 2: `search <query>` -- Catalog Search

**Argument:** `/jlcpcb-parts search 0805 capacitor 10uF`

Searches the JLCPCB parts catalog for components matching the query.

### Steps

1. Use WebSearch to query `site:jlcpcb.com/parts <search terms>`
2. Parse search results for part numbers, specs, prices
3. Present top 5 matches with comparison table

## Mode 3: `footprint <LCSC_PART>` -- Footprint Lookup (via EasyEDA API)

**Argument:** `/jlcpcb-parts footprint C25804`

Fetches footprint details for an LCSC part using the EasyEDA/JLCPCB component API (same method as JLC2KiCad_lib).

### Steps

1. Run `python3 scripts/jlcpcb_parts.py footprint <LCSC_PART>`
2. The script queries `https://easyeda.com/api/products/<LCSC_PART>/components?version=6.5.40`
3. Extracts: footprint name, pad count, body dimensions, 3D model availability, datasheet URL
4. Reports results in a table format

### Use Cases

- Verify a BOM component's footprint matches the PCB design
- Check if a 3D model exists for PCBA rendering
- Compare footprint dimensions against datasheet

## Mode 4: `<LCSC_PART>` -- Part Lookup

**Argument:** `/jlcpcb-parts C25804`

Looks up detailed information for a specific LCSC part number.

### Steps

1. Use WebFetch to load `https://jlcpcb.com/partdetail/<LCSC_PART>`
2. Extract: description, package, stock, price tiers, basic/extended
3. Present detailed part information

## Summary Report Format

The final output for `check` mode should be a markdown table:

```
| # | LCSC Part | Component | Footprint | Stock | Type | Price | Status |
|---|-----------|-----------|-----------|-------|------|-------|--------|
| 1 | C2913202 | ESP32-S3 | Module | 5000 | Ext | $3.20 | OK |
| 2 | C181692 | IP5306 | ESOP-8 | 0 | Ext | $0.45 | OUT! |
```

Status values:
- **OK** -- in stock, no issues
- **OUT!** -- out of stock, needs alternative
- **EXT** -- extended part (higher assembly fee, flag for awareness)
- **$$$** -- expensive part (>$1/pc, flag for cost review)

## Key Files

- `release_jlcpcb/bom.csv` -- Current BOM for JLCPCB order
- `hardware/kicad/jlcpcb/bom.csv` -- Alternative BOM location
- `scripts/jlcpcb_parts.py` -- BOM parser helper script
