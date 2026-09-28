## 1. 配置层

- [x] 1.1 `PipelineSettings` 增加 `auto_push_after_export: bool = True` 字段
- [x] 1.2 `from_dict` 解析该字段：`bool(data.get("auto_push_after_export", True))`，缺键即默认开
- [x] 1.3 `config/default_settings.json` 写入 `"auto_push_after_export": true`
- [x] 1.4 测试：缺键时默认为 True；显式 false 被读成 False；`to_dict` 往返保留该值

## 2. 界面开关

- [x] 2.1 `strings.py` 增加开关标签与说明文案（复选框文本 + 表单左侧标签）
- [x] 2.2 `ExportPanel` 在 `GROUP_UE_HANDOFF` 分组、`include_rig` 之后新增 `self._auto_push` 复选框
- [x] 2.3 `ExportPanel` 增加 `auto_push()` 读取方法，与 `include_rig()` 同构
- [x] 2.4 `_apply_export_defaults()` 用 `settings.auto_push_after_export` 回填勾选状态
- [x] 2.5 测试：默认勾选；配置为 false 时不勾选；`auto_push()` 反映勾选状态

## 3. 自动触发链路

- [x] 3.1 抽出 `_handoff_code(result)`，返回 `S.HANDOFF_CODE.format(repo=..., manifest=...)`
- [x] 3.2 `show_delivery()` 改用 `_handoff_code(result)` 生成交接区代码，行为不变
- [x] 3.3 `_on_export()` 的 `result.is_complete()` 分支中，在成功弹窗**之前**、开关开启时调用 `self._push_to_ue(self._handoff_code(result))`
- [x] 3.4 确认交付不完整与检查阻断两条路径都不会走到触发点

## 4. 测试

- [x] 4.1 开关开启 + 交付齐全 → 推送被发起（打桩 `_push_to_ue`，断言收到的代码等于交接区代码）
- [x] 4.2 开关关闭 + 交付齐全 → 未发起推送
- [x] 4.3 manifest 缺失 → 未发起推送
- [x] 4.4 检查阻断导致未导出 → 未发起推送
- [x] 4.5 自动推送失败 → 导出仍判成功，无额外弹窗，卡片显示失败原因，按钮仍可点
- [x] 4.6 已有 `show_delivery` 相关测试全部保持绿（确认呈现层未被污染）

## 5. 验证

- [x] 5.1 把开关默认值改成 False 跑一遍自动推送测试，确认它变红——否则等于在测空气
- [x] 5.2 `D:\Maya2022\bin\mayapy.exe -m unittest discover -s tests` 全绿
- [x] 5.3 离屏出图确认复选框在 UE 交接分组内、标签与行距与相邻行一致、文字未被裁
- [x] 5.4 Maya 内实测：开着 UE 导出一次，资产直接就位，零点击
- [ ] 5.5 Maya 内实测：关掉 UE 导出一次，卡片显示未发现编辑器，导出仍报成功
- [x] 5.6 README 补一句自动推送开关的说明

## 6. 交付区收敛

- [x] 6.1 `_push_status` 从 `_handoff` 内部提到卡片层，收拢态下仍可见
- [x] 6.2 `DeliveryCard.set_collapsed(bool)`：收起产物行、分隔线与交接区，保留状态行
- [x] 6.3 状态行右侧加【详情/收起】入口，点击切换展开态
- [x] 6.4 `clear()` 复位为展开态，下一轮导出不继承上一轮的收拢
- [x] 6.5 `_on_export()` 发起自动推送时收拢；未自动推送 / 交付不完整时保持展开
- [x] 6.6 `_on_push_finished()` 失败时展开，成功时保持收拢
- [x] 6.7 测试：发起即收拢、成功保持收拢、失败自动展开、开关关闭时不收拢、详情入口可展开
- [x] 6.8 出图确认：收拢态只有一行、成功文案完整不裁；展开态与改动前一致
- [x] 6.9 推送成功后标题改为「已送达 UE」，不再说"可以直接导入"

## 7. 导出入口去重

- [x] 7.1 删掉 `ExportPanel._export_btn`，导出动作只留检查步的导航按钮
- [x] 7.2 `set_export_enabled` / `set_busy` 不再操作已删除的按钮，`_gate_open` 仍是门禁真值
- [x] 7.3 导出期间禁用 `_nav_export_btn`，`finally` 里按门禁恢复
- [x] 7.4 门禁测试改指导航按钮；新增「导出设置步没有导出按钮」测试
- [x] 7.5 出图确认第②步无导出按钮、表单不再与按钮重叠
