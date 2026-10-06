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

- 在主机画面上显示替换后的问候名称（[问候中的名称](bdsp_protocol.md#the-name-in-the-greeting)）。尚未追踪到 `StartupSessionJob` 如何根据启动设置填写 +0x480 处的本站记录。
- 向本次进入联合房间后从未发起对战招募的实机发送 0x08，是否会使其发生异常。代码会通过空模型指针写入；此前发送的 0x08 使用了可靠窗口已经见过的序列号，因此尚无消息进入这条路径（[对战交互流程](bdsp_protocol.md#the-battle-ladder)）。
- 未担任地下大洞窟会话主机的实机是否会接受 pokeldn 发来的 0x61。已测量的地下会话均由游戏主机主持，pokeldn 尚不主持此类会话。公共分发逻辑和 `UgNetworkManager` 处理器都不筛选发送方（[协议页](bdsp_protocol.md#the-grand-underground)）。
- 什么原因会让联合房间中的主机停止广播，而画面没有变化（[占用席位](bdsp_session.md#taking-a-seat)）。
- `SS_box_182` 的文本、`BoxWindow.SetSendPokemon` 在交换带标记的宝可梦时选择的消息，以及 `RequestValidateTrade` 在线上交换中检查哪些内容（[重复检测](bdsp_trade.md#duplicate-detection)）。
- Unity 播放器从哪里取得 `Screen.width`。二维网格位置的计算依赖 1280 × 720 这一默认值；当 `/Data/rawsettings` 的 +0x1c 为 0 时，`0x6062e8` 保留该值（[协议页](bdsp_protocol.md#the-grand-underground)）。尚未排除其他来源，例如 `globalgamemanagers` 中的播放器设置。
- 是否有场景把 `UnionRoomManager` 或 `UgNetworkManager` 预置为组件。在代码中，两者都只通过一次 `AddComponent` 添加到新 GameObject 上创建（`0x01b35f70`、`UgFieldManager$$StartSession` `0x01cfed48`）；没有代码把任一类型用作 `typeof`，也没有针对它们的泛型 `GetComponent` 或 `FindObjectOfType`，而联合房间没有调用 `GameObject.Find`。预置实例会通过其单例 `Awake` 注册，无需查找。因此答案在场景资源包中：查找 `m_Script` 指向任一类 `MonoScript` 的 `MonoBehaviour`。
