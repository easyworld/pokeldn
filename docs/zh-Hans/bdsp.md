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

- 游戏机屏幕显示替换后的问候名字（[问候中的名字](bdsp_protocol.md#the-name-in-the-greeting)）。尚未追踪 `StartupSessionJob` 如何根据启动设置填充本站 +0x480 处的记录。
- 对从未发起对战招募的游戏机发送 0x08 是否会在实机上导致故障。代码会写入空模型；已发送的 0x08 使用了可靠窗口此前已见过的序列号，因此尚未到达此路径（[对战流程](bdsp_protocol.md#the-battle-ladder)）。
- 实机作为地下大洞窟会话的非主机时，是否接纳 pokeldn 的 0x61；已测量的地下会话均由游戏机担任主机，pokeldn 尚不创建此类会话。通用分发器和 `UgNetworkManager` 处理程序均不筛选发送方（[协议页面](bdsp_protocol.md#the-grand-underground)）。
- 什么原因会让联合房间中的游戏机在画面不变时停止广播（[入座](bdsp_session.md#taking-a-seat)）。
