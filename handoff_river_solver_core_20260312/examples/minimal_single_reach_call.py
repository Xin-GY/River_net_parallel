from __future__ import annotations

import sys
import datetime as dt
from pathlib import Path

import numpy as np


PACK_DIR = Path(__file__).resolve().parents[1]
CODE_DIR = PACK_DIR / "code" / "current"
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from single_river_clean import River


def build_rectangular_geometry(length: float = 25.0, num_cells: int = 120, width: float = 1.0, bank_height: float = 5.0):
    x_centers = np.linspace(length / (2.0 * num_cells), length - length / (2.0 * num_cells), num_cells)
    section_names = [f"s{i}" for i in range(num_cells)]
    section_data = {}
    section_pos = {}
    for i, x in enumerate(x_centers):
        section_data[section_names[i]] = [
            [0.0, bank_height],
            [0.0, 0.0],
            [width, 0.0],
            [width, bank_height],
        ]
        section_pos[section_names[i]] = [float(x), 0.0]
    river_data = {
        "cell_num": num_cells,
        "pos": [[0.0, 0.0, 0.0], [length, 0.0, 0.0]],
        "section_name": section_names,
    }
    return river_data, section_data, section_pos, x_centers


def make_sim_data(case_name: str, output_dir: Path):
    start = dt.datetime(2024, 1, 1, 0, 0, 0)
    end = start + dt.timedelta(seconds=2.0)
    return {
        "model_name": case_name,
        "sim_start_time": start.strftime("%Y-%m-%d %H:%M:%S.%f"),
        "sim_end_time": end.strftime("%Y-%m-%d %H:%M:%S.%f"),
        "time_step": 0.05,
        "save_min_interval": 0.05,
        "output_path": str(output_dir),
        "CFL": 0.35,
        "n": 0.03,
    }


def main():
    out_dir = PACK_DIR / "example_outputs" / "handoff_demo_single_reach"
    out_dir.mkdir(parents=True, exist_ok=True)

    river_data, section_data, section_pos, x = build_rectangular_geometry()
    sim_data = make_sim_data("handoff_demo_single_reach", out_dir)

    river = River(river_data, section_data, section_pos, sim_data)

    # 例子：全域常水深初值
    river.Set_init_water_depth_profile(np.full_like(x, 1.0, dtype=float))
    river.Q[1:-1] = 0.0

    # 例子：封闭边界
    def wall_bc(r):
        r.S[0] = r.S[1]
        r.Q[0] = -r.Q[1]
        r._refresh_cell_state(0, level_hint=r.water_level[1])
        r.S[-1] = r.S[-2]
        r.Q[-1] = -r.Q[-2]
        r._refresh_cell_state(-1, level_hint=r.water_level[-2])

    river.boundary_updater = wall_bc

    for current_time in river.Evolve(fine=False, yield_step=0.05):
        print(f"time = {current_time:.3f} s")

    print("done")


if __name__ == "__main__":
    main()
