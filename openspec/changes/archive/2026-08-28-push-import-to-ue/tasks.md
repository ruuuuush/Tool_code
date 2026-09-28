## 1. 协议客户端

- [x] 1.1 新建 `bridge/ue_remote.py`：协议常量、`build_message()` 构造、`parse_message()` 校验（魔数/版本不符即丢弃）
- [x] 1.2 `local_ipv4s()`：枚举本机 IPv4，`127.0.0.1` 排最前
- [x] 1.3 `discover(timeout)`：逐接口多播 ping，返回 `EditorNode`（节点 id、接口、工程名、引擎版本）或 None
- [x] 1.4 忽略 source 等于自身 node id 的消息

## 2. 命令通道

- [x] 2.1 `execute(node, code, timeout)`：`bind(port=0)` 动态取端口 → 发 `open_connection` → `accept()` → 发 `command`（`ExecuteFile` 模式）→ 收 `command_result`
- [x] 2.2 结果封装为 `PushResult(ok, message, output, editor)`，任何失败都返回而不抛出
- [x] 2.3 每一步有独立超时；退出路径确保套接字关闭
- [x] 2.4 收尾发 `close_connection`
- [x] 2.5 新增 `on_listening` 回调暴露实际端口（端口由系统分配，外部无从得知）

## 3. 顶层 API

- [x] 3.1 `push(code, ...)`：发现 + 执行的组合入口，未发现编辑器时返回带明确原因的失败
- [x] 3.2 失败原因文案区分「没发现编辑器」与「编辑器没连回来」

## 4. UI 接入

- [x] 4.1 `style.py` 交接区增加「推送到 UE」按钮与结果回显标签，发 `push_requested` 信号
- [x] 4.2 `main_window.py` 用 `QThread`（`_PushWorker`）执行推送，完成后经信号回主线程更新
- [x] 4.3 推送期间按钮禁用并显示进行中；结束后恢复
- [x] 4.4 推送复用交接区已生成的代码文本
- [x] 4.5 失败时代码块与复制按钮保持可用
- [x] 4.6 `strings.py` 补推送按钮、进行中、成功、各类失败文案（含开启远程执行的路径提示）
- [x] 4.7 `stop_push()` + `closeEvent` 回收在途线程，避免 worker 活过面板

## 5. 测试

- [x] 5.1 新建 `tests/test_ue_remote.py`：消息必含 `version`/`magic`/`source`/`type`
- [x] 5.2 定向消息带 `dest`
- [x] 5.3 魔数、版本、半截 JSON、非对象数据均被丢弃
- [x] 5.4 `local_ipv4s()` 把回环排在最前且去重
- [x] 5.5 无编辑器时 `push()` 返回原因而非抛异常
- [x] 5.6 用假编辑器验证 `execute()` 的成功、失败、无人回连三条路径
- [x] 5.7 `tests/test_ui.py` 覆盖推送按钮存在性、忙碌禁用、失败后手动路径仍在

## 6. 实机验证与收尾

- [x] 6.1 对运行中的 UE 实测推送成功：状态显示「已在 UE 中导入完成（我的项目 · 5.7.4）」
- [x] 6.2 编辑器不可达时实测降级：提示带开启路径，复制按钮与代码块保持可用
- [x] 6.3 `mayapy` 跑全量测试，297 个全绿
- [x] 6.4 README 补远程推送的前置条件、开启方式与仅同机的限制
