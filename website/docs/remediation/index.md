---
id: index
title: Remediation
slug: /remediation
---

# Remediation

What is left to close the current console (v3): the known bugs, each with
how its fix is proven on the board. With these fixes the console becomes
**v3.1**, still on the ESP32-S3. Studies for new consoles are under
[Next Steps](/docs/next-steps).

| Area | What is open |
|:---|:---|
| [Audio](/docs/remediation/audio) | PDM carrier hiss: R38 RC values, I2S amplifier on the respin, default volume |
| [Emulators](/docs/remediation/emulators) | cores never measured (2600, Duke3D, Lynx, G&W, MSX), DOOM memory leak, Mario Kart at 57 fps, frameskip 0 on the light cores |
| [Hardware](/docs/remediation/hardware) | respin backlog (R37, silkscreen on J3 and the speaker pads) and the open IP5306 no-battery claim |
| [Battery Indicator](/docs/remediation/battery) | battery icon in the launcher's top-right corner: divider rework to GPIO16, ADC driver, launcher only |
