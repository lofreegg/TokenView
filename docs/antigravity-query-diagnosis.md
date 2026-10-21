# TokenView Antigravity 查询诊断

## 已确认

1. 运行中的 `D:\myagent\TokenView\TokenView.exe` 与当前便携包构建的 EXE 哈希一致，不是另一个旧程序。
2. 截图账号的独立只读额度查询成功。Google 响应中 Gemini 周额度 `remainingFraction=0`；5H 桶 `window=5h, disabled=true, remainingFraction=1`。停用标记优先，不能把这个1显示成100%，也不能称5H未授权。当前解析器跳过disabled桶，造成界面“未返回”；应改为明确显示“当前停用”。接口未返回停用原因，不能断言就是周额度耗尽导致。
3. 另一条 MyAgents 关联账号查询走全局 AGY CLI。使用与程序相同的 `/usage` 参数实测，CLI登录账号为ben.lofree66@gmail.com，而非该关联行的wei.guo.lmsee@gmail.com。CLI日志显示keyring令牌尚未过期、静默认证成功，随后“Account ineligible”，进程退出码1。这是账号通道不一致/资格拒绝，不是截图账号周额度为0。
4. TokenView自动刷新只调用fetch；主动authorize只来自添加账号或用户确认重新登录，零额度并不调用authorize。独立账号查询不调用浏览器登录。

## 未确认

本次复现没有捕获浏览器授权页实际启动事件，因此周期性弹授权页的直接触发原因仍不能认定。之前关联CLI查询超时是已存错误状态；此次实测则快速返回资格拒绝，不能把两次症状当同一已证实机制。

## 建议处理（尚未实施）

- 界面保留disabled字段，将5H显示为“当前停用”，并明确不推测Google停用原因。
- MyAgents关联AGY账号不要依赖全局AGY CLI的不同登录账号；改用匹配该账号的只读额度通道，缺失凭据时只提示，不自动授权。
- 下一次授权页出现时记录启动来源，确认是CLI、TokenView主动操作还是其他程序，再修相应链路。

此次没有切换MyAgents账号、完成新OAuth授权或修改查询实现。诊断只输出额度元数据和脱敏日志，不输出Token、Key或授权URL。
