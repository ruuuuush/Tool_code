## Why

导出完成后，用户还得切到 UE、打开 Output Log、粘一段代码。交接区已经把代码填好了，但"切窗口、粘贴、回车"这三步依然横在交付路径上——尤其是调动画时一天要来回几十次。

UE 提供了官方的 Python Remote Execution：编辑器监听多播端口，外部进程可以把 Python 代码推给正在运行的编辑器执行。Maya 端完全可以在导出成功后直接触发导入，不用离开 Maya。

可行性已实测通过（mayapy → 运行中的 UE 5.7.4）：ping/pong 发现编辑器、UE 反向 TCP 连回、`ExecuteFile` 模式执行完整导入、结果原样回传。实测跑完拿到 `success: true`、`Succeeded (1): test`、骨架与 SkeletalMesh 均创建。

## What Changes

- **新增 UE 远程执行客户端**：纯标准库实现多播发现 + 反向 TCP 命令通道，不依赖引擎自带的 `remote_execution.py`（那个文件的位置随安装而变）。
- **交付卡片新增「推送到 UE」按钮**：交付完整时可用，点击后直接在运行中的编辑器里完成导入，并把 UE 侧的输出回显到 Maya。
- **连不上时安静降级**：未开启远程执行、编辑器没开、被防火墙拦——都退回现有的复制代码方式，并说明原因，MUST NOT 阻塞界面。
- **不移除现有交接区**：复制代码仍然保留，它是跨机器交付和远程执行不可用时的唯一出路。

## Capabilities

### New Capabilities
- `ue-remote-push`: Maya 端把导入命令推送给运行中的 UE 编辑器的能力——如何发现编辑器、如何执行、失败如何降级。

### Modified Capabilities
- `export-ui`: 交接区增加推送入口（在原有复制代码之外）。

## Impact

- `bridge/ue_remote.py`（新增）：远程执行协议客户端，纯标准库，无 Maya/UE 依赖，可单测
- `mtu_maya/ui/style.py`：交接区增加推送按钮与状态回显
- `mtu_maya/ui/main_window.py`：推送动作、结果展示、失败降级
- `mtu_maya/ui/strings.py`：推送相关文案
- `tests/test_ue_remote.py`（新增）：协议编解码、发现逻辑、超时与降级
- `README.md`：远程推送的前置条件与开启方式
- 导出器、检查项、UE 导入逻辑均不改动
