---
sidebar_position: 17
title: JLCPCB API & MCP Integration
---

# JLCPCB API & MCP Integration

Research on available tools to integrate JLCPCB services directly into the Claude Code workflow.

## LCSC-MCP-Server

**Repository:** [mageoch/LCSC-MCP-Server](https://github.com/mageoch/LCSC-MCP-Server)  
**Last updated:** 2026-03-26  
**Status:** Functional, early stage (0 stars)

MCP server for searching LCSC/JLCPCB parts with live API access.

### Features

- Parametric search for passives (R, C, L) by value, package, tolerance
- Free-text search across 2.5M+ parts
- Real-time pricing and stock availability
- Basic vs Extended part classification (impacts JLCPCB assembly cost)
- KiCad symbol, footprint, and 3D model download
- Local SQLite cache for fast repeated queries

### Setup

1. Register at [JLCPCB Developer Portal](https://jlcpcb.com/developer)
2. Obtain credentials: `JLCPCB_APP_ID`, `JLCPCB_API_KEY`, `JLCPCB_API_SECRET`
3. Add to `.mcp.json`:

```json
{
  "mcpServers": {
    "lcsc": {
      "command": "node",
      "args": ["path/to/lcsc-mcp-server/dist/index.js"],
      "env": {
        "JLCPCB_APP_ID": "...",
        "JLCPCB_API_KEY": "...",
        "JLCPCB_API_SECRET": "..."
      }
    }
  }
}
```

### Integration with ESP32 Emu Turbo

- Replaces manual LCSC lookups in the `/jlcpcb-parts` skill
- Enables the pcb-engineer agent to query live stock and pricing
- Can verify Basic/Extended status before BOM finalization
- Potential to auto-download KiCad footprints for new components

---

## JLCPCB API Documentation

**Repository:** [Jackster/JLCPCB-API](https://github.com/Jackster/JLCPCB-API)  
**Last updated:** 2026-02-16  
**Status:** Documentation only (no server)

Reverse-engineered documentation of the JLCPCB Overseas OpenAPI endpoints.

### Available Endpoints

| Endpoint | Description |
|----------|-------------|
| PCB Price Calculation | Get instant quotes for PCB fabrication |
| Gerber Upload | Upload gerber files for order creation |
| Order Creation | Place PCB/PCBA orders programmatically |
| Order Tracking | Check order status and shipping info |

### Authentication

Uses HMAC-SHA256 signing with app credentials. Python examples provided in the repository.

### Potential Skills

| Skill | Description |
|-------|-------------|
| `/jlcpcb-quote` | Get instant price for current gerbers without leaving the CLI |
| `/jlcpcb-order` | Upload gerbers and place an order directly |
| `/jlcpcb-track` | Check order status from the terminal |

---

## Next Steps

1. **Register** for JLCPCB Developer Portal API access
2. **Install** LCSC-MCP-Server and add to `.mcp.json`
3. **Test** part search queries against our BOM components
4. **Evaluate** building a pricing/ordering MCP server using the JLCPCB-API docs
