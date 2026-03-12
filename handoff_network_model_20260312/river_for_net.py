import datetime
import json
import math
import numpy as np
import pandas as pd
import config as config
from shapely.geometry import Polygon, box, LineString, Point
from scipy.sparse import bmat
from scipy.sparse.linalg import spsolve
import matplotlib
import xarray as xr
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from concurrent.futures import ProcessPoolExecutor
from scipy.spatial import cKDTree
from mpl_toolkits.mplot3d import Axes3D
from shapely.ops import substring
from itertools import combinations
import os
from scipy.interpolate import UnivariateSpline, CubicSpline
from pyproj import Transformer
from multiprocessing import Process, Queue

class CrossSectionModel_V3:

    def __init__(self, section_data, section_pos, n_samples=100, use_spline_interpolator=True):
        self.section_data = section_data
        self.section_pos = section_pos
        self.n_samples = n_samples
        self.use_spline_interpolator = bool(use_spline_interpolator)
        self.resampled = {}
        self.sorted_names = []
        self.sorted_coords = np.empty((0, 2), dtype=float)
        self.s_vals = np.array([], dtype=float)
        self.line2d = None
        if self.section_pos is None or len(self.section_pos) == 0:
            print('输入数据为空，无法进行插值重构')
            return
        else:
            for name, pts in section_data.items():
                arr = np.array(pts, float)
                x0, z0 = (arr[:, 0], arr[:, 1])
                x_new = np.linspace(x0.min(), x0.max(), n_samples)
                z_new = np.interp(x_new, x0, z0)
                self.resampled[name] = np.vstack([x_new, z_new]).T
            names = list(section_pos.keys())
            centers = [Point(section_pos[nm]) for nm in names]
            max_d = 0
            for p, q in combinations(centers, 2):
                d = p.distance(q)
                if d > max_d:
                    max_d, start_pt, end_pt = (d, p, q)
            baseline = LineString([(start_pt.x, start_pt.y), (end_pt.x, end_pt.y)])
            proj = [(nm, baseline.project(Point(section_pos[nm]))) for nm in names]
            proj.sort(key=lambda x: x[1])
            self.sorted_names = [nm for nm, _ in proj]
            self.sorted_coords = np.array([section_pos[nm] for nm in self.sorted_names])
            N = len(self.sorted_coords)
            self.s_vals = np.zeros(N)
            for i in range(1, N):
                self.s_vals[i] = self.s_vals[i - 1] + np.linalg.norm(self.sorted_coords[i] - self.sorted_coords[i - 1])
            self.line2d = LineString(self.sorted_coords)

    def get_section_at_xy(self, pt_xy):
        if self.line2d is None:
            raise ValueError('section_pos 缺失，无法进行断面插值重构')
        p = Point(pt_xy)
        s = self.line2d.project(p)
        L = self.line2d.length
        tol = 1e-06 * L
        if s < tol:
            i0, i1, t = (0, 1, 0.0)
        elif s > L - tol:
            i0, i1, t = (len(self.s_vals) - 2, len(self.s_vals) - 1, 1.0)
        else:
            i1 = np.searchsorted(self.s_vals, s)
            i0 = i1 - 1
            t = (s - self.s_vals[i0]) / (self.s_vals[i1] - self.s_vals[i0])
        n0, n1 = (self.sorted_names[i0], self.sorted_names[i1])
        sec0, sec1 = (self.resampled[n0], self.resampled[n1])
        proj_pt = self.line2d.interpolate(s)
        bx, by = (proj_pt.x, proj_pt.y)
        Xmat = np.vstack([self.resampled[nm][:, 0] for nm in self.sorted_names])
        Zmat = np.vstack([self.resampled[nm][:, 1] for nm in self.sorted_names])
        idxs = np.unique(np.clip([i0 - 1, i0, i1, i1 + 1], 0, len(self.s_vals) - 1))
        s_sel = self.s_vals[idxs]
        X_sel = Xmat[idxs, :]
        Z_sel = Zmat[idxs, :]
        X_local = np.zeros(self.n_samples)
        Z_local = np.zeros(self.n_samples)
        for j in range(self.n_samples):
            if self.use_spline_interpolator and len(s_sel) >= 3 and np.unique(s_sel).size >= 3:
                csx = CubicSpline(s_sel, X_sel[:, j], bc_type='natural')
                csz = CubicSpline(s_sel, Z_sel[:, j], bc_type='natural')
                X_local[j] = csx(s)
                Z_local[j] = csz(s)
            else:
                X_local[j] = np.interp(s, s_sel, X_sel[:, j])
                Z_local[j] = np.interp(s, s_sel, Z_sel[:, j])
        X = bx + X_local
        Y = np.full(self.n_samples, by)
        Z = Z_local
        if tol < s < L - tol:
            label = f'InterpSection({n0}-{n1})@{pt_xy}'
        else:
            idx = i0 if s < tol else i1
            label = f'NearestSection@{self.sorted_names[idx]}'
        return {'X': X, 'Y': Y, 'Z': Z, 'label': label, 's_along': s}

    def visualize(self, pt_xy):
        sec = self.get_section_at_xy(pt_xy)
        fig = plt.figure(figsize=(18, 5))
        ax3 = fig.add_subplot(131, projection='3d')
        n, m = (len(self.sorted_names), self.n_samples)
        X3 = np.zeros((n, m))
        Y3 = np.zeros_like(X3)
        Z3 = np.zeros_like(X3)
        for i, nm in enumerate(self.sorted_names):
            bx0, by0 = self.section_pos[nm]
            arr = self.resampled[nm]
            X3[i], Y3[i], Z3[i] = (arr[:, 0] + bx0, by0, arr[:, 1])
            ax3.plot(X3[i], Y3[i], Z3[i], c='gray', alpha=0.5)
        ax3.plot_surface(X3, Y3, Z3, cmap='viridis', alpha=0.6)
        ax3.plot(sec['X'], sec['Y'], sec['Z'], c='red', lw=3, label=sec['label'])
        ax3.set_xlabel('X')
        ax3.set_ylabel('Y')
        ax3.set_zlabel('Z')
        ax3.legend()
        ax2 = fig.add_subplot(132)
        xs, ys = zip(*self.sorted_coords)
        ax2.plot(xs, ys, '-o', color='gold', label='河道折线')
        p2 = Point(pt_xy)
        sal = self.line2d.project(p2)
        pr = self.line2d.interpolate(sal)
        ax2.scatter(*pt_xy, color='red', s=80, label='额外点')
        ax2.scatter(pr.x, pr.y, marker='x', color='blue', s=100, label=f's_along={sal:.1f}')
        seg = substring(self.line2d, 0, sal)
        sx, sy = seg.xy
        ax2.plot(sx, sy, '--', color='green')
        ax2.set_aspect('equal', 'datalim')
        ax2.set_xlabel('X')
        ax2.set_ylabel('Y')
        ax2.set_title(f"投影示意 (s={sec['s_along']:.1f})")
        ax2.legend()
        ax2.grid(alpha=0.3)
        ax1 = fig.add_subplot(133)
        ax1.plot(sec['X'], sec['Z'], '-o', color='red', label=sec['label'])
        ax1.set_xlabel('X (m)')
        ax1.set_ylabel('Z (m)')
        ax1.set_title(f'剖面 at {pt_xy}')
        ax1.grid(True)
        ax1.legend()
        plt.tight_layout()
        plt.show()

class CrossSectionTable:

    def __init__(self, depths, levels, areas, widths, wetted_perimeters, hydraulic_radii, presses, DEBs):
        # Table semantics:
        # - depths: local water depth above the section minimum elevation
        # - levels: absolute water-surface elevation in the section datum
        # - areas/widths/perimeters/radii/presses/DEBs: sampled at the same wet state
        # Query helpers below convert between depth/level/area coordinates by interpolation.
        depths = np.asarray(depths, dtype=float)
        levels = np.asarray(levels, dtype=float)
        areas = np.asarray(areas, dtype=float)
        widths = np.asarray(widths, dtype=float)
        wetted_perimeters = np.asarray(wetted_perimeters, dtype=float)
        hydraulic_radii = np.asarray(hydraulic_radii, dtype=float)
        presses = np.asarray(presses, dtype=float)
        DEBs = np.asarray(DEBs, dtype=float)
        idx = np.argsort(depths)
        self._depth_axis = depths[idx]
        self._area_d = areas[idx]
        idx = np.argsort(levels)
        self._level_axis = levels[idx]
        self._area_l = areas[idx]
        idx = np.argsort(areas)
        self._area_axis = areas[idx]
        self._depth_a = depths[idx]
        self._level_a = levels[idx]
        self._DEB_a = DEBs[idx]
        self._width_a = widths[idx]
        self._wetted_a = wetted_perimeters[idx]
        self._hradius_a = hydraulic_radii[idx]
        self._press_a = presses[idx]
        positive_mask = self._area_axis > 0.0
        self._area_axis_wet = self._area_axis[positive_mask]
        self._width_a_wet = self._width_a[positive_mask]
        self._bed_level = float(self._level_axis[0]) if self._level_axis.size else 0.0
        self._top_level = float(self._level_axis[-1]) if self._level_axis.size else 0.0
        self._min_depth = float(self._depth_axis[0]) if self._depth_axis.size else 0.0
        self._max_depth = float(self._depth_axis[-1]) if self._depth_axis.size else 0.0

    def get_area_by_depth(self, depth, method='interp'):
        if method == 'exact':
            mask = self._depth_axis == depth
            if not mask.any():
                return None
            return float(self._area_d[mask][0])
        return float(np.interp(depth, self._depth_axis, self._area_d))

    def get_area_by_level(self, level, method='interp'):
        if method == 'exact':
            mask = self._level_axis == level
            if not mask.any():
                return None
            return float(self._area_l[mask][0])
        return float(np.interp(level, self._level_axis, self._area_l))

    def get_level_by_area(self, area, method='interp'):
        if method == 'exact':
            mask = self._area_axis == area
            if not mask.any():
                return None
            return float(self._level_a[mask][0])
        return float(np.interp(area, self._area_axis, self._level_a))

    def get_DEB_by_area(self, area, method='interp'):
        if method == 'exact':
            mask = self._area_axis == area
            if not mask.any():
                return None
            return float(self._DEB_a[mask][0])
        return float(np.interp(area, self._area_axis, self._DEB_a))

    def get_depth_by_area(self, area, method='interp'):
        if method == 'exact':
            mask = self._area_axis == area
            if not mask.any():
                return None
            return float(self._depth_a[mask][0])
        return float(np.interp(area, self._area_axis, self._depth_a))

    def get_width_by_area(self, area, method='interp'):
        if method == 'exact':
            mask = self._area_axis == area
            if not mask.any():
                return None
            return float(self._width_a[mask][0])
        area = float(area)
        if area <= 0.0:
            return 0.0
        # Keep the exact dry knot for A=0, but interpolate positive wetted widths on the
        # wet branch only. This matches the positive-side planimetry semantics used by
        # MASCARET's width/celerity chain more closely than interpolating against the dry
        # knot, which artificially collapses width for tiny positive areas.
        if self._area_axis_wet.size > 0:
            return float(np.interp(area, self._area_axis_wet, self._width_a_wet))
        return float(np.interp(area, self._area_axis, self._width_a))

    def get_wetted_perimeter_by_area(self, area, method='interp'):
        if method == 'exact':
            mask = self._area_axis == area
            if not mask.any():
                return None
            return float(self._wetted_a[mask][0])
        return float(np.interp(area, self._area_axis, self._wetted_a))

    def get_hydraulic_radius_by_area(self, area, method='interp'):
        if method == 'exact':
            mask = self._area_axis == area
            if not mask.any():
                return None
            wetted = float(self._wetted_a[mask][0])
            area = float(self._area_axis[mask][0])
            if wetted <= 0.0:
                return 0.0
            return float(area / wetted)
        area = float(area)
        if area <= 0.0:
            return 0.0
        wetted = float(np.interp(area, self._area_axis, self._wetted_a))
        if wetted <= 0.0 or math.isnan(wetted):
            return 1e-07
        return float(area / wetted)

    def get_press_by_area(self, area, method='interp'):
        if method == 'exact':
            mask = self._area_axis == area
            if not mask.any():
                return None
            return float(self._press_a[mask][0])
        return float(np.interp(area, self._area_axis, self._press_a))

    def get_bed_level(self):
        return self._bed_level

    def get_top_level(self):
        return self._top_level

    def get_max_depth(self):
        return self._max_depth

    def get_value_by_area(self, area, value_name, method='interp'):
        mapping = {'depth': (self._area_axis, self._depth_a), 'level': (self._area_axis, self._level_a), 'area': (self._area_axis, self._area_axis), 'DEB': (self._area_axis, self._DEB_a), 'width': (self._area_axis, self._width_a), 'wetted_perimeter': (self._area_axis, self._wetted_a), 'hydraulic_radius': (self._area_axis, self._hradius_a), 'press': (self._area_axis, self._press_a)}
        if value_name not in mapping:
            raise KeyError(f"No field named '{value_name}'")
        axis, arr = mapping[value_name]
        if method == 'exact':
            mask = axis == area
            if not mask.any():
                return None
            return float(arr[mask][0])
        return float(np.interp(area, axis, arr))

class CrossSectionTableManagerV2:

    def __init__(self):
        self.tables = {}

    def add_table(self, name, depths, level, areas, width, wetted_perimeter, hydraulic_radius, press, DEB):
        self.tables[name] = CrossSectionTable(depths, level, areas, width, wetted_perimeter, hydraulic_radius, press, DEB)

    def get_area_by_depth(self, name, depth, method='interp'):
        tbl = self.tables.get(name)
        if tbl is None:
            raise KeyError(f'No table named {name}')
        return tbl.get_area_by_depth(depth, method)

    def get_area_by_level(self, name, level, method='interp'):
        tbl = self.tables.get(name)
        if tbl is None:
            raise KeyError(f'No table named {name}')
        return tbl.get_area_by_level(level, method)

    def get_level_by_area(self, name, area, method='interp'):
        tbl = self.tables.get(name)
        if tbl is None:
            raise KeyError(f'No table named {name}')
        return tbl.get_level_by_area(area, method)

    def get_DEB_by_area(self, name, area, method='interp'):
        tbl = self.tables.get(name)
        if tbl is None:
            raise KeyError(f'No table named {name}')
        return tbl.get_DEB_by_area(area, method)

    def get_depth_by_area(self, name, area, method='interp'):
        tbl = self.tables.get(name)
        if tbl is None:
            raise KeyError(f'No table named {name}')
        return tbl.get_depth_by_area(area, method)

    def get_width_by_area(self, name, area, method='interp'):
        tbl = self.tables.get(name)
        if tbl is None:
            raise KeyError(f'No table named {name}')
        return tbl.get_width_by_area(area, method)

    def get_wetted_perimeter_by_area(self, name, area, method='interp'):
        tbl = self.tables.get(name)
        if tbl is None:
            raise KeyError(f'No table named {name}')
        return tbl.get_wetted_perimeter_by_area(area, method)

    def get_hydraulic_radius_by_area(self, name, area, method='interp'):
        tbl = self.tables.get(name)
        if tbl is None:
            raise KeyError(f'No table named {name}')
        return tbl.get_hydraulic_radius_by_area(area, method)

    def get_press_by_area(self, name, area, method='interp'):
        tbl = self.tables.get(name)
        if tbl is None:
            raise KeyError(f'No table named {name}')
        return tbl.get_press_by_area(area, method)

    def get_bed_level(self, name):
        tbl = self.tables.get(name)
        if tbl is None:
            raise KeyError(f'No table named {name}')
        return tbl.get_bed_level()

    def get_top_level(self, name):
        tbl = self.tables.get(name)
        if tbl is None:
            raise KeyError(f'No table named {name}')
        return tbl.get_top_level()

    def get_max_depth(self, name):
        tbl = self.tables.get(name)
        if tbl is None:
            raise KeyError(f'No table named {name}')
        return tbl.get_max_depth()

    def get_value_by_area(self, name, area, value_name, method='interp'):
        tbl = self.tables.get(name)
        if tbl is None:
            raise KeyError(f'No table named {name}')
        return tbl.get_value_by_area(area, value_name, method)

class River(Process):

    def __init__(self, river_data, section_data, section_pos, sim_data):
        self.Plot_flag = False
        self.FRTIMP = 1
        dtype = np.float32 if config.DTYPE == 'float32' else np.float64
        self.EPSILON = config.EPSILON
        self.water_depth_limit = float(sim_data.get('water_depth_limit', 1.0e-4))
        if self.water_depth_limit <= 0.0:
            self.water_depth_limit = 1.0e-4
        self.velocity_depth_limit = float(sim_data.get('velocity_depth_limit', max(self.water_depth_limit, 1.0e-3)))
        if self.velocity_depth_limit <= 0.0:
            self.velocity_depth_limit = max(self.water_depth_limit, 1.0e-3)
        # 面积干湿阈值应为小量，避免将正常小过水面积误判为干单元
        self.S_limit = 1e-6
        self.g = 9.81
        self.DT_increase_factor = 1.05
        self.model_name = sim_data['model_name']
        self.save_with_ghost = False
        self.bc_use_order2_extrap = bool(sim_data.get('bc_use_order2_extrap', False))
        self.bc_use_order2_extrap_flow = bool(sim_data.get('bc_use_order2_extrap_flow', False))
        self.bc_use_order2_extrap_stage = bool(sim_data.get('bc_use_order2_extrap_stage', False))
        self.bc_stage_on_face = False
        self.bc_use_general_chi = False
        self.refined_section_table = bool(sim_data.get('refined_section_table', True))
        self.section_table_dz = float(sim_data.get('section_table_dz', 0.02))
        if self.section_table_dz <= 0.0:
            self.section_table_dz = 0.02
        self.section_table_num = int(sim_data.get('section_table_num', 300))
        if self.section_table_num < 10:
            self.section_table_num = 10
        self.use_spline_interpolator = bool(sim_data.get('use_spline_interpolator', True))
        self.fix_01_ghost_layout = bool(sim_data.get('fix_01_ghost_layout', False))
        self.fix_02_preserve_true_width = bool(sim_data.get('fix_02_preserve_true_width', False))
        self.fix_03_friction_sign = bool(sim_data.get('fix_03_friction_sign', False))
        self.fix_04_old_state_slice = bool(sim_data.get('fix_04_old_state_slice', False))
        self.fix_05_leveque_wetdry = bool(sim_data.get('fix_05_leveque_wetdry', False))
        self.fix_06_section_area_threshold = bool(sim_data.get('fix_06_section_area_threshold', False))
        self.debug_supercritical_in_count = 0
        self.debug_supercritical_out_count = 0
        self.bc_moc_with_source = False
        self.bc_moc_with_source_flow = False
        self.bc_moc_with_source_stage = False
        self.bc_moc_source_scale = 1.0
        # 可选：超浅水时关闭曼宁摩阻，默认关闭该特性（0表示不启用）
        self.friction_min_depth = 0.0
        # 摩阻模型（保持 Roe 通量主框架）：
        # - manning: 现有曼宁摩阻
        # - chezy: 广义断面 Chézy，dQ/dt = -g * Q|Q| / (C^2 A R)
        # - chezy_h2: SWASHES/FullSWOF 单宽浅水 Chézy，dQ/dt = -g * Q|Q| / (C^2 h^2)
        # - linear_tau: 线性阻尼 dQ/dt = -tau * Q
        # - laminar_h2: 层流阻尼 dQ/dt = -(k/h^2) * Q
        self.friction_model = str(sim_data.get('friction_model', 'manning')).lower()
        self.chezy_friction_c = float(sim_data.get('chezy_friction_c', 0.0))
        self.linear_friction_tau = float(sim_data.get('linear_friction_tau', 0.0))
        self.laminar_friction_k = float(sim_data.get('laminar_friction_k', 0.0))
        self.roe_entropy_fix = float(sim_data.get('roe_entropy_fix', 1.0e-6))
        self.roe_entropy_fix_factor = float(sim_data.get('roe_entropy_fix_factor', 0.1))
        self.positivity_flux_control = bool(sim_data.get('positivity_flux_control', True))
        self._char_potential_cache = {}
        self.section_table_manning_used = {}
        self.cross_section_table = CrossSectionTableManagerV2()
        self.section_interpolation_enabled = bool(section_pos)
        self.Interpolator = None
        if self.section_interpolation_enabled:
            self.Interpolator = CrossSectionModel_V3(
                section_data=section_data,
                section_pos=section_pos,
                use_spline_interpolator=self.use_spline_interpolator,
            )
        def _parse_sim_time(ts):
            if isinstance(ts, datetime.datetime):
                return ts
            txt = str(ts)
            for fmt in ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S'):
                try:
                    return datetime.datetime.strptime(txt, fmt)
                except ValueError:
                    continue
            raise ValueError(f'Unsupported time format: {txt}')

        self.sim_start_time = _parse_sim_time(sim_data['sim_start_time'])
        self.sim_end_time = _parse_sim_time(sim_data['sim_end_time'])
        self.Max_time_step = self.time_step = sim_data['time_step']
        self.output_folder_path = sim_data['output_path']
        self.CFL = sim_data['CFL']
        now = datetime.datetime.now()
        self.file_name = f'result_{now.day:02d}_{now.minute:02d}'
        self.cell_num = river_data['cell_num']
        self.pos = np.array(river_data['pos'], dtype=dtype)
        self.section_name = river_data['section_name']
        self.sections_data = section_data
        self.section_pos = section_pos
        self.DT = 0.1
        self.DT_old = self.DT
        self.min_dt = 1e-05
        self.current_sim_time = 0
        self.current_report_time_step_remaining_time = self.time_step
        self.time_step_count = 0
        self.revelent_time = 0
        self.cell_pos, self.cell_sections, self.cell_lengths = self.interpolate_uniformly()
        self.cell_sections, self.cell_pos, self.cell_lengths = self._build_ghost_layout(
            self.cell_sections, self.cell_pos, self.cell_lengths
        )
        self.cell_coordinate_pos = np.zeros_like(self.cell_pos)
        self.river_bed_height = self.cell_pos[:, 2]
        self.water_level = np.array(self.river_bed_height)
        self.water_depth = self.water_level - self.river_bed_height
        self.Q = np.zeros(self.cell_num + 2, dtype)
        self.S = np.zeros_like(self.Q)
        self.Cell_left_Q = np.zeros_like(self.Q)
        self.Cell_right_Q = np.zeros_like(self.Q)
        self.Cell_left_S = np.zeros_like(self.S)
        self.Cell_right_S = np.zeros_like(self.S)
        self.U = np.zeros_like(self.Q)
        self.FR = np.zeros_like(self.Q)
        self.C = np.zeros_like(self.Q)
        self.PRESS = np.zeros_like(self.Q)
        self.BETA = np.zeros_like(self.Q)
        self.P = np.zeros_like(self.Q)
        self.R = np.zeros_like(self.Q)
        self.cell_press_source = np.zeros((self.cell_num + 1, 2))
        self.QIN = np.zeros_like(self.Q)
        self.DEB = np.zeros_like(self.Q)
        self.Slop = np.zeros_like(self.Q)
        self.DTI = np.zeros_like(self.Q)
        self.n = np.zeros_like(self.Q)
        self.n[:] = sim_data['n']
        self.F_U = np.zeros(self.cell_num + 1, dtype)
        self.F_C = np.zeros_like(self.F_U)
        self.F_Q_SOURCE = np.zeros((self.cell_num + 1, 2))
        self.F_Friction_SOURCE = np.zeros_like(self.F_Q_SOURCE)
        self.F_Singular_Head_Loss = np.zeros_like(self.F_U)
        self.Lambda1 = np.zeros_like(self.F_U)
        self.Lambda2 = np.zeros_like(self.F_U)
        self.abs_Lambda1 = np.zeros_like(self.F_U)
        self.abs_Lambda2 = np.zeros_like(self.F_U)
        self.alpha1 = np.zeros_like(self.F_U)
        self.alpha2 = np.zeros_like(self.F_U)
        self.dissipation1 = np.zeros_like(self.F_U)
        self.dissipation2 = np.zeros_like(self.F_U)
        self.Vactor1 = np.zeros((self.cell_num + 1, 2))
        self.Vactor2 = np.zeros((self.cell_num + 1, 2))
        self.Vactor1_T = np.zeros((self.cell_num + 1, 2))
        self.Vactor2_T = np.zeros((self.cell_num + 1, 2))
        self.Flux_LOC = np.zeros((self.cell_num + 1, 2))
        self.Flux_Source_left = np.zeros((self.cell_num + 2, 2))
        self.Flux_Source_right = np.zeros((self.cell_num + 2, 2))
        self.Flux_Source_center = np.zeros((self.cell_num + 1, 2))
        self.Flux_Friction_left = np.zeros((self.cell_num + 2, 2))
        self.Flux_Friction_right = np.zeros((self.cell_num + 2, 2))
        self.bottom_source = np.zeros((self.cell_num + 2, 2))
        self.friction_source = np.zeros((self.cell_num + 2, 2))
        self.Flux = np.zeros((self.cell_num + 2, 2))
        self.Debit_Flux = np.zeros((self.cell_num + 1, 2))
        self.flag_LeVeque = np.zeros(self.cell_num + 1)
        self.Implic_flag = False
        self.S_old = np.zeros_like(self.S)
        self.Q_old = np.zeros_like(self.Q)
        self.V0 = np.zeros(2, dtype=dtype)
        self.V1 = np.zeros_like(self.V0)
        self.D = np.zeros((self.cell_num + 1, 4), dtype=dtype)
        self.ID = np.zeros_like(self.D)
        self.A = np.zeros((self.cell_num + 2, 4), dtype=dtype)
        self.Lambda1I = np.zeros(self.cell_num + 2)
        self.Lambda2I = np.zeros(self.cell_num + 2)
        self.Vactor1I = np.zeros((self.cell_num + 2, 2))
        self.Vactor2I = np.zeros((self.cell_num + 2, 2))
        self.Vactor1I_T = np.zeros((self.cell_num + 2, 2))
        self.Vactor2I_T = np.zeros((self.cell_num + 2, 2))
        self.Depth_init = False
        self.Level_init = False
        self.Depth_profile_init = False
        self.init_depth_profile = None
        self.save_result_name = None
        # 测试长时案例时可仅保存首末时刻，避免小时间步导致内存膨胀
        self.save_only_end_state = False
        self.save_all_time_steps = bool(sim_data.get('save_all_time_steps', False))
        # 原始结果默认按输出时间步抽样保存，避免 raw nc 只有首末两帧或内存膨胀。
        self.save_min_interval = float(sim_data.get('save_min_interval', self.time_step))
        if self.save_min_interval <= 0.0:
            self.save_min_interval = float(self.time_step) if float(self.time_step) > 0.0 else 1.0
        self._next_save_time = 0.0
        # 可选：在每个内部时间步执行一次边界更新函数（例如测试脚本传入）
        self.boundary_updater = None
        self.constant_rectangular_width = self._detect_constant_rectangular_width()
        self.use_rectangular_hr_flux = bool(
            sim_data.get('use_rectangular_hr_flux', self.constant_rectangular_width is not None)
        )
        self.use_general_hr_flux = bool(
            sim_data.get('use_general_hr_flux', not self.use_rectangular_hr_flux)
        )
        self.use_explicit_tvd_limiter = bool(sim_data.get('use_explicit_tvd_limiter', False))
        self.explicit_tvd_limiter_type = str(sim_data.get('explicit_tvd_limiter_type', 'minmod')).lower()
        self.explicit_tvd_reconstruct_mode = str(sim_data.get('explicit_tvd_reconstruct_mode', 'eta_q')).lower()
        if self.explicit_tvd_reconstruct_mode not in {'eta_q', 'eta_only', 'q_only'}:
            self.explicit_tvd_reconstruct_mode = 'eta_q'
        self.explicit_tvd_limiter_wet_only = bool(sim_data.get('explicit_tvd_limiter_wet_only', True))
        self.explicit_tvd_limiter_min_depth = float(
            sim_data.get('explicit_tvd_limiter_min_depth', max(5.0 * self.water_depth_limit, 0.02))
        )
        self.explicit_tvd_limiter_depth_rel_jump = float(
            sim_data.get('explicit_tvd_limiter_depth_rel_jump', 0.05)
        )
        self.explicit_tvd_limiter_stage_rel_jump = float(
            sim_data.get('explicit_tvd_limiter_stage_rel_jump', 0.005)
        )
        self.explicit_tvd_limiter_q_rel_jump = float(
            sim_data.get('explicit_tvd_limiter_q_rel_jump', 0.05)
        )
        self.explicit_tvd_sensor_fr_tol = float(
            sim_data.get('explicit_tvd_sensor_fr_tol', 0.03)
        )
        self.explicit_tvd_sensor_neighbor_half_window = max(
            int(sim_data.get('explicit_tvd_sensor_neighbor_half_window', 1)), 1
        )
        self.explicit_tvd_sensor_min_neighbor_hits = max(
            int(sim_data.get('explicit_tvd_sensor_min_neighbor_hits', 2)), 1
        )
        self.enable_diagnostics = bool(sim_data.get('enable_diagnostics', False))
        self.diagnostics_stride = max(int(sim_data.get('diagnostics_stride', 1)), 1)
        self.variant_name = str(sim_data.get('variant_name', 'baseline'))
        self.case_name_alias = str(sim_data.get('case_name_alias', self.model_name))
        self.diagnostics_file_prefix = str(sim_data.get('diagnostics_file_prefix', 'run_diagnostics'))
        self.enable_boundary_diagnostics = bool(sim_data.get('enable_boundary_diagnostics', self.enable_diagnostics))
        self.boundary_diagnostics_stride = max(int(sim_data.get('boundary_diagnostics_stride', self.diagnostics_stride)), 1)
        self.enable_boundary_chi_audit = bool(sim_data.get('enable_boundary_chi_audit', False))
        self.near_dry_velocity_cutoff_mode = str(
            sim_data.get('near_dry_velocity_cutoff_mode', 'preserve_q_floor_derived')
        ).lower()
        if self.near_dry_velocity_cutoff_mode not in {'zero_q', 'preserve_q_floor_derived'}:
            self.near_dry_velocity_cutoff_mode = 'preserve_q_floor_derived'
        self.near_dry_derived_mode = str(
            sim_data.get('near_dry_derived_mode', 'actual_u_waterdepth_floor_c')
        ).lower()
        if self.near_dry_derived_mode not in {
            'floor_u_and_c',
            'actual_u_floor_c',
            'actual_u_soft_floor_c',
            'actual_u_waterdepth_floor_c',
        }:
            self.near_dry_derived_mode = 'actual_u_waterdepth_floor_c'
        # Keep an explicit debug escape hatch via `off`, but default fully-wet
        # general-chi stage closure to the guarded clamp verified by the local
        # comparison study. Dry/near-dry paths still bypass this entirely.
        self.bc_general_chi_candidate_mode = str(sim_data.get('bc_general_chi_candidate_mode', 'guarded_clamp')).lower()
        if self.bc_general_chi_candidate_mode not in {'off', 'wet_width', 'guarded_clamp'}:
            self.bc_general_chi_candidate_mode = 'off'
        self.bc_general_chi_guard_abs_delta = float(sim_data.get('bc_general_chi_guard_abs_delta', 0.15))
        self.bc_general_chi_guard_selector = str(
            sim_data.get('bc_general_chi_guard_selector', 'closure_q_delta')
        ).lower()
        if self.bc_general_chi_guard_selector not in {'closure_q_delta', 'legacy_abs_delta'}:
            self.bc_general_chi_guard_selector = 'closure_q_delta'
        self.bc_general_chi_guard_q_delta = float(sim_data.get('bc_general_chi_guard_q_delta', 0.005))
        self.bc_discharge_wetting_mode = str(sim_data.get('bc_discharge_wetting_mode', 'engineering')).lower()
        self.bc_wetting_target_fr = float(sim_data.get('bc_wetting_target_fr', -1.0))
        self.bc_wetting_min_depth = float(sim_data.get('bc_wetting_min_depth', -1.0))
        self.bc_wetting_trigger_depth = float(sim_data.get('bc_wetting_trigger_depth', -1.0))
        self.bc_wetting_trigger_area_factor = float(sim_data.get('bc_wetting_trigger_area_factor', -1.0))
        self.section_S_min = {}
        self.current_forced_dry_count = 0
        self.total_forced_dry_count = 0
        self._forced_dry_recorded = np.zeros(self.cell_num + 2, dtype=bool)
        self.current_leveque_count = 0
        self.total_leveque_count = 0
        self.current_friction_clip_count = 0
        self.total_friction_clip_count = 0
        self.current_interface_counts = {'supercritical_pos': 0, 'supercritical_neg': 0, 'subcritical': 0}
        self.lambda_range_current = {'lambda1_min': 0.0, 'lambda1_max': 0.0, 'lambda2_min': 0.0, 'lambda2_max': 0.0}
        self.diagnostics_history = []
        self.diagnostics_last_snapshot = None
        self.initial_total_volume = None
        self.final_total_volume = None
        self.volume_relative_change = None
        self._init_layout_printed = False
        self.last_old_state_tail = {}
        self.boundary_diagnostics_history = []
        self.left_inflow_fallback_count = 0
        self.left_inflow_cell1_dry_to_wet_count = 0
        self._prev_left_inner_is_dry = None
        self.boundary_face_discharge_left = None
        self.boundary_face_discharge_right = None
        self.boundary_face_area_left = None
        self.boundary_face_area_right = None
        self.boundary_face_width_left = None
        self.boundary_face_width_right = None
        self.boundary_face_level_left = None
        self.boundary_face_level_right = None
        self.use_boundary_face_flux_override = bool(sim_data.get('use_boundary_face_flux_override', False))
        self.use_boundary_face_mass_flux_override = bool(sim_data.get('use_boundary_face_mass_flux_override', False))

    def _detect_constant_rectangular_width(self):
        width_ref = None
        for section_name, section_point in self.sections_data.items():
            pts = np.asarray(section_point, dtype=float)
            if pts.ndim != 2 or pts.shape[1] != 2 or pts.shape[0] < 4:
                return None
            xs = np.unique(np.round(pts[:, 0], 10))
            if xs.size != 2:
                return None
            width = float(xs[1] - xs[0])
            if width <= self.EPSILON:
                return None
            y_min = float(np.min(pts[:, 1]))
            bottom = pts[np.isclose(pts[:, 1], y_min)]
            if bottom.shape[0] < 2:
                return None
            bx = np.sort(bottom[:, 0])
            if not (np.isclose(bx[0], xs[0]) and np.isclose(bx[-1], xs[1])):
                return None
            if width_ref is None:
                width_ref = width
            elif not np.isclose(width, width_ref, rtol=1.0e-8, atol=1.0e-10):
                return None
        return width_ref

    def _build_ghost_layout(self, cell_sections, cell_pos, cell_lengths):
        sections = list(cell_sections)
        pos = np.asarray(cell_pos)
        lengths = np.asarray(cell_lengths)
        if self.fix_01_ghost_layout:
            sections = [sections[0]] + sections + [sections[-1]]
            pos = np.concatenate([pos[:1], pos, pos[-1:]], axis=0)
            lengths = np.concatenate([lengths[:1], lengths, lengths[-1:]], axis=0)
            return sections, pos, lengths
        sections.insert(0, sections[0])
        sections.append(sections[-1])
        pos = np.insert(pos, 0, pos[0], axis=0)
        pos = np.insert(pos, pos.shape[0], pos[-1], axis=0)
        lengths = np.insert(lengths, 0, lengths[0], axis=0)
        lengths = np.insert(lengths, lengths.shape[0], lengths[-1], axis=0)
        return sections, pos, lengths

    def _real_cell_slice(self):
        return slice(1, self.cell_num + 1)

    def _set_boundary_face_state(self, side, level=None, area=None, discharge=None, width=None):
        side_txt = 'left' if str(side).lower().startswith('l') else 'right'
        area_val = None if area is None else float(area)
        width_val = width
        if width_val is None and area_val is not None:
            ghost_idx = 0 if side_txt == 'left' else -1
            sec_name = self.cell_sections[ghost_idx]
            if area_val <= 0.0:
                width_val = 0.0
            else:
                width_val = float(self.cross_section_table.get_width_by_area(sec_name, max(area_val, 1.0e-12)))
        setattr(self, f'boundary_face_level_{side_txt}', None if level is None else float(level))
        setattr(self, f'boundary_face_area_{side_txt}', area_val)
        setattr(self, f'boundary_face_discharge_{side_txt}', None if discharge is None else float(discharge))
        setattr(self, f'boundary_face_width_{side_txt}', None if width_val is None else float(width_val))

    def _sync_boundary_face_state_from_ghost(self, side):
        side_txt = 'left' if str(side).lower().startswith('l') else 'right'
        ghost_idx = 0 if side_txt == 'left' else -1
        area = float(self.S[ghost_idx])
        self._set_boundary_face_state(
            side_txt,
            level=float(self.water_level[ghost_idx]),
            area=area,
            discharge=float(self.Q[ghost_idx]),
        )

    def _real_interface_slice(self):
        return slice(0, self.cell_num + 1)

    def _get_section_s_limit(self, section_name):
        if not self.fix_06_section_area_threshold:
            return self.S_limit
        return max(float(self.section_S_min.get(section_name, self.S_limit)), self.S_limit)

    def _get_section_table_bed_level(self, section_name):
        try:
            return float(self.cross_section_table.get_bed_level(section_name))
        except KeyError:
            section_point = self.sections_data[section_name]
            ys = [pt[1] for pt in section_point]
            return float(np.min(ys))

    def _get_cell_s_limit(self, idx):
        return self._get_section_s_limit(self.cell_sections[idx])

    def _get_face_s_limit(self, i):
        left_limit = self._get_cell_s_limit(i)
        right_limit = self._get_cell_s_limit(i + 1)
        return max(left_limit, right_limit)

    def _get_dry_discharge_tolerance(self, idx, depth=None):
        """Scale a negligible-Q tolerance from the cell dry-area threshold.

        This keeps the explicit dry admissibility chain from snapping a
        still-wet front cell to dry solely because its depth is tiny, while
        still allowing truly stagnant near-dry films to be cleared.
        """
        if depth is None:
            depth = float(self.water_depth[idx])
        depth_ref = max(float(depth), float(self.water_depth_limit), self.EPSILON)
        return float(self._get_cell_s_limit(idx)) * np.sqrt(self.g * depth_ref)

    def _is_cell_dry(self, idx, area=None, depth=None):
        if area is None:
            area = float(self.S[idx])
        if depth is None:
            depth = float(self.water_depth[idx])
        area_limit = self._get_cell_s_limit(idx)
        if area <= area_limit:
            return True
        if depth <= self.water_depth_limit:
            return np.abs(float(self.Q[idx])) <= self._get_dry_discharge_tolerance(idx, depth)
        return False

    def _record_forced_dry(self, idx, prev_s=None, prev_depth=None):
        """Diagnostics owner: count a forced-dry event at most once per cell per step."""
        if 0 <= idx < self._forced_dry_recorded.shape[0] and self._forced_dry_recorded[idx]:
            return
        if prev_s is None:
            prev_s = float(self.S[idx])
        if prev_depth is None:
            prev_depth = float(self.water_depth[idx])
        if prev_s > self._get_cell_s_limit(idx) or prev_depth > self.water_depth_limit:
            self.current_forced_dry_count += 1
            self.total_forced_dry_count += 1
            if 0 <= idx < self._forced_dry_recorded.shape[0]:
                self._forced_dry_recorded[idx] = True

    def _zero_conservative_cell(self, idx):
        """Bookkeeping owner: zero conservative unknowns without touching derived state."""
        self.S[idx] = 0.0
        self.Q[idx] = 0.0

    def _apply_conservative_dry_guard(self, idx, prev_s=None, prev_depth=None):
        """Conservative owner: enforce dry-state admissibility on S/Q only."""
        if prev_s is None:
            prev_s = float(self.S[idx])
        if prev_depth is None:
            prev_depth = float(self.water_depth[idx])
        self._record_forced_dry(idx, prev_s=prev_s, prev_depth=prev_depth)
        self._zero_conservative_cell(idx)

    def _apply_explicit_conservative_increment(self):
        """Conservative owner: apply explicit flux/source increment to S/Q."""
        N = self.cell_num
        flux_div = self.Flux_LOC[1:N + 1] - self.Flux_LOC[:N]
        sum_src = (
            self.Flux_Source_right[1:N + 1]
            + self.Flux_Source_left[1:N + 1]
            + self.Flux_Friction_right[1:N + 1]
            + self.Flux_Friction_left[1:N + 1]
        )
        sum_src[:, 1] += self.Flux_Source_center[1:N + 1, 1]
        self.Flux[1:N + 1] = flux_div + sum_src
        lengths = self.cell_lengths[1:N + 1]
        ww = -self.Flux[1:N + 1] * (self.DT / lengths)[:, None]
        S_old = self.S[1:N + 1].copy()
        Q_old = self.Q[1:N + 1].copy()
        self.S[1:N + 1] = S_old + ww[:, 0]
        self.Q[1:N + 1] = Q_old + ww[:, 1]

    def _apply_explicit_friction_substep(self):
        """Conservative owner: apply post-flux friction update on Q."""
        if self.FRTIMP:
            for i in range(1, self.cell_num + 1):
                prev_s = float(self.S[i])
                prev_depth = float(self.water_depth[i])
                depth_i = self.cross_section_table.get_depth_by_area(self.cell_sections[i], max(self.S[i], 0.0))
                if self._is_cell_dry(i, area=self.S[i], depth=depth_i):
                    self._apply_conservative_dry_guard(i, prev_s=prev_s, prev_depth=prev_depth)
                else:
                    if self.friction_min_depth > 0.0 and depth_i <= self.friction_min_depth:
                        coef = 0.0
                    else:
                        deb = self.cross_section_table.get_DEB_by_area(self.cell_sections[i], self.S[i])
                        coef = self.g * self.DT * self.S[i] / (deb * deb)
                    delta = 1 + 4 * coef * np.abs(self.Q[i])
                    if coef > 1e-06:
                        if self.Q[i] > 0:
                            self.Q[i] = (-1 + np.sqrt(delta)) / (2 * coef)
                        else:
                            self.Q[i] = (1 - np.sqrt(delta)) / (2 * coef)
                    else:
                        self.Q[i] = self.Q[i] * (1 - coef * self.Q[i])
        if self.friction_model == 'linear_tau' and self.linear_friction_tau > 0.0:
            coef = max(self.DT * self.linear_friction_tau, 0.0)
            decay = np.exp(-coef)
            for i in range(1, self.cell_num + 1):
                if self.S[i] > self._get_cell_s_limit(i):
                    self.Q[i] = self.Q[i] * decay
        elif self.friction_model == 'chezy' and self.chezy_friction_c > 0.0:
            c2 = self.chezy_friction_c * self.chezy_friction_c
            for i in range(1, self.cell_num + 1):
                if self.S[i] > self._get_cell_s_limit(i):
                    area_i = max(float(self.S[i]), self._get_cell_s_limit(i))
                    radius_i = self.cross_section_table.get_hydraulic_radius_by_area(self.cell_sections[i], area_i)
                    radius_i = max(float(radius_i), self.water_depth_limit)
                    coef = self.DT * self.g * np.abs(self.Q[i]) / (c2 * area_i * radius_i + self.EPSILON)
                    self.Q[i] = self.Q[i] / (1.0 + coef)
        elif self.friction_model == 'chezy_h2' and self.chezy_friction_c > 0.0:
            c2 = self.chezy_friction_c * self.chezy_friction_c
            for i in range(1, self.cell_num + 1):
                if self.S[i] > self._get_cell_s_limit(i):
                    depth_i = self.cross_section_table.get_depth_by_area(self.cell_sections[i], self.S[i])
                    depth_i = max(float(depth_i), self.water_depth_limit)
                    coef = self.DT * self.g * np.abs(self.Q[i]) / (c2 * depth_i * depth_i + self.EPSILON)
                    self.Q[i] = self.Q[i] / (1.0 + coef)
        elif self.friction_model == 'laminar_h2' and self.laminar_friction_k > 0.0:
            for i in range(1, self.cell_num + 1):
                if self.S[i] > self._get_cell_s_limit(i):
                    depth_i = self.cross_section_table.get_depth_by_area(self.cell_sections[i], self.S[i])
                    depth_i = max(depth_i, self.water_depth_limit)
                    coef = max(self.DT * self.laminar_friction_k / (depth_i * depth_i + self.EPSILON), 0.0)
                    self.Q[i] = self.Q[i] * np.exp(-coef)

    def _enforce_explicit_conservative_admissibility(self):
        """Conservative owner: final dry admissibility on settled S/Q after substeps."""
        for i in range(1, self.cell_num + 1):
            prev_s = float(self.S[i])
            prev_depth = float(self.water_depth[i])
            depth_i = self.cross_section_table.get_depth_by_area(self.cell_sections[i], max(self.S[i], 0.0))
            if self._is_cell_dry(i, area=self.S[i], depth=depth_i):
                self._apply_conservative_dry_guard(i, prev_s=prev_s, prev_depth=prev_depth)

    def _resolve_width_for_state(self, section_name, area, depth):
        width = float(self.cross_section_table.get_width_by_area(section_name, area))
        if (not self.fix_02_preserve_true_width) and width < self.EPSILON and depth > self.water_depth_limit:
            width = max(area / max(depth, self.water_depth_limit), self.EPSILON)
        return max(width, self.EPSILON)

    def _compute_near_dry_derived_state(self, idx):
        """Derived-state owner for still-wet near-dry cells.

        Preserve conservative Q on still-wet near-dry cells while regularizing
        only the derived wave-speed path strongly enough to avoid diagnostic and
        CFL blow-ups at the front tail.
        """
        sec = self.cell_sections[idx]
        depth_actual = max(
            float(self.water_depth[idx]),
            float(self.water_depth_limit),
            self.EPSILON,
        )
        area_actual = max(
            float(self.S[idx]),
            float(self._get_cell_s_limit(idx)),
            self.EPSILON,
        )
        depth_floor = max(float(self.velocity_depth_limit), float(self.water_depth_limit))
        if self.near_dry_derived_mode == 'actual_u_soft_floor_c':
            # Keep a nonzero wave-speed floor, but avoid forcing every near-dry
            # cell up to velocity_depth_limit. The geometric-mean depth is the
            # first regularization level above the true dry threshold.
            depth_floor = max(
                depth_actual,
                np.sqrt(max(float(self.water_depth_limit), self.EPSILON) * depth_floor),
            )
        elif self.near_dry_derived_mode == 'actual_u_waterdepth_floor_c':
            # Use the explicit dry threshold itself as the minimum wave-speed
            # depth for still-wet cells. This keeps a nonzero celerity floor
            # without inflating C all the way up to velocity_depth_limit.
            depth_floor = max(depth_actual, float(self.water_depth_limit), self.EPSILON)
        area_floor = max(
            area_actual,
            float(self.cross_section_table.get_area_by_depth(sec, depth_floor)),
            float(self._get_cell_s_limit(idx)),
            self.EPSILON,
        )
        width_floor = self._resolve_width_for_state(sec, area_floor, depth_floor)
        if self.near_dry_derived_mode == 'floor_u_and_c':
            self.U[idx] = float(self.Q[idx]) / area_floor
        else:
            self.U[idx] = float(self.Q[idx]) / area_actual
        self.C[idx] = np.sqrt(self.g * area_floor / width_floor)
        self.FR[idx] = np.abs(self.U[idx]) / max(self.C[idx], self.EPSILON)

    def _compute_total_volume(self):
        sl = self._real_cell_slice()
        return float(np.sum(np.maximum(self.S[sl], 0.0) * self.cell_lengths[sl]))

    def _print_initial_layout(self):
        if self._init_layout_printed:
            return
        self._init_layout_printed = True
        layout = {
            'variant_name': self.variant_name,
            'case_name_alias': self.case_name_alias,
            'ghost_layout': {
                'left_ghost_index': 0,
                'left_real_index': 1,
                'right_real_index': self.cell_num,
                'right_ghost_index': self.cell_num + 1,
            },
            'cell_sections_head3': list(self.cell_sections[:3]),
            'cell_sections_tail3': list(self.cell_sections[-3:]),
            'cell_pos_head3': np.asarray(self.cell_pos[:3]).tolist(),
            'cell_pos_tail3': np.asarray(self.cell_pos[-3:]).tolist(),
            'cell_lengths_head3': np.asarray(self.cell_lengths[:3]).tolist(),
            'cell_lengths_tail3': np.asarray(self.cell_lengths[-3:]).tolist(),
        }
        print(json.dumps(layout, ensure_ascii=False))
        if self.enable_diagnostics:
            os.makedirs(self.output_folder_path, exist_ok=True)
            path = os.path.join(self.output_folder_path, f'{self.diagnostics_file_prefix}_initial_layout.json')
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(layout, f, ensure_ascii=False, indent=2)

    def _update_section_S_min(self):
        if not self.fix_06_section_area_threshold:
            self.section_S_min = {}
            return
        data = {}
        for section_name in self.sections_data:
            data[section_name] = max(
                float(self.cross_section_table.get_area_by_depth(section_name, self.water_depth_limit)),
                self.S_limit,
            )
        self.section_S_min = data

    def _diagnostics_snapshot(self, tag, success=True):
        sl = self._real_cell_slice()
        if self.cell_num <= 0:
            return None
        depth = np.asarray(self.water_depth[sl], dtype=float)
        area = np.asarray(self.S[sl], dtype=float)
        flow = np.asarray(self.Q[sl], dtype=float)
        wave = np.asarray(self.C[sl], dtype=float)
        froude = np.asarray(self.FR[sl], dtype=float)
        lambda1 = np.asarray(self.Lambda1[self._real_interface_slice()], dtype=float)
        lambda2 = np.asarray(self.Lambda2[self._real_interface_slice()], dtype=float)
        nan_exists = bool(
            np.isnan(depth).any() or np.isnan(area).any() or np.isnan(flow).any() or np.isnan(wave).any() or np.isnan(froude).any()
        )
        inf_exists = bool(
            np.isinf(depth).any() or np.isinf(area).any() or np.isinf(flow).any() or np.isinf(wave).any() or np.isinf(froude).any()
        )
        wet = depth > self.water_depth_limit
        snapshot = {
            'tag': tag,
            'time_s': float(self.current_sim_time),
            'step': int(self.time_step_count),
            'success': bool(success),
            'nan_exists': nan_exists,
            'inf_exists': inf_exists,
            'negative_s_exists': bool((area < 0.0).any()),
            'negative_depth_exists': bool((depth < 0.0).any()),
            'min_water_depth': float(np.nanmin(depth)),
            'max_water_depth': float(np.nanmax(depth)),
            'min_S': float(np.nanmin(area)),
            'max_S': float(np.nanmax(area)),
            'min_Q': float(np.nanmin(flow)),
            'max_Q': float(np.nanmax(flow)),
            'min_C': float(np.nanmin(wave)),
            'max_C': float(np.nanmax(wave)),
            'min_Fr': float(np.nanmin(froude)),
            'max_Fr': float(np.nanmax(froude)),
            'wet_cell_count': int(np.count_nonzero(wet)),
            'dry_cell_count': int(depth.size - np.count_nonzero(wet)),
            'forced_dry_count_step': int(self.current_forced_dry_count),
            'forced_dry_count_total': int(self.total_forced_dry_count),
            'leveque_trigger_count_step': int(self.current_leveque_count),
            'leveque_trigger_count_total': int(self.total_leveque_count),
            'supercritical_pos_interfaces': int(self.current_interface_counts['supercritical_pos']),
            'supercritical_neg_interfaces': int(self.current_interface_counts['supercritical_neg']),
            'subcritical_interfaces': int(self.current_interface_counts['subcritical']),
            'friction_denom_clip_count_step': int(self.current_friction_clip_count),
            'friction_denom_clip_count_total': int(self.total_friction_clip_count),
            'lambda1_min': float(np.nanmin(lambda1)),
            'lambda1_max': float(np.nanmax(lambda1)),
            'lambda2_min': float(np.nanmin(lambda2)),
            'lambda2_max': float(np.nanmax(lambda2)),
            'total_volume': float(self._compute_total_volume()),
        }
        self.diagnostics_last_snapshot = snapshot
        if self.enable_diagnostics:
            self.diagnostics_history.append(snapshot)
            if (self.time_step_count % self.diagnostics_stride == 0) or tag in ('init', 'final'):
                print(json.dumps(snapshot, ensure_ascii=False))
        return snapshot

    def _reset_step_diagnostics(self):
        self.current_forced_dry_count = 0
        self._forced_dry_recorded.fill(False)
        self.current_leveque_count = 0
        self.current_friction_clip_count = 0
        self.current_interface_counts = {'supercritical_pos': 0, 'supercritical_neg': 0, 'subcritical': 0}

    def _write_diagnostics_outputs(self, success=True):
        if not self.enable_diagnostics:
            return
        os.makedirs(self.output_folder_path, exist_ok=True)
        if self.initial_total_volume is None:
            self.initial_total_volume = self._compute_total_volume()
        self.final_total_volume = self._compute_total_volume()
        denom = max(abs(self.initial_total_volume), 1.0e-12)
        self.volume_relative_change = (self.final_total_volume - self.initial_total_volume) / denom
        final_snapshot = self._diagnostics_snapshot('final', success=success)
        summary = {
            'variant_name': self.variant_name,
            'case_name_alias': self.case_name_alias,
            'model_name': self.model_name,
            'success': bool(success),
            'total_volume_initial': float(self.initial_total_volume),
            'total_volume_final': float(self.final_total_volume),
            'relative_volume_change': float(self.volume_relative_change),
            'forced_dry_count_total': int(self.total_forced_dry_count),
            'leveque_trigger_count_total': int(self.total_leveque_count),
            'friction_denom_clip_count_total': int(self.total_friction_clip_count),
            'debug_supercritical_in_count': int(self.debug_supercritical_in_count),
            'debug_supercritical_out_count': int(self.debug_supercritical_out_count),
            'last_old_state_tail': self.last_old_state_tail,
            'last_snapshot': final_snapshot,
        }
        with open(os.path.join(self.output_folder_path, f'{self.diagnostics_file_prefix}_summary.json'), 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        if self.diagnostics_history:
            pd.DataFrame(self.diagnostics_history).to_csv(
                os.path.join(self.output_folder_path, f'{self.diagnostics_file_prefix}_timeseries.csv'),
                index=False,
            )
        if self.boundary_diagnostics_history:
            pd.DataFrame(self.boundary_diagnostics_history).to_csv(
                os.path.join(self.output_folder_path, f'{self.diagnostics_file_prefix}_boundary_inflow.csv'),
                index=False,
            )
            boundary_summary = {
                'left_inflow_fallback_count_total': int(self.left_inflow_fallback_count),
                'left_inflow_cell1_dry_to_wet_count': int(self.left_inflow_cell1_dry_to_wet_count),
                'bc_discharge_wetting_mode': self.bc_discharge_wetting_mode,
            }
            with open(os.path.join(self.output_folder_path, f'{self.diagnostics_file_prefix}_boundary_inflow_summary.json'), 'w', encoding='utf-8') as f:
                json.dump(boundary_summary, f, ensure_ascii=False, indent=2)

    def _get_left_inflow_wetting_params(self):
        mode = self.bc_discharge_wetting_mode
        if mode == 'benchmark':
            fr_target = 0.85
            min_depth = max(50.0 * self.water_depth_limit, 2.0e-2)
            trigger_depth = max(10.0 * self.water_depth_limit, 2.0e-3)
            trigger_area_factor = 50.0
        elif mode == 'engineering':
            fr_target = 0.95
            min_depth = max(20.0 * self.water_depth_limit, 5.0e-3)
            trigger_depth = max(5.0 * self.water_depth_limit, 1.0e-3)
            trigger_area_factor = 20.0
        else:
            fr_target = 0.95
            min_depth = max(20.0 * self.water_depth_limit, 5.0e-3)
            trigger_depth = max(5.0 * self.water_depth_limit, 1.0e-3)
            trigger_area_factor = 20.0
        if self.bc_wetting_target_fr > 0.0:
            fr_target = float(self.bc_wetting_target_fr)
        if self.bc_wetting_min_depth > 0.0:
            min_depth = float(self.bc_wetting_min_depth)
        if self.bc_wetting_trigger_depth > 0.0:
            trigger_depth = float(self.bc_wetting_trigger_depth)
        if self.bc_wetting_trigger_area_factor > 0.0:
            trigger_area_factor = float(self.bc_wetting_trigger_area_factor)
        fr_target = float(np.clip(fr_target, 0.5, 0.99))
        return {
            'mode': mode,
            'fr_target': fr_target,
            'min_depth': float(max(min_depth, self.water_depth_limit)),
            'trigger_depth': float(max(trigger_depth, self.water_depth_limit)),
            'trigger_area_factor': float(max(trigger_area_factor, 1.0)),
        }

    def _should_use_left_inflow_wetting_fallback(self, Q_in):
        params = self._get_left_inflow_wetting_params()
        if params['mode'] == 'off':
            return False, params
        if float(Q_in) <= 0.0:
            return False, params
        s1 = float(self.S[1])
        h1 = float(self.water_depth[1])
        s_trigger = max(self._get_cell_s_limit(1) * params['trigger_area_factor'], self.S_limit)
        near_dry = (s1 <= s_trigger) or (h1 <= params['trigger_depth']) or self._is_cell_dry(1, area=s1, depth=h1)
        return bool(near_dry), params

    def _solve_area_for_target_froude(self, section_name, Q_abs, fr_target, min_depth):
        tinyA = 1.0e-12
        tinyT = 1.0e-08
        q_abs = float(max(abs(Q_abs), 0.0))
        if q_abs <= tinyA:
            depth = float(max(min_depth, self.water_depth_limit))
            area = float(max(self.cross_section_table.get_area_by_depth(section_name, depth), self._get_section_s_limit(section_name), tinyA))
            width = float(max(self.cross_section_table.get_width_by_area(section_name, area), tinyT))
            celerity = float(np.sqrt(max(self.g * area / width, 0.0)))
            return area, depth, width, celerity
        area_probe = max(float(self.cross_section_table.get_area_by_depth(section_name, max(min_depth, self.water_depth_limit))), self._get_section_s_limit(section_name), tinyA)
        width = float(max(self.cross_section_table.get_width_by_area(section_name, area_probe), tinyT))
        depth = float(max((q_abs / (fr_target * np.sqrt(self.g) * width + tinyT)) ** (2.0 / 3.0), min_depth))
        area = area_probe
        celerity = float(np.sqrt(max(self.g * area / width, 0.0)))
        for _ in range(8):
            area = float(max(self.cross_section_table.get_area_by_depth(section_name, depth), self._get_section_s_limit(section_name), tinyA))
            width = float(max(self.cross_section_table.get_width_by_area(section_name, area), tinyT))
            celerity = float(np.sqrt(max(self.g * area / width, 0.0)))
            if celerity <= tinyT:
                break
            target_area = float(max(q_abs / (fr_target * celerity + tinyT), self._get_section_s_limit(section_name), tinyA))
            depth_new = float(max(self.cross_section_table.get_depth_by_area(section_name, target_area), min_depth))
            if abs(depth_new - depth) <= max(1.0e-7, 1.0e-5 * depth):
                depth = depth_new
                area = target_area
                break
            depth = depth_new
        area = float(max(self.cross_section_table.get_area_by_depth(section_name, depth), self._get_section_s_limit(section_name), tinyA))
        width = float(max(self.cross_section_table.get_width_by_area(section_name, area), tinyT))
        celerity = float(np.sqrt(max(self.g * area / width, 0.0)))
        return area, depth, width, celerity

    def _peek_interface_flux_for_diagnostics(self, iface_idx):
        if self.use_rectangular_hr_flux and self.constant_rectangular_width is not None:
            flux, _, _ = self._compute_rectangular_hr_interface_flux(iface_idx)
            return flux
        if self.use_general_hr_flux:
            flux, _, _ = self._compute_general_hr_interface_flux(iface_idx)
            return flux
        s_i = max(float(self.S[iface_idx]), self._get_cell_s_limit(iface_idx))
        q_i = float(self.Q[iface_idx])
        u_i = q_i / max(s_i, self.EPSILON)
        return np.array([q_i, q_i * u_i + float(self.PRESS[iface_idx])], dtype=float)

    def _append_boundary_diagnostics(self, record, fallback_triggered=False, force=False):
        if not self.enable_boundary_diagnostics:
            return
        should_store = bool(force or fallback_triggered or (self.time_step_count % self.boundary_diagnostics_stride == 0))
        if not should_store:
            return
        self.boundary_diagnostics_history.append(record)
        print(json.dumps(record, ensure_ascii=False))

    def _rectangular_pressure(self, depth):
        if self.constant_rectangular_width is None:
            return 0.0
        h = max(float(depth), 0.0)
        return 0.5 * self.g * self.constant_rectangular_width * h * h

    def _roe_abs_with_fix(self, lam, c):
        delta = max(float(self.roe_entropy_fix), float(self.roe_entropy_fix_factor) * max(float(c), 0.0))
        aval = abs(float(lam))
        if delta <= 0.0 or aval >= delta:
            return aval
        return 0.5 * (lam * lam / delta + delta)

    def _tvd_limiter_phi(self, r):
        if r is None or not np.isfinite(r):
            return 0.0
        r = float(r)
        if self.explicit_tvd_limiter_type == 'vanleer':
            if r <= 0.0:
                return 0.0
            return (r + abs(r)) / (1.0 + abs(r))
        if self.explicit_tvd_limiter_type == 'mc':
            return max(0.0, min((1.0 + r) / 2.0, 2.0, 2.0 * r))
        # default: minmod
        return max(0.0, min(1.0, r))

    def _limited_slope(self, delta_back, delta_fwd):
        tiny = 1.0e-12
        if (not np.isfinite(delta_back)) or (not np.isfinite(delta_fwd)):
            return (0.0, None, 0.0)
        if abs(delta_fwd) <= tiny:
            r = None
            phi = 0.0 if abs(delta_back) > tiny else 1.0
            return (0.0, r, phi)
        r = float(delta_back) / float(delta_fwd)
        phi = self._tvd_limiter_phi(r)
        slope = phi * float(delta_fwd)
        return (float(slope), float(r), float(phi))

    def _compute_rectangular_center_roe_state(self, i):
        if self.constant_rectangular_width is None:
            return None
        if not (1 <= i <= self.cell_num - 1):
            return None
        tiny = max(self.S_limit, self.EPSILON)
        width = float(self.constant_rectangular_width)
        eta = self.river_bed_height + self.water_depth
        z_left = float(self.river_bed_height[i])
        z_right = float(self.river_bed_height[i + 1])
        depth_left = max(float(self.water_depth[i]), 0.0)
        depth_right = max(float(self.water_depth[i + 1]), 0.0)
        eta_left = float(eta[i])
        eta_right = float(eta[i + 1])
        z_face = max(z_left, z_right)
        h_left_hr = max(0.0, eta_left - z_face)
        h_right_hr = max(0.0, eta_right - z_face)
        if h_left_hr <= tiny or h_right_hr <= tiny:
            return None
        a_left = width * h_left_hr
        a_right = width * h_right_hr
        if a_left <= tiny or a_right <= tiny:
            return None
        if self.S[i] > tiny and depth_left > tiny:
            u_left = float(self.Q[i]) / max(float(self.S[i]), tiny)
        else:
            u_left = 0.0
        if self.S[i + 1] > tiny and depth_right > tiny:
            u_right = float(self.Q[i + 1]) / max(float(self.S[i + 1]), tiny)
        else:
            u_right = 0.0
        q_left = a_left * u_left
        q_right = a_right * u_right
        sqrt_hl = np.sqrt(max(h_left_hr, 0.0))
        sqrt_hr = np.sqrt(max(h_right_hr, 0.0))
        denom = sqrt_hl + sqrt_hr
        if denom <= tiny:
            u_roe = 0.0
        else:
            u_roe = (u_left * sqrt_hl + u_right * sqrt_hr) / denom
        c_roe = np.sqrt(self.g * 0.5 * max(h_left_hr + h_right_hr, 0.0))
        return {
            'h_left_hr': float(h_left_hr),
            'h_right_hr': float(h_right_hr),
            'q_left': float(q_left),
            'q_right': float(q_right),
            'u_left': float(u_left),
            'u_right': float(u_right),
            'u_roe': float(u_roe),
            'c_roe': float(c_roe),
            'lambda1': float(u_roe - c_roe),
            'lambda2': float(u_roe + c_roe),
        }

    def _compute_rectangular_tvd_sensor_core(self, i):
        details = {
            'shock_sensor_wet_gate': False,
            'shock_sensor_fr_cross': False,
            'shock_sensor_roe_subcritical': False,
            'shock_sensor_depth_jump_gate': False,
            'shock_sensor_stage_jump_gate': False,
            'shock_sensor_q_jump_gate': False,
            'shock_sensor_jump_gate': False,
            'shock_sensor_core_active': False,
            'shock_sensor_depth_jump_rel': 0.0,
            'shock_sensor_stage_jump_rel': 0.0,
            'shock_sensor_q_jump_rel': 0.0,
            'shock_sensor_fr_min_local': None,
            'shock_sensor_fr_max_local': None,
            'shock_sensor_lambda1_center': None,
            'shock_sensor_lambda2_center': None,
        }
        if not self.use_explicit_tvd_limiter:
            return details
        if self.constant_rectangular_width is None:
            return details
        if not (1 <= i <= self.cell_num - 1):
            return details
        if not self.explicit_tvd_limiter_wet_only:
            wet_gate = True
        else:
            min_depth = max(float(self.explicit_tvd_limiter_min_depth), float(self.water_depth_limit))
            idxs = [max(i - 1, 0), i, i + 1, min(i + 2, self.cell_num + 1)]
            wet_gate = all(float(self.water_depth[idx]) > min_depth for idx in idxs)
        details['shock_sensor_wet_gate'] = bool(wet_gate)
        if not wet_gate:
            return details
        eta = self.river_bed_height + self.water_depth
        fr_tol = max(float(self.explicit_tvd_sensor_fr_tol), 0.0)
        fr_idxs = [max(i - 1, 1), i, i + 1, min(i + 2, self.cell_num)]
        fr_vals = np.asarray([float(self.FR[idx]) for idx in fr_idxs], dtype=float)
        fr_min = float(np.nanmin(fr_vals))
        fr_max = float(np.nanmax(fr_vals))
        fr_cross = (fr_min < 1.0 - fr_tol) and (fr_max > 1.0 + fr_tol)
        details['shock_sensor_fr_cross'] = bool(fr_cross)
        details['shock_sensor_fr_min_local'] = fr_min
        details['shock_sensor_fr_max_local'] = fr_max
        roe_state = self._compute_rectangular_center_roe_state(i)
        if roe_state is not None:
            lam1 = float(roe_state['lambda1'])
            lam2 = float(roe_state['lambda2'])
            roe_subcritical = (lam1 < 0.0) and (lam2 > 0.0)
            details['shock_sensor_lambda1_center'] = lam1
            details['shock_sensor_lambda2_center'] = lam2
        else:
            roe_subcritical = False
        details['shock_sensor_roe_subcritical'] = bool(roe_subcritical)
        depth_left = max(float(self.water_depth[i]), 0.0)
        depth_right = max(float(self.water_depth[i + 1]), 0.0)
        eta_left = float(eta[i])
        eta_right = float(eta[i + 1])
        depth_jump = abs(depth_right - depth_left)
        stage_jump = abs(eta_right - eta_left)
        q_jump = abs(float(self.Q[i + 1]) - float(self.Q[i]))
        depth_scale = max(depth_left, depth_right, float(self.explicit_tvd_limiter_min_depth), self.EPSILON)
        stage_scale = max(abs(eta_left), abs(eta_right), 1.0, self.EPSILON)
        q_scale = max(abs(float(self.Q[i])), abs(float(self.Q[i + 1])), self.EPSILON)
        depth_jump_rel = float(depth_jump / depth_scale)
        stage_jump_rel = float(stage_jump / stage_scale)
        q_jump_rel = float(q_jump / q_scale)
        details['shock_sensor_depth_jump_rel'] = depth_jump_rel
        details['shock_sensor_stage_jump_rel'] = stage_jump_rel
        details['shock_sensor_q_jump_rel'] = q_jump_rel
        depth_jump_gate = depth_jump_rel >= float(self.explicit_tvd_limiter_depth_rel_jump)
        stage_jump_gate = stage_jump_rel >= float(self.explicit_tvd_limiter_stage_rel_jump)
        q_jump_gate = q_jump_rel >= float(self.explicit_tvd_limiter_q_rel_jump)
        jump_gate = depth_jump_gate or stage_jump_gate or q_jump_gate
        details['shock_sensor_depth_jump_gate'] = bool(depth_jump_gate)
        details['shock_sensor_stage_jump_gate'] = bool(stage_jump_gate)
        details['shock_sensor_q_jump_gate'] = bool(q_jump_gate)
        details['shock_sensor_jump_gate'] = bool(jump_gate)
        details['shock_sensor_core_active'] = bool(fr_cross and roe_subcritical and jump_gate)
        return details

    def _should_use_tvd_reconstruction(self, i):
        if not self.use_explicit_tvd_limiter:
            return False
        core = self._compute_rectangular_tvd_sensor_core(i)
        if not core['shock_sensor_core_active']:
            return False
        support = 0
        half_window = int(self.explicit_tvd_sensor_neighbor_half_window)
        for j in range(max(1, i - half_window), min(self.cell_num - 1, i + half_window) + 1):
            if self._compute_rectangular_tvd_sensor_core(j)['shock_sensor_core_active']:
                support += 1
        return support >= int(self.explicit_tvd_sensor_min_neighbor_hits)

    def _reconstruct_rectangular_tvd_states(self, i, z_left, z_right):
        dx_im1 = max(float(self.cell_lengths[max(i - 1, 1)]), self.EPSILON)
        dx_i = max(float(self.cell_lengths[i]), self.EPSILON)
        dx_ip1 = max(float(self.cell_lengths[min(i + 1, self.cell_num)]), self.EPSILON)

        eta = self.river_bed_height + self.water_depth
        q_center = self.Q

        d_eta_back_left = (float(eta[i]) - float(eta[i - 1])) / dx_im1
        d_eta_fwd_left = (float(eta[i + 1]) - float(eta[i])) / dx_i
        slope_eta_left, r_eta_left, phi_eta_left = self._limited_slope(d_eta_back_left, d_eta_fwd_left)

        d_eta_back_right = (float(eta[i + 1]) - float(eta[i])) / dx_i
        d_eta_fwd_right = (float(eta[i + 2]) - float(eta[i + 1])) / dx_ip1
        slope_eta_right, r_eta_right, phi_eta_right = self._limited_slope(d_eta_back_right, d_eta_fwd_right)

        d_q_back_left = (float(q_center[i]) - float(q_center[i - 1])) / dx_im1
        d_q_fwd_left = (float(q_center[i + 1]) - float(q_center[i])) / dx_i
        slope_q_left, r_q_left, phi_q_left = self._limited_slope(d_q_back_left, d_q_fwd_left)

        d_q_back_right = (float(q_center[i + 1]) - float(q_center[i])) / dx_i
        d_q_fwd_right = (float(q_center[i + 2]) - float(q_center[i + 1])) / dx_ip1
        slope_q_right, r_q_right, phi_q_right = self._limited_slope(d_q_back_right, d_q_fwd_right)

        eta_left_rec = float(eta[i]) + 0.5 * dx_i * slope_eta_left
        eta_right_rec = float(eta[i + 1]) - 0.5 * dx_ip1 * slope_eta_right
        q_left_rec = float(q_center[i]) + 0.5 * dx_i * slope_q_left
        q_right_rec = float(q_center[i + 1]) - 0.5 * dx_ip1 * slope_q_right

        # Keep the reconstruction bounded by neighbouring cell values.
        eta_left_min = min(float(eta[i - 1]), float(eta[i]), float(eta[i + 1]))
        eta_left_max = max(float(eta[i - 1]), float(eta[i]), float(eta[i + 1]))
        eta_right_min = min(float(eta[i]), float(eta[i + 1]), float(eta[i + 2]))
        eta_right_max = max(float(eta[i]), float(eta[i + 1]), float(eta[i + 2]))
        eta_left_rec = float(np.clip(eta_left_rec, eta_left_min, eta_left_max))
        eta_right_rec = float(np.clip(eta_right_rec, eta_right_min, eta_right_max))

        q_left_min = min(float(q_center[i - 1]), float(q_center[i]), float(q_center[i + 1]))
        q_left_max = max(float(q_center[i - 1]), float(q_center[i]), float(q_center[i + 1]))
        q_right_min = min(float(q_center[i]), float(q_center[i + 1]), float(q_center[i + 2]))
        q_right_max = max(float(q_center[i]), float(q_center[i + 1]), float(q_center[i + 2]))
        q_left_rec = float(np.clip(q_left_rec, q_left_min, q_left_max))
        q_right_rec = float(np.clip(q_right_rec, q_right_min, q_right_max))

        h_left_raw = max(eta_left_rec - float(z_left), 0.0)
        h_right_raw = max(eta_right_rec - float(z_right), 0.0)
        return {
            'eta_left_center': float(eta[i]),
            'eta_right_center': float(eta[i + 1]),
            'eta_left_recon': float(eta_left_rec),
            'eta_right_recon': float(eta_right_rec),
            'q_left_center': float(q_center[i]),
            'q_right_center': float(q_center[i + 1]),
            'q_left_recon': float(q_left_rec),
            'q_right_recon': float(q_right_rec),
            'h_left_raw_recon': float(h_left_raw),
            'h_right_raw_recon': float(h_right_raw),
            'slope_eta_left': float(slope_eta_left),
            'slope_eta_right': float(slope_eta_right),
            'slope_q_left': float(slope_q_left),
            'slope_q_right': float(slope_q_right),
            'r_eta_left': r_eta_left,
            'r_eta_right': r_eta_right,
            'r_q_left': r_q_left,
            'r_q_right': r_q_right,
            'phi_eta_left': float(phi_eta_left),
            'phi_eta_right': float(phi_eta_right),
            'phi_q_left': float(phi_q_left),
            'phi_q_right': float(phi_q_right),
        }

    def Init_cell_proprity(self, fine):
        n = np.unique(self.n)
        self.Create_cross_section_table(n, num=self.section_table_num)
        for i in range(self.cell_num + 2):
            section_name = self.cell_sections[i]
            section_bed = self._get_section_table_bed_level(section_name)
            self.river_bed_height[i] = section_bed
            # 初始化阶段需要保持“用户指定量”不被地形重算破坏：
            # - 若设置的是水位(Level_init)，则固定水位并反推水深；
            # - 否则沿用当前水深并更新水位。
            if self.Level_init:
                self.water_level[i] = self.init_water_level
                self.water_depth[i] = self.water_level[i] - section_bed
            else:
                self.water_level[i] = self.water_depth[i] + section_bed
            if self.water_depth[i] < self.water_depth_limit:
                self.water_depth[i] = 0.0
                self.water_level[i] = self.river_bed_height[i]
            self.S[i] = self.cross_section_table.get_area_by_level(section_name, self.water_level[i])
            if self._is_cell_dry(i, area=self.S[i], depth=self.water_depth[i]):
                self.S[i] = 0.0
                self.Q[i] = 0.0
                self.U[i] = 0
            else:
                if self.water_depth[i] <= self.velocity_depth_limit:
                    self.Q[i] = 0.0
                    self.U[i] = 0.0
                else:
                    self.U[i] = self.Q[i] / self.S[i]
            water_surface_width = self.cross_section_table.get_width_by_area(section_name, self.S[i])
            if water_surface_width > self.water_depth_limit and self.S[i] > self._get_cell_s_limit(i) and self.water_depth[i] > self.velocity_depth_limit:
                self.C[i] = np.sqrt(self.g * self.S[i] / water_surface_width)
                self.FR[i] = np.abs(self.U[i]) / self.C[i]
            else:
                self.C[i] = self.EPSILON
                self.FR[i] = 0.0
            self.P[i] = self.cross_section_table.get_wetted_perimeter_by_area(section_name, self.S[i])
            self.PRESS[i] = self.cross_section_table.get_press_by_area(section_name, self.S[i])
            self.R[i] = self.cross_section_table.get_hydraulic_radius_by_area(section_name, self.S[i])
            self.BETA[i] = 1
            if i >= self.cell_num:
                self.Slop[i] = (self.river_bed_height[i - 1] - self.river_bed_height[i]) / self.cell_lengths[i]
            else:
                self.Slop[i] = (self.river_bed_height[i] - self.river_bed_height[i + 1]) / self.cell_lengths[i]
            if self.Slop[i] == 0:
                self.Slop[i] = self.EPSILON
        self.river_bed_height[0] = self.river_bed_height[1]
        self.river_bed_height[-1] = self.river_bed_height[-2]
        self.cell_sections[0] = self.cell_sections[1]
        self.cell_sections[-1] = self.cell_sections[-2]
        self.water_level[0] = self.water_level[1]
        self.water_level[-1] = self.water_level[-2]
        self.water_depth[0] = self.water_depth[1]
        self.water_depth[-1] = self.water_depth[-2]

    def Caculate_face_U_C(self):
        N = self.cell_num + 1
        if self.fix_06_section_area_threshold:
            cell_limits = np.array([self._get_cell_s_limit(i) for i in range(self.cell_num + 2)], dtype=float)
        else:
            cell_limits = np.full(self.cell_num + 2, self.S_limit, dtype=float)
        sqrt_S = np.sqrt(np.clip(self.S, cell_limits, None))
        left_S = sqrt_S[:N]
        right_S = sqrt_S[1:N + 1]
        left_U = self.U[:N]
        right_U = self.U[1:N + 1]
        self.F_U[:N] = (left_U * left_S + right_U * right_S) / (left_S + right_S)
        diff_S = np.abs(left_S - right_S)
        mask_avg = diff_S <= 0.001
        avg_C = 0.5 * (self.C[:N] + self.C[1:N + 1])
        press_diff = self.PRESS[:N] - self.PRESS[1:N + 1]
        S_diff = self.S[:N] - self.S[1:N + 1]
        ratio = np.zeros(N, dtype=press_diff.dtype)
        np.divide(press_diff, S_diff, out=ratio, where=~mask_avg)
        ratio = np.clip(ratio, a_min=self.EPSILON, a_max=None)
        F_C = np.empty(N, dtype=self.F_C.dtype)
        F_C[mask_avg] = avg_C[mask_avg]
        F_C[~mask_avg] = np.sqrt(ratio[~mask_avg])
        dry_left = self.S[:N] <= cell_limits[:N]
        dry_right = self.S[1:N + 1] <= cell_limits[1:N + 1]
        one_side_dry = dry_left ^ dry_right
        if np.any(one_side_dry):
            wet_is_right = one_side_dry & dry_left
            wet_is_left = one_side_dry & dry_right
            self.F_U[wet_is_right] = right_U[wet_is_right]
            self.F_U[wet_is_left] = left_U[wet_is_left]
            F_C[wet_is_right] = self.C[1:N + 1][wet_is_right]
            F_C[wet_is_left] = self.C[:N][wet_is_left]
        both_dry = dry_left & dry_right
        if np.any(both_dry):
            self.F_U[both_dry] = 0.0
            F_C[both_dry] = self.EPSILON
        self.F_C[:N] = F_C

    def Caculate_source_term_2(self):
        for i in range(self.cell_num + 1):
            if self.FRTIMP or self.friction_model != 'manning':
                self.friction_source[i, 0] = 0
                self.friction_source[i, 1] = 0
            else:
                g = self.g
                sd = self.S[i + 1]
                sg = self.S[i]
                qd = self.Q[i + 1]
                qg = self.Q[i]
                smil = 0.5 * (sg + sd)
                qmil = 0.5 * (qg + qd)
                section_nameg = self.cell_sections[i]
                section_named = self.cell_sections[i + 1]
                debd = self.cross_section_table.get_DEB_by_area(section_named, sd)
                debg = self.cross_section_table.get_DEB_by_area(section_nameg, sg)
                d_avg = 0.5 * (self.water_depth[i] + self.water_depth[i + 1])
                if self.friction_min_depth > 0.0 and d_avg <= self.friction_min_depth:
                    self.friction_source[i, 0] = 0
                    self.friction_source[i, 1] = 0
                    continue
                if np.abs(sd - sg) > 0.001:
                    deb = (debd * (smil - sg) + debg * (sd - smil)) / (sd - sg)
                else:
                    deb = 0.5 * (debd + debg)
                denom = deb * deb
                if denom <= self.EPSILON:
                    self.current_friction_clip_count += 1
                    self.total_friction_clip_count += 1
                    denom = self.EPSILON
                frot = qmil * np.abs(qmil) / denom
                self.friction_source[i, 0] = 0
                self.friction_source[i, 1] = 2 * g * smil * frot

    def Caculate_Roe_matrix(self):
        N = self.cell_num + 1
        eps = self.EPSILON
        Roe_C = self.F_C[:N]
        Roe_U = self.F_U[:N]
        BETA_arr = 0.5 * (self.BETA[:N] + self.BETA[1:N + 1])
        self.flag_LeVeque[:N] = 0
        tmp = BETA_arr * (1 - BETA_arr) * Roe_U ** 2
        Z = np.sqrt(np.maximum(Roe_C ** 2 - tmp, 0))
        Z_safe = Z + self.EPSILON
        Lambda1 = BETA_arr * Roe_U - Z
        Lambda2 = BETA_arr * Roe_U + Z
        FR_L = self.FR[:N]
        FR_R = self.FR[1:N + 1]
        depth_L = self.water_depth[:N]
        depth_R = self.water_depth[1:N + 1]
        if self.fix_05_leveque_wetdry:
            indic = (depth_L > self.water_depth_limit) & (depth_R > self.water_depth_limit)
        else:
            indic = (depth_L > self.water_depth_limit) & (depth_R > self.water_depth_limit)
        mask1 = (FR_R > 1) & (FR_L < 1) & (Roe_U > 0) & indic
        mask2 = (FR_R < 1) & (FR_L > 1) & (Roe_U < 0) & indic
        if np.any(mask1):
            L1D = BETA_arr[mask1] * self.U[:N][mask1] - self.C[:N][mask1]
            L1G = BETA_arr[mask1] * self.U[1:N + 1][mask1] - self.C[1:N + 1][mask1]
            ratio1 = np.zeros_like(L1D)
            np.divide(Lambda1[mask1] - L1D, L1G - L1D, out=ratio1, where=L1G - L1D != 0)
            Lambda1[mask1] = L1G * ratio1
            self.flag_LeVeque[mask1] = 2
        if np.any(mask2):
            L2D = BETA_arr[mask2] * self.U[:N][mask2] + self.C[:N][mask2]
            L2G = BETA_arr[mask2] * self.U[1:N + 1][mask2] + self.C[1:N + 1][mask2]
            ratio2 = np.zeros_like(L2D)
            np.divide(Lambda2[mask2] - L2G, L2D - L2G, out=ratio2, where=L2D - L2G != 0)
            Lambda2[mask2] = L2D * ratio2
            self.flag_LeVeque[mask2] = 1
        self.abs_Lambda1[:N] = np.abs(Lambda1)
        self.abs_Lambda2[:N] = np.abs(Lambda2)
        dS = self.S[1:N + 1] - self.S[:N]
        dQ = self.Q[1:N + 1] - self.Q[:N]
        self.alpha2[:N] = (dQ - dS * (Roe_U - Roe_C)) / (2 * Roe_C + self.EPSILON)
        self.alpha1[:N] = dS - self.alpha2[:N]
        Beta_U = BETA_arr * Roe_U
        self.Vactor1[:N, 0] = 1
        self.Vactor1[:N, 1] = Beta_U - Z
        self.Vactor1_T[:N, 0] = (Beta_U + Z) / (2 * Z_safe)
        self.Vactor1_T[:N, 1] = -1 / (2 * Z_safe)
        self.Vactor2[:N, 0] = 1
        self.Vactor2[:N, 1] = Beta_U + Z
        self.Vactor2_T[:N, 0] = -(Beta_U - Z) / (2 * Z_safe)
        self.Vactor2_T[:N, 1] = 1 / (2 * Z_safe)
        self.Lambda1[:N] = Lambda1
        self.Lambda2[:N] = Lambda2
        wet_iface = (depth_L > self.water_depth_limit) | (depth_R > self.water_depth_limit)
        self.current_interface_counts = {
            'supercritical_pos': int(np.count_nonzero((Roe_U >= Roe_C) & wet_iface)),
            'supercritical_neg': int(np.count_nonzero((Roe_U <= -Roe_C) & wet_iface)),
            'subcritical': int(np.count_nonzero((np.abs(Roe_U) < Roe_C) & wet_iface)),
        }
        self.current_leveque_count = int(np.count_nonzero(self.flag_LeVeque[:N] != 0))
        self.total_leveque_count += self.current_leveque_count
        if N > 0:
            self.lambda_range_current = {
                'lambda1_min': float(np.nanmin(Lambda1)),
                'lambda1_max': float(np.nanmax(Lambda1)),
                'lambda2_min': float(np.nanmin(Lambda2)),
                'lambda2_max': float(np.nanmax(Lambda2)),
            }

    def _rectangular_physical_flux(self, q, u, h):
        return np.array([q, q * u + self._rectangular_pressure(h)], dtype=float)

    def _load_rectangular_interface_center_state(self, i, tiny):
        width = float(self.constant_rectangular_width)
        z_left = float(self.river_bed_height[i])
        z_right = float(self.river_bed_height[i + 1])
        h_left_center = max(float(self.water_depth[i]), 0.0)
        h_right_center = max(float(self.water_depth[i + 1]), 0.0)
        eta_left_center = z_left + h_left_center
        eta_right_center = z_right + h_right_center
        q_left_center = float(self.Q[i])
        q_right_center = float(self.Q[i + 1])
        if h_left_center > tiny and self.S[i] > tiny:
            u_left_center = float(self.Q[i]) / float(self.S[i])
        else:
            u_left_center = 0.0
        if h_right_center > tiny and self.S[i + 1] > tiny:
            u_right_center = float(self.Q[i + 1]) / float(self.S[i + 1])
        else:
            u_right_center = 0.0
        return {
            'width': width,
            'z_left': z_left,
            'z_right': z_right,
            'h_left_center': h_left_center,
            'h_right_center': h_right_center,
            'eta_left_center': eta_left_center,
            'eta_right_center': eta_right_center,
            'q_left_center': q_left_center,
            'q_right_center': q_right_center,
            'u_left_center': u_left_center,
            'u_right_center': u_right_center,
            'h_left': h_left_center,
            'h_right': h_right_center,
            'eta_left': eta_left_center,
            'eta_right': eta_right_center,
            'q_left': q_left_center,
            'q_right': q_right_center,
            'u_left': u_left_center,
            'u_right': u_right_center,
        }

    def _apply_rectangular_interface_limiter(self, i, state):
        limiter_active = False
        limiter_details = None
        sensor_details = self._compute_rectangular_tvd_sensor_core(i)
        sensor_support_hits = 0
        if self.use_explicit_tvd_limiter:
            half_window = int(self.explicit_tvd_sensor_neighbor_half_window)
            for j in range(max(1, i - half_window), min(self.cell_num - 1, i + half_window) + 1):
                if self._compute_rectangular_tvd_sensor_core(j)['shock_sensor_core_active']:
                    sensor_support_hits += 1
        sensor_active = bool(
            sensor_details['shock_sensor_core_active']
            and sensor_support_hits >= int(self.explicit_tvd_sensor_min_neighbor_hits)
        )
        if sensor_active:
            limiter_details = self._reconstruct_rectangular_tvd_states(i, state['z_left'], state['z_right'])
            limiter_active = True
            if self.explicit_tvd_reconstruct_mode in {'eta_q', 'eta_only'}:
                state['eta_left'] = float(limiter_details['eta_left_recon'])
                state['eta_right'] = float(limiter_details['eta_right_recon'])
                state['h_left'] = max(float(limiter_details['h_left_raw_recon']), 0.0)
                state['h_right'] = max(float(limiter_details['h_right_raw_recon']), 0.0)
            if self.explicit_tvd_reconstruct_mode in {'eta_q', 'q_only'}:
                state['q_left'] = float(limiter_details['q_left_recon'])
                state['q_right'] = float(limiter_details['q_right_recon'])
        state['limiter_active'] = bool(limiter_active)
        state['limiter_details'] = limiter_details
        state['sensor_details'] = sensor_details
        state['sensor_support_hits'] = int(sensor_support_hits)
        state['sensor_active'] = bool(sensor_active)
        return state

    def _project_rectangular_hr_face_state(self, state, tiny):
        z_face = max(state['z_left'], state['z_right'])
        h_left_hr = max(0.0, state['eta_left'] - z_face)
        h_right_hr = max(0.0, state['eta_right'] - z_face)
        a_left = state['width'] * h_left_hr
        a_right = state['width'] * h_right_hr
        if state['limiter_active']:
            if a_left > tiny and h_left_hr > tiny:
                state['u_left'] = state['q_left'] / a_left
            else:
                state['q_left'] = 0.0
                state['u_left'] = 0.0
            if a_right > tiny and h_right_hr > tiny:
                state['u_right'] = state['q_right'] / a_right
            else:
                state['q_right'] = 0.0
                state['u_right'] = 0.0
        else:
            state['q_left'] = a_left * state['u_left']
            state['q_right'] = a_right * state['u_right']
        state['z_face'] = z_face
        state['h_left_hr'] = h_left_hr
        state['h_right_hr'] = h_right_hr
        state['a_left_hr'] = a_left
        state['a_right_hr'] = a_right
        return state

    def _solve_rectangular_hr_roe_flux(self, state, tiny):
        branch = "wet_wet"
        u_roe = None
        c_roe = None
        lam1 = None
        lam2 = None
        abs1 = None
        abs2 = None
        alpha1 = None
        alpha2 = None
        a_left = state['a_left_hr']
        a_right = state['a_right_hr']
        h_left_hr = state['h_left_hr']
        h_right_hr = state['h_right_hr']
        q_left = state['q_left']
        q_right = state['q_right']
        u_left = state['u_left']
        u_right = state['u_right']
        width = state['width']
        if a_left <= tiny and a_right <= tiny:
            branch = "dry_dry"
            flux = np.zeros(2, dtype=float)
        elif a_right <= tiny:
            branch = "wet_dry_right"
            c_left = np.sqrt(self.g * max(h_left_hr, 0.0))
            left_flux = self._rectangular_physical_flux(q_left, u_left, h_left_hr)
            if u_left - c_left >= 0.0:
                flux = left_flux
            elif u_left + 2.0 * c_left <= 0.0:
                flux = np.zeros(2, dtype=float)
            else:
                c_star = max((u_left + 2.0 * c_left) / 3.0, 0.0)
                h_star = (c_star * c_star) / self.g
                u_star = c_star
                q_star = width * h_star * u_star
                flux = self._rectangular_physical_flux(q_star, u_star, h_star)
        elif a_left <= tiny:
            branch = "dry_wet_left"
            c_right = np.sqrt(self.g * max(h_right_hr, 0.0))
            right_flux = self._rectangular_physical_flux(q_right, u_right, h_right_hr)
            if u_right + c_right <= 0.0:
                flux = right_flux
            elif u_right - 2.0 * c_right >= 0.0:
                flux = np.zeros(2, dtype=float)
            else:
                c_star = max((2.0 * c_right - u_right) / 3.0, 0.0)
                h_star = (c_star * c_star) / self.g
                u_star = -c_star
                q_star = width * h_star * u_star
                flux = self._rectangular_physical_flux(q_star, u_star, h_star)
        else:
            f_left = self._rectangular_physical_flux(q_left, u_left, h_left_hr)
            f_right = self._rectangular_physical_flux(q_right, u_right, h_right_hr)
            sqrt_hl = np.sqrt(max(h_left_hr, 0.0))
            sqrt_hr = np.sqrt(max(h_right_hr, 0.0))
            denom = sqrt_hl + sqrt_hr
            if denom <= tiny:
                u_roe = 0.0
            else:
                u_roe = (u_left * sqrt_hl + u_right * sqrt_hr) / denom
            c_roe = np.sqrt(self.g * 0.5 * max(h_left_hr + h_right_hr, 0.0))
            if c_roe <= tiny:
                flux = 0.5 * (f_left + f_right)
            else:
                dh = h_right_hr - h_left_hr
                dq = q_right - q_left
                alpha1 = ((u_roe + c_roe) * dh - dq) / (2.0 * c_roe)
                alpha2 = (dq - (u_roe - c_roe) * dh) / (2.0 * c_roe)
                lam1 = u_roe - c_roe
                lam2 = u_roe + c_roe
                abs1 = self._roe_abs_with_fix(lam1, c_roe)
                abs2 = self._roe_abs_with_fix(lam2, c_roe)
                r1 = np.array([1.0, u_roe - c_roe], dtype=float)
                r2 = np.array([1.0, u_roe + c_roe], dtype=float)
                flux = 0.5 * (f_left + f_right) - 0.5 * (abs1 * alpha1 * r1 + abs2 * alpha2 * r2)
        state['branch'] = branch
        state['flux'] = flux
        state['u_roe'] = u_roe
        state['c_roe'] = c_roe
        state['lambda1'] = lam1
        state['lambda2'] = lam2
        state['abs_lambda1'] = abs1
        state['abs_lambda2'] = abs2
        state['alpha1'] = alpha1
        state['alpha2'] = alpha2
        return state

    def _apply_rectangular_flux_positivity_control(self, i, state, tiny):
        flux = state['flux']
        # 矩形 HR 通量本身按 FullSWOF 风格做了干湿/真空处理，
        # 再叠加 donor-cell 质量限流会明显拖慢前沿。
        if (not self.use_rectangular_hr_flux) and self.positivity_flux_control and abs(flux[0]) > tiny and self.DT > 0.0:
            donor = None
            if flux[0] > 0.0 and 1 <= i <= self.cell_num:
                donor = i
            elif flux[0] < 0.0 and 1 <= i + 1 <= self.cell_num:
                donor = i + 1
            if donor is not None:
                available = max(float(self.S[donor]), 0.0) * max(float(self.cell_lengths[donor]), tiny)
                max_flux = available / max(float(self.DT), tiny)
                if max_flux < abs(flux[0]):
                    scale = max_flux / max(abs(flux[0]), tiny)
                    flux = flux * scale
        state['flux'] = flux
        return state

    def _build_rectangular_hr_interface_details(self, i, state, corr_left, corr_right):
        x_left = float(self.cell_pos[i][0])
        x_right = float(self.cell_pos[i + 1][0])
        dx_face = max(float(abs(x_right - x_left)), self.EPSILON)
        details = {
            'iface_index': int(i),
            'branch': state['branch'],
            'x_left': x_left,
            'x_right': x_right,
            'x_face': 0.5 * (x_left + x_right),
            'dx_face': dx_face,
            'z_left': state['z_left'],
            'z_right': state['z_right'],
            'z_face': state['z_face'],
            'bed_slope': (state['z_right'] - state['z_left']) / dx_face,
            'limiter_active': bool(state['limiter_active']),
            'limiter_name': self.explicit_tvd_limiter_type if state['limiter_active'] else None,
            'limiter_mode': self.explicit_tvd_reconstruct_mode if state['limiter_active'] else None,
            'shock_sensor_active': bool(state['sensor_active']),
            'shock_sensor_neighbor_hits': int(state['sensor_support_hits']),
            'shock_sensor_min_neighbor_hits': int(self.explicit_tvd_sensor_min_neighbor_hits),
            'h_left_center': state['h_left_center'],
            'h_right_center': state['h_right_center'],
            'eta_left_center': state['eta_left_center'],
            'eta_right_center': state['eta_right_center'],
            'q_left_center': state['q_left_center'],
            'q_right_center': state['q_right_center'],
            'u_left_center': state['u_left_center'],
            'u_right_center': state['u_right_center'],
            'h_left_raw': state['h_left'],
            'h_right_raw': state['h_right'],
            'eta_left': state['eta_left'],
            'eta_right': state['eta_right'],
            'h_left_hr': state['h_left_hr'],
            'h_right_hr': state['h_right_hr'],
            'a_left_hr': state['a_left_hr'],
            'a_right_hr': state['a_right_hr'],
            'u_left': state['u_left'],
            'u_right': state['u_right'],
            'q_left': state['q_left'],
            'q_right': state['q_right'],
            'pressure_left_raw': self._rectangular_pressure(state['h_left']),
            'pressure_right_raw': self._rectangular_pressure(state['h_right']),
            'pressure_left_hr': self._rectangular_pressure(state['h_left_hr']),
            'pressure_right_hr': self._rectangular_pressure(state['h_right_hr']),
            'corr_left': corr_left,
            'corr_right': corr_right,
            'u_roe': None if state['u_roe'] is None else float(state['u_roe']),
            'c_roe': None if state['c_roe'] is None else float(state['c_roe']),
            'lambda1': None if state['lambda1'] is None else float(state['lambda1']),
            'lambda2': None if state['lambda2'] is None else float(state['lambda2']),
            'abs_lambda1': None if state['abs_lambda1'] is None else float(state['abs_lambda1']),
            'abs_lambda2': None if state['abs_lambda2'] is None else float(state['abs_lambda2']),
            'alpha1': None if state['alpha1'] is None else float(state['alpha1']),
            'alpha2': None if state['alpha2'] is None else float(state['alpha2']),
            'flux_mass': float(state['flux'][0]),
            'flux_momentum': float(state['flux'][1]),
        }
        details.update(state['sensor_details'])
        limiter_details = state['limiter_details']
        if limiter_details is None:
            details.update(
                {
                    'eta_left_recon': None,
                    'eta_right_recon': None,
                    'q_left_recon': None,
                    'q_right_recon': None,
                    'r_eta_left': None,
                    'r_eta_right': None,
                    'r_q_left': None,
                    'r_q_right': None,
                    'phi_eta_left': None,
                    'phi_eta_right': None,
                    'phi_q_left': None,
                    'phi_q_right': None,
                }
            )
        else:
            details.update(limiter_details)
        return details

    def Caculate_impli_trans_coefficient(self):
        for i in range(self.cell_num + 1):
            X1 = self.Vactor1[i, 0] * self.Vactor1_T[i, 0]
            Y1 = self.Vactor2[i, 0] * self.Vactor2_T[i, 0]
            X2 = self.Vactor1[i, 0] * self.Vactor1_T[i, 1]
            Y2 = self.Vactor2[i, 0] * self.Vactor2_T[i, 1]
            X3 = self.Vactor1[i, 1] * self.Vactor1_T[i, 0]
            Y3 = self.Vactor2[i, 1] * self.Vactor2_T[i, 0]
            X4 = self.Vactor1[i, 1] * self.Vactor1_T[i, 1]
            Y4 = self.Vactor2[i, 1] * self.Vactor2_T[i, 1]
            VAB1 = np.abs(self.Lambda1[i])
            VAB2 = np.abs(self.Lambda2[i])
            self.D[i, 0] = VAB1 * X1 + VAB2 * Y1
            self.D[i, 1] = VAB1 * X2 + VAB2 * Y2
            self.D[i, 2] = VAB1 * X3 + VAB2 * Y3
            self.D[i, 3] = VAB1 * X4 + VAB2 * Y4
            self.ID[i, 0] = 1
            self.ID[i, 1] = 0
            self.ID[i, 2] = 0
            self.ID[i, 3] = 1
        for i in range(self.cell_num + 2):
            UG = self.U[i]
            CG = self.C[i]
            BETA = self.BETA[i]
            self.Lambda1I[i] = BETA * UG - np.sqrt(CG ** 2 - BETA * (1 - BETA) * UG ** 2)
            self.Lambda2I[i] = BETA * UG + np.sqrt(CG ** 2 - BETA * (1 - BETA) * UG ** 2)
            UG1 = BETA * UG
            CG1 = np.sqrt(CG ** 2 - BETA * (1 - BETA) * UG ** 2)
            self.Vactor1I[i, 0] = 1
            self.Vactor1I[i, 1] = UG1 - CG1
            self.Vactor1I_T[i, 0] = (UG1 + CG1) / (2 * CG1)
            self.Vactor1I_T[i, 1] = -1 / (2 * CG1)
            self.Vactor2I[i, 0] = 1
            self.Vactor2I[i, 1] = UG1 + CG1
            self.Vactor2I_T[i, 0] = -(UG1 - CG1) / (2 * CG1)
            self.Vactor2I_T[i, 1] = 1 / (2 * CG1)
        for i in range(self.cell_num + 2):
            X1 = self.Vactor1I[i, 0] * self.Vactor1I_T[i, 0]
            Y1 = self.Vactor2I[i, 0] * self.Vactor2I_T[i, 0]
            X2 = self.Vactor1I[i, 0] * self.Vactor1I_T[i, 1]
            Y2 = self.Vactor2I[i, 0] * self.Vactor2I_T[i, 1]
            X3 = self.Vactor1I[i, 1] * self.Vactor1I_T[i, 0]
            Y3 = self.Vactor2I[i, 1] * self.Vactor2I_T[i, 0]
            X4 = self.Vactor1I[i, 1] * self.Vactor1I_T[i, 1]
            Y4 = self.Vactor2I[i, 1] * self.Vactor2I_T[i, 1]
            self.A[i, 0] = self.Lambda1I[i] * X1 + self.Lambda2I[i] * Y1
            self.A[i, 1] = self.Lambda1I[i] * X2 + self.Lambda2I[i] * Y2
            self.A[i, 2] = self.Lambda1I[i] * X3 + self.Lambda2I[i] * Y3
            self.A[i, 3] = self.Lambda1I[i] * X4 + self.Lambda2I[i] * Y4

    def _compute_rectangular_hr_interface_flux(self, i, return_details=False):
        tiny = max(self.S_limit, self.EPSILON)
        state = self._load_rectangular_interface_center_state(i, tiny)
        state = self._apply_rectangular_interface_limiter(i, state)
        state = self._project_rectangular_hr_face_state(state, tiny)
        state = self._solve_rectangular_hr_roe_flux(state, tiny)
        state = self._apply_rectangular_flux_positivity_control(i, state, tiny)
        corr_left = self._rectangular_pressure(state['h_left']) - self._rectangular_pressure(state['h_left_hr'])
        corr_right = self._rectangular_pressure(state['h_right']) - self._rectangular_pressure(state['h_right_hr'])
        if not return_details:
            return state['flux'], corr_left, corr_right
        details = self._build_rectangular_hr_interface_details(i, state, corr_left, corr_right)
        return state['flux'], corr_left, corr_right, details

    def _general_physical_flux(self, q, u, press):
        return np.array([q, q * u + press], dtype=float)

    def _load_general_interface_center_state(self, i, tiny):
        sec_left = self.cell_sections[i]
        sec_right = self.cell_sections[i + 1]
        z_left = float(self.river_bed_height[i])
        z_right = float(self.river_bed_height[i + 1])
        h_left = max(float(self.water_depth[i]), 0.0)
        h_right = max(float(self.water_depth[i + 1]), 0.0)
        eta_left = z_left + h_left
        eta_right = z_right + h_right
        if self.S[i] > tiny and h_left > tiny:
            u_left = float(self.Q[i]) / max(float(self.S[i]), tiny)
        else:
            u_left = 0.0
        if self.S[i + 1] > tiny and h_right > tiny:
            u_right = float(self.Q[i + 1]) / max(float(self.S[i + 1]), tiny)
        else:
            u_right = 0.0
        return {
            'sec_left': sec_left,
            'sec_right': sec_right,
            'z_left': z_left,
            'z_right': z_right,
            'h_left': h_left,
            'h_right': h_right,
            'eta_left': eta_left,
            'eta_right': eta_right,
            'u_left': u_left,
            'u_right': u_right,
            'area_left_center': float(self.S[i]),
            'area_right_center': float(self.S[i + 1]),
            'q_left_center': float(self.Q[i]),
            'q_right_center': float(self.Q[i + 1]),
            'press_left_center': float(self.PRESS[i]),
            'press_right_center': float(self.PRESS[i + 1]),
        }

    def _project_general_hr_face_state(self, state):
        z_face = max(state['z_left'], state['z_right'])
        h_left_hr = max(0.0, state['eta_left'] - z_face)
        h_right_hr = max(0.0, state['eta_right'] - z_face)
        a_left = float(self.cross_section_table.get_area_by_depth(state['sec_left'], h_left_hr))
        a_right = float(self.cross_section_table.get_area_by_depth(state['sec_right'], h_right_hr))
        p_left_hr = float(self.cross_section_table.get_press_by_area(state['sec_left'], a_left))
        p_right_hr = float(self.cross_section_table.get_press_by_area(state['sec_right'], a_right))
        q_left = a_left * state['u_left']
        q_right = a_right * state['u_right']
        state['z_face'] = z_face
        state['h_left_hr'] = h_left_hr
        state['h_right_hr'] = h_right_hr
        state['a_left_hr'] = a_left
        state['a_right_hr'] = a_right
        state['p_left_hr'] = p_left_hr
        state['p_right_hr'] = p_right_hr
        state['q_left'] = q_left
        state['q_right'] = q_right
        state['f_left'] = self._general_physical_flux(q_left, state['u_left'], p_left_hr)
        state['f_right'] = self._general_physical_flux(q_right, state['u_right'], p_right_hr)
        return state

    def _solve_general_hr_roe_flux(self, state, tiny):
        a_left = state['a_left_hr']
        a_right = state['a_right_hr']
        q_left = state['q_left']
        q_right = state['q_right']
        u_left = state['u_left']
        u_right = state['u_right']
        f_left = state['f_left']
        f_right = state['f_right']
        p_left_hr = state['p_left_hr']
        p_right_hr = state['p_right_hr']
        branch = 'wet_wet'
        u_roe = None
        c_roe = None
        lam1 = None
        lam2 = None
        abs1 = None
        abs2 = None
        alpha1 = None
        alpha2 = None
        s_left = None
        s_right = None
        c_left = 0.0
        c_right = 0.0
        t_left = None
        t_right = None
        if a_left <= tiny and a_right <= tiny:
            branch = 'dry_dry'
            flux = np.zeros(2, dtype=float)
        else:
            t_left = float(self.cross_section_table.get_width_by_area(state['sec_left'], max(a_left, tiny)))
            t_right = float(self.cross_section_table.get_width_by_area(state['sec_right'], max(a_right, tiny)))
            t_left = max(t_left, tiny)
            t_right = max(t_right, tiny)
            c_left = np.sqrt(max(self.g * a_left / t_left, 0.0)) if a_left > tiny else 0.0
            c_right = np.sqrt(max(self.g * a_right / t_right, 0.0)) if a_right > tiny else 0.0
            s_left = min(u_left - c_left, u_right - c_right)
            s_right = max(u_left + c_left, u_right + c_right)

            if a_left > tiny and a_right > tiny:
                sqrt_al = np.sqrt(max(a_left, 0.0))
                sqrt_ar = np.sqrt(max(a_right, 0.0))
                denom = sqrt_al + sqrt_ar
                if denom <= tiny:
                    u_roe = 0.0
                else:
                    u_roe = (u_left * sqrt_al + u_right * sqrt_ar) / denom
                if abs(a_right - a_left) > tiny:
                    c_roe = np.sqrt(max((p_right_hr - p_left_hr) / (a_right - a_left), 0.0))
                else:
                    c_roe = 0.5 * (c_left + c_right)
                if c_roe <= tiny:
                    flux = 0.5 * (f_left + f_right)
                else:
                    da = a_right - a_left
                    dq = q_right - q_left
                    alpha1 = ((u_roe + c_roe) * da - dq) / (2.0 * c_roe)
                    alpha2 = (dq - (u_roe - c_roe) * da) / (2.0 * c_roe)
                    lam1 = u_roe - c_roe
                    lam2 = u_roe + c_roe
                    abs1 = self._roe_abs_with_fix(lam1, c_roe)
                    abs2 = self._roe_abs_with_fix(lam2, c_roe)
                    r1 = np.array([1.0, u_roe - c_roe], dtype=float)
                    r2 = np.array([1.0, u_roe + c_roe], dtype=float)
                    flux = 0.5 * (f_left + f_right) - 0.5 * (abs1 * alpha1 * r1 + abs2 * alpha2 * r2)
            elif s_left >= 0.0:
                branch = 'left_upwind'
                flux = f_left
            elif s_right <= 0.0:
                branch = 'right_upwind'
                flux = f_right
            elif s_right - s_left <= tiny:
                branch = 'degenerate_hll'
                flux = np.zeros(2, dtype=float)
            else:
                branch = 'hll_transition'
                u_left_vec = np.array([a_left, q_left], dtype=float)
                u_right_vec = np.array([a_right, q_right], dtype=float)
                flux = (s_right * f_left - s_left * f_right + s_left * s_right * (u_right_vec - u_left_vec)) / (s_right - s_left)
        state['branch'] = branch
        state['flux'] = flux
        state['t_left'] = t_left
        state['t_right'] = t_right
        state['c_left'] = c_left
        state['c_right'] = c_right
        state['s_left'] = s_left
        state['s_right'] = s_right
        state['u_roe'] = u_roe
        state['c_roe'] = c_roe
        state['lambda1'] = lam1
        state['lambda2'] = lam2
        state['abs_lambda1'] = abs1
        state['abs_lambda2'] = abs2
        state['alpha1'] = alpha1
        state['alpha2'] = alpha2
        return state

    def _apply_general_flux_positivity_control(self, i, state, tiny):
        flux = state['flux']
        if self.positivity_flux_control and abs(flux[0]) > tiny and self.DT > 0.0:
            donor = None
            if flux[0] > 0.0 and 1 <= i <= self.cell_num:
                donor = i
            elif flux[0] < 0.0 and 1 <= i + 1 <= self.cell_num:
                donor = i + 1
            if donor is not None:
                available = max(float(self.S[donor]), 0.0) * max(float(self.cell_lengths[donor]), tiny)
                max_flux = available / max(float(self.DT), tiny)
                if max_flux < abs(flux[0]):
                    scale = max_flux / max(abs(flux[0]), tiny)
                    flux = flux * scale
        state['flux'] = flux
        return state

    def _build_general_hr_interface_details(self, i, state, corr_left, corr_right):
        return {
            'interface_index': int(i),
            'sec_left': state['sec_left'],
            'sec_right': state['sec_right'],
            'branch': state['branch'],
            'z_left': state['z_left'],
            'z_right': state['z_right'],
            'z_face': state['z_face'],
            'h_left_center': state['h_left'],
            'h_right_center': state['h_right'],
            'eta_left_center': state['eta_left'],
            'eta_right_center': state['eta_right'],
            'area_left_center': state['area_left_center'],
            'area_right_center': state['area_right_center'],
            'press_left_center': state['press_left_center'],
            'press_right_center': state['press_right_center'],
            'u_left_center': state['u_left'],
            'u_right_center': state['u_right'],
            'h_left_hr': state['h_left_hr'],
            'h_right_hr': state['h_right_hr'],
            'area_left_hr': state['a_left_hr'],
            'area_right_hr': state['a_right_hr'],
            'press_left_hr': state['p_left_hr'],
            'press_right_hr': state['p_right_hr'],
            'width_left_hr': state['t_left'],
            'width_right_hr': state['t_right'],
            'c_left': state['c_left'],
            'c_right': state['c_right'],
            's_left': state['s_left'],
            's_right': state['s_right'],
            'u_roe': state['u_roe'],
            'c_roe': state['c_roe'],
            'lambda1': state['lambda1'],
            'lambda2': state['lambda2'],
            'abs_lambda1': state['abs_lambda1'],
            'abs_lambda2': state['abs_lambda2'],
            'alpha1': state['alpha1'],
            'alpha2': state['alpha2'],
            'q_left_hr': state['q_left'],
            'q_right_hr': state['q_right'],
            'flux_mass': float(state['flux'][0]),
            'flux_momentum': float(state['flux'][1]),
            'corr_left': float(corr_left),
            'corr_right': float(corr_right),
        }

    def _compute_general_hr_interface_flux(self, i, return_details=False):
        tiny = max(self.S_limit, self.EPSILON)
        state = self._load_general_interface_center_state(i, tiny)
        state = self._project_general_hr_face_state(state)
        state = self._solve_general_hr_roe_flux(state, tiny)
        state = self._apply_general_flux_positivity_control(i, state, tiny)
        corr_left = state['press_left_center'] - state['p_left_hr']
        corr_right = state['press_right_center'] - state['p_right_hr']
        if not return_details:
            return state['flux'], corr_left, corr_right
        details = self._build_general_hr_interface_details(i, state, corr_left, corr_right)
        return state['flux'], corr_left, corr_right, details

    def _caculate_roe_flux_rectangular_hr(self):
        self.Flux_LOC.fill(0.0)
        self.Flux_Source_left.fill(0.0)
        self.Flux_Source_right.fill(0.0)
        self.Flux_Source_center.fill(0.0)
        self.Flux_Friction_left.fill(0.0)
        self.Flux_Friction_right.fill(0.0)
        self.cell_press_source.fill(0.0)
        for i in range(self.cell_num + 1):
            flux, corr_left, corr_right = self._compute_rectangular_hr_interface_flux(i)
            self.Flux_LOC[i, :] = flux
            self.Flux_Source_right[i, 1] = corr_left
            self.Flux_Source_left[i + 1, 1] = -corr_right
        for j in range(1, self.cell_num + 1):
            if abs(float(self.QIN[j])) > 0.0:
                rain_half = -0.5 * float(self.cell_lengths[j]) * float(self.QIN[j])
                self.Flux_Source_left[j, 0] += rain_half
                self.Flux_Source_right[j, 0] += rain_half

    def _caculate_roe_flux_general_hr(self):
        self.Flux_LOC.fill(0.0)
        self.Flux_Source_left.fill(0.0)
        self.Flux_Source_right.fill(0.0)
        self.Flux_Source_center.fill(0.0)
        self.Flux_Friction_left.fill(0.0)
        self.Flux_Friction_right.fill(0.0)
        self.cell_press_source.fill(0.0)
        for i in range(self.cell_num + 1):
            flux, corr_left, corr_right = self._compute_general_hr_interface_flux(i)
            self.Flux_LOC[i, :] = flux
            self.Flux_Source_right[i, 1] = corr_left
            self.Flux_Source_left[i + 1, 1] = -corr_right
        for j in range(1, self.cell_num + 1):
            if abs(float(self.QIN[j])) > 0.0:
                rain_half = -0.5 * float(self.cell_lengths[j]) * float(self.QIN[j])
                self.Flux_Source_left[j, 0] += rain_half
                self.Flux_Source_right[j, 0] += rain_half

    def Caculate_Roe_Flux_2(self):
        if self.use_rectangular_hr_flux and self.constant_rectangular_width is not None:
            self._caculate_roe_flux_rectangular_hr()
            return
        if self.use_general_hr_flux:
            self._caculate_roe_flux_general_hr()
            return
        for i in range(self.cell_num + 1):
            self.Flux_LOC[i, 0] = 0
            self.Flux_LOC[i, 1] = 0
            self.Flux_Source_right[i, 0] = 0
            self.Flux_Source_right[i, 1] = 0
            self.Flux_Source_left[i + 1, 0] = 0
            self.Flux_Source_left[i + 1, 1] = 0
            self.Flux_Friction_right[i, 0] = 0
            self.Flux_Friction_right[i, 1] = 0
            self.Flux_Friction_left[i + 1, 0] = 0
            self.Flux_Friction_left[i + 1, 1] = 0
            PROD = self.Lambda1[i] * self.Lambda2[i]
            SAUTS = self.S[i + 1] - self.S[i]
            SAUTQ = self.Q[i + 1] - self.Q[i]
            right_water_depth = self.water_depth[i] + self.river_bed_height[i] - self.river_bed_height[i + 1]
            left_water_depth = self.water_depth[i + 1] + self.river_bed_height[i + 1] - self.river_bed_height[i]
            if right_water_depth < self.water_depth_limit:
                right_wetted_area = 0.0
            else:
                right_wetted_area = self.cross_section_table.get_area_by_depth(self.cell_sections[i + 1], right_water_depth)
            if left_water_depth < self.water_depth_limit:
                left_wetted_area = 0.0
            else:
                left_wetted_area = self.cross_section_table.get_area_by_depth(self.cell_sections[i], left_water_depth)
            z = 2 / self.cell_lengths[i]
            if left_water_depth < 0:
                DsDx = z * (right_wetted_area - self.S[i])
            elif right_water_depth < 0:
                DsDx = z * (self.S[i + 1] - left_wetted_area)
            else:
                DsDx = z * (self.S[i + 1] + right_wetted_area - self.S[i] - left_wetted_area) / 2
            self.cell_press_source[i, 0] = 0
            self.cell_press_source[i, 1] = self.PRESS[i + 1] - self.PRESS[i]
            sotild1 = -2 * self.QIN[i + 1]
            sotild2 = -DsDx * self.F_C[i] * self.F_C[i]
            sofrot1 = self.friction_source[i, 0]
            sofrot2 = self.friction_source[i, 1]
            a = 0.5 * self.cell_lengths[i]
            # 避免在浅水/干单元下出现 Q^2/S 数值发散
            s_limit_i = self._get_cell_s_limit(i)
            s_limit_ip1 = self._get_cell_s_limit(i + 1)
            s_i = self.S[i] if self.S[i] > s_limit_i else s_limit_i
            s_ip1 = self.S[i + 1] if self.S[i + 1] > s_limit_ip1 else s_limit_ip1
            if PROD > 0:
                if self.F_U[i] > 0:
                    if self.water_depth[i] < self.water_depth_limit:
                        PSFLU1 = self.Vactor1_T[i, 0] * SAUTS + self.Vactor1_T[i, 1] * SAUTQ
                        PSFLU2 = self.Vactor2_T[i, 0] * SAUTS + self.Vactor2_T[i, 1] * SAUTQ
                        self.Flux_LOC[i, 0] = self.Q[i + 1] - (self.Vactor1[i, 0] * self.Lambda1[i] * PSFLU1 + self.Vactor2[i, 0] * self.Lambda2[i] * PSFLU2)
                        self.Flux_LOC[i, 1] = self.BETA[i + 1] * self.Q[i + 1] * self.Q[i + 1] / s_ip1 + self.PRESS[i + 1] - (self.Vactor1[i, 1] * self.Lambda1[i] * PSFLU1 + self.Vactor2[i, 1] * self.Lambda2[i] * PSFLU2)
                        self.Flux_Source_right[i, 0] = 0
                        self.Flux_Source_right[i, 1] = 0
                        self.Flux_Source_left[i + 1, 0] = a * sotild1
                        self.Flux_Source_left[i + 1, 1] = a * sotild2
                        self.Flux_Friction_right[i, 0] = 0
                        self.Flux_Friction_right[i, 1] = 0
                        self.Flux_Friction_left[i + 1, 0] = a * sofrot1
                        self.Flux_Friction_left[i + 1, 1] = a * sofrot2
                    else:
                        self.Flux_LOC[i, 0] = self.Q[i]
                        self.Flux_LOC[i, 1] = self.BETA[i] * self.Q[i] * self.Q[i] / s_i + self.PRESS[i]
                        self.Flux_Source_right[i, 0] = a * sotild1
                        self.Flux_Source_right[i, 1] = a * sotild2
                        self.Flux_Source_left[i + 1, 0] = 0
                        self.Flux_Source_left[i + 1, 1] = 0
                        self.Flux_Friction_right[i, 0] = a * sofrot1
                        self.Flux_Friction_right[i, 1] = a * sofrot2
                        self.Flux_Friction_left[i + 1, 0] = 0
                        self.Flux_Friction_left[i + 1, 1] = 0
                else:
                    self.Flux_LOC[i, 0] = self.Q[i + 1]
                    self.Flux_LOC[i, 1] = self.BETA[i + 1] * self.Q[i + 1] * self.Q[i + 1] / s_ip1 + self.PRESS[i + 1]
            elif self.flag_LeVeque[i] == 1 or self.water_depth[i] <= self.EPSILON:
                PSFLU = self.Vactor2_T[i, 0] * SAUTS + self.Vactor2_T[i, 1] * SAUTQ
                self.Flux_LOC[i, 0] = self.Q[i + 1] - self.Lambda2[i] * PSFLU * self.Vactor2[i, 0]
                self.Flux_LOC[i, 1] = self.BETA[i + 1] * self.Q[i + 1] * self.Q[i + 1] / s_ip1 + self.PRESS[i + 1] - self.Lambda2[i] * PSFLU * self.Vactor2[i, 1]
            else:
                PSFLU = self.Vactor1_T[i, 0] * SAUTS + self.Vactor1_T[i, 1] * SAUTQ
                self.Flux_LOC[i, 0] = self.Q[i] + self.Lambda1[i] * PSFLU * self.Vactor1[i, 0]
                self.Flux_LOC[i, 1] = self.BETA[i] * self.Q[i] * self.Q[i] / s_i + self.PRESS[i] + self.Lambda1[i] * PSFLU * self.Vactor1[i, 1]
                PSSOD = a * (self.Vactor1_T[i, 0] * sotild1 + self.Vactor1_T[i, 1] * sotild2)
                self.Flux_Source_right[i, 0] = self.Vactor1[i, 0] * PSSOD
                self.Flux_Source_right[i, 1] = self.Vactor1[i, 1] * PSSOD
                PSSOG = a * (self.Vactor2_T[i, 0] * sotild1 + self.Vactor2_T[i, 1] * sotild2)
                self.Flux_Source_left[i + 1, 0] = self.Vactor2[i, 0] * PSSOG
                self.Flux_Source_left[i + 1, 1] = self.Vactor2[i, 1] * PSSOG
                PSFRD = a * (self.Vactor1_T[i, 0] * sofrot1 + self.Vactor1_T[i, 1] * sofrot2)
                self.Flux_Friction_right[i, 0] = self.Vactor1[i, 0] * PSFRD
                self.Flux_Friction_right[i, 1] = self.Vactor1[i, 1] * PSFRD
                PSFRG = a * (self.Vactor2_T[i, 0] * sofrot1 + self.Vactor2_T[i, 1] * sofrot2)
                self.Flux_Friction_left[i + 1, 0] = self.Vactor2[i, 0] * PSFRG
                self.Flux_Friction_left[i + 1, 1] = self.Vactor2[i, 1] * PSFRG
            self.Flux_Source_center[i, 0] = self.cell_press_source[i, 0]
            self.Flux_Source_center[i, 1] = self.cell_press_source[i, 1]
            if not np.isfinite(self.Flux_LOC[i, 0]):
                self.Flux_LOC[i, 0] = 0.0
            if not np.isfinite(self.Flux_LOC[i, 1]):
                self.Flux_LOC[i, 1] = 0.0

    def Caculate_dam(self):
        pass

    def Assemble_Flux_2(self):
        # Conservative owner only: apply explicit flux increment, friction substep,
        # and post-update dry admissibility on S/Q. Final derived-state refresh is
        # intentionally delegated to Update_cell_proprity2() / _refresh_cell_state().
        self._apply_explicit_conservative_increment()
        self._apply_explicit_friction_substep()
        self._enforce_explicit_conservative_admissibility()

    def Assemble_Flux_impli_trans(self):
        self.S_old[1:-1] = self.S[1:-1].copy()
        self.Q_old[1:-1] = self.Q[1:-1].copy()
        L = np.zeros((4, self.cell_num + 2))
        M = np.zeros_like(L)
        N = np.zeros_like(L)
        WW1 = np.zeros((2, self.cell_num + 2))
        A = self.A
        D = self.D
        ID = self.ID
        DT = self.DT
        for i in range(1, self.cell_num + 1):
            self.Flux[i, 0] = self.Flux_LOC[i, 0] - self.Flux_LOC[i - 1, 0] + self.Flux_Source_right[i, 0] + self.Flux_Source_left[i, 0] + self.Flux_Friction_left[i, 0] + self.Flux_Friction_right[i, 0]
            self.Flux[i, 1] = self.Flux_LOC[i, 1] - self.Flux_LOC[i - 1, 1] + self.Flux_Source_center[i, 1] + self.Flux_Source_right[i, 1] + self.Flux_Source_left[i, 1] + self.Flux_Friction_left[i, 1] + self.Flux_Friction_right[i, 1]
            k = i
            dx_2 = self.cell_lengths[i + 1] + self.cell_lengths[i - 1]
            for j in range(4):
                L[j, k] = -(A[i - 1, j] + D[i - 1, j]) * DT / dx_2
                M[j, k] = ID[i, j] + (D[i - 1, j] + D[i, j]) * DT / dx_2
                N[j, k] = (A[i + 1, j] - D[i, j]) * DT / dx_2
        NC = self.cell_num + 1
        for j in range(4):
            L[j, 0] = 0
            N[j, 0] = 0
            L[j, NC] = 0
            N[j, NC] = 0
        M[0, 0] = 1
        M[1, 0] = 0
        M[2, 0] = 0
        M[3, 0] = 1
        M[0, NC] = 1
        M[1, NC] = 0
        M[2, NC] = 0
        M[3, NC] = 1
        for i in range(1, self.cell_num + 1):
            k = i
            dx_2 = self.cell_lengths[i + 1] + self.cell_lengths[i - 1]
            WW1[0, k] = -self.Flux[i, 0] * 2 * DT / dx_2
            WW1[1, k] = -self.Flux[i, 1] * 2 * DT / dx_2
        WW1[0, 0] = self.V0[0]
        WW1[1, 0] = self.V0[1]
        WW1[0, NC] = self.V1[0]
        WW1[1, NC] = self.V1[1]
        WW2 = self.bissn(WW1, L, M, N, NC)
        for i in range(1, self.cell_num + 1):
            k = i
            self.S[i] = self.S_old[i] + WW2[0, k]
            self.Q[i] = self.Q_old[i] + WW2[1, k]
            if np.abs(self.S[i]) < self.EPSILON:
                self.S[i] = self.EPSILON
            if self.S[i] < 0:
                import warnings
                print('网格位置', i)
                print('时间步长', self.DT)
                print('过水面积', self.S[i])
                print('上一时间步过水面积', self.S_old[i])
                print('叠加参数', WW2[0, i])
                print('计算通量', self.Flux[i, 0])
                self.S[i] = self.EPSILON
                warnings.simplefilter('always', RuntimeWarning)
                warnings.warn('计算过水面积小于零，已重置为最小值')
                print(' ')
            self.U[i] = self.Q[i] / self.S[i]
            water_surface_width = self.cross_section_table.get_width_by_area(self.cell_sections[i], self.S[i])
            depth_i = self.cross_section_table.get_depth_by_area(self.cell_sections[i], max(self.S[i], 0.0))
            prev_s = float(self.S[i])
            prev_depth = float(self.water_depth[i])
            if self._is_cell_dry(i, area=self.S[i], depth=depth_i):
                self._record_forced_dry(i, prev_s=prev_s, prev_depth=prev_depth)
                self.S[i] = 0.0
                self.Q[i] = 0.0
                self.U[i] = 0.0
                self.C[i] = self.EPSILON
                self.FR[i] = 0.0
                continue
            if depth_i <= self.velocity_depth_limit:
                self.Q[i] = 0.0
                self.U[i] = 0.0
            if water_surface_width > self.EPSILON and self.S[i] > self.EPSILON and depth_i > self.velocity_depth_limit:
                self.C[i] = np.sqrt(self.g * self.S[i] / water_surface_width)
                self.FR[i] = np.abs(self.U[i]) / self.C[i]
            else:
                self.C[i] = self.EPSILON
                self.FR[i] = 0.0
        tail = self.cell_num
        self.last_old_state_tail = {
            'cell_index': int(tail),
            'S_old': float(self.S_old[tail]),
            'S_new': float(self.S[tail]),
            'Q_old': float(self.Q_old[tail]),
            'Q_new': float(self.Q[tail]),
        }

    def bissn(self, X, A, B, C, KM):
        KM = KM + 1
        n = X.shape[0]
        if A.shape != (n * n, KM) or B.shape != (n * n, KM) or C.shape != (n * n, KM):
            print(f'A的形状是{A.shape}')
            print(f'B的形状是{B.shape}')
            print(f'C的形状是{C.shape}')
            raise ValueError(f'A,B,C 必须是 ({n * n}, {KM}) 形状')
        blocks = [[None] * KM for _ in range(KM)]
        for k in range(KM):
            blocks[k][k] = B[:, k].reshape((n, n))
            if k > 0:
                blocks[k][k - 1] = A[:, k].reshape((n, n))
            if k < KM - 1:
                blocks[k][k + 1] = C[:, k].reshape((n, n))
        M = bmat(blocks, format='csc')
        rhs = X.reshape((n * KM,))
        sol = spsolve(M, rhs)
        Xsol = sol.reshape((n, KM))
        return Xsol

    def _update_cfl_dt(self, used_dt=None, advance_time=True):
        if used_dt is None:
            used_dt = float(self.DT)
        else:
            used_dt = float(used_dt)
        self.DT_old = self.DT
        DT_limit = self.DT_old + 10
        i0 = 0
        i1 = self.cell_num + 2
        U_slice = self.U[i0:i1]
        C_slice = self.C[i0:i1]
        L_slice = self.cell_lengths[i0:i1]
        diff1 = np.abs(U_slice - C_slice)
        diff2 = np.abs(U_slice + C_slice)
        CNODE = np.maximum(diff1, diff2)
        CNODE = np.clip(CNODE, 0.001, None)
        COU = CNODE / L_slice
        self.DTI[i0:i1] = self.CFL / COU
        dt_min = self.DTI[i0:i1].min()
        self.DT = min(DT_limit, dt_min)
        if self.DT < self.min_dt:
            self.DT = self.min_dt
        self.DT = np.minimum(self.DT, self.DT_old * self.DT_increase_factor)
        self.DT = np.minimum(self.DT, self.Max_time_step)
        if advance_time:
            # 时间推进按“本步实际使用时间步”累计，而非下一步预测时间步
            self.current_sim_time += used_dt

    def Caculate_CFL_time(self):
        self._update_cfl_dt(used_dt=self.DT, advance_time=True)

    def get_current_dt(self):
        print(f'河道{self.name}当前时间步长为：{self.DT}')

    def set_next_dt(self, next_dt):
        if next_dt > 0:
            self.DT = next_dt
            self.current_sim_time += self.DT
        else:
            raise ValueError('时间步长必须大于零。')

    def Caculate_CFL_time_for_river_net(self):
        self.DT_old = self.DT
        DT_limit = self.DT_old + 10
        i0 = 0
        i1 = self.cell_num + 2
        U_slice = self.U[i0:i1]
        C_slice = self.C[i0:i1]
        L_slice = self.cell_lengths[i0:i1]
        diff1 = np.abs(U_slice - C_slice)
        diff2 = np.abs(U_slice + C_slice)
        CNODE = np.maximum(diff1, diff2)
        CNODE = np.clip(CNODE, 0.001, None)
        COU = CNODE / L_slice
        self.DTI[i0:i1] = self.CFL / COU
        dt_min = self.DTI[i0:i1].min()
        self.DT = min(DT_limit, dt_min)
        if self.DT < self.min_dt:
            self.DT = self.min_dt
        DT = np.minimum(self.DT, self.DT_old * self.DT_increase_factor)
        return DT

    def Resample_and_Save_Output_result(self):
        os.makedirs(self.output_folder_path, exist_ok=True)
        ds_data = xr.concat(self.ds_list, dim='time')
        ds = self.ds_coords.merge(ds_data)
        t_fixed = np.arange(0, ds.time.max().item(), self.time_step)
        ds_fixed = ds.interp(time=t_fixed)
        if self.save_result_name == None:
            out_raw = os.path.join(self.output_folder_path, f'{self.model_name}_raw_output.nc')
            out_interp = os.path.join(self.output_folder_path, f'{self.model_name}_interpolated_output.nc')
            for p in (out_raw, out_interp):
                if os.path.exists(p):
                    os.remove(p)
            ds.to_netcdf(path=out_raw, mode='w', format='NETCDF4', engine='h5netcdf')
            ds_fixed.to_netcdf(path=out_interp, mode='w', format='NETCDF4', engine='h5netcdf')
        else:
            output_path = os.path.join(self.output_folder_path, f'{self.save_result_name}.nc')
            if os.path.exists(output_path):
                os.remove(output_path)
            ds_fixed.to_netcdf(path=output_path, mode='w', format='NETCDF4', engine='h5netcdf')

    def Check_Resample_and_Save_Output_result(self):
        import os
        import numpy as np
        import pandas as pd
        import xarray as xr

        def _make_unique_time(ds: xr.Dataset, dim: str='time', float_round_decimals: int=6, dt_floor_freq: str='S', agg: str='mean') -> xr.Dataset:
            if dim not in ds.coords:
                raise KeyError(f'Dataset 中不存在坐标 {dim!r}')
            t = ds[dim].values
            ds2 = ds.copy()
            if np.issubdtype(t.dtype, np.floating):
                t_new = np.round(t, float_round_decimals)
                ds2 = ds2.assign_coords({dim: t_new})
            elif np.issubdtype(t.dtype, np.datetime64):
                t_new = pd.to_datetime(t).floor(dt_floor_freq).to_numpy()
                ds2 = ds2.assign_coords({dim: t_new})
            gb = ds2.groupby(dim)
            if agg == 'mean':
                ds2 = gb.mean()
            elif agg == 'median':
                ds2 = gb.median()
            elif agg == 'first':
                ds2 = gb.first()
            elif agg == 'last':
                ds2 = gb.last()
            elif agg == 'max':
                ds2 = gb.max()
            elif agg == 'min':
                ds2 = gb.min()
            else:
                raise ValueError('agg 必须为 mean/median/first/last/max/min 之一')
            ds2 = ds2.sortby(dim)
            return ds2
        ds_data = xr.concat(self.ds_list, dim='time')
        ds = self.ds_coords.merge(ds_data)
        ds = _make_unique_time(ds, dim='time', float_round_decimals=6, dt_floor_freq='S', agg='mean')
        t0 = ds['time'].values[0]
        t1 = ds['time'].values[-1]
        step = float(self.time_step)
        if step <= 0:
            raise ValueError(f"time_step 必须大于0，当前为 {self.time_step}")
        if np.issubdtype(ds['time'].dtype, np.number):
            start = float(t0)
            end = float(t1)
            t_fixed = np.arange(start, end + step * 0.5, step, dtype=float)
        elif np.issubdtype(ds['time'].dtype, np.datetime64):
            start = pd.to_datetime(t0)
            end = pd.to_datetime(t1)
            step_seconds = int(round(step))
            if step_seconds <= 0:
                step_seconds = 1
            t_fixed = pd.date_range(start=start, end=end, freq=f'{step_seconds}S').to_numpy()
        else:
            raise TypeError(f"不支持的 time dtype: {ds['time'].dtype}")
        tmin = ds['time'].values[0]
        tmax = ds['time'].values[-1]
        if np.issubdtype(ds['time'].dtype, np.number):
            t_fixed = t_fixed[(t_fixed >= tmin) & (t_fixed <= tmax)]
        else:
            t_fixed = t_fixed[(t_fixed >= pd.to_datetime(tmin)) & (t_fixed <= pd.to_datetime(tmax))]
        ds_fixed = ds.interp(time=t_fixed)
        if self.save_result_name is None:
            out_raw = os.path.join(self.output_folder_path, f'{self.model_name}_raw_output.nc')
            out_interp = os.path.join(self.output_folder_path, f'{self.model_name}_interpolated_output.nc')
            for p in (out_raw, out_interp):
                if os.path.exists(p):
                    os.remove(p)
            ds.to_netcdf(path=out_raw, mode='w', format='NETCDF4', engine='h5netcdf')
            ds_fixed.to_netcdf(path=out_interp, mode='w', format='NETCDF4', engine='h5netcdf')
        else:
            output_path = os.path.join(self.output_folder_path, f'{self.save_result_name}.nc')
            if os.path.exists(output_path):
                os.remove(output_path)
            ds_fixed.to_netcdf(path=output_path, mode='w', format='NETCDF4', engine='h5netcdf')

    def Save_result_per_time_step(self):
        if self.save_with_ghost:
            sl = slice(0, self.cell_num + 2)
        else:
            sl = slice(1, self.cell_num + 1)
        depth = self.water_depth[sl].copy()
        level = self.water_level[sl].copy()
        U = self.U[sl].copy()
        Q = self.Q[sl].copy()
        ds_t = xr.Dataset(data_vars={'depth': (('time', 'space'), depth[np.newaxis, :]), 'level': (('time', 'space'), level[np.newaxis, :]), 'U': (('time', 'space'), U[np.newaxis, :]), 'Q': (('time', 'space'), Q[np.newaxis, :])}, coords={'time': [self.current_sim_time], 'space': self.ds_coords.coords['space'].values})
        self.ds_list.append(ds_t)

    def _reset_save_scheduler(self):
        self._next_save_time = 0.0

    def _advance_save_scheduler(self):
        interval = max(float(self.save_min_interval), 1.0e-9)
        while self._next_save_time <= self.current_sim_time + 1.0e-9:
            self._next_save_time += interval

    def _should_save_current_state(self, total_sim_time):
        if self.save_only_end_state:
            return False
        if self.save_all_time_steps:
            return True
        if len(self.ds_list) == 0:
            return True
        if self.current_sim_time + 1.0e-9 >= float(total_sim_time):
            return True
        return self.current_sim_time + 1.0e-9 >= self._next_save_time

    def Save_Basic_data(self):
        self.ds_list = []
        if self.save_with_ghost:
            sl = slice(0, self.cell_num + 2)
            space = np.arange(self.cell_num + 2)
        else:
            sl = slice(1, self.cell_num + 1)
            space = np.arange(self.cell_num)
        x = self.cell_pos[sl, 0]
        y = self.cell_pos[sl, 1]
        z = self.cell_pos[sl, 2]
        print('经纬度转化')
        transformer = Transformer.from_crs('EPSG:4546', 'EPSG:4490', always_xy=True)
        lon, lat = transformer.transform(x, y)
        self.ds_coords = xr.Dataset(coords={'space': space, 'x': ('space', x), 'y': ('space', y), 'z': ('space', z), 'lon': ('space', lon), 'lat': ('space', lat)})

    def Side_inflow(self, pos, side_Q):
        cell_num = self.Get_nearest_cell_num(pos)
        cell_length = self.cell_lengths[cell_num]
        self.QIN[cell_num] += side_Q / cell_length

    def Evolve_impli(self, DT, fine=False):
        time = datetime.datetime.now()
        total_sim_time = self.sim_end_time - self.sim_start_time
        total_sim_time = total_sim_time.total_seconds()
        self.DT = DT
        self.Implic_flag = True
        if fine:
            self.Fine_cell_property2()
        self.Init_cell_proprity(fine)
        self._print_initial_layout()
        self.initial_total_volume = self._compute_total_volume()
        self._reset_step_diagnostics()
        self._diagnostics_snapshot('init', success=True)
        self.Save_Basic_data()
        self._reset_save_scheduler()
        if self.save_only_end_state:
            self.Save_result_per_time_step()
        else:
            self.Save_result_per_time_step()
            self._advance_save_scheduler()
        while self.current_sim_time < total_sim_time:
            if self.current_sim_time + self.DT > total_sim_time:
                self.DT = total_sim_time - self.current_sim_time
            if self.DT <= 0.0:
                break
            if callable(self.boundary_updater):
                self.boundary_updater(self)
            self._reset_step_diagnostics()
            self.Caculate_face_U_C()
            self.Caculate_Roe_matrix()
            self.Caculate_source_term_2()
            self.Caculate_Roe_Flux_2()
            self.Caculate_dam()
            self.Caculate_impli_trans_coefficient()
            self.Assemble_Flux_impli_trans()
            self.time_step_count = self.time_step_count + 1
            self.Update_cell_proprity2()
            self.current_sim_time += self.DT
            self._diagnostics_snapshot('step', success=True)
            yield self.DT
            if self._should_save_current_state(total_sim_time):
                self.Save_result_per_time_step()
                self._advance_save_scheduler()
        if self.save_only_end_state:
            self.Save_result_per_time_step()
        self._write_diagnostics_outputs(success=True)
        self.Resample_and_Save_Output_result()
        if self.Plot_flag:
            print('等待绘制结果图......')
            self._plot_executor.shutdown(wait=True)
            print('----模拟结束，总耗时{}---'.format(datetime.datetime.now() - time))

    def Evolve(self, fine=False, yield_step=None):
        time = datetime.datetime.now()
        total_sim_time = self.sim_end_time - self.sim_start_time
        total_sim_time = total_sim_time.total_seconds()
        local_time_sum = 0
        if fine:
            self.Fine_cell_property2()
        if yield_step == None:
            yield_step = self.time_step
        else:
            self.Max_time_step = yield_step
        self.Init_water_serface()
        self.Implic_flag = False
        self.Init_cell_proprity(fine)
        self._print_initial_layout()
        # 显式格式首步改为 CFL 约束时间步，避免固定 0.1s 首步导致的稳态偏移。
        first_dt = float(self.Caculate_CFL_time_for_river_net())
        self.DT = min(first_dt, float(self.Max_time_step))
        if self.DT < self.min_dt:
            self.DT = self.min_dt
        self.DT_old = self.DT
        self.initial_total_volume = self._compute_total_volume()
        self._reset_step_diagnostics()
        self._diagnostics_snapshot('init', success=True)
        self.Save_Basic_data()
        self._reset_save_scheduler()
        if self.save_only_end_state:
            self.Save_result_per_time_step()
        else:
            self.Save_result_per_time_step()
            self._advance_save_scheduler()
        print('Start Evolve......')
        while self.current_sim_time < total_sim_time:
            if self.current_sim_time + self.DT > total_sim_time:
                self.DT = total_sim_time - self.current_sim_time
            if self.DT <= 0.0:
                break
            used_dt = float(self.DT)
            if callable(self.boundary_updater):
                self.boundary_updater(self)
            self._reset_step_diagnostics()
            self.Caculate_face_U_C()
            self.Caculate_Roe_matrix()
            self.Caculate_source_term_2()
            self.Caculate_Roe_Flux_2()
            self.Caculate_dam()
            self.Assemble_Flux_2()
            self.Update_cell_proprity2()
            self.current_sim_time += used_dt
            self._diagnostics_snapshot('step', success=True)
            if self._should_save_current_state(total_sim_time):
                self.Save_result_per_time_step()
                self._advance_save_scheduler()
            local_time_sum += used_dt
            if local_time_sum > yield_step:
                yield self.current_sim_time
                local_time_sum = 0
            self._update_cfl_dt(used_dt=used_dt, advance_time=False)
            self.time_step_count = self.time_step_count + 1
        if self.save_only_end_state:
            self.Save_result_per_time_step()
        self._write_diagnostics_outputs(success=True)
        self.Resample_and_Save_Output_result()
        if self.Plot_flag:
            print('等待绘制结果图......')
            self._plot_executor.shutdown(wait=True)
            print('----模拟结束，总耗时{}---'.format(datetime.datetime.now() - time))

    def Update_cell_proprity2(self):
        # State-refresh owner: derive depth/level/U/C/Fr and final dry flags from S/Q.
        for i in range(0, self.cell_num + 2):
            self._refresh_cell_state(i)
            self.QIN[i] = 0

    def Update_boundry_condition(self, implic=False):
        if not implic:
            self.U[0] = self.U[1] = 0
            self.S[0] = self.S[1] = self.S[2]
            self.U[-1] = -self.U[-2]
            self.S[-1] = self.S[-2]
        else:
            self.U[0] = self.U[1]
            self.S[0] = self.S[1]
            self.U[-1] = -self.U[-2]
            self.S[-1] = self.S[-2]

    def _refresh_cell_state(self, idx, level_hint=None):
        """State-refresh owner for a single cell after S/Q have been settled."""
        sec = self.cell_sections[idx]
        section_bed = self._get_section_table_bed_level(sec)
        prev_s = float(self.S[idx])
        prev_depth = float(self.water_depth[idx])
        S = float(max(self.S[idx], 0.0))
        self.S[idx] = S
        if level_hint is None:
            level = float(self.cross_section_table.get_level_by_area(sec, S))
        else:
            level = float(level_hint)
        self.water_level[idx] = level
        self.water_depth[idx] = max(level - section_bed, 0.0)
        if self._is_cell_dry(idx, area=S, depth=self.water_depth[idx]):
            self._apply_conservative_dry_guard(idx, prev_s=prev_s, prev_depth=prev_depth)
            self.water_depth[idx] = 0.0
            self.water_level[idx] = float(section_bed)
            self.U[idx] = 0.0
            self.C[idx] = self.EPSILON
            self.FR[idx] = 0.0
        else:
            if self.water_depth[idx] <= self.velocity_depth_limit:
                if self.near_dry_velocity_cutoff_mode == 'zero_q':
                    self.Q[idx] = 0.0
                    self.U[idx] = 0.0
                    self.C[idx] = self.EPSILON
                    self.FR[idx] = 0.0
                else:
                    self._compute_near_dry_derived_state(idx)
            else:
                self.U[idx] = float(self.Q[idx]) / self.S[idx]
                width = self._resolve_width_for_state(sec, self.S[idx], self.water_depth[idx])
                self.C[idx] = np.sqrt(self.g * self.S[idx] / width)
                self.FR[idx] = np.abs(self.U[idx]) / max(self.C[idx], self.EPSILON)
        final_area = float(self.S[idx])
        self.P[idx] = float(self.cross_section_table.get_wetted_perimeter_by_area(sec, final_area))
        self.PRESS[idx] = float(self.cross_section_table.get_press_by_area(sec, final_area))
        self.R[idx] = float(self.cross_section_table.get_hydraulic_radius_by_area(sec, final_area))

    def Set_ghost_from_face_state(self, side, level, flow):
        side_txt = str(side).lower()
        if side_txt == 'left':
            ghost_idx = 0
            inner_idx = 1
        elif side_txt == 'right':
            ghost_idx = -1
            inner_idx = -2
        else:
            raise ValueError(f'unsupported ghost side: {side}')
        face_level = float(level)
        face_flow = float(flow)
        ghost_level = 2.0 * face_level - float(self.water_level[inner_idx])
        sec = self.cell_sections[ghost_idx]
        area = float(self.cross_section_table.get_area_by_level(sec, ghost_level))
        self.S[ghost_idx] = max(area, 0.0)
        if self.S[ghost_idx] <= self._get_cell_s_limit(ghost_idx):
            self.Q[ghost_idx] = 0.0
        else:
            self.Q[ghost_idx] = 2.0 * face_flow - float(self.Q[inner_idx])
        self._refresh_cell_state(ghost_idx, level_hint=ghost_level)

    def InBound_In_Q(self, Q):
        self.Q[0] = Q
        self.S[0] = self.S[0] + self.DT * (self.Q[0] - self.Q[1]) / self.cell_lengths[0]
        sec = self.cell_sections[0]
        self.water_depth[0] = self.cross_section_table.get_depth_by_area(sec, self.S[0])
        width = float(self.cross_section_table.get_width_by_area(sec, max(self.S[0], 1e-12)))
        width = max(width, 1e-08)
        self.C[0] = np.sqrt(self.g * max(self.S[0], 1e-12) / width)
        self.FR[0] = np.abs(self.Q[0]) / max(self.C[0] * self.S[0], 1e-12)
        if self.FR[0] > 0.99:
            q_cap = 0.99 * self.C[0] * self.S[0]
            Q = float(np.sign(Q) * min(abs(Q), q_cap))
        self.Q[0] = Q
        self._refresh_cell_state(0)
        if self.Implic_flag:
            self.V0[0] = self.S[0] - self.S_old[0]
            self.V0[1] = self.Q[0] - self.Q_old[0]

    def _moc_source_term(self, idx, kind='stage'):
        use_global = bool(getattr(self, 'bc_moc_with_source', False))
        if kind == 'flow':
            use_local = bool(getattr(self, 'bc_moc_with_source_flow', False))
        else:
            use_local = bool(getattr(self, 'bc_moc_with_source_stage', False))
        if not (use_global or use_local):
            return 0.0
        tinyA = 1e-12
        tinyR = 1e-08
        A = float(max(self.S[idx], tinyA))
        Q = float(self.Q[idx])
        R = float(max(self.R[idx], tinyR))
        n_val = float(self.n[idx]) if np.ndim(self.n) else float(self.n)
        sf = n_val * n_val * Q * abs(Q) / (A * A * R ** (4.0 / 3.0) + 1e-12)
        s0 = float(self.Slop[idx])
        scale = float(getattr(self, 'bc_moc_source_scale', 1.0))
        return float(self.g * (s0 - sf) * scale)

    def _build_char_potential_cache(self, section_name):
        # Boundary-only general-chi support:
        # chi(A) = chi(A0) + integral sqrt(g*A/T(A)) / A dA
        # This cache is derived from the same area-width table as the hydraulic solver,
        # but is currently consumed only by characteristic boundary closure when
        # bc_use_general_chi=True.
        tbl = self.cross_section_table.tables.get(section_name)
        if tbl is None:
            return None
        tinyA = 1e-12
        tinyT = 1e-08
        area_axis_raw = np.asarray(tbl._area_axis, dtype=float)
        if area_axis_raw.size == 0:
            return None
        area_axis = np.unique(area_axis_raw[np.isfinite(area_axis_raw)])
        area_axis = area_axis[area_axis > tinyA]
        if area_axis.size == 0:
            return None
        width_axis = np.asarray([tbl.get_width_by_area(a) for a in area_axis], dtype=float)
        width_axis = np.maximum(width_axis, tinyT)
        integrand = np.sqrt(self.g * area_axis / width_axis) / np.maximum(area_axis, tinyA)
        chi_axis = np.zeros_like(area_axis)
        if area_axis.size > 1:
            chi_axis[1:] = np.cumsum(0.5 * (integrand[1:] + integrand[:-1]) * np.diff(area_axis))
        chi0 = 2.0 * np.sqrt(self.g * area_axis[0] / width_axis[0])
        chi_axis = chi_axis + chi0
        cache = {'A': area_axis, 'chi': chi_axis, 'A0': float(area_axis[0]), 'Amax': float(area_axis[-1]), 'w0': float(width_axis[0]), 'chi_max': float(chi_axis[-1]), 'kmax': float(integrand[-1])}
        self._char_potential_cache[section_name] = cache
        return cache

    def _get_section_points_for_table(self, section_name):
        # Assumption: section_data already represents the intended hydraulic
        # domain for this solver (main channel only in the current use-case).
        # If stricter main-channel cropping is needed in the future, the
        # preprocessing hook belongs here rather than inside the geometric
        # clipping kernel.
        return self.sections_data[section_name]

    def _char_potential_from_width(self, section_name, area, tinyA=1e-12, tinyT=1e-08):
        A = float(max(area, tinyA))
        T = float(self.cross_section_table.get_width_by_area(section_name, A))
        T = max(T, tinyT)
        return float(2.0 * np.sqrt(self.g * A / T))

    def _char_potential_from_general_cache(self, section_name, area, tinyA=1e-12, tinyT=1e-08):
        A = float(max(area, tinyA))
        cache = self._char_potential_cache.get(section_name)
        if cache is None:
            cache = self._build_char_potential_cache(section_name)
        if cache is None:
            return self._char_potential_from_width(section_name, A, tinyA=tinyA, tinyT=tinyT)
        if A <= cache['A0']:
            return float(2.0 * np.sqrt(self.g * A / max(cache['w0'], tinyT)))
        if A >= cache['Amax']:
            return float(cache['chi_max'] + cache['kmax'] * (A - cache['Amax']))
        return float(np.interp(A, cache['A'], cache['chi']))

    def _char_potential(self, section_name, area):
        tinyA = 1e-12
        tinyT = 1e-08
        if not bool(getattr(self, 'bc_use_general_chi', False)):
            return self._char_potential_from_width(section_name, area, tinyA=tinyA, tinyT=tinyT)
        return self._char_potential_from_general_cache(section_name, area, tinyA=tinyA, tinyT=tinyT)

    def _char_potential_from_depth_reference(self, section_name, area, tinyA=1e-12):
        A = float(max(area, tinyA))
        depth = float(max(self.cross_section_table.get_depth_by_area(section_name, A), 0.0))
        return float(2.0 * np.sqrt(self.g * depth))

    def _stage_boundary_char_triplet(self, section_name, area):
        A = float(max(area, 1.0e-12))
        return {
            'width': self._char_potential_from_width(section_name, A),
            'general': self._char_potential_from_general_cache(section_name, A),
            'depth_ref': self._char_potential_from_depth_reference(section_name, A),
        }

    def _compute_stage_boundary_characteristic_velocity_with_explicit_chi(self, ctx, chi_inner, chi_b, chi_second=None):
        probe_ctx = dict(ctx)
        probe_ctx['chi1'] = float(chi_inner)
        if probe_ctx.get('use_o2', False) and chi_second is not None:
            probe_ctx['chi2'] = float(chi_second)
        return float(self._compute_stage_boundary_characteristic_velocity(probe_ctx, float(chi_b)))

    def _build_stage_boundary_chi_audit(self, ctx, target):
        if (not self.enable_boundary_chi_audit) or float(target.get('Ab', 0.0)) <= 0.0:
            return {}
        inner_sec = self.cell_sections[ctx['inner_idx']]
        ghost_sec = target['sec_b']
        inner_triplet = self._stage_boundary_char_triplet(inner_sec, ctx['Ai'])
        ghost_triplet = self._stage_boundary_char_triplet(ghost_sec, target['Ab'])
        second_triplet = None
        if ctx.get('use_o2', False):
            second_triplet = self._stage_boundary_char_triplet(self.cell_sections[ctx['second_idx']], ctx['A2'])
        ub_width = self._compute_stage_boundary_characteristic_velocity_with_explicit_chi(
            ctx,
            inner_triplet['width'],
            ghost_triplet['width'],
            None if second_triplet is None else second_triplet['width'],
        )
        ub_general = self._compute_stage_boundary_characteristic_velocity_with_explicit_chi(
            ctx,
            inner_triplet['general'],
            ghost_triplet['general'],
            None if second_triplet is None else second_triplet['general'],
        )
        return {
            'chi_mode_active': 'general_cache' if bool(getattr(self, 'bc_use_general_chi', False)) else 'width',
            'chi_inner_width': float(inner_triplet['width']),
            'chi_inner_general': float(inner_triplet['general']),
            'chi_inner_depth_ref': float(inner_triplet['depth_ref']),
            'chi_target_width': float(ghost_triplet['width']),
            'chi_target_general': float(ghost_triplet['general']),
            'chi_target_depth_ref': float(ghost_triplet['depth_ref']),
            'chi_inner_general_minus_width': float(inner_triplet['general'] - inner_triplet['width']),
            'chi_target_general_minus_width': float(ghost_triplet['general'] - ghost_triplet['width']),
            'ub_char_width': float(ub_width),
            'ub_char_general': float(ub_general),
            'Qb_raw_width': float(ub_width * target['Ab']),
            'Qb_raw_general': float(ub_general * target['Ab']),
            'Qb_raw_general_minus_width': float((ub_general - ub_width) * target['Ab']),
        }

    def _select_stage_boundary_chi_from_triplet(self, triplet, dry_entry, near_dry_entry, allow_candidate=True):
        base_mode = 'general_cache' if bool(getattr(self, 'bc_use_general_chi', False)) else 'width'
        selected_mode = base_mode
        selected = float(triplet['general'] if base_mode == 'general_cache' else triplet['width'])
        candidate_applied = False
        if (not bool(getattr(self, 'bc_use_general_chi', False))) or dry_entry or near_dry_entry or (not allow_candidate):
            return {
                'selected': selected,
                'selected_mode': selected_mode,
                'candidate_applied': candidate_applied,
            }
        candidate_mode = str(getattr(self, 'bc_general_chi_candidate_mode', 'off')).lower()
        if candidate_mode == 'wet_width':
            selected = float(triplet['width'])
            selected_mode = 'candidate_wet_width'
            candidate_applied = True
        elif candidate_mode == 'guarded_clamp':
            delta = float(triplet['general'] - triplet['width'])
            guard = float(max(getattr(self, 'bc_general_chi_guard_abs_delta', 0.15), 0.0))
            if abs(delta) > guard:
                selected = float(triplet['width'] + np.sign(delta) * guard)
                selected_mode = 'candidate_guarded_clamp'
                candidate_applied = True
        return {
            'selected': selected,
            'selected_mode': selected_mode,
            'candidate_applied': candidate_applied,
        }

    def _evaluate_stage_boundary_chi_guard(self, ctx, target, inner_triplet, target_triplet, second_triplet, dry_entry, near_dry_entry):
        guard_info = {
            'guard_selector': str(getattr(self, 'bc_general_chi_guard_selector', 'closure_q_delta')),
            'guard_threshold_q_delta': float(max(getattr(self, 'bc_general_chi_guard_q_delta', 0.005), 0.0)),
            'closure_q_delta_general_vs_width': np.nan,
            'closure_ub_delta_general_vs_width': np.nan,
            'allow_candidate': True,
            'guard_triggered': False,
        }
        candidate_mode = str(getattr(self, 'bc_general_chi_candidate_mode', 'off')).lower()
        if (not bool(getattr(self, 'bc_use_general_chi', False))) or dry_entry or near_dry_entry or candidate_mode != 'guarded_clamp':
            return guard_info
        if guard_info['guard_selector'] != 'closure_q_delta':
            return guard_info
        if float(target.get('Ab', 0.0)) <= 0.0:
            return guard_info
        ub_width = self._compute_stage_boundary_characteristic_velocity_with_explicit_chi(
            ctx,
            inner_triplet['width'],
            target_triplet['width'],
            None if second_triplet is None else second_triplet['width'],
        )
        ub_general = self._compute_stage_boundary_characteristic_velocity_with_explicit_chi(
            ctx,
            inner_triplet['general'],
            target_triplet['general'],
            None if second_triplet is None else second_triplet['general'],
        )
        q_delta = abs(float((ub_general - ub_width) * target['Ab']))
        ub_delta = abs(float(ub_general - ub_width))
        guard_info['closure_q_delta_general_vs_width'] = float(q_delta)
        guard_info['closure_ub_delta_general_vs_width'] = float(ub_delta)
        allow_candidate = bool(q_delta > guard_info['guard_threshold_q_delta'])
        guard_info['allow_candidate'] = allow_candidate
        guard_info['guard_triggered'] = allow_candidate
        return guard_info

    def _resolve_stage_boundary_chi_bundle(self, ctx, target, dry_entry, near_dry_entry):
        inner_sec = self.cell_sections[ctx['inner_idx']]
        ghost_sec = target['sec_b']
        inner_triplet = self._stage_boundary_char_triplet(inner_sec, ctx['Ai'])
        target_triplet = self._stage_boundary_char_triplet(ghost_sec, target['Ab'])
        second_triplet = None
        if ctx.get('use_o2', False):
            second_triplet = self._stage_boundary_char_triplet(self.cell_sections[ctx['second_idx']], ctx['A2'])
        guard_info = self._evaluate_stage_boundary_chi_guard(
            ctx,
            target,
            inner_triplet,
            target_triplet,
            second_triplet,
            dry_entry,
            near_dry_entry,
        )
        allow_candidate = bool(guard_info['allow_candidate'])
        inner_sel = self._select_stage_boundary_chi_from_triplet(inner_triplet, dry_entry, near_dry_entry, allow_candidate=allow_candidate)
        target_sel = self._select_stage_boundary_chi_from_triplet(target_triplet, dry_entry, near_dry_entry, allow_candidate=allow_candidate)
        second_sel = None
        if second_triplet is not None:
            second_sel = self._select_stage_boundary_chi_from_triplet(second_triplet, dry_entry, near_dry_entry, allow_candidate=allow_candidate)
        return {
            'inner_triplet': inner_triplet,
            'target_triplet': target_triplet,
            'second_triplet': second_triplet,
            'inner_selected': inner_sel,
            'target_selected': target_sel,
            'second_selected': second_sel,
            'guard_info': guard_info,
        }

    def _get_stage_boundary_layout(self, side):
        side_txt = str(side).lower()
        if side_txt == 'left':
            return {
                'side': 'left',
                'ghost_idx': 0,
                'inner_idx': 1,
                'second_idx': 2,
                'dry_limit_idx': 1,
                'face_idx': 0,
                'tag': 'left_stage',
                'debug_attr': 'debug_supercritical_in_count',
                'prev_q_attr': 'prev_Qb_left',
                'swap_attr': 'swap_moc_sign_stage_in',
                'vector_attr': 'V0',
            }
        if side_txt == 'right':
            return {
                'side': 'right',
                'ghost_idx': -1,
                'inner_idx': -2,
                'second_idx': -3,
                'dry_limit_idx': self.cell_num,
                'face_idx': self.cell_num,
                'tag': 'right_stage',
                'debug_attr': 'debug_supercritical_out_count',
                'prev_q_attr': 'prev_Qb_right',
                'swap_attr': 'swap_moc_sign_stage_out',
                'vector_attr': 'V1',
            }
        raise ValueError(f'unsupported stage boundary side: {side}')

    def _prepare_stage_boundary_context(self, side, level, stage_on_face, tinyA, tinyT, g):
        ctx = self._get_stage_boundary_layout(side)
        inner_idx = ctx['inner_idx']
        if stage_on_face:
            level = 2.0 * float(level) - float(self.water_level[inner_idx])
        ctx['level'] = float(level)
        Ai = float(self.S[inner_idx])
        Ti = float(self.cross_section_table.get_width_by_area(self.cell_sections[inner_idx], Ai))
        Ti = max(Ti, tinyT)
        ui = float(self.Q[inner_idx]) / max(Ai, tinyA)
        ci = (g * Ai / Ti) ** 0.5
        chi1 = self._char_potential(self.cell_sections[inner_idx], Ai)
        dt_moc = float(getattr(self, 'DT', 0.0))
        src1 = self._moc_source_term(inner_idx, kind='stage')
        use_o2 = bool(getattr(self, 'bc_use_order2_extrap_stage', getattr(self, 'bc_use_order2_extrap', False))) and self.cell_num >= 3
        ctx.update({
            'Ai': Ai,
            'Ti': Ti,
            'ui': ui,
            'ci': ci,
            'chi1': chi1,
            'dt_moc': dt_moc,
            'src1': src1,
            'use_o2': bool(use_o2),
        })
        if use_o2:
            second_idx = ctx['second_idx']
            A2 = float(max(self.S[second_idx], tinyA))
            u2 = float(self.Q[second_idx]) / A2
            chi2 = self._char_potential(self.cell_sections[second_idx], A2)
            src2 = self._moc_source_term(second_idx, kind='stage')
            ctx.update({
                'A2': A2,
                'u2': u2,
                'chi2': chi2,
                'src2': src2,
            })
        return ctx

    def _prepare_stage_boundary_target_state(self, ctx, tinyA, tinyT, g):
        ghost_idx = ctx['ghost_idx']
        sec_b = self.cell_sections[ghost_idx]
        Ab = float(self.cross_section_table.get_area_by_level(sec_b, ctx['level']))
        target = {
            'sec_b': sec_b,
            'Ab': Ab,
        }
        if Ab <= 0.0:
            return target
        Tb = float(self.cross_section_table.get_width_by_area(sec_b, Ab))
        Tb = max(Tb, tinyT)
        cb = (g * Ab / Tb) ** 0.5
        chi_b = self._char_potential(sec_b, Ab)
        target.update({
            'Tb': Tb,
            'cb': cb,
            'chi_b': chi_b,
        })
        return target

    def _compute_stage_boundary_characteristic_velocity(self, ctx, chi_b):
        jm1 = ctx['ui'] - ctx['chi1'] + ctx['src1'] * ctx['dt_moc']
        jp1 = ctx['ui'] + ctx['chi1'] + ctx['src1'] * ctx['dt_moc']
        if ctx['use_o2']:
            jm2 = ctx['u2'] - ctx['chi2'] + ctx['src2'] * ctx['dt_moc']
            jp2 = ctx['u2'] + ctx['chi2'] + ctx['src2'] * ctx['dt_moc']
            jm = 2.0 * jm1 - jm2
            jp = 2.0 * jp1 - jp2
        else:
            jm = jm1
            jp = jp1
        swap_moc_sign = bool(getattr(self, ctx['swap_attr'], getattr(self, 'swap_moc_sign_stage', getattr(self, 'swap_moc_sign', False))))
        ctx['swap_moc_sign'] = bool(swap_moc_sign)
        if ctx['side'] == 'left':
            return jp - chi_b if swap_moc_sign else jm + chi_b
        return jm + chi_b if swap_moc_sign else jp - chi_b

    def _classify_stage_boundary_entry(self, ctx, tinyA):
        dry_limit = max(self._get_cell_s_limit(ctx['dry_limit_idx']) * 10.0, tinyA * 10.0)
        near_dry_limit = max(self._get_cell_s_limit(ctx['dry_limit_idx']) * 40.0, tinyA * 40.0)
        inner_depth = float(self.water_depth[ctx['inner_idx']])
        dry_entry = (ctx['Ai'] <= dry_limit) or (inner_depth <= max(self.water_depth_limit * 5.0, 1.0e-4))
        near_dry_entry = (ctx['Ai'] <= near_dry_limit) or (inner_depth <= max(self.water_depth_limit * 20.0, 5.0e-4))
        return (bool(dry_entry), bool(near_dry_entry))

    def _apply_stage_boundary_stabilizers(self, ctx, target, ub, Fr_max, head_gain_factor, relax_Q, cap_du_factor, cap_dQ_factor, use_stabilizers=True, q_hint=None, q_hint_blend=0.0, q_hint_cap_factor=0.0, dry_entry=None, near_dry_entry=None):
        g = getattr(self, 'g', 9.81)
        tinyC = 1e-08
        if dry_entry is None or near_dry_entry is None:
            dry_entry, near_dry_entry = self._classify_stage_boundary_entry(ctx, 1e-12)
        head_cap_applied = False
        if use_stabilizers or dry_entry:
            Frb = abs(ub) / max(target['cb'], tinyC)
            if Frb > Fr_max:
                ub = ub / max(abs(ub), 1e-12) * Fr_max * target['cb']
            Hi = float(self.water_level[ctx['inner_idx']])
            if ctx['side'] == 'left':
                dH = ctx['level'] - Hi
            else:
                dH = Hi - ctx['level']
            if dH >= 0.0 and (dry_entry or near_dry_entry):
                u_head = (2.0 * g * dH) ** 0.5
                ub = ub / max(abs(ub), 1e-12) * min(abs(ub), head_gain_factor * u_head)
                head_cap_applied = True
            ub = max(ctx['ui'] - cap_du_factor * ctx['ci'], min(ctx['ui'] + cap_du_factor * ctx['ci'], ub))
        Qb_raw = ub * target['Ab']
        if ctx['side'] == 'left' and q_hint is not None and np.isfinite(q_hint):
            q_hint = float(q_hint)
            cap_factor = float(max(q_hint_cap_factor, 0.0))
            if cap_factor > 0.0:
                q_cap = max(cap_factor * target['Ab'] * target['cb'], 5.0 * abs(q_hint), 1.0e-8)
                Qb_raw = float(np.clip(Qb_raw, q_hint - q_cap, q_hint + q_cap))
            blend = float(np.clip(q_hint_blend, 0.0, 1.0))
            if blend > 0.0:
                Qb_raw = (1.0 - blend) * Qb_raw + blend * q_hint
        if use_stabilizers or dry_entry:
            cap_dQ = cap_dQ_factor * ctx['Ai'] * ctx['ci']
            if dry_entry:
                cap_dQ = max(cap_dQ, 0.25 * target['Ab'] * target['cb'])
            inner_q = float(self.Q[ctx['inner_idx']])
            Qb_raw = max(inner_q - cap_dQ, min(inner_q + cap_dQ, Qb_raw))
            prev = getattr(self, ctx['prev_q_attr'], None)
            if prev is None:
                prev = 0.0 if dry_entry else Qb_raw
            relax = relax_Q if not dry_entry else min(relax_Q, 0.2)
            Qb = prev + relax * (Qb_raw - prev)
            setattr(self, ctx['prev_q_attr'], Qb)
        else:
            Qb = Qb_raw
        return {
            'Qb_raw': float(Qb_raw),
            'Qb': float(Qb),
            'dry_entry': bool(dry_entry),
            'near_dry_entry': bool(near_dry_entry),
            'head_cap_applied': bool(head_cap_applied),
        }

    def _apply_supercritical_stage_boundary_copy(self, ctx):
        setattr(self, ctx['debug_attr'], int(getattr(self, ctx['debug_attr'])) + 1)
        ghost_idx = ctx['ghost_idx']
        inner_idx = ctx['inner_idx']
        self.S[ghost_idx] = self.S[inner_idx]
        self.Q[ghost_idx] = self.Q[inner_idx]
        self.water_level[ghost_idx] = self.water_level[inner_idx]
        self._refresh_cell_state(ghost_idx, level_hint=self.water_level[ghost_idx])
        self._sync_boundary_face_state_from_ghost(ctx['side'])
        self._update_stage_boundary_implicit_vector(ctx)

    def _apply_empty_stage_boundary_state(self, ctx):
        ghost_idx = ctx['ghost_idx']
        self.S[ghost_idx] = 0.0
        self.Q[ghost_idx] = 0.0
        self.water_level[ghost_idx] = ctx['level']
        self._refresh_cell_state(ghost_idx, level_hint=ctx['level'])
        self._set_boundary_face_state(ctx['side'], level=ctx['level'], area=0.0, discharge=0.0, width=0.0)
        self._update_stage_boundary_implicit_vector(ctx)

    def _commit_stage_boundary_state(self, ctx, Ab, Qb, Tb=None):
        ghost_idx = ctx['ghost_idx']
        self.S[ghost_idx] = Ab
        self.Q[ghost_idx] = Qb
        self._refresh_cell_state(ghost_idx, level_hint=ctx['level'])
        self._set_boundary_face_state(ctx['side'], level=ctx['level'], area=Ab, discharge=Qb, width=Tb)
        self._update_stage_boundary_implicit_vector(ctx)

    def _update_stage_boundary_implicit_vector(self, ctx):
        if not getattr(self, 'Implic_flag', False):
            return
        vector = getattr(self, ctx['vector_attr'])
        ghost_idx = ctx['ghost_idx']
        vector[0] = self.S[ghost_idx] - self.S_old[ghost_idx]
        vector[1] = self.Q[ghost_idx] - self.Q_old[ghost_idx]

    def _append_stage_boundary_record(self, ctx, target, stabilizer_state):
        face_flux = self._peek_interface_flux_for_diagnostics(ctx['face_idx'])
        ghost_idx = ctx['ghost_idx']
        inner_idx = ctx['inner_idx']
        record = {
            'tag': ctx['tag'],
            'time_s': float(self.current_sim_time),
            'step': int(self.time_step_count),
            'target_level': float(ctx['level']),
            'Ai': float(ctx['Ai']),
            'Hi': float(self.water_level[inner_idx]),
            'Qi': float(self.Q[inner_idx]),
            'ui': float(ctx['ui']),
            'Ab': float(target['Ab']),
            'Qb_raw': float(stabilizer_state['Qb_raw']),
            'Qb': float(stabilizer_state['Qb']),
            'ghost_level': float(self.water_level[ghost_idx]),
            'ghost_depth': float(self.water_depth[ghost_idx]),
            'ghost_U': float(self.U[ghost_idx]),
            'ghost_C': float(self.C[ghost_idx]),
            'ghost_chi_active': float(self._char_potential(self.cell_sections[ghost_idx], max(self.S[ghost_idx], 1.0e-12))),
            'face_flux_mass': float(face_flux[0]),
            'face_flux_momentum': float(face_flux[1]),
            'dry_entry': bool(stabilizer_state['dry_entry']),
            'near_dry_entry': bool(stabilizer_state['near_dry_entry']),
            'head_cap_applied': bool(stabilizer_state['head_cap_applied']),
        }
        if self.enable_boundary_chi_audit:
            record.update(self._build_stage_boundary_chi_audit(ctx, target))
        chi_bundle = stabilizer_state.get('chi_bundle')
        if chi_bundle is not None:
            record.update(
                {
                    'chi_selected_mode_inner': str(chi_bundle['inner_selected']['selected_mode']),
                    'chi_selected_mode_target': str(chi_bundle['target_selected']['selected_mode']),
                    'chi_inner_selected': float(chi_bundle['inner_selected']['selected']),
                    'chi_target_selected': float(chi_bundle['target_selected']['selected']),
                    'chi_candidate_applied': bool(
                        chi_bundle['inner_selected']['candidate_applied'] or chi_bundle['target_selected']['candidate_applied']
                    ),
                }
            )
            guard_info = chi_bundle.get('guard_info', {})
            record.update(
                {
                    'chi_guard_selector': str(guard_info.get('guard_selector', '')),
                    'chi_guard_triggered': bool(guard_info.get('guard_triggered', False)),
                    'chi_guard_threshold_q_delta': float(guard_info.get('guard_threshold_q_delta', np.nan)),
                    'chi_closure_q_delta_general_vs_width': float(guard_info.get('closure_q_delta_general_vs_width', np.nan)),
                    'chi_closure_ub_delta_general_vs_width': float(guard_info.get('closure_ub_delta_general_vs_width', np.nan)),
                }
            )
        self._append_boundary_diagnostics(record)

    def InBound_In_Q2(self, Q_in):
        tinyA = 1e-12
        sec_in = self.cell_sections[1]
        sec_b = self.cell_sections[0]
        dt_moc = float(getattr(self, 'DT', 0.0))
        cell1_is_dry = bool(self._is_cell_dry(1, area=self.S[1], depth=self.water_depth[1]))
        cell1_dry_to_wet = bool(self._prev_left_inner_is_dry is True and (not cell1_is_dry))
        if cell1_dry_to_wet:
            self.left_inflow_cell1_dry_to_wet_count += 1
        self._prev_left_inner_is_dry = cell1_is_dry

        S1 = float(max(self.S[1], self._get_cell_s_limit(1), tinyA))
        h1 = float(max(self.water_depth[1], 0.0))
        Q1 = float(self.Q[1])
        u1 = Q1 / S1
        chi1 = self._char_potential(sec_in, S1)
        src1 = self._moc_source_term(1, kind='flow')
        use_fallback, fallback_params = self._should_use_left_inflow_wetting_fallback(Q_in)
        fallback_triggered = False
        fallback_area_min = float(max(self._get_cell_s_limit(0), self.cross_section_table.get_area_by_depth(sec_b, fallback_params['min_depth'])))
        fallback_depth_min = float(fallback_params['min_depth'])

        if use_fallback:
            q_target = float(Q_in)
            area_target, depth_target, width_target, c_target = self._solve_area_for_target_froude(
                sec_b,
                abs(q_target),
                fallback_params['fr_target'],
                fallback_depth_min,
            )
            self.S[0] = float(max(area_target, fallback_area_min))
            self.Q[0] = float(q_target)
            level_b = float(self.river_bed_height[0]) + float(depth_target)
            self._refresh_cell_state(0, level_hint=level_b)
            fallback_triggered = True
            self.left_inflow_fallback_count += 1
        else:
            swap_moc_sign = bool(getattr(self, 'swap_moc_sign_flow', getattr(self, 'swap_moc_sign', False)))
            use_o2 = bool(getattr(self, 'bc_use_order2_extrap_flow', getattr(self, 'bc_use_order2_extrap', False))) and self.cell_num >= 3
            if use_o2:
                S2 = float(max(self.S[2], self._get_cell_s_limit(2), tinyA))
                Q2 = float(self.Q[2])
                u2 = Q2 / S2
                chi2 = self._char_potential(self.cell_sections[2], S2)
                src2 = self._moc_source_term(2, kind='flow')
                f_minus_1 = u1 - chi1 + src1 * dt_moc
                f_minus_2 = u2 - chi2 + src2 * dt_moc
                f_plus_1 = u1 + chi1 + src1 * dt_moc
                f_plus_2 = u2 + chi2 + src2 * dt_moc
            else:
                f_minus_1 = u1 - chi1 + src1 * dt_moc
                f_plus_1 = u1 + chi1 + src1 * dt_moc
            if swap_moc_sign:
                f_plus = 2.0 * f_plus_1 - f_plus_2 if use_o2 else f_plus_1
            else:
                f_minus = 2.0 * f_minus_1 - f_minus_2 if use_o2 else f_minus_1
            Qb = float(Q_in)
            Sb = float(max(S1, self._get_cell_s_limit(0)))
            for _ in range(12):
                ub = Qb / max(Sb, tinyA)
                chi_b = self._char_potential(sec_b, Sb)
                if swap_moc_sign:
                    F = ub + chi_b - f_plus
                else:
                    F = ub - chi_b - f_minus
                dS = max(1e-06, 0.0001 * Sb)
                Sp = max(Sb + dS, self._get_cell_s_limit(0))
                chi_p = self._char_potential(sec_b, Sp)
                if swap_moc_sign:
                    Fp = Qb / max(Sp, tinyA) + chi_p - f_plus
                else:
                    Fp = Qb / max(Sp, tinyA) - chi_p - f_minus
                dF = (Fp - F) / (Sp - Sb)
                if abs(dF) < 1e-10:
                    break
                step = F / dF
                step = float(np.clip(step, -0.5 * Sb, 0.5 * Sb))
                Sb_new = max(Sb - step, self._get_cell_s_limit(0))
                if abs(Sb_new - Sb) / max(Sb, 1e-06) < 1e-06:
                    Sb = Sb_new
                    break
                Sb = Sb_new
            self.S[0] = float(Sb)
            self.Q[0] = float(Qb)
            self._refresh_cell_state(0)
        self._sync_boundary_face_state_from_ghost('left')

        face_flux = self._peek_interface_flux_for_diagnostics(0)
        hb = float(max(self.water_depth[0], 0.0))
        Sb = float(self.S[0])
        Qb = float(self.Q[0])
        ub = float(Qb / max(Sb, tinyA)) if Sb > tinyA else 0.0
        record = {
            'tag': 'left_inflow_q',
            'time_s': float(self.current_sim_time),
            'step': int(self.time_step_count),
            'bc_discharge_wetting_mode': self.bc_discharge_wetting_mode,
            'Q_in': float(Q_in),
            'S1': float(self.S[1]),
            'h1': float(self.water_depth[1]),
            'Q1': float(self.Q[1]),
            'u1': float(self.Q[1] / max(float(self.S[1]), tinyA)) if float(self.S[1]) > tinyA else 0.0,
            'chi1': float(chi1),
            'ghost_Sb': Sb,
            'ghost_hb': hb,
            'ghost_ub': ub,
            'face_flux_mass': float(face_flux[0]),
            'face_flux_momentum': float(face_flux[1]),
            'wetting_inflow_fallback_triggered': bool(fallback_triggered),
            'fallback_min_area': float(fallback_area_min),
            'fallback_min_depth': float(fallback_depth_min),
            'fallback_target_fr': float(fallback_params['fr_target']),
            'cell1_dry_to_wet_this_step': bool(cell1_dry_to_wet),
            'cell1_is_dry_now': bool(cell1_is_dry),
        }
        self._append_boundary_diagnostics(record, fallback_triggered=fallback_triggered, force=cell1_dry_to_wet)
        if self.Implic_flag:
            self.V0[0] = self.S[0] - self.S_old[0]
            self.V0[1] = self.Q[0] - self.Q_old[0]

    def InBound_In_Q_re(self, Q):
        self.S[-1] = self.S[-1] + self.DT * (self.Q[-1] - self.Q[-2]) / self.cell_lengths[-1]
        sec = self.cell_sections[-1]
        width = float(self.cross_section_table.get_width_by_area(sec, max(self.S[-1], 1e-12)))
        width = max(width, 1e-08)
        c = np.sqrt(self.g * max(self.S[-1], 1e-12) / width)
        fr = abs(Q) / max(c * self.S[-1], 1e-12)
        if fr > 0.99:
            Q = float(np.sign(Q) * min(abs(Q), 0.99 * c * self.S[-1]))
        self.Q[-1] = Q
        self._refresh_cell_state(-1)

    def OutBound_Free_Outfall(self):
        self.Q[-1] = self.Q[-2]
        self.S[-1] = self.S[-2]
        self._refresh_cell_state(-1)
        self._sync_boundary_face_state_from_ghost('right')

    def OutBound_Free_Outfall_re(self):
        self.Q[0] = self.Q[1]
        self.S[0] = self.S[1]
        self._refresh_cell_state(0)
        self._sync_boundary_face_state_from_ghost('left')

    def OutBound_Fix_level(self, level):
        section_name = self.cell_sections[-1]
        Ai = max(float(self.S[-2]), 1e-12)
        ui = self.Q[-2] / Ai
        chi_i = self._char_potential(self.cell_sections[-2], Ai)
        Ab = float(self.cross_section_table.get_area_by_level(section_name, level))
        Ab = max(Ab, 1e-12)
        chi_b = self._char_potential(section_name, Ab)
        ub = ui + chi_i - chi_b
        Q = Ab * ub
        self.S[-1] = Ab
        self.Q[-1] = Q
        self._refresh_cell_state(-1, level_hint=level)
        self._set_boundary_face_state('right', level=level, area=Ab, discharge=Q)
        if self.Implic_flag:
            self.V1[0] = self.S[-1] - self.S_old[-1]
            self.V1[1] = self.Q[-1] - self.Q_old[-1]

    def InBound_Fix_level(self, level):
        section_name = self.cell_sections[0]
        Ai = max(float(self.S[1]), 1e-12)
        ui = self.Q[1] / Ai
        chi_i = self._char_potential(self.cell_sections[1], Ai)
        Ab = float(self.cross_section_table.get_area_by_level(section_name, level))
        Ab = max(Ab, 1e-12)
        chi_b = self._char_potential(section_name, Ab)
        ub = ui - chi_i + chi_b
        Qb = Ab * ub
        self.S[0] = Ab
        self.Q[0] = Qb
        self._refresh_cell_state(0, level_hint=level)
        self._set_boundary_face_state('left', level=level, area=Ab, discharge=Qb)
        if self.Implic_flag:
            self.V0[0] = self.S[0] - self.S_old[0]
            self.V0[1] = self.Q[0] - self.Q_old[0]

    def InBound_Fix_level_V2(self, level, Fr_max=0.85, head_gain_factor=0.65, relax_Q=0.4, cap_du_factor=0.8, cap_dQ_factor=0.7):
        Ai = float(self.S[1])
        Ti = float(self.cross_section_table.get_width_by_area(self.cell_sections[1], Ai))
        Ti = max(Ti, 1e-08)
        ui = float(self.Q[1]) / max(Ai, 1e-12)
        ci = (self.g * Ai / Ti) ** 0.5
        chi_i = self._char_potential(self.cell_sections[1], Ai)
        sec_b = self.cell_sections[0]
        Ab = float(self.cross_section_table.get_area_by_level(sec_b, level))
        Tb = float(self.cross_section_table.get_width_by_area(sec_b, Ab))
        Tb = max(Tb, 1e-08)
        cb = (self.g * Ab / Tb) ** 0.5
        chi_b = self._char_potential(sec_b, Ab)
        ub = ui - chi_i + chi_b
        Frb = abs(ub) / max(cb, 1e-08)
        if Frb > Fr_max:
            ub = ub / max(abs(ub), 1e-12) * Fr_max * cb
        Hi = float(self.water_level[1])
        dH = level - Hi
        if dH >= 0.0:
            u_head = (2.0 * self.g * dH) ** 0.5
            ub = ub / max(abs(ub), 1e-12) * min(abs(ub), head_gain_factor * u_head)
        ub = max(ui - cap_du_factor * ci, min(ui + cap_du_factor * ci, ub))
        Qb_raw = ub * Ab
        cap_dQ = cap_dQ_factor * Ai * ci
        Qb_raw = max(self.Q[1] - cap_dQ, min(self.Q[1] + cap_dQ, Qb_raw))
        prev = getattr(self, 'prev_Qb_left', None)
        if prev is None:
            prev = Qb_raw
        Qb = prev + relax_Q * (Qb_raw - prev)
        self.prev_Qb_left = Qb
        self.S[0] = Ab
        self.Q[0] = Qb
        self._refresh_cell_state(0, level_hint=level)
        self._set_boundary_face_state('left', level=level, area=Ab, discharge=Qb, width=Tb)
        if getattr(self, 'Implic_flag', False):
            self.V0[0] = self.S[0] - self.S_old[0]
            self.V0[1] = self.Q[0] - self.Q_old[0]

    def OutBound_Fix_level_V2(self, level, Fr_max=0.85, head_gain_factor=0.65, relax_Q=0.4, cap_du_factor=0.8, cap_dQ_factor=0.7):
        Ai = float(self.S[-2])
        Ti = float(self.cross_section_table.get_width_by_area(self.cell_sections[-2], Ai))
        Ti = max(Ti, 1e-08)
        ui = float(self.Q[-2]) / max(Ai, 1e-12)
        ci = (self.g * Ai / Ti) ** 0.5
        chi_i = self._char_potential(self.cell_sections[-2], Ai)
        sec_b = self.cell_sections[-1]
        Ab = float(self.cross_section_table.get_area_by_level(sec_b, level))
        Tb = float(self.cross_section_table.get_width_by_area(sec_b, Ab))
        Tb = max(Tb, 1e-08)
        cb = (self.g * Ab / Tb) ** 0.5
        chi_b = self._char_potential(sec_b, Ab)
        ub = ui + chi_i - chi_b
        Frb = abs(ub) / max(cb, 1e-08)
        if Frb > Fr_max:
            ub = ub / max(abs(ub), 1e-12) * Fr_max * cb
        Hi = float(self.water_level[-2])
        dH = Hi - level
        if dH >= 0.0:
            u_head = (2.0 * self.g * dH) ** 0.5
            ub = ub / max(abs(ub), 1e-12) * min(abs(ub), head_gain_factor * u_head)
        ub = max(ui - cap_du_factor * ci, min(ui + cap_du_factor * ci, ub))
        Qb_raw = ub * Ab
        cap_dQ = cap_dQ_factor * Ai * ci
        Qb_raw = max(self.Q[-2] - cap_dQ, min(self.Q[-2] + cap_dQ, Qb_raw))
        prev = getattr(self, 'prev_Qb_right', None)
        if prev is None:
            prev = Qb_raw
        Qb = prev + relax_Q * (Qb_raw - prev)
        self.prev_Qb_right = Qb
        self.S[-1] = Ab
        self.Q[-1] = Qb
        self._refresh_cell_state(-1, level_hint=level)
        self._set_boundary_face_state('right', level=level, area=Ab, discharge=Qb, width=Tb)
        if getattr(self, 'Implic_flag', False):
            self.V1[0] = self.S[-1] - self.S_old[-1]
            self.V1[1] = self.Q[-1] - self.Q_old[-1]

    def InBound_Fix_level_V3(self, level, Fr_max=0.85, head_gain_factor=0.65, relax_Q=0.4, cap_du_factor=0.8, cap_dQ_factor=0.7, use_stabilizers=True, respect_supercritical=True, stage_on_face=None, q_hint=None, q_hint_blend=0.0, q_hint_cap_factor=0.0):
        g = getattr(self, 'g', 9.81)
        tinyA, tinyT, tinyC = (1e-12, 1e-08, 1e-08)
        if stage_on_face is None:
            stage_on_face = bool(getattr(self, 'bc_stage_on_face', False))
        ctx = self._prepare_stage_boundary_context('left', level, stage_on_face, tinyA, tinyT, g)
        if respect_supercritical and abs(ctx['ui']) >= ctx['ci']:
            self._apply_supercritical_stage_boundary_copy(ctx)
            return
        target = self._prepare_stage_boundary_target_state(ctx, tinyA, tinyT, g)
        if target['Ab'] <= 0.0:
            self._apply_empty_stage_boundary_state(ctx)
            return
        dry_entry, near_dry_entry = self._classify_stage_boundary_entry(ctx, tinyA)
        chi_bundle = self._resolve_stage_boundary_chi_bundle(ctx, target, dry_entry, near_dry_entry)
        ub = self._compute_stage_boundary_characteristic_velocity_with_explicit_chi(
            ctx,
            chi_bundle['inner_selected']['selected'],
            chi_bundle['target_selected']['selected'],
            None if chi_bundle['second_selected'] is None else chi_bundle['second_selected']['selected'],
        )
        stabilizer_state = self._apply_stage_boundary_stabilizers(
            ctx,
            target,
            ub,
            Fr_max=Fr_max,
            head_gain_factor=head_gain_factor,
            relax_Q=relax_Q,
            cap_du_factor=cap_du_factor,
            cap_dQ_factor=cap_dQ_factor,
            use_stabilizers=use_stabilizers,
            q_hint=q_hint,
            q_hint_blend=q_hint_blend,
            q_hint_cap_factor=q_hint_cap_factor,
            dry_entry=dry_entry,
            near_dry_entry=near_dry_entry,
        )
        stabilizer_state['chi_bundle'] = chi_bundle
        self._commit_stage_boundary_state(ctx, target['Ab'], stabilizer_state['Qb'], Tb=target.get('Tb'))
        self._append_stage_boundary_record(ctx, target, stabilizer_state)

    def OutBound_Fix_level_V3(self, level, Fr_max=0.85, head_gain_factor=0.65, relax_Q=0.4, cap_du_factor=0.8, cap_dQ_factor=0.7, use_stabilizers=True, respect_supercritical=True, stage_on_face=None):
        g = getattr(self, 'g', 9.81)
        tinyA, tinyT, tinyC = (1e-12, 1e-08, 1e-08)
        if stage_on_face is None:
            stage_on_face = bool(getattr(self, 'bc_stage_on_face', False))
        ctx = self._prepare_stage_boundary_context('right', level, stage_on_face, tinyA, tinyT, g)
        if respect_supercritical and abs(ctx['ui']) >= ctx['ci']:
            self._apply_supercritical_stage_boundary_copy(ctx)
            return
        target = self._prepare_stage_boundary_target_state(ctx, tinyA, tinyT, g)
        if target['Ab'] <= 0.0:
            self._apply_empty_stage_boundary_state(ctx)
            return
        dry_entry, near_dry_entry = self._classify_stage_boundary_entry(ctx, tinyA)
        chi_bundle = self._resolve_stage_boundary_chi_bundle(ctx, target, dry_entry, near_dry_entry)
        ub = self._compute_stage_boundary_characteristic_velocity_with_explicit_chi(
            ctx,
            chi_bundle['inner_selected']['selected'],
            chi_bundle['target_selected']['selected'],
            None if chi_bundle['second_selected'] is None else chi_bundle['second_selected']['selected'],
        )
        stabilizer_state = self._apply_stage_boundary_stabilizers(
            ctx,
            target,
            ub,
            Fr_max=Fr_max,
            head_gain_factor=head_gain_factor,
            relax_Q=relax_Q,
            cap_du_factor=cap_du_factor,
            cap_dQ_factor=cap_dQ_factor,
            use_stabilizers=use_stabilizers,
            dry_entry=dry_entry,
            near_dry_entry=near_dry_entry,
        )
        stabilizer_state['chi_bundle'] = chi_bundle
        self._commit_stage_boundary_state(ctx, target['Ab'], stabilizer_state['Qb'], Tb=target.get('Tb'))
        self._append_stage_boundary_record(ctx, target, stabilizer_state)

    def interpolate_uniformly(self):
        distances = np.sqrt(np.sum(np.diff(self.pos, axis=0) ** 2, axis=1))
        cumulative_distances = np.insert(np.cumsum(distances), 0, 0)
        target_distances = np.linspace(cumulative_distances[0], cumulative_distances[-1], self.cell_num + 1)
        cell_centers = (target_distances[:-1] + target_distances[1:]) / 2
        x_interp = np.interp(cell_centers, cumulative_distances, self.pos[:, 0])
        y_interp = np.interp(cell_centers, cumulative_distances, self.pos[:, 1])
        z_interp = np.interp(cell_centers, cumulative_distances, self.pos[:, 2])
        interpolated_pos = np.vstack((x_interp, y_interp, z_interp)).T
        section_distances = np.linspace(cumulative_distances[0], cumulative_distances[-1], len(self.section_name))
        cell_sections = []
        for center in cell_centers:
            closest_section_idx = np.argmin(np.abs(section_distances - center))
            cell_sections.append(self.section_name[closest_section_idx])
        cell_lengths = np.diff(target_distances)
        return (interpolated_pos, cell_sections, cell_lengths)

    def Calculate_cross_section_area_by_water_depth(self, points, water_depth):
        points = np.asarray(points, dtype=float)
        if points.ndim != 2 or points.shape[0] < 2:
            return 0.0
        min_y = float(np.min(points[:, 1]))
        level = min_y + max(float(water_depth), 0.0)
        area, _, _ = self._section_hydraulics_at_level(points, level)
        return area

    def _section_hydraulics_at_level(self, points, level):
        """Return wetted area, top width, and wetted perimeter for an absolute section level."""
        pts = np.asarray(points, dtype=float)
        if pts.ndim != 2 or pts.shape[0] < 2:
            return (0.0, 0.0, 0.0)
        if pts[0, 0] > pts[-1, 0]:
            pts = pts[::-1].copy()

        level = float(level)
        xs = pts[:, 0]
        zs = pts[:, 1]
        min_z = float(np.min(zs))
        max_z = float(np.max(zs))
        top_width = float(xs[-1] - xs[0])
        if level <= min_z + self.EPSILON:
            return (0.0, 0.0, 0.0)

        area = 0.0
        wetted_perimeter = 0.0
        wet_x = []

        for i in range(len(pts) - 1):
            x1, z1 = float(pts[i, 0]), float(pts[i, 1])
            x2, z2 = float(pts[i + 1, 0]), float(pts[i + 1, 1])
            dx = x2 - x1
            seg_len = float(np.hypot(dx, z2 - z1))
            d1 = level - z1
            d2 = level - z2

            if d1 <= 0.0 and d2 <= 0.0:
                continue

            if d1 >= 0.0 and d2 >= 0.0:
                area += 0.5 * (d1 + d2) * abs(dx)
                wetted_perimeter += seg_len
                wet_x.extend([x1, x2])
                continue

            denom = z2 - z1
            if abs(denom) <= self.EPSILON:
                continue
            frac = (level - z1) / denom
            frac = float(np.clip(frac, 0.0, 1.0))
            xi = x1 + frac * dx

            if d1 > 0.0:
                area += 0.5 * d1 * abs(xi - x1)
                wetted_perimeter += seg_len * frac
                wet_x.extend([x1, xi])
            else:
                area += 0.5 * d2 * abs(x2 - xi)
                wetted_perimeter += seg_len * (1.0 - frac)
                wet_x.extend([xi, x2])

        width = float(max(wet_x) - min(wet_x)) if wet_x else 0.0

        if level > max_z:
            extra_h = level - max_z
            area += extra_h * top_width
            wetted_perimeter += 2.0 * extra_h
            width = top_width

        return (float(area), float(width), float(wetted_perimeter))

    def _resolve_section_manning_for_table(self, section_name, default_n):
        """Resolve a section-local Manning n for DEB table construction.

        The unified CrossSectionTable remains a single main-channel table, but DEB should
        still reflect the roughness attached to the section consumers that use that table.
        When multiple real cells reference the same section name, use the median positive
        Manning value as a stable section representative. This keeps scalar-n cases
        unchanged and moves spatially varying n closer to MASCARET's section-wise debitance
        semantics.
        """
        values = []
        for i in range(1, self.cell_num + 1):
            if self.cell_sections[i] != section_name:
                continue
            val = float(self.n[i])
            if np.isfinite(val) and val > 0.0:
                values.append(val)
        if values:
            section_n = float(np.median(values))
        else:
            section_n = float(default_n)
        section_n = max(section_n, 1.0e-8)
        self.section_table_manning_used[section_name] = section_n
        return section_n

    def Current_sim_progress(self):
        total_time = self.sim_end_time - self.sim_start_time
        total_time = total_time.total_seconds()
        return self.current_sim_time / total_time

    def Create_cross_section_table(self, manning, num=300):
        # Build one hydraulic lookup table per section geometry.
        # Sampling coordinate:
        # - depth_slice: local water depth measured from the section minimum elevation (min_y)
        # Stored coordinates:
        # - depth_list: local depth above min_y
        # - level_list: absolute elevation = min_y + depth
        # - area-indexed fields: width, wetted perimeter, hydraulic radius, PRESS, DEB
        # PRESS is accumulated as g * integral(A(depth) d(depth)), i.e. the hydrostatic
        # pressure integral with local depth as the integration coordinate.
        # The builder now inserts an exact dry-state knot explicitly:
        # depth=0, area=0, width=0, wetted_perimeter=0, hydraulic_radius=0,
        # PRESS=0, DEB=0. Wet samples start strictly above the dry cutoff.
        # manning 由 np.unique(self.n) 传入，可能是 ndarray。
        default_n = float(np.atleast_1d(manning)[0])
        default_n = max(default_n, 1e-8)
        self.section_table_manning_used = {}
        for section_name in self.sections_data:
            n_val = self._resolve_section_manning_for_table(section_name, default_n)
            section_point = self._get_section_points_for_table(section_name)
            area_list = []
            level_list = []
            depth_list = []
            width_list = []
            wetted_perimeter_list = []
            hydraulic_radius_list = []
            press_list = []
            DEB = []
            xs = [pt[0] for pt in section_point]
            ys = [pt[1] for pt in section_point]
            max_y = np.max(ys)
            if self.refined_section_table:
                depth_range = max(float(np.max(ys) - np.min(ys)), self.water_depth_limit)
                extra_depth = max(5.0, 0.5 * depth_range)
                max_depth = depth_range + extra_depth
                target_dz = self.section_table_dz
                num_local = max(int(np.ceil(max_depth / target_dz)) + 1, int(num))
            else:
                depth_range = max(float(np.max(ys) - np.min(ys)), self.water_depth_limit)
                extra_depth = max(5.0, 0.5 * depth_range)
                max_depth = depth_range + extra_depth
                num_local = max(int(num), int(np.ceil(max_depth / max(self.section_table_dz, 0.05))) + 1)
            min_y = np.min(ys)
            wet_start_depth = float(np.nextafter(self.EPSILON, np.inf))
            wet_count = max(int(num_local) - 1, 1)
            wet_depth_slice = np.linspace(wet_start_depth, max_depth, num=wet_count)
            depth_list.append(0.0)
            level_list.append(float(min_y))
            area_list.append(0.0)
            width_list.append(0.0)
            wetted_perimeter_list.append(0.0)
            hydraulic_radius_list.append(0.0)
            DEB.append(0.0)
            for depth in wet_depth_slice:
                depth_list.append(depth)
                level = depth + min_y
                level_list.append(level)
                area, width, wetted_perimeter = self._section_hydraulics_at_level(section_point, level)
                area_list.append(area)
                width_list.append(width)
                wetted_perimeter = max(float(wetted_perimeter), self.EPSILON)
                wetted_perimeter_list.append(wetted_perimeter)
                hydraulic_radius_list.append(area_list[-1] / wetted_perimeter)
                s = float(area)
                r = float(area_list[-1] / wetted_perimeter)
                deb = s * r ** 0.66666666666667 / n_val
                DEB.append(float(deb))
            press_list.append(0.0)
            dz = np.diff(depth_list)
            for i in range(1, len(depth_list)):
                press = press_list[i - 1] + self.g * (area_list[i - 1] + area_list[i]) * dz[i - 1] / 2
                press_list.append(press)
            self.cross_section_table.add_table(name=section_name, depths=depth_list, level=level_list, areas=area_list, width=width_list, wetted_perimeter=wetted_perimeter_list, hydraulic_radius=hydraulic_radius_list, press=press_list, DEB=DEB)
        self._update_section_S_min()

    def Debug(self):
        import pandas as pd
        import numpy as np
        import os
        output_folder_path = os.path.join(self.output_folder_path, 'debug')
        os.makedirs(output_folder_path, exist_ok=True)

        def append_time_step_data(file_path, attr_name, new_data, time_id):
            if os.path.exists(file_path):
                df = pd.read_csv(file_path)
            else:
                df = pd.DataFrame()
            if new_data.ndim == 1:
                col_name = f'{attr_name}_{time_id}'
                new_df = pd.DataFrame({col_name: new_data})
            elif new_data.ndim == 2:
                n_cols = new_data.shape[1]
                new_dict = {}
                for i in range(n_cols):
                    col_name = f'{attr_name}_{time_id}_{i + 1}'
                    new_dict[col_name] = new_data[:, i]
                new_df = pd.DataFrame(new_dict)
            else:
                raise ValueError('new_data 必须为一维或二维数组')
            if not df.empty:
                if len(df) != len(new_df):
                    raise ValueError(f'原 CSV 文件的行数 ({len(df)}) 与新数据的行数 ({len(new_df)}) 不一致')
                df = pd.concat([df, new_df], axis=1)
            else:
                df = new_df
            df.to_csv(file_path, index=False)
            print(f"属性 '{attr_name}' (时间步 {time_id}) 数据已保存到 {file_path}")
        time_id = self.current_sim_time
        attributes = {'water_level': self.water_level, 'water_depth': self.water_depth, 'Q': self.Q, 'S': self.S, 'U': self.U, 'FR': self.FR, 'C': self.C, 'PRESS': self.PRESS, 'P': self.P, 'R': self.R, 'cell_press_source': self.cell_press_source, 'QIN': self.QIN, 'DTI': self.DTI, 'n': self.n, 'F_U': self.F_U, 'F_C': self.F_C, 'F_Q_SOURCE': self.F_Q_SOURCE, 'F_Friction_SOURCE': self.F_Friction_SOURCE, 'F_Singular_Head_Loss': self.F_Singular_Head_Loss, 'Lambda1': self.Lambda1, 'Lambda2': self.Lambda2, 'abs_Lambda1': self.abs_Lambda1, 'abs_Lambda2': self.abs_Lambda2, 'alpha1': self.alpha1, 'alpha2': self.alpha2, 'dissipation1': self.dissipation1, 'dissipation2': self.dissipation2, 'Vactor1': self.Vactor1, 'Vactor2': self.Vactor2, 'Vactor1_T': self.Vactor1_T, 'Vactor2_T': self.Vactor2_T, 'Flux_LOC': self.Flux_LOC, 'Flux_Source_left': self.Flux_Source_left, 'Flux_Source_right': self.Flux_Source_right, 'Flux_Source_center': self.Flux_Source_center, 'Flux_Friction_left': self.Flux_Friction_left, 'Flux_Friction_right': self.Flux_Friction_right, 'bottom_source': self.bottom_source, 'friction_source': self.friction_source, 'Flux': self.Flux, 'Debit_Flux': self.Debit_Flux, 'flag_LeVeque': self.flag_LeVeque}
        for name, data in attributes.items():
            file_path = os.path.join(output_folder_path, f'{self.file_name}_{name}.csv')
            try:
                append_time_step_data(file_path, name, data, time_id)
            except Exception as e:
                print(f"保存属性 '{name}' 时出错: {e}")

    def from_result_get_variable_at_time(self, nc_path, var_name, time_point, method='nearest'):
        ds = xr.open_dataset(nc_path)
        if var_name not in ds.data_vars:
            raise ValueError(f'变量 {var_name} 不存在，数据集变量有：{list(ds.data_vars)}')
        da = ds[var_name]
        if method:
            da_sel = da.sel(time=time_point, method=method)
        else:
            da_sel = da.sel(time=time_point)
        return da_sel

    def Get_nearest_cell_num(self, pos):
        coords_xy = self.cell_pos[:, :2]
        new_xy = np.array(pos)
        tree = cKDTree(coords_xy)
        dist, idx2 = tree.query(new_xy)
        if idx2 == 0:
            idx2 = 1
        if idx2 == -1:
            idx2 = -2
        return idx2

    def Fine_cell_property(self):
        if not self.section_interpolation_enabled or self.Interpolator is None:
            print('缺少 section_pos，跳过 Fine 断面插值优化')
            return
        print('优化网格参数......')
        for i in range(self.cell_num + 2):
            section_name = self.cell_sections[i]
            section_point = self.sections_data[section_name]
            ys = [pt[1] for pt in section_point]
            self.river_bed_height[i] = np.min(ys)
        z_pos = np.array([row[-1] for row in self.cell_pos])
        length = np.array(self.cell_lengths[0:-1])
        x = np.concatenate(([0], np.cumsum(length)))
        m, b = np.polyfit(x, z_pos, deg=1)
        y_fit = m * x + b
        for i in range(self.cell_num + 2):
            self.river_bed_height[i] = y_fit[i]
        for i in range(self.cell_num + 2):
            pos = self.cell_pos[i][0:2]
            new_section_name = f'Interpolator_{i}'
            section_point = self.Interpolator.get_section_at_xy(pos)
            self.Interpolator.visualize(pos)
            X = section_point['X'].copy()
            x_min = np.min(X)
            Z = section_point['Z'].copy()
            section_point = [[x - x_min, z] for x, z in zip(X, Z)]
            ys = [pt[1] for pt in section_point]
            y_min = np.min(ys)
            diff = y_min - self.river_bed_height[i]
            new_section_point = [[x, y - diff] for x, y in section_point]
            self.sections_data[new_section_name] = new_section_point
            self.cell_sections[i] = new_section_name
        self.Plot_fined_cell_property()

    def Fine_cell_property2(self):
        if not self.section_interpolation_enabled or self.Interpolator is None:
            print('缺少 section_pos，跳过 Fine 断面插值优化')
            return
        print('优化网格参数......')
        for i in range(self.cell_num + 2):
            section_name = self.cell_sections[i]
            section_point = self.sections_data[section_name]
            ys = [pt[1] for pt in section_point]
            self.river_bed_height[i] = np.min(ys)
        z_pos = np.array([row[-1] for row in self.cell_pos])
        length = np.array(self.cell_lengths[0:-1])
        x = np.concatenate(([0], np.cumsum(length)))
        m, b = np.polyfit(x, z_pos, deg=1)
        y_fit = m * x + b
        for i in range(self.cell_num + 2):
            self.river_bed_height[i] = y_fit[i]
        for i in range(self.cell_num + 2):
            pos = self.cell_pos[i][0:2]
            new_section_name = f'Interpolator_{i}'
            section_point = self.Interpolator.get_section_at_xy(pos)
            X = section_point['X'].copy()
            x_min = np.min(X)
            Z = section_point['Z'].copy()
            section_point = [[x - x_min, z] for x, z in zip(X, Z)]
            ys = [pt[1] for pt in section_point]
            y_min = np.min(ys)
            diff = y_min - self.river_bed_height[i]
            new_section_point = [[x, y - diff] for x, y in section_point]
            self.sections_data[new_section_name] = new_section_point
            self.cell_sections[i] = new_section_name
            if i >= self.cell_num:
                self.Slop[i] = (self.river_bed_height[i - 1] - self.river_bed_height[i]) / self.cell_lengths[i]
            else:
                self.Slop[i] = (self.river_bed_height[i] - self.river_bed_height[i + 1]) / self.cell_lengths[i]
            if self.Slop[i] == 0:
                self.Slop[i] = self.EPSILON

    def Plot_fined_cell_property(self):
        fig, axs = plt.subplots(2, 1, figsize=(40, 50))
        ax_bottom = axs[0]
        ax_bottom.plot(self.cell_pos[:, 0], self.river_bed_height, '-o')
        ax_bottom.grid(True)
        ax_shape = axs[1]
        for i in range(self.cell_num + 2):
            section_name = self.cell_sections[i]
            section_point = self.sections_data[section_name]
            xs = [pt[0] for pt in section_point]
            ys = [pt[1] for pt in section_point]
            ax_shape.plot(xs, ys, label=f'{i}')
        plt.legend()
        save_path = os.path.join(self.output_folder_path, f'{self.model_name}_fined_cell_property.png')
        plt.savefig(save_path, dpi=100)
        plt.close()

    def Init_water_serface(self):
        if self.Depth_profile_init and self.init_depth_profile is not None:
            profile = np.asarray(self.init_depth_profile, dtype=float)
            if profile.size == self.cell_num:
                self.water_depth[1:-1] = profile
                self.water_depth[0] = self.water_depth[1]
                self.water_depth[-1] = self.water_depth[-2]
            elif profile.size == self.cell_num + 2:
                self.water_depth[:] = profile
            else:
                raise ValueError('init_depth_profile 长度必须为 cell_num 或 cell_num+2')
            self.water_level = self.water_depth + self.river_bed_height
            return
        if self.Depth_init:
            print('基于水深初始化......')
            self.water_depth[:] = self.init_depth
            self.water_level = self.water_depth + self.river_bed_height
        if self.Level_init:
            print('基于水位初始化......')
            self.water_level[:] = self.init_water_level
            self.water_depth = self.water_level - self.river_bed_height

    def Set_init_watr_depth(self, depth):
        self.Depth_init = True
        self.init_depth = depth

    def Set_init_water_depth_profile(self, depth_profile):
        self.Depth_profile_init = True
        self.init_depth_profile = np.asarray(depth_profile, dtype=float)

    def Set_init_water_level(self, level):
        self.Level_init = True
        self.init_water_level = level

    def Plot_section_Press_table(self):
        plt.close()
        for i in range(self.cell_num):
            index = i + 1
            section_name = self.cell_sections[index]
            x = []
            press = []
            for j in range(20):
                s = self.cross_section_table.get_area_by_depth(section_name, j)
                x.append(j)
                press.append(s)
            plt.plot(x, press, label=f'{index}')
        plt.legend()
        plt.grid(True)
        plt.title('depth - S')
        plt.show()
