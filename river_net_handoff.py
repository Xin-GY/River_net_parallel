from __future__ import annotations

import datetime as dt
import math
import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

import matplotlib
import networkx as nx
import numpy as np

from river_for_net import River


matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt  # noqa: E402


def _parse_sim_time(value: object) -> dt.datetime:
    if isinstance(value, dt.datetime):
        return value
    text = str(value)
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return dt.datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unsupported time format: {text}")


class Rivernet:
    def __init__(self, Topology, model_data, verbos: bool = True):
        self.verbos = bool(verbos)
        self.Fine_flag = False
        self.model_data = dict(model_data)
        self.topology = dict(Topology)
        self.G = nx.DiGraph()
        self.boundaries = {}
        self.ALLOWED_OUT_BTYPE = {"free", "fix_level"}
        self.ALLOWED_IN_BTYPE = {"flow", "fix_level"}

        self.sim_start_time = _parse_sim_time(self.model_data["sim_start_time"])
        self.sim_end_time = _parse_sim_time(self.model_data["sim_end_time"])
        self.total_sim_time = (self.sim_end_time - self.sim_start_time).total_seconds()

        self.current_sim_time = 0.0
        self.cfl_allowed_dt = 1.0e-5
        self.DT = 1.0e-5
        self.step_count = 0
        self.sub_step_count = 0
        self.sub_step_time = 0.0
        self.sub_step_max_dt = 0.0
        self.sub_step_min_dt = 999999.0
        self.sub_step_start_time = 0.0
        self.sub_step_caculation_time_using = 0.0
        self.caculation_time = 0.0
        self.caculation_start_time = 0.0

        self.alpha = 1.2
        self.relax = float(self.model_data.get("junction_relax", 0.5))
        self.max_iteration = int(self.model_data.get("max_iteration", 20))
        self.g = 9.81
        self.JPWSPC_EPS = 1.0e-3
        self.JPWSPC_Q_limit = 1.0e-3

        self.parallel_mode = str(self.model_data.get("parallel_mode", "thread")).lower()
        self.parallel_workers = max(int(self.model_data.get("parallel_workers", 0)), 0)
        self._pool = None
        if self.parallel_workers >= 2:
            self._pool = ThreadPoolExecutor(
                max_workers=self.parallel_workers,
                thread_name_prefix="Rivernet",
            )

        self.Create_Rivernet()

    def __del__(self):
        if self._pool is not None:
            self._pool.shutdown(wait=False)

    def _iter_rivers(self):
        return [data["river"] for _, _, data in self.G.edges(data=True) if data.get("river") is not None]

    def _run_river_method(self, method_name: str):
        rivers = self._iter_rivers()
        if self._pool is None:
            for river in rivers:
                getattr(river, method_name)()
            return
        futures = [self._pool.submit(getattr(river, method_name)) for river in rivers]
        for future in futures:
            future.result()

    def _call_stage_in(self, river: River, level: float):
        if hasattr(river, "InBound_Fix_level_V3"):
            river.InBound_Fix_level_V3(level)
        else:
            river.InBound_Fix_level(level)

    def _call_stage_out(self, river: River, level: float):
        if hasattr(river, "OutBound_Fix_level_V3"):
            river.OutBound_Fix_level_V3(level)
        else:
            river.OutBound_Fix_level(level)

    def _call_inflow(self, river: River, flow: float):
        if hasattr(river, "InBound_In_Q2"):
            river.InBound_In_Q2(flow)
        else:
            river.InBound_In_Q(flow)

    def _build_river_model_data(self, info: dict) -> dict:
        sim_data = dict(self.model_data)
        sim_data.update(info.get("model_data", {}))
        sim_data["model_name"] = info["name"]
        sim_data["sim_start_time"] = str(self.model_data["sim_start_time"])
        sim_data["sim_end_time"] = str(self.model_data["sim_end_time"])
        sim_data["time_step"] = float(self.model_data["time_step"])
        sim_data["output_path"] = str(self.model_data["output_path"])
        sim_data["CFL"] = float(self.model_data["CFL"])
        sim_data["n"] = float(info["manning"])
        sim_data.setdefault("save_min_interval", float(self.model_data.get("time_step", 0.0)))
        sim_data.setdefault("bc_use_general_chi", True)
        sim_data.setdefault("bc_general_chi_candidate_mode", "guarded_clamp")
        sim_data.setdefault("bc_general_chi_guard_selector", "closure_q_delta")
        sim_data.setdefault("bc_general_chi_guard_q_delta", 0.005)
        sim_data.setdefault("bc_use_order2_extrap", True)
        sim_data.setdefault("bc_use_order2_extrap_flow", True)
        sim_data.setdefault("bc_use_order2_extrap_stage", True)
        return sim_data

    def Create_Rivernet(self):
        for (u, v), info in self.topology.items():
            river = River(
                info["river_data"],
                info["section_data"],
                info.get("section_pos"),
                self._build_river_model_data(info),
            )
            self.G.add_edge(u, v, river=river, name=info["name"])
            if self.verbos:
                print(f"river {info['name']} created")

    def classfy_nodes(self):
        self.internal_nodes = []
        self.external_in_nodes = []
        self.external_out_nodes = []
        self.isolated_nodes = []

        for node in self.G.nodes():
            indeg = self.G.in_degree(node)
            outdeg = self.G.out_degree(node)
            deg = indeg + outdeg
            if deg == 0:
                self.isolated_nodes.append(node)
            elif deg == 1:
                if indeg == 1 and outdeg == 0:
                    self.external_out_nodes.append(node)
                elif indeg == 0 and outdeg == 1:
                    self.external_in_nodes.append(node)
            else:
                self.internal_nodes.append(node)

        self.external_nodes = self.external_in_nodes + self.external_out_nodes

    def set_boundary(self, node: str, btype: str, data=None):
        if not all(hasattr(self, name) for name in ("internal_nodes", "external_in_nodes", "external_out_nodes")):
            self.classfy_nodes()

        if node in self.external_in_nodes:
            if btype not in self.ALLOWED_IN_BTYPE:
                raise ValueError(f"{node} invalid inflow boundary type: {btype}")
        elif node in self.external_out_nodes:
            if btype not in self.ALLOWED_OUT_BTYPE:
                raise ValueError(f"{node} invalid outflow boundary type: {btype}")
        else:
            raise ValueError(f"{node} is not an external boundary node")

        if data is None:
            self.boundaries[node] = {"type": btype, "call": (lambda t: None)}
            return

        if callable(data):
            self.boundaries[node] = {"type": btype, "call": data}
            return

        box = [float(data)]
        self.boundaries[node] = {
            "type": btype,
            "call": (lambda t, _box=box: _box[0]),
            "_val": box,
        }

    def update_const(self, node: str, new_value: float):
        item = self.boundaries.get(node)
        if not item or "_val" not in item:
            raise TypeError(f"{node} is not a mutable constant boundary")
        item["_val"][0] = float(new_value)

    def update_func(self, node: str, new_func: Callable[[float], float]):
        if not callable(new_func):
            raise TypeError("new_func must be callable")
        if node not in self.boundaries:
            raise KeyError(f"{node} boundary not configured")
        self.boundaries[node]["call"] = new_func

    def update_type(self, node: str, new_type: str):
        if node not in self.boundaries:
            raise KeyError(f"{node} boundary not configured")
        self.boundaries[node]["type"] = new_type

    def get_boundary_value(self, node: str, t: float):
        item = self.boundaries.get(node)
        if item is None:
            raise KeyError(f"{node} boundary not configured")
        return item["type"], item["call"](t)

    def evaluate_all_boundaries(self, t: float):
        return {node: {"type": item["type"], "value": item["call"](t)} for node, item in self.boundaries.items()}

    def call_river_function_by_name(self, function_name: str):
        self._run_river_method(function_name)

    def Fine_cell_property_net(self):
        self.call_river_function_by_name("Fine_cell_property2")
        self.Fine_flag = True

    def Init_water_surface_net(self):
        self.call_river_function_by_name("Init_water_serface")

    def Init_cell_property_net(self):
        fine = bool(self.Fine_flag)
        for river in self._iter_rivers():
            river.Init_cell_proprity(fine)

    def Save_basic_data_net(self):
        self.call_river_function_by_name("Save_Basic_data")

    def Caculate_face_U_C_net(self):
        self.call_river_function_by_name("Caculate_face_U_C")

    def Caculate_Roe_matrix_net(self):
        self.call_river_function_by_name("Caculate_Roe_matrix")

    def Caculate_Source_term_net(self):
        self.call_river_function_by_name("Caculate_source_term_2")

    def Caculate_Roe_flux_net(self):
        self.call_river_function_by_name("Caculate_Roe_Flux_2")

    def Assemble_flux_net(self):
        self.call_river_function_by_name("Assemble_Flux_2")

    def Update_cell_property_net(self):
        self.call_river_function_by_name("Update_cell_proprity2")

    def Save_step_result_net(self):
        self.call_river_function_by_name("Save_result_per_time_step")

    def Resample_and_Save_result_net(self):
        for river in self._iter_rivers():
            if hasattr(river, "Check_Resample_and_Save_Output_result"):
                river.Check_Resample_and_Save_Output_result()
            else:
                river.Resample_and_Save_Output_result()

    def Caculate_global_CFL(self):
        dt_list = [river.Caculate_CFL_time_for_river_net() for river in self._iter_rivers()]
        if not dt_list:
            raise RuntimeError("rivernet contains no river objects")
        self.cfl_allowed_dt = float(min(dt_list))
        if self.verbos:
            print(f"global CFL dt = {self.cfl_allowed_dt:.6f}s")

    def Set_global_time_step(self, dt_value: float):
        for river in self._iter_rivers():
            river.set_next_dt(dt_value)

    def Update_boundary_conditions(self):
        self.Update_external_boundary_conditions()
        self.Update_internal_boundary_conditions()

    def Update_external_boundary_conditions(self):
        for node in self.external_in_nodes:
            btype, value = self.get_boundary_value(node, self.current_sim_time)
            for _, _, data in self.G.out_edges(node, data=True):
                river = data["river"]
                if btype == "flow":
                    self._call_inflow(river, float(value))
                elif btype == "fix_level":
                    self._call_stage_in(river, float(value))

        for node in self.external_out_nodes:
            btype, value = self.get_boundary_value(node, self.current_sim_time)
            for _, _, data in self.G.in_edges(node, data=True):
                river = data["river"]
                if btype == "free":
                    river.OutBound_Free_Outfall()
                elif btype == "fix_level":
                    self._call_stage_out(river, float(value))

    def Caculate_node_average_level_at_real_cell(self, node):
        levels = []
        for _, _, data in self.G.in_edges(node, data=True):
            levels.append(float(data["river"].water_level[-2]))
        for _, _, data in self.G.out_edges(node, data=True):
            levels.append(float(data["river"].water_level[1]))
        return float(np.mean(levels)) if levels else float("nan")

    def Caculate_node_average_level_at_ghost_cell(self, node):
        levels = []
        for _, _, data in self.G.in_edges(node, data=True):
            levels.append(float(data["river"].water_level[-1]))
        for _, _, data in self.G.out_edges(node, data=True):
            levels.append(float(data["river"].water_level[0]))
        return float(np.mean(levels)) if levels else float("nan")

    def Caculate_node_Ac_at_ghost_cell(self, node):
        ac = 0.0
        eps = 1.0e-12
        for _, _, data in self.G.in_edges(node, data=True):
            river = data["river"]
            area = max(float(river.S[-1]), eps)
            width = max(float(river.cross_section_table.get_width_by_area(river.cell_sections[-1], area)), 1.0e-8)
            flow = float(river.Q[-1])
            ac += math.sqrt(self.g * area * width) - flow * width / area
        for _, _, data in self.G.out_edges(node, data=True):
            river = data["river"]
            area = max(float(river.S[0]), eps)
            width = max(float(river.cross_section_table.get_width_by_area(river.cell_sections[0], area)), 1.0e-8)
            flow = float(river.Q[0])
            ac += math.sqrt(self.g * area * width) + flow * width / area
        return self.g * ac

    def Apply_node_target_level(self, node, level: float):
        for _, _, data in self.G.in_edges(node, data=True):
            self._call_stage_out(data["river"], level)
        for _, _, data in self.G.out_edges(node, data=True):
            self._call_stage_in(data["river"], level)

    def Get_node_clear_flow_at_ghost_cell_net(self, node):
        pure_q = 0.0
        for _, _, data in self.G.in_edges(node, data=True):
            pure_q += float(data["river"].Q[-1])
        for _, _, data in self.G.out_edges(node, data=True):
            pure_q -= float(data["river"].Q[0])
        return pure_q

    def Update_internal_boundary_conditions(self):
        for node in self.internal_nodes:
            node_level = self.Caculate_node_average_level_at_real_cell(node)
            if not np.isfinite(node_level):
                continue
            node_level = max(float(node_level), 0.0)

            for iteration in range(1, self.max_iteration + 1):
                self.Apply_node_target_level(node, node_level)
                ac = self.Caculate_node_Ac_at_ghost_cell(node)
                pure_q = self.Get_node_clear_flow_at_ghost_cell_net(node)
                dz = 0.0 if abs(ac) <= self.JPWSPC_EPS else pure_q / ac
                node_level = max(node_level + self.relax * dz, 0.0)

                level_scale = max(abs(node_level), 1.0)
                if abs(dz) / level_scale < 1.0e-5 and abs(pure_q) < self.JPWSPC_Q_limit:
                    self.Apply_node_target_level(node, node_level)
                    break

                if iteration == self.max_iteration:
                    self.Apply_node_target_level(node, node_level)

    def print_evolve_info(self):
        td = dt.timedelta(seconds=float(self.current_sim_time))
        days = td.days
        hours, rem = divmod(td.seconds, 3600)
        minutes, seconds = divmod(rem, 60)
        total_time_use = time.perf_counter() - self.caculation_start_time
        print(
            f"sim={days}d {hours}h {minutes}m {seconds}s, "
            f"sub_steps={self.sub_step_count}, "
            f"sub_step_wall={self.sub_step_caculation_time_using:.2f}s, "
            f"dt_range=[{self.sub_step_min_dt:.6f}, {self.sub_step_max_dt:.6f}]s, "
            f"wall={total_time_use:.2f}s"
        )

    def _evolve_base(self, yield_step: float):
        yield_flag = False
        self.sub_step_start_time = time.perf_counter()
        self.caculation_start_time = time.perf_counter()

        while self.current_sim_time < self.total_sim_time:
            self.Set_global_time_step(self.DT)
            self.current_sim_time += self.DT
            self.step_count += 1
            self.sub_step_time += self.DT
            self.sub_step_count += 1
            self.sub_step_max_dt = max(self.sub_step_max_dt, self.DT)
            self.sub_step_min_dt = min(self.sub_step_min_dt, self.DT)

            self.Update_boundary_conditions()
            self.Caculate_face_U_C_net()
            self.Caculate_Roe_matrix_net()
            self.Caculate_Source_term_net()
            self.Caculate_Roe_flux_net()
            self.Assemble_flux_net()
            self.Update_cell_property_net()
            self.Save_step_result_net()

            if yield_flag:
                self.sub_step_caculation_time_using = time.perf_counter() - self.sub_step_start_time
                yield self.current_sim_time
                yield_flag = False
                self.sub_step_start_time = time.perf_counter()
                self.sub_step_time = 0.0
                self.sub_step_count = 0
                self.sub_step_max_dt = 0.0
                self.sub_step_min_dt = 999999.0

            if self.current_sim_time >= self.total_sim_time:
                break

            self.Caculate_global_CFL()

            if self.current_sim_time + self.cfl_allowed_dt > self.total_sim_time + 1.0e-5:
                self.DT = self.total_sim_time - self.current_sim_time
            elif self.sub_step_time + self.cfl_allowed_dt > yield_step + 1.0e-5:
                self.DT = yield_step - self.sub_step_time
                yield_flag = True
            else:
                self.DT = self.cfl_allowed_dt

            self.DT = max(float(self.DT), 1.0e-5)

        self.caculation_time = time.perf_counter() - self.caculation_start_time
        self.Resample_and_Save_result_net()

    def Evolve(self, yield_step=None):
        if yield_step is None:
            yield_step = float(self.model_data["time_step"])
        else:
            yield_step = float(yield_step)

        if self.Fine_flag:
            self.Fine_cell_property_net()

        self.Init_water_surface_net()
        self.Init_cell_property_net()
        self.Save_basic_data_net()
        self.Caculate_global_CFL()
        self.DT = min(max(self.cfl_allowed_dt, 1.0e-5), max(self.total_sim_time, 1.0e-5))

        for current_time in self._evolve_base(yield_step):
            yield current_time

    def export_png(
        self,
        path="rivernet.png",
        figsize=(9, 6),
        layout="spring",
        show_node_labels=True,
        show_edge_labels=True,
        dpi=400,
    ):
        if not all(hasattr(self, name) for name in ("internal_nodes", "external_in_nodes", "external_out_nodes")):
            self.classfy_nodes()

        count = max(len(self.G), 1)
        if layout == "spring":
            pos = nx.spring_layout(self.G, seed=42, k=1.0 / math.sqrt(count))
        elif layout == "kamada_kawai":
            pos = nx.kamada_kawai_layout(self.G)
        elif layout == "circular":
            pos = nx.circular_layout(self.G)
        elif layout == "random":
            pos = nx.random_layout(self.G, seed=42)
        else:
            raise ValueError(f"unknown layout: {layout}")

        color_internal = "#4C78A8"
        color_external_in = "#F58518"
        color_external_out = "#54A24B"
        node_size_internal = 700
        node_size_external = 600

        fig, ax = plt.subplots(figsize=figsize)
        nx.draw_networkx_nodes(
            self.G,
            pos,
            nodelist=self.internal_nodes,
            node_color=color_internal,
            node_size=node_size_internal,
            ax=ax,
            label="internal",
        )
        nx.draw_networkx_nodes(
            self.G,
            pos,
            nodelist=self.external_in_nodes,
            node_color=color_external_in,
            node_size=node_size_external,
            ax=ax,
            label="external_in",
        )
        nx.draw_networkx_nodes(
            self.G,
            pos,
            nodelist=self.external_out_nodes,
            node_color=color_external_out,
            node_size=node_size_external,
            ax=ax,
            label="external_out",
        )
        nx.draw_networkx_edges(
            self.G,
            pos,
            ax=ax,
            arrows=True,
            arrowstyle="-|>",
            arrowsize=18,
            width=1.6,
            connectionstyle="arc3,rad=0.05",
        )

        if show_node_labels:
            nx.draw_networkx_labels(self.G, pos, font_size=10, ax=ax)

        if show_edge_labels:
            edge_labels = {
                (u, v): data.get("name")
                for u, v, data in self.G.edges(data=True)
                if data.get("name")
            }
            if edge_labels:
                nx.draw_networkx_edge_labels(self.G, pos, edge_labels=edge_labels, font_size=9, ax=ax)

        ax.legend(loc="best", frameon=False)
        ax.set_axis_off()
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        plt.tight_layout()
        plt.savefig(path, dpi=dpi, bbox_inches="tight")
        plt.close(fig)


RiverNet = Rivernet
