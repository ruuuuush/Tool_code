## Why

用户填完「UE 内容根目录」导出，然后去 UE 工程里找资产——找不到，以为工具坏了。

工具没坏。Maya 端的导出只写 FBX 和 manifest，它不可能碰 UE：那是另一个进程、另一个 Python 解释器。「UE 内容根目录」是写进 manifest 的**目标声明**，真正建资产的是 UE 侧的 `launch_ue_importer`。

但界面从头到尾没提过这件事。第 ② 步叫「导出设置」，FBX 保存目录和 UE 目标路径并排摆着，读起来就像一次导出全办完。交付卡片列完 FBX / Manifest / 报告就收尾，没有任何"还没结束"的信号。上一轮改版删掉全部说明文字，把这个断层暴露得更彻底——界面既不解释，也不给出口。

管线的价值在于闭环。链条断在最后一米，而且断得无声无息。

## What Changes

- **交付卡片增加交接区**：导出成功后，在产物清单下方给出「下一步：在 UE 里导入」，附带一段已填好本次 manifest 路径的 UE Python 代码。
- **一键复制**：点按钮把代码复制到剪贴板，切到 UE 的 Output Log 直接粘贴即可运行。
- **仅在交付完整时出现**：FBX 与 manifest 都写成了才提示下一步；缺 manifest 时仍然只报交付不完整。
- **导出设置里点明归属**：UE 相关字段标注为交给 UE 侧读取的约定，消除"填了就会自动进 UE"的误解。

## Capabilities

### New Capabilities
<!-- 无新增能力，属于既有 export-ui 的交接契约补充 -->

### Modified Capabilities
- `export-ui`: 新增导出完成后的交接指引要求。

## Impact

- `mtu_maya/ui/style.py`：`DeliveryCard` 增加交接区（代码块 + 复制按钮）
- `mtu_maya/ui/main_window.py`：`show_delivery()` 填充交接代码；复制到剪贴板
- `mtu_maya/ui/strings.py`：交接区文案与代码模板
- `tests/test_ui.py`：交接区的显示条件、路径填充、复制行为
- `README.md`：把 UE 侧步骤提到导出流程的紧后面
- 导出器、manifest、UE 导入逻辑均不改动
