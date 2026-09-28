## Context

主题是一整份 QSS 字符串（`style.py` 的 `APP_QSS`），按控件类型选择器组织。`QLineEdit` 那条规则是为导出表单里的独立输入框写的：`padding: 6px 8px` + 圆角 + 聚焦描边，在 32px 高的独立控件上很合适。

表格进入编辑态时，`QStyledItemDelegate` 创建的编辑器同样是一个 `QLineEdit`，父级是 view 的 viewport。类型选择器不区分"独立控件"和"内嵌编辑器"，于是那套表单度量原样落到编辑器上。

叠加效应：
- 表单 padding 让编辑器 `sizeHint().height()` = 34px
- 片段表行高 = 28px
- `QTableView::item { padding: 5px 4px }` 又让 `updateEditorGeometry` 给出的矩形只剩 19px
- 字体高度 18px

结果是 19px 的框里塞 18px 的字，加上内部还要扣 padding —— 只剩几像素可见。

## Goals / Non-Goals

**Goals:**
- 单元格编辑器完整显示文本。
- 约束覆盖将来可能出现的编辑器类型，而不只是修当前这一个。
- 行距与可编辑性解耦。
- 回归测试能真正抓住这个缺陷。

**Non-Goals:**
- 不改独立表单输入框的观感——那套 padding 在表单里是对的。
- 不引入自定义 delegate 来控制编辑器外观；样式问题用样式解决。
- 不追求编辑器与单元格像素级贴合。

## Decisions

### 决策 1：用后代选择器 `QAbstractItemView QLineEdit`，而不是给编辑器加 objectName

后代选择器一次覆盖所有 item view 内的输入类控件，且对将来新增的列类型自动生效。选 `QAbstractItemView` 而非 `QTableView`，是因为检查树将来若变成可编辑，同样受益。

规则里同时列出 `QComboBox` / `QSpinBox` / `QDoubleSpinBox`——当前用不上，但这正是防复发的点：新增下拉列时不需要有人记得回来补样式。

*备选*：在 delegate 的 `createEditor()` 里逐个 `setStyleSheet`。否决——把样式散进逻辑代码，且每种编辑器都要记得写一遍，正是要避免的复发模式。

### 决策 2：行距改由行高承担，item 垂直内边距降到 2px

`QTableView::item` 的 padding 同时影响两件事：视觉行距，以及 `updateEditorGeometry` 交给编辑器的矩形。用它调行距，等于每次调行距都在改可编辑性——这两件事不该耦合。

行距改用 `setDefaultSectionSize(30)`；只读的检查树用 `QTreeView::item { min-height: 24px }` 恢复观感。树只读，min-height 不会波及编辑器。

### 决策 3：断言"内边距开销"，不断言高度

这条是排查过程直接换来的。前三版测试全部写错，且**每一版在把 padding 改回缺陷值后依然是绿的**——等于什么都没测：

| 度量方式 | 为什么测不到 |
|---|---|
| `editor.height()` | 控件高度不变，被裁的是内容区 |
| `editor.contentsRect()` | Qt 的 contentsRect 不反映 QSS padding |
| `sizeHint() <= rowHeight` | 方向对，但随字体大小浮动；测试环境字体 12px 时刚好边界通过 |

最终采用 `sizeHint().height() - fontMetrics().height()`，即"内边距与边框吃掉多少像素"。这个值只由 QSS 决定，与字体、DPI 无关：缺陷状态 18px，修复后 4px，阈值取 10px。

**只有把 padding 改回缺陷值、确认测试变红之后，这个测试才算数。** 前三版没做这一步，所以三次都没发现自己在测空气。

### 决策 4：测试必须先 `apply_theme`

缺陷存在于样式表里。不应用主题的话，断言跑在 Qt 默认样式上，永远通过。

## Risks / Trade-offs

- **后代选择器可能影响未来某个刻意需要厚内边距的内嵌控件** → 届时用更具体的选择器覆盖即可；默认紧凑对内嵌编辑器是正确的。
- **10px 阈值是经验值** → 它落在缺陷值 18 与修复值 4 的中间，两侧余量都够；DPI 变化影响字体而非内边距，阈值不随之漂移。
- **行高写死 30px** → 高 DPI 下可能偏紧；真出现时应改为按 `fontMetrics` 计算，而不是回头去加内边距。
