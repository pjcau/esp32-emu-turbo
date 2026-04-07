# Test ROMs

Place SNES (.sfc, .smc) and NES (.nes) ROM files here for simulator testing.

These files are NOT committed to git (see .gitignore).
The simulator mounts this directory automatically.

## Usage

```bash
# Place a ROM
cp ~/Downloads/game.sfc test-roms/

# Run simulator
./scripts/sim-run.sh run
```
