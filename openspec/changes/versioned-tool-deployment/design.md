## Context

Maya/UE 长驻 Python 会话，版本模块缓存会混用。部署不能全局替换 PySide，不能热切生产版本。

## Goals / Non-Goals

**Goals:** 可移交的 zip 发布包、严格缓存校验、项目版本锁、显式回滚、轻量宿主入口。
**Non-Goals:** 网络更新、签名 PKI、公司启动平台、自动宿主安装、Max、真实宿主兼容认证。

## Decisions

- 单独 tool_deployment.py 是标准库 bootstrap，独立于 bridge，避免校验前导入待执行代码。使用 zipfile/hashlib/tempfile/json。
- 运行时白名单目录 bridge/config/mtu_maya/unreal 和启动/安装脚本、tool_version.py；仅 py/json，排除 __pycache__。release.json 记录版本、兼容性声明、所有文件大小/hash；工具版本与包声明一致。
- 包构建采用排他输出，避免覆盖旧发布。安装在缓存临时目录，逐条拒绝绝对路径、反斜杠、..、Windows 非法/保留名、符号链接与大小写重名；清单必须与包文件精确一致。文件校验后 rename 到版本目录；旧缓存拒绝替换，失败只清理本次临时目录。
- 锁文件包含 version/release_sha256；激活前完整复验缓存，锁文件临时写入替换。回滚调用同一 pin 接口选择旧版本；不是场景/资产回滚。
- bootstrap launch_maya/launch_unreal 校验锁及文件后加载入口。已有同名工具模块来自其他路径时拒绝，提示重启宿主，不清空运行线程和控件。UE 内置 unreal 不作为工具模块处理。
- 兼容性元数据声明最低 Python 3.7、Maya 2022、UE 5.3；宿主启动判断最低版本，不承诺未实测版本兼容。

## Risks / Trade-offs

- 哈希无签名 → 锁文件需由可信项目配置管理，不防恶意人同时修改包与锁。
- 本机缓存编译文件 → 允许 pyc 缓存，不允许额外 py/json 可执行配置文件；逐文件重检。
- 共享盘 rename 非分布式事务 → 本机缓存部署，不自动发布到网络。

## Migration Plan

旧源码启动不变。将 bootstrap 放固定可访问路径；项目锁文件和缓存由显式命令管理。升级/回滚后重启 Maya/UE。
