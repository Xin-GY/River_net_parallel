from __future__ import annotations

from copy import deepcopy


def adjust_sections_by_river_bed_average(river_data, section_data):
    """Shift each section vertically so its minimum bed matches the cell bed average."""
    pos = river_data["pos"]
    names = river_data["section_name"]
    cell_num = river_data["cell_num"]

    assert len(pos) == cell_num + 1, "pos length must be cell_num + 1"
    assert len(names) == cell_num, "section_name length must equal cell_num"

    out = deepcopy(section_data)
    for i, name in enumerate(names):
        z_left = pos[i][2]
        z_right = pos[i + 1][2]
        z_avg = 0.5 * (z_left + z_right)

        pts = out.get(name)
        if not pts:
            continue

        min_y = min(point[1] for point in pts)
        shift = z_avg - min_y
        for point in pts:
            point[1] += shift

    return out
