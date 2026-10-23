# Kepler V

**A 3-inch FPV drone that was designed, 3D printed, assembled, and flown.**

Kepler V started as a CAD project for a small printed quad and became a working aircraft. The current repository documents the flying configuration, the printable parts that match it, the wiring, and the problems found during the first flights.

![Kepler V current build](docs/img/kepler-v-current.png)

## Project status

| Item | Current state |
|---|---|
| Airframe | Designed and printed |
| Electronics | Installed and running |
| First flights | Completed |
| Current prop | Gemfan 3016-3 |
| Hover | Roughly 20% throttle |
| 30% throttle | Fast climb |
| 50% throttle | More power than is useful in close flight |
| Main next task | Throttle tuning and durability testing |

The first flights showed a large surplus of thrust. The aircraft leaves the ground around 20% throttle and climbs hard by 30%. Above 50% it is difficult to hold in a small area. That is useful headroom, but it is too aggressive for early tuning.

## Current configuration

| System | Part |
|---|---|
| Flight controller | JHEMCU GHF435AIO V2, 30 x 30 mm, 20 A 4-in-1 ESC |
| Motors | 1106 4200KV |
| Propellers | Gemfan 3016-3 |
| Battery | 3S LiPo, 70 x 31 x 22 mm envelope |
| Video | EWRF TS5823 Pro 600 mW and S1039 camera |
| Receiver | Built-in ELRS 2.4 GHz |
| GPS | Not installed |
| Auxiliary controller | KEPLER V CH32V003 board over UART5 MSP |
| Airframe material | PLA, with ABS used only as a material proxy in the Fusion appearance |

## Printable parts in the current revision

The current model is split into parts that can be printed and replaced on their own.

| File | What it is | Quantity |
|---|---|---|
| [`v5-base-print.stl`](outputs/cad/v5-base-print.stl) | Main lower frame | 1 |
| [`v5-top-print.stl`](outputs/cad/v5-top-print.stl) | Upper plate | 1 |
| [`v5-top-layer-spacer-4.5.stl`](outputs/cad/v5-top-layer-spacer-4.5.stl) | 4.5 mm spacer under the upper plate | 1 |
| [`motor-spacer-3mm-four-hole-slot.stl`](outputs/cad/motor-spacer-3mm-four-hole-slot.stl) | 18 mm round motor spacer, 3 mm high, with wire slot | 4 |
| [`v5-vtx-tray-separate.stl`](outputs/cad/v5-vtx-tray-separate.stl) | Removable VTX and fan carrier | 1 |
| [`xt30-cable-clamp-base.stl`](outputs/cad/xt30-cable-clamp-base.stl) | Fixed side of the XT30 strain relief | 1 |
| [`xt30-cable-clamp-plate.stl`](outputs/cad/xt30-cable-clamp-plate.stl) | Outer pressure plate | 1 |

All current STLs are watertight and exported with the print surface at `z = 0`.

## Key dimensions

| Feature | Dimension |
|---|---|
| Motor centers | `x = +/-47.73 mm`, `y = +/-47.73 mm` |
| Motor mounting pattern | 6.364 mm square, 9.000 mm diagonal |
| Motor screw hole | 2.2 mm |
| Motor spacer | 18 mm diameter, 3 mm high, four mounting holes plus one side wire slot |
| FC mounting | 25.5 x 25.5 mm, M2, rotated 45 degrees |
| Lower and upper plate | 4.0 mm and 3.0 mm |
| Upper plate height with spacer | 26.5 mm above the lower plate top face |
| Camera holes in lower plate | 20 mm left-to-right spacing, rows at `y = 22` and `y = 30` |
| Camera tray and bracket | 19 mm screw spacing with slotted adjustment |
| Central lower opening | Diamond, nominal 18 mm half-diagonal |

## How the current parts fit

The lower frame keeps the four motor hole patterns but no longer includes fixed motor posts. Each motor sits on a separate 3 mm spacer. The spacer has four screw holes and an open side slot between the mounting holes for the motor wires. This reduces the amount of support that has to be reprinted when a mount is damaged.

The upper plate is raised 4.5 mm by a U-shaped spacer. The open front leaves room for camera uptilt. The rear hole at `(0, -18.031)` is shared with the upper plate and the XT30 clamp.

The VTX tray is a separate part with its own fan frame, upper support frame, four posts, rear braces, and four M2 mounting points. It can be modified or reprinted without touching the main frame.

The XT30 clamp uses a fixed C-shaped body and a removable outer plate. Two horizontal M2 screws pull the plate toward the cable. The fixed body has two 3.9 mm hex nut pockets, which keeps the screwdriver path clear from the outside.

## Wiring

![FC, VTX, and camera wiring](docs/img/fc-vtx-wiring.png)

The video path is:

```text
Camera video out -> FC CAM
FC VTX video out -> VTX Video in
```

The VTX gets battery voltage on the red wire, not 5 V. Its orange 5 V output powers the camera. The white audio input is unused. The FC UART5 port connects to KEPLER V J1 for MSP.

See the [FC and VTX wiring guide](docs/15-FC与图传接线速查.md) for the full pad map.

## First-flight notes

The aircraft flew on 3016-3 props. A hover around 20% throttle is expected with this lightweight build and a charged 3S pack. The current tune is not suited to confined spaces because small stick changes cause large altitude changes.

Start with motor output limit near 70 to 75 percent. Add throttle expo around the actual hover point. Check battery and XT30 temperature after each run. A 2S pack is also a practical way to make the aircraft easier to control without changing the airframe.

## Print settings that worked as a starting point

Use four or more walls, five to six top and bottom layers, and 60 to 80 percent gyroid for the frame. Increase infill around arm roots and mounting points. Print motor spacers and the XT30 clamp with enough walls that the screw holes do not collapse.

Check the STL orientation before slicing. The upper plate, top spacer, motor spacer, VTX tray, and both clamp parts are already exported in print coordinates.

## Repository layout

```text
.
|-- README.md
|-- README.zh-CN.md
|-- docs/
|   |-- current design, wiring, parts, OSD, and auxiliary board notes
|   `-- previous-versions/
|       |-- archived design notes and Fusion screenshots
|       `-- simulation index
|-- outputs/
|   |-- cad/                 current STL files
|   |-- osd_font/            Chinese OSD font files
|   |-- osd_logo/            boot logo BMP files
|   `-- previous-versions/   old CAD and simulation results
|-- ref/                     manufacturer reference images
`-- tools/                   OSD font and boot logo tools
```

## Previous versions

The V1 to V4 hardware, early CAD, and simulation studies are kept for reference. They do not describe the aircraft that is flying now. Start with [Previous versions](docs/previous-versions/README.md) if you are looking for the old frame geometry or FEA results.

## Auxiliary controller

The CH32V003 auxiliary controller lives in a separate repository:

<https://github.com/Mudycrafter-rubbish-coder/kepler-v-acm>

Its local design notes are summarized in [KEPLER V auxiliary controller](docs/14-KEPLER%20V辅助控制模块.md).

## Safety

This is a hobby prototype. Power the aircraft with the propellers removed when testing wiring or firmware. Never power the VTX without an antenna. Treat every LiPo pack as a fire risk, and inspect printed parts after hard landings.

No license file is included yet. Ask before redistributing the design or using it commercially.
