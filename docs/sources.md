# 资料与适配证据

核对日期：2026-10-14。官方帮助中心页面更新时间不等于历史 9.0 发布日期；例如 9.0 更新说明仍是旧版本内容。只使用链接与独立整理的操作说明，不在仓库分发厂商 PDF 或授权数据库。

| 来源 | 支持的事实与适用边界 |
|---|---|
| [SimaPro 9.0 更新说明](https://support.simapro.com/en/articles/504166-what-s-new-in-simapro-9-0) | 9.0 数据库系统升级，初始随附 ecoinvent 3.5；不证明用户当前库版本 |
| [文件交换格式](https://support.simapro.com/en/articles/504094-which-file-formats-can-i-import-and-export-in-simapro) | SimaPro 原生 CSV 可交换过程；具体授权存在限制 |
| [File Import/Export](https://support.simapro.com/en/articles/504509-how-do-i-exchange-data-with-other-simapro-users) | CSV 导入/导出入口；数据库交换可能覆盖同名库/方法，需区分 |
| [COM 编程](https://support.simapro.com/en/articles/504670-programming-the-com-interface) | COM 自动控制属于 Developer，不能假定普通授权可用 |
| [Excel 外部链接](https://support.simapro.com/en/articles/504560-linking-data-to-excel) | Developer 专属 |
| [Excel 情景导入](https://support.simapro.com/en/articles/504561-importing-scenarios-from-excel) | Developer 专属 |
| [参数情景](https://support.simapro.com/en/articles/504539-using-parameters-for-scenario-analysis) | 参数可在数据库/项目/过程层使用，实际许可证另核对 |
| [参数许可证](https://support.simapro.com/en/articles/504208-which-simapro-licenses-include-the-parameters-feature) | 当前帮助列 Analyst/Developer/PhD，不以“普通版”推定 9.0 实际能力 |
| [复制结果](https://support.simapro.com/en/articles/504264-can-i-copy-results-to-excel-and-word) | 表格/图形可 Ctrl+C 复制；不是对剪贴板来源的证明 |
| [Market 与 transformation](https://support.simapro.com/en/articles/504202-what-is-the-difference-between-ecoinvent-market-and-transformation-processes) | 背景选择需考虑供应者与市场含义，不能只用文字相似度 |
| [桌面教程入口](https://support.simapro.com/en/articles/504364-simapro-desktop-tutorial) | 当前链接为 SimaPro 10 教程，不作为 9.0 菜单/API 精确契约 |
| [官方 9.5 教程](https://simapro.com/wp-content/uploads/2023/07/SimaPro-Tutorial.pdf) | 通用建模流程参考；明确版本差异，不能保证 9.0 界面一致 |
| [Codex MCP](https://developers.openai.com/codex/mcp) | 本地 stdio command/args/env 和配置方式 |
| [Codex Skill 发现](https://developers.openai.com/codex/skills) | 仓库 .agents/skills 和用户 ~/.agents/skills |

本机只读证据：安装路径为 D:/Program Files/SimaPro/SimaPro.exe，文件版本 9.0.0.48；进程窗口识别成功。本机 Manual/SimaPro9Tutorial.pdf 的正文为 2016 年 report 5.3，并明确基于 SimaPro 8.0.3，因此不能根据文件名把它称作 9.0 专用手册。它用于理解旧桌面工作流，不用于证明 import schema 或授权状态。手册全文提取只存本地 local-evidence，不提交。

原生序列化是基于提供的格式样例和局部模板的候选实现，未做本机真实模板往返。未知段、复杂多段字段、非 9.0、逗号小数和不支持的流会拒绝；没有照搬其它软件或新版本 API。
