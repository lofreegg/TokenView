# TokenView Python Implementation Plan

**Goal:** 完成三模型个人版，交付可直接运行的 Python 桌面程序。
**Architecture:** Python.NET WinForms 自绘窗口，独立 Provider 和本地加密存储，线程池查询、UI 定时消费结果。
**Spec:** `2026-10-11-python-rebuild-design.md`
**Execution:** 用户明确要求连续执行直到交付；本会话直接实施，不再设置文档审批停点。

## Global Constraints

- 只用 Codex、Antigravity、DeepSeek；只用 MyAgents 吸附。
- 不编译、不打包；直接 Python/Pythonw 运行。
- 默认刷新 300 秒；多账号、缓存、错误状态、低额度提醒。
- 凭据不复制、不日志输出；DeepSeek Key 用 DPAPI；账号授权由 CLI 完成。
- 旧项目原样保留；新目录自身就是独立实施空间。

## Review Focus

- 删除账号时已启动查询的迟到结果不能复活数据。
- 5H/周窗口按返回窗口时长映射，缺失不能推算。
- 胶囊、设置和展开面板的尺寸/裁剪必须分别更新。
- 宿主焦点转移到插件自身时插件不能立刻隐藏。
- 多账号不能修改正在使用的 MyAgents/CLI 登录上下文。

## Tasks

- [x] 1. `tokenview/model.py`, `store.py`, `tests/test_core.py`：实现快照、账号存储、DPAPI、选择状态、旧结果丢弃；测试缓存持久化、选中模型不回弹、删除后迟到结果。
- [ ] 2. `tokenview/providers.py`, `rpc.py`, `tests/test_providers.py`：三种查询/解析已完成；Codex独立账号上下文与DeepSeek多Key已完成。**仅AGY独立多账号尚不可实现**，空配置目录仍使用共享登录，当前只连接当前账号。真人授权/对账留给用户测试。
- [x] 3. `tokenview/service.py`, `feed.py`, `tests/test_service.py`：后台查询、默认300秒、去重、低额度提醒、Tibo首条；测试错误保留缓存和真实字段。
- [x] 4. `tokenview/native.py`, `ui.py`, `dialogs.py`, `main.py`：自绘原生胶囊与面板、账号添加/登录、主题、设置应用、右键恢复；实际运行渲染检查、尺寸和模式切换。
- [x] 5. `启动TokenView.vbs`, `README.md`, `tools/smoke.py`：静默运行入口、仅自身窗口的渲染检查；运行全部测试、预览、检查日志，交付桌面唯一启动文件。

接口：Store.accounts 按 id 管理；Store.update_snapshot(id,generation,snapshot) 拒绝迟到结果；Provider.fetch(Account)->Snapshot；Controller.refresh/authorize 通过队列回传；UI 只消费队列，不在 UI 线程查询网络。
