# 心跳记录 2026-05-22 00:40

## 行动：修复跨层级引力计算Bug

### 问题分析
系统日志显示 `hierarchical_evolver.py` 中的 `_compute_cross_layer_gravity` 方法报错：
- Line 159: `total_mass = sum(source_masses[j] for j in source_bits)` 
- Line 212, 232: `_apply_cross_layer_gravity_modulation` 相关错误

### 根本原因
`enc_bit.bit_id` 只是封装比特在列表中的顺序（0, 1, 2...），
但实际在目标层的索引应该是 `n_active + enc_bit.bit_id`。
因为新层状态格式是 `[活跃比特..., 封装比特...]`。

### 修复
```python
# 之前（错误）：
for enc_bit in enc_bits:
    target_idx = enc_bit.bit_id  # ❌ 错误

# 之后（正确）：
n_enc = len(enc_bits)
n_active = N_target - n_enc
for enc_bit in enc_bits:
    target_idx = n_active + enc_bit.bit_id  # ✅ 正确
```

### 验证结果
分层封装实验成功完成所有层级：
- L0: N=48, sealed=True, 870 cycles → L1 (12 bits)
- L1: N=12, sealed=True, 3 cycles → L2 (3 bits)  
- L2: N=3, sealed=True, 3 cycles → L3 (3 bits)
- L3: N=3, OPEN

### Git提交
`4a8e4e5 fix: 修复跨层级引力计算中封装比特索引偏移错误`
