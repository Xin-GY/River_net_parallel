import os

# ===== OpenMP / BLAS 线程控制（必须放在数值库导入之前） =====
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OMP_MAX_ACTIVE_LEVELS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")
os.environ.setdefault("KMP_WARNINGS", "0")

# -*- coding: utf-8 -*-
# Auto-generated single-file: river + rivernet with numba & parallel patches
# Source: river_for_net.py + Rivernet.py

import datetime
import math
import numpy as np
import pandas as pd
import config as config
from shapely.geometry import Polygon, box, LineString, Point
from scipy.sparse import bmat
from scipy.sparse.linalg import spsolve
import matplotlib
import xarray as xr
try:
    matplotlib.use('TkAgg')
except Exception:
    matplotlib.use('Agg')
import matplotlib.pyplot as plt
from concurrent.futures import ProcessPoolExecutor
from scipy.spatial import cKDTree  # 可选，用于加速查询
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
from shapely.ops import substring
from itertools import combinations
import os
from scipy.interpolate import UnivariateSpline, CubicSpline
from pyproj import Transformer
from multiprocessing import Process, Queue

# 断面插值
class SectionInterpolator:
    """
    用于在任意平面XY位置插值河道断面。
    输入：
      section_data: dict, key=断面名, value=list of [x_local, elevation]
      section_pos: dict, key=断面名, value=[x, y]平面坐标
      n_samples: int, 每个断面重采样点数
    方法：
      get_section_at_xy(pt_xy) -> (n_samples, 2) ndarray: [x_local, elevation]
    """
    def __init__(self, section_data, section_pos, n_samples=100):
        self.n_samples = n_samples
        # 转换输入数据格式
        self.section_data = {
            name: np.array(pts, dtype=float)
            for name, pts in section_data.items()
        }
        self.section_pos = {
            name: np.array(pos, dtype=float)
            for name, pos in section_pos.items()
        }
        # 所有断面名字
        self.names = list(self.section_pos.keys())
        # 推断上下游顺序
        self.section_order = self._infer_order()
        # 按顺序提取坐标并计算累计沿河距离
        self.ordered_coords = [self.section_pos[nm] for nm in self.section_order]
        self.s_vals = self._compute_s_vals()
        # 重采样所有断面
        self.resampled = self._resample_sections()

    def _infer_order(self):
        # PCA 方法，根据断面坐标投影找主方向
        coords = np.vstack([self.section_pos[nm] for nm in self.names])
        ctr = coords.mean(axis=0)
        coords_ctr = coords - ctr
        cov = coords_ctr.T @ coords_ctr
        eigvals, eigvecs = np.linalg.eigh(cov)
        pc1 = eigvecs[:, np.argmax(eigvals)]
        proj = coords_ctr @ pc1
        sorted_idx = np.argsort(proj)
        return [self.names[i] for i in sorted_idx]

    def _compute_s_vals(self):
        # 计算相邻断面间累积距离
        s_vals = [0.0]
        for i in range(len(self.ordered_coords) - 1):
            p0 = self.ordered_coords[i]
            p1 = self.ordered_coords[i+1]
            dist = np.linalg.norm(p1 - p0)
            s_vals.append(s_vals[-1] + dist)
        return s_vals

    def _resample_sections(self):
        res = {}
        for name, arr in self.section_data.items():
            x0, z0 = arr[:,0], arr[:,1]
            x_new = np.linspace(x0.min(), x0.max(), self.n_samples)
            z_new = np.interp(x_new, x0, z0)
            res[name] = np.vstack([x_new, z_new]).T
        return res

    def _project_onto_river(self, pt):
        # 将查询点投影到河道折线，返回沿河距离
        best = (np.inf, None)
        for i in range(len(self.ordered_coords) - 1):
            P = self.ordered_coords[i]
            Q = self.ordered_coords[i+1]
            v = Q - P
            t = np.dot(pt - P, v) / np.dot(v, v)
            t = np.clip(t, 0.0, 1.0)
            proj = P + t * v
            d = np.linalg.norm(pt - proj)
            s = self.s_vals[i] + t * (self.s_vals[i+1] - self.s_vals[i])
            if d < best[0]:
                best = (d, s)
        return best[1]

    def get_section_at_xy(self, pt_xy):
        """
        在平面坐标 pt_xy 处插值断面。
        返回：(n_samples, 2) ndarray，第一列为局部横向坐标，第二列为高程
        """
        pt = np.array(pt_xy, dtype=float)
        s = self._project_onto_river(pt)
        # 精确匹配
        for nm, sv in zip(self.section_order, self.s_vals):
            if np.isclose(s, sv):
                return self.resampled[nm].copy()
        # 区间插值
        idx = np.searchsorted(self.s_vals, s)
        if idx == 0 or idx == len(self.s_vals):
            raise ValueError("查询点超出断面范围")
        n1, n2 = self.section_order[idx-1], self.section_order[idx]
        s1, s2 = self.s_vals[idx-1], self.s_vals[idx]
        sec1, sec2 = self.resampled[n1], self.resampled[n2]
        t = (s - s1) / (s2 - s1)
        x = sec1[:,0]
        z = (1-t) * sec1[:,1] + t * sec2[:,1]
        return np.vstack([x, z]).T

# 断面插值第二代
class CrossSectionModel:
    def __init__(self, section_data, section_pos, n_samples=100):
        """
        初始化截面模型。
        :param section_data: dict, key=名称, value=list of [x, z] points
        :param section_pos: dict, key=名称, value=[bx, by] 基点坐标
        :param n_samples: 重采样点数量
        """
        self.section_data = section_data
        self.section_pos = section_pos
        self.n_samples = n_samples
        # 重采样
        self.resampled = {}
        for name, pts in section_data.items():
            arr = np.array(pts, float)
            x0, z0 = arr[:,0], arr[:,1]
            x_new = np.linspace(x0.min(), x0.max(), n_samples)
            z_new = np.interp(x_new, x0, z0)
            self.resampled[name] = np.vstack([x_new, z_new]).T
        # 原始断面坐标
        self.names = list(section_data.keys())
        coords = np.array([section_pos[n] for n in self.names], float)
        self.original_coords = coords
        # PCA求主方向
        mean_coord = coords.mean(axis=0)
        ctr = coords - mean_coord
        cov = ctr.T @ ctr
        eigvals, eigvecs = np.linalg.eig(cov)
        u = eigvecs[:, np.argmax(eigvals)]
        self.u = u / np.linalg.norm(u)
        self.mean_coord = mean_coord
        # 投影并排序计算累积距离
        proj_vals = (coords - mean_coord) @ self.u
        idx = np.argsort(proj_vals)
        self.sorted_names = [self.names[i] for i in idx]
        self.sorted_coords = coords[idx]
        self.s_vals = np.zeros(len(idx))
        for i in range(1, len(idx)):
            self.s_vals[i] = self.s_vals[i-1] + np.linalg.norm(
                self.sorted_coords[i] - self.sorted_coords[i-1]
            )
        self.proj_vals = proj_vals

    def get_section_at_xy(self, pt_xy):
        """
        给定查询点(pt_x, pt_y)，返回截面坐标和标签。
        :param pt_xy: [x, y]
        :return: dict with keys 'X', 'Y', 'Z', 'label'
        """
        pt = np.array(pt_xy, float)
        # 投影到主方向获得s_cut
        s_cut = (pt - self.mean_coord) @ self.u
        s_min, s_max = self.proj_vals.min(), self.proj_vals.max()
        n = self.n_samples
        # 超出范围 -> 最近断面
        if s_cut < s_min or s_cut > s_max:
            dists = np.linalg.norm(self.original_coords - pt, axis=1)
            idx_near = np.argmin(dists)
            name = self.names[idx_near]
            arr = self.resampled[name]
            bx, by = self.section_pos[name]
            X = arr[:,0] + bx
            Y = np.full(n, by)
            Z = arr[:,1]
            label = f"NearestSection@{name}"
        else:
            # 插值逻辑
            best = (np.inf, None, None, None, None, None)
            for i in range(len(self.s_vals)-1):
                P, Q = self.sorted_coords[i], self.sorted_coords[i+1]
                v = Q - P
                t0 = np.dot(pt - P, v) / np.dot(v, v)
                t0 = np.clip(t0, 0.0, 1.0)
                proj_pt = P + t0*v
                d = np.linalg.norm(pt - proj_pt)
                s = self.s_vals[i] + t0*(self.s_vals[i+1] - self.s_vals[i])
                if d < best[0]:
                    best = (d, s, proj_pt, i, i+1, t0)
            _, _, proj_pt, i1, i2, t = best
            name1 = self.sorted_names[i1]
            name2 = self.sorted_names[i2]
            sec1 = self.resampled[name1]
            sec2 = self.resampled[name2]
            bx, by = proj_pt
            X = proj_pt[0] + sec1[:,0]
            Y = np.full(n, proj_pt[1])
            Z = (1-t)*sec1[:,1] + t*sec2[:,1]
            label = f"SectionInterp@{pt_xy}"
        return {'X': X, 'Y': Y, 'Z': Z, 'label': label}

    def visualize(self, pt_xy):
        """
        可视化3D面与高亮截面，以及生成二维剖面图。
        :param pt_xy: [x, y]
        """
        # 构建3D网格面
        n = len(self.sorted_names)
        m = self.n_samples
        X = np.zeros((n, m))
        Y = np.zeros_like(X)
        Z = np.zeros_like(X)
        for i, name in enumerate(self.sorted_names):
            bx, by = self.section_pos[name]
            arr = self.resampled[name]
            X[i] = arr[:,0] + bx
            Y[i] = by
            Z[i] = arr[:,1]
        fig = plt.figure(figsize=(10,6))
        ax = fig.add_subplot(111, projection='3d')
        # 绘所有断面
        for name in self.sorted_names:
            pts = np.array(self.section_data[name])
            bx, by = self.section_pos[name]
            ax.plot(pts[:,0]+bx, np.full_like(pts[:,0], by), pts[:,1], c='gray', alpha=0.5)
            arr = self.resampled[name]
            ax.plot(arr[:,0]+bx, np.full(m,by), arr[:,1], c='gray', alpha=0.7)
        ax.plot_surface(X, Y, Z, cmap='viridis', alpha=0.6, rstride=1, cstride=1)
        # 获取截面并高亮
        sec = self.get_section_at_xy(pt_xy)
        ax.plot(sec['X'], sec['Y'], sec['Z'], c='red', lw=3, label=sec['label'])
        ax.set_xlabel('X')
        ax.set_ylabel('Y')
        ax.set_zlabel('Z')
        ax.legend()
        plt.tight_layout()
        plt.show()
        # 二维剖面图
        plt.figure(figsize=(6,4))
        plt.plot(sec['X'], sec['Z'], '-o', c='red', label=sec['label'])
        plt.xlabel('X (m)')
        plt.ylabel('Z (m)')
        plt.title(f"Cross‐section at {pt_xy}")
        plt.grid(True)
        plt.legend()
        plt.tight_layout()
        plt.show()

# 断面插值第三代, 采用线性插值
class CrossSectionModel_V2:
    def __init__(self, section_data, section_pos, n_samples=100):
        """
        :param section_data: dict, key=名称, value=list of [x, z] points
        :param section_pos:  dict, key=名称, value=[bx, by] 平面坐标
        """
        self.section_data = section_data
        self.section_pos = section_pos
        self.n_samples = n_samples

        # 1) 重采样所有断面
        self.resampled = {}
        for name, pts in section_data.items():
            arr = np.array(pts, float)
            x0, z0 = arr[:,0], arr[:,1]
            x_new = np.linspace(x0.min(), x0.max(), n_samples)
            z_new = np.interp(x_new, x0, z0)
            self.resampled[name] = np.vstack([x_new, z_new]).T

        # 2) Shapely 按基线投影对断面位置排序
        names = list(section_pos.keys())
        centers = [Point(section_pos[nm]) for nm in names]
        max_d = 0
        for p, q in combinations(centers, 2):
            d = p.distance(q)
            if d > max_d:
                max_d, start_pt, end_pt = d, p, q
        baseline = LineString([(start_pt.x, start_pt.y),
                               (end_pt.x,   end_pt.y)])
        proj = [(nm, baseline.project(Point(section_pos[nm]))) for nm in names]
        proj.sort(key=lambda x: x[1])
        self.sorted_names = [nm for nm, _ in proj]
        self.sorted_coords = np.array([section_pos[nm]
                                       for nm in self.sorted_names])

        # 3) 累积弧长计算
        N = len(self.sorted_coords)
        self.s_vals = np.zeros(N)
        for i in range(1, N):
            self.s_vals[i] = self.s_vals[i-1] + np.linalg.norm(
                self.sorted_coords[i] - self.sorted_coords[i-1]
            )

        # 4) 用于投影的折线
        self.line2d = LineString(self.sorted_coords)

    def get_section_at_xy(self, pt_xy):
        """
        返回：
          X,Y,Z: 剖面在三维空间的坐标；
          label: 剖面标签；
          s_along: 投影弧长参数。
        """
        p = Point(pt_xy)
        s = self.line2d.project(p)
        L = self.line2d.length

        # 容差：只有当 s 非常靠近 0 或 L 时才认定为端点
        tol = 1e-6 * L

        # 确定插值区间 [i0,i1] 以及局部参数 t
        if s < tol:
            i0, i1, t = 0, 1, 0.0
        elif s > L - tol:
            i0, i1, t = len(self.s_vals)-2, len(self.s_vals)-1, 1.0
        else:
            i1 = np.searchsorted(self.s_vals, s)
            i0 = i1 - 1
            t = (s - self.s_vals[i0]) / (self.s_vals[i1] - self.s_vals[i0])

        # 两端断面名称 & 数据
        n0, n1 = self.sorted_names[i0], self.sorted_names[i1]
        sec0, sec1 = self.resampled[n0], self.resampled[n1]

        # 投影点真是坐标
        proj_pt = self.line2d.interpolate(s)
        bx, by = proj_pt.x, proj_pt.y

        # 插值得到剖面
        X = bx + (1-t)*sec0[:,0] + t*sec1[:,0]
        Y = np.full(self.n_samples, by)
        Z = (1-t)*sec0[:,1] + t*sec1[:,1]

        # 标签
        if tol < s < L - tol:
            label = f"InterpSection({n0}-{n1})@{pt_xy}"
        else:
            # 退化为最近的端点断面
            idx = i0 if s < tol else i1
            name = self.sorted_names[idx]
            label = f"NearestSection@{name}"

        return {'X': X, 'Y': Y, 'Z': Z, 'label': label, 's_along': s}

    def visualize(self, pt_xy):
        """
        绘制同一窗口 1×3 子图：
         1) 3D 剖面面 + 高亮剖面
         2) 平面投影示意
         3) 二维剖面 (X vs Z)
        :param extra_pt: 可选，用于第2图标注额外点
        """
        extra_pt = pt_xy
        sec = self.get_section_at_xy(pt_xy)

        fig = plt.figure(figsize=(15,5))

        # 设置弹出窗口的位置：左上角距离屏幕（x=100,y=100）
        # 格式是 "+X+Y"
        manager = plt.get_current_fig_manager()
        manager.window.wm_geometry("+0+150")

        # --- 子图 1：3D 剖面面 + 剖面线
        ax3 = fig.add_subplot(131, projection='3d')
        n, m = len(self.sorted_names), self.n_samples
        X3 = np.zeros((n,m)); Y3 = np.zeros_like(X3); Z3 = np.zeros_like(X3)
        for i, nm in enumerate(self.sorted_names):
            bx0, by0 = self.section_pos[nm]
            arr = self.resampled[nm]
            X3[i], Y3[i], Z3[i] = arr[:,0]+bx0, by0, arr[:,1]
            ax3.plot(X3[i], Y3[i], Z3[i], c='gray', alpha=0.5)
        ax3.plot_surface(X3, Y3, Z3, cmap='viridis', alpha=0.6)
        ax3.plot(sec['X'], sec['Y'], sec['Z'], c='red', lw=3,
                 label=sec['label'])
        ax3.set_xlabel('X'); ax3.set_ylabel('Y'); ax3.set_zlabel('Z')
        ax3.legend()

        # --- 子图 2：平面投影示意
        ax2 = fig.add_subplot(132)
        xs, ys = zip(*self.sorted_coords)
        ax2.plot(xs, ys, '-o', color='gold', label='河道折线')
        if extra_pt is not None:
            p2 = Point(extra_pt)
            sal = self.line2d.project(p2)
            pr = self.line2d.interpolate(sal)
            ax2.scatter(*extra_pt, color='red', s=80, label='额外点')
            ax2.scatter(pr.x, pr.y, marker='x', color='blue', s=100,
                        label='投影点')
            seg = substring(self.line2d, 0, sal)
            sx, sy = seg.xy
            ax2.plot(sx, sy, '--', color='green',
                     label=f"s_along={sal:.1f}")
        ax2.set_aspect('equal','datalim')
        ax2.set_xlabel('X'); ax2.set_ylabel('Y')
        ax2.set_title(f"投影示意 (s={sec['s_along']:.1f})")
        ax2.legend(); ax2.grid(alpha=0.3)

        # --- 子图 3：二维剖面 (X vs Z)
        ax1 = fig.add_subplot(133)
        ax1.plot(sec['X'], sec['Z'], '-o', color='red', label=sec['label'])
        ax1.set_xlabel('X (m)'); ax1.set_ylabel('Z (m)')
        ax1.set_title(f"剖面 at {pt_xy}")
        ax1.grid(True); ax1.legend()

        plt.tight_layout()
        plt.show()

# 断面插值第四代, 采用样条插值
class CrossSectionModel_V3:
    def __init__(self, section_data, section_pos, n_samples=100):
        """
        :param section_data: dict, key=名称, value=list of [x, z] points
        :param section_pos:  dict, key=名称, value=[bx, by] 平面坐标
        """
        self.section_data = section_data
        self.section_pos  = section_pos
        self.n_samples    = n_samples

        if self.section_pos == None:
            print('输入数据为空，无法进行插值重构')
        else:
            # 1) 重采样所有断面（保持线性重采样）
            self.resampled = {}
            for name, pts in section_data.items():
                arr = np.array(pts, float)
                x0, z0 = arr[:,0], arr[:,1]
                x_new  = np.linspace(x0.min(), x0.max(), n_samples)
                z_new  = np.interp(x_new, x0, z0)
                self.resampled[name] = np.vstack([x_new, z_new]).T

            # 2) Shapely 按基线投影对断面位置排序
            names   = list(section_pos.keys())
            centers = [Point(section_pos[nm]) for nm in names]
            max_d   = 0
            for p, q in combinations(centers, 2):
                d = p.distance(q)
                if d > max_d:
                    max_d, start_pt, end_pt = d, p, q

            baseline = LineString([(start_pt.x, start_pt.y),
                                   (end_pt.x,   end_pt.y)])
            proj = [(nm, baseline.project(Point(section_pos[nm])))
                    for nm in names]
            proj.sort(key=lambda x: x[1])
            self.sorted_names  = [nm for nm, _ in proj]
            self.sorted_coords = np.array([section_pos[nm]
                                           for nm in self.sorted_names])

            # 3) 计算累积沿线距离
            N = len(self.sorted_coords)
            self.s_vals = np.zeros(N)
            for i in range(1, N):
                self.s_vals[i] = (self.s_vals[i-1] +
                                  np.linalg.norm(self.sorted_coords[i]
                                                 - self.sorted_coords[i-1]))

            # 4) 构造折线用于投影
            self.line2d = LineString(self.sorted_coords)

    def get_section_at_xy(self, pt_xy):
        """
        返回：
          'X','Y','Z': 三维剖面坐标数组，
          'label': 剖面标签，
          's_along': 投影弧长参数
        """
        p = Point(pt_xy)
        s = self.line2d.project(p)
        L = self.line2d.length
        tol = 1e-6 * L

        # 确定落在哪两段之间，以及局部参数 t
        if s < tol:
            i0, i1, t = 0, 1, 0.0
        elif s > L - tol:
            i0, i1, t = len(self.s_vals)-2, len(self.s_vals)-1, 1.0
        else:
            i1 = np.searchsorted(self.s_vals, s)
            i0 = i1 - 1
            t  = (s - self.s_vals[i0]) / (self.s_vals[i1] - self.s_vals[i0])

        # 对应断面名与重采样数据
        n0, n1 = self.sorted_names[i0], self.sorted_names[i1]
        sec0, sec1 = self.resampled[n0], self.resampled[n1]

        # 投影点真实坐标
        proj_pt = self.line2d.interpolate(s)
        bx, by  = proj_pt.x, proj_pt.y

        # —— 横向本地坐标矩阵 (各断面 local x,z) ——
        Xmat = np.vstack([self.resampled[nm][:,0]
                          for nm in self.sorted_names])  # shape=(N_sections, n_samples)
        Zmat = np.vstack([self.resampled[nm][:,1]
                          for nm in self.sorted_names])

        # 选取样条节点（i0-1, i0, i1, i1+1）
        idxs = np.unique(np.clip([i0-1, i0, i1, i1+1],
                                 0, len(self.s_vals)-1))
        s_sel = self.s_vals[idxs]         # 节点弧长
        X_sel = Xmat[idxs, :]             # 节点横坐标
        Z_sel = Zmat[idxs, :]             # 节点高程

        # 用 CubicSpline 对每个横向样本 j 分别插值 X 和 Z
        X_local = np.zeros(self.n_samples)
        Z_local = np.zeros(self.n_samples)
        for j in range(self.n_samples):
            csx = CubicSpline(s_sel, X_sel[:, j], bc_type='natural')
            csz = CubicSpline(s_sel, Z_sel[:, j], bc_type='natural')
            X_local[j] = csx(s)
            Z_local[j] = csz(s)

        # 全局坐标
        X = bx + X_local
        Y = np.full(self.n_samples, by)
        Z = Z_local

        # 标签
        if tol < s < L - tol:
            label = f"InterpSection({n0}-{n1})@{pt_xy}"
        else:
            idx   = i0 if s < tol else i1
            label = f"NearestSection@{self.sorted_names[idx]}"

        return {'X': X, 'Y': Y, 'Z': Z,
                'label': label, 's_along': s}

    def visualize(self, pt_xy):
        """同一窗口 1×3 子图：3D 面／平面投影／二维剖面。"""
        sec = self.get_section_at_xy(pt_xy)

        fig = plt.figure(figsize=(18,5))

        # — 子图 1：3D 面 + 剖面线
        ax3 = fig.add_subplot(131, projection='3d')
        n,m = len(self.sorted_names), self.n_samples
        X3 = np.zeros((n,m)); Y3 = np.zeros_like(X3); Z3 = np.zeros_like(X3)
        for i,nm in enumerate(self.sorted_names):
            bx0,by0 = self.section_pos[nm]
            arr     = self.resampled[nm]
            X3[i],Y3[i],Z3[i] = arr[:,0]+bx0, by0, arr[:,1]
            ax3.plot(X3[i],Y3[i],Z3[i], c='gray', alpha=0.5)
        ax3.plot_surface(X3,Y3,Z3, cmap='viridis', alpha=0.6)
        ax3.plot(sec['X'],sec['Y'],sec['Z'], c='red', lw=3,
                 label=sec['label'])
        ax3.set_xlabel('X'); ax3.set_ylabel('Y'); ax3.set_zlabel('Z')
        ax3.legend()

        # — 子图 2：平面投影
        ax2 = fig.add_subplot(132)
        xs,ys = zip(*self.sorted_coords)
        ax2.plot(xs, ys, '-o', color='gold', label='河道折线')
        p2  = Point(pt_xy)
        sal = self.line2d.project(p2)
        pr  = self.line2d.interpolate(sal)
        ax2.scatter(*pt_xy, color='red',   s=80, label='额外点')
        ax2.scatter(pr.x, pr.y, marker='x',
                    color='blue', s=100, label=f"s_along={sal:.1f}")
        seg = substring(self.line2d, 0, sal)
        sx,sy = seg.xy
        ax2.plot(sx, sy, '--', color='green')
        ax2.set_aspect('equal','datalim')
        ax2.set_xlabel('X'); ax2.set_ylabel('Y')
        ax2.set_title(f"投影示意 (s={sec['s_along']:.1f})")
        ax2.legend(); ax2.grid(alpha=0.3)

        # — 子图 3：二维剖面 (X vs Z)
        ax1 = fig.add_subplot(133)
        ax1.plot(sec['X'], sec['Z'], '-o', color='red',
                 label=sec['label'])
        ax1.set_xlabel('X (m)'); ax1.set_ylabel('Z (m)')
        ax1.set_title(f"剖面 at {pt_xy}")
        ax1.grid(True); ax1.legend()

        plt.tight_layout()
        plt.show()

# 断面表V1
class CrossSectionTableManagerV1:
    def __init__(self):
        # 存放所有表：name -> DataFrame(depth, area)
        self.tables = {}

    def add_table(self, name, depths, level, areas, width, wetted_perimeter, hydraulic_radius, press, DEB):
        """
        新增一张断面水力参数表，并按水位升序存储到 self.tables 中。

        :param name: str
            表的名字，用于在 self.tables 中作为键。
        :param depths: iterable of float
            各水位对应的水深列表（一维可迭代对象），单位同模型输入（如 m）。
        :param level: iterable of float
            各水位数值列表（一维可迭代对象），单位同模型输入（如 m）。
        :param areas: iterable of float
            各水位对应的过水断面面积列表（一维可迭代对象），单位同模型输入（如 m²）。
        :param width: iterable of float
            各水位对应的水面宽度列表（一维可迭代对象），单位同模型输入（如 m）。
        :param wetted_perimeter: iterable of float
            各水位对应的湿周长度列表（一维可迭代对象），单位同模型输入（如 m）。
        :param hydraulic_radius: iterable of float
            各水位对应的水力半径列表（一维可迭代对象），单位同模型输入（如 m）。
        :param press: iterable of float
            各水位对应的水压力（一维可迭代对象），单位同模型输入。
        """
        df = pd.DataFrame({
            'depth': depths,  # 水深
            'area': areas,  # 过水断面面积
            'level': level,  # 水位
            'width': width,  # 水面宽度
            'wetted_perimeter': wetted_perimeter,  # 湿周
            'hydraulic_radius': hydraulic_radius,  # 水力半径
            'press': press,  # 水压力
            'DEB' : DEB
        }).sort_values('level').reset_index(drop=True)
        self.tables[name] = df

    def get_area_by_depth(self, name, depth, method='interp'):
        """
        根据水深查面积
        :param name:   表名
        :param depth:  水深值（标量）
        :param method: 'exact'（精确匹配）或 'interp'（线性插值）
        :return: 面积值 or None
        """
        df = self.tables.get(name)
        if df is None:
            raise KeyError(f"No table named {name}")
        if method == 'exact':
            m = df['depth'] == depth
            if not m.any():
                return None
            return float(df.loc[m, 'area'].iloc[0])
        elif method == 'interp':
            return float(np.interp(depth, df['depth'], df['area']))
        else:
            raise ValueError("method must be 'exact' or 'interp'")

    def get_area_by_level(self, name, level, method='interp'):
        """
        根据水位查面积
        :param name:   表名
        :param level:  水位值（标量）
        :param method: 'exact'（精确匹配）或 'interp'（线性插值）
        :return: 面积值 or None
        """
        df = self.tables.get(name)
        if df is None:
            raise KeyError(f"No table named {name}")
        if method == 'exact':
            m = df['level'] == level
            if not m.any():
                return None
            return float(df.loc[m, 'area'].iloc[0])
        elif method == 'interp':
            return float(np.interp(level, df['level'], df['area']))
        else:
            raise ValueError("method must be 'exact' or 'interp'")

    def get_level_by_area(self, name, area, method='interp'):
        """
        根据过水断面面积查水深
        :param name:   表名
        :param area:   面积值（标量）
        :param method: 'exact'（精确匹配）或 'interp'（线性插值）
        :return: 水位值 or None
        """
        df = self.tables.get(name)
        if df is None:
            raise KeyError(f"No table named {name}")
        if method == 'exact':
            m = df['area'] == area
            if not m.any():
                return None
            return float(df.loc[m, 'level'].iloc[0])
        elif method == 'interp':
            # 注意：为了插值，area 列需要是单调的；否则先 df.sort_values('area')
            df2 = df.sort_values('area').reset_index(drop=True)
            return float(np.interp(area, df2['area'], df2['level']))
        else:
            raise ValueError("method must be 'exact' or 'interp'")

    def get_DEB_by_area(self, name, area, method='interp'):
        """
        根据过水断面面积查水深
        :param name:   表名
        :param area:   面积值（标量）
        :param method: 'exact'（精确匹配）或 'interp'（线性插值）
        :return: 水位值 or None
        """
        df = self.tables.get(name)
        if df is None:
            raise KeyError(f"No table named {name}")
        if method == 'exact':
            m = df['area'] == area
            if not m.any():
                return None
            return float(df.loc[m, 'DEB'].iloc[0])
        elif method == 'interp':
            # 注意：为了插值，area 列需要是单调的；否则先 df.sort_values('area')
            df2 = df.sort_values('area').reset_index(drop=True)
            return float(np.interp(area, df2['area'], df2['DEB']))
        else:
            raise ValueError("method must be 'exact' or 'interp'")

    def get_depth_by_area(self, name, area, method='interp'):
        """
        根据过水断面面积查水深
        :param name:   表名
        :param area:   面积值（标量）
        :param method: 'exact'（精确匹配）或 'interp'（线性插值）
        :return: 水深值 or None
        """
        df = self.tables.get(name)
        if df is None:
            raise KeyError(f"No table named {name}")
        if method == 'exact':
            m = df['area'] == area
            if not m.any():
                return None
            return float(df.loc[m, 'depth'].iloc[0])
        elif method == 'interp':
            # 注意：为了插值，area 列需要是单调的；否则先 df.sort_values('area')
            df2 = df.sort_values('area').reset_index(drop=True)
            return float(np.interp(area, df2['area'], df2['depth']))
        else:
            raise ValueError("method must be 'exact' or 'interp'")

    def get_width_by_area(self, name, area, method='interp'):
        """
        根据过水断面面积查水面宽度
        :param name:   表名
        :param area:   面积值（标量）
        :param method: 'exact'（精确匹配）或 'interp'（线性插值）
        :return: 水面宽度值 or None
        """
        df = self.tables.get(name)
        if df is None:
            raise KeyError(f"No table named {name}")
        if method == 'exact':
            m = df['area'] == area
            if not m.any():
                return None
            return float(df.loc[m, 'width'].iloc[0])
        elif method == 'interp':
            # 注意：为了插值，area 列需要是单调的；否则先 df.sort_values('area')
            df2 = df.sort_values('area').reset_index(drop=True)
            return float(np.interp(area, df2['area'], df2['width']))
        else:
            raise ValueError("method must be 'exact' or 'interp'")

    def get_wetted_perimeter_by_area(self, name, area, method='interp'):
        """
        根据过水断面面积查湿周
        :param name:   表名
        :param area:   面积值（标量）
        :param method: 'exact'（精确匹配）或 'interp'（线性插值）
        :return: 湿周值 or None
        """
        df = self.tables.get(name)
        if df is None:
            raise KeyError(f"No table named {name}")
        if method == 'exact':
            m = df['area'] == area
            if not m.any():
                return None
            return float(df.loc[m, 'wetted_perimeter'].iloc[0])
        elif method == 'interp':
            # 注意：为了插值，area 列需要是单调的；否则先 df.sort_values('area')
            df2 = df.sort_values('area').reset_index(drop=True)
            return float(np.interp(area, df2['area'], df2['wetted_perimeter']))
        else:
            raise ValueError("method must be 'exact' or 'interp'")

    def get_hydraulic_radius_by_area(self, name, area, method='interp'):
        """
        根据过水断面面积查水力半径
        :param name:   表名
        :param area:   面积值（标量）
        :param method: 'exact'（精确匹配）或 'interp'（线性插值）
        :return: 水力半径值 or None
        """
        df = self.tables.get(name)
        if df is None:
            raise KeyError(f"No table named {name}")
        if method == 'exact':
            m = df['area'] == area
            if not m.any():
                return None
            return float(df.loc[m, 'hydraulic_radius'].iloc[0])
        elif method == 'interp':
            # 注意：为了插值，area 列需要是单调的；否则先 df.sort_values('area')
            df2 = df.sort_values('area').reset_index(drop=True)
            value = float(np.interp(area, df2['area'], df2['hydraulic_radius']))
            if math.isnan(value) : value = 1e-7
            return value
        else:
            raise ValueError("method must be 'exact' or 'interp'")

    def get_press_by_area(self, name, area, method='interp'):
        """
        根据过水断面面积查水压力
        :param name:   表名
        :param area:   面积值（标量）
        :param method: 'exact'（精确匹配）或 'interp'（线性插值）
        :return: 水压力值 or None
        """
        df = self.tables.get(name)
        if df is None:
            raise KeyError(f"No table named {name}")
        if method == 'exact':
            m = df['area'] == area
            if not m.any():
                return None
            return float(df.loc[m, 'press'].iloc[0])
        elif method == 'interp':
            # 注意：为了插值，area 列需要是单调的；否则先 df.sort_values('area')
            df2 = df.sort_values('area').reset_index(drop=True)
            return float(np.interp(area, df2['area'], df2['press']))
        else:
            raise ValueError("method must be 'exact' or 'interp'")

    def get_value_by_area(self, name, area, value_name, method='interp'):
        """
        根据过水断面面积查指定参数
        :param name:   表名
        :param area:   面积值（标量）
        :param method: 'exact'（精确匹配）或 'interp'（线性插值）
        :return: 参数值值 or None
        """
        df = self.tables.get(name)
        if value_name not in df.columns.tolist():
            raise KeyError(f"No value named {value_name}")

        if df is None:
            raise KeyError(f"No table named {name}")
        if method == 'exact':
            m = df['area'] == area
            if not m.any():
                return None
            return float(df.loc[m, value_name].iloc[0])
        elif method == 'interp':
            # 注意：为了插值，area 列需要是单调的；否则先 df.sort_values('area')
            df2 = df.sort_values('area').reset_index(drop=True)
            return float(np.interp(area, df2['area'], df2[value_name]))
        else:
            raise ValueError("method must be 'exact' or 'interp'")

class CrossSectionTable:
    """
    内部缓存深度、水平面、面积等三种排序后的 NumPy 数组，
    提供高效的 exact 和 interp 查询接口。
    """
    def __init__(self, depths, levels, areas,
                 widths, wetted_perimeters,
                 hydraulic_radii, presses, DEBs):
        depths = np.asarray(depths, dtype=float)
        levels = np.asarray(levels, dtype=float)
        areas  = np.asarray(areas, dtype=float)
        widths = np.asarray(widths, dtype=float)
        wetted_perimeters = np.asarray(wetted_perimeters, dtype=float)
        hydraulic_radii   = np.asarray(hydraulic_radii, dtype=float)
        presses           = np.asarray(presses, dtype=float)
        DEBs              = np.asarray(DEBs, dtype=float)

        # 1. 按 depth 排序，用于 depth→area
        idx = np.argsort(depths)
        self._depth_axis = depths[idx]
        self._area_d     = areas[idx]

        # 2. 按 level 排序，用于 level→area
        idx = np.argsort(levels)
        self._level_axis = levels[idx]
        self._area_l     = areas[idx]

        # 3. 按 area 排序，用于 area→其他
        idx = np.argsort(areas)
        self._area_axis    = areas[idx]
        self._depth_a      = depths[idx]
        self._level_a      = levels[idx]
        self._DEB_a        = DEBs[idx]
        self._width_a      = widths[idx]
        self._wetted_a     = wetted_perimeters[idx]
        self._hradius_a    = hydraulic_radii[idx]
        self._press_a      = presses[idx]

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
            return float(self._hradius_a[mask][0])
        val = float(np.interp(area, self._area_axis, self._hradius_a))
        return val if not math.isnan(val) else 1e-7

    def get_press_by_area(self, area, method='interp'):
        if method == 'exact':
            mask = self._area_axis == area
            if not mask.any():
                return None
            return float(self._press_a[mask][0])
        return float(np.interp(area, self._area_axis, self._press_a))

    def get_value_by_area(self, area, value_name, method='interp'):
        mapping = {
            'depth':            (self._area_axis, self._depth_a),
            'level':            (self._area_axis, self._level_a),
            'area':             (self._area_axis, self._area_axis),
            'DEB':              (self._area_axis, self._DEB_a),
            'width':            (self._area_axis, self._width_a),
            'wetted_perimeter': (self._area_axis, self._wetted_a),
            'hydraulic_radius': (self._area_axis, self._hradius_a),
            'press':            (self._area_axis, self._press_a),
        }
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
    """
    完全兼容旧 API 的高效实现：
    add_table(...) 输入不变，
    get_*_by_*(...) 方法签名与返回值保持一致。
    """
    def __init__(self):
        self.tables = {}

    def add_table(self, name,
                  depths, level, areas,
                  width, wetted_perimeter,
                  hydraulic_radius, press, DEB):
        # 新版内部使用 CrossSectionTable
        self.tables[name] = CrossSectionTable(
            depths, level, areas,
            width, wetted_perimeter,
            hydraulic_radius, press, DEB
        )

    def get_area_by_depth(self, name, depth, method='interp'):
        tbl = self.tables.get(name)
        if tbl is None:
            raise KeyError(f"No table named {name}")
        return tbl.get_area_by_depth(depth, method)

    def get_area_by_level(self, name, level, method='interp'):
        tbl = self.tables.get(name)
        if tbl is None:
            raise KeyError(f"No table named {name}")
        return tbl.get_area_by_level(level, method)

    def get_level_by_area(self, name, area, method='interp'):
        tbl = self.tables.get(name)
        if tbl is None:
            raise KeyError(f"No table named {name}")
        return tbl.get_level_by_area(area, method)

    def get_DEB_by_area(self, name, area, method='interp'):
        tbl = self.tables.get(name)
        if tbl is None:
            raise KeyError(f"No table named {name}")
        return tbl.get_DEB_by_area(area, method)

    def get_depth_by_area(self, name, area, method='interp'):
        tbl = self.tables.get(name)
        if tbl is None:
            raise KeyError(f"No table named {name}")
        return tbl.get_depth_by_area(area, method)

    def get_width_by_area(self, name, area, method='interp'):
        tbl = self.tables.get(name)
        if tbl is None:
            raise KeyError(f"No table named {name}")
        return tbl.get_width_by_area(area, method)

    def get_wetted_perimeter_by_area(self, name, area, method='interp'):
        tbl = self.tables.get(name)
        if tbl is None:
            raise KeyError(f"No table named {name}")
        return tbl.get_wetted_perimeter_by_area(area, method)

    def get_hydraulic_radius_by_area(self, name, area, method='interp'):
        tbl = self.tables.get(name)
        if tbl is None:
            raise KeyError(f"No table named {name}")
        return tbl.get_hydraulic_radius_by_area(area, method)

    def get_press_by_area(self, name, area, method='interp'):
        tbl = self.tables.get(name)
        if tbl is None:
            raise KeyError(f"No table named {name}")
        return tbl.get_press_by_area(area, method)

    def get_value_by_area(self, name, area, value_name, method='interp'):
        tbl = self.tables.get(name)
        if tbl is None:
            raise KeyError(f"No table named {name}")
        return tbl.get_value_by_area(area, value_name, method)

# 河道计算
class River (Process) :
    def __init__(self, river_data, section_data, section_pos, sim_data):
        # 优化参数
        # 创建一个持久的绘图进程池，只起一个 worker
        # self._plot_executor = ProcessPoolExecutor(max_workers=12)

        self.Plot_flag = False
        self.FRTIMP = 1   # 半隐式处理源项

        # 设置基础参数
        dtype = np.float32 if config.DTYPE == "float32" else np.float64
        self.EPSILON = config.EPSILON # 0值
        self.water_depth_limit = 0.02 # 计算最小水深值
        self.S_limit = 1
        self.g = 9.81 # 重力加速度
        self.DT_increase_factor = 1.05
        self.model_name = sim_data['model_name']

        # 断面面积表句柄
        self.cross_section_table = CrossSectionTableManagerV2()

        # 断面插值句柄
        self.Interpolator = CrossSectionModel_V3(section_data=section_data, section_pos=section_pos)

        # 设置模型参数
        self.sim_start_time = datetime.datetime.strptime (sim_data['sim_start_time'], "%Y-%m-%d %H:%M:%S")
        self.sim_end_time = datetime.datetime.strptime (sim_data['sim_end_time'], "%Y-%m-%d %H:%M:%S")
        self.Max_time_step = self.time_step = sim_data['time_step']
        self.output_folder_path = sim_data['output_path']
        self.CFL = sim_data['CFL']
        now = datetime.datetime.now()
        self.file_name = f"result_{now.day:02d}_{now.minute:02d}"

        # 存入初始参数
        self.cell_num = river_data['cell_num']
        self.pos = np.array(river_data['pos'], dtype=dtype)
        self.section_name = river_data['section_name']
        self.sections_data = section_data
        self.section_pos = section_pos

        # 模拟时间参数
        self.DT = 0.1 # 时间步长
        self.DT_old = self.DT # 上一时间步长
        self.current_sim_time = 0 # 累计模拟时间
        self.current_report_time_step_remaining_time = self.time_step # 当前时间步长剩余时间
        self.time_step_count = 0 # 模拟时间步长统计
        self.revelent_time = 0

        # 差分网格，实现初始化
        self.cell_pos, self.cell_sections, self.cell_lengths = self.interpolate_uniformly()

        # 补充两侧虚拟网格
        self.cell_sections.insert(0, self.cell_sections[0])
        self.cell_sections.insert (-1, self.cell_sections[-1])
        self.cell_pos = np.insert(self.cell_pos, 0, self.cell_pos[0], axis=0)
        self.cell_pos = np.insert(self.cell_pos, -1, self.cell_pos[-1], axis=0)
        self.cell_lengths = np.insert(self.cell_lengths, 0, self.cell_lengths[0], axis=0)
        self.cell_lengths = np.insert(self.cell_lengths, -1, self.cell_lengths[-1], axis=0)
        self.cell_coordinate_pos = np.zeros_like(self.cell_pos)

        # 网格初始参数, 虚拟网格也算在内
        self.river_bed_height = self.cell_pos[:, 2] # 河底高程
        self.water_level = np.array(self.river_bed_height) # 水位
        self.water_depth = self.water_level - self.river_bed_height # 水深

        self.Q = np.zeros (self.cell_num + 2, dtype)  # 流量
        self.S = np.zeros_like (self.Q)  # 过水断面面积
        self.Cell_left_Q = np.zeros_like (self.Q) # 格左侧流量
        self.Cell_right_Q = np.zeros_like (self.Q) # 格右侧流量
        self.Cell_left_S = np.zeros_like (self.S) # 格左侧过水面积
        self.Cell_right_S = np.zeros_like (self.S) # 格右侧过水面积
        self.U = np.zeros_like (self.Q)  # 流速
        self.FR = np.zeros_like (self.Q)  # 福汝德数
        self.C = np.zeros_like (self.Q)  # 波速
        self.PRESS = np.zeros_like (self.Q)  # 垂向压力
        self.BETA = np.zeros_like (self.Q)  # 修正系数
        self.P = np.zeros_like (self.Q)  # 湿周
        self.R = np.zeros_like (self.Q)  # 水力半径
        self.cell_press_source = np.zeros ((self.cell_num + 1, 2))  # 界面中心压力源项目
        self.QIN = np.zeros_like (self.Q)  # 对于任意网格的外部入流
        self.DEB = np.zeros_like(self.Q) # 过水断面面积对水位导数
        self.Slop = np.zeros_like(self.Q) # 河床坡度
        self.DTI = np.zeros_like(self.Q) # 每个网格的时间步长
        self.n = np.zeros_like(self.Q) # 网格曼宁摩擦系数
        self.n[:] = sim_data['n']

        # 界面参数
        self.F_U = np.zeros (self.cell_num + 1, dtype)  # 界面平均流速
        self.F_C = np.zeros_like(self.F_U) # 界面平均波速
        self.F_Q_SOURCE = np.zeros((self.cell_num + 1, 2)) # 界面流量源项
        self.F_Friction_SOURCE = np.zeros_like(self.F_Q_SOURCE) # 界面摩擦源项
        self.F_Singular_Head_Loss = np.zeros_like(self.F_U) # 界面处局部水头损失系数
        self.Lambda1 = np.zeros_like(self.F_U) # 第一特征值
        self.Lambda2 = np.zeros_like(self.F_U) # 第二特征值
        self.abs_Lambda1 = np.zeros_like(self.F_U)  # 第一特征值的绝对值
        self.abs_Lambda2 = np.zeros_like(self.F_U)  # 第二特征值的绝对值
        self.alpha1 = np.zeros_like(self.F_U)  # 波幅系数
        self.alpha2 = np.zeros_like(self.F_U)  # 波幅系数
        self.dissipation1 = np.zeros_like(self.F_U)  # 粘性系数
        self.dissipation2 = np.zeros_like(self.F_U)  # 粘性系数
        self.Vactor1 = np.zeros((self.cell_num + 1, 2)) # 第一特征向量
        self.Vactor2 = np.zeros((self.cell_num + 1, 2)) # 第二特征向量
        self.Vactor1_T = np.zeros ((self.cell_num + 1, 2))  # 特征矩阵的逆第一列
        self.Vactor2_T = np.zeros ((self.cell_num + 1, 2))  # 特征矩阵的逆第二列

        self.Flux_LOC = np.zeros ((self.cell_num + 1, 2))  # 界面中心通量
        self.Flux_Source_left = np.zeros ((self.cell_num + 2, 2)) # 网格左侧界面源项
        self.Flux_Source_right = np.zeros ((self.cell_num + 2, 2))  # 网格右侧界面源项
        self.Flux_Source_center = np.zeros ((self.cell_num + 1, 2))  # 中心源项
        self.Flux_Friction_left = np.zeros ((self.cell_num + 2, 2))  # 网格左侧界面摩擦通量
        self.Flux_Friction_right = np.zeros ((self.cell_num + 2, 2))  # 网格右侧界面摩擦通量

        self.bottom_source = np.zeros ((self.cell_num + 2, 2)) # 网格底坡源项
        self.friction_source = np.zeros((self.cell_num + 2, 2))  # 网格摩擦源项

        self.Flux = np.zeros ((self.cell_num + 2, 2))  # 通量数组

        self.Debit_Flux = np.zeros((self.cell_num + 1, 2))

        self.flag_LeVeque = np.zeros (self.cell_num + 1)  # LeVeque修正标识

        '''隐式计算所需参数'''
        self.Implic_flag = False
        self.S_old = np.zeros_like(self.S) # 上一时间步S的值
        self.Q_old = np.zeros_like(self.Q) # 上一时间步Q的值

        # 增量的边界条件
        self.V0 = np.zeros(2, dtype=dtype)
        self.V1 = np.zeros_like(self.V0)

        # 隐式系数矩阵系数
        self.D = np.zeros((self.cell_num + 1, 4), dtype=dtype)
        self.ID = np.zeros_like(self.D)
        self.A = np.zeros((self.cell_num + 2, 4), dtype=dtype)
        self.Lambda1I = np.zeros(self.cell_num + 2)  # 隐式求解时第一特征值
        self.Lambda2I = np.zeros(self.cell_num + 2)  # 隐式求解时第二特征值
        self.Vactor1I = np.zeros((self.cell_num + 2, 2))  # 隐式求解时第一特征向量
        self.Vactor2I = np.zeros((self.cell_num + 2, 2))  # 隐式求解时第二特征向量
        self.Vactor1I_T = np.zeros((self.cell_num + 2, 2))  # 隐式求解时特征矩阵的逆第一列
        self.Vactor2I_T = np.zeros((self.cell_num + 2, 2))  # 隐式求解时特征矩阵的逆第二列

        # 初始化参数
        self.Depth_init = False
        self.Level_init = False

        # 保存参数
        self.save_result_name = None

    '''初始化网格参数，基于查表和caleta.f90'''
    def Init_cell_proprity(self, fine):
        # 初始化断面表
        n = np.unique(self.n)
        self.Create_cross_section_table(n)

        for i in range(self.cell_num + 2):
            # 获取断面名称
            section_name = self.cell_sections[i]

            # 基于断面修正河底高程
            if not fine:
                section_point = self.sections_data[section_name]
                ys = [pt[1] for pt in section_point]  # 坐标点y
                self.river_bed_height[i] = np.min(ys) # 断面最低点

            # 修正最小水深
            if self.water_depth[i] < self.water_depth_limit:
                self.water_depth[i] = self.water_depth_limit

            # 计算水位
            self.water_level[i] = self.water_depth[i] + self.river_bed_height[i]

            # 基于水位查找过流断面面积
            self.S[i] = self.cross_section_table.get_area_by_level(section_name, self.water_level[i])

            # 计算流速
            if self.S[i] < self.S_limit:
                self.U[i] = 0
            else:
                self.U[i] = self.Q[i] / self.S[i]

            # 基于过水断面面积查找水面宽度
            water_surface_width = self.cross_section_table.get_width_by_area(section_name, self.S[i])

            # 计算波速
            if water_surface_width > self.water_depth_limit and self.S[i] > self.water_depth_limit ** 2:
                self.C[i] = np.sqrt(self.g * self.S[i] / water_surface_width)
                self.FR[i] = np.abs(self.U[i]) / self.C[i]  # 计算福汝德数
            else:
                self.C[i] = 1e-2
                self.FR[i] = np.abs(self.U[i]) / self.C[i]  # 计算福汝德数

            # 基于过水断面面积查找湿周
            self.P[i] = self.cross_section_table.get_width_by_area(section_name, self.S[i])

            # 基于过水断面面积查找水压力
            self.PRESS[i] = self.cross_section_table.get_press_by_area(section_name, self.S[i])

            # 基于过水断面面积查找水力半径
            self.R[i] = self.cross_section_table.get_hydraulic_radius_by_area(section_name, self.S[i])

            # 压力分布
            self.BETA[i] = 1

            # 计算网格坡度
            if i == self.cell_num + 1:
                self.Slop[i] = (self.river_bed_height[i - 1] - self.river_bed_height[i]) / self.cell_lengths[i]
            else:
                self.Slop[i] = (self.river_bed_height[i] - self.river_bed_height[i + 1]) / self.cell_lengths[i]

            if self.Slop[i] == 0 : self.Slop[i] = self.EPSILON

        # 将两侧边界网格参数与内部统一
        self.river_bed_height[0] = self.river_bed_height[1]
        self.river_bed_height[-1] = self.river_bed_height[-2]

        self.cell_sections[0] = self.cell_sections[1]
        self.cell_sections[-1] = self.cell_sections[-2]

        self.water_level[0] = self.water_level[1]
        self.water_level[-1] = self.water_level[-2]

        self.water_depth[0] = self.water_depth[1]
        self.water_depth[-1] = self.water_depth[-2]

    '''计算界面平均Roe参数 solvro.f90'''
    def Caculate_face_U_C(self):
        """
        for i in range(self.cell_num + 1): # 基于界面进行计算
            # 计算平均流速
            left_S = np.sqrt(self.S[i])  # 界面左侧过水断面面积
            right_S = np.sqrt(self.S[i + 1])  # 界面右侧过水断面面积

            left_U = self.U[i]  # 界面左侧流速
            right_U = self.U[i + 1]  # 界面右侧流速

            # 过水断面面积加权计算平均流速
            self.F_U[i] = (left_U * left_S + right_U * right_S) / (left_S + right_S)

            # 计算平均波速
            diff_S = np.abs(self.S[i] - self.S[i + 1])
            if diff_S <= self.EPSILON:
                # 两侧湿润面积差较小时，采用平均值
                left_C = self.C[i]
                right_C = self.C[i + 1]
                self.F_C[i] = 0.5 * (left_C + right_C)
            else :
                # 其余情况基于压力和面积重新计算
                left_PRESS = self.PRESS[i]
                right_PRESS = self.PRESS[i + 1]
                self.F_C[i] = np.sqrt((left_PRESS - right_PRESS) / (self.S[i] - self.S[i+1]))


            self.dissipation1[i] = 0.5 * (self.abs_Lambda1[i] * self.alpha1[i] * self.Vactor1[i, 0] + self.abs_Lambda2[i] * self.alpha2[i] * self.Vactor2[i, 0])
            self.dissipation2[i] = 0.5 * (self.abs_Lambda1[i] * self.alpha1[i] * self.Vactor1[i, 1] + self.abs_Lambda2[i] * self.alpha2[i] * self.Vactor2[i, 1])
    """
        # 0. 接口数
        N = self.cell_num + 1

        # 1. 左右过水断面“根号化”
        sqrt_S = np.sqrt(np.clip(self.S, self.S_limit, None))  # shape=(cell_num+2,)

        left_S = sqrt_S[:N]  # 接口左侧面积根号
        right_S = sqrt_S[1:N + 1]  # 接口右侧面积根号

        # 2. 左右流速
        left_U = self.U[:N]
        right_U = self.U[1:N + 1]

        # 3. 批量计算加权平均流速 F_U
        #    F_U = (left_U*left_S + right_U*right_S) / (left_S + right_S)
        self.F_U[:N] = (left_U * left_S + right_U * right_S) / (left_S + right_S)

        # 4. 批量计算平均波速 F_C
        # 4.1 差值判断：湿润面积差小则用平均，否则用压力差重算
        diff_S = np.abs(left_S - right_S)
        mask_avg = diff_S <= 1e-3  # True→用平均，False→用压力差

        # 4.2 平均波速部分
        avg_C = 0.5 * (self.C[:N] + self.C[1:N+1])

        # 4.3 压力差／断面差部分
        press_diff = self.PRESS[:N] - self.PRESS[1:N + 1]
        S_diff = self.S[:N] - self.S[1:N + 1]

        # 4.4 用 np.divide 做安全除法，避免零除和 NaN
        ratio = np.zeros(N, dtype=press_diff.dtype)
        np.divide(
            press_diff,
            S_diff,
            out=ratio,
            where=~mask_avg
        )

        # 限制范围
        ratio = np.clip(ratio, a_min=self.EPSILON, a_max=None)

        # 4.5 组合最终 F_C
        F_C = np.empty(N, dtype=self.F_C.dtype)
        F_C[mask_avg] = avg_C[mask_avg]  # 差小用平均
        F_C[~mask_avg] = np.sqrt(ratio[~mask_avg])  # 差大用 pressure 差重算
        self.F_C[:N] = F_C

        # 5. 批量计算耗散项 dissipation1, dissipation2
        # idx = slice(0, N)
        # # 第一分量
        # self.dissipation1[idx] = 0.5 * (
        #         self.abs_Lambda1[idx] * self.alpha1[idx] * self.Vactor1[idx, 0]
        #         + self.abs_Lambda2[idx] * self.alpha2[idx] * self.Vactor2[idx, 0]
        # )
        # # 第二分量
        # self.dissipation2[idx] = 0.5 * (
        #         self.abs_Lambda1[idx] * self.alpha1[idx] * self.Vactor1[idx, 1]
        #         + self.abs_Lambda2[idx] * self.alpha2[idx] * self.Vactor2[idx, 1]
        # )


    '''计算源项2 数值文档'''
    def Caculate_source_term_2(self):
        """
        for i in range(self.cell_num + 2):  # 基于网格进行计算
            # 计算摩擦源项
            section_points = self.sections_data[self.cell_sections[i]]
            eps = self.EPSILON
            Q = self.Q[i]
            S = self.S[i]
            P = self.Caculate_wetted_perimeter_by_water_depth(section_points, self.water_depth[i])

            friction = self.g * self.n[i] * self.n[i] * Q * np.abs(Q) / (S * P ** (4 / 3) + eps)

            self.friction_source[i, 0] = 0
            self.friction_source[i, 1] = friction

        """
        """
        # 常量
        g = self.g

        # 1. 计算 Q * |Q|
        Q2 = self.Q * np.abs(self.Q)

        # 2. 计算分母 S * P^(4/3) + eps
        denom = (self.S * self.R ** (4.0 / 3.0))
        denom = np.clip(denom, a_min=1e-4, a_max=None)

        friction = np.divide(
            g * (self.n ** 2) * Q2,
            denom,
            out=np.zeros_like(denom),
            where=denom != 0
        )

        grivaty_source = g * self.S * self.Slop
        self.friction_source[:, 0] = 0
        self.friction_source[:, 1] = friction # + grivaty_source
        """
        # DEB计算模式 debitance_s
        # D表示界面右侧, G表示界面左侧
        for i in range(self.cell_num + 1):
            if self.FRTIMP:
                self.friction_source[i, 0] = 0
                self.friction_source[i, 1] = 0
            else:
                g = self.g

                sd = self.S[i+1]
                sg = self.S[i]

                qd = self.Q[i+1]
                qg = self.Q[i]

                smil = 0.5 * (sg + sd)
                qmil = 0.5 * (qg + qd)

                section_nameg = self.cell_sections[i]
                section_named = self.cell_sections[i + 1]

                debd = self.cross_section_table.get_DEB_by_area(section_named, sd)
                debg = self.cross_section_table.get_DEB_by_area(section_nameg, sg)

                if np.abs(sd - sg) > 1e-3:
                    deb = (debd * (smil - sg) + debg * (sd - smil)) / (sd - sg)
                else:
                    deb = 0.5 * (debd + debg)

                frot = qmil * np.abs(qmil)/ (deb*deb)

                self.friction_source[i, 0] = 0
                self.friction_source[i, 1] = 2 * g * smil * frot



    '''计算Roe格式特征值 vvpropi.f90'''
    def Caculate_Roe_matrix(self):
        """
        for i in range(self.cell_num + 1):
            Roe_C = self.F_C[i] # Roe平均波速
            Roe_U = self.F_U[i] # Roe平均流速
            BETA = (self.BETA[i] + self.BETA[i + 1]) / 2
            eps = self.EPSILON
            Z = np.sqrt (Roe_C * Roe_C - (BETA * (1 - BETA) * Roe_U * Roe_U )) + eps

            self.Lambda1[i] = BETA * Roe_U - Z # 特征变量1
            self.Lambda2[i] = BETA * Roe_U + Z # 特征变量2

            'LeVeque修正'
            right_Frude = self.FR[i + 1]  # 界面右侧福汝德数
            left_Frude = self.FR[i]  # 界面左侧福汝德数

            if self.water_depth[i] > self.water_depth_limit and self.water_depth[i+1] > self.water_depth_limit:
                indic = True
            else:
                indic = False

            if right_Frude > 1 and left_Frude < 1 and Roe_U > 0 and indic:
                Lambda1D = BETA * self.U[i] - self.C[i]  # 采用界面左侧侧单元参数进行计算
                Lambda1G = BETA * self.U[i + 1] - self.C[i + 1] # 采用界面右侧
                self.Lambda1[i] = Lambda1G * (self.Lambda1[i] - Lambda1D) / (Lambda1G - Lambda1D)
                self.flag_LeVeque[i] = 2

            if right_Frude < 1 and left_Frude > 1 and Roe_U < 0 and indic:
                Lambda2D = BETA * self.U[i] + self.C[i]  # 采用界面左侧侧单元参数进行计算
                Lambda2G = BETA * self.U[i + 1] + self.C[i + 1]  # 采用界面右侧
                self.Lambda2[i] = Lambda2D * (self.Lambda2[i] - Lambda2G) / (Lambda2D - Lambda2G)
                self.flag_LeVeque[i] = 1 # LeVeque修正标识


            # 计算特征向量的绝对值
            self.abs_Lambda1[i] = np.abs(self.Lambda1[i])
            self.abs_Lambda2[i] = np.abs(self.Lambda2[i])

            # 计算波幅系数
            diff_S = self.S[i+1] - self.S[i]
            diff_Q = self.Q[i+1] - self.Q[i]
            self.alpha2[i] = (diff_Q - diff_S * (Roe_U - Roe_C)) / (2 * Roe_C)
            self.alpha1[i] = diff_S - self.alpha2[i]

            # 计算特征向量与逆矩阵向量
            Beta_U = BETA * Roe_U

            # 第一特征向量
            self.Vactor1[i, 0] = 1
            self.Vactor1[i, 1] = Beta_U - Z

            # 特征矩阵逆矩阵的第一向量
            self.Vactor1_T[i, 0] = (Beta_U + Z) / ((2 * Z))
            self.Vactor1_T[i, 1] = -1 / ((2 * Z))

            # 第二特征向量
            self.Vactor2[i, 0] = 1
            self.Vactor2[i, 1] = Beta_U + Z

            # 特征矩阵逆矩阵的第二向量
            self.Vactor2_T[i, 0] = -(Beta_U - Z) / ((2 * Z))
            self.Vactor2_T[i, 1] = 1 / ((2 * Z))
            """
        # 接口数
        N = self.cell_num + 1
        eps = self.EPSILON

        # ——— 1. 准备基础向量 ———
        Roe_C = self.F_C[:N]  # Roe 平均波速
        Roe_U = self.F_U[:N]  # Roe 平均流速
        BETA_arr = 0.5 * (self.BETA[:N] + self.BETA[1:N + 1])  # 接口处 BETA

        # ——— 2. 计算 Z, Lambda1, Lambda2 ———
        #   Z = sqrt(Roe_C² - BETA*(1-BETA)*Roe_U²) + eps
        tmp = BETA_arr * (1 - BETA_arr) * Roe_U ** 2
        Z = np.sqrt(np.maximum(Roe_C ** 2 - tmp, 0))
        Lambda1 = BETA_arr * Roe_U - Z
        Lambda2 = BETA_arr * Roe_U + Z

        # ——— 3. LeVeque 修正掩码 ———
        FR_L = self.FR[:N]
        FR_R = self.FR[1:N + 1]
        depth_L = self.water_depth[:N]
        depth_R = self.water_depth[1:N + 1]

        # 右侧单元为空以及两侧均有水的情况
        indic = (depth_L > self.water_depth_limit)

        mask1 = (FR_R > 1) & (FR_L < 1) & (Roe_U > 0) & indic  # 修正 λ1
        mask2 = (FR_R < 1) & (FR_L > 1) & (Roe_U < 0) & indic  # 修正 λ2

        # —— 3.1 λ1 修正
        if np.any(mask1):
            L1D = BETA_arr[mask1] * self.U[:N][mask1] - self.C[:N][mask1]
            L1G = BETA_arr[mask1] * self.U[1:N + 1][mask1] - self.C[1:N + 1][mask1]
            # 安全除法
            ratio1 = np.zeros_like(L1D)
            np.divide(
                Lambda1[mask1] - L1D,
                L1G - L1D,
                out=ratio1,
                where=(L1G - L1D) != 0
            )
            Lambda1[mask1] = L1G * ratio1
            self.flag_LeVeque[mask1] = 2

        # —— 3.2 λ2 修正
        if np.any(mask2):
            L2D = BETA_arr[mask2] * self.U[:N][mask2] + self.C[:N][mask2]
            L2G = BETA_arr[mask2] * self.U[1:N + 1][mask2] + self.C[1:N + 1][mask2]
            ratio2 = np.zeros_like(L2D)
            np.divide(
                Lambda2[mask2] - L2G,
                L2D - L2G,
                out=ratio2,
                where=(L2D - L2G) != 0
            )
            Lambda2[mask2] = L2D * ratio2
            self.flag_LeVeque[mask2] = 1

        # ——— 4. 绝对特征值 ———
        self.abs_Lambda1[:N] = np.abs(Lambda1)
        self.abs_Lambda2[:N] = np.abs(Lambda2)

        # ——— 5. 波幅系数 α1, α2 ———
        dS = self.S[1:N + 1] - self.S[:N]
        dQ = self.Q[1:N + 1] - self.Q[:N]
        # α2 = (dQ - dS*(Roe_U - Roe_C)) / (2*Roe_C)
        self.alpha2[:N] = (dQ - dS * (Roe_U - Roe_C)) / (2 * Roe_C + self.EPSILON)
        self.alpha1[:N] = dS - self.alpha2[:N]

        # ——— 6. 特征向量及其逆矩阵行 ———
        Beta_U = BETA_arr * Roe_U
        # Vactor1
        self.Vactor1[:N, 0] = 1
        self.Vactor1[:N, 1] = Beta_U - Z
        # Vactor1_T
        self.Vactor1_T[:N, 0] = (Beta_U + Z) / (2 * Z)
        self.Vactor1_T[:N, 1] = -1 / (2 * Z)
        # Vactor2
        self.Vactor2[:N, 0] = 1
        self.Vactor2[:N, 1] = Beta_U + Z
        # Vactor2_T
        self.Vactor2_T[:N, 0] = -(Beta_U - Z) / (2 * Z)
        self.Vactor2_T[:N, 1] = 1 / (2 * Z)

        # ——— 7. 最后写回 Lambda1, Lambda2 ———
        self.Lambda1[:N] = Lambda1
        self.Lambda2[:N] = Lambda2

    '''计算隐式格式的矩阵系数 matri.f90, vvprop.f90, matria.f90'''
    def Caculate_impli_trans_coefficient(self):
        # 保留增量的边界条件
        # self.V0[0] =  self.S_old[1] - self.V0[0]
        # self.V0[1] =  self.Q_old[1] - self.V0[1]
        # self.V1[0] =  self.S_old[-2] - self.V1[0]
        # self.V1[1] =  self.Q_old[-2] - self.V1[1]

        # 基于断面进行计算
        for i in range(self.cell_num + 1): # matri.f90
            X1 = self.Vactor1[i,0] * self.Vactor1_T[i,0]
            Y1 = self.Vactor2[i,0] * self.Vactor2_T[i,0]

            X2 = self.Vactor1[i,0] * self.Vactor1_T[i,1]
            Y2 = self.Vactor2[i,0] * self.Vactor2_T[i,1]

            X3 = self.Vactor1[i,1] * self.Vactor1_T[i,0]
            Y3 = self.Vactor2[i,1] * self.Vactor2_T[i,0]

            X4 = self.Vactor1[i,1] * self.Vactor1_T[i,1]
            Y4 = self.Vactor2[i,1] * self.Vactor2_T[i,1]

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

        # 基于断面重新计算向量
        for i in range(self.cell_num + 2): # vvprop.f90
            UG = self.U[i]
            CG = self.C[i]
            BETA = self.BETA[i]

            self.Lambda1I[i] = BETA * UG - np.sqrt( CG**2 - ( BETA * ( 1 - BETA ) * UG**2 ) )
            self.Lambda2I[i] = BETA * UG + np.sqrt( CG**2 - ( BETA * ( 1 - BETA ) * UG**2 ) )

            UG1 = BETA * UG
            CG1 = np.sqrt(CG ** 2 - BETA * (1 - BETA) * UG ** 2)

            self.Vactor1I[i, 0] = 1
            self.Vactor1I[i, 1] = UG1 - CG1
            self.Vactor1I_T[i, 0] = (UG1 + CG1) / (2 * CG1)
            self.Vactor1I_T[i, 1] = -1 / (2 * CG1)

            self.Vactor2I[i, 0] = 1
            self.Vactor2I[i, 1] = UG1 + CG1
            self.Vactor2I_T[i, 0] =  - (UG1 - CG1) / (2 * CG1)
            self.Vactor2I_T[i, 1] = 1 / (2 * CG1)

        # 基于断面计算系数
        for i in range(self.cell_num + 2): # matria.f90
            X1 = self.Vactor1I[i,0] * self.Vactor1I_T[i,0]
            Y1 = self.Vactor2I[i,0] * self.Vactor2I_T[i,0]
            X2 = self.Vactor1I[i,0] * self.Vactor1I_T[i,1]
            Y2 = self.Vactor2I[i,0] * self.Vactor2I_T[i,1]
            X3 = self.Vactor1I[i,1] * self.Vactor1I_T[i,0]
            Y3 = self.Vactor2I[i,1] * self.Vactor2I_T[i,0]
            X4 = self.Vactor1I[i,1] * self.Vactor1I_T[i,1]
            Y4 = self.Vactor2I[i,1] * self.Vactor2I_T[i,1]

            self.A[i, 0] = self.Lambda1I[i] * X1 + self.Lambda2I[i] * Y1
            self.A[i, 1] = self.Lambda1I[i] * X2 + self.Lambda2I[i] * Y2
            self.A[i, 2] = self.Lambda1I[i] * X3 + self.Lambda2I[i] * Y3
            self.A[i, 3] = self.Lambda1I[i] * X4 + self.Lambda2I[i] * Y4

    '计算Roe格式通量 数值文档'
    def Caculate_Roe_Flux_2(self):

        for i in range(self.cell_num + 1):
            # 重置对应参数，避免因未计算而带入上步结果
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

            PROD = self.Lambda1[i] * self.Lambda2[i]  # 用于判断流态P
            SAUTS = self.S[i + 1] - self.S[i]  # 右左单元过水断面面积差
            SAUTQ = self.Q[i + 1] - self.Q[i]  # 右左单元流量差

            # 界面交叉水深
            right_water_depth = self.water_depth[i] + self.river_bed_height[i] - self.river_bed_height[i + 1]
            left_water_depth = self.water_depth[i + 1] + self.river_bed_height[i + 1] - self.river_bed_height[i]

            # 获取右侧过水断面面积
            if right_water_depth < self.water_depth_limit:
                right_wetted_area = self.cross_section_table.get_area_by_depth(self.cell_sections[i + 1], self.water_depth_limit)
            else:
                right_wetted_area = self.cross_section_table.get_area_by_depth(self.cell_sections[i + 1], right_water_depth)

            # 获取左侧过水断面面积
            if left_water_depth < self.water_depth_limit:
                left_wetted_area = self.cross_section_table.get_area_by_depth(self.cell_sections[i], self.water_depth_limit)
            else:
                left_wetted_area = self.cross_section_table.get_area_by_depth(self.cell_sections[i], left_water_depth)

            # 计算过水断面面积关于x的导数
            z = 2 / self.cell_lengths[i]
            if left_water_depth < 0:
                DsDx = z * (right_wetted_area - self.S[i])
            elif right_water_depth < 0:
                DsDx = z * (self.S[i + 1] - left_wetted_area)
            else:
                DsDx = z * (self.S[i + 1] + right_wetted_area - self.S[i] - left_wetted_area) / 2

            # 计算压力源项目
            self.cell_press_source[i, 0] = 0
            self.cell_press_source[i, 1] = self.PRESS[i + 1] - self.PRESS[i]  # SOTILD(2) 加法后半部分需要重构

            # 数值重构系数
            sotild1 = - 2 * self.QIN[i + 1]
            sotild2 = - DsDx * self.F_C[i] * self.F_C[i]

            sofrot1 = self.friction_source[i, 0]
            sofrot2 = self.friction_source[i, 1]

            a = 0.5 * self.cell_lengths[i]

            # 判断水流流态
            if PROD > 0:  # 超临界流情况
                if self.F_U[i] > 0:  # 正流向
                    if self.water_depth[i] < self.water_depth_limit:  # 界面左侧单元为干
                        # 基于界面右侧网格参数进行计算
                        PSFLU1 = self.Vactor1_T[i, 0] * SAUTS + self.Vactor1_T[i, 1] * SAUTQ
                        PSFLU2 = self.Vactor2_T[i, 0] * SAUTS + self.Vactor2_T[i, 1] * SAUTQ
                        self.Flux_LOC[i, 0] = self.Q[i + 1] - (self.Vactor1[i, 0] * self.Lambda1[i] * PSFLU1 + self.Vactor2[i, 0] * self.Lambda2[i] * PSFLU2)  # 计算质量通量
                        self.Flux_LOC[i, 1] = (self.BETA[i + 1] * self.Q[i + 1] * self.Q[i + 1] / self.S[i + 1] + self.PRESS[i + 1] - (self.Vactor1[i, 1] * self.Lambda1[i] * PSFLU1 + self.Vactor2[i, 1] * self.Lambda2[i] * PSFLU2))  # 计算动量通量

                        # 源项数值重构
                        self.Flux_Source_right[i, 0] = 0
                        self.Flux_Source_right[i, 1] = 0
                        self.Flux_Source_left[i + 1, 0] = a * sotild1
                        self.Flux_Source_left[i + 1, 1] = a * sotild2

                        self.Flux_Friction_right[i, 0] = 0
                        self.Flux_Friction_right[i, 1] = 0
                        self.Flux_Friction_left[i + 1, 0] = a * sofrot1
                        self.Flux_Friction_left[i + 1, 1] = a * sofrot2
                    else:  # 界面左侧单元有水
                        # 基于界面左侧网格参数进行计算
                        self.Flux_LOC[i, 0] = self.Q[i]  # 计算质量通量
                        self.Flux_LOC[i, 1] = self.BETA[i] * self.Q[i] * self.Q[i] / self.S[i] + self.PRESS[i]  # 计算动量通量

                        # 源项数值重构
                        self.Flux_Source_right[i, 0] = a * sotild1
                        self.Flux_Source_right[i, 1] = a * sotild2
                        self.Flux_Source_left[i + 1, 0] = 0
                        self.Flux_Source_left[i + 1, 1] = 0

                        self.Flux_Friction_right[i, 0] = a * sofrot1
                        self.Flux_Friction_right[i, 1] = a * sofrot2
                        self.Flux_Friction_left[i + 1, 0] = 0
                        self.Flux_Friction_left[i + 1, 1] = 0

                else:  # 负流向
                    self.Flux_LOC[i, 0] = self.Q[i + 1]  # 计算质量通量
                    self.Flux_LOC[i, 1] = self.BETA[i + 1] * self.Q[i + 1] * self.Q[i + 1] / self.S[i + 1] + self.PRESS[i + 1]  # 计算动量通量

            else:  # 亚临界流
                if self.flag_LeVeque[i] == 1 or self.water_depth[i] <= self.EPSILON:  # 基于界面右侧网格计算
                    PSFLU = self.Vactor2_T[i, 0] * SAUTS + self.Vactor2_T[i, 1] * SAUTQ
                    self.Flux_LOC[i, 0] = self.Q[i + 1] - self.Lambda2[i] * PSFLU * self.Vactor2[i, 0]  # 计算质量通量
                    self.Flux_LOC[i, 1] = self.BETA[i + 1] * self.Q[i + 1] * self.Q[i + 1] / self.S[i + 1] + self.PRESS[i + 1] - self.Lambda2[i] * PSFLU * self.Vactor2[i, 1]  # 计算能量通量

                else:  # 基于界面左侧网格计算
                    PSFLU = self.Vactor1_T[i, 0] * SAUTS + self.Vactor1_T[i, 1] * SAUTQ
                    self.Flux_LOC[i, 0] = self.Q[i] + self.Lambda1[i] * PSFLU * self.Vactor1[i, 0]  # 计算质量通量
                    self.Flux_LOC[i, 1] = self.BETA[i] * self.Q[i] * self.Q[i] / self.S[i] + self.PRESS[i] + self.Lambda1[i] * PSFLU * self.Vactor1[i, 1]  # 计算能量通量

                    # 源项数值重构
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

            # 扣除粘滞项
            # self.Flux_LOC[i, 0] = self.Flux_LOC[i, 0] - self.dissipation1[i]
            # self.Flux_LOC[i, 1] = self.Flux_LOC[i, 1] - self.dissipation2[i]

            # 计算中心源项
            self.Flux_Source_center[i, 0] = self.cell_press_source[i, 0]
            self.Flux_Source_center[i, 1] = self.cell_press_source[i, 1]

            """
        N = self.cell_num + 1
        eps = self.EPSILON

        # ——— 1. 界面左右交叉水深（vectorized） ———
        h0 = self.water_depth[:N] + self.river_bed_height[:N] - self.river_bed_height[1:N + 1]
        h1 = self.water_depth[1:N + 1] + self.river_bed_height[1:N + 1] - self.river_bed_height[:N]

        # ——— 2. 保留过水断面面积循环调用 ———
        left_wet = np.zeros(N, dtype=float)
        right_wet = np.zeros(N, dtype=float)
        for i in range(N):
            if h0[i] < self.water_depth_limit:
                # left_wet[i] = 0
                left_wet[i] = self.cross_section_table.get_area_by_depth(self.cell_sections[i], self.water_depth_limit)
            else:
                left_wet[i] = self.cross_section_table.get_area_by_depth(self.cell_sections[i], h0[i])

            if h1[i] < self.water_depth_limit:
                # right_wet[i] = 0
                right_wet[i] = self.cross_section_table.get_area_by_depth(self.cell_sections[i+1], self.water_depth_limit)
            else:
                right_wet[i] = self.cross_section_table.get_area_by_depth(self.cell_sections[i+1], h1[i])

        # ——— 3. 基本切片取值 ———
        S0, S1 = self.S[:N], self.S[1:N + 1]
        Q0, Q1 = self.Q[:N], self.Q[1:N + 1]
        P0, P1 = self.PRESS[:N], self.PRESS[1:N + 1]
        U0, U1 = self.U[:N], self.U[1:N + 1]
        Fc = self.F_C[:N]
        Fr0, Fr1 = self.FR[:N], self.FR[1:N + 1]
        β0, β1 = self.BETA[:N], self.BETA[1:N + 1]
        Λ1, Λ2 = self.Lambda1[:N], self.Lambda2[:N]
        a = 0.5 * self.cell_lengths[:N]
        sot1 = -2 * self.QIN[1:N + 1]
        sof1 = self.friction_source[:N, 0]
        sof2 = self.friction_source[:N, 1]
        V1, V2 = self.Vactor1[:N], self.Vactor2[:N]
        V1T, V2T = self.Vactor1_T[:N], self.Vactor2_T[:N]

        # ——— 4. 交叉量和源项 DSQ, DSX ———
        SAUTS = S1 - S0
        SAUTQ = Q1 - Q0

        dx_inv = 2.0 / self.cell_lengths[:N]
        # DsDx 三段式
        DsDx = np.empty(N)
        m1 = h0 < 0
        m2 = (h0 >= 0) & (h1 < 0)
        m3 = ~(m1 | m2)
        DsDx[m1] = dx_inv[m1] * (right_wet[m1] - S0[m1])
        DsDx[m2] = dx_inv[m2] * (S1[m2] - left_wet[m2])
        DsDx[m3] = dx_inv[m3] * (S1[m3] + right_wet[m3] - S0[m3] - left_wet[m3]) / 2.0

        # ——— 5. cell_press_source, 重构系数 sotild2 ———
        self.cell_press_source[:N, 0] = 0
        self.cell_press_source[:N, 1] = P1 - P0
        sot2 = - DsDx * Fc * Fc

        # ——— 6. 初始化所有输出为 0 ———
        self.Flux_LOC[:N, :] = 0
        self.Flux_Source_right[:N, :] = 0
        self.Flux_Source_left[:N + 1, :] = 0
        self.Flux_Friction_right[:N, :] = 0
        self.Flux_Friction_left[:N + 1, :] = 0
        self.Flux_Source_center[:N, 0] = 0
        self.Flux_Source_center[:N, 1] = self.cell_press_source[:N, 1]

        # ——— 7. 流态掩码 ———
        PROD = Λ1 * Λ2
        sup_mask = PROD > 0
        pos_mask = sup_mask & (self.F_U[:N] > 0)
        neg_mask = sup_mask & ~pos_mask

        # — 7.1 超临界 & 正流向 & 左干
        m = pos_mask & (self.water_depth[:N] < eps)
        if m.any():
            idx = np.nonzero(m)[0]
            PS1 = V1T[idx, 0] * SAUTS[idx] + V1T[idx, 1] * SAUTQ[idx]
            PS2 = V2T[idx, 0] * SAUTS[idx] + V2T[idx, 1] * SAUTQ[idx]
            self.Flux_LOC[idx, 0] = Q1[idx] - (V1[idx, 0] * Λ1[idx] * PS1 + V2[idx, 0] * Λ2[idx] * PS2)
            self.Flux_LOC[idx, 1] = (β1[idx] * Q1[idx] ** 2 / S1[idx] + P1[idx]
                                     - (V1[idx, 1] * Λ1[idx] * PS1 + V2[idx, 1] * Λ2[idx] * PS2))
            self.Flux_Source_left[idx + 1, :] = np.stack([a[idx] * sot1[idx], a[idx] * sot2[idx]], axis=1)
            self.Flux_Friction_left[idx + 1, :] = np.stack([a[idx] * sof1[idx], a[idx] * sof2[idx]], axis=1)

        # — 7.2 超临界 & 正流向 & 左有水
        m = pos_mask & (self.water_depth[:N] >= eps)
        if m.any():
            idx = np.nonzero(m)[0]
            self.Flux_LOC[idx, 0] = Q0[idx]
            self.Flux_LOC[idx, 1] = β0[idx] * Q0[idx] ** 2 / S0[idx] + P0[idx]
            self.Flux_Source_right[idx, :] = np.stack([a[idx] * sot1[idx], a[idx] * sot2[idx]], axis=1)
            self.Flux_Friction_right[idx, :] = np.stack([a[idx] * sof1[idx], a[idx] * sof2[idx]], axis=1)

        # — 7.3 超临界 & 负流向
        if neg_mask.any():
            idx = np.nonzero(neg_mask)[0]
            self.Flux_LOC[idx, 0] = Q1[idx]
            self.Flux_LOC[idx, 1] = β1[idx] * Q1[idx] ** 2 / S1[idx] + P1[idx]

        # — 8. 亚临界流分支
        sub_mask = ~sup_mask
        sub_r_mask = sub_mask & ((self.flag_LeVeque[:N] == 1) | (self.water_depth[:N] <= eps))
        sub_l_mask = sub_mask & ~sub_r_mask

        # 8.1 亚 & 右特征
        if sub_r_mask.any():
            idx = np.nonzero(sub_r_mask)[0]
            PS = V2T[idx, 0] * SAUTS[idx] + V2T[idx, 1] * SAUTQ[idx]
            self.Flux_LOC[idx, 0] = Q1[idx] - Λ2[idx] * PS * V2[idx, 0]
            self.Flux_LOC[idx, 1] = (β1[idx] * Q1[idx] ** 2 / S1[idx] + P1[idx]
                                     - Λ2[idx] * PS * V2[idx, 1])

        # 8.2 亚 & 左特征
        if sub_l_mask.any():
            idx = np.nonzero(sub_l_mask)[0]
            PS = V1T[idx, 0] * SAUTS[idx] + V1T[idx, 1] * SAUTQ[idx]
            self.Flux_LOC[idx, 0] = Q0[idx] + Λ1[idx] * PS * V1[idx, 0]
            self.Flux_LOC[idx, 1] = β0[idx] * Q0[idx] ** 2 / S0[idx] + P0[idx] + Λ1[idx] * PS * V1[idx, 1]
            PSSOD = a[idx] * (V1T[idx, 0] * sot1[idx] + V1T[idx, 1] * sot2[idx])
            PSSOG = a[idx] * (V2T[idx, 0] * sot1[idx] + V2T[idx, 1] * sot2[idx])
            self.Flux_Source_right[idx, :] = np.stack([V1[idx, 0] * PSSOD, V1[idx, 1] * PSSOD], axis=1)
            self.Flux_Source_left[idx + 1, :] = np.stack([V2[idx, 0] * PSSOG, V2[idx, 1] * PSSOG], axis=1)

        # ——— 9. 扣除耗散 ———
        self.Flux_LOC[:N, 0] -= self.dissipation1[:N]
        self.Flux_LOC[:N, 1] -= self.dissipation2[:N]
"""
    '''计算溢流坝影响'''
    def Caculate_dam(self):
        pass

    '''向下取整，保留两位小数'''
    def Floor2(sele, x) :
        """向下取整，保留两位小数"""
        return np.floor (x * 100) / 100.0

    '''废弃----基于时间步累计和CFL条件，推求合适的时间步长'''
    def Calculate_advance_dt(self, cfl_dt, current_total, report_dt) :
        """
        根据 CFL 计算得到的 dt（cfl_dt）与累计时间 current_total，
        确定本步应使用的实际 dt (advance_dt)，使得输出时刻恰好为 report_dt。

        参数:
          cfl_dt: 当前计算得到的 CFL 时间步长（可能较小）。
          current_total: 当前时间步累计的 dt。
          report_dt: 指定的输出时间步长。

        返回:
          advance_dt: 本次时间步的 dt（向下取整到两位小数）。
          current_total: 更新后的累计时间步（若达到或超过 report_dt，则重置为 0）。
        """
        if current_total + cfl_dt > report_dt :
            # 如果累计时间加上当前 dt 超过报告时刻，
            # 则取剩余时间作为当前 dt，并重置累计时间
            advance_dt = self.Floor2 (report_dt - current_total)
            current_total = 0.0
        else :
            advance_dt = self.Floor2 (cfl_dt)
            current_total += advance_dt
        return advance_dt, current_total

    '''通量组合  数值文档'''
    def Assemble_Flux_2(self):
        """
        WW = np.zeros(2)
        flux_1 = []
        flux_2 = []
        for i in range(1, self.cell_num + 1):
            Q_old = self.Q[i]
            S_old = self.S[i]

            self.Flux[i, 0] = (self.Flux_LOC[i, 0] - self.Flux_LOC[i - 1, 0] + self.Flux_Source_right[i, 0] + self.Flux_Source_left[i, 0] + self.Flux_Friction_left[i,0] + self.Flux_Friction_right[i,0])
            self.Flux[i, 1] = (self.Flux_LOC[i, 1] - self.Flux_LOC[i - 1, 1] + self.Flux_Source_center[i, 1] + self.Flux_Source_right[i, 1] + self.Flux_Source_left[i, 1] + self.Flux_Friction_left[i,1]+self.Flux_Friction_right[i,1]) # +格左 + 格右

            WW[0] = - self.Flux[i, 0] * self.DT / self.cell_lengths[i]
            WW[1] = - self.Flux[i, 1] * self.DT / self.cell_lengths[i]

            self.S[i] = S_old + WW[0] # 更新过水断面面积
            self.Q[i] = Q_old + WW[1] # 更新流量

            if self.S[i] < 0:
                print('网格位置',i)
                print('时间步长',self.DT)
                print('过水面积',self.S[i])
                print('上一时间步过水面积',S_old)
                print('叠加参数',WW[0])
                print('计算通量',self.Flux[i, 0])
                exit('计算过水面积小于零')
            pass

            # 更新流速和波速
            self.U[i] = self.Q[i] / self.S[i]
            # 获取断面点
            section_points = self.sections_data[self.cell_sections[i]]
            # 计算水面宽度
            water_surface_width = self.Calculate_water_surface_width_by_water_depth(section_points, self.water_depth[i])

            # 计算波速
            if water_surface_width > self.EPSILON and self.S[i] > self.EPSILON:
                self.C[i] = np.sqrt(self.g * self.S[i] / water_surface_width)
                self.FR[i] = np.abs(self.U[i]) / self.C[i]  # 计算福汝德数
            else:
                self.C[i] = self.EPSILON
                self.FR[i] = np.abs(self.U[i]) / self.C[i]  # 计算福汝德数
        """
        N = self.cell_num
        # 1. 计算所有 i=1…N 的总通量 Flux[i]
        #   flux_div = Flux_LOC[i] - Flux_LOC[i-1]
        flux_div = self.Flux_LOC[1:N + 1] - self.Flux_LOC[:N]
        #   sum_sources = right + left + friction_right + friction_left
        sum_src = (
                self.Flux_Source_right[1:N + 1]
                + self.Flux_Source_left[1:N + 1]
                + self.Flux_Friction_right[1:N + 1]
                + self.Flux_Friction_left[1:N + 1]
        )
        #   center 源只加到动量分量（第 1 分量）
        sum_src[:, 1] += self.Flux_Source_center[1:N + 1, 1]
        #   赋值
        self.Flux[1:N + 1] = flux_div + sum_src

        # 2. 计算增量 WW = -Flux * DT / cell_length
        lengths = self.cell_lengths[1:N + 1]  # shape (N,)
        ww = - self.Flux[1:N + 1] * (self.DT / lengths)[:, None]  # (N,2)

        # 3. 更新 S, Q
        S_old = self.S[1:N + 1].copy()
        Q_old = self.Q[1:N + 1].copy()
        self.S[1:N + 1] = S_old + ww[:, 0]
        self.Q[1:N + 1] = Q_old + ww[:, 1]

        '''半隐式处理源项'''
        if self.FRTIMP:
            for i in range(1, self.cell_num + 1):
                if self.S[i] < self.S_limit:
                    self.S[i] = self.cross_section_table.get_area_by_depth(self.cell_sections[i], self.water_depth_limit)
                    self.Q[i] = 0
                    self.U[i] = 0
                    self.C[i] = 0
                    self.FR[i] = 0
                else:
                    # if self.U[i] > 0:
                    #     d = i + 1
                    #     g = i
                    #
                    #     sd = self.S[d]
                    #     sg = self.S[g]
                    #
                    #     smil = 0.5 * (sg + sd)
                    #
                    #     section_nameg = self.cell_sections[g]
                    #     section_named = self.cell_sections[d]
                    #
                    #     debd = self.cross_section_table.get_DEB_by_area(section_named, sd)
                    #     debg = self.cross_section_table.get_DEB_by_area(section_nameg, sg)
                    # else:
                    #     d = i
                    #     g = i - 1
                    #
                    #     sd = self.S[d]
                    #     sg = self.S[g]
                    #
                    #     smil = 0.5 * (sg + sd)
                    #
                    #     section_nameg = self.cell_sections[g]
                    #     section_named = self.cell_sections[d]
                    #
                    #     debd = self.cross_section_table.get_DEB_by_area(section_named, sd)
                    #     debg = self.cross_section_table.get_DEB_by_area(section_nameg, sg)
                    #
                    # if np.abs(sd - sg) > 1e-3:
                    #     deb = (debd * (smil - sg) + debg * (sd - smil)) / (sd - sg)
                    # else:
                    #     deb = 0.5 * (debd + debg)

                    deb = self.cross_section_table.get_DEB_by_area(self.cell_sections[i], self.S[i])

                    coef = self.g * self.DT * self.S[i] / (deb * deb)

                    delta = (1 + 4 * coef * np.abs(self.Q[i]))

                    if coef > 1e-6:
                        if self.Q[i] > 0:
                            self.Q[i] = (-1 + np.sqrt(delta)) / (2 * coef)
                        else:
                            self.Q[i] = (1 - np.sqrt(delta)) / (2 * coef)
                    else:
                        self.Q[i] = self.Q[i] * (1 - coef * self.Q[i])

        # 6. 保留水面宽度 & 波速/弗劳德数的小循环
        for i in range(1, N + 1):
            if self.S[i] < self.S_limit:
                # print('修正前索引', i, ', 过水面积：', self.S[i], ', 流量：', self.Q[i])
                self.S[i] = self.cross_section_table.get_area_by_depth(self.cell_sections[i], self.water_depth_limit)
                self.Q[i] = 0
                self.U[i] = 0
                self.C[i] = 0
                self.FR[i] = 0
            else:
                self.U[i] = self.Q[i] / self.S[i]
                wsw = self.cross_section_table.get_width_by_area(self.cell_sections[i], self.S[i])

                depth = self.water_depth[i]
                wsw = self.S[i] / depth

                if wsw > self.EPSILON:
                    self.C[i] = np.sqrt(self.g * self.S[i] / wsw)
                    self.FR[i] = np.abs(self.U[i]) / self.C[i]
                else:
                    self.C[i] = 0
                    self.FR[i] = 0

    # 隐式计算通量组装
    def Assemble_Flux_impli_trans(self):
        # 记录上一步历史数据
        self.S_old[1:-2] = self.S[1:-2].copy()
        self.Q_old[1:-2] = self.Q[1:-2].copy()

        # 中间值矩阵
        L = np.zeros((4, self.cell_num + 2))
        M = np.zeros_like(L)
        N = np.zeros_like(L)
        WW1 = np.zeros((2, self.cell_num + 2))

        A = self.A
        D = self.D
        ID = self.ID
        DT = self.DT


        for i in range(1, self.cell_num + 1):
            self.Flux[i, 0] = (self.Flux_LOC[i, 0] - self.Flux_LOC[i - 1, 0] + self.Flux_Source_right[i, 0] +
                               self.Flux_Source_left[i, 0] + self.Flux_Friction_left[i, 0] + self.Flux_Friction_right[
                                   i, 0])
            self.Flux[i, 1] = (self.Flux_LOC[i, 1] - self.Flux_LOC[i - 1, 1] + self.Flux_Source_center[i, 1] +
                               self.Flux_Source_right[i, 1] + self.Flux_Source_left[i, 1] + self.Flux_Friction_left[
                                   i, 1] + self.Flux_Friction_right[i, 1])  # +格左 + 格右

            # 构建系数矩阵
            k = i
            dx_2 = self.cell_lengths[i + 1] + self.cell_lengths[i - 1]
            for j in range(4):
                L[j, k] = -(A[i - 1, j] + D[i - 1, j]) * DT / dx_2
                M[j, k] = ID[i, j] + (D[i - 1, j] + D[i, j]) * DT / dx_2
                N[j, k] = (A[i + 1, j] - D[i, j]) * DT / dx_2

        NC = self.cell_num + 1
        for j in range(4):
            L[j,0] = 0
            N[j,0] = 0
            L[j,NC] = 0
            N[j,NC] = 0

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
            '''flux末尾会出现nan，造成全局nan'''
            WW1[0, k] = - self.Flux[i, 0] * 2 * DT / dx_2
            WW1[1, k] = - self.Flux[i, 1] * 2 * DT / dx_2

        '''两侧封闭边界有问题，下边界问题更大一点'''
        WW1[0, 0] = self.V0[0]
        WW1[1, 0] = self.V0[1]
        WW1[0, NC] = self.V1[0]
        WW1[1, NC] = self.V1[1]

        WW2 = self.bissn(WW1, L, M, N, NC)

        for i in range(1, self.cell_num + 1):
            k = i
            self.S[i] = self.S_old[i] + WW2[0,k]
            self.Q[i] = self.Q_old[i] + WW2[1,k]

            if np.abs(self.S[i]) < self.EPSILON: self.S[i] = self.EPSILON

            if self.S[i] < 0:
                import warnings
                print('网格位置', i)
                print('时间步长', self.DT)
                print('过水面积', self.S[i])
                print('上一时间步过水面积', self.S_old[i])
                print('叠加参数', WW2[0,i])
                print('计算通量', self.Flux[i, 0])
                self.S[i] = self.EPSILON
                warnings.simplefilter("always", RuntimeWarning)
                warnings.warn('计算过水面积小于零，已重置为最小值')
                print(' ')

            # 更新流速和波速
            self.U[i] = self.Q[i] / self.S[i]

            # 计算水面宽度
            water_surface_width = self.cross_section_table.get_width_by_area(self.cell_sections[i],  self.S[i])

            # 计算波速
            if water_surface_width > self.EPSILON and self.S[i] > self.EPSILON:
                self.C[i] = np.sqrt(self.g * self.S[i] / water_surface_width)
                self.FR[i] = np.abs(self.U[i]) / self.C[i]  # 计算福汝德数
            else:
                self.C[i] = self.EPSILON
                self.FR[i] = np.abs(self.U[i]) / self.C[i]  # 计算福汝德数

    '''追赶法求解矩阵'''
    def bissn(self, X, A, B, C, KM):
        """
        用稀疏矩阵复现 MASCARET 中的块三对角追赶算法 BISSN1。

        参数
        ----
        X : np.ndarray, shape=(n, KM)
            右端项；On output 会被覆盖成解向量。
        A, B, C : np.ndarray, shape=(n*n, KM)
            三条对角的块矩阵，每列都是按 Fortran 列主序 flatten 的 n×n 矩阵。
        KM : int
            块的数量（Fortran 里的 KM）。
        NFU : int
            功能数，Fortran 中仅支持 NFU=1（即 n=2）。
        返回
        ----
        np.ndarray, shape=(n, KM)
            返回解矩阵（与 X 同形），同时 X 也被改写为该值。
        """
        KM = KM + 1
        n = X.shape[0]
        if A.shape != (n * n, KM) or B.shape != (n * n, KM) or C.shape != (n * n, KM):
            print(f'A的形状是{A.shape}')
            print(f'B的形状是{B.shape}')
            print(f'C的形状是{C.shape}')
            raise ValueError(f"A,B,C 必须是 ({n * n}, {KM}) 形状")
        # ——组装稀疏块三对角矩阵——
        # blocks[i][j] 对应大矩阵的第 i 块行、第 j 块列
        blocks = [[None] * KM for _ in range(KM)]
        for k in range(KM):
            # 主对角 B_k
            blocks[k][k] = B[:, k].reshape((n, n))
            # 下对角 A_k (对应 x_{k-1})
            if k > 0:
                blocks[k][k - 1] = A[:, k].reshape((n, n))
            # 上对角 C_k (对应 x_{k+1})
            if k < KM - 1:
                blocks[k][k + 1] = C[:, k].reshape((n, n))

        M = bmat(blocks, format="csc")

        # ——组装 RHS，求解——
        rhs = X.reshape((n * KM,))
        sol = spsolve(M, rhs)

        # ——返回并替换原 X——
        Xsol = sol.reshape((n, KM))
        return Xsol

    '''计算时间步长'''
    def Caculate_CFL_time(self):
            """
            self.DT_old = self.DT # 保存上一时间步长
            DT_temp = self.DT_old + 10
            for i in range(1, self.cell_num + 1):
                CNODE1 = self.U[i] - self.C[i]
                CNODE2 = self.U[i] + self.C[i]
                CNODE = max(abs(CNODE1), abs(CNODE2))

                COU = np.abs(CNODE / self.cell_lengths[i])
                self.DTI [i] = self.CFL / COU

                DT_temp = min(DT_temp, self.DTI[i])
                # if DT_temp < 0.001: DT_temp = 0.005
            self.DT = DT_temp
            self.current_sim_time += self.DT
            """
            # 保存上一时间步长
            self.DT_old = self.DT
            # 设一个上限
            DT_limit = self.DT_old + 10

            # 只处理 i=1…cell_num 的切片
            i0 = 0
            i1 = self.cell_num + 2

            # 1. 取出 U, C, cell_lengths 三个数组切片
            U_slice = self.U[i0:i1]
            C_slice = self.C[i0:i1]
            L_slice = self.cell_lengths[i0:i1]

            # 2. 计算 CNODE = max(|U-C|, |U+C|)
            #    |U-C|
            diff1 = np.abs(U_slice - C_slice)
            #    |U+C|
            diff2 = np.abs(U_slice + C_slice)
            #    取两者元素级最大值
            CNODE = np.maximum(diff1, diff2)

            CNODE = np.clip(CNODE, 1e-3, None)

            # 3. 计算 COU = |CNODE / Δx|
            COU = CNODE / L_slice  # 已经都是正数

            # 4. 批量更新 self.DTI
            self.DTI[i0:i1] = self.CFL / COU

            # 5. 直接取最小值
            dt_min = self.DTI[i0:i1].min()

            # 6. 取全局最小
            self.DT = min(DT_limit, dt_min) # CFL条件DT

            if self.DT < 1e-5: self.DT = 1e-5

            self.DT = np.minimum(self.DT, self.DT_old * self.DT_increase_factor) # 允许增长的最大DT

            self.DT = np.minimum(self.DT, self.Max_time_step)

            # 7. 推进仿真时间
            self.current_sim_time += self.DT

    def get_current_dt(self):
        print(f'河道{self.name}当前时间步长为：{self.DT}')

    def set_next_dt(self, next_dt):
        """
        设置下一个时间步长，通常用于在仿真过程中调整时间步长。
        :param next_dt: 下一个时间步长
        """
        if next_dt > 0:
            self.DT = next_dt # 设定下一个时间步长
            self.current_sim_time += self.DT # 更新当前仿真时间
        else:
            raise ValueError("时间步长必须大于零。")

    def Caculate_CFL_time_for_river_net(self):
            # 保存上一时间步长
            self.DT_old = self.DT
            # 设一个上限
            DT_limit = self.DT_old + 10

            # 只处理 i=1…cell_num 的切片
            i0 = 0
            i1 = self.cell_num + 2

            # 1. 取出 U, C, cell_lengths 三个数组切片
            U_slice = self.U[i0:i1]
            C_slice = self.C[i0:i1]
            L_slice = self.cell_lengths[i0:i1]

            # 2. 计算 CNODE = max(|U-C|, |U+C|)
            #    |U-C|
            diff1 = np.abs(U_slice - C_slice)
            #    |U+C|
            diff2 = np.abs(U_slice + C_slice)
            #    取两者元素级最大值
            CNODE = np.maximum(diff1, diff2)

            CNODE = np.clip(CNODE, 1e-3, None)

            # 3. 计算 COU = |CNODE / Δx|
            COU = CNODE / L_slice  # 已经都是正数

            # 4. 批量更新 self.DTI
            self.DTI[i0:i1] = self.CFL / COU

            # 5. 直接取最小值
            dt_min = self.DTI[i0:i1].min()

            # 6. 取全局最小
            self.DT = min(DT_limit, dt_min) # CFL条件DT

            if self.DT < 1e-5: self.DT = 1e-5

            DT = np.minimum(self.DT, self.DT_old * self.DT_increase_factor) # 允许增长的最大DT
            return DT

    '''将结果合并、重采样并保存出去'''
    def Resample_and_Save_Output_result(self):
        # 1) 拼接数据
        ds_data = xr.concat(self.ds_list, dim='time')
        ds = self.ds_coords.merge(ds_data)

        # 2) 等时插值
        t_fixed = np.arange(0, ds.time.max().item(), self.time_step)
        ds_fixed = ds.interp(time=t_fixed)
        if self.save_result_name == None:
            # 3) 输出路径
            out_raw = os.path.join(self.output_folder_path, f"{self.model_name}_raw_output.nc")
            out_interp = os.path.join(self.output_folder_path, f"{self.model_name}_interpolated_output.nc")

            # 4) 如果文件存在，就先删除
            for p in (out_raw, out_interp):
                if os.path.exists(p):
                    os.remove(p)

            # 5) 强制用写模式 + h5netcdf 引擎保存
            ds.to_netcdf(
                path=out_raw,
                mode='w',
                format='NETCDF4',
                engine='h5netcdf'
            )
            ds_fixed.to_netcdf(
                path=out_interp,
                mode='w',
                format='NETCDF4',
                engine='h5netcdf'
            )
        else:
            output_path = os.path.join(self.output_folder_path, self.save_result_name, '.nc')
            if os.path.exists(output_path):
                os.remove(output_path)

            ds_fixed.to_netcdf(
                path=output_path,
                mode='w',
                format='NETCDF4',
                engine='h5netcdf'
                        )

    '''检查并保存结果'''
    def Check_Resample_and_Save_Output_result(self):
        """
        将 self.ds_list 中每一小段结果沿 time 维连接，统一时间坐标（去重+排序），
        再按固定步长重采样并保存 NetCDF。
        兼容 time 为 float（秒/小时等）或 datetime64 两种情形。
        """
        import os
        import numpy as np
        import pandas as pd
        import xarray as xr

        # ------------------------------
        # 0) 小工具：检查/统一 time 坐标
        # ------------------------------
        def _make_unique_time(ds: xr.Dataset,
                              dim: str = "time",
                              float_round_decimals: int = 6,
                              dt_floor_freq: str = "S",
                              agg: str = "mean") -> xr.Dataset:
            """
            返回“time 唯一且有序”的 Dataset：
            - 若 time 为 float：先 round 再 groupby(time).agg；
            - 若 time 为 datetime64：先 floor 到指定粒度（默认秒）再 groupby；
            - 末尾 sortby(time)。
            """
            if dim not in ds.coords:
                raise KeyError(f"Dataset 中不存在坐标 {dim!r}")

            t = ds[dim].values
            ds2 = ds.copy()

            if np.issubdtype(t.dtype, np.floating):
                # 浮点时间（常见：以秒或小时作为浮点）：四舍五入规一，去掉“近重复”
                t_new = np.round(t, float_round_decimals)
                ds2 = ds2.assign_coords({dim: t_new})

            elif np.issubdtype(t.dtype, np.datetime64):
                # 日期时间：统一到秒（或你需要的精度），避免纳秒级混乱
                t_new = pd.to_datetime(t).floor(dt_floor_freq).to_numpy()
                ds2 = ds2.assign_coords({dim: t_new})

            # groupby 合并重复（按聚合方式）
            gb = ds2.groupby(dim)
            if   agg == "mean":   ds2 = gb.mean()
            elif agg == "median": ds2 = gb.median()
            elif agg == "first":  ds2 = gb.first()
            elif agg == "last":   ds2 = gb.last()
            elif agg == "max":    ds2 = gb.max()
            elif agg == "min":    ds2 = gb.min()
            else:
                raise ValueError("agg 必须为 mean/median/first/last/max/min 之一")

            # 排序，保证单调递增
            ds2 = ds2.sortby(dim)
            return ds2

        # ------------------------------
        # 1) 拼接数据
        # ------------------------------
        # （注）xr.concat 后 time 可能无序或有重复（来自块边界或浮点误差）
        ds_data = xr.concat(self.ds_list, dim='time')
        ds = self.ds_coords.merge(ds_data)

        # ------------------------------
        # 2) 统一 time（去重 + 排序）
        # ------------------------------
        # 对 float 时间保留 1e-6 精度，对 datetime 统一到秒；聚合方式用 mean（如需改成 first/last 请自行替换）
        ds = _make_unique_time(ds, dim='time', float_round_decimals=6, dt_floor_freq='S', agg='mean')

        # ------------------------------
        # 3) 生成等时刻序列 t_fixed （包含末端）
        # ------------------------------
        t0 = ds['time'].values[0]
        t1 = ds['time'].values[-1]

        # self.time_step：建议含义为“秒”的步长（整数）
        step = int(self.time_step)

        if np.issubdtype(ds['time'].dtype, np.floating):
            # 浮点时间（通常是“秒”或“小时”）
            # 若你的 time 是“小时”，请把 step 换算为“小时步长”（如 step/3600.0）
            # 这里假设你的 time 单位为“秒”（和 self.time_step 一致）：
            start = float(t0)
            end   = float(t1)
            # arange 不包含右端点，这里 +step*0.5 以确保最后一个点能覆盖到 end（数值稳定）
            t_fixed = np.arange(start, end + step * 0.5, step, dtype=float)

            # 如果你的 time 实际是“小时”，请改为：
            # t_fixed = np.arange(start, end + (step/3600.0)*0.5, step/3600.0, dtype=float)

        elif np.issubdtype(ds['time'].dtype, np.datetime64):
            # 日期时间：用 pandas 生成等间隔时序（freq=step 秒）
            start = pd.to_datetime(t0)
            end   = pd.to_datetime(t1)
            # pandas.date_range 是闭区间（包含 end），刚好满足需求
            t_fixed = pd.date_range(start=start, end=end, freq=f'{step}S').to_numpy()

        else:
            raise TypeError(f"不支持的 time dtype: {ds['time'].dtype}")

        # 为安全起见，再按 time 的取值范围裁剪一下（避免极端情况下 extrapolate）
        # （xarray 的 interp 默认不外推）
        tmin = ds['time'].values[0]
        tmax = ds['time'].values[-1]
        if np.issubdtype(ds['time'].dtype, np.floating):
            t_fixed = t_fixed[(t_fixed >= tmin) & (t_fixed <= tmax)]
        else:
            # datetime 情形
            t_fixed = t_fixed[(t_fixed >= pd.to_datetime(tmin)) & (t_fixed <= pd.to_datetime(tmax))]

        # ------------------------------
        # 4) 等时插值（此时 time 唯一且有序，不会再报错）
        # ------------------------------
        ds_fixed = ds.interp(time=t_fixed)

        # ------------------------------
        # 5) 保存 NetCDF（修复文件名拼接错误）
        # ------------------------------
        if self.save_result_name is None:
            # 输出路径
            out_raw = os.path.join(self.output_folder_path, f"{self.model_name}_raw_output.nc")
            out_interp = os.path.join(self.output_folder_path, f"{self.model_name}_interpolated_output.nc")

            # 如果文件存在，就先删除
            for p in (out_raw, out_interp):
                if os.path.exists(p):
                    os.remove(p)

            # 强制用写模式 + h5netcdf 引擎保存
            ds.to_netcdf(
                path=out_raw,
                mode='w',
                format='NETCDF4',     # 对 h5netcdf 来说这个参数会被忽略，不影响
                engine='h5netcdf'
            )
            ds_fixed.to_netcdf(
                path=out_interp,
                mode='w',
                format='NETCDF4',
                engine='h5netcdf'
            )
        else:
            # 你原先写成 os.path.join(..., self.save_result_name, '.nc') 会变成目录/.nc；应当拼成 “name.nc”
            output_path = os.path.join(self.output_folder_path, f"{self.save_result_name}.nc")
            if os.path.exists(output_path):
                os.remove(output_path)

            ds_fixed.to_netcdf(
                path=output_path,
                mode='w',
                format='NETCDF4',
                engine='h5netcdf'
            )

    '''将每一时间步的结果保存出去'''
    def Save_result_per_time_step(self):
        """
        在每个时间步调用，生成一个只有 time, space, and data_vars 的 Dataset
        """
        # 取中间网格数据
        depth = self.water_depth[1:self.cell_num + 1].copy()
        level = self.water_level[1:self.cell_num + 1].copy()
        U = self.U[1:self.cell_num + 1].copy()
        Q = self.Q[1:self.cell_num + 1].copy()

        # 封装成一个小 Dataset
        ds_t = xr.Dataset(
            data_vars={
                'depth': (('time', 'space'), depth[np.newaxis, :]),
                'level': (('time', 'space'), level[np.newaxis, :]),
                'U': (('time', 'space'), U[np.newaxis, :]),
                'Q': (('time', 'space'), Q[np.newaxis, :]),
            },
            coords={
                'time': [self.current_sim_time],  # 本步时刻
                'space': self.ds_coords.coords['space'].values,  # 复用已定义的 space
            }
        )
        self.ds_list.append(ds_t)

    '''初始化保存数据，保存坐标结果'''
    def Save_Basic_data(self):
        # 过程数据
        self.ds_list = []

        # 只保存中间网格参数，不保存两侧边界网格
        space = np.arange(self.cell_num)
        x = self.cell_pos[1:self.cell_num + 1, 0]
        y = self.cell_pos[1:self.cell_num + 1, 1]
        z = self.cell_pos[1:self.cell_num + 1, 2]

        # 经纬度坐标转化
        print('经纬度转化')
        transformer = Transformer.from_crs("EPSG:4546", "EPSG:4490", always_xy=True)
        lon, lat = transformer.transform(x, y)  # 返回 (lon_array, lat_array)
        # print(lon, lat)
        # 保存坐标数据
        self.ds_coords = xr.Dataset(
            coords={
                'space': space,
                'x': ('space', x),
                'y': ('space', y),
                'z': ('space', z),
                'lon': ('space', lon),
                'lat': ('space', lat),
            }
        )

    '''侧向入流计算'''
    def Side_inflow(self, pos, side_Q):
        # 获取对应网格编号
        cell_num = self.Get_nearest_cell_num(pos)

        # 获取对应网格长度
        cell_length = self.cell_lengths[cell_num]

        # 计算并加入侧向流量
        self.QIN[cell_num] += side_Q / cell_length

    '''隐式演进'''
    def Evolve_impli(self, DT, fine=False):
        time = datetime.datetime.now()
        total_sim_time = self.sim_end_time - self.sim_start_time
        total_sim_time = total_sim_time.total_seconds()
        self.DT = DT # 确定演进时间步长

        self.Implic_flag = True

        # 优化网格参数
        if fine:
            self.Fine_cell_property2()

        # 初始化网格参数
        self.Init_cell_proprity(fine)

        # 保存初始结果
        self.Save_Basic_data()

        # 模拟计算
        while self.current_sim_time < total_sim_time:
            '''----每一时间步----'''
            # 计算界面平均流速和波速
            self.Caculate_face_U_C()

            # 计算Roe格式特征值
            self.Caculate_Roe_matrix()

            # 计算源项
            self.Caculate_source_term_2()

            # 计算Roe格式通量
            self.Caculate_Roe_Flux_2()

            # 计算溢流坝影响
            self.Caculate_dam()

            # 计算隐式格式系数
            self.Caculate_impli_trans_coefficient()

            # 隐式组合通量
            self.Assemble_Flux_impli_trans()

            # 更新时间
            self.time_step_count = self.time_step_count + 1
            self.current_sim_time += self.DT
            yield (self.DT)

            # 保存单步模拟结果
            self.Save_result_per_time_step()

            # 更新边界条件
            # self.Update_boundry_condition(implic=True)

            # 更新网格参数C
            self.Update_cell_proprity2()
            '''----每一时间步----'''

        # 写出模拟结果
        self.Resample_and_Save_Output_result()

        if self.Plot_flag:
            print('等待绘制结果图......')
            self._plot_executor.shutdown(wait=True)
            print('----模拟结束，总耗时{}---'.format(datetime.datetime.now() - time))

    '''显式演进'''
    def Evolve(self, fine = False, yield_step = None):
        time = datetime.datetime.now()
        total_sim_time = self.sim_end_time - self.sim_start_time
        total_sim_time = total_sim_time.total_seconds()

        local_time_sum = 0

        # 优化网格参数
        if fine: self.Fine_cell_property2()

        if yield_step == None:
            yield_step = self.time_step
        else:
            self.Max_time_step = yield_step

        # 初始水面
        self.Init_water_serface()

        self.Implic_flag = False

        # 初始化网格参数
        self.Init_cell_proprity(fine)

        # 保存初始结果
        self.Save_Basic_data()

        # 模拟计算
        print('Start Evolve......')
        while self.current_sim_time < total_sim_time:
            # 计算每一时间步
            '''单一时间步'''
            # 计算界面平均流速和波速
            self.Caculate_face_U_C()

            # 计算Roe格式特征值
            self.Caculate_Roe_matrix()

            # 计算源项
            self.Caculate_source_term_2()

            # 计算Roe格式通量
            self.Caculate_Roe_Flux_2()

            # 计算溢流坝影响
            self.Caculate_dam()

            # 组合通量
            self.Assemble_Flux_2()

            # 保存单步模拟结果
            self.Save_result_per_time_step()

            local_time_sum += self.DT
            if local_time_sum > yield_step:
                yield (self.current_sim_time)
                local_time_sum = 0

            # 更新网格参数C
            self.Update_cell_proprity2()

            # 计算下一时间步长
            self.Caculate_CFL_time()

            # 时间步计数器
            self.time_step_count = self.time_step_count + 1

            # 更新边界条件
            # self.Update_boundry_condition()

        # 写出模拟结果
        self.Resample_and_Save_Output_result()

        if self.Plot_flag:
            print('等待绘制结果图......')
            self._plot_executor.shutdown(wait=True)
            print('----模拟结束，总耗时{}---'.format(datetime.datetime.now() - time))

    '''更新网格参数'''
    def Update_cell_proprity2(self):
        for i in range (0, self.cell_num + 2) :
            # 获取断面名称
            section_name = self.cell_sections[i]

            # 基于过水断面面积，更新水深
            self.water_depth[i] = self.cross_section_table.get_depth_by_area(section_name, self.S[i])

            # 基于过水断面面积，更新水位
            self.water_level[i] = self.cross_section_table.get_level_by_area(section_name, self.S[i])

            # 计算流速
            if self.S[i] < self.S_limit:
                self.U[i] = 0
            else:
                self.U[i] = self.Q[i] / self.S[i]

            # 基于过水断面面积，查找水面宽度
            water_surface_width = self.cross_section_table.get_width_by_area(section_name, self.S[i])

            # 计算波速
            if self.S[i] > self.S_limit :
                if water_surface_width < self.EPSILON:
                    water_surface_width = self.S[i] / self.water_depth[i]

                self.C[i] = np.sqrt(self.g * self.S[i] / water_surface_width)
                self.FR[i] = np.abs(self.U[i]) / self.C[i] # 计算福汝德数

            else:
                self.C[i] = self.EPSILON
                self.FR[i] = np.abs(self.U[i]) / self.C[i] # 计算福汝德数

            # 基于过水断面面积，查找湿周
            self.P[i] = self.cross_section_table.get_wetted_perimeter_by_area(section_name, self.S[i])

            # 基于过水断面面积，查找水压力
            self.PRESS[i] = self.cross_section_table.get_press_by_area(section_name, self.S[i])

            # 基于过水断面面积查找水力半径
            self.R[i] = self.cross_section_table.get_hydraulic_radius_by_area(section_name, self.S[i])

            # 重置侧向入流
            self.QIN[i] = 0

    '''更新边界条件'''
    def Update_boundry_condition(self, implic=False):
        if not implic:
            self.U[0] = self.U[1] = 0
            self.S[0] = self.S[1] = self.S[2]

            self.U[-1] = - self.U[-2]
            self.S[-1] = self.S[-2]

        else:
            self.U[0] = self.U[1]
            self.S[0] = self.S[1]

            self.U[-1] = - self.U[-2]
            self.S[-1] = self.S[-2]

    '''流量输入边界'''
    def InBound_In_Q(self, Q):
        self.Q[0] = Q
        self.S[0] = self.S[0] + self.DT * (self.Q[0] - self.Q[1]) / self.cell_lengths[0]

        self.water_depth[0] = self.cross_section_table.get_depth_by_area(self.cell_sections[0], self.S[0])
        self.C[0] = np.sqrt(self.g * self.water_depth[0])
        self.FR[0] = np.abs(self.Q[0]) / self.C[0] / self.S[0]

        if self.FR[0] > 0.99:
            depth = self.cross_section_table.get_depth_by_area(self.cell_sections[0], self.S[0])
            c = np.sqrt(self.g * depth)
            Q = np.minimum(Q, c * self.S[0])
        self.Q[0] = Q

        # 隐式边界
        if self.Implic_flag:
            self.V0[0] = self.S[0]- self.S_old[0]
            self.V0[1] = self.Q[0] - self.Q_old[0]

    def InBound_In_Q2(self, Q_in):
        """
        上游给定流量 Q_in，利用负特征不变量恢复面积 S[0]。
        """
        # 1) 中间态 u1,h1
        S1 = self.S[1]
        Q1 = self.Q[1]
        h1 = self.cross_section_table.get_depth_by_area(self.cell_sections[1], S1)
        u1 = Q1 / S1

        # 2) 负特征不变量 f_minus
        c1 = np.sqrt(self.g * h1)
        f_minus = u1 - 2 * c1

        # 3) 强制流量
        Qb = Q_in

        # 4) 迭代求解边界水深 hb，使得 (Qb/Sb) - 2*sqrt(g*hb) = f_minus
        #    初始猜 Sb = S1
        Sb = S1
        for _ in range(5):
            hb = self.cross_section_table.get_depth_by_area(self.cell_sections[0], Sb)
            cb = np.sqrt(self.g * hb)
            ub = Qb / Sb
            # F(Sb) = ub - 2*cb - f_minus = 0
            F = ub - 2 * cb - f_minus
            # dF/dSb ≈ -Qb/Sb^2 - 2*(g/(2*cb))*(dh/dSb)
            # 近似用 dh/dSb = 1/(dA/dh)   —— 具体可用表格微分
            dAdh = self.cross_section_table.get_dA_dh(self.cell_sections[0], hb)
            dcb_dSb = (self.g / (2 * cb)) * (1 / dAdh)
            dF_dSb = -Qb / Sb ** 2 - 2 * dcb_dSb
            Sb = Sb - F / dF_dSb
            Sb = max(Sb, self.S_limit)

        # 5) 更新边界状态
        self.S[0] = Sb
        self.Q[0] = Qb

        # 如果用隐式格式，还要更新源项增量 V1
        if self.Implic_flag:
            self.V1[0] = self.S[0] - self.S_old[0]
            self.V1[1] = self.Q[0] - self.Q_old[0]

    def InBound_In_Q_re(self, Q):
        self.S[-1] = self.S[-1] + self.DT * (self.Q[-1] - self.Q[-2]) / self.cell_lengths[-1]

        if self.FR[-1] > 0.99:
            depth = self.cross_section_table.get_depth_by_area(self.cell_sections[-1], self.S[-1])
            c = np.sqrt(self.g * depth)
            Q = np.minimum(Q, c * self.S[-1])
        self.Q[-1] = Q

    '''自由出流边界'''
    def OutBound_Free_Outfall(self):
        self.Q[-1] = self.Q[-2]
        self.S[-1] = self.S[-2]

    def OutBound_Free_Outfall_re(self):
        self.Q[0] = self.Q[1]
        self.S[0] = self.S[1]

    '''固定水位出流边界'''
    def OutBound_Fix_level(self, level):
        section_name = self.cell_sections[-1]

        # 最后一个计算网格参数
        hi = self.cross_section_table.get_depth_by_area(section_name, self.S[-2])
        ui = self.Q[-2] / self.S[-2]

        # 边界条件
        hb = level - self.river_bed_height[-1]
        Ab = self.cross_section_table.get_area_by_level(section_name, level)

        # 计算域内特征不变量f+
        ci = np.sqrt(self.g * hi)
        f_plus = ui + 2 * ci

        # 下游参数
        cb = np.sqrt(self.g * hb)
        ub = f_plus - 2 * cb

        Q = Ab * ub

        self.S[-1] = Ab
        self.Q[-1] = Q

        if self.Implic_flag:
            self.V1[0] = self.S[-1] - self.S_old[-1]
            self.V1[1] = self.Q[-1] - self.Q_old[-1]

    '''固定水位的入流边界'''
    def InBound_Fix_level(self, level):
        section_name = self.cell_sections[0]
        # 用中间态面积 S[1] 反推水深 hi 和流速 ui
        hi = self.cross_section_table.get_depth_by_area(section_name, self.S[1])
        ui = self.Q[1] / self.S[1]

        # 2) 给定水面标高 level，计算对应的水深和截面面积
        hb = level - self.river_bed_height[0]
        Ab = self.cross_section_table.get_area_by_level(section_name, level)

        # 3) 计算内部特征不变量 f⁻ = u - 2√(g h)
        ci = np.sqrt(self.g * hi)
        f_minus = ui - 2 * ci

        # 4) 下（上）游状态的 celerity
        cb = np.sqrt(self.g * hb)

        # 利用 f⁻ 恢复边界处的 u_b = f⁻ + 2 c_b
        ub = f_minus + 2 * cb

        # 5) 计算边界流量
        Qb = Ab * ub

        # 6) 设置边界值
        self.S[0] = Ab
        self.Q[0] = Qb

        # 7) 如果是隐式格式，更新 V1 用于源项增量
        if self.Implic_flag:
            self.V0[0] = self.S[0] - self.S_old[0]
            self.V0[1] = self.Q[0] - self.Q_old[0]

    '''进行坐标插值和断面插值至每一个计算单元'''
    def interpolate_uniformly(self):
        # 计算累积距离
        distances = np.sqrt (np.sum (np.diff (self.pos, axis=0) ** 2, axis=1))  # 每段欧几里得距离
        cumulative_distances = np.insert (np.cumsum (distances), 0, 0)  # 原始点的累积距离

        # 生成计算单元中心点
        target_distances = np.linspace (cumulative_distances[0], cumulative_distances[-1], self.cell_num + 1)
        cell_centers = (target_distances[:-1] + target_distances[1 :]) / 2  # 取 10 个网格的中心位置

        # 计算插值后的网格坐标
        x_interp = np.interp (cell_centers, cumulative_distances, self.pos[:, 0])
        y_interp = np.interp (cell_centers, cumulative_distances, self.pos[:, 1])
        z_interp = np.interp (cell_centers, cumulative_distances, self.pos[:, 2])
        interpolated_pos = np.vstack ((x_interp, y_interp, z_interp)).T

        # 计算 `section_name` 的划分点（均匀分布）
        section_distances = np.linspace (cumulative_distances[0], cumulative_distances[-1], len (self.section_name))

        # **最近邻匹配法** 为每个网格中心点分配 `section_name`
        cell_sections = []
        for center in cell_centers :
            closest_section_idx = np.argmin (np.abs (section_distances - center))  # 找到最近的 section
            cell_sections.append (self.section_name[closest_section_idx])

        # 计算每个网格的长度
        cell_lengths = np.diff(target_distances)

        return interpolated_pos, cell_sections, cell_lengths

    '''基于水深求解过水断面面积'''
    def Calculate_cross_section_area_by_water_depth(self, points, water_depth) :
        import numpy as np
        points = np.array(points)
        intersections = []

        # 计算断面最低点
        min_x = np.min(points[:, 0])
        max_x = np.max(points[:, 0])
        # 根据水深确定水面高度
        width = max_x - min_x
        total_area = water_depth * width

        return total_area

    # '''绘制结果图'''
    # @staticmethod
    # def _plot_worker(data, count, name):
    #     import os
    #     try:
    #         os.makedirs(data['output_folder_path'], exist_ok=True)
    #
    #         cell_pos = data['cell_pos']
    #         water_depth = data['water_depth']
    #         river_bed = data['river_bed_height']
    #         water_level = data['water_level']
    #         U = data['U']
    #         C = data['C']
    #         Q = data['Q']
    #         S = data['S']
    #         Fr = data['Fr']
    #         current_time = data['current_sim_time']
    #         output_folder = data['output_folder_path']
    #         slop = data['slop']
    #         flux_loc0 = []
    #         flux_loc1 = []
    #
    #         for i in range(len(data['flux_loc'])):
    #             flux_loc0.append (data['flux_loc'][i,0])
    #             flux_loc1.append(data['flux_loc'][i,0])
    #
    #         fig, axs = plt.subplots(5, 2, figsize=(18, 12))
    #
    #         # 1. 水位/水深/河床
    #         ax1 = axs[0, 0]
    #         ax1.grid(True)
    #         # line1, = ax1.plot(cell_pos[:, 0], water_depth, label='water_depth (ax_L)', color='green')
    #         line1, = ax1.plot( water_depth, label='water_depth (ax_L)', color='green')
    #         ax2 = ax1.twinx()
    #
    #         # line2, = ax2.plot(cell_pos[:, 0], river_bed, label='river_bed (ax_R)', color='black')
    #         # line3, = ax2.plot(cell_pos[:, 0], water_level, label='water_level (ax_R)', color='blue')
    #         line2, = ax2.plot(river_bed, label='river_bed (ax_R)', color='black')
    #         line3, = ax2.plot(water_level, label='water_level (ax_R)', color='blue')
    #
    #         ax1.legend([line1, line2, line3],
    #                    [ln.get_label() for ln in (line1, line2, line3)])
    #         ax1.set_title('Water level & depth')
    #
    #         # 2. 流速/波速
    #         ax_ws = axs[1, 0]
    #         # lin1, = ax_ws.plot(cell_pos[:, 0], U, label='U (ax_L)', color = 'blue')
    #         lin1, = ax_ws.plot(U, label='U (ax_L)', color = 'blue')
    #         ax_ws2 = ax_ws.twinx()
    #         # lin2, = ax_ws2.plot(cell_pos[:, 0], C, label='C (ax_R)', color = 'orange')
    #         lin2, = ax_ws2.plot(C, label='C (ax_R)', color = 'orange')
    #         ax_ws.legend([lin1, lin2],
    #                    [ln.get_label() for ln in (lin1, lin2)])
    #         ax_ws.grid(True)
    #         ax_ws.set_title('water speed & wave speed')
    #
    #         # 3. 流量 Q
    #         ax_q = axs[0, 1]
    #         # ax_q.plot(cell_pos[:, 0], Q, label='Q')
    #         ax_q.plot(Q, label='Q')
    #         ax_q.legend()
    #         ax_q.grid(True)
    #         ax_q.set_title('water discharge')
    #         # ax_fr = ax_q.twinx()
    #         # ax_fr.plot(cell_pos[:, 0], Fr, label='Fr', color='orange')
    #
    #         # 4. 过水断面面积 S
    #         ax_s = axs[1, 1]
    #         # ax_s.plot(cell_pos[:, 0], S, label='Wetted area',m='o-')
    #         ax_s.plot(S, 'o-' ,label='Wetted area')
    #
    #         ax_s.legend()
    #         ax_s.grid(True)
    #         ax_s.set_title('wetted area')
    #
    #         # 5. 断面信息表
    #         ax_se = axs[2, 0]
    #
    #         # # 假设 data['section_name'] 是长度和 cell_pos[:,0] 一致的 list 或 array
    #         # names = data['section_name']
    #         #
    #         # # 直接把名字当 y 值传进去
    #         # ax_se.scatter(cell_pos[:, 0], names, s=5)
    #         # ax_se.grid(True)
    #         #
    #         # # 可选：调整格式
    #         # ax_se.set_xlabel('cell_pos x')
    #         # ax_se.set_ylabel('section name')
    #         # ax_se.set_title('section_name')
    #
    #         # ax_se.plot(cell_pos[:, 0], Fr)
    #         ax_se.plot(Fr)
    #         ax_se.set_xlabel('cell_pos x')
    #         ax_se.set_title('Fr')
    #
    #         # 6. press
    #         ax_p = axs[2, 1]
    #         # ax_p.plot(cell_pos[:, 0], data['press'], label='press')
    #         ax_p.plot(data['press'], label='press')
    #         ax_p.legend()
    #         ax_p.grid(True)
    #         ax_p.set_title('pressure')
    #
    #         ax_loc = axs[3, 0]
    #         # ax_loc.plot(cell_pos[0:-1, 0], flux_loc0, label='flux_loc[0]')
    #         # ax_loc.plot(cell_pos[0:-1, 0], flux_loc1, label='flux_loc[1]')
    #         ax_loc.plot(flux_loc0, label='flux_loc[0]')
    #         ax_loc.plot(flux_loc1, label='flux_loc[1]')
    #         ax_loc.grid(True)
    #         ax_loc.set_title('flux_loc')
    #         ax_loc.legend()
    #
    #         ax_n = axs[3, 1]
    #         # ax_n.plot(cell_pos[:, 0], data['friction'], label='friction')
    #         ax_n.plot(data['friction'], label='friction')
    #
    #         ax_n.grid(True)
    #         ax_n.set_title('fricion')
    #         ax_n.legend()
    #
    #         ax_source = axs[4,0]
    #         # ax_source.plot(cell_pos[:, 0], data['flux_source_right'], label='flux_source_right')
    #         # ax_source.plot(cell_pos[:, 0], data['flux_source_left'], label='flux_source_left')
    #         # ax_source.plot(cell_pos[:-1, 0], data['flux_source_center'], label='flux_source_center')
    #         ax_source.plot(data['flux_source_right'], label='flux_source_right')
    #         ax_source.plot(data['flux_source_left'], label='flux_source_left')
    #         ax_source.plot(data['flux_source_center'], label='flux_source_center')
    #
    #         ax_source.grid(True)
    #         ax_source.set_title('flux_source')
    #         ax_source.legend()
    #
    #         ax_friction = axs[4,1]
    #         # ax_friction.plot(cell_pos[:, 0], data['flux_friction_right'], label='flux_friction_right')
    #         # ax_friction.plot(cell_pos[:, 0], data['flux_friction_left'], label='flux_friction_left')
    #         ax_friction.plot(data['flux_friction_right'], label='flux_friction_right')
    #         ax_friction.plot(data['flux_friction_left'], label='flux_friction_left')
    #
    #         ax_friction.grid(True)
    #         ax_friction.set_title('flux_friction')
    #         ax_friction.legend()
    #
    #         fig.suptitle(f'sim data (time: {current_time} S)')
    #         plt.tight_layout()
    #         save_path = os.path.join(output_folder, f'{name}_pic_{count:06d}.png')
    #         plt.savefig(save_path, dpi=100)  # 可调整 dpi
    #         plt.close(fig)
    #
    #
    #     except Exception as e:
    #         # 如果出错，写日志
    #         with open(os.path.join(data['output_folder_path'], 'plot_error.log'), 'a') as f:
    #             f.write(f"[{count}] {type(e).__name__}: {e}\n")
    #
    # '''绘制结果图'''
    # def Plot_result(self):
    #     count = self.time_step_count
    #     self.Plot_flag = True
    #     # 打包并拷贝必要数据
    #     data = {
    #         'cell_pos':           self.cell_pos.copy(),
    #         'water_depth':        self.water_depth.copy(),
    #         'river_bed_height':   self.river_bed_height.copy(),
    #         'water_level':        self.water_level.copy(),
    #         'U':                   self.U.copy(),
    #         'C':                   self.C.copy(),
    #         'Q':                   self.Q.copy(),
    #         'S':                   self.S.copy(),
    #         'current_sim_time':   self.current_sim_time,
    #         'output_folder_path': self.output_folder_path,
    #         'section_name': self.cell_sections,
    #         'press' : self.PRESS,
    #         'Fr':self.FR,
    #         'slop' : self.Slop,
    #         'flux_loc': self.Flux_LOC,
    #         'friction': self.friction_source,
    #         'flux_source_right': self.Flux_Source_right,
    #         'flux_source_left': self.Flux_Source_left,
    #         'flux_source_center': self.Flux_Source_center,
    #         'flux_friction_right': self.Flux_Friction_right,
    #         'flux_friction_left': self.Flux_Friction_left,
    #     }
    #
    #     # 并发提交给池，最多同时运行 max_workers 个绘图进程
    #     future = self._plot_executor.submit(River._plot_worker, data, count, self.model_name)
    #     future.add_done_callback(
    #         lambda fut: fut.exception() and print(f"Plot #{count} failed:", fut.exception())
    #     )

    def Current_sim_progress(self):
        total_time = self.sim_end_time - self.sim_start_time
        total_time = total_time.total_seconds()
        return self.current_sim_time / total_time

    '''创建断面表'''
    def Create_cross_section_table(self, manning, num=100):

        # 遍历每一个断面
        for section_name in self.sections_data:
            # 获取断面点坐标
            section_point = self.sections_data[section_name]

            area_list = []  # 过水断面面积
            level_list = []  # 水位
            depth_list = []  # 水深
            width_list = []  # 水面宽度
            wetted_perimeter_list = []  # 湿周
            hydraulic_radius_list = []  # 水力半径
            press_list = []  # 压力列表
            DEB = [] # 参数列表

            xs = [pt[0] for pt in section_point]  # 坐标点x
            ys = [pt[1] for pt in section_point]  # 坐标点y

            # 补充高程，图形封闭
            first_x, first_y = section_point[0]
            last_x, last_y = section_point[-1]

            max_y = np.max(ys) # 获取断面最高点

            # 创造两侧封闭最高点
            left_top = [first_x, max_y + 5]
            right_top = [last_x, max_y + 5]

            section_point = [left_top] + section_point + [right_top]

            max_depth = np.max(ys) - np.min(ys) + 100  # 获取断面最大水深
            min_y = np.min(ys)  # 断面最低点
            depth_slice = np.linspace(self.EPSILON, max_depth, num=num)  # 均匀划分水层

            # 基于水层计算不同层的过水面积
            for depth in depth_slice:
                depth_list.append(depth)  # 记录水深
                level = depth + min_y  # 计算水位
                level_list.append(level)  # 记录对应水位

                # 计算过水断面面积
                poly = Polygon(section_point)  # 河道断面形状
                section_line = LineString(section_point)  # 河道断面形状线

                minx, miny, maxx, maxy = poly.bounds  # 河道断面外边界点
                clip = box(minx - 10, miny - 10, maxx + 10, level)  # 水位区域盒子
                water_level = LineString([(minx - 10, level), (maxx + 10, level)])  # 水位线

                poly = poly.buffer(0)  # 自相交修复

                wetted_area = poly.intersection(clip)  # 计算过水断面面积
                width = poly.intersection(water_level)  # 计算水面宽度
                under_water_length = section_line.intersection(clip)  # 计算湿周

                area_list.append(wetted_area.area)  # 记录对应过水面积
                width_list.append(width.length)  # 记录对应的水面宽度
                wetted_perimeter_list.append(under_water_length.length)  # 记录对应的湿周
                hydraulic_radius_list.append(area_list[-1] / wetted_perimeter_list[-1])  # 记录对应的水力半径

                # 计算DEB
                s = float(wetted_area.area)
                r = float(area_list[-1] / wetted_perimeter_list[-1])
                deb = (1 / manning) * s * r ** (0.66666666666667)
                DEB.append(float(deb))


            # 计算压力列表
            press_list.append(self.EPSILON)
            dz = np.diff(depth_list)
            '''planma.f90'''
            for i in range(1, len(depth_slice)):
                press = press_list[i - 1] + self.g * (area_list[i - 1] + area_list[i]) * dz[i - 1] / 2
                press_list.append(press)

            # 记录计算结果
            self.cross_section_table.add_table(
                name=section_name,
                depths=depth_list,
                level=level_list,
                areas=area_list,
                width=width_list,
                wetted_perimeter=wetted_perimeter_list,
                hydraulic_radius=hydraulic_radius_list,
                press=press_list,
                DEB=DEB
            )

    '''debug mode'''
    def Debug(self):
        import pandas as pd
        import numpy as np
        import os
        output_folder_path = os.path.join(self.output_folder_path, 'debug')
        os.makedirs(output_folder_path, exist_ok=True)

        def append_time_step_data(file_path, attr_name, new_data, time_id):
            """
            将单个属性的新数据追加到 CSV 文件中，新数据可能为一维或二维数组，
            新列名中包含时间步标识。

            参数:
              file_path: str，目标 CSV 文件路径。
              attr_name: str，属性名称（例如 "water_level"）。
              new_data: numpy 数组，数据可以为一维或二维数组。
              time_id: str，时间步标识（例如 "ts1"）。

            对于一维数据，新列名格式为： attr_name_timeid  例如 "water_level_ts1"
            对于二维数据，新数据中每一列分别保存为单独的列，列名格式为： attr_name_timeid_i
            例如："cell_press_source_ts1_1", "cell_press_source_ts1_2"
            """
            # 判断 CSV 文件是否存在
            if os.path.exists(file_path):
                df = pd.read_csv(file_path)
            else:
                df = pd.DataFrame()

            # 根据数据的维度构造要追加的 DataFrame
            if new_data.ndim == 1:
                col_name = f"{attr_name}_{time_id}"
                new_df = pd.DataFrame({col_name: new_data})
            elif new_data.ndim == 2:
                n_cols = new_data.shape[1]
                new_dict = {}
                for i in range(n_cols):
                    # 对于二维数据，每一列生成一个单独的新列（从 1 开始计数）
                    col_name = f"{attr_name}_{time_id}_{i + 1}"
                    new_dict[col_name] = new_data[:, i]
                new_df = pd.DataFrame(new_dict)
            else:
                raise ValueError("new_data 必须为一维或二维数组")

            # 如果原文件已有数据，则要求新数据的行数与原数据一致，然后横向拼接（即按列追加）
            if not df.empty:
                if len(df) != len(new_df):
                    raise ValueError(f"原 CSV 文件的行数 ({len(df)}) 与新数据的行数 ({len(new_df)}) 不一致")
                df = pd.concat([df, new_df], axis=1)
            else:
                df = new_df

            # 保存 DataFrame 到 CSV 文件中（不保存行索引）
            df.to_csv(file_path, index=False)
            print(f"属性 '{attr_name}' (时间步 {time_id}) 数据已保存到 {file_path}")

        time_id = self.current_sim_time

        # 将所有要保存的属性整理到字典中（键为属性名称，值为对应的数组）
        attributes = {
            "water_level": self.water_level,  # 水位，一般是一维数组
            "water_depth": self.water_depth,  # 水深
            "Q": self.Q,  # 流量
            "S": self.S,  # 过水断面面积
            # "Cell_left_Q": self.Cell_left_Q,  # 格左侧流量
            # "Cell_right_Q": self.Cell_right_Q,  # 格右侧流量
            # "Cell_left_S": self.Cell_left_S,  # 格左侧过水面积
            # "Cell_right_S": self.Cell_right_S,  # 格右侧过水面积
            "U": self.U,  # 流速
            "FR": self.FR,  # 福汝德数
            "C": self.C,  # 波速
            "PRESS": self.PRESS,  # 垂向压力
            # "BETA": self.BETA,  # 修正系数
            "P": self.P,  # 湿周
            "R": self.R,  # 水力半径
            "cell_press_source": self.cell_press_source,  # 界面中心压力源项目（二维数组）
            "QIN": self.QIN,  # 外部入流
            # "DEB": self.DEB,  # 过水断面面积对水位导数
            "DTI": self.DTI,  # 每个网格的时间步长
            "n": self.n,  # 曼宁摩擦系数
            "F_U": self.F_U,  # 界面平均流速
            "F_C": self.F_C,  # 界面平均波速
            "F_Q_SOURCE": self.F_Q_SOURCE,  # 界面流量源项（二维数组）
            "F_Friction_SOURCE": self.F_Friction_SOURCE,  # 界面摩擦源项
            "F_Singular_Head_Loss": self.F_Singular_Head_Loss,  # 局部水头损失系数
            "Lambda1": self.Lambda1,  # 第一特征值
            "Lambda2": self.Lambda2,  # 第二特征值
            "abs_Lambda1": self.abs_Lambda1,  # 第一特征值的绝对值
            "abs_Lambda2": self.abs_Lambda2,  # 第二特征值的绝对值
            "alpha1": self.alpha1,  # 波幅系数
            "alpha2": self.alpha2,  # 波幅系数
            "dissipation1": self.dissipation1,  # 粘性系数
            "dissipation2": self.dissipation2,  # 粘性系数
            "Vactor1": self.Vactor1,  # 第一特征向量（二维数组）
            "Vactor2": self.Vactor2,  # 第二特征向量
            "Vactor1_T": self.Vactor1_T,  # 特征矩阵的逆第一列
            "Vactor2_T": self.Vactor2_T,  # 特征矩阵的逆第二列
            "Flux_LOC": self.Flux_LOC,  # 界面中心通量（二维数组）
            "Flux_Source_left": self.Flux_Source_left,  # 网格左侧界面源项（二维数组）
            "Flux_Source_right": self.Flux_Source_right,  # 网格右侧界面源项
            "Flux_Source_center": self.Flux_Source_center,  # 中心源项
            "Flux_Friction_left": self.Flux_Friction_left,  # 网格左侧界面摩擦通量
            "Flux_Friction_right": self.Flux_Friction_right,  # 网格右侧界面摩擦通量
            "bottom_source": self.bottom_source,  # 网格底坡源项（二维数组）
            "friction_source": self.friction_source,  # 网格摩擦源项（二维数组）
            "Flux": self.Flux,  # 通量数组（二维数组）
            "Debit_Flux": self.Debit_Flux,  # 流量通量（二维数组）
            "flag_LeVeque": self.flag_LeVeque  # LeVeque 修正标识（一维数组）
        }

        # 遍历属性字典，对每个属性调用 append_time_step_data
        for name, data in attributes.items():
            file_path = os.path.join( output_folder_path, f"{self.file_name}_{name}.csv")
            try:
                append_time_step_data(file_path, name, data, time_id)
            except Exception as e:
                print(f"保存属性 '{name}' 时出错: {e}")

    '''基于结果的数据查找'''
    def from_result_get_variable_at_time(self, nc_path, var_name, time_point, method='nearest'):
        """
        从 NetCDF 文件中读取指定变量在给定时间点的空间场值。

        参数
        ----
        nc_path : str
            NetCDF 文件路径。
        var_name : str
            变量名，如 'h', 'eta', 'u', 'Q'。
        time_point : str or datetime-like
            时间点，例如 "2025-04-29T00:30:00"。
        method : str or None
            插值方法；'nearest' 表示最近邻插值，None 表示精确匹配。

        返回
        ----
        xarray.DataArray
            维度为 ('space',)，包含 coords['space', 'x', 'y']。
        """
        ds = xr.open_dataset(nc_path)
        if var_name not in ds.data_vars:
            raise ValueError(f"变量 {var_name} 不存在，数据集变量有：{list(ds.data_vars)}")
        da = ds[var_name]
        if method:
            da_sel = da.sel(time=time_point, method=method)
        else:
            da_sel = da.sel(time=time_point)
        return da_sel

    '''查找坐标最近网格编号'''
    def Get_nearest_cell_num(self, pos):
        # 切片x,y坐标
        coords_xy = self.cell_pos[:,:2]

        # 格式化查询点
        new_xy = np.array(pos)

        # tree查询
        tree = cKDTree(coords_xy)
        dist, idx2 = tree.query(new_xy)
        # print("KDTree 最近点索引：", idx2, "距离：", dist)

        # 避免返回两侧边缘网格
        if idx2 == 0: idx2 = 1
        if idx2 == -1: idx2 = -2

        return idx2

    '''优化底坡'''
    def Fine_cell_property(self):
        print('优化网格参数......')

        '''首先获取计算单元坐标， 获得插值断面， 降低插值断面'''
        # 1.按照断面参数赋予河底高程参数
        for i in range(self.cell_num + 2):
            section_name = self.cell_sections[i]
            section_point = self.sections_data[section_name]
            ys = [pt[1] for pt in section_point]  # 坐标点y
            self.river_bed_height[i] = np.min(ys)  # 断面最低点

        # # 2.基于河底高程，拟合出一条直线
        z_pos = np.array([row[-1] for row in self.cell_pos])
        length = np.array(self.cell_lengths[0:-1])
        x = np.concatenate(([0], np.cumsum(length))) # 累计长度
        m, b = np.polyfit(x, z_pos, deg=1) # 拟合直线
        y_fit = m * x + b # 计算新河底高程

        for i in range(self.cell_num + 2):
            self.river_bed_height[i] = y_fit[i]

        # # 2. 基于河底高程，用三次样条替代线性拟合
        # z_pos = np.array([row[-1] for row in self.cell_pos])  # 原始河床高程
        # lengths = np.array(self.cell_lengths[:-1])  # 各单元长度
        # x = np.concatenate(([0], np.cumsum(lengths)))  # 累计距
        #
        # # 用三次样条过所有点 (s=0 表示严格插值)
        # spline = UnivariateSpline(x, z_pos, k=3, s=0)
        # y_fit = spline(x)  # 插值后的河床高程

        # 其余赋值不变
        # for i in range(self.cell_num + 2):
        #     self.river_bed_height[i] = y_fit[i]

        # 3.基于新的河底高程制作断面数据
        for i in range(self.cell_num + 2):
            pos = self.cell_pos[i][0:2]
            new_section_name = f"Interpolator_{i}"

            # 修改断面数据
            section_point = self.Interpolator.get_section_at_xy(pos)
            self.Interpolator.visualize(pos) # 绘图

            X = section_point['X'].copy()
            x_min = np.min(X)
            Z = section_point['Z'].copy()
            section_point = [[x - x_min, z] for x, z in zip(X, Z)]

            ys = [pt[1] for pt in section_point]  # 坐标点y
            y_min = np.min(ys) # 断面最低点
            diff = y_min - self.river_bed_height[i] # 断面点与河底高程之差
            new_section_point = [[x, y - diff] for x, y in section_point] # 计算新的断面数据

            self.sections_data[new_section_name] = new_section_point # 制作新断面
            self.cell_sections[i] = new_section_name # 赋予新断面

        self.Plot_fined_cell_property()

    def Fine_cell_property2(self):
        print('优化网格参数......')

        '''首先获取计算单元坐标， 获得插值断面， 降低插值断面'''
        # 1.按照断面参数赋予河底高程参数
        for i in range(self.cell_num + 2):
            section_name = self.cell_sections[i]
            section_point = self.sections_data[section_name]
            ys = [pt[1] for pt in section_point]  # 坐标点y
            self.river_bed_height[i] = np.min(ys)  # 断面最低点

        # # 2.基于河底高程，拟合出一条直线
        z_pos = np.array([row[-1] for row in self.cell_pos])
        length = np.array(self.cell_lengths[0:-1])
        x = np.concatenate(([0], np.cumsum(length))) # 累计长度
        m, b = np.polyfit(x, z_pos, deg=1) # 拟合直线
        y_fit = m * x + b # 计算新河底高程

        for i in range(self.cell_num + 2):
            self.river_bed_height[i] = y_fit[i]

        # 3.基于新的河底高程制作断面数据
        for i in range(self.cell_num + 2):
            pos = self.cell_pos[i][0:2]
            new_section_name = f"Interpolator_{i}"

            # 修改断面数据
            section_point = self.Interpolator.get_section_at_xy(pos)
            # self.Interpolator.visualize(pos) # 绘图

            # 将断面修正到最左侧
            X = section_point['X'].copy()
            x_min = np.min(X)
            Z = section_point['Z'].copy()
            section_point = [[x - x_min, z] for x, z in zip(X, Z)]

            ys = [pt[1] for pt in section_point]  # 坐标点y
            y_min = np.min(ys) # 断面最低点
            self.river_bed_height[i] = y_min
            new_section_point = [[x, y] for x, y in section_point] # 计算新的断面数据

            self.sections_data[new_section_name] = new_section_point # 制作新断面
            self.cell_sections[i] = new_section_name # 赋予新断面

            # 计算网格坡度
            if i == self.cell_num + 1:
                self.Slop[i] = (self.river_bed_height[i - 1] - self.river_bed_height[i]) / self.cell_lengths[i]
            else:
                self.Slop[i] = (self.river_bed_height[i] - self.river_bed_height[i + 1]) / self.cell_lengths[i]

            if self.Slop[i] == 0: self.Slop[i] = self.EPSILON

        # self.Plot_fined_cell_property()

    '''绘制优化后的河底高程'''
    def Plot_fined_cell_property(self):
        fig, axs = plt.subplots(2, 1, figsize=(40, 50))

        # 绘制河底高程
        ax_bottom = axs[0]
        ax_bottom.plot(self.cell_pos[:, 0], self.river_bed_height, '-o')
        ax_bottom.grid(True)

        # 绘制断面形状
        ax_shape = axs[1]
        for i in range(self.cell_num + 2):
            section_name = self.cell_sections[i]
            section_point = self.sections_data[section_name]

            xs = [pt[0] for pt in section_point]
            ys = [pt[1] for pt in section_point]
            ax_shape.plot(xs, ys, label=f"{i}")

        plt.legend()
        save_path = os.path.join(self.output_folder_path, f'{self.model_name}_fined_cell_property.png')
        plt.savefig(save_path, dpi=100)  # 可调整 dpi
        plt.close()

    '''初始化水面'''
    def Init_water_serface(self):
        # 基于水深初始化水位
        if self.Depth_init:
            print('基于水深初始化......')
            self.water_depth[:] = self.init_depth
            self.water_level = self.water_depth + self.river_bed_height

        # 基于水位初始化
        if self.Level_init:
            print('基于水位初始化......')
            self.water_level[:] = self.init_water_level
            self.water_depth = self.water_level - self.river_bed_height

    '''设置水深'''
    def Set_init_watr_depth(self, depth):
        self.Depth_init = True
        self.init_depth = depth

    '''设置水位'''
    def Set_init_water_level(self, level):
        self.Level_init = True
        self.init_water_level = level

    '''绘制断面表'''
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
                # press.append(self.cross_section_table.get_press_by_area(section_name, s))
                press.append(s)
            plt.plot(x, press, label=f"{index}")


        plt.legend()
        plt.grid(True)
        plt.title('depth - S')
        plt.show()

    def Call_fun_test(self):
        print('successfully call function test!')


if __name__ == '__main__' and False :
    import os
    import glob
    def delete_png_in_folder(folder_path):
        # 构造匹配所有 .png 文件的通配符路径
        pattern = os.path.join(folder_path, '*.png')
        # 使用 glob 获取文件列表
        png_files = glob.glob(pattern)

        for file_path in png_files:
            try:
                os.remove(file_path)
            except Exception as e:
                pass


    file_path = "/Users/xin/Library/CloudStorage/OneDrive-个人/研究生/大论文/telemac-mascaret-main/模型构建/model/output3/loc.csv"
    if os.path.exists(file_path):
        os.remove(file_path)

    # 示例使用
    folder = "output3"  # 修改为目标文件夹路径
    delete_png_in_folder(folder)

    river_data = {
        "cell_num" : 2400,  # 计算单元数量
        "pos" : [[1, 2, 0], [400, 2, 0], [800, 2, 0], [1200, 2, 0]],  # 河道点坐标 长度、宽度、高度
        "section_name" : ['se1', 'se2', 'se3']  # 断面名称
    }
    section_data = {
        'se1': [[0, 0], [0, -1], [3, -1], [3, 0]],
        'se2': [[0, 0], [0, -1], [3, -1], [3, 0]],
        'se3': [[0, 0], [0, -1], [3, -1], [3, 0]]
    }
    model_data = {
        'sim_start_time' : '2024-01-01 00:00:00',
        'sim_end_time' : '2024-01-02 00:00:00',
        'time_step': 60, # 单位：秒
        'output_path': 'output3',
        'CFL' : 0.5,
        'n' : 0.0
    }

    river = River(river_data, section_data, model_data)
    river.Case_Dam_Break(10)
    # river.Case_inflow()
    time = datetime.datetime.now()
    for t in river.Evolve():
        elapsed = datetime.datetime.now() - time
        elapsed = elapsed.total_seconds()
        print(f'总模拟时间为：{round(river.current_sim_time, 4)} , 当前时间步长为：{round(river.DT, 4)}, 计算耗时{elapsed}')
        river.Plot_result()




# ---- END river_for_net ----

import random
import time

# from river_for_net import River  # replaced by single-file merge
# from river_for_net_optimized import River
import networkx as nx
from pprint import pprint
import pandas as pd
import datetime
import numpy as np

class Rivernet():
    def __init__(self, Topology, model_data, verbos=True):
        # 构建参数
        self.verbos = verbos # 是否打印详细信息
        self.Fine_flag = False  # 网格参数是否已优化
        self.model_data = model_data # 模型数据
        self.caculation_time = 0 # 模拟总时间（单位：秒）
        self.caculation_start_time = 0 # 模拟开始时间（单位：秒）

        # 构建河网拓扑
        self.topology = Topology # 存储河网拓扑信息
        self.G = nx.DiGraph() # 创建有向图
        self.Create_Rivernet() # 创建河网

        # 边界条件组织
        # { node_name: {"type": btype, "call": f(t), "_val":[v](仅常数有)} }
        self.boundaries = {} # 边界条件字典
        self.ALLOWED_OUT_BTYPE = {'free', 'fix_level'} # 允许的出边界类型
        self.ALLOWED_IN_BTYPE = {'flow', 'fix_level'} # 允许的入边界类型

        # 模拟时间参数
        self.sim_start_time = datetime.datetime.strptime(model_data['sim_start_time'], '%Y-%m-%d %H:%M:%S')
        self.sim_end_time = datetime.datetime.strptime(model_data['sim_end_time'], '%Y-%m-%d %H:%M:%S')
        self.total_sim_time = (self.sim_end_time - self.sim_start_time).total_seconds()  # 模拟总时间（单位：秒）
        self.step_count = 0 # 模拟步数

        # 子步参数
        self.sub_step_count = 0 # 子步数
        self.sub_step_time = 0.0 # 子步时间
        self.sub_step_max_dt = 0.0 # 子步最大时间步长
        self.sub_step_min_dt = 999999 # 子步最小时间步长
        self.sub_step_start_time = 0 # 子步开始时间
        self.sub_step_caculation_time_using= 0 # 子步计算时间（单位：秒）

        # 河网所需参数
        self.current_sim_time = 0.0 # 模拟进行时间
        self.cfl_allowed_dt = 1e-5 # cfl允许的时间步长
        self.DT = 1e-5 # 时间步长

        # 汊点迭代算法相关参数
        self.alpha = 1.2 # 计算调节参数，1-2之间
        self.max_iteration = 20 # 汊点计算最大迭代次数
        self.g = 9.81 # 重力加速度
        self.JPWSPC_EPS = 1e-3 # JPWSPC算法容差
        self.JPWSPC_Q_limit = 1e-3 # JPWSPC算法流量限制

    # 创建河网
    def Create_Rivernet(self):
        for (u, v), info in self.topology.items():

            # 基于数据，组织河道class所需model_data
            name = info['name']
            manning = info['manning']

            model_data = {
                'model_name': name,
                'sim_start_time': self.model_data['sim_start_time'],
                'sim_end_time': self.model_data['sim_end_time'],
                'time_step': self.model_data['time_step'],  # 单位：秒
                'output_path': self.model_data['output_path'],
                'CFL': self.model_data['CFL'],
                'n': manning
            }

            # 创建河道对象
            river = River(info['river_data'], info['section_data'], info['section_pos'], model_data)
            self.G.add_edge(u, v, river=river, name=info['name'])
            print(f'河道{name}创建完成')

    # 判断流向
    def edge_direction(self):
        if not self.G.is_directed():
            raise ValueError('无向图没有天然方向，请先转换为有向图或添加方向属性')
        results = []
        for u, v in self.G.edges():
            results.append({
                'edge': (u, v),
                'from_node': u,
                'to_node': v
            })
        if self.verbos:
            pprint(results)

    # 判断内外部点
    def classfy_nodes(self):
        """
        将节点分成三类：
          - internal:   degree >= 2
          - external_in:  in_degree == 1 且 out_degree == 0
          - external_out: out_degree == 1 且 in_degree == 0
        另外会记录孤立点（degree == 0），以便排查拓扑问题。
        """
        self.internal_nodes = []
        self.external_in_nodes = []
        self.external_out_nodes = []
        self.isolated_nodes = []

        for n in self.G.nodes():
            indeg = self.G.in_degree(n)
            outdeg = self.G.out_degree(n)
            deg = indeg + outdeg

            if deg == 0:
                self.isolated_nodes.append(n)
            elif deg == 1:
                if indeg == 1 and outdeg == 0:
                    self.external_out_nodes.append(n)
                elif outdeg == 1 and indeg == 0:
                    self.external_in_nodes.append(n)
                else:
                    # 理论上不会出现（DiGraph 无并行边时 deg==1 只能是上面两种）
                    pass
            else:
                # deg >= 2
                self.internal_nodes.append(n)

        # 兼容旧属性：external_nodes = external_in ∪ external_out
        self.external_nodes = self.external_in_nodes + self.external_out_nodes

        if self.verbos:
            print('内部节点 (internal):', self.internal_nodes)
            print('外部入点 (external_in):', self.external_in_nodes)
            print('外部出点 (external_out):', self.external_out_nodes)
            if self.isolated_nodes:
                print('孤立节点 (degree=0):', self.isolated_nodes)

    # 分别遍历内部和外部节点
    def node_flow_direction(self):
        if not self.G.is_directed():
            raise ValueError('无向图没有天然方向，请先转换为有向图或添加方向属性')

        # 确保已经按三类完成分类
        need_attrs = ('internal_nodes', 'external_in_nodes', 'external_out_nodes')
        if not all(hasattr(self, a) for a in need_attrs):
            self.classfy_nodes()

        result = {'internal': {}, 'external_in': {}, 'external_out': {}}

        # —— 内部节点：既有入又有出
        for n in self.internal_nodes:
            ins = list(self.G.in_edges(n, data=True))  # [(u, n, data), ...]
            outs = list(self.G.out_edges(n, data=True))  # [(n, v, data), ...]
            result['internal'][n] = {'in': ins, 'out': outs}

        # —— 外部入点：只有入边（按你的定义应当 out_edges 为空）
        for n in self.external_in_nodes:
            ins = list(self.G.in_edges(n, data=True))
            outs = list(self.G.out_edges(n, data=True))
            result['external_in'][n] = {'in': ins, 'out': outs}

        # —— 外部出点：只有出边（按你的定义应当 in_edges 为空）
        for n in self.external_out_nodes:
            ins = list(self.G.in_edges(n, data=True))
            outs = list(self.G.out_edges(n, data=True))
            result['external_out'][n] = {'in': ins, 'out': outs}

        if self.verbos:
            print('\n—— 内部节点 (internal) ——')
            for n, d in result['internal'].items():
                print(f'节点 {n}:')
                for u, v, data in d['in']:
                    print(f'  in  : {data.get("name", f"({u},{v})")}  ({u} -> {v})')
                for u, v, data in d['out']:
                    print(f'  out : {data.get("name", f"({u},{v})")}  ({u} -> {v})')

            print('\n—— 外部入点 (external_in) ——')
            for n, d in result['external_in'].items():
                print(f'节点 {n}:')
                for u, v, data in d['in']:
                    print(f'  in  : {data.get("name", f"({u},{v})")}  ({u} -> {v})')
                if d['out']:
                    for u, v, data in d['out']:
                        print(f'  out : {data.get("name", f"({u},{v})")}  ({u} -> {v})')

            print('\n—— 外部出点 (external_out) ——')
            for n, d in result['external_out'].items():
                print(f'节点 {n}:')
                if d['in']:
                    for u, v, data in d['in']:
                        print(f'  in  : {data.get("name", f"({u},{v})")}  ({u} -> {v})')
                for u, v, data in d['out']:
                    print(f'  out : {data.get("name", f"({u},{v})")}  ({u} -> {v})')

            # print('\n—— 结构化结果 ——')
            # pprint(result)

        return result

    # 调用每条河道函数
    def call_river_function(self):
        for u, v, data in self.G.edges(data=True):
            river = data['river']
            river.Call_fun_test()  # 假设每条河道都有 Call_fun_test 函数

    # 调用河道指定函数
    def call_river_function_by_name(self, function_name):
        for u, v, data in self.G.edges(data=True):
            river = data['river']
            if river is None:
                print(f'河道 {data["name"]} 没有定义河流对象，无法调用')
                continue
            if hasattr(river, function_name):
                func = getattr(river, function_name)
                if callable(func):
                    func()
                    if self.verbos:
                        print(f'河道 {data["name"]} 的 {function_name} 函数调用成功')
                else:
                    print(f'河道 {data["name"]} 的 {function_name} 不是一个可调用的函数')
            else:
                print(f'河道 {data["name"]} 没有名为 {function_name} 的函数')

    # 设置边界条件
    def set_boundary(self, node: str, btype: str, data=None):
        """
        设定边界
        - node: 节点名，如 "N1"
        - btype: 边界类型，如 "free" / "stage" / "flow" / "rating" / "wall" ...
        - data:  None（自由/自然边界等不需要输入）
                 或 常数（int/float）
                 或 函数 f(t)
        """
        # 确保节点分类可用
        need_attrs = ('internal_nodes', 'external_in_nodes', 'external_out_nodes')
        if not all(hasattr(self, a) for a in need_attrs):
            self.classfy_nodes()

        # 检查设定边界是否合法
        if node in self.external_in_nodes:
            if btype not in self.ALLOWED_IN_BTYPE:
                raise ValueError(f"{node}为入流边界，不支持边界类型: {btype!r}；可选: {sorted(self.ALLOWED_IN_BTYPE)}")
        elif node in self.external_out_nodes:
            if btype not in self.ALLOWED_OUT_BTYPE:
                raise ValueError(f"{node}为出流边界，不支持边界类型: {btype!r}；可选: {sorted(self.ALLOWED_OUT_BTYPE)}")
        else:
            raise ValueError(f"节点 {node} 不是外部入点或出点，无法设置边界条件，边界节点有：{self.external_in_nodes + self.external_out_nodes}")

        if data is None:
            # 例如自由边界
            self.boundaries[node] = {"type": btype, "call": (lambda t: None)}
            return

        if callable(data):
            # lambda/函数：直接存
            self.boundaries[node] = {"type": btype, "call": data}
        else:
            # 常数：用可变容器保存，方便运行中实时修改
            box = [float(data)]
            self.boundaries[node] = {
                "type": btype,
                "call": (lambda t, _box=box: _box[0]),
                "_val": box
            }

    # 修改定值的边界条件
    def update_const(self, node: str, new_value: float):
        """运行中实时修改【常数】边界的数值"""
        item = self.boundaries.get(node)
        if not item or "_val" not in item:
            raise TypeError(f"{node} 不是常数边界或未设置")
        item["_val"][0] = float(new_value)

    # 替换边界条件函数
    def update_func(self, node: str, new_func):
        """运行中替换【函数】边界"""
        if not callable(new_func):
            raise TypeError("new_func 必须可调用")
        item = self.boundaries.get(node)
        if not item:
            raise KeyError(f"{node} 边界未设置")
        item["call"] = new_func

    # 更新边界类型
    def update_type(self, node: str, new_type: str):
        """需要的话也可动态切换边界类型（数值/函数保持不变）"""
        if node not in self.boundaries:
            raise KeyError(f"{node} 边界未设置")
        self.boundaries[node]["type"] = new_type

    # 获取边界值
    def get_boundary_value(self, node: str, t: float):
        """
        返回 (btype, value)
        - 对于自由/不需要数值的边界，value 为 None
        - 其余返回浮点数
        """
        item = self.boundaries.get(node)
        if not item:
            raise KeyError(f"{node} 边界未设置")
        return item["type"], item["call"](t)

    # 求指定时刻所有边界的值
    def evaluate_all_boundaries(self, t: float):
        """批量获取：{ node: {'type': ..., 'value': ...} }"""
        out = {}
        for node, item in self.boundaries.items():
            out[node] = {"type": item["type"], "value": item["call"](t)}
        return out

    # 调用河道网格参数优化函数
    def Fine_cell_property_net(self):
        self.call_river_function_by_name('Fine_cell_property2')
        self.Fine_flag = True  # 标记网格参数已优化

    # 调用水面初始化函数
    def Init_water_surface_net(self):
        self.call_river_function_by_name('Init_water_serface')

    # 初始化网格参数
    def Init_cell_property_net(self):
        if self.Fine_flag:
            for u, v, data in self.G.edges(data=True):
                river = data['river']
                river.Init_cell_proprity(True) # 如果网格已重新插值，则不根据断面高度修改河底高程
        else:
            for u, v, data in self.G.edges(data=True):
                river = data['river']
                river.Init_cell_proprity(False) # 如果网格未重新插值，则根据断面高度修改河底高程

    # 保存初始结果
    def Save_basic_data_net(self):
        self.call_river_function_by_name('Save_Basic_data')

    # 计算界面平均流速和波速
    def Caculate_face_U_C_net(self):
        self.call_river_function_by_name('Caculate_face_U_C')

    # 计算Roe格式特征值
    def Caculate_Roe_matrix_net(self):
        self.call_river_function_by_name('Caculate_Roe_matrix')

    # 计算源项
    def Caculate_Source_term_net(self):
        self.call_river_function_by_name('Caculate_source_term_2')

    # 计算Roe格式通量
    def Caculate_Roe_flux_net(self):
        self.call_river_function_by_name('Caculate_Roe_Flux_2')

    # 组合通量
    def Assemble_flux_net(self):
        self.call_river_function_by_name('Assemble_Flux_2')

    # 保存单步模拟结果
    def Save_step_result_net(self):
        self.call_river_function_by_name('Save_result_per_time_step')

    # 更新网格参数
    def Update_cell_property_net(self):
        self.call_river_function_by_name('Update_cell_proprity2')

    # 计算全局CFL时间步长
    def Caculate_global_CFL(self):
        dt_list = []

        # 计算每条河道的CFL时间步长
        for u, v, data in self.G.edges(data=True):
            dti = data['river'].Caculate_CFL_time_for_river_net()
            dt_list.append(dti)

        self.cfl_allowed_dt = min(dt_list) # 计算全局最小时间步长

        if self.verbos:
            print(f'全局最小CFL时间步长: {self.cfl_allowed_dt:.4f} 秒')

    def Set_global_time_step(self, dt):
        # 更新每条河道的时间步长
        for u, v, data in self.G.edges(data=True):
            data['river'].set_next_dt(dt)

    # 更新边界条件
    def Update_boundary_conditions(self):
        # 更新外部边界条件
        self.Update_external_boundary_conditions()

        # 更新内部边界条件
        self.Update_internal_boundary_conditions()

    # 更新外部边界条件
    def Update_external_boundary_conditions(self):
        if self.verbos: print('更新外部入流边界')
        for n in self.external_in_nodes:
            # 获取边界条件及类型
            btype, value = self.get_boundary_value(n, self.current_sim_time)
            for u, v, data in self.G.out_edges(n, data=True):
                river_temp = data['river']
                if btype == 'flow': # 流量边界
                    river_temp.InBound_In_Q(value)
                elif btype == 'fix_level': # 固定水位边界
                    river_temp.InBound_Fix_level(value)
            if self.verbos: print(river_temp.model_name, n, btype, value)

        if self.verbos: print('更新外部出流边界')
        for n in self.external_out_nodes:
            # 获取边界条件及类型
            btype, value = self.get_boundary_value(n, self.current_sim_time)
            for u, v, data in self.G.in_edges(n, data=True):
                river_temp = data['river']
                if btype == 'free': # 自由边界
                    river_temp.OutBound_Free_Outfall()
                elif btype == 'fix_level': # 固定水位边界
                    river_temp.OutBound_Fix_level(value)
            if self.verbos: print(river_temp.model_name, n, btype, value)

    # 更新内部边界条件
    def Update_internal_boundary_conditions(self):
        if self.verbos: print('\n更新内部边界条件...')
        for n in self.internal_nodes:
            if self.verbos: print(f'更新内部节点 {n} 的边界条件')

            iter_time = 1 # 迭代次数
            dz = 999 # 水位变化量
            pure_Q = 999 # 净流量

            # 基于平均水深计算第一步
            node_level = self.Caculate_node_average_level_at_real_cell(n)

            while True:
                # 判断水位错误
                if node_level < 0:
                    node_level = 0
                    print(f'节点{n}迭代水位为{node_level}，小于0，被重置')

                # 应用计算出的水位
                self.Apply_node_target_level(n, node_level)

                # 计算节点处Ac
                ac = self.Caculate_node_Ac_at_ghost_cell(n)

                # 计算节点净流量
                pure_Q = self.Get_node_clear_flow_at_ghost_cell_net(n)

                # 计算节点处dz
                if ac !=0:
                    dz = pure_Q / ac
                else:
                    dz = 0

                # 增加迭代次数
                iter_time += 1

                # 计算新的水位
                node_level += dz

                if self.verbos:(f"第{iter_time}次迭代，ac = {ac}, dz = {dz}，新水位为{node_level}")

                # 终止条件
                if dz / node_level < 1e-5 and np.abs(pure_Q) < self.JPWSPC_Q_limit:
                    self.Apply_node_target_level(n, node_level)  # 应用最终水位
                    if self.verbos:
                        print(f'节点 {n} 达到收敛条件，迭代次数: {iter_time}, 最终水位: {node_level:.2f} 米')
                    break

                # 最大收敛条件
                if iter_time > self.max_iteration:
                    if self.verbos:
                        print(f'节点 {n} 超出迭代次数，最终dz: {dz:.2f} 米， 净流量: {pure_Q:.2f} m³/s')
                    break





    # 计算节点处真实网格的平均水位
    def Caculate_node_average_level_at_real_cell(self, node):
        level_list = []
        river_name = []

        # 流入节点边
        for u, v, data in self.G.in_edges(node, data=True):
            river_temp = data['river']
            level_list.append(river_temp.water_level[-2])
            river_name.append(data['name'])

        # 流出节点边
        for u, v, data in self.G.out_edges(node, data=True):
            river_temp = data['river']
            level_list.append(river_temp.water_level[1])
            river_name.append(data['name'])

        if level_list:
            result = np.average(level_list)
        else:
            result = np.nan

        if self.verbos:
            print(f'节点 {node} 处的真实网格平均水位: {result:.2f} 米 (基于河道{river_name})')

        return result

    # 计算节点处Ac
    def Caculate_node_Ac_at_ghost_cell(self, node):
        ac = 0

        # 流入节点边
        for u, v, data in self.G.in_edges(node, data=True):
            river_temp = data['river']

            level_temp = river_temp.water_level[-1]  # 获取流入节点的水位
            section_name_temp = river_temp.cell_sections[-1]  # 虚拟网格对应断面名称

            A = river_temp.S[-1]  # 对应位置的水面面积
            B = river_temp.cross_section_table.get_width_by_area(section_name_temp, A)  # 获取对应断面宽度
            Q = river_temp.Q[-1]

            ac += (np.sqrt(self.g * A * B) - Q * B / A)

        # 流出节点边
        for u, v, data in self.G.out_edges(node, data=True):
            river_temp = data['river']
            level_temp = river_temp.water_level[0]
            section_name_temp = river_temp.cell_sections[0]  # 虚拟网格对应断面名称
            A = river_temp.S[0]  # 对应位置的水面面积
            B = river_temp.cross_section_table.get_width_by_area(section_name_temp, A)
            Q = river_temp.Q[0]
            ac += (np.sqrt(self.g * A * B) + Q * B / A)
            # 返回Ac
        return self.g * ac


    # 计算节点处虚拟网格的平均水位
    def Caculate_node_average_level_at_ghost_cell(self, node):
        level_list = []
        river_name = []

        # 流入节点边
        for u, v, data in self.G.in_edges(node, data=True):
            river_temp = data['river']
            level_list.append(river_temp.water_level[-1])
            river_name.append(data['name'])

        # 流出节点边
        for u, v, data in self.G.out_edges(node, data=True):
            river_temp = data['river']
            level_list.append(river_temp.water_level[0])
            river_name.append(data['name'])

        if level_list:
            result = np.average(level_list)
        else:
            result = np.nan

        if self.verbos:
            print(f'节点 {node} 处的虚拟网格平均水位: {result:.2f} 米 (基于河道{river_name})')
        return result

    # 将计算出的汊点水位应用
    def Apply_node_target_level(self, node, level):
        # 流入节点的边
        for u, v, data in self.G.in_edges(node, data=True):
            river_temp = data['river']
            river_temp.OutBound_Fix_level(level)

        # 流出节点的边
        for u, v, data in self.G.out_edges(node, data=True):
            river_temp = data['river']
            river_temp.InBound_Fix_level(level)

    # 获取应用汊点水位后，汊点的净流量大小
    def Get_node_clear_flow_at_ghost_cell_net(self, node):
        pure_Q = 0 # 净流量

        # 流入节点的边
        for u, v, data in self.G.in_edges(node,data=True):
            river_temp = data['river']
            pure_Q += river_temp.Q[-1]  # 获取流入节点的水流量

        # 流出节点的边
        for u, v, data in self.G.out_edges(node,data=True):
            river_temp = data['river']
            pure_Q -= river_temp.Q[0]  # 获取流出节点的水流量1

        return pure_Q

    # 重采样并保存结果
    def Resample_and_Save_result_net(self):
        self.call_river_function_by_name('Check_Resample_and_Save_Output_result')

    # 获取演进信息
    def print_evolve_info(self):
        td = datetime.timedelta(seconds=float(self.current_sim_time))
        days = td.days
        hours, rem = divmod(td.seconds, 3600)  # 先拆小时
        minutes, seconds = divmod(rem, 60)  # 再拆分钟
        total_time_use = time.time() - self.caculation_start_time  # 总耗时
        print(f'当前模拟时间:{days}天{hours}小时{minutes}分钟{seconds}秒，模拟子步数量:{self.sub_step_count}，当前步计算耗时:{self.sub_step_caculation_time_using:.2f}秒，时间步长范围:[{self.sub_step_min_dt:.2f} - {self.sub_step_max_dt:.2f}]秒，总耗时:{total_time_use:.2f}秒')

    # 演进子步
    def _evolve_base(self, yield_step):
        yield_flag = False  # 是否需要回报子步
        finish_flag = False # 判断是否结束
        self.sub_step_start_time = time.time()  # 子步开始时间
        self.caculation_start_time = time.time()  # 计算开始时间
        while self.current_sim_time < self.total_sim_time:
            # 同步时间
            self.Set_global_time_step(self.DT)

            # 累加总时间
            self.current_sim_time += self.DT
            self.step_count += 1

            # 累加子步时间
            self.sub_step_time += self.DT
            self.sub_step_count += 1

            self.sub_step_max_dt = max(self.sub_step_max_dt, self.DT)  # 更新子步最大时间步长
            self.sub_step_min_dt = min(self.sub_step_min_dt, self.DT)  # 更新子步最小时间步长

            # 更新边界条件
            self.Update_boundary_conditions()

            # 计算界面U、C
            self.Caculate_face_U_C_net()

            # 计算Roe matrix
            self.Caculate_Roe_matrix_net()

            # 计算Source_term2
            self.Caculate_Source_term_net()

            # 计算Roe_flux2
            self.Caculate_Roe_flux_net()

            # 组装assemble flux2
            self.Assemble_flux_net()

            # 更新河道网格参数 cell proptirty2
            self.Update_cell_property_net()

            # 保存结果
            self.Save_step_result_net()

            # 汇报子步演进
            if yield_flag:
                self.sub_step_caculation_time_using = time.time() - self.sub_step_start_time  # 计算子步耗时
                yield self.current_sim_time

                yield_flag = False  # 重置标志
                self.sub_step_start_time = time.time()  # 重置子步开始时间
                self.sub_step_time = 0.0  # 重置子步时间
                self.sub_step_count = 0  # 重置子步计数
                self.sub_step_max_dt = 0.0  # 重置子步最大时间步长
                self.sub_step_min_dt = 999999  # 重置子步最小时间

            # 计算完最后一个时间步退出
            if finish_flag:
                break

            # 计算CFL条件，更新时间步长
            self.Caculate_global_CFL()

            # 统计全局最小时间步长，处理时间逻辑
            # 保证最后一个时刻为总时间的最后一个时间
            if self.current_sim_time + self.cfl_allowed_dt > self.total_sim_time + 1e-5:
                self.DT = self.total_sim_time - self.current_sim_time # 基于总时间计算时间步长

            elif self.sub_step_time + self.cfl_allowed_dt > yield_step + 1e-5:
                self.DT = yield_step - self.sub_step_time # 基于子步时间计算时间步长
                yield_flag = True  # 标记需要回报子步

            else:
                self.DT = self.cfl_allowed_dt # 基于全局最小CFL时间步长计算时间步长

        # 计算结束，保存结果
        self.caculation_time = time.time() - self.caculation_start_time  # 计算总耗时
        print(f'计算结束，保存结果...\n共计算 {self.step_count} 步，总耗时: {self.caculation_time:.2f} 秒')
        self.Resample_and_Save_result_net()

    # 演进过程
    def Evolve(self, yield_step=None):
        # 框定回报时间
        if yield_step is None:
            yield_step = self.model_data['time_step']

        # 优化网格参数
        if self.Fine_flag:
            self.Fine_cell_property_net()

        # 初始化水面参数
        self.Init_water_surface_net()

        # 初始化其余参数
        self.Init_cell_property_net()

        # 保存初始结果
        self.Save_basic_data_net()

        # 计算第一步时间步长
        self.Caculate_global_CFL()
        self.DT = self.cfl_allowed_dt  # 初始时间步长为全局最小CFL时间步长

        # 调用evolve_base, 统计子步演进数量、DT范围
        for t in self._evolve_base(yield_step):
            yield t


    # 导出为 PNG 图片
    def export_png(self, path='rivernet.png', figsize=(9, 6), layout='spring', show_node_labels=True, show_edge_labels=True, dpi=400):
        """
        将当前有向图渲染为 PNG 图片并保存到 path。
        - 默认输出到当前目录的 rivernet.png
        - 在无界面环境中强制使用 'Agg' 后端
        """
        import os, math
        import networkx as nx
        import matplotlib
        matplotlib.use('Agg', force=True)  # 关键：无界面后端
        import matplotlib.pyplot as plt
        from matplotlib.patches import Patch

        if not self.G.is_directed():
            raise ValueError('当前图不是有向图，请先用 DiGraph 存储或转换为有向图。')

        # 确保节点分类可用
        need_attrs = ('internal_nodes', 'external_in_nodes', 'external_out_nodes')
        if not all(hasattr(self, a) for a in need_attrs):
            self.classfy_nodes()

        # 选择布局
        n = max(len(self.G), 1)
        if layout == 'spring':
            k = 1 / math.sqrt(n)
            pos = nx.spring_layout(self.G, seed=42, k=k)
        elif layout == 'kamada_kawai':
            pos = nx.kamada_kawai_layout(self.G)
        elif layout == 'circular':
            pos = nx.circular_layout(self.G)
        elif layout == 'random':
            pos = nx.random_layout(self.G, seed=42)
        else:
            raise ValueError(f'未知布局: {layout}')

        # 颜色与尺寸
        color_internal = '#4C78A8'  # 蓝
        color_external_in = '#F58518'  # 橙（只有入）
        color_external_out = '#54A24B'  # 绿（只有出）
        node_size_internal, node_size_external = 700, 600

        # 绘图
        fig, ax = plt.subplots(figsize=figsize)

        nx.draw_networkx_nodes(self.G, pos,
                               nodelist=self.internal_nodes,
                               node_color=color_internal, node_size=node_size_internal, ax=ax, label='internal')
        nx.draw_networkx_nodes(self.G, pos,
                               nodelist=getattr(self, 'external_in_nodes', []),
                               node_color=color_external_in, node_size=node_size_external, ax=ax, label='external_in')
        nx.draw_networkx_nodes(self.G, pos,
                               nodelist=getattr(self, 'external_out_nodes', []),
                               node_color=color_external_out, node_size=node_size_external, ax=ax, label='external_out')

        nx.draw_networkx_edges(
            self.G, pos, ax=ax,
            arrows=True, arrowstyle='-|>', arrowsize=18,
            width=1.6, connectionstyle='arc3,rad=0.05'
        )

        if show_node_labels:
            nx.draw_networkx_labels(self.G, pos, font_size=10, ax=ax)

        if show_edge_labels:
            edge_labels = {(u, v): data.get('name') for u, v, data in self.G.edges(data=True) if data.get('name')}
            if edge_labels:
                nx.draw_networkx_edge_labels(self.G, pos, edge_labels=edge_labels,
                                             font_size=9, label_pos=0.5, ax=ax)

        # 图例
        handles = [
            Patch(facecolor=color_internal, edgecolor='none', label='internal'),
            Patch(facecolor=color_external_in, edgecolor='none', label='external_in'),
            Patch(facecolor=color_external_out, edgecolor='none', label='external_out'),
        ]
        ax.legend(handles=handles, loc='best', frameon=False)

        ax.set_axis_off()
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        plt.tight_layout()
        plt.savefig(path, dpi=dpi, bbox_inches='tight')
        plt.close(fig)

        if self.verbos:
            print(f'[OK] PNG 导出完成 -> {path}')


if __name__ == '__main__' and False:
    output_path = 'result'  # 输出路径

    river_data = {
        "cell_num": 120,  # 计算单元数量
        "pos": [[1, 1, 0], [400, 1, 0], [800, 1, 0], [1200, 1, 0]],  # 河道点坐标 长度、宽度、高度
        "section_name": ['se1', 'se2', 'se3']  # 断面名称
    }
    section_data = {
        'se1': [[0, 12], [0.5, 0], [1, 0], [1.5, 12]],
        'se2': [[0, 12], [0.5, 0], [1, 0], [1.5, 12]],
        'se3': [[0, 12], [0.5, 0], [1, 0], [1.5, 12]],
    }

    model_data = {
        'model_name':'river_net',
        'sim_start_time': '2024-01-01 00:00:00',
        'sim_end_time': '2024-01-01 01:30:00',
        'time_step': 5,  # 单位：秒
        'output_path': output_path,
        'CFL': 0.3,
    }

    section_pos = {
        'se1': [1, 1],
        'se2': [400, 1],
        'se3': [1200, 1]
    }

    section_pos = None

    top = {
        ('n1', 'n5'): {'name': 'river1', 'river_data': river_data,
                       'section_data': section_data, 'model_data': model_data, 'section_pos': section_pos,
                       'manning': 0.1},

        ('n2', 'n5'): {'name': 'river2', 'river_data': river_data,
                       'section_data': section_data, 'model_data': model_data, 'section_pos': section_pos,
                       'manning': 0.1},

        ('n3', 'n6'): {'name': 'river3', 'river_data': river_data, 'section_data': section_data,
                       'model_data': model_data, 'section_pos': section_pos, 'manning': 0.1},

        ('n4', 'n6'): {'name': 'river4', 'river_data': river_data, 'section_data': section_data,
                       'model_data': model_data, 'section_pos': section_pos, 'manning': 0.1},

        ('n5', 'n6'): {'name': 'river5', 'river_data': river_data, 'section_data': section_data,
                       'model_data': model_data, 'section_pos': section_pos, 'manning': 0.1},

        ('n7', 'n8'): {'name': 'river8', 'river_data': river_data, 'section_data': section_data,
                       'model_data': model_data, 'section_pos': section_pos, 'manning': 0.1},

        ('n5', 'n7'): {'name': 'river6', 'river_data': river_data, 'section_data': section_data,
                       'model_data': model_data, 'section_pos': section_pos, 'manning': 0.1},

        ('n6', 'n8'): {'name': 'river7', 'river_data': river_data, 'section_data': section_data,
                       'model_data': model_data, 'section_pos': section_pos, 'manning': 0.1},

        ('n7', 'n9'): {'name': 'river9', 'river_data': river_data, 'section_data': section_data,
                       'model_data': model_data, 'section_pos': section_pos, 'manning': 0.1},

        ('n9', 'n10'): {'name': 'river10', 'river_data': river_data, 'section_data': section_data,
                        'model_data': model_data, 'section_pos': section_pos, 'manning': 0.1},
    }

    # top = {
    #     ('n1', 'n3'): {'name': 'river1', 'river_data': river_data,
    #                    'section_data': section_data, 'model_data': model_data, 'section_pos': section_pos,
    #                    'manning': 0.1},
    #     ('n2', 'n3'): {'name': 'river2', 'river_data': river_data,
    #                    'section_data': section_data, 'model_data': model_data, 'section_pos': section_pos,
    #                    'manning': 0.1},
    #     ('n3', 'n4'): {'name': 'river3', 'river_data': river_data,
    #                    'section_data': section_data, 'model_data': model_data, 'section_pos': section_pos,
    #                    'manning': 0.1},
    #
    # }

    net = Rivernet(top, model_data)

    net.export_png(path='result/rivernet.png')

    net.max_iteration = 50

    net.verbos = False

    # net.Fine_flag = True

    net.set_boundary('n1', 'flow', 1)  # 流量边界
    net.set_boundary('n2', 'flow', 2)
    net.set_boundary('n3', 'flow', 2)

    net.set_boundary('n4', 'flow', 2)  # 固定水位边界

    net.set_boundary('n10', 'free')


    for u, v, data in net.G.edges(data=True):
        river = data['river']
        river.Set_init_water_level(2)

    for t in net.Evolve(yield_step=300):
        net.print_evolve_info()



# ---- END Rivernet ----


# =========================
# Numba + Parallel Patches
# =========================
import atexit
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed

try:
    from numba import njit, prange
    _NUMBA_OK = True
except Exception:
    _NUMBA_OK = False
    def njit(*args, **kwargs):
        def deco(f): return f
        return deco
    def prange(n): return range(n)

# --------- Numba kernels ---------
@njit(cache=True, fastmath=True)
def _nb_face_uc(S, U, C, PRESS, S_limit, EPS, F_U, F_C):
    """
    Compute Roe-averaged interface velocity (F_U) and wave speed (F_C).
    All arrays are 1D; length assumptions:
      - S, U, C, PRESS have length >= N+1
      - F_U, F_C length == N  where N = len(F_U)
    """
    N = F_U.shape[0]
    for i in range(N):
        # weighted average velocity
        ls = S[i]; rs = S[i+1]
        if ls < S_limit: ls = S_limit
        if rs < S_limit: rs = S_limit
        lsr = (ls) ** 0.5
        rsr = (rs) ** 0.5
        lu = U[i]
        ru = U[i+1]
        F_U[i] = (lu * lsr + ru * rsr) / (lsr + rsr)

        # wave speed
        # if |S[i]-S[i+1]| small => average C; else sqrt((dP)/(dS))
        dS = S[i] - S[i+1]
        if dS*dS <= 1e-6:
            F_C[i] = 0.5 * (C[i] + C[i+1])
        else:
            dP = PRESS[i] - PRESS[i+1]
            r = dP / (dS + (0.0 if dS != 0.0 else EPS))
            if r < EPS:
                r = EPS
            F_C[i] = (r) ** 0.5

@njit(cache=True, fastmath=True)
def _nb_roe_matrix(F_C, F_U, BETA, FR, water_depth, water_depth_limit, U, C, S, Q,
                   EPS, Lambda1, Lambda2, abs_L1, abs_L2, alpha1, alpha2,
                   V1, V2, V1T, V2T, flag_LeVeque):
    """
    Vectorized Roe matrix build per interface.
    Array lengths:
      - interface arrays length N = len(F_C) = len(F_U)
      - cell arrays length N+1 (S, Q, U, C, BETA, FR, water_depth)
    """
    N = F_C.shape[0]
    for i in range(N):
        Roe_C = F_C[i]
        Roe_U = F_U[i]
        beta = 0.5 * (BETA[i] + BETA[i+1])

        # Z
        t = beta * (1.0 - beta) * Roe_U * Roe_U
        zsq = Roe_C*Roe_C - t
        if zsq < 0.0: zsq = 0.0
        Z = zsq ** 0.5

        # lambdas
        l1 = beta * Roe_U - Z
        l2 = beta * Roe_U + Z

        # LeVeque indicators
        frL = FR[i]
        frR = FR[i+1]
        depL = water_depth[i]
        # depR = water_depth[i+1]   # not used, condition simplified
        indic = (depL > water_depth_limit)  # conservative

        if (frR > 1.0) and (frL < 1.0) and (Roe_U > 0.0) and indic:
            L1D = beta * U[i]     - C[i]
            L1G = beta * U[i+1]   - C[i+1]
            denom = (L1G - L1D)
            if denom != 0.0:
                l1 = L1G * ((l1 - L1D) / denom)
            flag_LeVeque[i] = 2.0

        if (frR < 1.0) and (frL > 1.0) and (Roe_U < 0.0) and indic:
            L2D = beta * U[i]     + C[i]
            L2G = beta * U[i+1]   + C[i+1]
            denom = (L2D - L2G)
            if denom != 0.0:
                l2 = L2D * ((l2 - L2G) / denom)
            flag_LeVeque[i] = 1.0

        Lambda1[i] = l1
        Lambda2[i] = l2
        abs_L1[i] = l1 if l1 >= 0.0 else -l1
        abs_L2[i] = l2 if l2 >= 0.0 else -l2

        # wave amplitudes
        dS = S[i+1] - S[i]
        dQ = Q[i+1] - Q[i]
        denom = (2.0 * Roe_C + EPS)
        a2 = (dQ - dS * (Roe_U - Roe_C)) / denom
        a1 = dS - a2
        alpha1[i] = a1
        alpha2[i] = a2

        # eigen vectors & inverse rows
        Beta_U = beta * Roe_U
        # V1
        V1[i,0] = 1.0
        V1[i,1] = Beta_U - Z
        # V1T
        denom2 = (2.0 * Z)
        if denom2 == 0.0:
            denom2 = EPS
        V1T[i,0] = (Beta_U + Z) / denom2
        V1T[i,1] = -1.0 / denom2

        # V2
        V2[i,0] = 1.0
        V2[i,1] = Beta_U + Z
        # V2T
        V2T[i,0] = -(Beta_U - Z) / denom2
        V2T[i,1] = 1.0 / denom2

@njit(cache=True, fastmath=True, parallel=True)
def _nb_flux_update(N, Flux_LOC, Flux_Source_right, Flux_Source_left,
                    Flux_Friction_right, Flux_Friction_left, Flux_Source_center,
                    DT, cell_lengths, S, Q, out_Flux, out_S, out_Q):
    """
    Compute Flux[i] = (Flux_LOC[i]-Flux_LOC[i-1]) + sources, i in 1..N
    Then update S,Q by WW = -Flux * DT / dx.
    Writes results into out_Flux[1:N+1], out_S[1:N+1], out_Q[1:N+1].
    """
    for i in prange(1, N+1):
        fl0 = Flux_LOC[i,0] - Flux_LOC[i-1,0]
        fl1 = Flux_LOC[i,1] - Flux_LOC[i-1,1]

        sr0 = Flux_Source_right[i,0] + Flux_Source_left[i,0] + Flux_Friction_left[i,0] + Flux_Friction_right[i,0]
        sr1 = (Flux_Source_center[i,1] + Flux_Source_right[i,1] + Flux_Source_left[i,1]
               + Flux_Friction_left[i,1] + Flux_Friction_right[i,1])

        f0 = fl0 + sr0
        f1 = fl1 + sr1

        out_Flux[i,0] = f0
        out_Flux[i,1] = f1

        dx = cell_lengths[i]
        ww0 = - f0 * DT / dx
        ww1 = - f1 * DT / dx

        out_S[i] = S[i] + ww0
        out_Q[i] = Q[i] + ww1

# --------- Monkey patches for River (Numba) ---------
def _patch_river_numba():
    # Only patch once
    if getattr(River, "_numba_patched", False):
        return

    def _Caculate_face_U_C(self):
        N = self.cell_num + 1
        _nb_face_uc(self.S, self.U, self.C, self.PRESS, self.S_limit, self.EPSILON, self.F_U[:N], self.F_C[:N])

    def _Caculate_Roe_matrix(self):
        N = self.cell_num + 1
        _nb_roe_matrix(self.F_C[:N], self.F_U[:N], self.BETA, self.FR,
                       self.water_depth, self.water_depth_limit,
                       self.U, self.C, self.S, self.Q,
                       self.EPSILON,
                       self.Lambda1[:N], self.Lambda2[:N],
                       self.abs_Lambda1[:N], self.abs_Lambda2[:N],
                       self.alpha1[:N], self.alpha2[:N],
                       self.Vactor1[:N], self.Vactor2[:N],
                       self.Vactor1_T[:N], self.Vactor2_T[:N],
                       self.flag_LeVeque[:N])

    def _Assemble_Flux_2(self):
        N = self.cell_num
        # run kernel
        _nb_flux_update(N,
                        self.Flux_LOC, self.Flux_Source_right, self.Flux_Source_left,
                        self.Flux_Friction_right, self.Flux_Friction_left, self.Flux_Source_center,
                        self.DT, self.cell_lengths, self.S, self.Q,
                        self.Flux, self.S, self.Q)

        # 半隐式处理源项（保持原逻辑）
        if getattr(self, "FRTIMP", 0):
            for i in range(1, self.cell_num + 1):
                if self.S[i] < self.S_limit:
                    self.S[i] = self.cross_section_table.get_area_by_depth(self.cell_sections[i], self.water_depth_limit)
                    self.Q[i] = 0.0
                    self.U[i] = 0.0
                    self.C[i] = 0.0
                    self.FR[i] = 0.0
                else:
                    deb = self.cross_section_table.get_DEB_by_area(self.cell_sections[i], self.S[i])
                    coef = self.g * self.DT * self.S[i] / (deb * deb)
                    delta = (1.0 + 4.0 * coef * abs(self.Q[i]))
                    if coef > 1e-6:
                        if self.Q[i] > 0.0:
                            self.Q[i] = (-1.0 + delta ** 0.5) / (2.0 * coef)
                        else:
                            self.Q[i] = ( 1.0 - delta ** 0.5) / (2.0 * coef)
                    else:
                        self.Q[i] = self.Q[i] * (1.0 - coef * self.Q[i])

        # 更新 U、C、FR（保持与原版一致）
        for i in range(1, self.cell_num + 1):
            if self.S[i] < self.S_limit:
                self.S[i] = self.cross_section_table.get_area_by_depth(self.cell_sections[i], self.water_depth_limit)
                self.Q[i] = 0.0
                self.U[i] = 0.0
                self.C[i] = 0.0
                self.FR[i] = 0.0
            else:
                self.U[i] = self.Q[i] / self.S[i]
                depth = self.water_depth[i]
                wsw = self.S[i] / depth if depth != 0 else 0.0
                if wsw > self.EPSILON:
                    self.C[i] = (self.g * self.S[i] / wsw) ** 0.5
                    cu = self.C[i]
                    self.FR[i] = abs(self.U[i]) / (cu if cu != 0 else 1e-12)
                else:
                    self.C[i] = 0.0
                    self.FR[i] = 0.0

    # Attach patches
    River.Caculate_face_U_C = _Caculate_face_U_C
    River.Caculate_Roe_matrix = _Caculate_Roe_matrix
    River.Assemble_Flux_2 = _Assemble_Flux_2
    River._numba_patched = True

# --------- Monkey patches for Rivernet (thread/process pool + coloring) ---------
def _parallel_call_river_method(river, method_name):
    getattr(river, method_name)()
    return river


def _patch_rivernet_parallel():
    if getattr(Rivernet, "_parallel_patched", False):
        return

    _orig_init = Rivernet.__init__
    def _init(self, Topology, model_data, verbos=True, parallel_workers=None, parallel_mode=None):
        _orig_init(self, Topology, model_data, verbos=verbos)

        def _normalize_workers(value):
            if value is None:
                return 0
            value = int(value)
            if value < 0:
                raise ValueError("parallel_workers must be >= 0")
            return value

        def _normalize_mode(value):
            if value is None:
                return "thread"
            value = str(value).strip().lower()
            if value in ("thread", "threads", "t"):
                return "thread"
            if value in ("process", "processes", "proc", "p"):
                return "process"
            raise ValueError("parallel_mode must be 'thread' or 'process'")

        def _shutdown_pool():
            old_pool = getattr(self, "_pool", None)
            if old_pool is not None:
                old_pool.shutdown(wait=True)
            self._pool = None

        def _set_parallel(new_workers=None, new_mode=None):
            if new_workers is None:
                new_workers = getattr(self, "parallel_workers", 0)
            if new_mode is None:
                new_mode = getattr(self, "parallel_mode", "thread")

            new_workers = _normalize_workers(new_workers)
            new_mode = _normalize_mode(new_mode)
            _shutdown_pool()

            self._parallel_enabled = False
            self.parallel_workers = new_workers
            self.parallel_mode = new_mode

            if new_workers >= 2:
                if new_mode == "process":
                    self._pool = ProcessPoolExecutor(max_workers=new_workers)
                else:
                    self._pool = ThreadPoolExecutor(
                        max_workers=new_workers,
                        thread_name_prefix="RivernetPool"
                    )
                self._parallel_enabled = True

        self._shutdown_parallel_pool = _shutdown_pool
        self._set_parallel = _set_parallel
        self._set_parallel_workers = lambda workers: _set_parallel(new_workers=workers, new_mode=getattr(self, "parallel_mode", "thread"))
        self._set_parallel_mode = lambda mode: _set_parallel(new_workers=getattr(self, "parallel_workers", 0), new_mode=mode)
        self.get_parallel_workers = lambda: self.parallel_workers
        self.get_parallel_mode = lambda: self.parallel_mode

        if parallel_workers is None:
            parallel_workers = model_data.get("parallel_workers", 0)
        if parallel_mode is None:
            parallel_mode = model_data.get("parallel_mode", "thread")
        self._set_parallel(parallel_workers, parallel_mode)
        atexit.register(lambda: getattr(self, "_pool", None) and self._pool.shutdown(wait=True))

    def _del(self):
        try:
            p = getattr(self, "_pool", None)
            if p:
                p.shutdown(wait=True)
        except Exception:
            pass

    def _all_rivers(self):
        return [data['river'] for _, _, data in self.G.edges(data=True) if data.get('river') is not None]

    def _parallel_map(self, method_name):
        river_edges = [(u, v, data['river']) for u, v, data in self.G.edges(data=True) if data.get('river') is not None]
        if not getattr(self, "_parallel_enabled", False):
            for _, _, r in river_edges:
                getattr(r, method_name)()
            return

        if getattr(self, "parallel_mode", "thread") == "process":
            futures = [self._pool.submit(_parallel_call_river_method, r, method_name) for _, _, r in river_edges]
            updated = [f.result() for f in futures]
            for (u, v, _), river in zip(river_edges, updated):
                self.G.edges[(u, v)]['river'] = river
        else:
            futures = [self._pool.submit(getattr(r, method_name)) for _, _, r in river_edges]
            for f in futures:
                f.result()

    def _Caculate_face_U_C_net(self): _parallel_map(self, 'Caculate_face_U_C')
    def _Caculate_Roe_matrix_net(self): _parallel_map(self, 'Caculate_Roe_matrix')
    def _Caculate_Source_term_net(self): _parallel_map(self, 'Caculate_source_term_2')
    def _Caculate_Roe_flux_net(self): _parallel_map(self, 'Caculate_Roe_Flux_2')
    def _Assemble_flux_net(self): _parallel_map(self, 'Assemble_Flux_2')
    def _Update_cell_property_net(self): _parallel_map(self, 'Update_cell_proprity2')
    def _Save_step_result_net(self): _parallel_map(self, 'Save_result_per_time_step')

    import networkx as _nx
    def _Update_internal_boundary_conditions(self):
        if self.verbos:
            print('\n更新内部边界条件(主进程序列)...')
        H = _nx.Graph()
        H.add_nodes_from(self.internal_nodes)
        for u, v in self.G.edges():
            if (u in self.internal_nodes) and (v in self.internal_nodes):
                H.add_edge(u, v)

        color_map = _nx.coloring.greedy_color(H, strategy='largest_first')
        batches = {}
        for n, c in color_map.items():
            batches.setdefault(c, []).append(n)

        def _solve_node(node):
            iter_time = 1
            dz = 999.0
            pure_Q = 999.0
            node_level = self.Caculate_node_average_level_at_real_cell(node)
            if node_level < 0:
                node_level = 0.0

            while True:
                if node_level < 0.0:
                    node_level = 0.0
                self.Apply_node_target_level(node, node_level)
                ac = self.Caculate_node_Ac_at_ghost_cell(node)
                pure_Q = self.Get_node_clear_flow_at_ghost_cell_net(node)
                dz = pure_Q / ac if ac != 0 else 0.0
                iter_time += 1
                node_level += dz
                if node_level != 0:
                    cond = (abs(dz / node_level) < 1e-5) and (abs(pure_Q) < self.JPWSPC_Q_limit)
                else:
                    cond = abs(pure_Q) < self.JPWSPC_Q_limit
                if cond:
                    self.Apply_node_target_level(node, node_level)
                    break
                if iter_time > self.max_iteration:
                    break
            return node

        for _, nodes in sorted(batches.items()):
            for n in nodes:
                _solve_node(n)

    Rivernet.__init__ = _init
    Rivernet.__del__ = _del
    Rivernet._parallel_map = _parallel_map
    Rivernet._all_rivers = _all_rivers
    Rivernet.Caculate_face_U_C_net = _Caculate_face_U_C_net
    Rivernet.Caculate_Roe_matrix_net = _Caculate_Roe_matrix_net
    Rivernet.Caculate_Source_term_net = _Caculate_Source_term_net
    Rivernet.Caculate_Roe_flux_net = _Caculate_Roe_flux_net
    Rivernet.Assemble_flux_net = _Assemble_flux_net
    Rivernet.Update_cell_property_net = _Update_cell_property_net
    Rivernet.Save_step_result_net = _Save_step_result_net
    Rivernet.Update_internal_boundary_conditions = _Update_internal_boundary_conditions
    Rivernet._parallel_patched = True

# Run patchers when this module is imported/executed
try:
    _patch_river_numba()
    _patch_rivernet_parallel()
except Exception as _e:
    print("[WARN] Patching failed:", _e)

# Keep compatibility with older import name.
RiverNet = Rivernet


# =========================
# True multiprocessing river-network manager
# =========================
import sys
import traceback
import multiprocessing as mp


def _river_apply_boundary_spec(river, side, spec):
    """Apply one-side boundary condition to a River instance."""
    if not spec:
        return
    btype = spec.get('type')
    value = spec.get('value', None)
    if side == 'upstream':
        if btype == 'flow':
            river.InBound_In_Q(value)
        elif btype == 'fix_level':
            river.InBound_Fix_level(value)
        elif btype in (None, 'none'):
            return
        else:
            raise ValueError(f'Unsupported upstream boundary type: {btype!r}')
    elif side == 'downstream':
        if btype == 'free':
            river.OutBound_Free_Outfall()
        elif btype == 'fix_level':
            river.OutBound_Fix_level(value)
        elif btype in (None, 'none'):
            return
        else:
            raise ValueError(f'Unsupported downstream boundary type: {btype!r}')
    else:
        raise ValueError(f'Unknown side: {side}')


def _river_get_real_levels(river):
    return {
        'upstream': float(river.water_level[1]),
        'downstream': float(river.water_level[-2]),
    }


def _river_get_ghost_summary(river, side):
    if side == 'upstream':
        idx = 0
    elif side == 'downstream':
        idx = -1
    else:
        raise ValueError(f'Unknown side: {side}')

    section_name = river.cell_sections[idx]
    A = float(river.S[idx])
    Q = float(river.Q[idx])
    B = float(river.cross_section_table.get_width_by_area(section_name, A))
    level = float(river.cross_section_table.get_level_by_area(section_name, A))
    return {
        'side': side,
        'A': A,
        'Q': Q,
        'B': B,
        'level': level,
        'section_name': section_name,
    }


def _river_initialize_for_network(river, fine=False, init_level=None):
    if fine:
        river.Fine_cell_property2()
    if init_level is not None:
        river.Set_init_water_level(init_level)
    river.Init_water_serface()
    river.Init_cell_proprity(bool(fine))
    river.Save_Basic_data()
    return {
        'ok': True,
        'real_levels': _river_get_real_levels(river),
        'dt': float(getattr(river, 'DT', 0.0)),
    }


def _river_advance_one_step(river, dt, save_result=True):
    river.DT = float(dt)
    river.current_sim_time += river.DT
    river.Caculate_face_U_C()
    river.Caculate_Roe_matrix()
    river.Caculate_source_term_2()
    river.Caculate_Roe_Flux_2()
    river.Caculate_dam()
    river.Assemble_Flux_2()
    river.Update_cell_proprity2()
    if save_result:
        river.Save_result_per_time_step()
    next_dt = float(river.Caculate_CFL_time_for_river_net())
    return {
        'ok': True,
        'current_time': float(river.current_sim_time),
        'next_dt': next_dt,
        'real_levels': _river_get_real_levels(river),
        'ghost_upstream': _river_get_ghost_summary(river, 'upstream'),
        'ghost_downstream': _river_get_ghost_summary(river, 'downstream'),
    }


class RiverWorkerProcess(mp.Process):
    """One persistent process for one river."""
    def __init__(self, edge_key, edge_info, model_data, cmd_queue, resp_queue,
                 fine=False, init_level=None):
        super().__init__()
        self.edge_key = edge_key
        self.edge_info = edge_info
        self.model_data = model_data
        self.cmd_queue = cmd_queue
        self.resp_queue = resp_queue
        self.fine = fine
        self.init_level = init_level

    def _make_river(self):
        sim_data = {
            'model_name': self.edge_info['name'],
            'sim_start_time': self.model_data['sim_start_time'],
            'sim_end_time': self.model_data['sim_end_time'],
            'time_step': self.model_data['time_step'],
            'output_path': self.model_data['output_path'],
            'CFL': self.model_data['CFL'],
            'n': self.edge_info.get('manning', self.model_data.get('n', 0.03)),
        }
        return River(
            self.edge_info['river_data'],
            self.edge_info['section_data'],
            self.edge_info.get('section_pos'),
            sim_data,
        )

    def run(self):
        river = None
        try:
            river = self._make_river()
            while True:
                msg = self.cmd_queue.get()
                if msg is None:
                    break
                cmd = msg.get('cmd')
                req_id = msg.get('req_id')
                try:
                    if cmd == 'INIT':
                        payload = _river_initialize_for_network(
                            river,
                            fine=msg.get('fine', self.fine),
                            init_level=msg.get('init_level', self.init_level),
                        )
                    elif cmd == 'APPLY_BOUNDARY':
                        side = msg['side']
                        spec = msg['spec']
                        _river_apply_boundary_spec(river, side, spec)
                        payload = {
                            'ok': True,
                            'ghost_summary': _river_get_ghost_summary(river, side),
                            'real_levels': _river_get_real_levels(river),
                        }
                    elif cmd == 'ADVANCE':
                        payload = _river_advance_one_step(
                            river,
                            dt=msg['dt'],
                            save_result=msg.get('save_result', True),
                        )
                    elif cmd == 'GET_REAL_LEVELS':
                        payload = {'ok': True, 'real_levels': _river_get_real_levels(river)}
                    elif cmd == 'FINALIZE':
                        river.Check_Resample_and_Save_Output_result()
                        payload = {'ok': True}
                    elif cmd == 'STOP':
                        do_finalize = msg.get('finalize', True)
                        if do_finalize:
                            river.Check_Resample_and_Save_Output_result()
                        self.resp_queue.put({'req_id': req_id, 'ok': True, 'payload': {'ok': True}})
                        break
                    else:
                        raise ValueError(f'Unknown command: {cmd}')
                    self.resp_queue.put({'req_id': req_id, 'ok': True, 'payload': payload})
                except Exception as e:
                    self.resp_queue.put({
                        'req_id': req_id,
                        'ok': False,
                        'error': repr(e),
                        'traceback': traceback.format_exc(),
                    })
        except Exception as e:
            self.resp_queue.put({
                'req_id': '__BOOT__',
                'ok': False,
                'error': repr(e),
                'traceback': traceback.format_exc(),
            })


class RivernetMP:
    """Process-based river-network manager: one persistent process per river."""
    def __init__(self, Topology, model_data, verbos=True, fine=False,
                 init_level=None, mp_start_method=None):
        self.topology = Topology
        self.model_data = model_data
        self.verbos = verbos
        self.fine = fine
        self.init_level = init_level
        self.current_sim_time = 0.0
        self.step_count = 0
        self.boundaries = {}
        self.ALLOWED_OUT_BTYPE = {'free', 'fix_level'}
        self.ALLOWED_IN_BTYPE = {'flow', 'fix_level'}
        self.alpha = 1.2
        self.max_iteration = 20
        self.g = 9.81
        self.JPWSPC_Q_limit = 1e-3
        self.sim_start_time = datetime.datetime.strptime(model_data['sim_start_time'], '%Y-%m-%d %H:%M:%S')
        self.sim_end_time = datetime.datetime.strptime(model_data['sim_end_time'], '%Y-%m-%d %H:%M:%S')
        self.total_sim_time = (self.sim_end_time - self.sim_start_time).total_seconds()
        self.report_time = 0.0
        self.node_levels = {}
        self._req_seq = 0
        if mp_start_method is None:
            mp_start_method = 'fork' if sys.platform != 'win32' else 'spawn'
        self.ctx = mp.get_context(mp_start_method)
        self.G = nx.DiGraph()
        self._build_graph()
        self.classfy_nodes()
        self.edge_runtime = {}
        self._started = False

    def _build_graph(self):
        for (u, v), info in self.topology.items():
            self.G.add_edge(u, v, **info)

    def classfy_nodes(self):
        self.internal_nodes = []
        self.external_in_nodes = []
        self.external_out_nodes = []
        self.isolated_nodes = []
        for n in self.G.nodes():
            indeg = self.G.in_degree(n)
            outdeg = self.G.out_degree(n)
            deg = indeg + outdeg
            if deg == 0:
                self.isolated_nodes.append(n)
            elif deg == 1:
                if indeg == 1 and outdeg == 0:
                    self.external_out_nodes.append(n)
                elif outdeg == 1 and indeg == 0:
                    self.external_in_nodes.append(n)
                else:
                    self.internal_nodes.append(n)
            else:
                self.internal_nodes.append(n)
        self.external_nodes = self.external_in_nodes + self.external_out_nodes

    def set_boundary(self, node: str, btype: str, data=None):
        if node in self.external_in_nodes:
            if btype not in self.ALLOWED_IN_BTYPE:
                raise ValueError(f"{node}为入流边界，不支持边界类型: {btype!r}")
        elif node in self.external_out_nodes:
            if btype not in self.ALLOWED_OUT_BTYPE:
                raise ValueError(f"{node}为出流边界，不支持边界类型: {btype!r}")
        else:
            raise ValueError(f"节点 {node} 不是外部边界节点")

        if data is None:
            self.boundaries[node] = {'type': btype, 'call': (lambda t: None)}
        elif callable(data):
            self.boundaries[node] = {'type': btype, 'call': data}
        else:
            box = [float(data)]
            self.boundaries[node] = {'type': btype, 'call': (lambda t, _box=box: _box[0]), '_val': box}

    def update_const(self, node: str, new_value: float):
        item = self.boundaries.get(node)
        if item is None or '_val' not in item:
            raise KeyError(f'{node} 不是可更新的常数边界')
        item['_val'][0] = float(new_value)

    def get_boundary_value(self, node: str, t: float):
        item = self.boundaries.get(node)
        if item is None:
            raise KeyError(f'{node} 边界未设置')
        return item['type'], item['call'](t)

    def _new_req_id(self):
        self._req_seq += 1
        return self._req_seq

    def _start_workers(self):
        if self._started:
            return
        for edge_key, info in self.topology.items():
            cmd_q = self.ctx.Queue()
            resp_q = self.ctx.Queue()
            proc = RiverWorkerProcess(
                edge_key=edge_key,
                edge_info=info,
                model_data=self.model_data,
                cmd_queue=cmd_q,
                resp_queue=resp_q,
                fine=self.fine,
                init_level=self.init_level,
            )
            proc.daemon = True
            proc.start()
            self.edge_runtime[edge_key] = {
                'process': proc,
                'cmd_q': cmd_q,
                'resp_q': resp_q,
                'name': info['name'],
            }
        self._started = True

    def _rpc(self, edge_key, cmd, **kwargs):
        rt = self.edge_runtime[edge_key]
        req_id = self._new_req_id()
        rt['cmd_q'].put({'req_id': req_id, 'cmd': cmd, **kwargs})
        msg = rt['resp_q'].get()
        if msg.get('req_id') != req_id:
            raise RuntimeError(f'RPC response mismatch for edge {edge_key}: {msg}')
        if not msg.get('ok', False):
            raise RuntimeError(
                f"Worker {edge_key} failed on {cmd}: {msg.get('error')}\n{msg.get('traceback', '')}"
            )
        return msg['payload']

    def initialize(self):
        self._start_workers()
        for edge_key in self.topology:
            self._rpc(edge_key, 'INIT', fine=self.fine, init_level=self.init_level)

    def finalize(self):
        if not self._started:
            return
        for edge_key in self.topology:
            self._rpc(edge_key, 'FINALIZE')

    def stop(self, finalize=True):
        if not self._started:
            return
        for edge_key, rt in self.edge_runtime.items():
            req_id = self._new_req_id()
            rt['cmd_q'].put({'req_id': req_id, 'cmd': 'STOP', 'finalize': finalize})
            msg = rt['resp_q'].get()
            if msg.get('req_id') != req_id:
                raise RuntimeError(f'STOP response mismatch for edge {edge_key}: {msg}')
        for rt in self.edge_runtime.values():
            rt['process'].join(timeout=5)
        self._started = False

    def _node_connected_edge_sides(self, node):
        items = []
        for u, v, data in self.G.in_edges(node, data=True):
            items.append(((u, v), 'downstream', 'in'))
        for u, v, data in self.G.out_edges(node, data=True):
            items.append(((u, v), 'upstream', 'out'))
        return items

    def _apply_external_boundaries(self):
        for n in self.external_in_nodes:
            btype, value = self.get_boundary_value(n, self.current_sim_time)
            for _, v, _ in self.G.out_edges(n, data=True):
                self._rpc((n, v), 'APPLY_BOUNDARY', side='upstream', spec={'type': btype, 'value': value})
        for n in self.external_out_nodes:
            btype, value = self.get_boundary_value(n, self.current_sim_time)
            for u, _, _ in self.G.in_edges(n, data=True):
                self._rpc((u, n), 'APPLY_BOUNDARY', side='downstream', spec={'type': btype, 'value': value})

    def _get_initial_node_level(self, node):
        levels = []
        for edge_key, side, role in self._node_connected_edge_sides(node):
            payload = self._rpc(edge_key, 'GET_REAL_LEVELS')
            levels.append(payload['real_levels'][side])
        return float(np.mean(levels)) if levels else 0.0

    def _solve_internal_boundaries(self):
        for node in self.internal_nodes:
            node_level = self._get_initial_node_level(node)
            if node_level < 0:
                node_level = 0.0
            for _ in range(self.max_iteration):
                summaries = []
                for edge_key, side, role in self._node_connected_edge_sides(node):
                    payload = self._rpc(edge_key, 'APPLY_BOUNDARY', side=side, spec={'type': 'fix_level', 'value': node_level})
                    summaries.append((role, payload['ghost_summary']))
                ac = 0.0
                pure_Q = 0.0
                for role, s in summaries:
                    A = max(float(s['A']), 1e-8)
                    B = max(float(s['B']), 1e-8)
                    Q = float(s['Q'])
                    if role == 'in':
                        ac += (np.sqrt(self.g * A * B) - Q * B / A)
                        pure_Q += Q
                    else:
                        ac += (np.sqrt(self.g * A * B) + Q * B / A)
                        pure_Q -= Q
                ac *= self.g
                dz = pure_Q / ac if abs(ac) > 1e-12 else 0.0
                node_level += dz
                if node_level < 0:
                    node_level = 0.0
                if node_level != 0:
                    cond = (abs(dz / node_level) < 1e-5) and (abs(pure_Q) < self.JPWSPC_Q_limit)
                else:
                    cond = abs(pure_Q) < self.JPWSPC_Q_limit
                if cond:
                    break
            self.node_levels[node] = node_level

    def step_once(self, dt):
        self._apply_external_boundaries()
        self._solve_internal_boundaries()
        next_dts = []
        for edge_key in self.topology:
            payload = self._rpc(edge_key, 'ADVANCE', dt=dt, save_result=True)
            next_dts.append(payload['next_dt'])
        self.current_sim_time += dt
        self.step_count += 1
        return max(1e-5, min(next_dts))

    def Evolve(self, yield_step=None):
        if yield_step is None:
            yield_step = self.model_data['time_step']
        self.initialize()
        dt = float(self.model_data.get('time_step', 1.0))
        dt = max(dt, 1e-5)
        sub_time = 0.0
        try:
            while self.current_sim_time < self.total_sim_time - 1e-12:
                dt = min(dt, self.total_sim_time - self.current_sim_time)
                dt = self.step_once(dt)
                sub_time += min(dt, self.total_sim_time - self.current_sim_time)
                if self.current_sim_time - self.report_time >= yield_step - 1e-12 or self.current_sim_time >= self.total_sim_time - 1e-12:
                    self.report_time = self.current_sim_time
                    yield self.current_sim_time
        finally:
            self.stop(finalize=True)


# Backward-compatible alias for the new process-based engine.
RiverNetMP = RivernetMP


def _build_demo_topology(output_path='result_mp'):
    river_data = {
        'cell_num': 120,
        'pos': [[1, 1, 0], [400, 1, 0], [800, 1, 0], [1200, 1, 0]],
        'section_name': ['se1', 'se2', 'se3']
    }
    section_data = {
        'se1': [[0, 12], [0.5, 0], [1, 0], [1.5, 12]],
        'se2': [[0, 12], [0.5, 0], [1, 0], [1.5, 12]],
        'se3': [[0, 12], [0.5, 0], [1, 0], [1.5, 12]],
    }
    model_data = {
        'model_name': 'river_net',
        'sim_start_time': '2024-01-01 00:00:00',
        'sim_end_time': '2024-01-01 01:30:00',
        'time_step': 5,
        'output_path': output_path,
        'CFL': 0.3,
    }
    section_pos = None
    top = {
        ('n1', 'n5'): {'name': 'river1', 'river_data': river_data, 'section_data': section_data, 'model_data': model_data, 'section_pos': section_pos, 'manning': 0.1},
        ('n2', 'n5'): {'name': 'river2', 'river_data': river_data, 'section_data': section_data, 'model_data': model_data, 'section_pos': section_pos, 'manning': 0.1},
        ('n3', 'n6'): {'name': 'river3', 'river_data': river_data, 'section_data': section_data, 'model_data': model_data, 'section_pos': section_pos, 'manning': 0.1},
        ('n4', 'n6'): {'name': 'river4', 'river_data': river_data, 'section_data': section_data, 'model_data': model_data, 'section_pos': section_pos, 'manning': 0.1},
        ('n5', 'n6'): {'name': 'river5', 'river_data': river_data, 'section_data': section_data, 'model_data': model_data, 'section_pos': section_pos, 'manning': 0.1},
        ('n7', 'n8'): {'name': 'river8', 'river_data': river_data, 'section_data': section_data, 'model_data': model_data, 'section_pos': section_pos, 'manning': 0.1},
        ('n5', 'n7'): {'name': 'river6', 'river_data': river_data, 'section_data': section_data, 'model_data': model_data, 'section_pos': section_pos, 'manning': 0.1},
        ('n6', 'n8'): {'name': 'river7', 'river_data': river_data, 'section_data': section_data, 'model_data': model_data, 'section_pos': section_pos, 'manning': 0.1},
        ('n7', 'n9'): {'name': 'river9', 'river_data': river_data, 'section_data': section_data, 'model_data': model_data, 'section_pos': section_pos, 'manning': 0.1},
        ('n9', 'n10'): {'name': 'river10', 'river_data': river_data, 'section_data': section_data, 'model_data': model_data, 'section_pos': section_pos, 'manning': 0.1},
    }
    return top, model_data


def _run_demo_mp():
    top, model_data = _build_demo_topology()
    net = RivernetMP(top, model_data, verbos=False, fine=False, init_level=2.0)
    net.set_boundary('n1', 'flow', 1)
    net.set_boundary('n2', 'flow', 2)
    net.set_boundary('n3', 'flow', 2)
    net.set_boundary('n4', 'flow', 2)
    net.set_boundary('n10', 'free')
    for t in net.Evolve(yield_step=300):
        td = datetime.timedelta(seconds=float(t))
        print(f'[MP] 当前模拟时间: {td}, step_count={net.step_count}')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='River network solver (single-file, multiprocessing capable).')
    parser.add_argument('--engine', choices=['mp'], default='mp', help='Execution engine. Current default: mp')
    parser.add_argument('--demo', action='store_true', help='Run built-in demo topology.')
    args = parser.parse_args()

    if args.demo:
        if args.engine == 'mp':
            _run_demo_mp()


# =========================
# Optimized process-pool patch
# - fuse per-river step into one process task
# - avoid saving xarray snapshots at every CFL substep by default
# =========================

def _parallel_call_river_step(river, save_result=False):
    river.Caculate_face_U_C()
    river.Caculate_Roe_matrix()
    river.Caculate_source_term_2()
    river.Caculate_Roe_Flux_2()
    river.Assemble_Flux_2()
    river.Update_cell_proprity2()
    if save_result:
        river.Save_result_per_time_step()
    return river


def _patch_rivernet_process_optimized():
    def _parallel_step_net(self, save_result=False):
        river_edges = [(u, v, data['river']) for u, v, data in self.G.edges(data=True) if data.get('river') is not None]
        if not getattr(self, '_parallel_enabled', False):
            for _, _, r in river_edges:
                _parallel_call_river_step(r, save_result=save_result)
            return

        # thread mode still uses per-river fused step to reduce scheduler overhead
        if getattr(self, 'parallel_mode', 'thread') == 'process':
            futures = [self._pool.submit(_parallel_call_river_step, r, save_result) for _, _, r in river_edges]
            updated = [f.result() for f in futures]
            for (u, v, _), river in zip(river_edges, updated):
                self.G.edges[(u, v)]['river'] = river
        else:
            futures = [self._pool.submit(_parallel_call_river_step, r, save_result) for _, _, r in river_edges]
            for f in futures:
                f.result()

    def _evolve_base_optimized(self, yield_step):
        yield_flag = False
        finish_flag = False
        self.sub_step_start_time = time.time()
        self.caculation_start_time = time.time()
        save_every_substep = bool(getattr(self, 'save_every_substep', self.model_data.get('save_every_substep', False)))
        while self.current_sim_time < self.total_sim_time:
            self.Set_global_time_step(self.DT)
            self.current_sim_time += self.DT
            self.step_count += 1
            self.sub_step_time += self.DT
            self.sub_step_count += 1
            self.sub_step_max_dt = max(self.sub_step_max_dt, self.DT)
            self.sub_step_min_dt = min(self.sub_step_min_dt, self.DT)
            self.Update_boundary_conditions()

            # For process mode, run the full per-river step in one submission.
            if getattr(self, 'parallel_mode', 'thread') == 'process' and getattr(self, '_parallel_enabled', False):
                should_save = save_every_substep
                self._parallel_step_net(save_result=should_save)
            else:
                self.Caculate_face_U_C_net()
                self.Caculate_Roe_matrix_net()
                self.Caculate_Source_term_net()
                self.Caculate_Roe_flux_net()
                self.Assemble_flux_net()
                self.Update_cell_property_net()
                if save_every_substep:
                    self.Save_step_result_net()

            # decide next dt
            self.Caculate_global_CFL()
            if self.current_sim_time + self.cfl_allowed_dt > self.total_sim_time + 1e-5:
                self.DT = self.total_sim_time - self.current_sim_time
                finish_flag = True
            elif self.sub_step_time + self.cfl_allowed_dt > yield_step + 1e-5:
                self.DT = yield_step - self.sub_step_time
                yield_flag = True
            else:
                self.DT = self.cfl_allowed_dt

            # save once per report interval instead of each CFL substep
            if yield_flag or finish_flag:
                if not save_every_substep:
                    self.Save_step_result_net()
                self.sub_step_caculation_time_using = time.time() - self.sub_step_start_time
                yield self.current_sim_time
                yield_flag = False
                self.sub_step_start_time = time.time()
                self.sub_step_time = 0.0
                self.sub_step_count = 0
                self.sub_step_max_dt = 0.0
                self.sub_step_min_dt = 999999

            if finish_flag:
                break

        self.caculation_time = time.time() - self.caculation_start_time
        print(f'计算结束，保存结果...\n共计算 {self.step_count} 步，总耗时: {self.caculation_time:.2f} 秒', flush=True)
        self.Resample_and_Save_result_net()

    Rivernet._parallel_step_net = _parallel_step_net
    Rivernet._evolve_base = _evolve_base_optimized

    class RivernetProcessPoolOptimized(Rivernet):
        def __init__(self, Topology, model_data, verbos=True, process_workers=None, save_every_substep=False):
            model_data = dict(model_data)
            if process_workers is not None:
                model_data['parallel_workers'] = int(process_workers)
            model_data['parallel_mode'] = 'process'
            model_data.setdefault('save_every_substep', save_every_substep)
            super().__init__(Topology, model_data, verbos=verbos,
                             parallel_workers=model_data.get('parallel_workers', 0),
                             parallel_mode='process')
            self.save_every_substep = bool(model_data.get('save_every_substep', save_every_substep))

    globals()['RivernetProcessPoolOptimized'] = RivernetProcessPoolOptimized
    globals()['RiverNetProcessPoolOptimized'] = RivernetProcessPoolOptimized


try:
    _patch_rivernet_process_optimized()
except Exception as _e:
    print('[WARN] Optimized process patch failed:', _e, flush=True)
