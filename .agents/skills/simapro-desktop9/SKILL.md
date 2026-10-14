---
name: simapro-desktop9
description: 用 SimaPro 9.0 Windows 桌面版辅助 LCA 建模、前景清单检查、授权背景数据匹配、过程导入候选、原生 LCIA 操作和情景结果比较。适用于普通桌面授权；不把 Developer COM、云端 API 或本地计算当作普通版功能。
---

# SimaPro 9.0 建模助手

使用本地 `simapro9` MCP，先调用 `simapro9_workflow` 检查连接。未连接时仍可做建模设计和手动指导，明确未执行步骤。文件参数均为 `SIMAPRO_WORKSPACE` 下相对路径。工程的 `scripts/install.ps1` 提供部署；本 Skill 复制到用户目录后，references 仍可独立使用。

## 选择工作方式

- 学习软件、建过程、运行 LCIA、导出结果：读 [操作指南](references/desktop-workflow.md)。菜单译名和按钮以实际界面为准。
- 研究方案或金属回收模型：读 [建模与清单审查](references/lca-methodology.md)。先设计完整网络，再选择录入方式。
- 自动准备导入和情景：使用下面流程。生成器仅支持单输出 material 前景过程和正数 technosphere inputs。排放、废水、固废、多输出、避免生产信用须在软件完整录入，不能为使工具通过而删去。

## 开始建模

确认 build、具体授权等级、背景库/版本/系统模型、LCIA 方法全名及版本。“9.0 普通版”不足以确定参数和 Monte Carlo 能力。沿用已知信息，不重复询问。

记录目标、功能单位、参考流、系统边界、地域/年份、分配及替代假设。FU 包括影响比较的纯度或性能，例如“获得 1 kg 达到指定纯度的回收铟”；不能默认回收产品与原生产品等效。

## 清单、匹配与导入

1. 按操作指南的清单字段整理 canonical CSV，调用 `validate_lci`、`summarize_lci`。工具检查数值/引用/单位/来源，不证明质量与能量守恒，需另按工艺核对。
2. 从用户允许的小范围真实原生导出调用 `build_local_background_catalog`，或整理本机核对的参考产品目录。目录保留本地，不随代码上传授权数据库。可连接参考产品名可能不同于过程说明标题。
3. 调用 `suggest_background_links`，分数只表示文字相似度。核对技术、地域、年代、market/production、系统模型、单位和实际可用性。用户已明确授权匹配时可记录 `approved=yes`；含糊匹配需澄清。每流只批准一个候选；流名、请求产品或地域变化后重新审查，数量情景可沿用供应者。
4. 导出本机一个全字段、单产品、无排放/参数的 Unit process 模板，调用 `inspect_native_csv_template`。默认 UTF-8；旧导出显式给出 `native_encoding='cp1252'` 或 `'gbk'`，不猜编码。不能用 `NOT_AUTHENTIC` 格式样例做真实导入。
5. 仅对全部支持的清单调用 `prepare_simapro9_import`。检查候选和 manifest；这不会在软件内创建过程。不支持的流采用完整手动录入或经验证的扩展。
6. 首次实机导入记录备份位置，创建独立测试项目，File → Import → SimaPro CSV。核对错误、重复处理、数量/单位、所有链接和项目归属。沿用当前会话已给出的具体写入授权，不把技术门槛变成重复确认。出现覆盖提示或未经授权的替换，停止相应写入并保存日志。

## LCIA 与结果

SimaPro 中选产品 → Analyze → 设置需求量和安装的方法 → Calculate。需求量对应 FU 的参考流，不一定等于过程输出批量。确认表格显示绝对值，不把图中百分比当作 kg CO₂-eq。

`gui_inspect` 只读，校验窗口所属 SimaPro.exe。`gui_single_step` 默认关闭；用户授权桌面操作后才启用，输入要求本次观测的精确窗口标题。`approval_token` 是确认字段，不是凭证或授权来源。逐步观测并保存截图；按键不证明导入/计算成功。控件、焦点或对话框不明确时停止输入并说明状态。

表格 Ctrl+C 后可调用 `capture_copied_result_table`，剪贴板来源仍需核对。`normalize_exported_lcia` 明确实际列名、分隔符、编码、方法、数据库/版本、系统模型、FU 和必填 **result_stage**：`characterization`、`damage_assessment`、`normalization`、`weighting` 或 `single_score`。保留原始表格与计算设置。

`combine_normalized_lcia_files` 合并后用 `compare_provenance_checked_lcia` 比较。v0.3 结果 CSV 新增必填 `result_stage`，旧文件从原始导出重新归一，不能猜阶段。核对缺失类别；方法、阶段、数据库、系统模型、FU 或单位不同不相减。元数据匹配只证明标签一致，不证明来源或模型质量。

## 情景与交付

`create_lci_scenarios`、`prepare_scenario_import_batch` 对一个流生成 1–20 个正数倍率情景。倍率 1 可作为基准，每批独立测试项目；S01 等后缀只在该批内唯一。属于单因素敏感性分析，不是 Monte Carlo。收率变化会同步影响多个投入，不能只修改输出或电耗就当作完整收率情景。

各情景在 SimaPro 分别计算。交付模型设计、清单/映射、候选/哈希、实际计算设置、原始结果/比较及未解决假设。准确标注状态：设计完成 → 文件生成 → 导入验证 → 原生计算验证；缺少后两项证据不能宣称全自动建模与计算已完成。
