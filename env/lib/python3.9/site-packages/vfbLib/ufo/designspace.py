from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fontTools.designspaceLib import (
        AxisDescriptor,
        DiscreteAxisDescriptor,
    )


def get_ds_location(
    axes: list[AxisDescriptor | DiscreteAxisDescriptor],
    vfb_location: list[float],
    factor=1000,
) -> dict[str, float]:
    # Transfrom a VFB master or instance location to a designspace location dict.
    # Master locations are given in VFB as per-mille in the design coords, so we need
    # the factor 1000.
    # For instance locations, the factor must be 1.
    ds_location: dict[str, float] = {}
    for i in range(len(axes)):
        axis = axes[i]
        if axis.name:
            ds_location[axis.name] = factor * vfb_location[i]
        else:
            raise ValueError(f"Axis doesn't have a name: {axis}")
    return ds_location


def get_ds_design_location(
    axes: list[AxisDescriptor | DiscreteAxisDescriptor], vfb_location: list[float]
) -> dict[str, float]:
    # Transform an instance user location to a design location.
    # Instances are given in the VFB as user coords, but as design coords in the DS.
    ds_user_location = get_ds_location(axes, vfb_location, 1)
    axis_names = {axis.name: axis for axis in axes}
    ds_design_location = {
        name: axis_names[name].map_forward(loc)
        for name, loc in ds_user_location.items()
    }
    return ds_design_location
