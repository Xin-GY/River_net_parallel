def compute_elevation(known_elev, slope, distance, direction="down"):
    """
    根据堤坡换算另一点的高程

    参数：
        known_elev : float
            已知点高程 (m)
        slope : float
            堤坡，垂直/水平（如 1/3 → 0.3333）
        distance : float
            水平距离 (m)
        direction : str
            "up"   表示往高处推算
            "down" 表示往低处推算

    返回：
        float : 另一点高程
    """
    delta_h = slope * distance
    if direction == "up":
        return known_elev + delta_h
    elif direction == "down":
        return known_elev - delta_h
    else:
        raise ValueError("direction 只能是 'up' 或 'down'")


# ================= 使用示例 =================
# 已知堤顶高程 100 m，堤坡 1:3，水平距离 6 m，求堤脚高程
# print(compute_elevation(known_elev=100, slope=1 / 3, distance=6, direction="down"))  # 结果 98.0
#
# # 已知堤脚高程 95 m，堤坡 1:2，水平距离 4 m，求堤顶高程
# print(compute_elevation(known_elev=95, slope=1 / 2, distance=4, direction="up"))  # 结果 97.0


print(compute_elevation(known_elev=1.5, slope=0.00030, distance=2000, direction="up"))
