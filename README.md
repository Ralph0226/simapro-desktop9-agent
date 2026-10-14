# SimaPro 9.0 Desktop Agent — Codex Skill + MCP (v0.3)

**适用：Windows 10/11、SimaPro Desktop 9.0 普通桌面授权、Codex、Python 3.12（本机已验证）。**

**当前状态：30 项本地测试、MCP stdio 握手/15 个工具发现及调用测试通过；本机 SimaPro.exe build 9.0.0.48 与只读窗口识别已核验。支持清单检查、本地背景候选、导入候选、单因素情景和结果处理。真实原生 CSV 导入及 SimaPro LCIA 计算尚未验收，不能把上述测试当作完整软件自动化成功。**

本工程不使用 COM、云端 API 或 Excel 动态链接。官方将 COM 自动控制、Excel 外部链接和 Excel 情景导入列为 Developer 功能；参数与 Monte Carlo 仍需核对具体授权等级。实际 LCIA 由 SimaPro 自身执行。

## 快速开始

在本工程目录运行（创建本地环境、执行检查；加第二个参数才注册用户 Skill 和 MCP）：

```powershell
.\scripts\install.ps1 -GuiDependencies -RegisterCodex
```

脚本使用本机 Python 3.12。已存在的同名 Skill 或 MCP 配置会停止并提示检查，不覆盖；配置备份仅存本地。GUI 输入默认关闭。重新打开 Codex 后调用 `$simapro-desktop9` 或 `simapro9_workflow()`。

完整软件指导见 [桌面操作指南](.agents/skills/simapro-desktop9/references/desktop-workflow.md)，金属回收模型见 [建模审查](.agents/skills/simapro-desktop9/references/lca-methodology.md)，本机检查及未验证项见 [验收报告](docs/verification.md)。

v0.3 结果规范新增必填 `result_stage`（characterization/damage_assessment/normalization/weighting/single_score）；旧规范化结果从原始表重新处理。原生模板默认 UTF-8，其他编码必须显式指定 `native_encoding`。这些要求防止混用计算阶段及中文乱码。

## 目录

```
.agents/skills/simapro-desktop9/SKILL.md   # Agent 工作流
.agents/skills/simapro-desktop9/references/  # 格式和科研审计说明
mcp_server/server.py                      # FastMCP / stdio
mcp_server/core.py                        # 原始通用清单 QA / 灵敏度
mcp_server/desktop9.py                    # 桌面 9.0 导入候选、目录、匹配、结果
mcp_server/gui9.py                        # 可选 Windows 安全 GUI 单步
mcp_server/requirements*.txt
examples/*                                 # 全是虚构的格式样例
scripts/self_check.ps1
configs/config.toml.example
AGENTS.md
tests/*
docs/sources.md
```

## 1. Windows 上的安装（推荐路径不带空格）

打开 Windows PowerShell（非管理员即可），将解压后的根目录放在例如 `D:\LCA-Agent\simapro-desktop9`：

```powershell
cd D:\LCA-Agent\simapro-desktop9
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r .\mcp_server\requirements.txt
$env:SIMAPRO_WORKSPACE = (Get-Location).Path
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

如果以后希望 Agent 与**正在打开且可见的 SimaPro 9.0 窗口**交互，再按需安装 GUI 可选项（Windows 登录桌面、非无头、同用户权限）：

```powershell
.\.venv\Scripts\python.exe -m pip install -r .\mcp_server\requirements-windows-gui.txt
```

GUI 默认是**关闭**的。它依赖实际 Win32 控件情况，老软件自绘控件可能无法由 Win32 自动定位。启用后仍需每个动作确认、明确窗口名称、保存前后截图。软件直接计算/结果真实性需要另外验收。

## 2. Codex MCP 配置

编辑用户目录下 `%USERPROFILE%\.codex\config.toml`，添加（请替换成你本机路径，**不要原样使用 D 盘示例路径**）：

```toml
[mcp_servers.simapro9]
command = 'D:\LCA-Agent\simapro-desktop9\.venv\Scripts\python.exe'
args = ['D:\LCA-Agent\simapro-desktop9\mcp_server\server.py']
startup_timeout_sec = 30

[mcp_servers.simapro9.env]
SIMAPRO_WORKSPACE = 'D:\LCA-Agent\simapro-desktop9'
SIMAPRO_GUI_ENABLED = '0'
```

重启 Codex，运行 `codex mcp get simapro9`；Skill 位于 `.agents/skills/simapro-desktop9/SKILL.md`，在仓库中使用时可发现。用户级目录为 `%USERPROFILE%\.agents\skills\simapro-desktop9\`，安装脚本会复制完整 Skill 及 references。调用 `simapro9_workflow` 验证工具连接。

## 3. 第一次配置 SimaPro 9.0（必做）

1. **先备份**数据库。新建空白 `AGENT_TEST_9` 项目，绝不直接在科研正式项目里验证导入。
2. SimaPro 9.0 中手动创建一个只有 **1 个 reference product** 的非常简单的 `material` 过程；没有排放、废物、回收信用及多输出。不使用复杂参数；保证有 `Materials/fuels` 字段。
3. 在该过程的列表选择它，使用 **File → Export**，文件格式选择 **SimaPro CSV**，分隔符选择 `Semicolon`，十进制点 `.`，包括过程的所有字段、选择恰好一个过程；保存为 `inputs/native9_simple_process_export.csv`。注意不是 `Export to platform`、不是普通 Excel CSV。
4. 如能合法导出**小范围**背景数据库过程，同样生成原生 CSV，MCP 的 `build_local_background_catalog` 可以抽取参考产品名称与单位；否则手工维护本地 `licensed_catalog.csv`（参考示例格式），名称必须和 SimaPro 中实际找到的产品/过程完全一致。不要批量提取/公开授权数据库。
5. 记录 SimaPro 9.0 build、背景数据库（如实际 ecoinvent 版本/系统模型）、安装 LCIA 方法/版本、GUI 语言与显示缩放比例。**不能把 9.0 的默认 ecoinvent 3.5 当作安装事实。**

> `examples/native_template_FORMAT_ONLY_NOT_AUTHENTIC.csv` 是**代码格式测试样品**，不是真的 SimaPro 导出，不得用它验证正式导入。原生候选生成器只支持简单 material、一个参考产品和不含废物流的前景过程；含排放/废水/固废及避免负担时会拒绝，而不是偷偷遗漏。

## 4. 首个成功路径（从清单到 SimaPro 原生计算）

**A. 数据输入**：按 `examples/desktop9_simple_lci_DEMO.csv` 结构创建 `inputs/lci.csv`。其中 `process_id` 唯一、`flow_role` 为 `reference_output` 或 `technosphere_input`（当前原生候选生成仅支持这两种）、`provider_type` 前景或背景、`provider_ref` 前景为过程 ID，背景为搜索词。示例中的数量和数据集名均为虚构。

**B. 质量检查**：调用 `validate_lci('inputs/lci.csv')`，校验金额/单位、来源、前景引用与循环关系。

**C. 准备背景数据索引**：`build_local_background_catalog('inputs/authorized_export.csv','inputs/licensed_catalog.csv','ecoinvent','3.5','cut-off','My own licensed export YYYY-MM-DD')`（只有当以上标签**确实准确**时才可填写），或手动创建符合字段的本地 CSV。此工具只识别真实原生 CSV 的 Products 行，不联网、无隐形 ecoinvent 数据。

**D. 匹配审批**：调用 `suggest_background_links('inputs/lci.csv','inputs/licensed_catalog.csv','outputs/map_review.csv')`。候选匹配是字符串近似，不是科学同义判断；打开 `map_review.csv` 按电压等级、国家、时间、系统模型、单位、用途、技术类型核查。对每个 `(process_id,flow_id)` **只批准一条**，把 `approved` 改为 `yes`。

**E. 构建原生导入候选**：

```
prepare_simapro9_import(
  inventory_csv='inputs/lci.csv',
  approved_mapping_csv='outputs/map_review.csv',
  authentic_template_csv='inputs/native9_simple_process_export.csv',
  candidate_csv='outputs/import_baseline_CANDIDATE.csv',
  scenario_suffix='BASE'
)
```

它会产生 `outputs/import_baseline_CANDIDATE.csv` 与 `.manifest.json`，状态为 `GENERATED_NOT_IMPORTED_NOT_CALCULATED`。**首次导入需要对照真实 SimaPro 9.0 的错误报告调校格式**，不能直接声称 100% 兼容。

**F. SimaPro 内导入**：在备份后的测试项目中使用 `File → Import`，文件格式选择 `SimaPro CSV`，检查目标项目、对象链接方式与替换已有过程选项。首次导入不要选择自动覆盖。导入结束必须回到过程列表，核对过程总数、输入值、参考产品、背景过程链接、单位、质量平衡和网络结构。验收后才能迁移到正式项目。

**G. 执行 LCIA**：在 SimaPro 9.0 中选择 reference product/FU、软件内当前可用的方法和表征结果，执行计算。GUI 可在实现控制检测、截图、逐动作经授权后协助打开菜单、进行快捷键操作；**此项目没有通过 API 触发 SimaPro 计算的能力**。可参考 `gui_inspect()` 和 `gui_single_step()`，务必由研究者进行计算结果核验。

**H. 结果导出**：结果表 Ctrl+C 后保存原始表格，整理为带单行表头的 CSV/TSV。`normalize_exported_lcia` 显式指定列名和 `result_stage`；数字须采用点小数。只读取绝对数值，图中百分比不是绝对 LCIA。合并/比较会核对 FU、方法、阶段、数据库、系统模型和单位，但不自动证明标签及来源真实。示例调用见桌面操作指南。

## 5. 情景批量建模

`create_lci_scenarios('inputs/lci.csv','P01','F04',[0.8,0.9,1.1,1.2],'outputs/scenarios')` 为指定流生成最多 20 个 CSV 文件，每个文件代表不同物耗/电耗假设。Agent 可调用 `prepare_scenario_import_batch`，自动为各情景创建前景清单、不同 `scenario_suffix` 的原生导入候选和独立审计 manifest。千万不要用同一个 reference product 名称覆盖其它情景。

SimaPro 9.0 普通版中参数支持情况取决于具体许可证。此包的参数扰动是在**外部 CSV 层**进行，**不是**调用了 SimaPro Developer 独有的 Excel 情景导入。

## 6. GUI 操作（审慎启用）

- `gui_inspect(max_controls=100)`: 只读探测 Win32 控件，当前 Windows 用户须已启动 SimaPro。
- `capture_copied_result_table(output_tsv=...)`：用户先在 SimaPro 结果表按 `Ctrl+C`，Agent 从 Windows 剪贴板读取原始制表符结果表保存本地；需检查来源并标注具体方法和功能单位。
- `gui_single_step` 默认关闭；授权桌面操作后设置 `SIMAPRO_GUI_ENABLED='1'` 并重启。输入需要 `gui_inspect` 返回的精确 `expected_window` 和 `approval_token='I_APPROVE_GUI_STEP'`；该固定字符串不是身份凭证，不能代替用户授权。保留行动前后截图及审计记录。
- 不提供所谓“按一次按钮全自动计算+证明成功”的假指令。操作是否成功，须通过 SimaPro 实际界面状态、导出结果与元数据验证。保持固定窗口状态与缩放比例；勿在远程锁屏/桌面会话断开时启用。

## 7. MCP 工具清单

| 工具 | 本地行为 | 是否真实 SimaPro 计算 |
|---|---|---|
| `simapro9_workflow` | 9.0 操作核对清单 | 否 |
| `validate_lci`, `summarize_lci` | 清单检验与汇总 | 否 |
| `build_local_background_catalog` | 根据授权 CSV 构造本地参考产品目录 | 否 |
| `suggest_background_links` | 候选索引 + 人工批准表 | 否 |
| `inspect_native_csv_template` | 验证模板头和结构 | 否 |
| `prepare_simapro9_import` | 准备过程文件、SHA-256审计 | 否；只供导入 |
| `create_lci_scenarios`, `prepare_scenario_import_batch` | 批量参数扰动、独立的导入候选生成 | 否 |
| `gui_inspect`, `gui_single_step`, `capture_copied_result_table` | Win32 控件检测、单步辅助、剪贴板结果采集 | 不保证；操作后需验收 |
| `normalize_exported_lcia` | 用户导出结果规范化 | 否 |
| `combine_normalized_lcia_files`, `compare_provenance_checked_lcia` | 合并结果与方法/FU/数据库一致性审查 | 否 |

## 8. 工作原则

- 单一功能单位、系统边界和分配规则；不要把 midpoint 类别加总。
- 数据库检索以**许可证下真实存在**的参考产品为准；不能仅因文本相似就默认正确。
- 环境影响属于 SimaPro 软件实际产生的结果；`examples/` 全部是演示数据，不用于论文。
- 任何本地导入尝试前备份数据库、隔离项目、避免覆盖和循环。
- 比较结果必须保存原始结果表、SimaPro 版本、数据版本、LCIA 方法版本和 FU。

## 官方/开放资料

- [SimaPro 文件交换支持](https://support.simapro.com/en/articles/504094-which-file-formats-can-i-import-and-export-in-simapro)
- [SimaPro CSV 项目交换](https://support.simapro.com/en/articles/504509-how-do-i-exchange-data-with-other-simapro-users)
- [SimaPro 9.0 信息](https://support.simapro.com/en/articles/504166-what-s-new-in-simapro-9-0)
- [CSVmaker](https://simapro.com/products/csv-maker/)
- [SimaPro COM Developer 专属](https://simapro.com/wp-content/uploads/2024/11/ProgrammingTheSimaProCOMinterface.pdf)
- [Excel 外部链接 Developer 专属](https://support.simapro.com/en/articles/504560-linking-data-to-excel)
- [Excel 情景导入 Developer 专属](https://support.simapro.com/en/articles/504561-importing-scenarios-from-excel)
- [SimaPro 结果复制](https://support.simapro.com/en/articles/504264-can-i-copy-results-to-excel-and-word)
- [开源 SimaPro CSV 格式描述，仅供辅助识别](https://github.com/GreenDelta/olca-simapro-csv/blob/main/format.md)
