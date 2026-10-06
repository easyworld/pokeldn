---
title: Scarlet and Violet
nav_order: 9
has_children: false
---

# 朱和紫

宝可梦朱 (`0100a3d008c5c000`) 和紫 (`01008f6008c5e000`) 是原生 Switch 游戏，Pia 链接到 `main`。两者都与扮演两种角色的实机进行交换：`bin/sv_host.py` 主持游戏机的离线链路交换搜索，`bin/sv_join.py` 加入游戏机的网络。零售紫加入主机广告朱的本地通信ID，并且其自己的搜索网络也广告朱的ID（`0x0100a3d008c5c000`，应用程序版本21，场景4）。

地址是更新 4.0.0 (`tools/switch/nso_read.py`) 的解压缩 `main` 中的偏移量：文本 `0x0..0x343fc90`、来自 `0x3440000` 的rodata、来自 `0x4383000` 的数据。
## 无线层

| |价值|
|---|---|
| Pia 头版本 | 11、传说阿尔宙斯乐队； `pokeldn.ldn.pia6` 会说话 |
|标题大小 | 0x1C，GCM 标签 8 字节 |
| LDN 密码 | `W3GoSMEn7RIIUQ89rzqBHGhGferRNb7K18ZBq2aNuj8Us9RO9Q9JYyGOZlLy8MYL`，数据 `0x44dfd0a` |
| Pia游戏键| `p1frXqxmeCZWFv0X`，数据 `0x44dfcfe`，紧接在密码之前 |
| LDN 本地通信 ID | 朱的 `0x0100a3d008c5c000` 在两个版本上（id 都不是图像中的常量；NACP 列出了两者）|

密码和游戏密钥与剑／盾和传说阿尔宙斯的相同。
## 搜索游戏机的广告内容

链路交换搜索交替托管（每次新的 SSID）和扫描，在通道 1、6 和 11 之间跳跃；主机阶段大约为五秒。

    local_communication_id  0x0100a3d008c5c000, Scarlet's, on both versions
    ldn protocol            1            advertisement version 4
    scene_id                4            app_version 21
    security_mode           1            accept_policy ALL
    participants            1/2
    application_data        132 bytes
 应用数据为0x5C Pia系统属性块和40个游戏字节：

|领域 |价值|
|---|---|
|系统通讯版| 0x15 |
|应用通讯版 | 0x15 |
|用户密码 |十六个零字节，无链接代码 |
|玩家限制已启用 | 1、玩家人数 1，一旦入座则为 2 |
|玩家姓名 |一个字节，一个空格，UTF-8 |
| 40 个游戏字节 |游戏 `+0x21` 中的零或非零值（看到 `fb149700`），每隔几秒交替一次；第二个游戏机关联到任一 |

`pokeldn.sv.build_advertise_data` 逐字节再现两个信标。
## 游戏运行的协议

零售对的被动捕获显示 Net、RTT、0x80 和 0x81，全部发送到会话 `/24` 的广播地址，并在明文页脚中包含接收者的变量 id。其他 6 个是单播（两个 Switch 2 控制台之间的 802.11ax）并且不参与捕获。

游戏的设置 `0x17ff030` 按顺序创建：端口 0 上的 Reliable `0x7C` 和 BroadcastReliable `0x80`、端口 1 和 2 上的 Unreliable `0x68`、Reliable 和 BroadcastReliable、`[0x44dfcd0]` StreamBroadcastReliable `0x81` 端口（线上 8 个）、克隆时钟 `0x77` 和克隆原子
`0x74`。 Pia添加了Net、RTT、Session `0x98`和MonitoringData `0xA4`； NatTraversalResult `0xA0` 仅当网络工厂启用 NAT 穿越（`0x6d3138`）时，本地网络没有启用 NAT 穿越。

|编号 |协议|版本 |
|---|---|---|
| `0x2C` |网| 0 |
| `0x58` |实时传输时间 | 3 |
| `0x68` |不可靠 | 1 |
| `0x74` |克隆原子| 0 |
| `0x77` |克隆时钟| 0 |
| `0x7C` |可靠| 2 |
| `0x80` |广播可靠| 3 |
| `0x81` |流媒体广播可靠 | 3 |
| `0x98` |会议| 0 |
| `0xA4` |监测数据| 0 |

零售传说阿尔宙斯在其加入请求中列出了相同的十个版本。零售对的开盘（从一次捕获开始的时间）：

    +0.00   the joiner associates
    +0.06   host: Net 0x11 (station list), 0.12 s later Net 0x50
    +0.14   host: acks all eleven streams, opens two
    +0.89   joiner: RTT request, acks all eleven, opens two
    +0.97   host: first records on 0x81 port 0
    +1.26   joiner: first records on 0x81 port 1

### 网0x11，电台列表

该布局是传说中阿尔宙斯的布局，有四个 21 字节的站槽：

    01 11 0054          version 1, type 0x11, payload size 0x54
    00000002            sequence id
    9141                host variable id, fresh every session
    eb9b2220f1480000    host constant id, the LDN MAC reordered
    0000000097392e8a    network id, the low four bytes crc32(ssid[1:16])
    01                  is network open
    0004                station slots
    00                  is migrating host
    ...                 four stations: migration state, ranking (host 0, joiner 1, empty 0xff),
                        one byte, 16 address bytes, big-endian u16 port (12345)

`01 40 00 00` 是一个裸 NetStartHostMigration，由移交其角色的主机发送。其搜索中的零售朱主机在其交给加入方的席位上重复该内容（[决定席位的因素](#what-decides-a-seat)）。

一个主机必须写四个站位（Pia 的计数，而不是游戏的两个站位限制）。对于两个，加入的游戏不发送任何内容，并在关联后 5 秒断开连接（49 个加入为 4.98 至 5.01 秒），实机回答 Net 0x11，ICMP 端口 12345 无法访问；如果是 4，则它会回答 Net 0x12 并发送其会话加入请求。开头标志 0x31（零售）或 0x01 没有区别。
### 十一条溪流

    0x80  BroadcastReliable         ports 0, 1, 2
    0x81  StreamBroadcastReliable   ports 0 to 7
 两个站大约每秒一次通过 `pokeldn.ldn.reliable5` 的批量确认确认所有 11 个条目：四个条目，站字节零，条目 *k* 超过站 *k* 的最高序列，目标位计数 3，位图中的对等位。站点使用 11 字节的 INITIALIZED 消息打开两个流，并在其站点索引的端口上发送记录（如 `pokeldn.pla.data_exchange`）。

|车站|打开|发送记录于 |
|---|---|---|
| 主机, 索引 0 | 0x81 端口 1 和 5 | 0x81 端口 0 |
| 加入方，索引 1 | 0x81 端口 0 和 4 | 0x81 端口 1 |

端口 0 和 1 上的开放拓扑为 `0000000000f38800000000`，端口 4 和 5 上的 `00 <port> 00 00 0ff0 0800000000`：StreamData 类型 0 发布 0xF388（传输 0）或 0xFF008（4 和 5）的接收。 0xFF008 传输永远不会在交换中发送。
`pokeldn.sv.streams` 构建了所有这些； `tests/test_sv.py` 将其固定到零售字节。
### Pia 消息标志

两个零售站都发送（不使用阿尔宙斯主机的建立标志）：

|留言 |旗帜|
|---|---|
| RTT，流打开，记录的首次传输 | 0x00 |
|再次发送记录| 0x40 |
|批量致谢| 0xA0 |
|主机网 0x11 和 0x50 | 0x31 |
| NetStartHostMigration | 网络启动主机迁移0x11 |

消息目的地字段始终为零。标志0x40是来自`ReliableSlidingWindow`发送循环`0x6f0638`的`w4 = 1`（发送计数`[slot+0x14]`为零时为0，`0x6f0908`为1；重新发送时为1）
`0x6f0a9c`或提前发送`0x6f0c38`），由`0x6e7250`存储为数据包写入器选项块的字节0。
### 实时传输时间

11 个字节：种类、大端 u64 时钟、大端 u16 目标。请求类型为 0，目标为 0；答案类型 1 具有相同的时钟和请求者的变量 ID，零售时在 20 毫秒内。

RttProtocol（vtable `0x43e5a28`）在`[proto+0x60] + index*0x40`处为每个站保留0x40字节记录：样本计数`+0`，环头`+4`，容量9在`+0x10`后面，环内联在其后面，中值缓存在 `+0x3c`，用于 `+0x38` 的计数。现在样本时钟减去回显时钟（`0x6f34b4`）；零或更少的样本被丢弃（`0x6f34e0`）。请求以 `[0x46d1528]` 的间隔进行，直到每个环都已满，然后在 `[0x46d1520]` = 500 处（在 `0x6f2fcc` 处写入，并由 `0x1e7c2bc` 处的游戏写入）。站事件 0 或 1 清除该站的记录 (vfunc11 `0x6f3bd8`)：新座位没有样本。

GetRtt (`0x6f4498`; `0x6f44bc` with a count *n*) 在没有样本的情况下返回 -1，否则为最后 min(count, *n*) 个样本的中位数；最小值 `0x6f44e4`、最大值 `0x6f4508` 和样本计数 `0x6f452c` 位于其旁边。唯一的调用者是 SessionTransportAnalyzer 的监控副本 (`0x6f9ab0`..`0x6f9ad4`) 和 `ReliableSlidingWindow` 重传截止时间 `0x6f0d14`，从 `0x6f073c` 的发送循环调用：

    deadline = now + [window+0x80] + 1.4 * (max over the destinations of GetRtt(count))
 在没有样本的情况下，`0x6f0d14` 返回未计划的标记 `[window+0x5c]`：排队时发送一次消息 (`0x6f1bbc`..`0x6f1bd4`)，并在 `0x6f0a18` 处跳过，直到样本重新准备它（`0x6f09f4`..`0x6f0a08`）。没有 RTT 样本的窗口永远不会重传。

构造函数 `0x6eeea8` （调用者 `0x6e69f8`、`0x1800038`）将 `[window+0x80]` 设置为
`ticks_per_second * 33 / 1000`（`0x6eef34`..`0x6eef74`；633,600 个刻度，19.2 MHz 时为 33.0 ms），标记
`[+0x5c]` 0，碱基序列 `[+0x30]` 1，自身索引 `[+0x10]` 0xfd，压缩 `[+0xa4]` 1，提前发送限制 `[+0x88]`，`[+0x89]` 0。后来的作者是vfunc17 `0x6f1f98`中的`0x6f1fc8`（来自`ReliableProtocol::vfunc17` `0x6eebbc`和`BroadcastReliableProtocol::vfunc17` `0x6e6818`，未知调用者）。发送循环每 16.7 ms 帧运行一次，因此在 `33 + int(1.4 * RTT)` ms 或之后在第一帧上重新发送：RTT 为 34 ms 时为 83 ms，RTT 为 358 ms 时为 550 ms。
### 记录

一条记录是一条带有 ZLIB 标志的可靠消息，一个带有 4 KB 窗口 (`484b`) 的 zlib 流，膨胀到 1395 字节，`[window+0x70]`：Pia 的 StreamData 标头下的 0x81 传输的一个块（[协议0x81](pia.md#protocol-0x81-the-stream-broadcast-reliable-transfer-pia-6)):

    +0x00  1   StreamData kind: 1 the first chunk of the block, 2 a later chunk
    +0x01  1   transfer id, 0
    +0x02  1   percent of the block delivered after this chunk
    +0x03  4   zero, the capacity field of a kind 0
    +0x07  4   big-endian u32 0x00000568, the 1384 bytes that follow
 站的块是 0xF388 (62,344) 字节：1384 的 45 个块和 64 之一，id 1 到 46，百分比字节 `floor(k * 1384 * 100 / 62344)` (2, 4, 6, 8, 0x0b, ..., 0x37 位于 25，0x52 位于 37，0x64 位于 46）。第一个块包含屏幕上显示的伙伴：

    +0x0b  5   unread
    +0x13  26  the player name, UTF-16 little-endian, NUL-padded; --trainer-name on both launchers
    +0x2d  22  the account identifier, ASCII, `u-` and twenty characters
    +0x53  1   5
 Chunks 2到24是高熵的； 25 到 46 为零。电台一次发送其整套数据，通常在第一个数据包中发送 ID 1、25、26 至 36 和 46，在第二个数据包中发送 2、37 和 38 至 45，然后每个数据包发送 3 至 24 个数据包（48 个零售数据包中的 41 个）。相同的零块在 0x00 的存在字节后面移动，每个头字段都继承（[消息帧](pia.md#message-framing)）。一套通常会在 0.2 秒内离开（52 套零售套中有 46 套在 0.19 秒内离开）。 `pokeldn.sv.streams.decompress` 读取它们。

`pokeldn.sv.reference` 在 0x7C 端口 0 上发送电台的 44 条记录及其两个身份片段，记录自模拟朱，其玩家为 `Player`，帐户标识符未设置。 `bin/sv_host.py` 和 `bin/sv_join.py` 发送它们，除非给出 `--record-set`、`--send-on-open` 或 `--no-identity`。
### 零售确认和大量转发

零售站通过连续运行之后的 ack id 确认对等点的记录流，字段 0x50 等于它，并且掩码其中字节 *k* 的位 *b* 是 id `ack_id + 1 + 8k + b`：持有 id 1 到 4 和 7 到 38 的主机发送 `0005 0005 feffffff01`。低于对等方自己的 `lowest_pending` 的 ID 视为已持有。 `pokeldn.sv.streams.ack_position` 构建此（固定在 `tests/test_sv.py` 中）； `bin/sv_join.py
--ack-highest` 发送一个超过所看到的最高 ID 的值。

A 主机 在 RTT 截止日期前重新发送每个未确认的记录，标记为 0x40，每个数据包一轮，最低 id 首先，随着 ack 到达而缩小。停在 0x00 存在字节处的消息遍历仅读取每轮的第一条记录，需要 19 轮； `--ack-highest` 将 `lowest_pending` 立即从 1 移动到 38。在未确认的情况下，主机每轮都会重新发送每个待处理的记录；在每秒数百条记录的小 RTT 下（HT MCS3 为 435 至 494 条记录，大约占空气的 3%），足以填充板串行线的 150 KB/s（[串行上限](hardware_esp32.md#the-serial-ceiling)）。舍入间隔，`[window+0x80] +
1.4 x RTT` 舍入到帧，相对于加入方的应答延迟：

|应答延迟 |预计 RTT |轮距、座位中间线|
|---|---|---|
| 0.000 秒 | 0.013 至 0.017 秒 | 0.065 至 0.069 秒 |
| 0.000 秒 | 0.033 至 0.038 秒 | 0.078 至 0.116 秒 |
| 0.000 秒 | 0.053 至 0.059 秒 | 0.115 至 0.221 秒 |
| 0.318 至 0.328 秒 | 0.354 至 0.363 秒 | 0.532 至 0.555 秒 |

当 RTT 环充满时，记录的间隔会收敛于其上（4 到 5 个答案为 0.19 秒，8 到 18 个答案为 0.10 秒，20 个答案为 0.082 秒）。构造函数 `0x6eeea8`，发送缓冲区 `0x6e6e94`，入队 `0x6f1994` 并在 unicorn 下发送循环 `0x6f0638` 一次发送 46 条记录，在截止日期之前仅此而已。 A 主机自己的处理设定了节奏：它的 `lowest_pending` 在设置后留下 1 大约 0.5 到 1.0 秒，无论 ack 延迟如何（0.73 到 0.81 秒，每帧在 7 毫秒内确认），它的 ack 掩码以大约 0.19 秒的步长前进。它在加入方的流打开和记录集（`--open-delay`、`--record-delay`）后约0.1秒发送其集。 RTT 应答之前保存的数据，然后将轮次间隔设置为低于该延迟，并重新发送加入方已保存的记录；延迟 0.3 秒应答 RTT 可以避免这种情况。在零售座位上：

| RTT 赛前答复 |应答延迟 |座位 | `lowest_pending` 之前重新发送的记录还剩 1 |后留下 1 |
|---|---|---|---|---|
| 0 或 1 | 0 | 3 |无二合一，138合一| 0.78 至 0.81 秒 |
| 3 至 6 | 0 | 4 | 122 至 137，每个 id 每 0.18 至 0.20 秒 | 0.73 至 0.80 秒 |
| 0 | 0.3 秒 | 4 |无 | 0.91 至 1.01 秒 |
| 1 至 7 | 0.3 秒 | 9 |无 | 0.50 至 0.58 秒 |

`--rtt-delay 0.3` 延迟 0.3 秒应答 RTT 请求，这使得轮次间隔高于主机的确认延迟。 `--leave-on-migration N`在游戏机发送Session type 7后N秒结束坐席，`--announce-timeout SECONDS`擅自离开坐席；两者都再次扫描。 `bin/sv_join.py` 立即确认一条新记录，每个流每 50 毫秒最多重复一次 (`--repeat-ack-gap`)，每个数据包每个流一次确认。

如果没有 RTT 样本，0x81 流永远不会重传（[协议 0x81](pia.md#protocol-0x81-the-stream-broadcast-reliable-transfer-pia-6)）：空中丢失的记录保持待定状态，主机的 `lowest_pending` 在其 id 处停止，并且对等点永远不会被宣布。

RTT样本启用重传；公告作业没有 RTT 门。无损模拟朱 4.0.0 主机宣布并完成交换，无需 RTT 请求或应答。丢失的身份记录将 BoxTrade 作业保持在状态 1 (`+0xb8`)； `0x1e51ae8` 处的完成槽数保持为 1，而所需的为 2，直到重传完成该组为止。

两个启动器都会重试待处理的身份记录。通过 `tests/test_sv_identity_loss.py` 中的启动器完成删除初始化程序和中间记录案例。修补后的模拟器在这些损失的情况下完成了交易；一名实机人每个角色完成了两次交易，待处理的身份记录经过重试和确认，然后干净利落地离开。较早未宣布的座位（其确认数量已达到 47）没有独立的空中捕获来确定哪个传出块（如果有）丢失。
### 捕获中的 A-MSDU 帧

两个控制台都将多个 MSDU 打包到一个 A-MSDU 帧中。被动捕获必须解包子帧，否则会丢失大部分 Pia 数据包（一次捕获中，313 个不可读，3667 个可读）。
## 链接代码

一个连接密码会重复广告两次；场景 id 保持为 4。用户密码是代码，NUL 填充为 16 个字节，与 `e5ab19ed742b6d40885998bf968aa166`（同一游戏密钥下的传说阿尔宙斯掩码）进行异或（[docs/pla.md](pla.md)）。游戏字节在 +0x00 处携带明文代码，在 +0x24 处携带 u32 长度。 `pokeldn.sv.build_advertise_data(code=...)` 再现了 12345678 字节逐字节搜索的实机。

搜索游戏机仅加入广告其代码 (`bin/sv_host.py --code`) 的主机。一个以代码托管的实机不接受加入方广告。 `bin/sv_join.py --code` 仅加入使用该代码搜索的游戏机。

只有搜索游戏机才会在其扫描的网络上检查代码。它的选择器`0x26e955c`（在加入之前从`0x272d838`调用）在使用代码搜索时跳过没有密码的网络（`0x26e95f4`），在没有密码搜索时跳过有密码的网络（`0x26e960c`）。然后，它将游戏字节从 +0x00 哈希到第一个 NUL 及其自己的代码 FNV-1a 64（素数
`0x100000001b3`，在 `0x26e96c8` 加载的偏移基础 `0xcbf29ce484222645`，不是标准基础）并跳过网络，除非两者相等（`0x26e972c`）。它既不读取密码的值，也不读取 +0x24 处的长度。

主机不比较加入方发送的任何内容。 LDN 关联使用固定密码，会话加入请求没有密码字段。 Pia对连接站的密码检查，Net 0x32处理程序`0x69ec50`（`0x69ee5c`，`0x69ee70`）中的结果7，需要Net 0x32及其唯一发送者
`0x69d42c` 在协议 vfunc 48 上门控：`LdnProtocol` (`0x6a2fac`) 中为 0，`LanProtocol` (`0x6ba278`) 中为 1。在加入端，LDN 连接运行 Pia 的网络检查 `0x6a22c4`，其密码比较 (`0x6a24a4`) 已关闭 (`0x6b0d90`)。

加入的游戏机不会再次检查代码。 Net 0x50 处理程序 `0x69ea3c` 验证系统属性大小 (0x5c)、应用程序数据大小（最多 0x124）和四个 Pia 身份字段 (`0x69d9d8`)，将字节复制到网络属性 (`0x69d8a4`)并确认网络 0x51；它不比较系统属性的字节或游戏字节。通过 LDN，副本落在缓存的广告数据中，下一个 `nn::ldn::GetNetworkInfo` (`0x6b30d4`) 会覆盖它。游戏仅在选择器和 UpdateSessionSetting (`0x26e63b8`) 中读取会话的第一个 0x28 游戏字节，这会重写自己的会话；另外两个读者（`0x268e988`、`0x268e9bc`）仅读取过去的+0x28。加入的游戏机将其代码保留为自己的 Pia 站密码（加入对象 vfunc `0x274bdb8`，setter `0x6a208c`），仅在托管时公布。 Link 交换的端口 2 类型 1 来自 BoxTrade 作业的状态 2 (`0x1e51b68`)：种类 1，静态空名称 `[0x46d3e30]`，无数据。
## 代码在哪里

RTTI 名称来自二进制文件的 type_info 记录（`tools/switch/rtti_names.py`、208 `nn::pia` 类）。

|地址 |什么|
|---|---|
| `0x697134` | Pia 标头初始值设定项：magic `0x32AB9864` at `+8`，版本 `0x0b` at `+0xc`，标头大小 0x1c at `+0x5f8` |
| `0x696f10` |标头解析器，版本 11 顺序的字段 |
| `0x697034` |轮椅界限：高于 0x5a3 的长度返回 null |
| `0x3c0c8c0`，`0x44dfcfe` |密码 (rodata) 和游戏密钥 (data) |
| `0x6b43a8` | `LdnConnectionStatus::vfunc20`：`GetNetworkInfo`参会站地址|
| `0x6b45e0`..`0x6b4754` |它针对对象 `+0x30` 处的站阵列，在八个 0x40 字节参与者插槽（地址 `+0x108`，当前字节 `+0x113`）上循环，计数 `+0x38` |
| `0x6b3090` | `LdnProtocol::vfunc104`，另一个 `GetNetworkInfo` 读卡器 |
| `0x046ca878` | `nn::ldn::GetNetworkInfo` 的 GOT 插槽，六个调用站点 |
| `0x475ea68`、`0x475ea6c`、`0x475ea70` |可靠的 0x7C 手柄，端口 0、1、2 |
| `0x475ea74`、`0x475ea78`、`0x475ea7c` | BroadcastReliable 0x80 手柄，端口 0、1、2 |
| `0xe45e9c` | 0x80 端口 2 发送：通过 `0xe21488` 解析协议，将缓冲区交给 `0x107e060` |
| `0xe2246c` | 0x5a0 字节应用程序在其下发送到 `BroadcastReliableProtocol::vfunc12` `0x6e6344` |
| `0xe457cc`、`0xe45740`、`0xe460bc`、`0xe454ec`、`0xe46148`、`0xe461d4`、`0xe46260` |消息类型 6、7、8、9、0x0A、0x0B、0x0C 的编写者，每个调用 `0xe45e9c` |
| `0xe45e1c`，`0xe46034` | type-7 和 type-8 字段串行器（`0xb9` 标记）|
| `0x46d6ca0`、`0x46d6ca8` |漏极 `0xe44cf0` 的单例，设置在 `0xe44ac0` |
| `0x1e685a4` |交换通道的端口 0 接收器：种类（标记整数）、步骤，然后通过表 `0x3c5bb82` 种类 0 到 5； 1个身份（`0x1e6864c`，解析为`+0xae0`），2个提议（`0x1e686cc`：由`0x1db949c`解析的344字节blob，由`0xeee8fc`和`0xe13ad8`包装，存储在`+0xb8` by `0x1e684fc`，状态 `+0xc4` = 3), 3 确认（`0x1e68768`，针对 `+0xe2`），4 取消 (`0x1e68678`)，5 提交（`0x1e68780`，状态 `+0xc0` 掩码为 4）|
## 会话协议

`nn::pia::session::SessionProtocol`（id vfunc `0x6d9f3c` 返回 0x98）位于 `JoinMeshJob` 旁边，
`CreateMeshJob`、`LeaveMeshJob`、`JoinSessionJob` 和 `SessionPacketReader`/`Writer`；网格连接据说是阿尔宙斯的。会话消息在数据包标头中携带对等方的变量 id，但没有页脚，因此它是单播的。方加入在加入请求的源位置 id 中声明其变量 id；主机在关联后 0.14 秒将其命名。
### 会话加入请求

编写器 `0x6d5464`..`0x6d58b0`，主机解析器 `0x6d5aa4`。该布局是零售传说阿尔宙斯的（`docs/pla.md`，会话加入请求；`tests/test_pla_session_v11.py` 中的 115 字节），由
`pokeldn.ldn.pia6.build_session_join`：

    +0    1    type 0
    +1    1    protocol count, ten
    +2    2n   (id, version) pairs, walked from the protocol manager's list
    +22   4    random, xorshift128 seeded from the system tick (`0x6c70a8`, `0x6c7184`)
    +26   12   source location id: u64 constant id, two zero bytes, u16 variable id, big-endian
    +38   1    NAT mapping, two bits
    +39   1    private-IPv6 flag
    +40   32   identification token
    +72   1    address kind, 0 for IPv4 (1 puts an 18-byte IPv6 address in place of the six bytes)
    +73   4    source IPv4 address
    +77   2    source port, big-endian
    +79   12   destination location id, the host's
    +91   1    player count
    +92   1    a flag the job sets to 1
    +93   ..   player records: a 16-byte id (`1` then `0` as two big-endian u64), a big-endian u32
               name length, a kind byte (1), the name
 零售加入方的一名玩家被命名为单个空间。数据包头携带目标变量id 0和加入方的id作为源；每次重复时消息标记 `0x01`（跳过源检查）。主机按顺序检查：

1. 协议计数等于其自身；否则什么也不会发送。
2. 每个版本都等于主机的（`0x6ed1b8`）； else status 3 带有 id 和主机版本。
3. 目的位置id为主机的常量和变量id；否则就掉了。
4. 源常量 id 和地址不是主机的。
5、已知常量id再次绘制状态1；关闭会话状态 5；主机端侦听器可以以状态 4 拒绝。

连接响应（类型 2，43 字节，`0x6d6390`）是阿尔宙斯布局：类型、协议 id、版本、状态、大端 u32、四个随机字节、位置 id、路由字节 A 和 B、站索引、连接顺序、站更新必须达到的序列 id。加入方用 13 字节类型 6 (`0x6d80a4`) 响应类型 5 更新：类型、常量 id、两个零字节、应用序列 (`pokeldn.ldn.pia_connect`)。
## 座位和上面的身份信息

上面的加入请求使站点入座：零售朱主机在 16 毫秒内接受，发送 41 字节加入响应（状态 1，无路由字节）和无路由站点更新，并在 0x81 端口 0 上流式传输其身份，每条记录一次。不接受加入方确认的主机会重新发送每条记录，直到席位结束（[使主机算作确认的标志](#the-flag-that-makes-the-host-count-an-acknowledgement)）：零售时每秒约 350 条记录，每条最多重传 70 次，针对无损 LAN 上的模拟，59 秒内每条记录重传 676 次。主机还可以发送会话类型 7 (`LeaveMeshWithHostMigrationJob`)，将主机角色交给加入方，每秒一次，直到类型 8 应答（[什么决定座位](#what-decides-a-seat)）。
### 使主机算作确认的标志

标志位为 5、ZLIB（`[msg+0x29]`、`0x6efc80`）的消息在站解析之前在 `0x6e9984`（`0x69804c`、zlib inflate `0x2801d0`）中膨胀；失败返回 0x2C03 (`0x6efd5c`)。标记为 0xA0 的普通批量确认在此失败（模拟游戏机上的 600 中的 600）。零售0xA0 acks携带zlib主体：三个零售加入方捕获中的所有1,774个都膨胀到99字节； 38字节的主体开始
`484b62606008` 使用记录的 4 KB 窗口、5 级同步刷新帧进行再现。在标志 0x00 下，相同的 99 字节采用另一条路径：主机发送每个记录一次（每秒 6.3 条，然后没有，而在普通 0xA0 下每秒发送 115 到 257 条）。两个零售站都标记批量确认 0xA0 并将它们发送到其 /24 的 LDN 广播； `bin/sv_join.py` 在设置位 5 时压缩主体（`--ack-flags`、`--ack-entries`、`--ack-dest-bits`、`--ack-sweep`）。
### 流中的第一个记录带有 INITIALIZED

电台的第一条记录带有带有START、END和ZLIB的INITIALIZED，标志0x1F；后来的记录
0x17。作为 0x17 发送的第一条记录从未被确认（198 次发送）；如 0x1F，它会在 90 毫秒内得到确认。在第一个记录上使用 zlib 批量确认和初始化时，除了源变量 id 和 nonce 之外，加入方的标识与所有 44 个记录中的一对加入方的字节相同。模拟和零售主机向 47 确认（掩码 `feffffffff01`，后面是 `field_0x50`），发送一次记录，并发出类型 5 电台更新，列出两个电台及其玩家块。
## 游戏机托管

除了 Net 0x11 中的四个站插槽外，主机还必须发送：

|主机发送 |它一定是什么 |
|---|---|
|会话加入响应 | 41字节：无路由字节，站索引1，连接顺序1，序列ID 0，+8处的四个随机字节（阿尔宙斯的43字节形式被重传）|
|会话类型 1 加入确认 |没有什么;实机两秒内发完剩余一张|
|会话类型 5 电台列表 |两次：在序列 id 0 下加入响应，然后在下一个 id 下（零售主机：1.5 到 2 秒后）|
|该列表中的每个电台 | 79 字节：位置 ID、地址和端口、站点索引、big-endian u16 加入顺序、NAT 字节、IPv6 标志、32 字节令牌、计数、玩家记录。无路由字节（阿尔宙斯的为 81）|
|其中的玩家姓名|一个空格 (0x20) |
|每个会话回复的消息标志 | 0x00 |
|可靠的0x7C | ack单项形式，无目标位图；未经确认，游戏机会无休止地重新发送频道表（经测量，九十秒内一千次）|
|可靠的每条数据消息 0x7C |九字节标头，destination_bits 0，无位图 |
|净0x11 |一次;重复是在已坐站的新连接请求 |
|净0x50，更新属性| 0x11 之后 0.2 秒，每 500 毫秒直到该站的 0x51，其中四十个游戏在 +0x82 处广告字节 |
|实时传输时间 |除了答案之外还有自己的请求（一对主机：每 410 毫秒）|
|开幕|加入响应、首台列表、频道表、双流打开、时钟应答、Net 0x50 以及座席后的所有 44 条记录（零售主机：0.3 秒内）；钥匙-0x80 在游戏机的交换屏幕绘制之前打开（[打开频道](#opening-the-channel)) |

每个会话的四十个游戏广告字节变化：零，或+0x21处的非零值（`648cf4`，
`8170f0` 和 `fb149700` 见），其余为零。对于 `--channel 6`、`--player-name RyuPlayer` 和 `--host-player-id
00000000000000010000000000000000`，除了会话 id 之外，NetworkInfo 还匹配实时模拟的朱主机。通过这些设置，游戏机的第一个加入保持不变；在席位之上失败的会话会导致重复连接（测量十六到五十七次）。
### 最低待定金额以及 5 和 6 的差距

电台的 id 5 和 6 永远不会发送（线路上有 44 条记录），其余的则乱序（一对主机：1, 2, 3, 46, 4, 7, 8, 19, 9, 15, 10, 16...）。每一条记录都宣告着
`lowest_pending` 1，目标位 3，位图 `[2]`，流 id 0。间隙由发送方在同一流上的下一个批量确认关闭，其 `lowest_pending` 从 1 步进到 47；然后，对等方使用空掩码确认设置为 47。左边为 1，对等方回答 `ack_id` 5，掩码 `feffffffff01`，所有会话。也接受无间隙的 ID 1 到 44；没有零售发件人使用它们。

发送者可以只推进`lowest_pending`过去已确认的记录。在初始突发之后直接前进到 47 可以隐藏丢失的身份块：对等方确认 47，而 StreamData 块仍然不完整并且永远不会宣布该站。

两个 SV 启动器都保留 `reliable5.SendWindow` 作为身份集。相应的bulk-ack条目释放其`ack_id`以下的记录以及由其选择性掩码命名的记录。每 250 毫秒，未确认的记录将连同其原始序列 ID 和 Pia 消息标志 `0x40` 一起重新发送。传出数据和批量确认标头声明最低记录仍处于待处理状态，即当该组完全确认时为 47。这保留了故意的间隙 5 和 6，同时保留了实际损失。

第一条 INITIALIZED 记录丢失后，所有 44 条记录均未得到确认，需要重试整个记录集。丢失的中间记录会自行重试。
## 游戏自己的协议，来自一对

从两个进行交易的模拟朱 4.0.0 实例进行测量，每个实例记录其发送的每个数据报告。交换运行在 Reliable 0x7C 上；广播流仅携带身份交换。
### 端口 2：公告、加入和答案

Reliable 0x7C（一个站）和BroadcastReliable 0x80（每个站）的端口2承载游戏的会话消息。轮询器 `0x1954978` 将 `[0x475ea70]` (`0x19549e4`) 和 `[0x475ea7c]` (`0x1954a54`) 读入调度程序 `0x1954aec`：第一个字节，类型 1 到 0xD，表`0x3c68988`。三种类型的交换：

|时间 |车站|电线|类型 |字节|
|---|---|---|---|---|
| 0.00 | 0.00 主机 | 0x80 端口 2，zlib | 7 | 167 膨胀：`07b901b905b906010200bc09`，9 个零字节，`bc8080`，128 个零字节，`000000b90183`，主机站 ID，`00` |
| 0.09 | 0.09 加入 | 加入0x7C 端口 2 | 3 | `03b90200bc09` 和九个零字节 |
| 0.15 | 0.15 主机 | 0x80 端口 2 | 9 | `09b9030000b90183` 和加入方的站id |

编码是通道表的（`pokeldn.ldn.channel_table`）加上标签`0xbc`，一个字节字符串：标签，长度为整数，字节。类型7是一个五元组的元组（作者`0xe464fc`）：

    b9 06 ...   the type-1 body as a tuple of six: kind, capacity, a zero byte, the name as a
                nine-byte string, the data as a 128-byte string, the data length
    key         body +0x8e, the relay's counter +0x1c4 before it steps
    index       body +0x8f, the relay's counter +0x1c0 masked to seven bits, before it steps
    b9 01 ...   a tuple of one u64, the station id of the type 1's sender
    0           body +0x98
 类型9是连接槽键的元组、结果字节和一个u64的元组。

类型 7 是中继的类型 1：类型 1 处理程序 `0x18ceb70` 无条件复制 0x8e 字节主体，标记密钥和索引，步进两个计数器，附加发送者的站 ID 并将其排队等待类型 7 编写器（队列 `+0x200`，跨步 0xa8）。 `0x18d5a58` 向一个站点发送 port-2 消息，当目标是自己时，通过 `0x1954aec` 进行调度，因此主机中继自己的类型 1。

1型本体（`0x18ab760`）：

    +0x00  kind
    +0x01  the slot's capacity: 2 for kinds 1 to 3, 4 for kinds 4 to 8 and 12, 0 for kinds 9 to 11
    +0x02  zero
    +0x03  a name of up to eight characters, NUL-terminated in nine bytes
    +0x0c  up to 128 bytes of data
    +0x8c  the data length
 交换的类型1是类型1，容量2，空名称，无数据。槽将主体保持在槽 `+0xd0`（构造函数 `0x18b73a0`），因此其密钥 `0x12fcabc`（槽 `+0x15e`）是主体 `+0x8e`。每个中继的类型 1，无论是自己的还是对等的，都会步进密钥；只有 `0x12fbef0` 将计数器归零。连接命名键 0（如 `03b90200bc09` 所做的那样）仅与计数器清零后的第一个公告匹配。

类型 3 处理程序 `0x1981e94` 将连接的第一个字段与槽键 (`0x1981ed4`) 进行比较，并在接受时将类型 9 (`+0x270`) 排队，否则类型 0x0D、`0d b9 01` 和代码，在
`+0x350`：

|代码|拒绝因为|
|---|---|
| 1 |没有插槽具有连接密钥 (`0x1981ffc`)，或者 `0x279c8fc` 拒绝 |
| 2 |插槽已满： `0x18f80c8` 针对容量 `0x1e64914` 读取，或 `0x279c9a0` 返回 0xfd |
| 3 |连接名称的 FNV-1a 64 哈希与插槽的 (`0x1e648a0`) 不同 |
| 4 |插槽已关闭（`0x1e64924`，插槽`+0x160`，创建插槽时清除）|

类型 0x0D 转到 `0x1954f3c`，它需要 `0xb9`，解码单元素元组 (`0x279c0e8`) 并调用接收者 `0x279c1ac` (`0x1954f78`)：

    0x279c1b8  ldr  x8, [x0, #0xb8]     the pending request
    0x279c1bc  cbz  x8, ret             none: nothing happens
    0x279c1d0  strb w9, [x8, #0x43]     result = the code
    0x279c1d8  strb #1, [x8, #0x42]     done
    0x279c1dc  bl   0xc8e6c4            wakes the request's waiter at +0x48
 它既不检查请求类型 `+0x40` 也不检查完成字节，因此来自加入方的 0x0D 会完成游戏机用其代码持有的任何请求。类型 9 接收器 `0x18b65c8` 通过时隙字节选择一个对象，应用该消息，然后丢弃它，除非 u64 是该站自己的 id
`[[0x46d0a08]] + 0xb8`。

站 id 是 Pia 常量 id，作为大端 u64（对于 MAC，`7f00020000020000`）
`02:00:7f:00:00:02`);对于实机，类型 9 携带来自其会话加入请求的常量 id。 `pokeldn.sv.port2` 构建三个（固定在 `tests/test_sv.py` 中）； `bin/sv_host.py
--announce` 在座席后发送类型 7，并用类型 9 应答类型 3。
### 发送公告的交换作业

> 本节已随上游更新，以下内容暂保留英文。

Link Trade creates the job at `0x1e2ea54`: config `BoxTrade` (`0x3aefac8`), factory `0x1e2f3d4`,
mode 4, need 2. Two script bindings reach it: `0x1e2e9bc` (GOT
`0x46d6608`, stored by `0x1b9c8c4` into `0x4717068`, tail call) and `0x1e2ec84` (GOT `0x46d6610`,
`bl` at `0x1e2ee40`). The job (constructor `0x1e3bd10`, vtable `0x44568a8`, Update `0x1e51a04`):
result `+0x40`, state `+0xb8`, session handle `+0xc0`, mode and need as u16 at `+0xc8` and `+0xca`,
slot object `+0xd0`, request handle `+0xf8`.

| state | address | what it does |
|---|---|---|
| 1 | `0x1e51a84` | result 3 if the station count `[[0x46d0a08]]+0xe0` is below need, result 1 if `0x18ab520` rejects the mode (0, 5, above 8); else waits, no timeout, for `need` finished identity blocks (`0x1e52004` over `[[job+0xd0]+0x10] - 0x28`), then state 2 on the master (`0x1639910`: own id `+0xb8` equals master id `+0xc0`), 4 on a client |
| 2, master | `0x1e51b2c` | kind `0x18ab550(mode)` (modes 1 to 8 give 2, 3, 4, 1, 0, 5, 5, 8), then request `0x18ab658`; null ends with result 8 |
| 3, master | `0x1e51ca8` | waits on the request, no timeout; result 0 goes to state 6, else the job ends via `0x1e5086c` |
| 4, 5, client | `0x1e51b8c`, `0x1e51c74` | the same wait, 15 s limit |

| result | meaning |
|---|---|
| 1 | success, or the mode rejected |
| 2 | the session in state 3 |
| 3 | fewer stations than need |
| 4 | a client's 15 s timeout |
| 8 | no session, or the request refused |

The request `0x18ab658` builds the type-1 body and sends it through `0x18ab83c`, which returns null
while the relay's pending request `[relay+0xb8]` has done byte `+0x42` still 0 (`0x18ab860`,
`0x18ab8e8`) or the send fails. Otherwise it clears `+0xb8` (`0x18ab894`), stores a new request
(`0x18ab8a8`; `0x18abec0`: `+0x40` type, 0 for the announcement, `+0x42` done, `+0x43` result) and
sends the type 1 to the master id (`0x18d58b8`), itself on the master; a failed send clears `+0xb8`
(`0x18ab900`).

`0x18ab658` has four callers: `0x1e51b68` (BoxTrade state 2), `0x18ab34c` (the same in a sibling job,
vtable `0x4456490`), `0xa188f0` (vtable `0x4452e68`) and `0x1d99568` (vtable `0x44536d8`). Only the
four request creators write `+0xb8`; `0x18ab83c` and `0x2799b10` refuse while a request is pending:

| creator | request type | store | sole caller |
|---|---|---|---|
| `0x18ab83c` | 0, the announcement | `0x18ab8a8` | `0x18ab6bc`, in `0x18ab658` |
| `0x2799b10` | 2, a client's join | `0x2799bd8` (guard `0x2799b2c`..`0x2799b40`) | `0x1e635fc` |
| `0x2799c44` | | `0x2799cfc` | `0x1e639ec` |
| `0x2799d6c` | | `0x2799e30` | `0x1e63c88` |

The last three callers each sit in a function whose sole caller is in `0x1d98xxx` (`0x1d986d8`,
`0x1d98990`, `0x1d98c20`).

In a Link Trade, the type-2 creator is reached from BoxTrade state 4 at `0x1e51c40`, through
`0x1d986d8` and `0x1e635fc`. It runs only on the client after the master's slot is present
(`0x1d999f4`, `0x18c7a40`), retains the request at job `+0xf8`, and enters state 5. The other
callers of `0x1d98698` belong to other job classes.

The drain `0xe44cf0` walks queues `+0x1c8`, `+0x200`, `+0x238`, `+0x270`, `+0x2a8`, `+0x2e0`,
`+0x318`, `+0x350` in order; a composer returning false ends the drain for the frame, so a stuck
type 7 holds the type 9 and 0x0D behind it. The
type-7 composer `0xe45740` dispatches locally alone when the station count is 1; otherwise it asks
`BroadcastReliableProtocol::vfunc20` (`0x6e6638`) whether 0x80 port 2 can send, sends with
`0x107e060`, and dispatches locally only when both succeed. vfunc20 refuses with 0x2c27 when no
entry of the destination list `[window+0x40]` is set (`0x6efb98`), 0x4c0d when the window lacks room
for the fragments (`0x6f1ef8`), 0x10408 with no session or window. Pia fills the destination list on
the station-join event ([Who a window sends to](pia.md#who-a-window-sends-to-pia-6)).

The type-7 receiver `0x18b566c` creates and applies the slot and, for a pending type-0 request and
the console's own station id (body `+0x90`), completes it with result 0: a master stays in state 3
until its own type 7 has left on the wire. Nothing between relay and wire reads RTT or a timer.

The 0x81 identity is one block per station on the port of its index (handles `0x475ea48 + 4*index`),
moved by the stream send API `0xe22188` and receive API `0xe22458` for three objects of one layout:

| object: Update, vtable | send | receive | block |
|---|---|---|---|
| `0xe21104`, slot 13 of `0x4455ec0` | `0xe21a44`, `bl` at `0xe21dc4`, `w2 = 0xf388` at `0xe21db8` | `0xe2150c`, `0xe2170c`, `w3 = 0xf388` at `0xe21708` | 0xF388 = 62,344 |
| | `0xa62c5c`, `w2 = 0xff008` | `0xa64ddc`, `w3 = 0xff008` | 0xFF008 = 1,044,488 |
| `0x1e5f87c`, slot 13 of `0x4458698` | `0x1e617a8`, `0x1e61980`, `w2 = 0x97e08` | `0x1e61a74`, `0x1e61c0c`, `w3 = 0x97e08` | 0x97E08 = 622,088 |

Only the 0xF388 block goes on the wire in a trade, so the job's `+0xd0` object is of that class
(instance untraced; built through `0x1e34b6c` -> `0x1e35e88`).

`0x1e52004` counts slots at `+0xd0 + 0x30*k` (four) holding a peer pointer with byte `+0xd8` set. The console's own slot gets it in `0xe21154` (`memcpy(slot, [+0x90], 0xf388)` at
`0xe21248`, `+0xd8 = 1` at `0xe21258`; called from `0xa536e0`, `0xd6dc88`, `0xe21128`, `0x195160c`).
A peer's slot gets it in `0xe212b8` (called from `0xa536f0`, `0xd6dc98`, `0xe21138`) only when the
send to the peer (`+0xda`) and the receive from it (`+0xd9`) have started, the own 0x81 stream is in
state 3 (`0xe2144c`, every own chunk acknowledged) and the peer's in state 6 (`0xe21404`, every peer
chunk received); state 7 clears a flag
([Protocol 0x81](pia.md#protocol-0x81-the-stream-broadcast-reliable-transfer-pia-6)). The 0x97E08
class has the same pair, `0x1e60284` and `0x1e615e8`.

On the wire the type 7 follows the console's last record of its own set, usually within 0.11 s
(0.020 to 0.106 s in 37 of 40 announced seats; 0.545, 0.864 and 3.902 s in the others).

The relay is a 0x388-byte object (vtable `0x44e56f8`), singleton `[0x46da9c0]` = `0x4739430`,
created by `0x165a200` from `0x1659b70` only when none exists (`0x1659b18`). Its station-event
handler is `0x12fbb90`, via the thunk `0x2b71650`:

| event | effect |
|---|---|
| 0, a station joined, on the master | `0x12fbf8c` sends it the current slots unless it is the master |
| 1, own id | a pending request not done completes with result 5 (`0x501` at `+0x42`), then `0x12fbef0` |
| 1, the master's id | `0x12fbef0` |
| 1, any station, on the master | then `0x12fcebc` drops the elements it relayed |

`0x12fbef0` removes every slot through `0x12fc644` (completing a pending type-1 request whose key
matches), empties seven queues (all but `+0x1c8`) and zeroes `+0x1c0` and `+0x1c4`; it leaves the
request at `+0xb8`. A type-0 request is completed only by the type-7 receiver, the type-0x0D
receiver and the own-leave event; type 2 by the type-9 receiver `0x18b6710`, type 3 by the type-0xA
receiver `0x1945404`, type 4 by the type-0xB receiver `0x279be18`.

The own-leave path at `0x12fbc3c..0x12fbc4c` completes a client's pending type-2 request with
result 5 (`+0x40..+0x43 = 02 00 01 05`). The next creator can replace that completed request
without restarting the game, including after a disconnect before type-9 acceptance. A leave event
for the master's id alone does not complete the request: `0x12fbc70..0x12fbc84` calls only
`0x12fbef0`. The client's BoxTrade job still ends at 15 s with result 4, because state 5 tests the
clock (`0x1e51c74..0x1e51ca4`, base `+0x108` set at `0x1e51c6c`) before it polls the request through
its weak reference `+0xf8` (`0x18ab588`, `0x18ab614`). Neither the timeout path `0x1e51d50` nor the
job destructor `0x1e51740`, which only releases the weak reference through `0x18ccdb4`, touches the
relay's request. It stays pending at relay `+0xb8`, and `0x2799b10` and `0x18ab83c` refuse, until
the type-9 or type-0x0D receiver or the client's own leave event completes it.

The relay lives until the application exits, so a request pending at `+0xb8` survives every seat,
search and menu until a completer runs. Its holder `0x4739430` (GOT `0x46da9c0`, guard `0x4739440`
via GOT `0x46da9b8`) is written only by the assignment `0x165a2b4` (from the creator, `bl` at
`0x165a230`), the reset `0x279d610` (`str xzr` at `0x279d62c`, then destructor and free), reached only
from the relay's own destroy slots `0x279d5ac` (slot 3) and `0x2b71660` (`+0x20` interface slot 1),
which have no direct callers, and the static destructor `0xa15f74` (`__cxa_atexit`). A generic
virtual call on slot 3 cannot be excluded statically. Vtable `0x44e56f8`: slot 0 `0x279a7b0`
(destructor), 1 `0x2b7164c`, 3 `0x279d5ac`, 4 `0x12fbb90`; interface `+0x20` slots `0x2b7165c`
(`ret`) and `0x2b71660`; interface `+0x28` the listener thunk `0x2b71650`. The base constructor
`0x165b0c8` (from `0x165a998`) installs a second vtable `0x44e5768` with the same destroy slots and
sets `[holder+8] = 1`.

The creator registers the `+0x20` interface with `0xf0ba9c` (`bl` at `0x165a244`) in a finalizer list
(up to 0x400 entries at `0x4763a18`, count `0x4765a18`), walked in reverse only by `0x27aff48` (slot
0) and `0x27b0054` (slot 1, then zeroes the count), both called only from `0x20e9c78`, slot 5 of
vtable `0x44e6be0`, on the path from `0x92d648` (slot 5 of `0x443ffd0`) that ends in
`nn::account::CloseUser`: the application's finalize.

### 打开频道

|时间 |车站|港口|字节| |
|---|---|---|---|---|
| 0.29 | 0.29 主机 | 1 | 31、初始化| `b90104b902b9027b0001b902b902320101b902b902320201b902b902320301` |
| 1.84 | 1.84 加入 | 加入1 | 31、初始化|相同的 31 字节 |
| 2.43 | 2.43 加入 | 加入2 | 15、初始化| `03b90200bc09000000000000000000` |
| 9.00 | 主机 | 1 | 11 | 11 `b90101b902b90280800001`，加入方发回同样的信息|

端口 1 是通道表（阿尔宙斯机制）：只有在其对等方宣布密钥后，站点才会发送密钥。方连接表是按主机的字节进行的；在到达之前，主机会停留在搜索屏幕上。主机的键 0x80 打开必须先出现：一个加入方，其交换屏幕在它从未发送第一个游戏消息之前绘制，而宝可梦上的 A 不提供菜单。 0x7C 可靠标头为 9 个字节，无位图、序列和最低挂起消息本身；打开的是标志0x0F，稍后更新0x07。

通道必须在交换屏幕绘制之前打开。稍后打开会留下一个模拟的 朱 4.0.0 交换框，没有选择光标；截止日期取决于同行。一个实机在座位绘制菜单后打开自己的钥匙 0x80 9.15 秒，主机在 6.0 秒打开，而不是在 11.0 秒打开。
### 交换

端口 0 承载游戏：一个四字节头和一个主体。

|时间 |车站|身体| |
|---|---|---|---|
| 9.15 | 9.15 加入 | 加入`80000100`，两个 zlib 片段 |第一条游戏消息|
| 9.31 | 9.31 主机 |相同| |
| 58.2 | 58.2 主机 | `80000200` + 348 字节 |提供的宝可梦|
| 67.6 | 67.6 加入 | 加入`80000200` + 348 字节 | |
| |要么 | `8000040100` |取消（接收者`0x1e68678`）：玩家退出等待|
| 112.7 | 112.7 主机 | `80000300` | |
| 116.0 | 116.0 加入 | 加入`80000300` | |
| 117.5 | 117.5 加入 | 加入`80000500` | |
| 117.5 | 117.5 主机 | `80000500` | |
| 117.6 | 117.6两者 |端口 1，`b90101b902b90280800101` |打开下一个键的表更新|
| 117.7 | 117.7两者 | `80010103`，`80010203` | |
| 117.8 | 117.8两者 | `80010106`，`80010206` | |
| 118.2 | 118.2两者 | `8001010b`, `8001020b` | |
| 118.9 | 118.9两者 | `8001010e`，`8001020e` | |
| 119.2 | 119.2两者 |端口 1，`b90101b902b90280800100` |关闭它的表更新 |

仅在电台宣布密钥 0x80 后，主机才将其第一条游戏消息发送四次（两个片段，然后在接下来的两个 id 下再次发送，标记为 `0x1b`、`0x15`、`0x13`、`0x15`）。发送之前，端口 0 上没有任何内容被调度；作为两个发送（就像一对主机对其克隆所做的那样），该站回答 `ack_id` 5，`lowest_pending` 5（一对的加入方：4 和 3），游戏永远不会看到下一条消息，并且游戏机保持“等待响应”（`--send-on-open`）。

0x7C 上的主机 ack 的 `lowest_pending` 字段携带其自己的下一个序列，如 0x81 上一样。超过电台的最后一个序列后，电台会等待该号码并丢弃主机在 `0x6f03cc` 处的下一条较低消息（[接收器在静默中丢弃的内容](pia.md#what-the-receiver-discards-in-silence)）；编号在提交时有所不同，其中电台首先提交。 `8001`步骤成对运行，01和02在第四字节步进03、06、0B、0E下；交换适用于它们，并且两个屏幕都返回到交换菜单。

针对 `bin/sv_host.py`，主机的交换流消息编号为 5（提议）、6（确认）、7（提交）、8 至 15（步骤）；游戏机的5、6、7和8至11，其密钥0x180打开和关闭其端口1消息3和4；其主机提议的确认为 `ack_id` 6、`lowest_pending` 5。两个相同的训练器可以交换。
### 电台自己的提议之前发送的确认

当提议 `80000200` 仍在排队时，切勿发送确认 `80000300`：按该顺序发送它们的实机崩溃（黑屏，系统错误），记录本身存储未经检查。两个启动器上的 `--offer-after-open` 都将要约挂在对等方的密钥 0x80 公告上，并且两个启动器都不会在已为同一站和端口排队的交换消息之前排队交换消息。

交换动画遵循游戏机的最后一步 `8001010e`，并且不包含交换消息。在状态为 `b90101b902b90280800100` 后，游戏机不会发送任何应用程序数据，直到玩家退出。
### 一席多交易

钥匙 0x0080 保持打开状态；钥匙 0x0180 每次交换都会打开和关闭。第二次交换重复循环，序列运行在（主机提供 16、确认 17、提交 18、步骤 19 到 26）上，并且没有新的关联、会话交换或身份。 `TradeStage` 和 `JoinerTradeStage` 获取一个记录列表，每次交换一个； `--trade-offer` 是可重复的。游戏机请求主机迁移后保留席位尚未得到验证。
### 第一条游戏消息及其携带的内容

`80 00 01 00`和2557字节，在两个可靠的片段中，开始然后结束（来自一对主机的238个压缩字节，来自实机的195个字节），每个都有自己的zlib流（`484b`）；该信息是两个通货膨胀的串联：

    b9 02          a tuple of two fields
    bc 81 f6 09    a blob, 0x9f6 = 2550 bytes
    ...            2550 bytes
    04
 blob 是 850 个小尾数三字节值，大部分为 1，其余位掩码（`0x0fffff`，
`0x0002ff`, `0x00003f`, 0)，每个站：站之间的值不同（实机和一对主机之间有 38 个条目；条目 36：`0x040000` 与 `0x0fffff`）。该指数的具体内容尚不清楚。一对主机的四个片段，重播后，被实机接受。
### 交换消息携带的记录

`80 00 02 00` 消息的 348 字节正文是常量 `bc 81 58 01` 和 Gen 8 加密 (`pokeldn/gen8.py`) 下的 344 字节 Gen-9 队列记录（PKHeX 的 PK9）：来自四个 0x50 字节块
0x08 由 `(EC >> 13) & 31` 排列，16 位字上的 LCG `seed = seed * 0x41C64E6D + 0x6073`，以及解密主体的 16 位校验和，直至 0x148。 0x148 处的行尾位于排列和校验和之外，并根据加密常数重新播种 LCG。

    0x000  u32  encryption constant, in the clear
    0x004  u16  sanity, 0 on every record measured
    0x006  u16  checksum, in the clear
    0x008       four 0x50-byte blocks, encrypted and permuted        -> 0x148
    0x148       level, a pad byte and the six stats, encrypted       -> 0x158
 场图是PK9的[`PKHeX.Core/PKM/PK9.cs`]； `pokeldn/gen9.py` 对其进行读写。

|偏移|领域 | |偏移|领域 |
|---|---|---|---|---|
| 0x08 |物种，内部索引| | 0x8A |当前HP |
| 0x0A |持有物品 | | 0x8C |六个 5 位 IV，然后是鸡蛋和绰号位 |
| 0x0C | 训练家ID，秘密ID | | 0x90 |状态条件|
| 0x10 |经验| | 0x94 | tera 类型、原始和覆盖 |
| 0x14 |能力，则其在 0x16 | 的位 0-2 中的编号| 0xA8 |处理程序名称，26 字节 |
| 0x18 |标记| | 0xC2 |处理员性别、语言、当前处理员 0xC4 |
| 0x1C |人格价值| | 0xC6 |处理程序 ID、友谊、内存 |
| 0x20 |自然，统计自然| | 0xCE |版本，战斗版本|
| 0x22 |命运在位 0，性别在位 1-2 | | 0xD0 |形式论证 |
| 0x24 |表格| | 0xD4 |附丝带，语言为 0xD5 |
| 0x26 |六辆电动汽车，hp atk def spe spa spd | | 0xF8 | 初训家名称，26字节|
| 0x2C |六大竞赛价值观| | 0x112 |教练友谊与记忆|
| 0x32 |扑克| | 0x119 |鸡蛋日期，见面日期为 0x11C，服从级别为 0x11F |
| 0x34 |丝带和标记旗帜| | 0x120 |鸡蛋地点、见面地点|
| 0x48 |身高标量、体重标量、比例| | 0x124 |球 |
| 0x4B | DLC 移动记录标志 | | 0x125 |位 0-6 中的达到水平，位 7 中的培训师性别 |
| 0x58 |昵称，26字节UTF-16LE | | 0x126 |超级训练旗帜|
| 0x72 |四个动作，他们的PP在0x7A，PP上涨在0x7E | | 0x127 | HOME 追踪器 |
| 0x82 |四个重新学习动作| | 0x12F |基础游戏移动记录标志 |

从 344 个零字节重建的记录和字段 `read` 逐字节报告（`tests/test_sv_pokemon.py`）。 Species 是内部索引，来自 National Dex 的 917 [`PKHeX.Core/PKM/Util/Conversion/SpeciesConverter.cs:92`]。错误的块顺序在校验和中幸存下来；记录阅读作为一个连贯的宝可梦钉它。 `bin/sv_host.py` 打印两个提议，
`--offer-out FILE`写入游戏机（在第一个之后提供N到`FILE`，在扩展名之前使用`-N`），并且`--trade-offer`采用344字节记录（明文或加密），348字节主体或352字节消息。
### 合成记录

由 `pokemon.build` 由零字节组成的记录，或用 `bin/sv_host.py --offer-set` 编辑的记录（昵称、昵称标志、个性值、IV），与组成的每个汇总字段一起交易到零售朱保存中。交换屏幕绘制了一个没有合法性检查的合成记录；主机写入校验和。摘要的训练家 ID 是
`(TID16 | SID16 << 16) % 1000000`（12345和54321开奖为993401，8131和64817开奖为855043）；特征线来自加密常数和 IV。

等级跟随经验：字节0x148在100级零经验到达1级，1,000,000经验为100级。六条增长曲线（`PKHeX.Core/PKM/Util/Experience.cs`）需要1,000,000、600,000、1,640,000、1,059,860， 100 级时为 800,000 和 1,250,000。物种表
`personal_sv`（0x50每个物种和形式的字节，`PersonalInfo9SV.cs`）的基本统计数据为0x00，性别比例0x0C，生长曲线0x0F，三种能力0x12（物种132：曲线 0，能力 7、7、150)。接收方游戏重新计算队伍统计数据：

    HP    = (2 * base + IV + EV/4) * level / 100 + level + 10
    other = ((2 * base + IV + EV/4) * level / 100 + 5) * nature
 一个百变怪，具有完美的 IV，没有 EV，中立性质，在 1 级显示 12 和 6 x5，在 100 级显示 237 和 132 x5，从零统计字段开始；在 1 级发送的 HP 99/99 到达时为 12。
### 加入方按顺序发送的内容

游戏第一条消息之前一对的加入方，一次捕获的次数：

|时间 |留言 |
|---|---|
| 0.04 | 0.04会话加入请求 |
| 0.17 | 0.17 Net 0x12，与主机的 0x11 | 的序列相呼应
| 0.38 | 0.38 Net 0x51，与主机的 0x50 | 的序列相呼应
| 1.63 | 1.63会话类型6，确认站更新|
| 1.68 | 1.68十一个批量确认和流在 0x81 端口 0 和 4 上打开 |
| 1.68 | 1.68 0x7C 端口 1 上的通道表 |
| 1.82 | 1.82克隆时钟 0x77，十八个零字节；主机回答 1，十六个字节，一个尾随字节 |
| 2.03 | 2.03 0x81 端口 1 上有自己的 44 条记录 |
| 2.43 | 2.43 0x7C 端口 2 上的打开 |

无人应答，游戏机重复 Net 0x11 和 0x50； 0x12 和 0x51 阻止它们（212 个网络消息在一个没有的座位上，2 个有）。
### 交换的加入方一方

一对加入方的整个 0x7C 脚本，每个消息的序列在其端口上：

|港口|序列|留言 |
|---|---|---|
| 1 | 1 |频道表、主机的四个键、INITIALIZED |
| 2 | 1 |类型 3 连接、`03b90200bc09` 和九个零字节 |
| 0 | 1 至 4 |第一场比赛留言，两次结束|
| 1 | 2 | `b90101b902b90280800001`，钥匙0x80打开，第四个片段之后|
| 0 | 5 |提供的宝可梦|
| 0 | 6 |确认|
| 0 | 7 |提交，首先发送 |
| 1 | 3 | `b90101b902b90280800101`，钥匙0x0180打开后，主机自己|
| 0 | 8 至 11 |每个步骤的回显 `8001 01 SS` (03, 06, 0B, 0E)； `8001 02 SS` 没有任何东西 |
| 1 | 4 | `b90101b902b90280800100`，关闭|

主机的钥匙 0x80 打开后 0.15 秒，身份进入，加入方自己的钥匙在 0.21 秒后打开。

`lowest_pending` 规则也绑定了加入方：它自己的下一个序列在 0x7C 上，超过了其 0x81 批量确认上的最高记录 ID。主机编号中的一个数字使主机的接收基地经过加入方的后续消息，这些消息在 `0x6f03cc` 处被丢弃。

`pokeldn.sv.trade.JoinerTradeStage` 是这一侧作为状态机，由 `bin/sv_join.py
--trade-offer` 运行（`--send-on-open` 用于在密钥 0x80 上门控的身份片段打开）。
`tests/test_sv.py` 用该对消息中主机的一半来驱动它，并固定加入方的一半。
### 交换改写了什么

在实机上交易并返回的复合记录有 27 个字节、7 个字段：

|领域 |发送时 |当它回来时|
|---|---|---|
| `current_handler` | 0 | 1 |
| `ht_name` |空 |游戏机玩家的名字 |
| `ht_language` | 0 |接收游戏机的语言（3，法语）|
| `ht_friendship` | 0 | 50 | 50
| `nickname` |空 |游戏机语言中的物种名称 |
| `current_hp` | 0 |计算出的最大HP（237，100级百变怪）|
| `stats` |零|游戏计算出的六个|

其他所有内容均按发送状态保留。一个空名称作为物种名称返回，如《Sword 神秘礼物》记录（`docs/swsh_gift.md`）中那样。
### 加入搜索游戏机：一次交换，以及什么决定了座位

`bin/sv_join.py` 通过其链接交换搜索与零售朱托管进行交易，编号为一对加入方。以站点更新为座席，以type-3 join应答游戏机的通告，游戏机打开密钥0x80后发送4个身份消息，并应用
`lowest_pending` 规则同上。
#### 座位由什么决定

通过搜索托管的实机要么运行游戏，要么将主机角色交给其加入方。游戏在 3 到 7 次浏览尝试后托管一次（`RandomMatchingSeq` `0x26e182c`，计数器
`rand%5+4`）并等待成员 3000 + rand%1000 毫秒，加上每个加入的成员 5000 毫秒（WaitMember，`0x26df898`）。超时等待会以 JoinRandomRecover `0x26f507c` 结束，从而离开会话。离开其中的另一个站的主机运行 `LeaveMeshWithHostMigrationJob`（仅从网格离开 `0x6d4040` 开始）：它将会话类型 7 发送到网络排名最低的站 (`0x6a012c`)，然后 NetStartHostMigration `01400000`，每 0.3 秒一次，最多 4 秒（[离开](#leaving)）。在 WaitMember 内接受加入的方加入会看到游戏运行；在休假期间，在接受之后接受的一帧或两帧后得到类型 7。方加入的开头不起作用。 `--join-delay 5` 在第一个座位上画了 7 型，并带有零售朱；游戏玩家在公告发送后也退出了。

交出角色的游戏机破坏其网络并重新浏览。 `--take-host`（默认）使 `bin/sv_join.py` 在公告之前收到的类型 7 上运行
`bin/sv_host.py` 在座位的频道上，并使用应用程序的主机标志进行编码，就像 `bin/pla_join.py` 为传说阿尔宙斯所做的那样；零售朱加入了该主机并完成了交换。

运行游戏，游戏机按顺序发送：

| | |
|---|---|
|座位|类型 5 站更新命名加入方的变量 id 和其请求所述的玩家 id，然后是 41 字节的加入响应 |
|开幕 |所有 11 个流上的批量确认，0x81 端口 1 上的 11 字节记录和端口 5 上的另一个记录 |
|它的身份| 0x81 端口 0 上有 46 条记录，它确认加入方的 44 至 47 |
|它的频道表|在 0x7C 端口 1 上，按键 `0x007b`、`0x0132`、`0x0232`、`0x0332` |
| `0db90101` |在 0x7C 端口 2 上，代码 1，仅响应在公告之前发送的类型 3 加入 |
|公告|在 0x80 端口 2 上，zlib，膨胀 167 字节：类型 7，类型 1，容量 2 和游戏机的站 ID |

方加入以类型 3 加入应答公告（`--port2-now` 改为使用通道表发送它）。在任何加入响应之前，一个实机单独加入了一个加入方并进行了电台更新；等待加入响应的方加入不会在所有会话中发送任何内容。
## 离开

退出座位的游戏机根据其角色运行两项 Pia 工作之一。每个都等待其对等点并放弃计时器。

联合游戏机运行 `LeaveMeshJob`。 SendLeaveRequest `0x6db590` 发送 Session type-3 离开请求（[docs/pla.md](pla.md#leaving) 中的布局）并设置 500 ms 的截止时间 (`0x6db6a0`)； WaitLeaveResponse `0x6db7b0` 在到期时重新发送，并在第四次发送（`[job+0x6c]` 经过 2、`0x6db8e8`）后或一旦设置 `[job+0x69]` 后完成。会话调度程序（`0x6d4960`，表
`0x3c0cd3b`，类型0到0xA）将类型4传递到`0x6d7b10`，它将`[job+0x69]`设置为17字节消息，其字节5到16是站自己的位置ID：

    04 | u32 random | location id (12), copied from the request
 A 主机的 type-3 处理程序 `0x6d7894` 一旦通过常量 id 和变量 id 找到站，就会准确地写入（在 `0x6d7a50` 处键入字节，从 `0x6c70a8` 中提取新的 xorshift，在 `0x6d7ad8` 发送）。在没有得到答复的情况下，实机发送了四个间隔 0.49 到 0.54 秒的离开请求，并在第一个（一个跟踪会话）后 2.04 秒取消身份验证。得到答复后，它会发送一个离开请求，并在 0.04 秒后解除身份验证。
`bin/sv_host.py` 回答第一个（`--no-leave-response` 未回答）；
`tests/test_sv_departure.py` 在unicorn下通过`0x6d7b10`运行答案。

通过搜索托管的游戏机将主机角色交给主机。 `LeaveMeshWithHostMigrationJob` 将会话类型 7 发送到下一个主机，并每秒重新发送一次 (`0x6df050`)，直到类型 8 命名该站 (`0x6ded94`)，在 5 秒后放弃 (`0x6defb8`)。然后，`NetDestroyNetworkJob`以其主机迁移的形式，等待每个客户端收到连接状态更新（最多4秒，`0x6ac68c`），每次发送NetStartHostMigration `01400000`（仅由`0x69d310`写入，仅从`0x6aca54`调用） 300 ms (`0x6aca98`)，直到网络的站计数为 1 (`0x6acaf4`) 或超过截止时间（4 秒，或更新等待超时时为 2 秒，`0x6ac984`），并破坏 LDN 网络。在线更新是 Net 0x11，带有迁移集；在加入方的 Net 0x12 后，45 毫秒后进行了第一个 NetStartHostMigration。客户端在 NetStartHostMigration 上启动哪个作业是无法追踪的； `NetHostMigrationJob` 使用 DisconnectNetwork 或 EmulateDisconnection (`0x6a93c4`) 打开。

立即回答类型 7 并占据席位的加入方会从游戏机中抽取 NetStartHostMigration 12 到 14 次，即类型 7 之后的最后 3.5 到 4.1 秒；在 LDN 广播以太类型 `88b7` 后，追踪到单座 7 型后，游戏机的网络出现故障 4.3 秒。在类型 7 之后留下 3.0 秒的加入方会看到游戏机的广告在 0.5 秒内消失，比游戏机自己的 4 秒截止时间早。 `bin/sv_join.py` 在第一次 NetStartHostMigration 时离开席位（`--stay-on-host-migration` 持有该席位）；在类型 7 发送 1 个 NetStartHostMigration 后 0.14 秒，它断开网络。

交换完成后，当游戏机离开时，两个启动器都会退出。未完成交换的座位让 `bin/sv_join.py` 恢复扫描（[结束运行](architecture.md#ending-a-run)）。
## 未解决

> 本节已随上游更新，以下内容暂保留英文。

- Why a console joined to `bin/sv_host.py` can acknowledge the host's announcement and never send its
  port-2 join.
- What a console does between its player backing out and its first departure message: none of the
  captures marks the button press. In one joiner seat the cancel `8000040100` preceded the type 7
  by 1.5 s.
