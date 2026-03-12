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
matplotlib.use('Agg')
matplotlib.use('TkAgg')
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
        self.save_with_ghost = False
        self.bc_use_order2_extrap = False
        self.bc_use_order2_extrap_flow = False
        self.bc_use_order2_extrap_stage = False
        self.bc_stage_on_face = False
        self.bc_use_general_chi = False
        self.refined_section_table = False
        # 调试统计：固定水位边界因超临界触发“外推”次数
        self.debug_supercritical_in_count = 0
        self.debug_supercritical_out_count = 0
        # 特征线边界源项修正（JPWSPC/FullSWOF 的 S0-Sf 近似）
        self.bc_moc_with_source = False
        self.bc_moc_with_source_flow = False
        self.bc_moc_with_source_stage = False
        self.bc_moc_source_scale = 1.0
        # 断面特征势函数 χ(A)=∫(c/A)dA 的缓存（按 section 名称）
        self._char_potential_cache = {}

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
        # 右侧 ghost 必须追加到末尾，不能插在“倒数第二个位置”
        self.cell_sections.append(self.cell_sections[-1])
        self.cell_pos = np.insert(self.cell_pos, 0, self.cell_pos[0], axis=0)
        self.cell_pos = np.insert(self.cell_pos, self.cell_pos.shape[0], self.cell_pos[-1], axis=0)
        self.cell_lengths = np.insert(self.cell_lengths, 0, self.cell_lengths[0], axis=0)
        self.cell_lengths = np.insert(self.cell_lengths, self.cell_lengths.shape[0], self.cell_lengths[-1], axis=0)
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
            self.P[i] = self.cross_section_table.get_wetted_perimeter_by_area(section_name, self.S[i])

            # 基于过水断面面积查找水压力
            self.PRESS[i] = self.cross_section_table.get_press_by_area(section_name, self.S[i])

            # 基于过水断面面积查找水力半径
            self.R[i] = self.cross_section_table.get_hydraulic_radius_by_area(section_name, self.S[i])

            # 压力分布
            self.BETA[i] = 1

            # 计算网格坡度
            # 说明：最后一个真实单元(i==cell_num)的下一个点是右侧ghost，不可再用前向差分，
            # 必须改为后向差分；否则会把末端真实单元坡度错误压成接近0。
            if i >= self.cell_num:
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
        # 每步重置 LeVeque 标志，避免历史步残留状态影响当前界面分流
        self.flag_LeVeque[:N] = 0

        # ——— 2. 计算 Z, Lambda1, Lambda2 ———
        #   Z = sqrt(Roe_C² - BETA*(1-BETA)*Roe_U²) + eps
        tmp = BETA_arr * (1 - BETA_arr) * Roe_U ** 2
        Z = np.sqrt(np.maximum(Roe_C ** 2 - tmp, 0))
        Z_safe = Z + self.EPSILON
        Lambda1 = BETA_arr * Roe_U - Z
        Lambda2 = BETA_arr * Roe_U + Z

        # ——— 3. LeVeque 修正掩码 ———
        FR_L = self.FR[:N]
        FR_R = self.FR[1:N + 1]
        depth_L = self.water_depth[:N]
        depth_R = self.water_depth[1:N + 1]

        # 右侧单元为空以及两侧均有水的情况
        indic = (depth_L > self.water_depth_limit) & (depth_R > self.water_depth_limit)

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
        self.Vactor1_T[:N, 0] = (Beta_U + Z) / (2 * Z_safe)
        self.Vactor1_T[:N, 1] = -1 / (2 * Z_safe)
        # Vactor2
        self.Vactor2[:N, 0] = 1
        self.Vactor2[:N, 1] = Beta_U + Z
        # Vactor2_T
        self.Vactor2_T[:N, 0] = -(Beta_U - Z) / (2 * Z_safe)
        self.Vactor2_T[:N, 1] = 1 / (2 * Z_safe)

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
        # 真实计算单元是 [1, cell_num]，对应切片 [1:-1]
        self.S_old[1:-1] = self.S[1:-1].copy()
        self.Q_old[1:-1] = self.Q[1:-1].copy()

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
        # 默认只保存中间网格；调试时可切换为包含两侧虚拟网格
        if self.save_with_ghost:
            sl = slice(0, self.cell_num + 2)
        else:
            sl = slice(1, self.cell_num + 1)

        depth = self.water_depth[sl].copy()
        level = self.water_level[sl].copy()
        U = self.U[sl].copy()
        Q = self.Q[sl].copy()

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

        # 默认只保存中间网格；调试时可切换为包含两侧虚拟网格
        if self.save_with_ghost:
            sl = slice(0, self.cell_num + 2)
            space = np.arange(self.cell_num + 2)
        else:
            sl = slice(1, self.cell_num + 1)
            space = np.arange(self.cell_num)

        x = self.cell_pos[sl, 0]
        y = self.cell_pos[sl, 1]
        z = self.cell_pos[sl, 2]

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
    def _refresh_cell_state(self, idx, level_hint=None):
        """
        边界写入 S/Q 后，同步刷新该单元的派生水力量，避免后续 Roe 通量使用陈旧 U/C/PRESS。
        """
        sec = self.cell_sections[idx]
        S = float(max(self.S[idx], 0.0))
        self.S[idx] = S

        if level_hint is None:
            level = float(self.cross_section_table.get_level_by_area(sec, S))
        else:
            level = float(level_hint)
        self.water_level[idx] = level
        self.water_depth[idx] = max(level - float(self.river_bed_height[idx]), 0.0)

        if S <= self.S_limit:
            self.U[idx] = 0.0
            self.C[idx] = self.EPSILON
            self.FR[idx] = 0.0
        else:
            self.U[idx] = float(self.Q[idx]) / S
            width = float(self.cross_section_table.get_width_by_area(sec, S))
            if width < self.EPSILON:
                width = max(S / max(self.water_depth[idx], self.water_depth_limit), self.EPSILON)
            self.C[idx] = np.sqrt(self.g * S / width)
            self.FR[idx] = np.abs(self.U[idx]) / max(self.C[idx], self.EPSILON)

        self.P[idx] = float(self.cross_section_table.get_wetted_perimeter_by_area(sec, S))
        self.PRESS[idx] = float(self.cross_section_table.get_press_by_area(sec, S))
        self.R[idx] = float(self.cross_section_table.get_hydraulic_radius_by_area(sec, S))

    def InBound_In_Q(self, Q):
        self.Q[0] = Q
        self.S[0] = self.S[0] + self.DT * (self.Q[0] - self.Q[1]) / self.cell_lengths[0]

        sec = self.cell_sections[0]
        self.water_depth[0] = self.cross_section_table.get_depth_by_area(sec, self.S[0])
        width = float(self.cross_section_table.get_width_by_area(sec, max(self.S[0], 1e-12)))
        width = max(width, 1e-8)
        self.C[0] = np.sqrt(self.g * max(self.S[0], 1e-12) / width)
        self.FR[0] = np.abs(self.Q[0]) / max(self.C[0] * self.S[0], 1e-12)

        if self.FR[0] > 0.99:
            q_cap = 0.99 * self.C[0] * self.S[0]
            Q = float(np.sign(Q) * min(abs(Q), q_cap))
        self.Q[0] = Q
        self._refresh_cell_state(0)

        # 隐式边界
        if self.Implic_flag:
            self.V0[0] = self.S[0]- self.S_old[0]
            self.V0[1] = self.Q[0] - self.Q_old[0]

    def _moc_source_term(self, idx, kind='stage'):
        """
        近似计算边界特征线的源项修正：g*(S0-Sf)。
        当 bc_moc_with_source=False 时返回 0，不影响原有结果。
        """
        use_global = bool(getattr(self, 'bc_moc_with_source', False))
        if kind == 'flow':
            use_local = bool(getattr(self, 'bc_moc_with_source_flow', False))
        else:
            use_local = bool(getattr(self, 'bc_moc_with_source_stage', False))
        if not (use_global or use_local):
            return 0.0

        tinyA = 1e-12
        tinyR = 1e-8
        A = float(max(self.S[idx], tinyA))
        Q = float(self.Q[idx])
        R = float(max(self.R[idx], tinyR))
        n_val = float(self.n[idx]) if np.ndim(self.n) else float(self.n)
        sf = (n_val * n_val * Q * abs(Q)) / (A * A * (R ** (4.0 / 3.0)) + 1e-12)
        s0 = float(self.Slop[idx])
        scale = float(getattr(self, 'bc_moc_source_scale', 1.0))
        return float(self.g * (s0 - sf) * scale)

    def _build_char_potential_cache(self, section_name):
        """
        构建一般断面的特征势函数 χ(A)=∫(c/A)dA，其中 c=sqrt(gA/T)。
        对矩形断面有 χ=2c；此实现对任意断面均可用。
        """
        tbl = self.cross_section_table.tables.get(section_name)
        if tbl is None:
            return None

        tinyA = 1e-12
        tinyT = 1e-8
        area_axis_raw = np.asarray(tbl._area_axis, dtype=float)
        if area_axis_raw.size == 0:
            return None
        area_axis = np.unique(area_axis_raw[np.isfinite(area_axis_raw)])
        area_axis = area_axis[area_axis > tinyA]
        if area_axis.size == 0:
            return None

        width_axis = np.asarray([tbl.get_width_by_area(a) for a in area_axis], dtype=float)
        width_axis = np.maximum(width_axis, tinyT)
        integrand = np.sqrt(self.g * area_axis / width_axis) / np.maximum(area_axis, tinyA)  # c/A

        chi_axis = np.zeros_like(area_axis)
        if area_axis.size > 1:
            chi_axis[1:] = np.cumsum(0.5 * (integrand[1:] + integrand[:-1]) * np.diff(area_axis))

        # A->0 的积分首段用局部矩形近似补偿，保证小流量区不出现零势能
        chi0 = 2.0 * np.sqrt(self.g * area_axis[0] / width_axis[0])
        chi_axis = chi_axis + chi0

        cache = {
            'A': area_axis,
            'chi': chi_axis,
            'A0': float(area_axis[0]),
            'Amax': float(area_axis[-1]),
            'w0': float(width_axis[0]),
            'chi_max': float(chi_axis[-1]),
            'kmax': float(integrand[-1]),
        }
        self._char_potential_cache[section_name] = cache
        return cache

    def _char_potential(self, section_name, area):
        """
        返回 χ(A)=∫(c/A)dA。用于一般断面特征线边界条件。
        """
        tinyA = 1e-12
        tinyT = 1e-8
        A = float(max(area, tinyA))

        if not bool(getattr(self, 'bc_use_general_chi', False)):
            T = float(self.cross_section_table.get_width_by_area(section_name, A))
            T = max(T, tinyT)
            return float(2.0 * np.sqrt(self.g * A / T))

        cache = self._char_potential_cache.get(section_name)
        if cache is None:
            cache = self._build_char_potential_cache(section_name)
        if cache is None:
            # 兜底：退化为局部矩形近似 χ≈2c
            T = float(self.cross_section_table.get_width_by_area(section_name, A))
            T = max(T, tinyT)
            return float(2.0 * np.sqrt(self.g * A / T))

        if A <= cache['A0']:
            return float(2.0 * np.sqrt(self.g * A / max(cache['w0'], tinyT)))
        if A >= cache['Amax']:
            return float(cache['chi_max'] + cache['kmax'] * (A - cache['Amax']))
        return float(np.interp(A, cache['A'], cache['chi']))

    def InBound_In_Q2(self, Q_in):
        """
        上游给定流量 Q_in，利用离域负特征不变量恢复面积 S[0]（一般断面）。
        注：一般断面采用 χ(A)=∫(c/A)dA，不再使用仅对矩形严格成立的 2c。
        """
        tinyA = 1e-12
        sec_in = self.cell_sections[1]
        sec_b = self.cell_sections[0]
        dt_moc = float(getattr(self, 'DT', 0.0))

        # 1) 相邻实格状态（可选二阶外推不变量）
        S1 = float(max(self.S[1], self.S_limit, tinyA))
        Q1 = float(self.Q[1])
        u1 = Q1 / S1
        chi1 = self._char_potential(sec_in, S1)
        src1 = self._moc_source_term(1, kind='flow')
        swap_moc_sign = bool(getattr(self, 'swap_moc_sign_flow', getattr(self, 'swap_moc_sign', False)))
        use_o2 = bool(
            getattr(
                self,
                'bc_use_order2_extrap_flow',
                getattr(self, 'bc_use_order2_extrap', False)
            )
        ) and (self.cell_num >= 3)
        if use_o2:
            S2 = float(max(self.S[2], self.S_limit, tinyA))
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
            # 备用模式：使用 J+ 不变量（用于符号核查）
            f_plus = 2.0 * f_plus_1 - f_plus_2 if use_o2 else f_plus_1
        else:
            f_minus = 2.0 * f_minus_1 - f_minus_2 if use_o2 else f_minus_1

        # 2) 给定边界流量，解边界面积
        Qb = float(Q_in)
        Sb = float(max(S1, self.S_limit))

        for _ in range(12):
            ub = Qb / max(Sb, tinyA)
            chi_b = self._char_potential(sec_b, Sb)
            if swap_moc_sign:
                F = ub + chi_b - f_plus
            else:
                F = ub - chi_b - f_minus

            dS = max(1e-6, 1e-4 * Sb)
            Sp = max(Sb + dS, self.S_limit)
            chi_p = self._char_potential(sec_b, Sp)
            if swap_moc_sign:
                Fp = (Qb / max(Sp, tinyA)) + chi_p - f_plus
            else:
                Fp = (Qb / max(Sp, tinyA)) - chi_p - f_minus
            dF = (Fp - F) / (Sp - Sb)

            if abs(dF) < 1e-10:
                break

            step = F / dF
            step = float(np.clip(step, -0.5 * Sb, 0.5 * Sb))
            Sb_new = max(Sb - step, self.S_limit)

            if abs(Sb_new - Sb) / max(Sb, 1e-6) < 1e-6:
                Sb = Sb_new
                break
            Sb = Sb_new

        # 3) 更新边界状态
        self.S[0] = float(Sb)
        self.Q[0] = float(Qb)
        self._refresh_cell_state(0)

        # 如果用隐式格式，还要更新源项增量 V0（左边界）
        if self.Implic_flag:
            self.V0[0] = self.S[0] - self.S_old[0]
            self.V0[1] = self.Q[0] - self.Q_old[0]

    def InBound_In_Q_re(self, Q):
        self.S[-1] = self.S[-1] + self.DT * (self.Q[-1] - self.Q[-2]) / self.cell_lengths[-1]

        sec = self.cell_sections[-1]
        width = float(self.cross_section_table.get_width_by_area(sec, max(self.S[-1], 1e-12)))
        width = max(width, 1e-8)
        c = np.sqrt(self.g * max(self.S[-1], 1e-12) / width)
        fr = abs(Q) / max(c * self.S[-1], 1e-12)
        if fr > 0.99:
            Q = float(np.sign(Q) * min(abs(Q), 0.99 * c * self.S[-1]))
        self.Q[-1] = Q
        self._refresh_cell_state(-1)

    '''自由出流边界'''
    def OutBound_Free_Outfall(self):
        self.Q[-1] = self.Q[-2]
        self.S[-1] = self.S[-2]
        self._refresh_cell_state(-1)

    def OutBound_Free_Outfall_re(self):
        self.Q[0] = self.Q[1]
        self.S[0] = self.S[1]
        self._refresh_cell_state(0)

    '''固定水位出流边界'''
    def OutBound_Fix_level(self, level):
        section_name = self.cell_sections[-1]

        # 一般断面：J+ = u + χ(A), χ(A)=∫(c/A)dA
        Ai = max(float(self.S[-2]), 1e-12)
        ui = self.Q[-2] / Ai
        chi_i = self._char_potential(self.cell_sections[-2], Ai)

        Ab = float(self.cross_section_table.get_area_by_level(section_name, level))
        Ab = max(Ab, 1e-12)
        chi_b = self._char_potential(section_name, Ab)

        # J+ 守恒
        ub = (ui + chi_i) - chi_b
        Q = Ab * ub

        self.S[-1] = Ab
        self.Q[-1] = Q
        self._refresh_cell_state(-1, level_hint=level)

        if self.Implic_flag:
            self.V1[0] = self.S[-1] - self.S_old[-1]
            self.V1[1] = self.Q[-1] - self.Q_old[-1]

    '''固定水位的入流边界'''
    def InBound_Fix_level(self, level):
        section_name = self.cell_sections[0]
        # 一般断面：J- = u - χ(A), χ(A)=∫(c/A)dA
        Ai = max(float(self.S[1]), 1e-12)
        ui = self.Q[1] / Ai
        chi_i = self._char_potential(self.cell_sections[1], Ai)

        Ab = float(self.cross_section_table.get_area_by_level(section_name, level))
        Ab = max(Ab, 1e-12)
        chi_b = self._char_potential(section_name, Ab)

        # J- 守恒
        ub = (ui - chi_i) + chi_b
        Qb = Ab * ub

        # 6) 设置边界值
        self.S[0] = Ab
        self.Q[0] = Qb
        self._refresh_cell_state(0, level_hint=level)

        # 7) 如果是隐式格式，更新 V1 用于源项增量
        if self.Implic_flag:
            self.V0[0] = self.S[0] - self.S_old[0]
            self.V0[1] = self.Q[0] - self.Q_old[0]

    def InBound_Fix_level_V2(self, level,
                             Fr_max=0.85, head_gain_factor=0.65,
                             relax_Q=0.4, cap_du_factor=0.8, cap_dQ_factor=0.7):
        """
        左端（上游）固定水位边界（允许倒流，适用于一般断面）：
        - 用一般断面 c = sqrt(g*A/T)
        - 负特征不变量 J- = u - χ(A) 从相邻实格(索引1)传到边界
        - 加稳健项：Fr 限幅、水头增益限速、Δu/ΔQ 限幅、欠松弛
        """
        # 1) 相邻实格
        Ai = float(self.S[1])
        Ti = float(self.cross_section_table.get_width_by_area(self.cell_sections[1], Ai))
        Ti = max(Ti, 1e-8)
        ui = float(self.Q[1]) / max(Ai, 1e-12)
        ci = (self.g * Ai / Ti) ** 0.5
        chi_i = self._char_potential(self.cell_sections[1], Ai)

        # 2) 已知水位 -> 边界 A,T,c
        sec_b = self.cell_sections[0]
        Ab = float(self.cross_section_table.get_area_by_level(sec_b, level))
        Tb = float(self.cross_section_table.get_width_by_area(sec_b, Ab))
        Tb = max(Tb, 1e-8)
        cb = (self.g * Ab / Tb) ** 0.5
        chi_b = self._char_potential(sec_b, Ab)

        # 3) J- 守恒
        ub = (ui - chi_i) + chi_b

        # 4) Fr 限幅
        Frb = abs(ub) / max(cb, 1e-8)
        if Frb > Fr_max:
            ub = (ub / max(abs(ub), 1e-12)) * Fr_max * cb

        # 5) 水头增益限速（上游：ΔH = level - Hi）
        Hi = float(self.water_level[1])
        dH = level - Hi
        if dH >= 0.0:
            u_head = (2.0 * self.g * dH) ** 0.5
            ub = (ub / max(abs(ub), 1e-12)) * min(abs(ub), head_gain_factor * u_head)

        # 6) Δu 限幅（相对相邻实格）
        ub = max(ui - cap_du_factor * ci, min(ui + cap_du_factor * ci, ub))

        # 7) 计算原始流量并做 ΔQ 限幅 + 欠松弛
        Qb_raw = ub * Ab
        cap_dQ = cap_dQ_factor * Ai * ci
        Qb_raw = max(self.Q[1] - cap_dQ, min(self.Q[1] + cap_dQ, Qb_raw))

        prev = getattr(self, 'prev_Qb_left', None)
        if prev is None:
            prev = Qb_raw
        Qb = prev + relax_Q * (Qb_raw - prev)
        self.prev_Qb_left = Qb

        # 8) 写回鬼格
        self.S[0] = Ab
        self.Q[0] = Qb
        self._refresh_cell_state(0, level_hint=level)

        # 9) 隐式格式增量（如果需要）
        if getattr(self, 'Implic_flag', False):
            self.V0[0] = self.S[0] - self.S_old[0]
            self.V0[1] = self.Q[0] - self.Q_old[0]


    def OutBound_Fix_level_V2(self, level,
                              Fr_max=0.85, head_gain_factor=0.65,
                              relax_Q=0.4, cap_du_factor=0.8, cap_dQ_factor=0.7):
        """
        右端（下游）固定水位边界（允许倒流，适用于一般断面）：
        - 正特征不变量 J+ = u + χ(A) 从相邻实格(索引-2)传到边界
        - 稳健项同上游对称，但水头差取 ΔH = Hi - level
        """
        # 1) 相邻实格
        Ai = float(self.S[-2])
        Ti = float(self.cross_section_table.get_width_by_area(self.cell_sections[-2], Ai))
        Ti = max(Ti, 1e-8)
        ui = float(self.Q[-2]) / max(Ai, 1e-12)
        ci = (self.g * Ai / Ti) ** 0.5
        chi_i = self._char_potential(self.cell_sections[-2], Ai)

        # 2) 已知水位 -> 边界 A,T,c
        sec_b = self.cell_sections[-1]
        Ab = float(self.cross_section_table.get_area_by_level(sec_b, level))
        Tb = float(self.cross_section_table.get_width_by_area(sec_b, Ab))
        Tb = max(Tb, 1e-8)
        cb = (self.g * Ab / Tb) ** 0.5
        chi_b = self._char_potential(sec_b, Ab)

        # 3) J+ 守恒
        ub = (ui + chi_i) - chi_b

        # 4) Fr 限幅
        Frb = abs(ub) / max(cb, 1e-8)
        if Frb > Fr_max:
            ub = (ub / max(abs(ub), 1e-12)) * Fr_max * cb

        # 5) 水头增益限速（下游：ΔH = Hi - level）
        Hi = float(self.water_level[-2])
        dH = Hi - level
        if dH >= 0.0:
            u_head = (2.0 * self.g * dH) ** 0.5
            ub = (ub / max(abs(ub), 1e-12)) * min(abs(ub), head_gain_factor * u_head)

        # 6) Δu 限幅
        ub = max(ui - cap_du_factor * ci, min(ui + cap_du_factor * ci, ub))

        # 7) ΔQ 限幅 + 欠松弛
        Qb_raw = ub * Ab
        cap_dQ = cap_dQ_factor * Ai * ci
        Qb_raw = max(self.Q[-2] - cap_dQ, min(self.Q[-2] + cap_dQ, Qb_raw))

        prev = getattr(self, 'prev_Qb_right', None)
        if prev is None:
            prev = Qb_raw
        Qb = prev + relax_Q * (Qb_raw - prev)
        self.prev_Qb_right = Qb

        # 8) 写回鬼格
        self.S[-1] = Ab
        self.Q[-1] = Qb
        self._refresh_cell_state(-1, level_hint=level)

        if getattr(self, 'Implic_flag', False):
            self.V1[0] = self.S[-1] - self.S_old[-1]
            self.V1[1] = self.Q[-1] - self.Q_old[-1]

    def InBound_Fix_level_V3(self, level,
                             Fr_max=0.85, head_gain_factor=0.65,
                             relax_Q=0.4, cap_du_factor=0.8, cap_dQ_factor=0.7,
                             use_stabilizers=True, respect_supercritical=True,
                             stage_on_face=None):
        """
        上游（左端）固定水位边界（FullSWOF-1D：Imposed stage + modified MOC）
        - 主体计算：保持 J- = u - χ(A)（离域特征）常值，先得 u_b，再得 Q_b = A_b*u_b
        - 一般断面声速：c = sqrt(g*A/T)
        - 可选稳健项（默认开启）：Fr 限幅、水头增益限速、Δu/ΔQ 限幅、欠松弛
        """
        g = getattr(self, 'g', 9.81)
        tinyA, tinyT, tinyC = 1e-12, 1e-8, 1e-8
        if stage_on_face is None:
            stage_on_face = bool(getattr(self, 'bc_stage_on_face', False))
        if stage_on_face:
            # 以边界界面为Dirichlet点：用线性外推将“目标界面水位”换算为ghost中心水位
            level = 2.0 * float(level) - float(self.water_level[1])

        # 1) 相邻实格(索引1)的几何/动力量
        Ai = float(self.S[1])
        Ti = float(self.cross_section_table.get_width_by_area(self.cell_sections[1], Ai))
        Ti = max(Ti, tinyT)
        ui = float(self.Q[1]) / max(Ai, tinyA)
        ci = (g * Ai / Ti) ** 0.5
        chi1 = self._char_potential(self.cell_sections[1], Ai)
        dt_moc = float(getattr(self, 'DT', 0.0))
        src1 = self._moc_source_term(1, kind='stage')
        use_o2 = bool(
            getattr(
                self,
                'bc_use_order2_extrap_stage',
                getattr(self, 'bc_use_order2_extrap', False)
            )
        ) and (self.cell_num >= 3)
        if use_o2:
            A2 = float(max(self.S[2], tinyA))
            T2 = float(self.cross_section_table.get_width_by_area(self.cell_sections[2], A2))
            T2 = max(T2, tinyT)
            u2 = float(self.Q[2]) / A2
            c2 = (g * A2 / T2) ** 0.5
            chi2 = self._char_potential(self.cell_sections[2], A2)
            src2 = self._moc_source_term(2, kind='stage')

        # 超临界（|u|>=c）时，单一水位边界不再适定，按 FullSWOF 思路改为外推。
        if respect_supercritical and (abs(ui) >= ci):
            self.debug_supercritical_in_count += 1
            self.S[0] = self.S[1]
            self.Q[0] = self.Q[1]
            self.water_level[0] = self.water_level[1]
            self._refresh_cell_state(0, level_hint=self.water_level[0])
            if getattr(self, 'Implic_flag', False):
                self.V0[0] = self.S[0] - self.S_old[0]
                self.V0[1] = self.Q[0] - self.Q_old[0]
            return

        # 2) 由给定水位 level 得到边界 A_b, T_b, c_b
        sec_b = self.cell_sections[0]
        Ab = float(self.cross_section_table.get_area_by_level(sec_b, level))
        if Ab <= 0.0:
            # 干边界：直接置 0，写回并返回
            self.S[0] = 0.0; self.Q[0] = 0.0; self.water_level[0] = level
            self._refresh_cell_state(0, level_hint=level)
            if getattr(self, 'Implic_flag', False):
                self.V0[0] = self.S[0] - self.S_old[0]
                self.V0[1] = self.Q[0] - self.Q_old[0]
            return

        Tb = float(self.cross_section_table.get_width_by_area(sec_b, Ab))
        Tb = max(Tb, tinyT)
        cb = (g * Ab / Tb) ** 0.5
        chi_b = self._char_potential(sec_b, Ab)

        # 3) FullSWOF-MOC：保持 J- 守恒 → u_b^MOC
        swap_moc_sign = bool(
            getattr(
                self,
                'swap_moc_sign_stage_in',
                getattr(self, 'swap_moc_sign_stage', getattr(self, 'swap_moc_sign', False))
            )
        )
        if swap_moc_sign:
            # 备用模式：使用 J+ 进行上游固定水位恢复（用于符号核查）
            if use_o2:
                jp = 2.0 * (ui + chi1 + src1 * dt_moc) - (u2 + chi2 + src2 * dt_moc)
                ub = jp - chi_b
            else:
                ub = (ui + chi1 + src1 * dt_moc) - chi_b
        else:
            if use_o2:
                jm = 2.0 * (ui - chi1 + src1 * dt_moc) - (u2 - chi2 + src2 * dt_moc)
                ub = jm + chi_b
            else:
                ub = (ui - chi1 + src1 * dt_moc) + chi_b

        # 4) 稳健限幅（可关）
        if use_stabilizers:
            # (a) Fr 限幅
            Frb = abs(ub) / max(cb, tinyC)
            if Frb > Fr_max:
                ub = (ub / max(abs(ub), 1e-12)) * Fr_max * cb

            # (b) 水头增益限速（上游：ΔH = level - H_i）
            Hi = float(self.water_level[1])
            dH = level - Hi
            if dH >= 0.0:
                u_head = (2.0 * g * dH) ** 0.5
                ub = (ub / max(abs(ub), 1e-12)) * min(abs(ub), head_gain_factor * u_head)

            # (c) Δu 限幅（以相邻实格为中心）
            ub = max(ui - cap_du_factor * ci, min(ui + cap_du_factor * ci, ub))

        # 5) 计算 Q_b 并做 ΔQ 限幅 + 欠松弛（可关）
        Qb_raw = ub * Ab
        if use_stabilizers:
            cap_dQ = cap_dQ_factor * Ai * ci
            Qb_raw = max(self.Q[1] - cap_dQ, min(self.Q[1] + cap_dQ, Qb_raw))
            prev = getattr(self, 'prev_Qb_left', None)
            if prev is None: prev = Qb_raw
            Qb = prev + relax_Q * (Qb_raw - prev)
            self.prev_Qb_left = Qb
        else:
            Qb = Qb_raw

        # 6) 写回鬼格
        self.S[0] = Ab
        self.Q[0] = Qb
        self._refresh_cell_state(0, level_hint=level)

        # 7) 隐式增量（若启用）
        if getattr(self, 'Implic_flag', False):
            self.V0[0] = self.S[0] - self.S_old[0]
            self.V0[1] = self.Q[0] - self.Q_old[0]


    def OutBound_Fix_level_V3(self, level,
                              Fr_max=0.85, head_gain_factor=0.65,
                              relax_Q=0.4, cap_du_factor=0.8, cap_dQ_factor=0.7,
                              use_stabilizers=True, respect_supercritical=True,
                              stage_on_face=None):
        """
        下游（右端）固定水位边界（FullSWOF-1D：Imposed stage + modified MOC）
        - 主体计算：保持 J+ = u + χ(A)（离域特征）常值，先得 u_b，再得 Q_b = A_b*u_b
        - 一般断面声速：c = sqrt(g*A/T)
        - 可选稳健项（默认开启）：Fr 限幅、水头增益限速、Δu/ΔQ 限幅、欠松弛
        """
        g = getattr(self, 'g', 9.81)
        tinyA, tinyT, tinyC = 1e-12, 1e-8, 1e-8
        if stage_on_face is None:
            stage_on_face = bool(getattr(self, 'bc_stage_on_face', False))
        if stage_on_face:
            # 以边界界面为Dirichlet点：用线性外推将“目标界面水位”换算为ghost中心水位
            level = 2.0 * float(level) - float(self.water_level[-2])


        # 1) 相邻实格(索引-2)
        Ai = float(self.S[-2])
        Ti = float(self.cross_section_table.get_width_by_area(self.cell_sections[-2], Ai))
        Ti = max(Ti, tinyT)
        ui = float(self.Q[-2]) / max(Ai, tinyA)
        ci = (g * Ai / Ti) ** 0.5
        chi1 = self._char_potential(self.cell_sections[-2], Ai)
        dt_moc = float(getattr(self, 'DT', 0.0))
        src1 = self._moc_source_term(-2, kind='stage')
        use_o2 = bool(
            getattr(
                self,
                'bc_use_order2_extrap_stage',
                getattr(self, 'bc_use_order2_extrap', False)
            )
        ) and (self.cell_num >= 3)
        if use_o2:
            A2 = float(max(self.S[-3], tinyA))
            T2 = float(self.cross_section_table.get_width_by_area(self.cell_sections[-3], A2))
            T2 = max(T2, tinyT)
            u2 = float(self.Q[-3]) / A2
            c2 = (g * A2 / T2) ** 0.5
            chi2 = self._char_potential(self.cell_sections[-3], A2)
            src2 = self._moc_source_term(-3, kind='stage')

        # 超临界（|u|>=c）时，单一水位边界不再适定，按 FullSWOF 思路改为外推。
        if respect_supercritical and (abs(ui) >= ci):
            self.debug_supercritical_out_count += 1
            self.S[-1] = self.S[-2]
            self.Q[-1] = self.Q[-2]
            self.water_level[-1] = self.water_level[-2]
            self._refresh_cell_state(-1, level_hint=self.water_level[-1])
            if getattr(self, 'Implic_flag', False):
                self.V1[0] = self.S[-1] - self.S_old[-1]
                self.V1[1] = self.Q[-1] - self.Q_old[-1]
            return

        # 2) 由给定水位 level 得到边界 A_b, T_b, c_b
        sec_b = self.cell_sections[-1]
        Ab = float(self.cross_section_table.get_area_by_level(sec_b, level))
        if Ab <= 0.0:
            self.S[-1] = 0.0; self.Q[-1] = 0.0; self.water_level[-1] = level
            self._refresh_cell_state(-1, level_hint=level)
            if getattr(self, 'Implic_flag', False):
                self.V1[0] = self.S[-1] - self.S_old[-1]
                self.V1[1] = self.Q[-1] - self.Q_old[-1]
            return

        Tb = float(self.cross_section_table.get_width_by_area(sec_b, Ab))
        Tb = max(Tb, tinyT)
        cb = (g * Ab / Tb) ** 0.5
        chi_b = self._char_potential(sec_b, Ab)

        # 3) FullSWOF-MOC：保持 J+ 守恒 → u_b^MOC
        swap_moc_sign = bool(
            getattr(
                self,
                'swap_moc_sign_stage_out',
                getattr(self, 'swap_moc_sign_stage', getattr(self, 'swap_moc_sign', False))
            )
        )
        if swap_moc_sign:
            # 备用模式：使用 J- 进行下游固定水位恢复（用于符号核查）
            if use_o2:
                jm = 2.0 * (ui - chi1 + src1 * dt_moc) - (u2 - chi2 + src2 * dt_moc)
                ub = jm + chi_b
            else:
                ub = (ui - chi1 + src1 * dt_moc) + chi_b
        else:
            if use_o2:
                jp = 2.0 * (ui + chi1 + src1 * dt_moc) - (u2 + chi2 + src2 * dt_moc)
                ub = jp - chi_b
            else:
                ub = (ui + chi1 + src1 * dt_moc) - chi_b

        # 4) 稳健限幅（可关）
        if use_stabilizers:
            # (a) Fr 限幅
            Frb = abs(ub) / max(cb, tinyC)
            if Frb > Fr_max:
                ub = (ub / max(abs(ub), 1e-12)) * Fr_max * cb

            # (b) 水头增益限速（下游：ΔH = H_i - level）
            Hi = float(self.water_level[-2])
            dH = Hi - level
            if dH >= 0.0:
                u_head = (2.0 * g * dH) ** 0.5
                ub = (ub / max(abs(ub), 1e-12)) * min(abs(ub), head_gain_factor * u_head)

            # (c) Δu 限幅
            ub = max(ui - cap_du_factor * ci, min(ui + cap_du_factor * ci, ub))

        # 5) 计算 Q_b 并做 ΔQ 限幅 + 欠松弛（可关）
        Qb_raw = ub * Ab
        if use_stabilizers:
            cap_dQ = cap_dQ_factor * Ai * ci
            Qb_raw = max(self.Q[-2] - cap_dQ, min(self.Q[-2] + cap_dQ, Qb_raw))
            prev = getattr(self, 'prev_Qb_right', None)
            if prev is None: prev = Qb_raw
            Qb = prev + relax_Q * (Qb_raw - prev)
            self.prev_Qb_right = Qb
        else:
            Qb = Qb_raw

        # 6) 写回鬼格
        self.S[-1] = Ab
        self.Q[-1] = Qb
        self._refresh_cell_state(-1, level_hint=level)

        # 7) 隐式增量（若启用）
        if getattr(self, 'Implic_flag', False):
            self.V1[0] = self.S[-1] - self.S_old[-1]
            self.V1[1] = self.Q[-1] - self.Q_old[-1]


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

            if self.refined_section_table:
                # 断面表在历史实现中额外扩展了 +100m 深度，导致水力表步长过粗（默认仅100层），
                # 会显著放大 area-level / DEB 插值误差。可选启用“有限外扩 + 细化层数”。
                depth_range = max(float(np.max(ys) - np.min(ys)), self.water_depth_limit)
                extra_depth = max(5.0, 0.5 * depth_range)
                max_depth = depth_range + extra_depth
                # 目标分辨率约 0.02m，并保证不低于传入 num
                target_dz = 0.02
                num_local = max(int(np.ceil(max_depth / target_dz)) + 1, int(num))
            else:
                # 保持历史行为，确保与既有测试基线一致
                max_depth = np.max(ys) - np.min(ys) + 100
                num_local = int(num)
            min_y = np.min(ys)  # 断面最低点
            depth_slice = np.linspace(self.EPSILON, max_depth, num=num_local)  # 均匀划分水层

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
            if i >= self.cell_num:
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


if __name__ == '__main__':
    import os
    import glob
    
    def delete_png_in_folder(folder_path):
        """删除文件夹中所有的 .png 文件"""
        pattern = os.path.join(folder_path, '*.png')
        png_files = glob.glob(pattern)
        for file_path in png_files:
            try:
                os.remove(file_path)
                print(f"删除文件: {file_path}")
            except Exception as e:
                print(f"删除文件失败 {file_path}: {e}")

    # ==================== 1. 清理输出目录 ====================
    output_path = os.path.join('output', 'ideal_1d_demo')
    os.makedirs(output_path, exist_ok=True)
    
    # 清理旧的图片文件
    delete_png_in_folder(output_path)
    print(f"输出路径: {output_path}\n")

    # ==================== 2. 定义河道几何参数 ====================
    # 河道基本信息
    river_data = {
        "cell_num": 100,  # 计算单元数量（推荐100-500之间）
        "pos": [
            [0, 0, 10.0],      # 上游起点: [x, y, 河床高程]
            [400, 0, 9.0],     # 中间点1
            [800, 0, 8.5],     # 中间点2
            [1200, 0, 8.0]     # 下游终点
        ],
        "section_name": ['se1', 'se2', 'se3']  # 断面名称列表
    }

    # 断面几何数据（局部坐标系，第一列为横向距离，第二列为高程）
    section_data = {
        'se1': [
            [0, 0],      # 左岸顶点
            [0, -2],     # 左岸底部
            [5, -2],     # 右岸底部
            [5, 0]       # 右岸顶点
        ],  # 矩形断面，宽5m，深2m
        'se2': [
            [0, 0],
            [0, -2],
            [6, -2],
            [6, 0]
        ],  # 矩形断面，宽6m，深2.5m
        'se3': [
            [0, 0],
            [0, -2],
            [8, -2],
            [8, 0]
        ]   # 矩形断面，宽8m，深3m
    }

    # 断面位置（平面坐标，对应river_data中的pos点）
    section_pos = {
        'se1': [0, 0],       # 断面se1在上游起点
        'se2': [600, 0],     # 断面se2在中段
        'se3': [1200, 0]     # 断面se3在下游终点
    }

    # ==================== 3. 定义模拟参数 ====================
    sim_data = {
        'model_name': 'ideal_1d_river_demo',    # 模型名称
        'sim_start_time': '2024-01-01 00:00:00',  # 模拟开始时间
        'sim_end_time': '2024-01-01 06:00:00',    # 模拟结束时间（6小时）
        'time_step': 30,                           # 输出时间步长（秒）
        'output_path': output_path,                # 输出路径
        'CFL': 0.6,                                # CFL数（0.5-0.9，越小越稳定但越慢）
        'n': 0.025                                 # Manning粗糙系数（0.01-0.05）
    }

    print("="*60)
    print("一维河道水动力模型 - 调用示范")
    print("="*60)
    print(f"模型名称: {sim_data['model_name']}")
    print(f"计算单元数: {river_data['cell_num']}")
    print(f"河道长度: {river_data['pos'][-1][0] - river_data['pos'][0][0]:.1f} m")
    print(f"模拟时长: {(datetime.datetime.strptime(sim_data['sim_end_time'], '%Y-%m-%d %H:%M:%S') - datetime.datetime.strptime(sim_data['sim_start_time'], '%Y-%m-%d %H:%M:%S')).total_seconds() / 3600:.1f} 小时")
    print(f"Manning系数: {sim_data['n']}")
    print(f"CFL数: {sim_data['CFL']}")
    print("="*60 + "\n")

    # ==================== 4. 创建河道模型对象 ====================
    print("正在创建河道模型...")
    river = River(river_data, section_data, section_pos, sim_data)
    print("河道模型创建完成\n")

    # ==================== 5. 设置初始条件 ====================
    # 方式1：设置初始水深（全河道统一水深）
    initial_depth = 1.0  # 初始水深 1.0m
    river.Set_init_watr_depth(initial_depth)
    print(f"设置初始水深: {initial_depth} m\n")
    
    # 方式2：设置初始水位（如果需要指定水位而非水深，可使用下面的方法）
    # initial_level = 9.5  # 初始水位（绝对高程）
    # river.Set_init_water_level(initial_level)

    # ==================== 6. 运行模拟 ====================
    print("开始模拟计算...")
    print("-"*60)
    
    start_time = datetime.datetime.now()
    step_count = 0
    
    # Evolve() 是一个生成器，每个输出时间步返回一次当前模拟时间
    for current_time in river.Evolve(fine=True):
        step_count += 1
        elapsed = (datetime.datetime.now() - start_time).total_seconds()
        progress = river.Current_sim_progress() * 100
        
        # 在每个时间步设置边界条件
        # 上游边界：固定流量入流
        inflow_Q = 10.0  # 上游入流流量 (m³/s)
        river.InBound_In_Q(inflow_Q)
        
        # 下游边界：固定水位
        river.OutBound_Fix_level_V3(-0.4)
        
        # 打印进度信息
        print(f"步数: {step_count:4d} | "
              f"模拟时间: {current_time:8.1f}s | "
              f"时间步长: {river.DT:6.3f}s | "
              f"进度: {progress:5.1f}% | "
              f"耗时: {elapsed:6.1f}s")
    
    # ==================== 7. 输出模拟结果统计 ====================
    total_elapsed = (datetime.datetime.now() - start_time).total_seconds()
    print("-"*60)
    print(f"\n模拟完成！")
    print(f"总步数: {step_count}")
    print(f"总耗时: {total_elapsed:.2f} 秒")
    print(f"平均每步耗时: {total_elapsed/step_count if step_count > 0 else 0:.3f} 秒")
    print(f"结果保存在: {output_path}")
    print("\n" + "="*60)
