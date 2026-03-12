result_dir=/Users/xingy/Downloads/River_net_gpt/result/exp_handoff_core_nofine_rfix_40h_20260312
real_dir=/Users/xingy/Downloads/River_net_gpt/result/Islam_real_data
flow_direction_mode=auto_dominant_positive
applied_flow_sign=1

文件说明:
- nse_summary.csv: 四条目标曲线的 NSE/Bias/RMSE
- node*_real.csv: 原始论文/实测对比数据
- node*_sim_raw.csv: 模型原始输出时序
- node*_compare_on_real_time.csv: 插值到观测时刻后的对比数据
- *_compare.png: 单图
- river11_four_curves_compare.png: 四图汇总
- internal_node_history.csv: 若存在，则附带保存汊点迭代后的结点时序