## Why

现有 Maya → UE 工具的检查、导出和桥接分层清晰，基线 412 项测试通过，但离屏截图暴露了字体回退、控件状态不清晰、详情密集和交付卡片占用过多空间等问题。代码审查还发现 UI 的跳过检查选择未传入导出器，导出时重跑检查会丢失选择，部分提示仍引用旧步骤顺序。

## What Changes

- 精修现有深色主题：保留三步向导与蓝色主色，统一中文无衬线字体、间距、按钮和表格层级。
- 修复 checkbox 勾选标记及下拉框箭头的可辨识性，状态不再只靠 emoji 或颜色。
- 对导出设置做轻量分组，检查详情做结构化排版，压缩交付卡片而不移除手动导入、复制代码或曲线预览。
- 导出请求携带会话内跳过检查集合；导出时仍从实时场景重建上下文，保留跳过记录与门禁规则。
- 修正检查提示中的旧步骤编号；不改骨架、曲线、FBX 或 UE 导入业务策略。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `export-ui`: 明确字体、控件状态、详情排版和交付卡片空间约束，保持现有导航和交付行为。
- `export-validation`: 明确从检查 UI 到实际导出重检的跳过选择传递。

## Impact

- `maya_to_ue/mtu_maya/ui/style.py`、`main_window.py`、`strings.py`。
- `maya_to_ue/mtu_maya/export/fbx_exporter.py`、检查提示及现有测试。
- `ExportRequest` 增加默认空集合的跳过字段；现有调用无需修改。
- 无新运行时依赖；继续支持 Maya 2022 的 Python 3.7 / PySide2 及 PySide6。
