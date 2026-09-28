## Context

导出成功后，`main_window._on_export()`（`main_window.py:1496`）调用 `show_delivery(result)` 就结束了。推送是另一条独立链路：`DeliveryCard.push_requested` → `_push_to_ue(code)`（1114 行）→ `_PushWorker` 后台线程 → `_on_push_finished`。两条链路之间没有连接。

推送代码文本由 `show_delivery()` 通过 `card.set_handoff(..., S.HANDOFF_CODE.format(repo=..., manifest=...))` 生成，只在 `result.is_complete()` 时才有。这个事实决定了自动推送的触发点必须在 `show_delivery()` 之后——那里才有代码文本，也才判定过交付是否齐全。

配置侧：`PipelineSettings`（`core/config.py:31`）是一个平铺 dataclass + `from_dict` 手写校验；UI 默认值由 `_apply_export_defaults()`（1035 行）从 settings 回填。现有布尔字段 `write_markdown_report` 走 `bool(data.get(...))`，是现成模板。

## Goals / Non-Goals

**Goals:**
- 交付齐全且开关开启时，导出流程自身发起推送，用户零点击。
- 开关默认开、写进配置文件、跨会话保持。
- 自动推送与手动推送共用同一条通道与同一套状态回显，不产生第二套逻辑。
- 自动推送失败不影响导出成功的判定，也不新增打断性弹窗。

**Non-Goals:**
- 不改交付卡片的常驻布局（`lift-delivery-card-global` 的结论不动）。
- 不做失败重试/退避，不做队列。用户点按钮就是重试。
- 不做跨机器推送。仍然只支持同机回环。
- 不移除手动推送按钮。

## Decisions

### 触发点放在 `_on_export()` 的 complete 分支，而不是 `show_delivery()` 内部

`show_delivery()` 是纯呈现函数，测试里被直接调用了十几次（`test_ui.py:175` 起）。把副作用塞进去，等于每个断言卡片状态的测试都会顺带起一个网络线程。触发点放在 `_on_export()` 的 `result.is_complete()` 分支里，紧跟成功弹窗之后。

**备选**：在 `show_delivery()` 里根据开关触发 —— 否决，污染呈现层且炸测试。

### 复用 `_push_to_ue(code)`，代码文本从 `show_delivery` 的同一处推导

自动路径不自造代码文本。把 `S.HANDOFF_CODE.format(...)` 的构造抽成一个小方法（如 `_handoff_code(result)`），`show_delivery()` 与自动触发都调它，保证两条路推的是同一段代码。

**备选**：从 `DeliveryCard` 读回已设置的代码文本 —— 否决，让主窗口依赖控件内部状态，脆。

### 成功弹窗先于自动推送

`QMessageBox.information` 是模态的，它挡在前面时推送线程照常跑，但状态回显要等用户关掉弹窗才看得见。把推送**发起**放在弹窗**之前**，让线程在用户读弹窗的同时干活；关掉弹窗时往往已经推完了。

### 开关状态：UI 是唯一真值来源，配置只提供默认值

`ExportPanel` 新增 `self._auto_push` 复选框 + `auto_push()` 读取方法，与 `include_rig` 完全同构。`_apply_export_defaults()` 用 `settings.auto_push_after_export` 回填初始勾选。运行期改动不写回文件——现有面板里没有任何字段会写回，破这个规矩会引出"什么时候存"的新问题。

**备选**：勾选变化即写回 `default_settings.json` —— 否决，超出本次范围，且改配置文件是有副作用的动作，需要单独设计。

### 复选框位置：放在 UE 交接分组内、`include_rig` 之后

它描述的是"交付之后怎么送到 UE"，属于 `GROUP_UE_HANDOFF` 分组语义。放在导出按钮旁边会让人误以为是导出参数的一部分。

### 交付不完整时不自动推送

沿用 `show_delivery()` 里的既有判断：只有 `result.is_complete()` 才有交接区、才有代码。不齐全时代码文本压根不存在，自动路径自然短路，无需额外分支。

### 失败仍走 `_on_push_finished` 的现有分支

自动与手动的失败呈现完全一致：卡片红字 + 原因，代码块与按钮保留。不为自动路径加弹窗——用户没主动点，不该被打断。

### 自动推送时交付区收敛为一行，失败才展开

只把动作自动化是半个改动：卡片照旧展开「下一步：在 UE 里导入」+ 代码块 + 推送按钮，等于系统已经把活干了还在催用户干。视觉体量也让人误以为凭空多了一页。

因此 `DeliveryCard` 增加收拢态：只留状态行，产物清单、交接区、推送按钮全部收起；成功保持收拢，失败自动展开（此时代码块与按钮就是兜底路径）。收拢行右侧留【详情】入口，路径随时可查——收拢是默认视图，不是信息丢失。

`_push_status` 从 `_handoff` 内部提到卡片层，否则收拢态下连状态都看不见。

**备选**：成功后整张卡隐藏 —— 否决，产物路径无处可查，且用户会怀疑到底导没导。

### 收拢由主窗口按推送结果驱动，卡片只提供状态

`DeliveryCard.set_collapsed()` 是纯呈现开关，何时收拢由 `_on_export()` / `_on_push_finished()` 决定：发起自动推送即收拢，失败回调里展开。卡片不去猜测流程。

## Risks / Trade-offs

- **[UE 没开时每次导出都要吃一次 3 秒发现超时]** → 发现过程已在后台线程，界面不阻塞；用户可关掉开关。文案里点明"未发现编辑器"是正常降级而非错误。
- **[导出成功弹窗与推送状态竞速，用户可能看到卡片先"正在推送"后被弹窗遮住]** → 可接受：关掉弹窗后卡片就是最终态；反之若等弹窗关闭再推，用户会白等。
- **[自动推送让"导出"这个动作有了网络副作用，测试里更容易误触发线程]** → 触发点只在 `_on_export()`，且受开关控制；UI 测试构造窗口后可显式关掉开关。`stop_push()` 已保证线程不活过窗口。
- **[新增配置字段会让旧 `default_settings.json` 缺该键]** → `from_dict` 用 `bool(data.get("auto_push_after_export", True))` 给默认，缺键即默认开，不报错。
