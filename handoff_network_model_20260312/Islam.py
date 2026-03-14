from Rivernet import Rivernet
import numpy as np, math
import pandas as pd
import os
import datetime
from math import gamma
from persistent_interpolator import PersistentLinearInterpolator
from tool_fun.section_偏移 import (
    adjust_sections_by_river_bed_average,
    adjust_sections_by_section_station_elevation,
)

output_path = os.environ.get('ISLAM_OUTPUT_PATH', 'result/Islam_base')
use_section_offset = os.environ.get('ISLAM_USE_SECTION_OFFSET', '1') == '1'
# Islam 论文案例里 section_name 数量与 cell_num 一致，默认应按 cell-center 口径，
# 因此这里默认走 auto，而不是历史的 station 口径。
section_offset_mode = os.environ.get('ISLAM_SECTION_OFFSET_MODE', 'auto').strip().lower()
section_pos_mode = os.environ.get('ISLAM_SECTION_POS_MODE', 'auto').strip().lower()

os.makedirs(output_path, exist_ok=True)


def infer_section_layout_mode(river_data):
    """
    推断断面数据在沿程上的布置口径。

    Islam 论文案例里 `section_name` 数量等于 `cell_num`，这更像是
    “每个 reach / 计算单元一个断面”，应按单元中心处理。
    若断面数与单元数不一致，再退回到沿程站位断面的历史口径。
    """
    cell_num = int(river_data['cell_num'])
    names = list(river_data['section_name'])
    if len(names) == cell_num:
        return 'cell_center'
    return 'station'

def build_local_section_pos(river_data):
    """
    为 Fine 断面重构补充 section_pos。

    说明：
    - Islam 案例当前 `river_data['pos']` 使用的是“单河段局部坐标系”，
      x 为沿程距离，y 基本为常数。
    - `Fine_cell_property2` 查询位置使用的正是该局部坐标系下的 `cell_pos[:,:2]`，
      因此这里也必须在同一局部坐标系内给出 section_pos，不能直接改成全网示意图坐标。
    - section_name 与 cell 一一对应，所以取各 cell 两端点的中点作为断面平面坐标。
    """
    pos = np.asarray(river_data['pos'], dtype=float)
    names = list(river_data['section_name'])

    seg_len = np.sqrt(np.sum(np.diff(pos[:, :2], axis=0) ** 2, axis=1))
    cum_len = np.insert(np.cumsum(seg_len), 0, 0.0)
    layout_mode = infer_section_layout_mode(river_data) if section_pos_mode == 'auto' else section_pos_mode
    if layout_mode == 'cell_center':
        target_dist = np.linspace(cum_len[0], cum_len[-1], int(river_data['cell_num']) + 1)
        sec_len = 0.5 * (target_dist[:-1] + target_dist[1:])
    elif layout_mode == 'station':
        sec_len = np.linspace(cum_len[0], cum_len[-1], len(names))
    else:
        raise ValueError(
            f'ISLAM_SECTION_POS_MODE={section_pos_mode!r} 非法，仅支持 auto / station / cell_center'
        )
    sec_x = np.interp(sec_len, cum_len, pos[:, 0])
    sec_y = np.interp(sec_len, cum_len, pos[:, 1])

    return {
        name: np.array([float(sec_x[i]), float(sec_y[i])], dtype=float)
        for i, name in enumerate(names)
    }


def maybe_adjust_sections(river_data, section_data):
    if use_section_offset:
        mode = infer_section_layout_mode(river_data) if section_offset_mode == 'auto' else section_offset_mode
        if mode == 'cell_center':
            mode = 'average'
        if mode == 'station':
            return adjust_sections_by_section_station_elevation(river_data, section_data)
        if mode == 'average':
            return adjust_sections_by_river_bed_average(river_data, section_data)
        raise ValueError(
            f'ISLAM_SECTION_OFFSET_MODE={section_offset_mode!r} 非法，仅支持 auto / station / average'
        )
    return section_data


def section_family_is_vertical_rectangular(section_data):
    """
    粗判该河段断面族是否为“垂直墙矩形”。
    Islam 案例里矩形断面都形如:
      [[xL, zTop], [xL, zBot], [xR, zBot], [xR, zTop]]
    非矩形（如梯形）不会同时满足两侧 x 常数。
    """
    if not section_data:
        return False
    for pts in section_data.values():
        if len(pts) != 4:
            return False
        if not (pts[0][0] == pts[1][0] and pts[2][0] == pts[3][0]):
            return False
    return True

model_data = {
    'model_name': 'river_net',
    'sim_start_time': '2024-01-01 00:00:00',
    'sim_end_time': os.environ.get('ISLAM_SIM_END_TIME', '2024-01-03 00:00:00'),
    'time_step': 60,  # 单位：秒
    'output_path': output_path,
    'CFL': float(os.environ.get('ISLAM_CFL', '0.3')),
    'save_output_mode': os.environ.get('ISLAM_OUTPUT_WRITE_MODE', 'single_resampled').strip().lower(),
}

river_data_1_2 = {
    "cell_num": 15,
    "pos": [[0.0, 1.0, 2.11], [100.0, 1.0, 2.0829999999999997], [200.0, 1.0, 2.056], [300.0, 1.0, 2.029], [400.0, 1.0, 2.0020000000000002], [500.0, 1.0, 1.975], [600.0, 1.0, 1.948], [700.0, 1.0, 1.921], [800.0, 1.0, 1.894], [900.0, 1.0, 1.867], [1000.0, 1.0, 1.84], [1100.0, 1.0, 1.8130000000000002], [1200.0, 1.0, 1.786], [1300.0, 1.0, 1.759], [1400.0, 1.0, 1.7320000000000002], [1500.0, 1.0, 1.705]],
    "section_name": ['se1', 'se2', 'se3', 'se4', 'se5', 'se6', 'se7', 'se8', 'se9', 'se10', 'se11', 'se12', 'se13', 'se14', 'se15']
}

section_data_1_2 = {
    'se1': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se2': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se3': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se4': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se5': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se6': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se7': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se8': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se9': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se10': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se11': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se12': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se13': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se14': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se15': [[0, 10], [10, 0], [20, 0], [30, 10]],
}

section_data_1_2 = maybe_adjust_sections(river_data_1_2, section_data_1_2)
section_pos_1_2 = build_local_section_pos(river_data_1_2)

river_data_3_4 = {
    "cell_num": 30,
    "pos": [[0.0, 1.0, 3.115], [100.0, 1.0, 3.0680000000000005], [200.0, 1.0, 3.0210000000000004], [300.0, 1.0, 2.974], [400.0, 1.0, 2.927], [500.0, 1.0, 2.8800000000000003], [600.0, 1.0, 2.8330000000000006], [700.0, 1.0, 2.786], [800.0, 1.0, 2.7390000000000003], [900.0, 1.0, 2.6919999999999997], [1000.0, 1.0, 2.6450000000000005], [1100.0, 1.0, 2.598], [1200.0, 1.0, 2.551], [1300.0, 1.0, 2.504], [1400.0, 1.0, 2.457], [1500.0, 1.0, 2.41], [1600.0, 1.0, 2.3630000000000004], [1700.0, 1.0, 2.3160000000000003], [1800.0, 1.0, 2.269], [1900.0, 1.0, 2.2220000000000004], [2000.0, 1.0, 2.1750000000000003], [2100.0, 1.0, 2.128], [2200.0, 1.0, 2.0810000000000004], [2300.0, 1.0, 2.034], [2400.0, 1.0, 1.987], [2500.0, 1.0, 1.94], [2600.0, 1.0, 1.893], [2700.0, 1.0, 1.846], [2800.0, 1.0, 1.7990000000000002], [2900.0, 1.0, 1.752], [3000.0, 1.0, 1.705]],
    "section_name": ['se1', 'se2', 'se3', 'se4', 'se5', 'se6', 'se7', 'se8', 'se9', 'se10', 'se11', 'se12', 'se13', 'se14', 'se15', 'se16', 'se17', 'se18', 'se19', 'se20', 'se21', 'se22', 'se23', 'se24', 'se25', 'se26', 'se27', 'se28', 'se29', 'se30']
}

section_data_3_4 = {
    'se1': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se2': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se3': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se4': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se5': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se6': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se7': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se8': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se9': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se10': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se11': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se12': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se13': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se14': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se15': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se16': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se17': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se18': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se19': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se20': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se21': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se22': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se23': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se24': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se25': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se26': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se27': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se28': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se29': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se30': [[0, 10], [10, 0], [20, 0], [30, 10]],
}

section_data_3_4 = maybe_adjust_sections(river_data_3_4, section_data_3_4)
section_pos_3_4 = build_local_section_pos(river_data_3_4)

river_data_5_6_7 = {
    "cell_num": 20,
    "pos": [[0.0, 1.0, 2.1], [100.0, 1.0, 2.07], [200.0, 1.0, 2.04], [300.0, 1.0, 2.01], [400.0, 1.0, 1.9800000000000002], [500.0, 1.0, 1.9500000000000002], [600.0, 1.0, 1.92], [700.0, 1.0, 1.8900000000000001], [800.0, 1.0, 1.86], [900.0, 1.0, 1.8300000000000003], [1000.0, 1.0, 1.8], [1100.0, 1.0, 1.77], [1200.0, 1.0, 1.74], [1300.0, 1.0, 1.71], [1400.0, 1.0, 1.68], [1500.0, 1.0, 1.65], [1600.0, 1.0, 1.62], [1700.0, 1.0, 1.5899999999999999], [1800.0, 1.0, 1.56], [1900.0, 1.0, 1.5299999999999998], [2000.0, 1.0, 1.5]],
    "section_name": ['se1', 'se2', 'se3', 'se4', 'se5', 'se6', 'se7', 'se8', 'se9', 'se10', 'se11', 'se12', 'se13', 'se14', 'se15', 'se16', 'se17', 'se18', 'se19', 'se20']
}

section_data_5_6_7 = {
    'se1': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se2': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se3': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se4': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se5': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se6': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se7': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se8': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se9': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se10': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se11': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se12': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se13': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se14': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se15': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se16': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se17': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se18': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se19': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se20': [[0, 10], [10, 0], [20, 0], [30, 10]],
}

section_data_5_6_7 = maybe_adjust_sections(river_data_5_6_7, section_data_5_6_7)
section_pos_5_6_7 = build_local_section_pos(river_data_5_6_7)


river_data_8_9 = {
    "cell_num": 15,
    "pos": [[0.0, 1.0, 1.705], [100.0, 1.0, 1.6780000000000002], [200.0, 1.0, 1.651], [300.0, 1.0, 1.624], [400.0, 1.0, 1.5970000000000002], [500.0, 1.0, 1.5700000000000003], [600.0, 1.0, 1.543], [700.0, 1.0, 1.516], [800.0, 1.0, 1.489], [900.0, 1.0, 1.4620000000000002], [1000.0, 1.0, 1.435], [1100.0, 1.0, 1.408], [1200.0, 1.0, 1.381], [1300.0, 1.0, 1.354], [1400.0, 1.0, 1.327], [1500.0, 1.0, 1.3]],
    "section_name": ['se1', 'se2', 'se3', 'se4', 'se5', 'se6', 'se7', 'se8', 'se9', 'se10', 'se11', 'se12', 'se13', 'se14', 'se15']
}

section_data_8_9 = {
    'se1': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se2': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se3': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se4': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se5': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se6': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se7': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se8': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se9': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se10': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se11': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se12': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se13': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se14': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se15': [[0, 10], [10, 0], [20, 0], [30, 10]],
}

section_data_8_9 = maybe_adjust_sections(river_data_8_9, section_data_8_9)
section_pos_8_9 = build_local_section_pos(river_data_8_9)


river_data_10 = {
    "cell_num": 20,
    "pos": [[0.0, 1.0, 1.5], [100.0, 1.0, 1.4699999999999998], [200.0, 1.0, 1.4400000000000002], [300.0, 1.0, 1.41], [400.0, 1.0, 1.3800000000000001], [500.0, 1.0, 1.35], [600.0, 1.0, 1.3199999999999998], [700.0, 1.0, 1.29], [800.0, 1.0, 1.26], [900.0, 1.0, 1.23], [1000.0, 1.0, 1.2], [1100.0, 1.0, 1.17], [1200.0, 1.0, 1.1400000000000001], [1300.0, 1.0, 1.1099999999999999], [1400.0, 1.0, 1.08], [1500.0, 1.0, 1.05], [1600.0, 1.0, 1.02], [1700.0, 1.0, 0.99], [1800.0, 1.0, 0.96], [1900.0, 1.0, 0.93], [2000.0, 1.0, 0.9]],
    "section_name": ['se1', 'se2', 'se3', 'se4', 'se5', 'se6', 'se7', 'se8', 'se9', 'se10', 'se11', 'se12', 'se13', 'se14', 'se15', 'se16', 'se17', 'se18', 'se19', 'se20']
}

section_data_10 = {
    'se1': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se2': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se3': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se4': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se5': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se6': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se7': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se8': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se9': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se10': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se11': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se12': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se13': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se14': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se15': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se16': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se17': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se18': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se19': [[0, 10], [10, 0], [20, 0], [30, 10]],
    'se20': [[0, 10], [10, 0], [20, 0], [30, 10]],
}

section_data_10 = maybe_adjust_sections(river_data_10, section_data_10)
section_pos_10 = build_local_section_pos(river_data_10)


river_data_11 = {
    "cell_num": 12,
    "pos": [[0.0, 1.0, 1.3], [100.0, 1.0, 1.2666666666666666], [200.0, 1.0, 1.2333333333333334], [300.0, 1.0, 1.2000000000000002], [400.0, 1.0, 1.1666666666666667], [500.0, 1.0, 1.1333333333333333], [600.0, 1.0, 1.1], [700.0, 1.0, 1.0666666666666667], [800.0, 1.0, 1.0333333333333334], [900.0, 1.0, 1.0], [1000.0, 1.0, 0.9666666666666666], [1100.0, 1.0, 0.9333333333333333], [1200.0, 1.0, 0.9]],
    "section_name": ['se1', 'se2', 'se3', 'se4', 'se5', 'se6', 'se7', 'se8', 'se9', 'se10', 'se11', 'se12']
}

section_data_11 = {
    'se1': [[0, 10], [0, 0], [10, 0], [10, 10]],
    'se2': [[0, 10], [0, 0], [10, 0], [10, 10]],
    'se3': [[0, 10], [0, 0], [10, 0], [10, 10]],
    'se4': [[0, 10], [0, 0], [10, 0], [10, 10]],
    'se5': [[0, 10], [0, 0], [10, 0], [10, 10]],
    'se6': [[0, 10], [0, 0], [10, 0], [10, 10]],
    'se7': [[0, 10], [0, 0], [10, 0], [10, 10]],
    'se8': [[0, 10], [0, 0], [10, 0], [10, 10]],
    'se9': [[0, 10], [0, 0], [10, 0], [10, 10]],
    'se10': [[0, 10], [0, 0], [10, 0], [10, 10]],
    'se11': [[0, 10], [0, 0], [10, 0], [10, 10]],
    'se12': [[0, 10], [0, 0], [10, 0], [10, 10]],
}

section_data_11 = maybe_adjust_sections(river_data_11, section_data_11)
section_pos_11 = build_local_section_pos(river_data_11)

river_data_12 = {
    "cell_num": 36,
    "pos": [[0.0, 1.0, 1.3], [100.0, 1.0, 1.275], [200.0, 1.0, 1.25], [300.0, 1.0, 1.225], [400.0, 1.0, 1.2], [500.0, 1.0, 1.175], [600.0, 1.0, 1.1500000000000001], [700.0, 1.0, 1.125], [800.0, 1.0, 1.0999999999999999], [900.0, 1.0, 1.0750000000000002], [1000.0, 1.0, 1.05], [1100.0, 1.0, 1.025], [1200.0, 1.0, 1.0000000000000002], [1300.0, 1.0, 0.975], [1400.0, 1.0, 0.9500000000000001], [1500.0, 1.0, 0.925], [1600.0, 1.0, 0.9000000000000001], [1700.0, 1.0, 0.875], [1800.0, 1.0, 0.8500000000000001], [1900.0, 1.0, 0.8250000000000001], [2000.0, 1.0, 0.7999999999999999], [2100.0, 1.0, 0.775], [2200.0, 1.0, 0.75], [2300.0, 1.0, 0.7250000000000001], [2400.0, 1.0, 0.7000000000000001], [2500.0, 1.0, 0.675], [2600.0, 1.0, 0.6500000000000001], [2700.0, 1.0, 0.625], [2800.0, 1.0, 0.6], [2900.0, 1.0, 0.575], [3000.0, 1.0, 0.55], [3100.0, 1.0, 0.525], [3200.0, 1.0, 0.5000000000000001], [3300.0, 1.0, 0.4750000000000001], [3400.0, 1.0, 0.45], [3500.0, 1.0, 0.42500000000000004], [3600.0, 1.0, 0.4]],
    "section_name": ['se1', 'se2', 'se3', 'se4', 'se5', 'se6', 'se7', 'se8', 'se9', 'se10', 'se11', 'se12', 'se13', 'se14', 'se15', 'se16', 'se17', 'se18', 'se19', 'se20', 'se21', 'se22', 'se23', 'se24', 'se25', 'se26', 'se27', 'se28', 'se29', 'se30', 'se31', 'se32', 'se33', 'se34', 'se35', 'se36']
}

section_data_12 = {
    'se1': [[0, 10], [0, 0], [20, 0], [20, 10]],
    'se2': [[0, 10], [0, 0], [20, 0], [20, 10]],
    'se3': [[0, 10], [0, 0], [20, 0], [20, 10]],
    'se4': [[0, 10], [0, 0], [20, 0], [20, 10]],
    'se5': [[0, 10], [0, 0], [20, 0], [20, 10]],
    'se6': [[0, 10], [0, 0], [20, 0], [20, 10]],
    'se7': [[0, 10], [0, 0], [20, 0], [20, 10]],
    'se8': [[0, 10], [0, 0], [20, 0], [20, 10]],
    'se9': [[0, 10], [0, 0], [20, 0], [20, 10]],
    'se10': [[0, 10], [0, 0], [20, 0], [20, 10]],
    'se11': [[0, 10], [0, 0], [20, 0], [20, 10]],
    'se12': [[0, 10], [0, 0], [20, 0], [20, 10]],
    'se13': [[0, 10], [0, 0], [20, 0], [20, 10]],
    'se14': [[0, 10], [0, 0], [20, 0], [20, 10]],
    'se15': [[0, 10], [0, 0], [20, 0], [20, 10]],
    'se16': [[0, 10], [0, 0], [20, 0], [20, 10]],
    'se17': [[0, 10], [0, 0], [20, 0], [20, 10]],
    'se18': [[0, 10], [0, 0], [20, 0], [20, 10]],
    'se19': [[0, 10], [0, 0], [20, 0], [20, 10]],
    'se20': [[0, 10], [0, 0], [20, 0], [20, 10]],
    'se21': [[0, 10], [0, 0], [20, 0], [20, 10]],
    'se22': [[0, 10], [0, 0], [20, 0], [20, 10]],
    'se23': [[0, 10], [0, 0], [20, 0], [20, 10]],
    'se24': [[0, 10], [0, 0], [20, 0], [20, 10]],
    'se25': [[0, 10], [0, 0], [20, 0], [20, 10]],
    'se26': [[0, 10], [0, 0], [20, 0], [20, 10]],
    'se27': [[0, 10], [0, 0], [20, 0], [20, 10]],
    'se28': [[0, 10], [0, 0], [20, 0], [20, 10]],
    'se29': [[0, 10], [0, 0], [20, 0], [20, 10]],
    'se30': [[0, 10], [0, 0], [20, 0], [20, 10]],
    'se31': [[0, 10], [0, 0], [20, 0], [20, 10]],
    'se32': [[0, 10], [0, 0], [20, 0], [20, 10]],
    'se33': [[0, 10], [0, 0], [20, 0], [20, 10]],
    'se34': [[0, 10], [0, 0], [20, 0], [20, 10]],
    'se35': [[0, 10], [0, 0], [20, 0], [20, 10]],
    'se36': [[0, 10], [0, 0], [20, 0], [20, 10]],
}

section_data_12 = maybe_adjust_sections(river_data_12, section_data_12)
section_pos_12 = build_local_section_pos(river_data_12)

river_data_13 = {
    "cell_num": 20,
    "pos": [[0.0, 1.0, 0.9], [100.0, 1.0, 0.875], [200.0, 1.0, 0.8500000000000001], [300.0, 1.0, 0.825], [400.0, 1.0, 0.8], [500.0, 1.0, 0.775], [600.0, 1.0, 0.75], [700.0, 1.0, 0.7250000000000001], [800.0, 1.0, 0.7000000000000001], [900.0, 1.0, 0.675], [1000.0, 1.0, 0.65], [1100.0, 1.0, 0.625], [1200.0, 1.0, 0.6000000000000001], [1300.0, 1.0, 0.575], [1400.0, 1.0, 0.55], [1500.0, 1.0, 0.525], [1600.0, 1.0, 0.5], [1700.0, 1.0, 0.4750000000000001], [1800.0, 1.0, 0.45], [1900.0, 1.0, 0.42500000000000004], [2000.0, 1.0, 0.4]],
    "section_name": ['se1', 'se2', 'se3', 'se4', 'se5', 'se6', 'se7', 'se8', 'se9', 'se10', 'se11', 'se12', 'se13', 'se14', 'se15', 'se16', 'se17', 'se18', 'se19', 'se20']
}

section_data_13 = {
    'se1': [[0, 10], [0, 0], [20, 0], [20, 10]],
    'se2': [[0, 10], [0, 0], [20, 0], [20, 10]],
    'se3': [[0, 10], [0, 0], [20, 0], [20, 10]],
    'se4': [[0, 10], [0, 0], [20, 0], [20, 10]],
    'se5': [[0, 10], [0, 0], [20, 0], [20, 10]],
    'se6': [[0, 10], [0, 0], [20, 0], [20, 10]],
    'se7': [[0, 10], [0, 0], [20, 0], [20, 10]],
    'se8': [[0, 10], [0, 0], [20, 0], [20, 10]],
    'se9': [[0, 10], [0, 0], [20, 0], [20, 10]],
    'se10': [[0, 10], [0, 0], [20, 0], [20, 10]],
    'se11': [[0, 10], [0, 0], [20, 0], [20, 10]],
    'se12': [[0, 10], [0, 0], [20, 0], [20, 10]],
    'se13': [[0, 10], [0, 0], [20, 0], [20, 10]],
    'se14': [[0, 10], [0, 0], [20, 0], [20, 10]],
    'se15': [[0, 10], [0, 0], [20, 0], [20, 10]],
    'se16': [[0, 10], [0, 0], [20, 0], [20, 10]],
    'se17': [[0, 10], [0, 0], [20, 0], [20, 10]],
    'se18': [[0, 10], [0, 0], [20, 0], [20, 10]],
    'se19': [[0, 10], [0, 0], [20, 0], [20, 10]],
    'se20': [[0, 10], [0, 0], [20, 0], [20, 10]],
}

section_data_13 = maybe_adjust_sections(river_data_13, section_data_13)
section_pos_13 = build_local_section_pos(river_data_13)


river_data_14 = {
    "cell_num": 25,
    "pos": [[0.0, 1.0, 0.4], [100.0, 1.0, 0.384], [200.0, 1.0, 0.36800000000000005], [300.0, 1.0, 0.35200000000000004], [400.0, 1.0, 0.336], [500.0, 1.0, 0.32000000000000006], [600.0, 1.0, 0.30400000000000005], [700.0, 1.0, 0.288], [800.0, 1.0, 0.27199999999999996], [900.0, 1.0, 0.256], [1000.0, 1.0, 0.24], [1100.0, 1.0, 0.22400000000000003], [1200.0, 1.0, 0.20800000000000002], [1300.0, 1.0, 0.192], [1400.0, 1.0, 0.176], [1500.0, 1.0, 0.16000000000000003], [1600.0, 1.0, 0.144], [1700.0, 1.0, 0.12799999999999997], [1800.0, 1.0, 0.11200000000000002], [1900.0, 1.0, 0.096], [2000.0, 1.0, 0.07999999999999999], [2100.0, 1.0, 0.06400000000000002], [2200.0, 1.0, 0.048], [2300.0, 1.0, 0.03199999999999999], [2400.0, 1.0, 0.016000000000000014], [2500.0, 1.0, 0.0]],
    "section_name": ['se1', 'se2', 'se3', 'se4', 'se5', 'se6', 'se7', 'se8', 'se9', 'se10', 'se11', 'se12', 'se13', 'se14', 'se15', 'se16', 'se17', 'se18', 'se19', 'se20', 'se21', 'se22', 'se23', 'se24', 'se25']
}

section_data_14 = {
    'se1': [[0, 10], [0, 0], [30, 0], [30, 10]],
    'se2': [[0, 10], [0, 0], [30, 0], [30, 10]],
    'se3': [[0, 10], [0, 0], [30, 0], [30, 10]],
    'se4': [[0, 10], [0, 0], [30, 0], [30, 10]],
    'se5': [[0, 10], [0, 0], [30, 0], [30, 10]],
    'se6': [[0, 10], [0, 0], [30, 0], [30, 10]],
    'se7': [[0, 10], [0, 0], [30, 0], [30, 10]],
    'se8': [[0, 10], [0, 0], [30, 0], [30, 10]],
    'se9': [[0, 10], [0, 0], [30, 0], [30, 10]],
    'se10': [[0, 10], [0, 0], [30, 0], [30, 10]],
    'se11': [[0, 10], [0, 0], [30, 0], [30, 10]],
    'se12': [[0, 10], [0, 0], [30, 0], [30, 10]],
    'se13': [[0, 10], [0, 0], [30, 0], [30, 10]],
    'se14': [[0, 10], [0, 0], [30, 0], [30, 10]],
    'se15': [[0, 10], [0, 0], [30, 0], [30, 10]],
    'se16': [[0, 10], [0, 0], [30, 0], [30, 10]],
    'se17': [[0, 10], [0, 0], [30, 0], [30, 10]],
    'se18': [[0, 10], [0, 0], [30, 0], [30, 10]],
    'se19': [[0, 10], [0, 0], [30, 0], [30, 10]],
    'se20': [[0, 10], [0, 0], [30, 0], [30, 10]],
    'se21': [[0, 10], [0, 0], [30, 0], [30, 10]],
    'se22': [[0, 10], [0, 0], [30, 0], [30, 10]],
    'se23': [[0, 10], [0, 0], [30, 0], [30, 10]],
    'se24': [[0, 10], [0, 0], [30, 0], [30, 10]],
    'se25': [[0, 10], [0, 0], [30, 0], [30, 10]],
}

section_data_14 = maybe_adjust_sections(river_data_14, section_data_14)
section_pos_14 = build_local_section_pos(river_data_14)

def parse_edge_direction(env_key, default_dir, node_a, node_b):
    direction = os.environ.get(env_key, default_dir).strip().lower()
    if direction == f'{node_a}_to_{node_b}':
        return direction, (node_a, node_b), +1
    if direction == f'{node_b}_to_{node_a}':
        return direction, (node_b, node_a), -1
    raise ValueError(
        f'{env_key}={direction!r} 非法，'
        f'仅支持 {node_a}_to_{node_b} 或 {node_b}_to_{node_a}'
    )


river11_dir, river11_edge, river11_sign = parse_edge_direction(
    'ISLAM_RIVER11_DIR', 'n11_to_n12', 'n11', 'n12'
)
river12_dir, river12_edge, river12_sign = parse_edge_direction(
    'ISLAM_RIVER12_DIR', 'n11_to_n13', 'n11', 'n13'
)
river13_dir, river13_edge, river13_sign = parse_edge_direction(
    'ISLAM_RIVER13_DIR', 'n12_to_n13', 'n12', 'n13'
)


manning_scale = float(os.environ.get('ISLAM_MANNING_SCALE', '1.0'))
init_q_mode = os.environ.get('ISLAM_INIT_Q_MODE', 'none').strip().lower()
node11_to_r11_ratio = float(os.environ.get('ISLAM_NODE11_TO_R11_RATIO', '0.25'))
node11_to_r11_ratio = max(0.0, min(1.0, node11_to_r11_ratio))


def river_manning(base_n, river_name):
    local_scale = float(os.environ.get(f'ISLAM_MANNING_SCALE_{river_name.upper()}', '1.0'))
    return base_n * manning_scale * local_scale


top = {
    ('n1', 'n8'): {'name': 'river1', 'river_data': river_data_1_2,
                   'section_data': section_data_1_2, 'model_data': model_data, 'section_pos': section_pos_1_2,
                   'manning': river_manning(0.022, 'river1')},

    ('n2', 'n8'): {'name': 'river2', 'river_data': river_data_1_2,
                   'section_data': section_data_1_2, 'model_data': model_data, 'section_pos': section_pos_1_2,
                   'manning': river_manning(0.022, 'river2')},

    ('n3', 'n9'): {'name': 'river3', 'river_data': river_data_3_4,
                   'section_data': section_data_3_4, 'model_data': model_data, 'section_pos': section_pos_3_4,
                   'manning': river_manning(0.025, 'river3')},

    ('n4', 'n9'): {'name': 'river4', 'river_data': river_data_3_4,
                   'section_data': section_data_3_4, 'model_data': model_data, 'section_pos': section_pos_3_4,
                   'manning': river_manning(0.025, 'river4')},

    ('n5', 'n10'): {'name': 'river5', 'river_data': river_data_5_6_7,
                    'section_data': section_data_5_6_7, 'model_data': model_data, 'section_pos': section_pos_5_6_7,
                    'manning': river_manning(0.022, 'river5')},

    ('n6', 'n10'): {'name': 'river6', 'river_data': river_data_5_6_7,
                    'section_data': section_data_5_6_7, 'model_data': model_data, 'section_pos': section_pos_5_6_7,
                    'manning': river_manning(0.022, 'river6')},

    ('n7', 'n10'): {'name': 'river7', 'river_data': river_data_5_6_7,
                    'section_data': section_data_5_6_7, 'model_data': model_data, 'section_pos': section_pos_5_6_7,
                    'manning': river_manning(0.022, 'river7')},

    ('n8', 'n11'): {'name': 'river8', 'river_data': river_data_8_9,
                    'section_data': section_data_8_9, 'model_data': model_data, 'section_pos': section_pos_8_9,
                    'manning': river_manning(0.022, 'river8')},

    ('n9', 'n11'): {'name': 'river9', 'river_data': river_data_8_9,
                    'section_data': section_data_8_9, 'model_data': model_data, 'section_pos': section_pos_8_9,
                    'manning': river_manning(0.022, 'river9')},

    ('n10', 'n12'): {'name': 'river10', 'river_data': river_data_10,
                     'section_data': section_data_10, 'model_data': model_data, 'section_pos': section_pos_10,
                     'manning': river_manning(0.022, 'river10')},

    river11_edge: {'name': 'river11', 'river_data': river_data_11,
                     'section_data': section_data_11, 'model_data': model_data, 'section_pos': section_pos_11,
                     'manning': river_manning(0.022, 'river11')},

    river12_edge: {'name': 'river12', 'river_data': river_data_12,
                   'section_data': section_data_12, 'model_data': model_data, 'section_pos': section_pos_12,
                   'manning': river_manning(0.022, 'river12')},

    river13_edge: {'name': 'river13', 'river_data': river_data_13,
                   'section_data': section_data_13, 'model_data': model_data, 'section_pos': section_pos_13,
                   'manning': river_manning(0.022, 'river13')},

    ('n13', 'n14'): {'name': 'river14', 'river_data': river_data_14,
                     'section_data': section_data_14, 'model_data': model_data, 'section_pos': section_pos_14,
                     'manning': river_manning(0.022, 'river14')},
}

level = PersistentLinearInterpolator('bound/Islam_level_out.csv', allow_extrapolation=True)
Q = PersistentLinearInterpolator('bound/Islam_Q_In.csv', allow_extrapolation=True)
init_level = float(os.environ.get('ISLAM_INIT_LEVEL', '3.25'))
q_shift_hours = float(os.environ.get('ISLAM_Q_SHIFT_HOURS', '0.0'))
level_bias = float(os.environ.get('ISLAM_LEVEL_BIAS', '0.0'))
q_scale_default = float(os.environ.get('ISLAM_Q_SCALE_DEFAULT', '1.0'))
q_scales = {
    f'n{i}': float(os.environ.get(f'ISLAM_Q_SCALE_N{i}', str(q_scale_default)))
    for i in range(1, 8)
}
boundary_cycle_hours = float(os.environ.get('ISLAM_BOUNDARY_CYCLE_HOURS', str(max(1e-6, Q.x_max - Q.x_min))))


def q_boundary_value(t_seconds, node_name):
    return q_scales[node_name] * Q(t_seconds / 3600.0 + q_shift_hours)


def level_boundary_value(t_seconds):
    return level(t_seconds / 3600.0) + level_bias


def wrap_hours(h):
    period = max(1e-6, boundary_cycle_hours)
    base = float(Q.x_min)
    return ((h - base) % period) + base


def q_boundary_value_cyclic(t_seconds, node_name, shift_hours=0.0):
    h = wrap_hours(t_seconds / 3600.0 + q_shift_hours + shift_hours)
    return q_scales[node_name] * Q(h)


def level_boundary_value_cyclic(t_seconds, shift_hours=0.0):
    h = wrap_hours(t_seconds / 3600.0 + shift_hours)
    return level(h) + level_bias


def build_initial_discharge_guess():
    q_in = {
        f'n{i}': q_boundary_value(0.0, f'n{i}')
        for i in range(1, 8)
    }
    guess = {
        'river1': q_in['n1'],
        'river2': q_in['n2'],
        'river3': q_in['n3'],
        'river4': q_in['n4'],
        'river5': q_in['n5'],
        'river6': q_in['n6'],
        'river7': q_in['n7'],
    }

    # 一次合流
    guess['river8'] = guess['river1'] + guess['river2']
    guess['river9'] = guess['river3'] + guess['river4']
    guess['river10'] = guess['river5'] + guess['river6'] + guess['river7']

    # n11 处分流比例（按经验参数）
    node11_total = guess['river8'] + guess['river9']
    q11_to_n12 = node11_to_r11_ratio * node11_total

    # 物理正向约定：
    #   river11: n11 -> n12
    #   river12: n11 -> n13
    #   river13: n12 -> n13
    q11_forward = q11_to_n12
    q12_forward = node11_total - q11_to_n12
    q13_forward = guess['river10'] + q11_to_n12

    guess['river11'] = river11_sign * q11_forward
    guess['river12'] = river12_sign * q12_forward
    guess['river13'] = river13_sign * q13_forward

    guess['river14'] = guess['river12'] + guess['river13']
    return guess


def apply_initial_discharge_guess(net_obj, guess):
    for _, _, data in net_obj.G.edges(data=True):
        river_name = data.get('name')
        if river_name not in guess:
            continue
        q0 = float(guess[river_name])
        river = data['river']
        river.Q[:] = q0
        river.Q_old[:] = q0



net = Rivernet(top, model_data)
warmup_hours = float(os.environ.get('ISLAM_WARMUP_HOURS', '0.0'))
output_rivers_env = os.environ.get('ISLAM_OUTPUT_RIVERS', '').strip()
output_rivers = {s.strip() for s in output_rivers_env.split(',') if s.strip()} if output_rivers_env else None


def configure_net_options(net_obj, export_png=False):
    net_obj.use_parallel_workers = os.environ.get('ISLAM_USE_PARALLEL', '0') == '1'
    net_obj.parallel_backend = os.environ.get('ISLAM_PARALLEL_BACKEND', 'threads').strip().lower()
    net_obj.parallel_n_workers = int(os.environ.get('ISLAM_N_WORKERS', str(net_obj.parallel_n_workers)))
    net_obj.parallel_start_method = os.environ.get('ISLAM_PARALLEL_START_METHOD', 'spawn').strip().lower()
    net_obj.parallel_sync_main_state_on_yield = os.environ.get('ISLAM_PARALLEL_SYNC_ON_YIELD', '1') == '1'
    save_interval_env = os.environ.get('ISLAM_SAVE_INTERVAL', '').strip()
    net_obj.output_save_interval = float(save_interval_env) if save_interval_env else None
    net_obj.save_cfl_history = os.environ.get('ISLAM_SAVE_CFL_HISTORY', '0') == '1'
    net_obj.external_flow_bc_use_characteristic = os.environ.get('ISLAM_USE_CHARFLOW_BC', '1') == '1'
    net_obj.external_bc_use_stabilizers = os.environ.get('ISLAM_USE_EXTERNAL_STAB', '0') == '1'
    net_obj.internal_bc_use_stabilizers = os.environ.get('ISLAM_USE_INTERNAL_STAB', '0') == '1'
    net_obj.external_bc_respect_supercritical = os.environ.get('ISLAM_RESPECT_SUPER_EXTERNAL', '1') == '1'
    net_obj.internal_bc_respect_supercritical = os.environ.get('ISLAM_RESPECT_SUPER_INTERNAL', '1') == '1'
    net_obj.use_fix_level_bc_v2 = os.environ.get('ISLAM_FIX_LEVEL_BC_V2', '0') == '1'
    net_obj.internal_use_ac_v2 = os.environ.get('ISLAM_NODE_AC_V2', '1') == '1'
    net_obj.internal_use_paper_ac = os.environ.get('ISLAM_NODE_PAPER_AC', '1') == '1'
    net_obj.internal_level_predict_from_last = os.environ.get('ISLAM_NODE_PREDICT_LAST', '1') == '1'
    net_obj.internal_sync_branch_end_Q = os.environ.get('ISLAM_NODE_SYNC_BRANCH_END_Q', '0') == '1'
    net_obj.internal_sync_branch_end_Q_relax = float(os.environ.get('ISLAM_NODE_SYNC_BRANCH_END_Q_RELAX', '1.0'))
    net_obj.internal_node_use_face_discharge = os.environ.get('ISLAM_NODE_USE_FACE_Q', '0') == '1'
    # 边界界面 discharge 口径仅作为诊断试验；默认仍保持历史 ghost-Q 结点残差。
    net_obj.internal_node_prefer_boundary_face_discharge = os.environ.get('ISLAM_NODE_USE_BOUNDARY_FACE_Q', '0') == '1'
    net_obj.internal_node_use_boundary_face_ac = os.environ.get('ISLAM_NODE_USE_BOUNDARY_FACE_AC', '0') == '1'
    # face-flux 残差是诊断试验路径，历史回归显示默认开启会显著劣化 Islam 案例；
    # 默认保持 ghost-Q 残差，只有显式试验时才打开。
    net_obj.internal_node_use_face_flux_residual = os.environ.get('ISLAM_NODE_USE_FACE_FLUX', '0') == '1'

    net_obj.max_iteration = int(os.environ.get('ISLAM_NODE_MAX_ITER', str(net_obj.max_iteration)))
    net_obj.alpha = float(os.environ.get('ISLAM_NODE_ALPHA', str(net_obj.alpha)))
    net_obj.relax = float(os.environ.get('ISLAM_NODE_RELAX', str(net_obj.relax)))
    net_obj.internal_use_numeric_jacobian = os.environ.get('ISLAM_NODE_NUMERIC_JAC', '0') == '1'
    net_obj.internal_use_coupled_newton = os.environ.get('ISLAM_NODE_COUPLED_NEWTON', '0') == '1'
    net_obj.use_implicit_branch_update = os.environ.get('ISLAM_USE_IMPLICIT_BRANCH', '0') == '1'
    net_obj.Fine_flag = os.environ.get('ISLAM_USE_FINE_INTERPOLATION', '1') == '1'
    stage_on_face_global = os.environ.get('ISLAM_BC_STAGE_ON_FACE', '0') == '1'
    net_obj.external_bc_stage_on_face = os.environ.get(
        'ISLAM_BC_STAGE_ON_FACE_EXTERNAL',
        '1' if stage_on_face_global else '0'
    ) == '1'
    net_obj.internal_bc_stage_on_face = os.environ.get(
        'ISLAM_BC_STAGE_ON_FACE_INTERNAL',
        '1' if stage_on_face_global else '0'
    ) == '1'
    net_obj.verbos = False

    if net_obj.Fine_flag:
        missing_pos = []
        for _, _, data in net_obj.G.edges(data=True):
            river = data['river']
            if not getattr(river, 'section_interpolation_enabled', False):
                missing_pos.append(data.get('name'))
        if missing_pos:
            print(
                f'ISLAM_USE_FINE_INTERPOLATION=1，但以下河段缺少 section_pos，'
                f'将禁用 Fine 插值优化: {missing_pos}'
            )
            net_obj.Fine_flag = False

    if export_png:
        net_obj.export_png(path=os.path.join(output_path, 'net.png'))


def apply_boundaries(net_obj, mode='main', warmup_shift_hours=0.0):
    if mode == 'constant':
        q0 = {f'n{i}': q_boundary_value(0.0, f'n{i}') for i in range(1, 8)}
        z0 = level_boundary_value(0.0)
        net_obj.set_boundary('n14', 'fix_level', lambda t, _z=z0: _z)
        for i in range(1, 8):
            net_obj.set_boundary(f'n{i}', 'flow', lambda t, _q=q0[f'n{i}']: _q)
    elif mode == 'cyclic':
        net_obj.set_boundary('n14', 'fix_level', lambda t, _s=warmup_shift_hours: level_boundary_value_cyclic(t, _s))
        for i in range(1, 8):
            net_obj.set_boundary(
                f'n{i}',
                'flow',
                lambda t, _n=f'n{i}', _s=warmup_shift_hours: q_boundary_value_cyclic(t, _n, _s)
            )
    else:
        net_obj.set_boundary('n14', 'fix_level', lambda t: level_boundary_value(t))
        for i in range(1, 8):
            net_obj.set_boundary(f'n{i}', 'flow', lambda t, _n=f'n{i}': q_boundary_value(t, _n))


def initialize_rivers(net_obj):
    swap_moc_all = os.environ.get('ISLAM_SWAP_MOC_SIGN', '0') == '1'
    swap_moc_flow = os.environ.get(
        'ISLAM_SWAP_MOC_FLOW',
        '1' if swap_moc_all else '0'
    ) == '1'
    swap_moc_stage = os.environ.get(
        'ISLAM_SWAP_MOC_STAGE',
        '1' if swap_moc_all else '0'
    ) == '1'
    swap_moc_stage_in = os.environ.get(
        'ISLAM_SWAP_MOC_STAGE_IN',
        '1' if swap_moc_stage else '0'
    ) == '1'
    swap_moc_stage_out = os.environ.get(
        'ISLAM_SWAP_MOC_STAGE_OUT',
        '1' if swap_moc_stage else '0'
    ) == '1'
    bc_use_order2_extrap = os.environ.get('ISLAM_BC_EXTRAP_ORDER2', '1') == '1'
    bc_use_order2_extrap_flow = os.environ.get(
        'ISLAM_BC_EXTRAP_ORDER2_FLOW',
        '1' if bc_use_order2_extrap else '0'
    ) == '1'
    bc_use_order2_extrap_stage = os.environ.get(
        'ISLAM_BC_EXTRAP_ORDER2_STAGE',
        '1' if bc_use_order2_extrap else '0'
    ) == '1'
    bc_order2_boundary_face = os.environ.get('ISLAM_BC_ORDER2_FACE', '0') == '1'
    bc_stage_on_face = os.environ.get('ISLAM_BC_STAGE_ON_FACE', '0') == '1'
    bc_stage_store_face_state = os.environ.get('ISLAM_BC_STAGE_STORE_FACE', '0') == '1'
    bc_stage_ghost_q_from_face = os.environ.get('ISLAM_BC_STAGE_GHOST_Q_FACE', '0') == '1'
    bc_stage_reconstruct_ghost_u = os.environ.get(
        'ISLAM_BC_STAGE_RECON_GHOST_U',
        '1' if (bc_stage_on_face and not bc_stage_store_face_state) else '0'
    ) == '1'
    bc_stage_reconstruct_ghost_q = os.environ.get('ISLAM_BC_STAGE_RECON_GHOST_Q', '0') == '1'
    bc_stage_char_on_face = os.environ.get(
        'ISLAM_BC_STAGE_CHAR_ON_FACE',
        '1' if bc_stage_on_face else '0'
    ) == '1'
    bc_stage_on_face_use_depth = os.environ.get('ISLAM_BC_STAGE_ON_FACE_DEPTH', '0') == '1'
    bc_use_general_chi = os.environ.get('ISLAM_BC_GENERAL_CHI', '1') == '1'
    bc_use_general_chi_flow = os.environ.get(
        'ISLAM_BC_GENERAL_CHI_FLOW',
        '1' if bc_use_general_chi else '0'
    ) == '1'
    bc_use_general_chi_stage = os.environ.get(
        'ISLAM_BC_GENERAL_CHI_STAGE',
        '1' if bc_use_general_chi else '0'
    ) == '1'
    bc_moc_with_source = os.environ.get('ISLAM_BC_MOC_WITH_SOURCE', '0') == '1'
    bc_moc_with_source_flow = os.environ.get(
        'ISLAM_BC_MOC_WITH_SOURCE_FLOW',
        '1' if bc_moc_with_source else '0'
    ) == '1'
    bc_moc_with_source_stage = os.environ.get(
        'ISLAM_BC_MOC_WITH_SOURCE_STAGE',
        '1' if bc_moc_with_source else '0'
    ) == '1'
    bc_use_general_chi_stage_nonrect = os.environ.get(
        'ISLAM_BC_GENERAL_CHI_STAGE_NONRECT',
        '0'
    ) == '1'
    bc_general_chi_candidate_mode = os.environ.get(
        'ISLAM_BC_GENERAL_CHI_CANDIDATE_MODE',
        'guarded_clamp'
    ).strip().lower()
    bc_general_chi_guard_selector = os.environ.get(
        'ISLAM_BC_GENERAL_CHI_GUARD_SELECTOR',
        'closure_q_delta'
    ).strip().lower()
    bc_general_chi_guard_q_delta = float(
        os.environ.get('ISLAM_BC_GENERAL_CHI_GUARD_Q_DELTA', '0.005')
    )
    bc_moc_dt_fraction = float(os.environ.get('ISLAM_BC_MOC_DT_FRACTION', '0.5'))
    bc_moc_source_scale = float(os.environ.get('ISLAM_BC_MOC_SOURCE_SCALE', '1.0'))
    use_roe_dissipation = os.environ.get('ISLAM_USE_ROE_DISS', '0') == '1'
    use_boundary_face_flux_override = os.environ.get('ISLAM_USE_BOUNDARY_FACE_FLUX_OVERRIDE', '0') == '1'
    use_boundary_face_mass_flux_override = os.environ.get('ISLAM_USE_BOUNDARY_FACE_MASS_FLUX_OVERRIDE', '0') == '1'
    frtimp = int(os.environ.get('ISLAM_FRTIMP', '1'))
    fix_dsdx_mapping = os.environ.get('ISLAM_FIX_DSDX_MAPPING', '0') == '1'
    for _, _, data in net_obj.G.edges(data=True):
        river = data['river']
        river.Set_init_water_level(init_level)
        river.swap_moc_sign = swap_moc_all
        river.swap_moc_sign_flow = swap_moc_flow
        river.swap_moc_sign_stage = swap_moc_stage
        river.swap_moc_sign_stage_in = swap_moc_stage_in
        river.swap_moc_sign_stage_out = swap_moc_stage_out
        river.bc_use_order2_extrap = bc_use_order2_extrap
        river.bc_use_order2_extrap_flow = bc_use_order2_extrap_flow
        river.bc_use_order2_extrap_stage = bc_use_order2_extrap_stage
        river.bc_order2_boundary_face = bc_order2_boundary_face
        river.bc_stage_on_face = bc_stage_on_face
        river.bc_stage_store_face_state = bc_stage_store_face_state
        river.bc_stage_ghost_q_from_face = bc_stage_ghost_q_from_face
        river.bc_stage_reconstruct_ghost_u = bc_stage_reconstruct_ghost_u
        river.bc_stage_reconstruct_ghost_q = bc_stage_reconstruct_ghost_q
        river.bc_stage_char_on_face = bc_stage_char_on_face
        river.bc_stage_on_face_use_depth = bc_stage_on_face_use_depth
        river.bc_use_general_chi = bc_use_general_chi
        river.bc_use_general_chi_flow = bc_use_general_chi_flow
        river.bc_use_general_chi_stage = bc_use_general_chi_stage
        river.bc_general_chi_candidate_mode = bc_general_chi_candidate_mode
        river.bc_general_chi_guard_selector = bc_general_chi_guard_selector
        river.bc_general_chi_guard_q_delta = bc_general_chi_guard_q_delta
        if bc_use_general_chi_stage_nonrect and not section_family_is_vertical_rectangular(river.sections_data):
            river.bc_use_general_chi_stage = True
        river.bc_moc_with_source = bc_moc_with_source
        river.bc_moc_with_source_flow = bc_moc_with_source_flow
        river.bc_moc_with_source_stage = bc_moc_with_source_stage
        river.bc_moc_dt_fraction = bc_moc_dt_fraction
        river.bc_moc_source_scale = bc_moc_source_scale
        river.use_roe_dissipation = use_roe_dissipation
        river.use_boundary_face_flux_override = use_boundary_face_flux_override
        river.use_boundary_face_mass_flux_override = use_boundary_face_mass_flux_override
        river.FRTIMP = frtimp
        river.fix_dsdx_mapping = fix_dsdx_mapping
        river.refined_section_table = os.environ.get('ISLAM_REFINED_SECTION_TABLE', '0') == '1'
        river.save_with_ghost = os.environ.get('ISLAM_SAVE_WITH_GHOST', '0') == '1'

    if init_q_mode == 'steady_guess':
        init_q_guess = build_initial_discharge_guess()
        apply_initial_discharge_guess(net_obj, init_q_guess)


def copy_warmup_state(src_net, dst_net):
    src_map = {data['name']: data['river'] for _, _, data in src_net.G.edges(data=True)}
    dst_map = {data['name']: data['river'] for _, _, data in dst_net.G.edges(data=True)}

    copy_attrs = ['Q', 'S', 'water_level', 'water_depth', 'U', 'C', 'FR', 'P', 'PRESS', 'R', 'BETA', 'Slop']
    copy_scalar_attrs = [
        'prev_Qb_left',
        'prev_Qb_right',
        'boundary_face_discharge_left',
        'boundary_face_discharge_right',
        'boundary_face_area_left',
        'boundary_face_area_right',
        'boundary_face_width_left',
        'boundary_face_width_right',
        'boundary_face_level_left',
        'boundary_face_level_right',
    ]
    for name, dst_river in dst_map.items():
        src_river = src_map[name]
        for attr in copy_attrs:
            if hasattr(src_river, attr) and hasattr(dst_river, attr):
                getattr(dst_river, attr)[:] = getattr(src_river, attr)
        for attr in copy_scalar_attrs:
            if hasattr(src_river, attr) and hasattr(dst_river, attr):
                setattr(dst_river, attr, getattr(src_river, attr))
        dst_river.Q_old[:] = dst_river.Q
        dst_river.S_old[:] = dst_river.S
        # 主算阶段不再覆写为统一初始水位
        dst_river.Level_init = False
        dst_river.Depth_init = False

    if os.environ.get('ISLAM_COPY_WARMUP_NODE_CACHE', '0') == '1':
        dst_net._internal_node_level_cache = dict(src_net._internal_node_level_cache)


configure_net_options(net, export_png=True)
if output_rivers is not None:
    net.output_river_names = output_rivers
apply_boundaries(net, mode='main')
initialize_rivers(net)

if warmup_hours > 0.0:
    warmup_mode = os.environ.get('ISLAM_WARMUP_MODE', 'constant').strip().lower()
    warmup_save_output = os.environ.get('ISLAM_WARMUP_SAVE_OUTPUT', '0') == '1'
    warm_model_data = dict(model_data)
    warm_model_data['sim_end_time'] = (
        datetime.datetime.strptime(model_data['sim_start_time'], '%Y-%m-%d %H:%M:%S')
        + datetime.timedelta(hours=warmup_hours)
    ).strftime('%Y-%m-%d %H:%M:%S')
    if warmup_save_output:
        warm_model_data['output_path'] = os.path.join(output_path, '_warmup_tmp')
        os.makedirs(warm_model_data['output_path'], exist_ok=True)
    else:
        warm_model_data['output_path'] = os.path.join(output_path, '_warmup_tmp_no_output')

    net_warm = Rivernet(top, warm_model_data)
    configure_net_options(net_warm, export_png=False)
    net_warm.save_outputs = warmup_save_output
    if warmup_mode == 'cyclic':
        apply_boundaries(net_warm, mode='cyclic', warmup_shift_hours=-warmup_hours)
    elif warmup_mode == 'main':
        apply_boundaries(net_warm, mode='main')
    else:
        apply_boundaries(net_warm, mode='constant')
    initialize_rivers(net_warm)

    for _ in net_warm.Evolve(1800):
        pass

    copy_warmup_state(net_warm, net)

for t in net.Evolve(1800):
    net.print_evolve_info()

# 记录固定水位边界“超临界外推”触发次数，便于判断某端是否长期失去边界控制
debug_rows = []
for _, _, data in net.G.edges(data=True):
    r = data['river']
    debug_rows.append({
        'river': data.get('name'),
        'supercritical_in_count': int(getattr(r, 'debug_supercritical_in_count', 0)),
        'supercritical_out_count': int(getattr(r, 'debug_supercritical_out_count', 0)),
    })
pd.DataFrame(debug_rows).sort_values('river').to_csv(
    os.path.join(output_path, 'boundary_supercritical_counts.csv'),
    index=False
)
