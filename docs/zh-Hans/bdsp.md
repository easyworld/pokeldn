---
title: Brilliant Diamond and Shining Pearl
nav_order: 5
has_children: true
---
# 晶灿钻石和明亮珍珠

晶灿钻石和明亮珍珠由 ILCA 使用 Unity 开发，IL2CPP 游戏代码直接使用 Pia。

测量使用法语版明亮珍珠 1.3.0，在联合房间（宝可梦中心二楼左侧接待员，选择普通的“是”）和地下大洞窟中进行。

## 状态

已在实机验证：

- 仅凭 `prod.keys` 和 LDN 口令即可加入游戏机会话；所有数据包均可解密，发送路径与游戏机自身密文逐字节一致。
- Local、Mesh Station 和 Mesh Protocol 的握手、RTT 定时器及双向可靠传输。
- 角色能在真实联合房间中行走、显示交换表情，并与玩家进行游戏原有的问候对话。
- 完整交换：接收游戏机提议、接受构建的宝可梦并写入存档；同一次关联中可连续交换（[交换](bdsp_trade.md#the-completed-trade)）。
- 担任主机：进入联合房间的游戏机加入 pokeldn 创建的房间，显示本机角色并完成交换（[担任主机](bdsp_session.md#hosting)）。
- 在联合房间交换制作的球壳；游戏机会使用玩家现有的贴纸，将球壳保存到收藏中（[游戏协议](bdsp_protocol.md)）。
- 混合记录和对战大厅，目前可接收到游戏机记录及其选择的六只宝可梦。
- 角色可在地下大洞窟中行走，并能读取游戏机的秘密基地。

## 相关页面

|页 |内容 |
|---|---|
| [连接与Pia层](bdsp_session.md) |广告、密码、席位、数据包格式、密钥层次结构、网状握手和托管 |
| [游戏协议](bdsp_protocol.md) | BDSP 说话、联合房间和控制角色的 65 条消息 |
| [交易](bdsp_trade.md) |交换流程、PB8、保存和断开惩罚 |
## 未解决

- 游戏机屏幕上的替换问候语名称（[问候语中的名称](bdsp_protocol.md#the-name-in-the-greeting)）。 `StartupSessionJob` 如何从启动设置开始在+0x480 处填充本站的记录尚未被追踪。
- 0x08对于从未招募过战斗的游戏机是否在硬件上存在故障。代码通过空模型编写；没有 0x08 到达该路径，因为那些发送的消息是在可靠窗口已经看到的序列 ID 下发出的（[战斗阶梯](bdsp_protocol.md#the-battle-ladder)）。离开联合房间是否会破坏`UnionRoomManager`未读（`UnionRoomManager$$OnDestroy` `0x1e4c540`存在；其调用者未知）。
- 非Grand Underground会话主机的实机是否采用pokeldn的0x61；测量的 Underground 会话将游戏机作为主机，而 pokeldn 则没有主机。   公共调度和 `UgNetworkManager` 处理程序没有发送者过滤器（[协议页面](bdsp_protocol.md#the-grand-underground)）。
- 是什么让联合房间里的游戏机停止广告，屏幕上没有任何变化（[入座](bdsp_session.md#taking-a-seat)）。
- `SS_box_182`的文本，消息`BoxWindow.SetSendPokemon`在交换中为标记的宝可梦选择，以及`RequestValidateTrade`检查在线交换的内容（[重复检测](bdsp_trade.md#duplicate-detection)）。
- Unity 播放器从哪里获取 `Screen.width`。当 `/Data/rawsettings` +0x1c 为 0 时，2D 网格位置基于 `0x6062e8` 保留的 1280 x 720 默认值（[协议页](bdsp_protocol.md#the-grand-underground)）；不排除其他来源，例如 `globalgamemanagers` 中的玩家设置。
- 任何场景是否将 `UnionRoomManager` 或 `UgNetworkManager` 作为组件放置。每个代码仅读取`AddComponent`；场景放置的实例将位于这些路径之外。
