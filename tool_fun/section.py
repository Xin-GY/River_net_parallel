from copy import deepcopy
from typing import List, Dict, Tuple, Iterable

def build_river_and_sections(
    base_section: List[List[float]],
    cell_num: int,
    start_elev: float,
    end_elev: float,
    length: float,
    y_const: float = 0.0,
    y_nodes: Iterable[float] | None = None,
) -> Tuple[Dict, Dict]:
    """
    生成 river_data 与 section_data：
      - river_data['pos'] 为节点坐标列表，每个元素是 [x, y, z]
      - section_data 的数量等于 cell_num（每个单元一个断面）
      - 每个 section 的纵坐标整体平移，使最低点与对应节点的 z 对齐
    """
    if cell_num <= 0:
        raise ValueError("cell_num 必须为正整数")
    n_node = cell_num + 1
    dx = length / cell_num

    # —— 生成 x 坐标（均匀布点）
    xs = [i * dx for i in range(n_node)]

    # —— 生成 y 坐标
    if y_nodes is not None:
        y_list = list(y_nodes)
        if len(y_list) != n_node:
            raise ValueError(f"y_nodes 长度应为 {n_node}，实际为 {len(y_list)}")
    else:
        y_list = [float(y_const)] * n_node

    # —— 线性插值 z 坐标
    pos = []
    for i, (x, y) in enumerate(zip(xs, y_list)):
        t = i / (n_node - 1)
        z = start_elev * (1 - t) + end_elev * t # 节点高程
        pos.append([float(x), float(y), float(z)])

    # —— 每个单元一个断面，并将最低点对齐到对应节点的 z
    section_names = [f"se{i+1}" for i in range(cell_num)]
    section_data = {}
    base_min = min(p[1] for p in base_section)  # 基础断面的最低点

    for i, name in enumerate(section_names):
        cell_z = pos[i][2]   # 用单元“起点节点”的 z 作为床面
        shift = cell_z - base_min
        new_section = [[p[0], p[1] + shift] for p in deepcopy(base_section)]
        section_data[name] = new_section

    river_data = {
        "cell_num": int(cell_num),
        "pos": pos,
        "section_name": section_names
    }

    # —— 打印输出
    print("river_data = {")
    print(f'    "cell_num": {river_data["cell_num"]},')
    print(f'    "pos": {river_data["pos"]},')
    print(f'    "section_name": {river_data["section_name"]}')
    print("}")
    print("section_data = {")
    for k, v in section_data.items():
        print(f"    '{k}': {v},")
    print("}")

    return river_data, section_data

# ==================== 使用示例 ====================
if __name__ == "__main__":
    base_sec = [[0, 30], [0, 0], [30, 0], [30, 30]]

    # 例1：y 全部为 1.0（常数）
    build_river_and_sections(
        base_section=base_sec,
        cell_num=25,         # 5 个单元 → 6 个节点
        start_elev=0.4,
        end_elev=0.0,
        length=2500,
        y_const=1
    )

    # 例2：自定义每个节点的 y（如沿线小幅摆动）
    # y_nodes 长度需为 cell_num+1
    # build_river_and_sections(
    #     base_section=base_sec,
    #     cell_num=5,
    #     start_elev=0.8,
    #     end_elev=0.2,
    #     length=1200.0,
    #     y_nodes=[1.0, 1.0, 1.1, 1.0, 0.9, 1.0]
    # )
