from copy import deepcopy
from typing import Dict, List, Tuple
import numpy as np

def adjust_sections_by_river_bed_average(
    river_data: Dict,
    section_data: Dict[str, List[List[float]]]
) -> Dict[str, List[List[float]]]:
    """
    将每个 section 的所有点整体平移，使该 section 的第二列最小值
    对齐到对应计算单元两侧 river pos 的 z 均值。

    约定/假设：
    - river_data['pos'] 长度 = cell_num + 1
    - river_data['section_name'] 长度 = cell_num
      第 i 个 section 对应 pos[i] 与 pos[i+1] 之间的单元
    - section_data[name] 是 [ [x, y], ... ] 列表，第二列为需要平移的值

    返回：
    - 新的 section_data（深拷贝），每个点的第二列被统一加上同一个位移量
    """
    pos: List[List[float]] = river_data['pos']
    names: List[str] = river_data['section_name']
    cell_num: int = river_data['cell_num']

    assert len(pos) == cell_num + 1, "pos 长度应为 cell_num + 1"
    assert len(names) == cell_num, "section_name 长度应为 cell_num"

    out = deepcopy(section_data)

    for i, name in enumerate(names):
        # 计算该单元两侧节点的 z 均值（第三列）
        z_left = pos[i][2]
        z_right = pos[i+1][2]
        z_avg = 0.5 * (z_left + z_right)

        if name not in out:
            # 如果某个 section 名称在 section_data 中不存在，就跳过
            continue

        pts = out[name]
        if not pts:
            continue

        # 当前断面最低值（第二列的最小值）
        min_y = min(p[1] for p in pts)

        # 为了让新最小值==z_avg，需要对所有点的第二列执行：
        # y_new = y_old - (min_y - z_avg) = y_old + (z_avg - min_y)
        shift = z_avg - min_y

        for p in pts:
            p[1] = p[1] + shift

    return out


def adjust_sections_by_section_station_elevation(
    river_data: Dict,
    section_data: Dict[str, List[List[float]]]
) -> Dict[str, List[List[float]]]:
    """
    将每个 section 的最低点对齐到“断面站位”的河底高程。

    这个口径与 `River.interpolate_uniformly()` 保持一致：
    - `section_name` 被视为沿河等距布置的一组断面站位；
    - 这些站位不是单元中心，而是从河段起点到终点的等距断面位置；
    - 因此 section 的绝对高程应对齐到对应断面站位处的河床高程，
      而不是该断面附近单元两端节点的平均高程。

    说明：
    - 对 Islam 网络这类论文案例，节点/汊点床高是按河段端点定义的。
      若按单元平均床高平移 section，会在汊点两侧引入系统性的半格高程错位。
    """
    pos = np.asarray(river_data['pos'], dtype=float)
    names: List[str] = list(river_data['section_name'])
    cell_num: int = int(river_data['cell_num'])

    assert len(pos) == cell_num + 1, "pos 长度应为 cell_num + 1"
    assert len(names) == cell_num, "section_name 长度应为 cell_num"

    seg_len = np.sqrt(np.sum(np.diff(pos[:, :2], axis=0) ** 2, axis=1))
    cum_len = np.insert(np.cumsum(seg_len), 0, 0.0)
    sec_len = np.linspace(cum_len[0], cum_len[-1], len(names))
    sec_bed = np.interp(sec_len, cum_len, pos[:, 2])

    out = deepcopy(section_data)
    for i, name in enumerate(names):
        if name not in out:
            continue
        pts = out[name]
        if not pts:
            continue

        min_y = min(p[1] for p in pts)
        shift = float(sec_bed[i] - min_y)
        for p in pts:
            p[1] = p[1] + shift

    return out

if __name__ == '__main__':
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

    section_data_1_2 = adjust_sections_by_river_bed_average(river_data_1_2,  section_data_1_2)
    print(section_data_1_2)
