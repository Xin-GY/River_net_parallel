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


def irregular_section_points(z_bed: float):
    # 一个简单的不规则主槽断面，不包含额外滩地逻辑。
    return [
        [0.0, z_bed + 1.4],
        [0.3, z_bed + 0.3],
        [1.0, z_bed + 0.0],
        [2.0, z_bed + 0.0],
        [2.8, z_bed + 0.25],
        [3.3, z_bed + 1.5],
    ]


def build_irregular_geometry(length: float = 10.0, dx: float = 0.05):
    x_centers = np.arange(dx / 2.0, length, dx)
    z_bed = np.zeros_like(x_centers)
    section_names = [f"s{i}" for i in range(len(x_centers))]
    section_data = {}
    section_pos = {}
    for name, x, zb in zip(section_names, x_centers, z_bed):
        section_data[name] = irregular_section_points(float(zb))
        section_pos[name] = [float(x), 0.0]
    river_data = {
        "cell_num": int(len(x_centers)),
        "pos": [[0.0, 0.0, 0.0], [length, 0.0, 0.0]],
        "section_name": section_names,
    }
    return river_data, section_data, section_pos, x_centers


def make_sim_data(case_name: str, output_dir: Path):
    start = dt.datetime(2024, 1, 1, 0, 0, 0)
    end = start + dt.timedelta(seconds=1.0)
    return {
        "model_name": case_name,
        "sim_start_time": start.strftime("%Y-%m-%d %H:%M:%S.%f"),
        "sim_end_time": end.strftime("%Y-%m-%d %H:%M:%S.%f"),
        "time_step": 0.05,
        "save_min_interval": 0.05,
        "output_path": str(output_dir),
        "CFL": 0.35,
        "n": 1.0e-4,
        # 当前 irregular boundary/general-chi baseline
        "bc_use_general_chi": True,
        "bc_general_chi_candidate_mode": "guarded_clamp",
        "bc_general_chi_guard_selector": "closure_q_delta",
        "bc_general_chi_guard_q_delta": 0.005,
        "bc_use_order2_extrap": True,
        "bc_use_order2_extrap_flow": True,
        "bc_use_order2_extrap_stage": True,
    }


def main():
    out_dir = PACK_DIR / "example_outputs" / "handoff_demo_irregular_dynamic"
    out_dir.mkdir(parents=True, exist_ok=True)

    river_data, section_data, section_pos, x = build_irregular_geometry()
    sim_data = make_sim_data("handoff_demo_irregular_dynamic", out_dir)
    river = River(river_data, section_data, section_pos, sim_data)

    # 例子：左侧湿、右侧干的初始 front
    init_depth = np.where(x <= 5.0, 0.42, 0.0)
    river.Set_init_water_depth_profile(init_depth)
    river.Q[1:-1] = 0.0

    def closed_bc(r):
        left_sec = r.cell_sections[0]
        right_sec = r.cell_sections[-1]
        r.S[0] = r.S[1]
        r.Q[0] = 0.0
        r._refresh_cell_state(0, level_hint=r.cross_section_table.get_level_by_area(left_sec, max(r.S[0], 0.0)))
        r.S[-1] = r.S[-2]
        r.Q[-1] = 0.0
        r._refresh_cell_state(-1, level_hint=r.cross_section_table.get_level_by_area(right_sec, max(r.S[-1], 0.0)))

    river.boundary_updater = closed_bc

    for current_time in river.Evolve(fine=False, yield_step=0.08):
        print(f"time = {current_time:.3f} s")

    print("done")


if __name__ == "__main__":
    main()
