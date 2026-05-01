# ChatGPT 原始设计方案 V0.1

**来源**：用户通过聊天上传的文件《chatgpt关于模拟局部模型的设计方案.md》

**原始 URL**：https://cnbj3-fusion.fds.api.xiaomi.com/chatbot-prod/multimedia/952985697/2d776d1a-fdf3-429a-9b2f-40864b20408b.md

**注意**：原始文件约 89KB，因 web_fetch 截断限制（50000 字符），此处仅保存摘要和关键结构。完整文件请从原始 URL 获取或从本地备份恢复。

---

## 核心内容摘要

### 项目定位
- 不是普通物理模拟器，而是**公理递归生成机**
- 核心主线：九公理 → ACL 公理约束语言 → 层级世界引擎 → 稳定结构封装 → 下一层递归 → 物理模块验证 → 理论回写

### 工程坐标系（九层）
| 层 | 说明 |
|---|---|
| T | Theory，理论来源与章节追踪 |
| ACL | Axiomatic Constraint Language，公理约束语言 |
| L | Layer，层级世界规格（五元组 S, N, T, Q, C） |
| E | Engine，世界演化引擎 |
| M | Model，学习模型（CNN → U-Net → GNN → Transformer） |
| V | Validator，验证器（七类指标） |
| R | Recursion，稳定结构封装与递归（五条件：寿命/边界/闭合/交互/压缩） |
| P | Physics Modules，WorldBase 物理模块 |
| D | Documentation，文档与理论回写 |

### 九公理工程定位
| 公理 | 工程角色 | 代码形态 |
|---|---|---|
| A1 差异/层级方向 | 存在条件 | state measure / difference operator |
| A2 二元或离散编码 | 类型约束 | state schema / projection |
| A3 有限离散 | 空间约束 | finite lattice / graph |
| A4 局部最小变易 | 演化约束 | variation loss |
| A5 守恒律 | 不变量约束 | conservation loss |
| A6 耦合/DAG | 关系约束 | graph constraint / mask |
| A7 稳定性闭合 | 长程约束 | rollout validator |
| A8 对称偏好 | 选择偏置 | symmetry score |
| A9 最小充分实现 | 压缩约束 | complexity penalty |

### 阶段施工计划
- **阶段 0**：理论到工程接口（M0）
- **阶段 1**：L0 最小离散世界（4×4 → 8×8 → 16×16）
- **阶段 2**：稳定结构检测与封装（关键转折点）
- **阶段 3**：L1 高层单元世界（图结构）
- **阶段 4**：标准物理 benchmark
- **阶段 5**：引力、连续极限、电磁
- **阶段 6**：内部态、不可逆、强弱相互作用
- **阶段 7**：量子模块

### 第一批实验
- EXP-L0-001：4×4 最小公理 rollout
- EXP-L0-002：8×8 守恒约束实验
- EXP-L0-003：16×16 局部变易实验
- EXP-L0-004：加入差异度量 A1 观察
- EXP-L0-005：稳定结构候选检测
- EXP-L0-006：有监督规则学习对照组

### 里程碑
- M0：理论接口完成
- M1：L0 可以公理约束 rollout
- M2：L0 出现可检测稳定结构
- M3：L0 到 L1 封装成功（最重要）
- M4：九公理可跨 L0/L1 复用
- M5：标准物理 benchmark 完成
- M6：WorldBase 第一批物理模块进入

---

## 后续讨论中对原始设计的修改

详见 `设计决策记录.md`。关键修改：

1. **A1**：从"差异度量"改为"差异源（太阳模型，持续+1）"
2. **A6**：从独立约束改为"差异从源到汇的有序流向"
3. **A8**：从"对称偏好"改为"差异汇（持续-1）"
4. **A7**：增加"活结构/死结构/噪声"三分
5. **A9**：从"压缩惩罚"改为"升维触发器（素数模型）"
6. **新增**：区域分类机制（死寂→吸收体，爆炸→辐射源）
7. **新增**：A5+A9 联动升维机制
