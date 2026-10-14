# SimaPro 9.0 桌面操作与文件流程

目标为 Windows SimaPro 9.0 普通桌面授权。操作路径依据官方桌面资料和本机旧版手册整理；菜单译名、按钮、授权及表头以实际 9.0 为准，不依赖屏幕坐标。

## 首次使用

确认 About 中 build 和具体授权，本机核验为 9.0.0.48，不据此推定 Analyst/PhD/Developer。使用软件备份功能保存数据库备份；不要直接复制正在使用的数据库作为可靠备份。

File → New project 建测试项目，填写 Goal and scope；Libraries 选择实际背景库与 Methods。库已安装不等于项目已启用。记录库全名、版本、系统模型、方法全名及版本。无法新建/导出时检查具体授权或演示版限制。

## 创建过程和清单

LCA Explorer → Inventory → Processes → 选择分类 → New，创建 Unit process。Input/output 中先填写 Products and co-products 的参考产品名、数量、单位，表示输出批次，不要求固定为 1 kg。

Materials/fuels 或 Electricity/heat 中选择上游参考产品并填量；先建立前景供应过程，背景从当前启用的授权库选择。双击选择字段或 Find/Search，核对参考产品与单位，不能只凭名称相近连接。

Resources 是自然输入，Emissions to air/water/soil 是直接排放，Waste to treatment 是处理服务。多输出需记录分配。生成器不支持这些复杂行，不能用 material input 代替。

保存并核对数量、单位转换、链接及说明。修改库数据前复制到自己的项目。试剂质量与背景数据集的产品形态/浓度一致。

## 原生导入

选择本机简单 Unit process，File → Export → SimaPro CSV，完整字段、分号、点小数；模板一个过程、一个产品，无排放/参数/废物/替代信用。记录编码。普通表格 CSV 不是 SimaPro 原生 CSV。

`inspect_native_csv_template(native_csv='inputs/native9.csv',native_encoding='utf-8-sig')` 只检查支持的结构，不证明来源。默认 UTF-8，其他编码显式指定 cp1252/gbk。解析器用空行识别段，不支持复杂多段字段、未知段、额外对象、其他软件版本或逗号小数，需要重新校准。

批准映射后 `prepare_simapro9_import` 生成候选。File → Import → SimaPro CSV 导入独立测试项目，阅读错误和重复处理提示，避免覆盖。核对产品、量、单位、供应者、分类、项目；保存日志并重新导出核对。

当前生成器全部 technosphere inputs 写 Materials/fuels，生成分类为 material；实机验收必须核对连接含义。尚未由本机真实导出/导入验证，不是官方保证的序列化器。

## 清单字段

UTF-8 CSV 列头：

```text
process_id,process_name,flow_id,flow_name,flow_role,amount,unit,provider_type,provider_ref,geography,source,notes
```

| 字段 | 含义 |
|---|---|
| process_id / process_name | 前景 ID 和名称，一个 ID 一个名称 |
| flow_id | 在本过程内唯一 |
| flow_name | 流名；reference_output 名用于连接，必须唯一 |
| flow_role | reference_output / technosphere_input / elementary_input / elementary_output / waste_output |
| amount / unit | 对应输出批次的有限正数量 |
| provider_type | technosphere_input 必填 foreground 或 background |
| provider_ref | foreground 为 process_id，background 为搜索词 |
| geography / source / notes | 地域、来源、假设，DEMO 保留标识 |

检查支持五种 role，候选只支持前两种。此清单无分配、环境介质和分布字段，不是完整数据库模式。

背景目录列：`simapro_process_name,reference_unit,geography,library,system_model,version,process_category,source`。`simapro_process_name` 保存 Products 行可连接的参考产品名。审批表保留工具生成的上下文，每流一个 `approved=yes`；语义改变重新生成和审查。

## LCIA

选产品 → Analyze → 设需求量/单位及实际方法 → Calculate。过程每批输出 100 kg、FU 为 1 kg，计算需求是 1 kg；若 FU 为产品中的 1 kg 金属、产品纯度 99%，需求产品为 1/0.99 kg。记录实际参考产品与需求。

Impact assessment → Characterization → Table 检查绝对数值。Network/Tree 看网络，Process contribution 看热点，Inventory 看物质及未表征项。按钮点击不是完成证据。

Ctrl 多选同等功能产品 → Compare → 核对需求量 → Calculate。方法、FU、数据库一致。参数依具体授权；Excel 动态链接、Excel 情景导入和 COM 属于 Developer 功能，不假定普通版具备。

## 结果读取与比较

结果表 Ctrl+C 存本地 CSV/TSV，检查多行表头、百分比和单位。`capture_copied_result_table` 不证明剪贴板来源。表头不在第一行时另存整理后的表格，保留原始文件。

调用示例，元数据填真实值：

```python
normalize_exported_lcia(
    file_path='inputs/baseline_raw.tsv', output_csv='outputs/baseline.csv',
    scenario='baseline', method='实际方法全名及版本',
    database='实际背景库全名及版本', system_model='实际系统模型',
    functional_unit='实际功能单位及质量要求',
    indicator_column='实际类别列名', value_column='实际绝对值列名', unit_column='实际单位列名',
    result_stage='characterization', delimiter='\t', encoding='utf-8-sig')
combine_normalized_lcia_files(['outputs/baseline.csv','outputs/alternative.csv'])
compare_provenance_checked_lcia('outputs/lcia_combined.csv',baseline='baseline')
```

支持 CSV/TSV，不直接读 XLSX；数值用点小数，转换保留原表。阶段必填 characterization/damage_assessment/normalization/weighting/single_score；v0.2 文件从原始结果重新归一。

改善百分比只适用于正基准和越低越好的指标，不能推断所有类别的综合优越性。

## 实机验收

保存：软件/授权/库记录、真实简单过程导出、候选、隔离项目导入日志、逐行核对、实际 FU/方法计算、原始绝对结果、同 FU 情景和比较。先验证手动路径，再校准逐步 UI 输入。

失败也保留证据。不上传授权背景目录、数据库、真实项目、剪贴板或截图。FORMAT_ONLY_NOT_AUTHENTIC 文件仅供代码测试。
