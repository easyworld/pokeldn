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

> 本节已随上游更新，以下内容暂保留英文。

- A substituted greeting name on a console's screen
  ([The name in the greeting](bdsp_protocol.md#the-name-in-the-greeting)). How `StartupSessionJob`
  fills the own station's record at +0x480 from the startup setting is untraced.
- Whether a 0x08 to a console that has never recruited a battle faults it on hardware. The code
  writes through a null model; no 0x08 has reached that path, because those sent went out under
  sequence ids the reliable window had already seen ([The battle
  ladder](bdsp_protocol.md#the-battle-ladder)).
- Whether a retail console that is not the Grand Underground session host adopts a 0x61 from
  pokeldn; the Underground sessions measured had the console as host, and pokeldn does not host one.
  The common dispatch and the `UgNetworkManager` handler have no sender filter
  ([the protocol page](bdsp_protocol.md#the-grand-underground)).
- What makes a console in the Union Room stop advertising with no change on screen
  ([Taking a seat](bdsp_session.md#taking-a-seat)).
- The text of `SS_box_182`, the message `BoxWindow.SetSendPokemon` selects for a flagged Pokemon in
  a trade, and what `RequestValidateTrade` checks for an online trade
  ([Duplicate detection](bdsp_trade.md#duplicate-detection)).
- Where the Unity player takes `Screen.width` from. The 2D grid positions rest on it being the
  1280 x 720 default that `0x6062e8` keeps when `/Data/rawsettings` +0x1c is 0
  ([the protocol page](bdsp_protocol.md#the-grand-underground)); another source, such as the
  player settings in `globalgamemanagers`, has not been excluded.
- Whether any scene places a `UnionRoomManager` or a `UgNetworkManager` as a component. In code each
  is created only by one `AddComponent` on a new GameObject (`0x01b35f70`, `UgFieldManager$$StartSession`
  `0x01cfed48`); no code takes either type as `typeof`, no generic `GetComponent` or `FindObjectOfType`
  of either exists, and `GameObject.Find` has no Union Room caller. A placed instance would register
  through its singleton `Awake` with no lookup, so the answer is in the scene bundles: a
  `MonoBehaviour` whose `m_Script` is either class's `MonoScript`.
