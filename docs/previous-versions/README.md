# Previous versions

This folder keeps the design history that led to the current Kepler V. The files are useful for comparison, but they are not the current build files.

The aircraft has changed enough that the old simulation results no longer describe the current frame. The V5 revision uses a removable VTX tray, independent motor spacers, a 4.5 mm upper spacer, revised camera holes, and an XT30 cable clamp. The simulation models were created before those changes.

## Archived CAD

Old 2D drawings, STL files, and previews are grouped by revision:

- [V2 parts and early frame](../../outputs/cad/previous-versions/v2/)
- [V3 parts and camera tray](../../outputs/cad/previous-versions/v3/)
- [V4 measured-fit parts](../../outputs/cad/previous-versions/v4/)

The current printable files are kept in [`outputs/cad`](../../outputs/cad/).

## Archived Fusion renders

- [Isometric render](images/fusion-drone-iso.png)
- [Camera end](images/fusion-drone-camera.png)
- [Top view](images/fusion-drone-top.png)
- [Bottom view](images/fusion-drone-bottom.png)

These show an earlier assembly. They are useful for tracing layout decisions, not for checking the current part set.

## Simulation studies

The simulation work was done for earlier frame geometry and material assumptions. Read it as design history.

- [Vibration and material study](07-振动与打印材料方案.md)
- [Impact and screw pullout study](08-冲击与螺丝拉脱.md)
- [Slot half-hole pullout study](09-长槽半孔拉脱.md)
- [Full assembly modal study](10-整机装配模态.md)

The numerical outputs and animations are in [`outputs/previous-versions`](../../outputs/previous-versions/).

## What changed after the simulations

The present aircraft has a different upper-plate height, separate motor spacers, a new VTX carrier, a new XT30 clamp, and revised camera mounting holes. The flight controller and motor mounting pattern are still related to the V3 layout, but the mass distribution and load paths are not identical to the simulated assembly.

Treat the old results as screening work. Use measurements from the aircraft that actually flies when making final tuning decisions.
