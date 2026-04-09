# JLCPCB DRC Gap Analysis

Cross-reference of agausmann/jlcpcb-kicad-drc rules vs our 115 DFM tests.

## 6 Critical Gaps (our thresholds below JLCPCB minimums)

| # | Rule | Our Value | JLCPCB Value | Test to Fix |
|---|------|-----------|-------------|-------------|
| 1 | Via-to-via (diff-net) | 0.25mm | **0.50mm** | test_via_to_via_spacing |
| 2 | PTH-to-track | 0.15mm | **0.33mm** | test_jlcdfm_pth_to_trace_clearance |
| 3 | Via-to-track | 0.15mm | **0.254mm** | test_drill_trace_clearance |
| 4 | Pad-to-track | 0.10mm | **0.20mm** | test_trace_pad_different_net_clearance |
| 5 | PTH pad-to-pad (diff-net) | 0.15mm | **0.50mm** | test_jlcdfm_pth_spacing |
| 6 | Min via diameter | not checked | **0.50mm** | NEW test needed |

## 22 Rules We Have That They Don't
Soldermask, silkscreen, assembly, signal integrity, firmware sync, etc.
