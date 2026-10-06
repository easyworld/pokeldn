---
title: The Let's Go cartridge and session
parent: Let's Go Pikachu and Eevee
nav_order: 1
---
# 盒式磁带、其密钥和会话

地址是 Let's Go 皮卡丘 1.0.2 的解压缩 `main` 中的偏移量，如 `tools/switch/nso_read.py` 所示：文本 `0..0xd32ba8`、来自 `0xd33000` 的rodata、来自 `0x1527000` 的数据。
## 标题是根据什么构建的

更新NSP携带程序NCA `2b7730a9e56498bbafac2002d4908c6b`（标题`010003f003a34000`，权利ID `010003f003a348000000000000000007`，密钥生成6）。其执行者持有`main`（13.0 MB压缩）、`rtld`、`sdk`、`subsdk0`和`subsdk1`；每个 `nn::pia` 和 `gflnet3` 参考都在
`main`。

    ./.venv/bin/python tools/switch/xci_read.py "<the .nsp>" --keys prod.keys \
        --nca 2b7730a9e56498bbafac2002d4908c6b --exefs 0 --extract main
    ./.venv/bin/python tools/switch/nso_read.py main main.bin
    ./.venv/bin/python tools/switch/rtti_names.py main.bin 0xd32ba8
 Pia 是静态链接的：269 个 `nn::pia` 类，2112 个命名虚拟方法。 `nn::pia::local` 包含 `Ldn*` 和 `Local*` 系列（`LdnCreateNetworkJob`、`LdnCreateSessionSetting`、
`LdnJoinSessionSetting`、`LocalProtocol`）。 `nn::ldn`是从nnSdk导入的（`CreateNetwork`，
`Connect`、`Scan`、`SetAdvertiseData`、`GetSecurityParameter`、`*Private` 变体）、GOT 插槽
`0x15fa1e0..0x15fa2a8`。在 Pia 之上，`gflnet3` 捆绑了协议缓冲区 (`lib/gflnet3/external/include/google/protobuf/`)。
## LDN 密码

    W3GoSMEn7RIIUQ89rzqBHGhGferRNb7K18ZBq2aNuj8Us9RO9Q9JYyGOZlLy8MYL
 64字节，`0xf73a50`，原始使用，与剑和盾相同。两个调用站点以文字长度 `0x40` 传递它：

    0x004db6b4  adrp x1, #0xf73000 ; add x1, x1, #0xa50
    0x004db6c4  mov  w2, #0x40
    0x004db6c8  bl   #0x5c0fb0              LdnCreateSessionSetting passphrase setter

    0x004dbba4  adrp x1, #0xf73000 ; add x1, x1, #0xa50
    0x004dbbb0  mov  w2, #0x40
    0x004dbbbc  bl   #0x5c1280              LdnJoinSessionSetting passphrase setter

`LdnCreateNetworkJob`（构造函数`0x5ce640`，Sword的偏移量）将密码短语保留在+0xC4，其长度保留在+0x104，并从它们之前构建`nn::ldn::SecurityConfig`
`nn::ldn::CreateNetwork`（`0x5ce988`，PLT 存根 `0xd31c78`）。
## Pia 游戏密钥

    p1frXqxmeCZWFv0X
 `0xefd659` 处有 16 个 ASCII 字节，维基百科列出的剑／盾、传奇：阿尔宙斯和朱／紫的文字键。一个调用站点将其存储到加密设置中，以模式字段为条件：

    0x0011a364  ldr  w9, [x19, #0x98]
    0x0011a368  orr  w9, w9, #2 ; cmp w9, #2 ; b.ne   (mode 0 or 2 takes the key)
    0x0011a374  adrp x9, #0xefd000 ; add x9, x9, #0x659
    0x0011a380  ldp  x10, x9, [x9]
    0x0011a384  stp  x10, x9, [x8]          x8 = setting + 0x24c

## Pia 头

版本 3（维基百科的 Pia 5.11-5.17）。初始化器 `0xd122d4` 将 magic 和 version 写入一个 64 位存储，`0x00000003_32AB9864`；验证器 `0xd12400` 检查魔法并
`(byte & 0x7f) == 3`。

    0x00  4  magic 0x32AB9864, big-endian
    0x04  1  0x80 (encrypted) | version (0x7F) = 3
    0x05  1  connection id
    0x06  2  packet id
    0x08  8  AES-GCM nonce
    0x10  16 AES-GCM tag, not truncated
    0x20     ciphertext
 wiki的5.11-5.21布局，Sword的版本4但针对版本字节； `pokeldn/ldn/pia4.py`。
## 消息框架

固定的 22 字节消息头（Pia 5.11-5.12；5.18 及更高版本带有存在标记）。
`ProtocolMessageAccessor::Header`的解串器`0x5ae870`拒绝少于`0x16`字节；写入器 `0x5aeb00` 在字节 1 处存储文字 1。

    0x00  1  message flags: 1 = destination is a bitmap, 2 = relay needed, 4 = relayed, 8 = unbundled
    0x01  1  version, always 1
    0x02  2  payload size, big-endian
    0x04  1  protocol type
    0x05  1  protocol port
    0x06  8  destination, big-endian: a constant id, or a station bitmap when flag 1 is set
    0x0E  8  source constant id, big-endian
    0x16     payload, then padding to a multiple of 4

`pokeldn/ldn/pia3.py` 通过 pia4 的标头实现它。
## 会话密钥

`LocalProtocol` 的派生 `0x5cd560` 是 BDSP 和 Sword 的：从一个 32 位值（`0x57cfc0`，围绕 `0x6C078965` 循环）播种 SEAD xorshift128，四次抽取到 16 个字节，游戏密钥下的 AES-128-ECB `LocalProtocol+0x49c`（启用标志+0x498）。
`pokeldn.ldn.pia5.ldn_session_key`。

广告的应用程序数据（Pia 5.9-5.18）以 24 字节标头打开：

    0x00  4  network id, random per session
    0x04  4  CRC32 of the user password
    0x08  1  system communication version, 4 for 5.11-5.17
    0x09  1  header size, 0x18
    0x0A  2  padding
    0x0C  4  session param
    0x10  8  zero
    0x18     the game's application data
 种子是 +0x0C 处的会话参数。来自 Let's Go 皮卡丘主机的 392 个数据报中的 392 个在 `ldn_session_key(game key, session param)` 下使用 pia4 IV 进行身份验证（三个字节
`crc32(network id little-endian || host MAC)`，源 ID 字节 0，八字节标头随机数）。
## 链接代码

链接代码为NetworkInfo场景id；应用程序数据 +4 处的密码 CRC32 保持为 0，SSID 保持为 `01000000000000000000000000000000`。场景id为`1000a + 100b + 10c + 1`，在选择器中分别选择其索引（皮卡丘0、伊布1、妙蛙种子2、小火龙3、杰尼龟4、波波5、绿毛虫6、小拉达7、胖丁8、地鼠9）。

它是在运行时构建的：`0x891580` 将选择折叠到 `100a + 10b + c`，`0x978080` 计算
`10 * number + mode`，交换模式 1（模式 2 和 3 来自 `0x9765f4` 的交换机，其功能未读）。该值将 `0x349010` 和 `0x4da710` 传递给会话构造函数 `0x4db1e0`（`u16` at `+0x302`）； `0x4db6ac`放入`LdnCreateSessionSetting+0x60`中，Pia将其复制到
`NetworkConfig.intentId.sceneId` 之前的 `nn::ldn::CreateNetwork` (`0x5ce988`)。

相同的构造函数选择搜索游戏机所在的频道：`{1, 6, 11}[scene % 3]`，表
`0xf73a44`，索引为`0x4db248..0x4db254`； `pokeldn.lgpe.search_channel(code)`。

|编写一个搜索到的游戏机 |广告场景 ID |频道 |
|---|---|---|
| 皮卡丘，皮卡丘，皮卡丘 | 1 | 6 |
| 妙蛙种子, 小火龙, 杰尼龟 | 2341 | 2341 6 |
| 妙蛙种子, 小火龙, 妙蛙种子 | 2321 | 2321 11 | 11
| 伊布, 皮卡丘, 地鼠 | 1091 | 1091 11 | 11
| 皮卡丘, 皮卡丘, 妙蛙种子 | 21 | 21 1 |

仅当搜索游戏机在其自己的频道上通告该游戏机的场景ID时，该搜索游戏机才加入另一个网络。 `bin/lgpe_host.py --code NAMES` 托管在代码的通道上（`--channel auto` 扫描游戏机的网络）； Let's Go 皮卡丘和 Let's Go 伊布加入其中。 `bin/lgpe_join.py` 不发送代码，游戏主机与其进行交易。
## 本地协议，测量

会话状态在 Pia 协议 0x24、端口 0 上发出，就像在 BDSP 和 Sword 上一样：wiki 的 5.7-5.45 更新会话消息 (`pokeldn.ldn.local_protocol.parse_update_session`)。 12字节本地头（版本1，类型0x11），序列id，本地网络id，主机变量id，服务变量id和常量id，允许参与字节，八个节点（IPv4地址，端口，迁移排名）：主机`169.254.105.1`排名0，加入方`169.254.105.2`排名1、其余255。

主体携带主机常量 id 小端 (`000048f120229beb`,
`station_protocol.ldn_constant_id` 通过 MAC `48:f1:eb:20:9b:22`)； Pia 消息头将其大端字节序作为源 (`eb9b2220f1480000`)，与 Sword 上一样。
## 站协议，用于网状连接

协议 0x14 上的连接请求，然后 0x18 上的网状连接。连接请求处理程序
`0x5b8800`读取wiki的5.10-5.18布局，station-protocol版本9：

    [0]     message type            1
    [1]     connection id
    [2]     version number          must be 9 (`cmp w8, #9` at 0x5b8848; 5.27-5.45 checks a platform)
    [3]     is inverse connection request; rejected above 1
    [4]     target constant id      big-endian u64, compared against the console's own at 0x5b6830
    [0xC]   target variable id      big-endian u32, checked only when [3] is 1 (0x5b6840)
    [0x10]  inverse connection id   compared against the station's own record at +0xA0
    [0x11]  station location        the 5.11-5.45 layout, unchanged from Sword
    [...]   ack id                  u32, the message size minus four
 Sword 的版本 4 请求（平台字节位于 [2]，移位标志位于 [3]）和 5.29-5.45 布局（协议列表位于 [1]）将每个字段放置在错误的位置。目标常量 id 是游戏机自己的，来自其 MAC；方加入的位置携带其常量ID、变量ID和服务变量ID。

零售 Let's Go 皮卡丘运行完整的版本 9 序列，其中反向连接请求已在 5.27 中删除：

    ->  connection request (type 1, is_inverse 0, target the host constant id, own location)
    <-  type-5 ack; inverse connection request (type 1, is_inverse 1) to the joiner's constant and
        variable ids, with the host's location and a trailing ack id
    ->  type-5 ack; connection response (type 2, result 0, host constant id at [5], variable id at
        [0xD], gate byte 1 at [0x37], padded to 0x38)
    <-  connection response (type 2, result 0, 840 bytes, platform 4, the joiner's ids, a network
        id, one player info), repeated until acknowledged
    ->  type-5 ack
 连接响应解析器 `0x5b9270` 读取 `[1]` 结果，`[5]` 是一个大端 u64 和
`[0xD]` 是针对其自己的 ID 的大端 u32，而 `[0x37]` 是门字节，当 5 或更多时，结果 0 路径会下降。
### 站发送的连接响应

0x348 字节（解析器接受 0x3C）：

    0x00  1  message type 2
    0x01  1  result
    0x02  1  version 9
    0x03  1  platform 4
    0x05  8  the receiver's constant id, big-endian
    0x0D  4  the receiver's variable id, big-endian
    0x31  4  the network id, big-endian: the advertise data's first u32, read little-endian
    0x35  2  01 01
    0x37  0xC3  a PlayerInfo: the station name "username", then the Switch profile's nickname,
             then the language. Its first byte is the gate the parser drops when 5 or more
    0x344 4  the ack id
 PlayerInfo是`station_protocol.player_info`构建的195字节结构；实机用其配置文件名称填充它。 `station9.build_connection_response(..., network_id=N,
player_name=B)`; `bin/lgpe_join.py --player-name NAME`（`--short-response` 发送 0x3C 字节）。

连接请求中的方加入站位置为 36 个字节：一个空公共地址（零端口）和零 NAT 标志和位置，`station_location(..., public=False, nat_flags=0,
nat_location=0)`。
## 加入网格

0x18（`mesh_protocol.build_join_request`，类型 1，本地站索引 253，尾随 ack id）上的网格加入请求绘制加入响应：类型 2，148 字节，两个站，主机索引 0，加入索引 1，一个片段，两个位置的两个站信息，最大活动 2，最大总数 8。然后主机广播更新网格（类型0x20，524字节，更新计数器1)。加入响应由 0x14 (`mesh_protocol.ack_for`) 上的 type-5 ack 确认；方加入是站索引 1。

然后，主机传输本地协议更新会话 (0x24，用 0x21 确认)、RTT (0x58)、同步时钟 (0x1C) 和克隆 (0x73)。方加入会应答每个请求，并从就座那一刻起发送自己的 RTT 和同步时钟请求。
## RTT 协议 (0x58)，版本 3

16 个字节：[0] 处的大端 u32（Sword 上的一个字节），发送者的 19.2 MHz 系统在 [8] 处标记为 u64。响应复制类型 1 的刻度。每个站大约每秒请求一次。

    00000000 00000000 0000000049845557     request
    00000001 00000000 0000000049845557     the answer to it

`rtt_protocol.build_v3` 和 `response_for_v3`； `bin/lgpe_join.py --connect` 双向运行（`--no-rtt` 将其关闭）。
## 同步时钟协议（0x1C）

主机控制的单调网状时钟（维基同步时钟协议）。站点每两秒请求一次，并将往返行程的一半添加到主机回复的值中。

    request, 16 bytes   [0] u64 the sender's system tick (19.2 MHz), [8] u64 zero
    reply,   16 bytes   [0] u64 the tick copied back, [8] u64 the mesh clock in milliseconds
 加入方在网格加入响应之后立即发送其第一个请求。克隆协议时钟就是这个时钟；一个主机在加入方自己的正常运行时间内给出克隆消息，释放克隆并离开。 `pokeldn.ldn.sync_clock`; `bin/lgpe_join.py --connect` 运行它（`--no-sync-clock` 停止）。

Keep-alive是协议0x08，无正文，以实物形式回答。
## 可靠协议（0x7C），其中游戏数据为

Pia 5.11的头部为24字节（5.29-5.43中为9或13）；两个站上的 32 位序列 ID 均从 0xFFFFF82F 开始。

    0x00  1  flags
    0x01  1  stream id, 3 for the game's stream and 0 on an acknowledgement
    0x02  2  payload size, big-endian
    0x04  4  zero
    0x08  4  sequence id, big-endian
    0x0C  4  the next sequence id expected from the peer, big-endian
    0x10  8  zero
    0x18     the payload
 确认是单独的标头、流和大小为零。 `pokeldn.ldn.reliable3`。轮椅是游戏的框架（下面的“可靠协议上的游戏消息”）。
## 克隆协议 (0x73)

`nn::pia::clone::CloneProtocol`（GetProtocolId `0x158aab8`；SDK 字符串 `PiaCommon-5_11_4`）携带合作伙伴同步。类型字节`0xAB`：高半字节结构，低半字节的一种变体。每条消息都以版本 3、类型和发送者的帧计数器作为大端 u16 开头（从发送者的 Pia 会话开始每秒大约 60 个）。在 Ryujinx 下通过 ldn_mitm 的两个 Let's Go 皮卡丘 1.0.2 端点之间进行测量；双方运行相同的状态机。
### 时钟同步，前两秒

双方每秒大约发送 5 次时钟请求（类型 0x11，18 字节，串行器 `0x51f9b0`），并通过回复回答对方的请求（类型 0x21，22 字节，`0x51fab0`）。

    clock request                              clock reply
    [0]   1  version 3                         [0]   1  version 3
    [1]   1  type 0x11                         [1]   1  type 0x21
    [2]   2  sender frame counter              [2]   2  sender frame counter
    [4]   4  sender message count              [4]   4  sender message count
    [8]   2  destination station bitmap       [8]   2  destination station bitmap
    [0xA] 8  sender system tick                [0xA] 4  sender clone clock, ms
                                               [0xE] 8  the request's system tick, echoed

- 消息计数是每个发送者在其时钟请求、回复和参与中的一个计数器，从 1 开始。
- 位图是目的地，`1 << station index`：主机（0）发送0x0002，加入方（1）0x0001。回复将发送给请求者。
- 刻度为发送者的`os::GetSystemTick`，19.2 MHz；回复只会回应请求的勾选，除此之外没有任何其他内容。
- 克隆时钟是自发送者的克隆协议启动（元素 +0x14）以来的毫秒数，大约在第一个请求之前 60 毫秒。时钟为零的回复留下实机请求。
### 参加

在十个应答请求后，加入方发送一个参与（类型 0x31，10 字节，序列化器
`0x51fbd0`)：标头、消息计数、位图 0x0003。主机用 0x33、位图 0x0002 进行应答，然后发送自己的参与，加入方用 0x33、0x0001 进行确认。从第一次参与开始，时钟回复的类型为 0x22。
### 克隆元素

克隆由克隆类型（1 到 4）、所属站（如果没有则为 0xFD）和 32 位克隆 ID 来键入。两个电台都发布自己的副本。在第一个交换中，随着交换屏幕的推进，主机创建 ids 1、2、3；每一次后来的交换都会宣布更多。双方都参与后，克隆类型 3 id 0 就存在。

    every command message   [0] version 3, [1] type, [2] u16 the sender's frame counter,
                            [4] u8 clone type, [5] u8 owning station, [6] u16 0,
                            [8] u32 clone id
    types 0x81 to 0xc4      [0xC] u32 the sender's message count, [0x10] u16 destination bitmap,
                            then the structure's own fields
    types 0xd1 to 0xf4      [0xC] the data, with no message count and no bitmap
 低半字节是命令标记加一：1 宣告（`SendClone::AnnounceCommandToken`，
`0x522480`)、2个请求(`ReceiveClone::RequestCommandToken`、`0x520df0`)、3个结束(`SendClone::EndCommandToken`、`0x522490`)、4个锁定(`AtomicSharingClone::LockCommandToken`、
`0x517820`）。高半字节是结构体； `0x51c110` 通过表 `0xf769c4` 进行调度：

|类型 |补充 |消息，长度 |接收案例 |
|---|---|---|---|
| 0x8N | 0x8N什么都没有| 0x12 | `0x51c614` |
| 0x9N | 0x9N [0x12] 处的 u32 时钟（以毫秒为单位）|时钟克隆命令消息，0x16 | `0x51c62c` |
| 0xaN |时钟，[0x16] 处的 u8 计数，一个 u8 和一个 u16 |时钟和计数，0x1a | `0x51c64c` |
| 0xbN | 0xbN时钟，u32 参与者位图，位于 [0x16] |时钟和参与者，0x1a | `0x51c66c` (`0x51c680`) |
| 0xcN |时钟、计数、位图 [0x1A] |时钟和计数和参与者，0x1e | `0x51c68c` |
| 0xeN |位于 [0xD] 的 zlib 流克隆的状态，确认 | |
| 0xfN | 0xfN [0xD] 处的一个字节，[0xE] 处的 zlib 流 |克隆的状态及其数据 | |

zlib 流膨胀为一条记录：标签 0x20、其长度、u16 克隆 ID，副本为空时为 1，满后为 3：

    0x20 0x06 u16 clone id  0x01  0x00
                                          a copy with nothing in it yet
    0x20 len  u16 clone id  0x03  u8 the station the data belongs to  u16 0
              u16 participant bitmap  u32 clock  then the clone's data
    0x20 0x0A u16 clone id  0x05  u8 the station being acknowledged   u32 clock
 A站先发布六字节表格，后填写填充表格；六字节形式是正在重试的发布，并且已确定的会话不会构建任何记录。 deflate 是一次压缩、一次同步刷新和 2 至 5 级的最终空块； `clone.pack_record` 再现每个捕获的流。 [0xC]处的0xfN头字节携带记录的参与者位图，0xeN头是它所确认的站。

|交流|留言 |
|---|---|
|业主宣布| 0xa1和0xb1与参与者位图；数据之前的其他答案 0xa2 和 0xc1 |
|接管|另一个答案是 0xa1 与 0x91 |
|数据|所有者的0xf3；另一个具有相同时钟的0xe3 |
|发布 | 0x83; 0x84 承认 |
|离开克隆会话 | 0x32; 0x41（14字节，应答者位图位于[0xA]）；无人应答的 0x32 会重复，直到游戏放弃 |

0xa2 携带网格时钟和计数，克隆类型 4 为 1，克隆类型 2 为 0。

`ClockAndCountCloneCommandMessage`（虚表`0x158ac58`，序列化器`0x51f4c0`）写入，大端，
`+0x1c`（时钟）位于[0x12]，`+0x20`（计数）位于[0x16]，`+0x21`位于[0x17]，`+0x22`（u16）位于[0x18]。计数是克隆的 vfunc 16：对于 SendClone (`0x519290`) 为 0，对于 ReceiveClone (`0x520de0`) 为 `+0x112`，对于 AtomicSharingClone (`0x517800`) 为 `+0x188`。字节 `0x17..0x19` 是堆栈残留，没有接收器读取：构建器（`0x51b3b0`、`0x51cb64`、`0x51ccf0`、`0x51cd8c`）不存储超过计数的任何内容，并且清除器 `0x51b380` 重用其 0xbN 路径的缓冲区在那里留下一个参与者词（`0x51b7a0`），因此 `01 2808ab`。 `0x51c110` 就地解析；每个陷阱都从接收循环 `0x51ad90` 或环回（`0x51e330`、`0x51e4c4`）到达它。

`0x51c110` 读取公共头（`0x51c2c0`：`[8]`、`[4]`、`[5]`），对于 0x80..0xc0 字节组
0x10-0x11（`0x51ce80`，表`0xf76e08` -> `0x51ced0`），那么上面表中的字段就不再赘述了。克隆类型表 `0xf769e4`（索引 `[4] - 1`）将 0xa1 和 0xa2 路由到采用克隆、站和时钟的处理程序，而不是缓冲区：

|克隆类型| 0xa1 | 0xa2 |
|---|---|---|
| 1 | `0x51c714` -> `0x51cb38`, `0x522350(clone, station, clock)`;未知克隆画出 0x91 |被忽略 |
| 2 |忽略（`0x51c3b8`）| `0x51cafc`、`[5]` 必须是本地站、`0x520ce0(clone, clock)` |
| 3 | `0x51c934` -> `0x51cc00`, `0x522a60` | `0x51c838`，`0x522b20(clone, station, clock)` |
| 4 | `0x51c8c0` -> `0x51cbc4`, `0x522a60` | `0x51c838` |

携带缓冲区的前向调用（`0x51c268`、`0x51c2fc`、`0x51c32c`、`0x51c784`、`mov x3,x22;
b 0x51d450`）服务于其他消息类型。

`0x522a60`，克隆类型 3 和 4 的 0xa1 处理程序，当元素状态时返回 1
当 `[[x0+0x30]+0xc0]` 中设置了发送者位时，`[x0+0x38]` 不是 1、2，否则记录电台并返回 0。主叫方使用 `0xfd04` 类型的 0xa2 应答 0（克隆类型 3 上为 `0xfd03`，
`0x51cd00`)，1 个带有 0x91 (`0x51cbe4`)，2 个什么都没有。未知克隆的 0xa1 绘制
直接0x91（`0x51c494`）。 `0x51c110` 在目的地检查 `0x51ce80` 处静默丢弃，每个发送者计数过滤器（`0x51c1e0`：`proto+0x714+4*station` 处的计数至少是消息的
`[0xC]`），以及长度和类型范围检查。

掩码 `+0xc0` 属于克隆协议对象，除了其站掩码 `+0x38` 和状态字 `+0x40` 之外：

|活动 |对`+0xc0`的影响|地址 |
|---|---|---|
|状态变为`0x22`（当`[[proto+0x48]+0x24]`为2至4时）|设置为 `+0x38` | `0x51b060..0x51b06c` |
|状态变为`0x42` |设置为 `+0x38` | `0x51b140..0x51b150` |
| | 站点以 `0x22` 或 `0x31` 状态加入 |其位已设置 | `0x51bc64..0x51bc88` |
|状态为 `0x31` 或 `0x22` 的 10 字节 0x33 |发送者位已清除| `0x51c354..0x51c3b4` |
| 14 字节 0x41，其中 `[0xa..0xd]` 等于 `[proto+0x3c]`，状态为 `0x42` |发送者位已清除| `0x51c380..0x51c3b4` |
|车站开出|其位已清除 | `0x51bce0..0x51bce8` |
|车站离开状态为 `0x42` |设置为 `+0x38` | `0x51bd04..0x51bd18` |
|其他路径 |归零| `0x519a1c`、`0x519ccc`、`0x51a2d4`、`0x51a7d0`、`0x51a9c0` |

在状态 `0x22` 中，协议等待掩码为空，然后再移至 `0x31` (`0x51b074..0x51b084`)。
### 克隆0对

克隆类型 3 上克隆 0 的所有者用 0xa1 和 0xb1 来宣布它；对方站回答0xa2和0xc1，然后所有者才发布。没有应答的实机主机（`bin/lgpe_join.py` 上的 `--withhold-clone0-answer`，仅测试）在第一个 0xa1 后 114 毫秒再次发送 0xb1 和 0xa1，并在此后 108 毫秒单独发送 0xb1，并且重复得到答案。发送该对一次并丢失答案的主机将游戏机留在“vous allez bientôt être connecté”上，没有任何过去的时钟流量。 `bin/lgpe_host.py` 每 110 ms 重复一次该对，最多 20 次，直到游戏机的 0xa2、0xc1 或 0x91 到达。已回答第一对的实机（启动器上的 `--ignore-clone0-answer` 忽略它，仅测试）回答重复
0xa2。
### 可靠协议上的游戏消息

`0x7c` 上的每条消息都是 16 字节的标头和正文：

```
+0x00  4  kind: the channel id, 1 to 4 in one trade
+0x04  4  body length: 0x168 for kind 1, 0xe8 for kinds 2 and 4, 4 for kind 3
+0x08  4  step, counting every message a station sends from 1
+0x0c  1  tag, 0 on every trade message
+0x0d  1  destination station index, 0xff for every station
+0x0e  2  zero
+0x10     the body
```

`0x116f30(mgr, kind, buf, len, tag, dest)` 在 `mgr+0x288` 处构建标头，步骤 `mgr+0x274` 加一。 交换发送者通过 `0x4d94e0`（标签 0，目的地 0xff）：`0x34945c`（种类 1）、`0x34a24c`（提议）、`0x838300` 和 `0x83838c`（提交）。 `0x4d9520` 从调用者那里获取两者；它的调用者是 `0x9dce94..0x9dede8` 中战斗场景的发送者，其标签为 3。

接收 `0x1171d0` 从任何站获取第一个排队的消息，其步骤是其站的下一个（`mgr+0x278[station] + 1`、`0x117334..0x117354`），对接收或丢弃的每条消息进行计数。它丢弃（`0x11722c`）一条既不发往0xff也不发往本地站索引的消息
`mgr+0x1288`（会话前的 0xfd），或未注册通道的类型（16 条目表）
`mgr+0x110`、`0x117398..0x1173f8`）。另一种已注册类型或标签的消息将保持排队状态，并阻止其后面来自任何站的所有消息。 交换接收方 (`0x4d9570`) 请求标签 0 (`0x11746c..0x117478`)。

该类型是一个通道 ID，由 `0x116e80` 从每会话计数器 `mgr+0x270` 从 1 分发（仅在会话开始时使用步计数器归零，`0x116a10`）并存储在 `chan+0x60` 中
`0x4d9450`;注册了 16 个通道 (`mgr+0x118 > 0xf`)，id 为 0。`0x117920` 压缩实时计数 `+0x54` 为零的通道。 `0x4d9450`的五个调用者：交换会话对象（`0x3492f8`）、队伍提议对象（`0x349d88`）、同步保存的状态2（`0x8382a8`）、
`0x347e10`类（`0x3481fc`），战斗场景（`0x9dce1c`）。交换将 1、2、3 注册到前三个，将 4 注册到交换后保存重新创建的队伍要约对象中。每个注册还会声明一个克隆集（`0x4d94b8`，将 `0x11b4c0` 转换为 `0x11aec0`），因此克隆 ID 与频道 ID 不同。

种类 1，主体 0x168，身份：保存的 MyStatus 块复制到 `obj+0x450` (`0x3493f4`)，由两个站在任何一个接收到任何内容之前从状态 6 发送。主体偏移处的 UTF-16LE 名称：

```
+0x34  2  0x0002
+0x38 26  trainer name, up to the Pokemon name; --trainer-name on both launchers
+0x52 16  Pokemon name
```

`pokeldn.lgpe.reference` 运送了一个，记录自模拟保存，其训练家是 `POKELDN`。
`bin/lgpe_join.py` 默认发送，训练家 ID 对替换为 `--our-trainer`。

类2，正文0xe8，提议，在该站发布的状态字达到2的瞬间进行，并在每次其玩家改变提议的宝可梦时再次进行下一步（选择浏览框）。回答了新的一步；重复的步骤是重传，但不是。

发送者是队伍提议对象（构造函数`0x349bf0`, 0x278字节，在`mgr+0x68`）。它的更新`0x34a210`将结构发送到`+0xa0`每当`+0x270`已设置并且`+0x272`清除，然后清除`+0x270`. `0x34a3d0`，由交换 UI 在选择更改时调用（`0x8f0c04`, `0x8f0c38`,
`0x8f8fb0`, `0x90b87c`, `0x90b8c0`），将一个宝可梦打包成`+0xa0` (`0x7294e0`) 和集合`+0x270`当状态允许时（A 0：除 1 或 2 之外的本地状态；A 1：本地状态 3 或以上 4；A 2：从不；A 3：伙伴离开，`0x3490c0`). `0x344620`提交后销毁对象（`0x886c70`）以及当链接结束时（`0x8869f0`）；交换后的正常保存会重新创建它（`0x8375a4`）在新的频道 ID 上。

种类3，主体4，提交，同步保存发送的u32（下面的“提交和交换锁”）：每个站发送一个1，一个在对等方的1之后发送一个2。发送2的站在获取对等方的1后发送它（状态5，`0x838310`）；在状态 6 提交中收到的 2，任何其他主体都会被忽略 (`0x83839c`)，因此也可以容忍用 2 回答 2 的加入方。提交后，工作站会显示一个没有按钮提示的旋转器。不完整的交换会留下交换锁。

类4，主体0xe8，乘队列提供对象的通道，正常保存在其`SaveThread`（`0x8377ec`，`0x8375a4`）后3000毫秒重新创建，交换演示后，并携带下一个交换的选择：第一站的第一个时隙（字节相同）到其第 2 步提议），然后每个选择一个。类型 4 熄灭前保存一次交换； kind 4 打开下一个交换。

交换 r，从 0 开始计数，在种类 2 + 2r 上提供，在 3 + 2r 上提交，并在 4 + 2r 上结束，交换 r + 1 的提供通道（`0x116e80` 从每个会话计数器分发 id；调度程序在每次交换时重新注册两个通道）。在连续两次测量的交易中，交换 r 的队伍对是克隆 2 + 3r 和 3 + 3r 及其提交克隆 4 + 3r；双方在一次交换保存后宣布属于下一次交换。主持，`bin/lgpe_host.py
--next-offer` 用下一条记录回答游戏机在以后每次交换中的选择。加入时，游戏机主机的第一个类型 4 是它的第一个槽：`bin/lgpe_join.py` 回答它，并且随后的每个选择与其下一个 `--offer` 回答类型 5 上的提交，并以类型 6 作为交换的结束；在最后一条记录之后，它什么也没回答。

游戏机主机将随后的每个交换作为第一个运行：在其第一个类型 4 之前宣布的下一个队伍对，每个选择的类型 4 步骤，在其确认时提交克隆，在类型 5 上提交，以及在类型 6 之前宣布的下一对。`bin/lgpe_host.py --lead` 扮演游戏主机的角色，自动提供和投票，为 `bin/lgpe_join.py`； `tests/test_esp32.py` 在两者之间各交换两条记录。

一次完整的交换，两个站都数着自己的步数：

```
step 1  kind 1   identity
step 2  kind 2   the offer, again under a fresh step per selection
step 5  kind 3   commit, body 1
step 6  kind 3   commit, body 2
step 7  kind 4   the first slot, again under a fresh step per selection
```
 类型 2 和 4 的主体是 232 字节的盒子结构：第 6 代加密下的第 7 代布局，加密常量在 +0x00，零健全字在 +0x04，校验和在 +0x06，四个 56 字节块+0x08 由 `((ec >> 13) & 0x1F) % 24` 排列并与以常量作为种子的 16 位 LCRNG 流进行异或。 `pokeldn.lgpe.pb7` 逐字节往返捕获的提议。

状态字是 `f3` 状态数据的字节 12，并且在站拥有的每个克隆上行走 0、1、2。发布 2 并发送其种类 2 的站等待对等点的种类 2。
### 是什么控制了游戏自己的第一条消息

链路交换对象的每帧状态机是 `0x349200`（+0x68 上的跳转表 `0xf4e994`）。状态 6 在没有网络输入的情况下发送第一条游戏消息：两个站在收到任何消息之前间隔 18 毫秒发送该消息。唯一的门是状态 4，`0x11b080`，询问 Pia 通道是否准备好：

- 对象 +0x90 处的 SendClone 报告就绪 (`0x5221b0`)：其元素的参与站 `element+0x3C` 必须全部位于克隆的确认集 `clone+0xA8` 中；
- +0x1258 上的共享克隆以同样的方式报告已准备就绪 (`0x522610`)；
- +0x250 处的每个站条目，每个 0x118 字节一个，其第一个字为 1，+0xD8 处有一个非零字节；
- +0x1430 处的字节（站索引）不是 0xFD（“无”；每个此类路径都返回 0）。

SendClone 的检查是`(element+0x3C & ~clone+0xA8) == 0`，共享克隆的`((clone+0x114 | ~clone+0xA8) & element+0x3C) == 0`;两者共享一个元素。在工作会话中，确认集已填充，`+0x114`排水沟和每个`+0xD8`变为1，而参与集从一开始就已满。站位到达`clone+0xA8`仅通过一个0xa2在来自该站的克隆类型 2 上（`0x51c52c`的跳转表`0xf76c38`进入`0x522350`).

状态 7 将每个到达的第一条消息存储在 `this + node * 0x1C8 + 0xC0` 处，并将它们计数为
`this+0x470`;它自己会循环回来，因此沉默的伙伴将计数保留为一。
### 在其交换屏幕上托管实机

加入托管会话的游戏机在加入方层之上需要什么：

- 本地协议主体携带主机的常量 ID 小端。游戏通过站表（`0x1171b0` -> `0x5bbe70` -> `0x5b6130`）解析发送者，而 `0x117334` 处的接收跳过未解析的发送者（节点 0xFD）：使用 id big-endian 游戏机在状态 7 等待，它的屏幕显示它将很快连接。
- 当会话发生变化时，更新会话就会消失，并再次在其后面，而不是在计时器上。   它的节点列表保留一个节点，直到对等方加入网格为止。
- 电台在参与时停止其克隆时钟请求。
- 主机在发布克隆 0 的帧中发布克隆 1；游戏机在数十毫秒后宣布自己的消息（实测为 31 毫秒），等待的主机会输掉比赛并进行角色交换。
- 应答对等方拥有主机的克隆的公告的 `0xa2` 携带来自 `0x81` 后面的 `0xa1` 的时钟，因此它是在解析整个数据报之后构建的。它承载着主机的时钟，让游戏机每半秒重新宣布一次，并且从不发布其副本。
- 两个电台都会用自己的副本回复每个克隆类型 2 发布的内容，整个会话大约每秒 10 次。
- 提议在其执行的步骤下得到答复；在新的步骤下回答会开启新一轮，各站相互回答，永无止境。
### 两个克隆人记录一次交换行走

交换对象在自己的克隆上发布其状态并读取对等体的状态。克隆类型 2 副本的 20 字节数据为 5 个字，由 `0x11bc00` 及其同级写入：

```
+0x00  4  the state: 1 a vote (0x11bc00), 2 a vote withdrawn (0x11b4e0), 4 a forced leave (0x11bcf0)
+0x04  4  that call's argument, 1 on selection and 2 on confirmation
+0x08  4  a counter, incremented on each call
+0x0c  4  the station's own step, the number of game messages it has sent
+0x10  4  the trailing word
```
 克隆类型4副本的32字节数据是会话主机（权限）视图：

```
+0x00  4  A, the agreed argument
+0x04  4  B
+0x08 16  one counter per station index (host 0, joiner 1): the counter of the vote it last saw withdrawn
+0x18  4  the station's step
+0x1c  4  the trailing word
```
 权限 `0x11b6c0` 在会话主机上运行每个刻度。仅当每个站都在当前尾随字上发布带有参数 X 的状态 1 时，才会将 A 移动到 X，同时发布 A 和尾随字加一；状态4立即移动A。对于状态 2 中的站，其参数与 A 不同，它将该站的计数器写入其槽中，将尾随字移动 1，保留 A 和 B，并在新的尾随字下重新发布其自己的类型 2。

交换屏的状态来自A及其自身记录的状态通过`0x34a300`（跳转表
A) 上的 `0xf4e9b0`； `+0x271` 设置为 `+0x272` 清除首先给出 1。

|一个 |本地状态 0 | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|
| 0（表`0xf4e9d0`）| 0 | 1 | 1 | 0 | 0 |
| 1（表`0xf4e9f0`）| 2 | 3 | 3 | 0 | 2 |

无论当地状态如何，A 2 都会给出 4，而 A 3 会给出 5，合作伙伴会离开 (`0x3490c0`)。

类似的状态函数`0x3488b0`（表`0xf4e920..0xf4e980`，循环`0x9c3300`）属于类`0x347e10`（0x718字节位于`mgr+0x70`，由`0x344690`创建）， `0x886530` 在模式 1 和 2 下创建。

交换 UI 的更新（`0x756a20`，子状态 `[ui+0xa8]`）适用于队伍要约对象（`0x7568ec`）。确认票 2 (`0x756e34` -> `0x34a4e0` -> `0x11bc00`)，子状态 2 (`0x757058`)。状态4在`[[x21+0x78]+0x60]`写入5，调用`0x74a590(ui, 2)`并继续（`0x756c0c..0x756c38`）；状态2返回选择（`0x756cb4`）；状态 1 或 3 下的菜单结果 3 撤回投票（`0x756d94` -> `0x34a500` -> `0x11b4e0`，状态 2）。在子状态0、状态1用`[x22+0x258]`零调用`0x34a4a0`(`0x756b94`)，对方退出。

`0x11b688` 在 `+0x1638` 上演到达的克隆类型 4 记录； `0x11ba20` 与 `+0x1638` 进行比较
`obj+0x04`、`+0x163c` 和 `obj+0x10`，以及 `+0x1640` 和 `obj+0x0c` 中每个节点一个字。在那里发布 32 个零的主机使游戏机处于“communication en coours”状态，除了 Retour 之外的每个按钮都变成灰色。

所提供的队伍克隆先走 `1 1 1`，尾随字 1，然后走 `x 2 2`，尾随字 2。提交克隆（队伍克隆上方的一个 id）取前两个，然后取零。主机的框架，零售和模拟都一样，将类型 2 数据克隆为五个单词：

```
+0 ms     type 4 data, 32 zeros, with the announcement
          the peer publishes 1 1 1 step 0 once its player has confirmed
          1 1 1 step 0                 the host's own confirmation
+30 ms    1 1 1 step 1                 type 4 data 1, zeros, step, 1
+8 ms     the peer answers 0 1 1 step 1
+27 ms    0 1 1 step+1 1               the offered clone goes 0 2 2 step+1 2 in the same frame,
                                       and the kind 3 carrying 1 goes under that step
+3 ms     the peer's kind 3 carrying 1, its copies under its own next step
+63 ms    kind 3 carrying 2 under the next step, every copy republished under it
after the trade demo and the normal save (3000 ms past SaveThread, 0x8377ec):
          two more clones announced, 32 zeros on type 4; the peer publishes 0 0 0 on each
then      kind 4 under the next step, every copy republished under it
```
 仅当类型 4 副本的第一个字为 1 时，对端才应答尾随字 1；在对等方的 `1 1 1` 落地之前构建，它携带 0，游戏机等待。将提交克隆移至 `1 2 2` 会绘制 `0 1 1`、尾随单词 2、无种类 3，并且游戏机位于其确认屏幕上。

游戏机主机首先宣布每个克隆：克隆 1，其第一个插槽之前的队伍对 2 和 3，其 A 2 之后的提交克隆 4（状态 1 的随机延迟，`0x8380d8`），以及保存后的下一对 5 和 6，然后是其第一种 4。它也首先投票：克隆 3 上的 `1 1 1`，带有尾随字的 A 1 1、`1 2 2`，A 2，尾随字2；在提交克隆 `0 0 0`、`1 1 1` 上，A 1 带有尾随字 1，然后 `0 1 1` 带有类型 3 携带 1，在宣布后 152 毫秒。加入方接管每个克隆并在其自己的状态字下重新发布主机的前三个字和尾随字，从而完成交换。

当确认按钮变灰时再次按 A，按钮将撤回投票：`1 2 2` 之后的 `2 2 3`（状态 2，参数 2，计数器 3）。回答 A 2 给出状态 4：游戏机启动同步保存，这会在提交交换之前提交交换锁 (600)。一个游戏机如此回答，重新发布 `0 2 3`，并在 5.0 秒后宣布其提交克隆，并对此保持沉默；交换永远不会完成，因此锁定保持设置状态，链接菜单拒绝下一次交换（`0x976634`）。正确答案是输入 4 `1 0 0 3 0 0 step T+1`，将该记录设为 `0x11ba20` 下的状态 0；状态 0 的 1 是状态 2 (`0xf4e9f0[0]`)，回到选择。 A 0下撤回的选择`2 1 4`取`0 0 0 4 0 0 step T+1`。
`bin/lgpe_host.py` 回答如此并同意一次发布的下一次投票；
`tests/test_lgpe_host_withdraw.py` 通过游戏代码运行两者。

两个零售控制台之间的交换在任一方向上都不携带有关克隆类型 4 和 1 的克隆数据；如果主机没有发布，则其搜索屏幕上会留下一个缺少门 `0x11b080` 的加入游戏机。
### 交换动画

游戏机在执行 `0e` 步后播放交换动画，并且在此期间不发送交换发票。以零售Let's Go托管`bin/lgpe_join.py`为例，从该步骤开始：动画在约1.7秒开始，接收到的宝可梦在约15.3秒出现（手按，最多晚2秒），游戏机的4型消防（248字节）在27.0秒到达，玩家在约28.8秒获得控制。
### 提交和交换锁

交换锁是保存的 MyStatus 块中的 u32 倒计时（以秒为单位）。交换的保存将其设置为 600 并在提交交换之前提交；交换完成后将其恢复为 0。

MyStatus块对象是`[[[0x15fad08]]+0x98]+0x58` -> `+0x78`，数据`obj+0x58`，0x168字节（`0x1c9ff0`，`0x1ca000`，vtable的插槽5和6 `0x153e0b0`），该种1体。计数器是
`obj+0xe8`、MyStatus `+0x90`（设置器 `0x1c9d40`、获取器 `0x1c9d50`）。在 `savedata.bin` 中，该块是
`0x1000..0x1168`（教练姓名为`0x1038`）和计数器`0x1090`：在中断交换后保留的保存将`58 02 00 00`保存在那里，并且块中没有其他变化。每个捕获的种类 1 在 `+0x90` 处都带有 0。

设置者调用者：同步保存600（`0x837f90`、`0x837fb0`）、收到宝可梦申请0（`0x838bec`、`0x838c0c`）、倒计时（`0x1ca54c`） `0x1ca56c`);加载保存写入块。链接菜单的检查 `0x9765f4` 打开链接模式：模式 1（交换）读取计数器（`0x976634`），并且非零，返回 -1 并拒绝 `0x0248810f825b1fee`（`0x97663c`）；零继续进行计数检查（消息 `0x0248800f825b1e3b`）。模式 3 拒绝时
`[x22+0x62] <= 1`（消息 `0x02487f0f825b1c88`）。

锁随着播放时间倒计时。 `0x1ca450(playtime, seconds)` 立即返回
`seconds > 1`（`0x1ca46c`）或`playtime+0x100`清零（`0x1ca474`）；否则它会减去
来自计数器的 `seconds`，下限为 0 (`0x1ca500`)，并将它们添加到播放时间（`+0x54` 小时 u16、`+0x56` 分钟、`+0x57` 秒，上限为 999:59:59， `0x1ca5a0`）。 `0x1ca7e0` 写入
`playtime+0x100` 为 `nn::oe::GetCurrentFocusState() != 3`（背景）。它的调用者 `0x1462a0` 每 20 个调用运行一次（计数器 `+0x70`），同时设置其启用字节 `+0x54` 并且不存在保存线程 (`0x1ce8f0`)：它将 `GetSystemTick` 减去基本刻度 (`+0x68`) 转换为整秒并将已计算秒数的增量 (`+0x60`) 传递给 `0x1ca450` (`0x146314..0x14637c`)；仅当刻度线向后移动时，底座才会移动 (`0x146384..0x1463c0`)。两秒或更多秒的跳跃会被丢弃，因此每次门控调用时钟最多增加一秒。 600 的锁定持续十分钟的计算游戏时间：在焦点状态 1 和 2 中，绝不会在后台或游戏关闭时（开始时重新读取基础，`0x14628c`）。

`0x13c944` 位于 `0x13c850`（也运行 `0x145560`、`0x13f0d0`、`0x142cd0`、`0x1427a0`），仅从 `0x13c5a0` 到达，插槽0x210 字节作业的 `+0x40`（虚表 `0x15379d8`，由 `0x13c440` 构建）
`0x13bfa0`在设置`0x13b650`，存储在`G+0x50`，完成字节`+0x204`）。来自工作循环 `0x20f30` 的执行器 `0x231a0` 在 `+0x204` 清除 (`0x23264..0x23288`) 时运行它。 `0x13bfa0` 将作业链接到 `0x1ca00` (`0x13c02c..0x13c120`) 的依赖图中；每帧提交图表的内容以及播放时间滴答运行的频率都是未知的。帧周期表`0xf7eeb8`以5个步长保存16666667到83333334 ns，由`0x39600`索引；帧循环从 33333334 ns（`0x38ba0..0x38bb8`，vtable `0x1529968`）开始，并呈现每个
`clamp(period / 16666666, 1, 5)` 垂直同步 (`0x29e80..0x29eb4`)。

`0x347190` 构建三个保存序列之一：0“正常保存”（`0x3474d0`）、1“同步保存”（`0x347670` -> `0x347ae0`、0xc8 字节）、2“致命错误” （`0x347810`）。交换使用同步保存。它的init `0x837c70`在`seq+0xb8`创建提交通道对象（`0x4d9030`），将计数器设置为600（`0x837f88`），并启动`SaveThread`（`0x1cdc80`），它在调用线程上序列化并提交一次写（`0x1cedd4..0x1cede0`，`nn::fs::CommitSaveData`）。其更新 `0x838070` 运行于
`seq+0xa8`通过跳转表`0xf867c4`：

|状态|地址 |它是做什么的 |
|---|---|---|
| 0 | `0x8380ac` |记录的网络错误（`0x4d8a70`）写入结果2并离开；否则等待`SaveThread`（`0x1cdf40`），将本站是否发送2（`0x838660`）存储在`seq+0xc0`，应用接收到的宝可梦并将内存中的计数器清零（`0x838800`），设置`netmgr+0x121` (`0x4d8b10`), 开始 `FirstSaveThread` (`0x1ce050`) |
| 1 | `0x8380d8` |等待 `FirstSaveThread` 写入 (`0x1ce310`)，然后从以 `GetSystemTick` 为种子的 MT19937-64 中提取 `2000 + r % 6000` 毫秒的延迟 |
| 2 | `0x838234` |延迟后，注册提交通道（`0x8382a8`）|
| 3 | `0x8382b4` |对提交克隆投 1 票（`0x4d9690`：`chan+0x64 = 1`、`0x11bc00`），然后等待通道的门（`0x4d94d0`）并且克隆空闲，`[chan+0x74]` 1 |
| 4 | `0x8382ec` |发送类型 3 携带 1 |
| 5 | `0x838310` |采用其他站的类型 3（跳过其环回）； 1 以外的主体是错误路径（`0x83836c`）；如果设置了 `seq+0xc0`，则发送类型 3 携带 2（失败的发送保留在 5 中，而对等方的 1 被消耗） |
| 6 | `0x83839c` |从任何站获取类型 3：2 清除 `netmgr+0x121` (`0x4d8b20`) 并发出提交信号 (`0x1ce3f0`)；任何其他机构都会被忽略|
| 7 | `0x8383e8` |等待 `FirstSaveThread` 提交 (`0x1ce410`)，结果 0 |

`FirstSaveThread` 启动时串行化（`0x1ce154`），计数器清零后，发出信号
`mgr+0x78` 一旦写入，就会等待 `mgr+0x84`，并且仅在中止字节 `mgr+0x100090` 清除 (`0x1cedf4..0x1cee18`) 时才提交。错误路径（状态2、3、5、6为`0x8383b0`；错误体为`0x838520`；状态0为`0x8380c8`）将结果2写入父节点（`[x0+0x88]+4`）；前两个调用 `0x1ce520`，它设置中止字节并等待线程结束。每条路径都以
`0x838540(seq, 0)`。第二个保存被删除，磁盘上的保存保持 600。

调度程序的状态 3 (`0x886684`) 读取结果：2 调用 `0x345b10` (`0x886690`) 并返回而不前进。 `0x345b10` 将致命错误包装器（vtable `0x154f1f8`、0xa8 字节、`+0x88 =
0`）推送到根进程堆栈（`0x13a6b0`）上；其`0x346140`构建了类型的保存过程
`[proc+0x88] != 0 ? 3 : 2`（`0x3461b8..0x3461d0`），都是致命错误序列，其init
`0x836320` 显示消息 `0x191615296121e064` 2 和 `0x977c18bf4135ff42` 3（`0x8365f0`，通过 `0x7ed60`），其更新（`0x836780`）是裸 `ret`。中止的提交在该屏幕上结束，随后不再保存，并且保存在下次启动时保留 600。

两个 id 都是 `common/message_error.dat` 的标签（`0xf22dfc` 处的字符串）、FNV-1a-64 以及基础
`0xcbf29ce484222645`，更新v131072的所有十种语言都相同：

|编号 |标签|英语 |法语 |
|---|---|---|---|
| `0x191615296121e064` | `error_fatal_save` |发生错误。你无法交换宝可梦。按HOME键结束游戏。 | Une erreur s'est produite。宝可梦的变化并没有达到预期的效果。打开 HOME 按钮并进行游戏。 |
| `0x977c18bf4135ff42` | `erro_fatal_storage`（原文如此）|无法识别 Nintendo Switch 中的保存数据。请关闭系统，然后重试。 |任天堂 Switch 游戏机的识别信息如下。 Veuillez éteindre votre votre 游戏机，la rallumer，puis réessayer。 |

该游戏有一个进程堆栈，植根于 `[G+0x68]` (`G = [0x160d310]`)。跑步者 `0x13a780` 仅更新顶部 `[root+0x78]` 到 `0x13a160`：3 在同一帧中运行新顶部，1 弹出它或交换挂起的 `[root+0x80]`。包装器永远不会返回 1（`0x346140` 将致命进程通过 `0x39c20` 交给管理器 `[G+0x60]`），因此其下面的调度程序永远不会再次更新。

链接菜单的拒绝 ID `0x02487f0f825b1c88`、`0x0248800f825b1e3b`、`0x0248810f825b1fee` 与 FNV 素数 `0x100000001b3` 成对不同：三个字符串的 FNV-1a-64 哈希值仅在最后一个字节不同（乘以素数的反模 2^64，它们结束`dd58`、`dd59`、`dd5a`）。琴弦未知；文本位于 romfs 消息档案中。

设置 `netmgr+0x121` 后，`0x4d8750` 会记录严重性为 4 的每个网络错误 (`0x4d8760..0x4d877c`)，其中指出 (`0x4d8a80`) 的 2、3、5 和 6 测试。记录的错误仅由更高严重性 (`0x4d879c`) 替换，因此在设置 `+0x121` 之前记录的高于 4 的错误无法通过测试。 `+0x121` 在状态 0（`0x8384f8` 处的 `0x4d8b10`）结束时设置，并在接收到的 2（`0x838494` 处的 `0x4d8b20`）上由状态 6 清除。没有状态有超时：安静的对等点让序列等待，直到链接失败。

录音机：`0x345790`（代码0xe）、`0x3457d0`（0x11）、`0x345810`（0xf）、`0x345860`、 `0x3458a0`，
`0x345900`（`nn::err::ErrorCode`）、`0x345940`（序列码客户端）、`0x3459f0`、`0x345a50`、
`0x345aa0`。 `mgr+0x60`（vtable `0x154f068`）处的监听器路由`0x344c30`，`0x344c60`，
`0x344c70`、`0x344c80` 至 `0x345790`、`0x344c40` 至 `0x345900`、`0x344c50` 至 `0x345860`、`0x344c90` 至`0x3457d0`。交换会话对象（vtable `0x154f608`）转发插槽 9（`0x349650`，代码 0xe）、插槽 10（`0x3497d0`）和插槽 11 至 14（`0x349880`、`0x3498e0`、 `0x349940`、`0x3499a0`；14为代码
0x11) 通过 `0x3496b0` 发送给它。

链接状态机 `0x4d9b70`（来自 `0x349520`）在其状态为 5 或更低时进入状态 6，没有操作挂起（`[x19+0x20]` null）并且泵 `0x1175d0` 返回 0（`0x4d9b98..0x4d9bc8`）；状态 6 (`0x4d9fb0`) 调用槽 9。当 `[x19+0x80]` 为空时，泵返回 0，传输的
`+0x48` 不是 5 (`0x11c560`)，或者会话的 u16 `+0x1e6` 为 1 或更少 (`0x1176b0..0x1176bc`)。仅 `0x59eab0` 写入 `+0x1e6`：每个状态 3 站记录（`0x5b5900`、`0x5a9cd0`）的字节 `+0x415` 中 `s+0x178` 中站的总和，由连接响应线字节填充`0x35` (`0x5b962c..0x5b9658`)。零售 Let's Go 向那里发送 1，因此该值是站点数。仅当 `[s+0xd8]` 在 2 到 6 之外、`[s+0xd4]` 为 2 或 4 且 `0x52abf0(s+0x38)` 为假 (`0x59eacc..0x59eaf8`) 时，才会进行重新计数。

链接机在六个偏移处调用交换会话对象（vtable `0x154f618`），每个偏移量来自
`[x19+0x10]`：

|偏移|功能|致电 |当 |
|---|---|---|---|
| `+0x30` | `0x3495e0` | `0x4da4b0` 中的 `0x4da584`（来自 `0x4d9cf0`）|状态 4 至 5 (`0x4d9cf4`) |
| `+0x38` | `0x349600` | `0x4d9f2c` |匹配成功，之前 `0x116890` |
| `+0x40` | `0x349620` |在`0x4da5e0`（来自`0x4d9e24`）|状态 9 至 10 (`0x4d9e28`) |
| `+0x48`，插槽 9 | `0x349650` | `0x4d9fb0` 中的 `0x4da084`（来自 `0x4d9bc8`）； `0x4da0e0`（来自 `0x4d9ee0`）|泵故障；与 `[job+0x300]` 清除 (`0x4d9e30`) 和零结果或位 10 至 12 而非 1 或 2 (`0x4da114..0x4da128`) 的匹配失败 |
| `+0x50`，插槽 10 | `0x3497d0` | `0x4da38c` 中的 `0x4da0e0`，来自 `0x4da294`，两个出参 |匹配失败，`[job+0x300]` 清零且结果 1 或 2 的位 10 至 12 |
| `+0x70`，插槽 14 | `0x3499a0` | `0x4d9efc` |与 `[job+0x300]` 集匹配失败 |

然后，两个失败匹配路径均设置状态 6（`0x4d9ee4`、`0x4d9f14`）。对于结果`0xa46e`（模块110，NIFM，描述82），槽10的out1是全局`0x163ce00`中对象的`+0x40`处的u32（`0x4da2a4..0x4da2c4`；当全局为空时，槽9代替，`0x4da3bc`），写于
`LoginJob::Logout` (`0x5de3ac..0x5de42c`) 来自传输的虚拟 `+0xb0`。任何其他结果都将成为 out2 中的 `nn::err::ErrorCode` 到 `0x5298a0`（对于 `0xe437` ，存储的代码来自
`0x1601e38`，否则为 `0x529940(result)` 的 N / 10000 和 N % 10000)。插槽 10 通过 `0x345860` 记录非零 out1，否则通过 `0x345900` 记录 ErrorCode；经理重复测试
`0x3443f4..0x34443c`。插槽 11 至 13 未找到呼叫者。

`0x838660` 决定谁发送 2. 其中 S = {144, 145, 146, 150, 151} （掩码中的 `species - 0x90`
`0xc7`) 且 M = {808, 809}：从 S 或 M 提供但从两者都不发送的电台；反之则不然；否则，`0x4d9720` 为真 (`[mgr+0x128c] != 0`) 的电台则为真。因此，为普通宝可梦提供急冻鸟、闪电鸟、火焰鸟、超梦、梦幻、美录坦或美录梅塔的电台会在任一角色中发送 2。

父节点区块（`[parent+0x88]`，下称“交换调度员”）保存着自己提供的宝可梦的盒子索引（`+8`）和到达的宝可梦（`+0x10`）。状态0调用`0x838660`，而盒子插槽仍然持有自己的宝可梦（`0x1c0d30`：`box + 0x3f800 + idx*8`的对象，0x3e9无，盒子
`[[[[0x15fad08]]+0x98]+0x58]+0xb0`），然后 `0x838800` 在该插槽（`0x838afc bl 0x1c0f30`）上写入 `[block+0x10]` 的副本并应用交换的副作用：

- 由`0x1cfe80`（`0x83897c`，再次在`0x838ab0`进化）在`[[[[0x15fad08]]+0x98]+0x58]+0x88`上注册图鉴； `0x1cff60` 跳过蛋和物种 0 或以上 809，否则将每个物种位设置为由 `species - 1` 索引的 `obj+0xdc`。当 `0x1760a0(species, form)` 为 true 时，表格被清零。
- 交换进化，`0x728250(pkm, partner, &species, &index)`：当持有的物品通过管理者的vfunc `+0x28`时，`0x723220`将物种保留为鸡蛋，或除64（勇敢基拉）之外的任何物种；   否则，第一个进化条目 `0x723340` 接受：方法 5 始终，当持有的项目等于参数时为 6，小嘴蜗 (616) 和盖盖虫 (588) 为 7。到达的副本作为宝可梦 (`0x838a44..0x838a4c`) 传递，因此方法 7 永远不会匹配。 `0x7282c0`适用：通过`0x7283c0`物种，方法`0x22`形式加一，方法6、19、20清除持有物品（掩码`0x180040`）。
- 当`0x115860`为真时，游戏记录477，否则476（`0x1ca840(id, 1)`，`0x838828..0x838840`）：`[[[[0x15fad08]]+0x98]+0x58]+0xc8`上`obj+0x54+4*id`的u32，上限为`0xf48368[0xf4b760[id]]`；   当设置 `obj+0x10f8` (`0x1ca8f8`) 或 id 大于 999 时，不会写入任何内容。 `0x115860` 返回字节 `0x1614076`，由 `0x1157f0` 从 `InternetConnectThread` 设置（`0xb2ea98`）并由 `0x115830` 从其出口和两个 `InternetDisconnectThread` 机构（`0xb2ebf8`、`0xb2f178`）清算：476 笔本地交易，477 笔在互联网连接建立时进行的交易。

`mgr+0x128c` 为本站是否为会话开始时的会话主机，仅由
`0x116890`（`0x59e920(session) & 1` at `0x116a48`）在链接机上从状态2到4（`0x4d9f54`）的步骤，匹配后； Pia 主机迁移不会重新运行它。当 `0x59e920` 返回 1 时
`[s+0xe0]`（本地站，创建 `0x59f864` 并加入时设置）等于 `[s+0xe8]`（会话主机，
`0x59f920` 加入）和站 `[s + 0x148 + 8*[s+0x142]]` 对其 vfunc `+0xe0` 的回答为真。
`mgr+0x1288` 也来自 `[s+0xe0]` (`0x116a3c`)。

对于同行：

- 确认子状态中的 2 给出状态 4，它启动同步保存并提交 600：发布 A 2 的权限欠整个提交交换。
- 同行的第一个类型 3 携带除 1 之外的任何内容，并在锁定设置后中止。
- 在接收者的状态 2 注册提交通道之前发送的种类 3 被丢弃；状态 3 投票保留每个电台的类型 3，直到两者都注册为止。
- 状态 1 的延迟使游戏机的类型 3 移动最多六秒（在主机 A 2 之后 5.0 秒和 9.0 秒宣布提交克隆）。
- 状态 0 结束和状态 2 之间记录的任何网络错误都会中止提交：保存保持 600 并且游戏机在致命错误屏幕上结束。
### 交换调度员

`0x886530` 运行从菜单到退出的链接，通过表格打开 `[obj+0x68]`
`0xf87bc4`：

|状态|条目 |它是做什么的 |
|---|---|---|
| 0 | `0x886578` |设置 |
| 1 | `0x88669c` |等待它的子节点；记录的网络错误 (`0x345af0`) 变为 8； mode `+0x8c` 1或2创建`0x347e10`对象（`0x886f04`）和战斗场景（`0x886f18`），然后是6；模式3等待`0x344510`的队伍要约对象报告就绪（`0x886f30`：通道和克隆集的就绪状态，`0x4d94d0 & 0x11b4d0`）|
| 2 | `0x8866f4` |复制盒子槽位`[obj+0xf8]`为`obj+0x148`作为出局宝可梦；网络错误转到 8； `[obj+0x100]` 5，交换UI继续，开始同步保存，任何其他值都变为8 |
| 3 | `0x886670` |等待它的子节点（`[obj+0x90]` 处的弱引用，在致命包装器被推送之前被销毁）；结果 2 调用 `0x345b10`，致命错误，并保持不变；否则销毁队伍要约对象（`0x886c70`），将 `[obj+0xf0]` 放在 `obj+0x150`，启动交换演示（`0x875f40`），状态 4 |
| 4 | `0x886930` |发布 `[obj+0x150]`，状态 5 |
| 5 | `0x886950` |等待它的子节点；将 `[obj+0x158]` 写入盒槽 `[obj+0xf8]` (`0x1c0f30`)，开始正常保存，状态 7 |
| 6 | `0x886ee8` |状态 8 |
| 7 | `0x886908` |等待它的子节点；结果 1 变为 8，任何其他结果变为 1 |
| 8 | `0x8869cc` |销毁队伍要约对象（`0x8869f0`）和`mgr+0x70`对象（`0x3447a0`）并离开|

通过`0x887340`开始一次保存，构建一个保存过程（`0x346670`，0x128字节）；调度程序将 `&obj+0x178` 存储到 `+0x90`（`0x8868dc`、`0x886e48`）中。它的第一次更新
`0x8345d0` 通过 `0xef9a80 = {1, 0, 2, 2}` 将保存类型映射到 `0x347190` 的序列类型，并将指针（`0x834688`）传递为 `[parent+0x88]`：

```
obj+0x178  +0x00  save type: 0 sync save, 1 normal save, 2 or 3 fatal error
obj+0x17c  +0x04  result, written by the sequence: 0 done, 2 aborted, 1 the link ends
obj+0x180  +0x08  box index of the own offered Pokemon, [obj+0xf8]
obj+0x188  +0x10  the received Pokemon, [obj+0xf0]
```
 状态 2 填充它以进行同步保存（`0x88685c..0x88689c`）；状态 5 将类型设置为 1 (`0x886e00..0x886e04`)。正常保存的更新`0x8374b0`运行`SaveThread`（`0x8377bc`），等待3000毫秒（`0x8377ec`），然后，如果交换会话对象处于状态8（`0x349090`），则创建队列提供对象（`0x8375a4`，每帧重试）并写入结果0（`0x8375b8`）；在任何其他状态下，它单独写入 0。结果 1 仅来自 `0x837860`，在 `[x20+0x258]` 上门控且队列位于
`[x20+0x250]` (`0x83776c..0x8377a0`)。交换后，调度程序从状态 7 返回到状态 1 (`0x88691c..0x88692c`)，并在新通道上提供新的队列提供对象，因此一个座位承载着一个又一个的交换。
### 战斗场景频道

`0x9dce94..0x9dede8` 中的发送者是唯一的非零标签，将其状态保存在全局块中
`0x1640eb0`，其第一个字是其通道（`0x9dce10..0x9dce1c`：`ldr x0,[0x1640eb0]; b
0x4d9450`）。 `0x9dce50`将标签1下的块`+0x78f0`（一个u16站字节，一个u16 0x6e）中的四个字节发送到0xff； `0x9dd3ec`将宝可梦（`0x721ef0`）打包到`+0x348`中，`0x9dd3fc..0x9dd40c`将其在标签3下发送。每站记录为0x1788字节（`0x9dcee8`）。

注册（`0x9d2d90`）位于战斗过程的步进设置`0x9d2c30`（跳转表
`0xf92c1c`;进程引用 `Pop_BGM_battle_to_field`、`vs_wild` 和 `btl_sky.gfbmdl`），仅在模式 1 和 2 中从调度程序状态 1 到达（`0x886f18` -> `0x95c470` -> `0x95c5c0` -> `0x28cd10` -> `0x28e630` -> `0x9cbba0`）。在模式 3 中，战斗频道永远不会注册。步骤0仅当链路会话对象`[[[0x15faec8]]+0x50]`处于状态8（`0x9dc61c..0x9dc634`）时，创建通道（`0x9dc5c0`）并将其存储在`0x1640eb0`（`0x9dc6f4`）；当 `0x1640eb0` 为空时，`0x9dce10` 不记录任何内容，并且准备状态 `0x9dce30` 在没有通道的情况下返回 1，因此狂野战斗不会记录任何内容。拆卸（`0x9d3df0` -> `0x9dcce0`）会清除指针。
### 托管交换可以节省什么

所提供的框结构在发送时保存，未选中。携带这些值的记录在Let's Go皮卡丘的摘要屏幕上读回不变：物种132，经验1,000,000（等级100），隐藏槽中的能力150，针对TID 41234和SID 12345的具有异色xor 0的PID（显示为083154，`(sid << 16 | tid) % 1000000`），自然10，无性别，每个 IV 31 个，每个 AV 200 个（100 级 HP 437，游戏最高），一招，达到等级 30，遇到地点 4（路线 2），语言 2，OT `POKELDN`。偏移量是 PKHeX 的 PB7 地图。
### A 加入方离开

使用 Retour 退出的游戏机在所提供的克隆上发布状态 4，在新计数器下发布参数 0，然后发布参数 3。主机每隔 30 毫秒回答一次，前三个单词为零，尾部单词加 1，参数作为类型 4 副本的第一个单词。然后，游戏机在克隆类型 4 上使用 0x83 释放其克隆，站 0xFD（克隆类型 3 上的克隆 0），重复（大约每 100 毫秒，测量一次），直到 0x84 应答；主机发布自己的主机（在其站下的克隆类型 2 上以及克隆类型 4 上为 0x83）。上次发布后，一旦其克隆协议空闲（[离开前的等待](#the-wait-before-leaving)），游戏机就会在网格协议的可靠端口上发送网格离开请求，在 24 字节可靠标头下：

```
04 01        leave request, station index
```
 该端口欠可靠确认，不可靠端口 `08` 和网格主机索引 (`08 00`) 欠一个两字节离开响应。仅当离开者处理程序 `0x591bf4` 的字节 [1] 是主机 getter `0x58e5d0` (`ldrb
[x0,#0xa3]`) 名称的站的索引时，才会获取响应，然后清除离开作业的标志 `+0x78`。作业（`LeaveMeshJob`，构造函数
`0x589470`) 在发送请求时设置 5000 ms 的截止时间 (`0x5895bc`)； `WaitLeaveResponse` (`0x5896c0`) 等待标志或截止时间，重新传输请求（每 40 毫秒，测量一次），然后断开其站点并离开网络。指定离开者 (`08 01`) 的响应被丢弃：游戏机在发出离开请求后 5.00 秒取消身份验证（两个控制台上的六次离开需要 4.98 到 5.01 秒，主机的断开连接请求在每个控制台中得到应答）；回答 `08 00` 两次，它在离开请求后 0.04 秒发送自己的断开连接请求，并在约 0.06 秒后取消身份验证。返回后，主机发送一字节站断开请求，类型 3；游戏机在 50 毫秒内回答类型 4。

游戏机主机用 `08 00` 两次应答加入方的离开请求，然后重复本地协议启动主机迁移（类型 0x13，每 0.3 秒测量一次）。当离开响应到达时，方加入发送的断开连接请求将主机的播放器返回到菜单（“l'autre joueur a choisi d'annuler l'échange”）；等待的方加入会使主机重复 0x13 五秒钟。
`bin/lgpe_join.py --leave-after SECONDS` 运行出口（`pokeldn.lgpe.leave`）。

一旦两个工作站在克隆上发布带有一个参数的状态 1，游戏机主机的类型 4 副本就会在 0.27 秒内将 A 移动到该状态。权限读取每个站的存储副本（`container + 0x8d8 + i*0x260`，i低于会话的站计数）。副本仅被具有严格较新时钟的记录替换（`0x52184c`）；相同的时钟确认并保留旧数据。一个加入方在该克隆上的前一个记录的时钟下（都在一个网格时钟滴答内）发送对提交克隆的投票，使得游戏机在交换屏幕上保留旧副本及其玩家。 `pokeldn.ldn.clone.Participant.record_clock` 为克隆上的每条记录提供高于最后一条记录的时钟。
当此类投票在任何类型 3 (`pokeldn.lgpe.leave.unagreed_vote`) 之前的 `--stall-leave` 秒（默认 5）内未达成一致时，`bin/lgpe_join.py` 运行退出。退出结束等待；它不会解除交换锁，该锁是同步保存在提交克隆投票之前写入的（状态 0）
`0x838070`）。
### A 主机离开

玩家退出的游戏机主机发布状态 4，参数 3，释放其克隆（0x83，由 0x84 应答），最后一次释放后，一旦其克隆协议空闲（[离开前等待](#the-wait-before-leaving)），在可靠端口上发送网格迁移开始，`44 00 01` （主机索引，下一个主机的索引）。它的等待（`0x58aeb0`）在`job+0x6e+index`处为每个连接的站保留一个标志，并在每个标志都清除或经过5000毫秒（`0x58a8f0`）时结束；迁移响应 `48 <index>` 会清除该站的标志（处理程序 `0x591e98` -> `0x58b010`），并且该站也会离开。如果没有得到答复，游戏机每 45 毫秒重传一次起始信息，持续 5.0 秒。

然后，它广播携带主机迁移状态 1 的更新会话，其节点列表不变，并重复本地协议启动主机迁移（类型0x13) 每 301 毫秒 (`0x5d40ac`）直到除了它本身之外没有任何站点连接到 LDN 网络（`0x5cc2d0`计算它们）或已经过去 10000 毫秒（`0x5d4050`），然后破坏网络：八个 LDN 断开帧，原因 3，广播超过 200 毫秒。既不回答也不回答的方加入在迁移开始后 15.0 秒内保持游戏机主机。模拟主机用 ack 应答并`48 01`发送其更新会话和第一个0x1334 毫秒后；零售主机以发送第一个相同的方式回答0x13迁移开始后 0.06 秒。`bin/lgpe_join.py`发送两个答案并在第一个答案时离开网络0x13 (`pokeldn.lgpe.leave.host_departure`).
### 出发前的等待

游戏的拆卸步骤 `0x116bc0`（链接对象更新 `0x4d9b70` 的状态 8）结束克隆会话（`0x51bee0`），然后当克隆协议状态 `& 0xf0` 为 `0x10`（空闲；由`0x5db760` 变为 `obj+0x16f4`)。否则计数为 150 次调用 (`obj+0x16fc`,
`cmp 0x95` at `0x116d38`) 在通过 `[obj+0x80]` vfunc `0x68` 调用休假之前。两种角色的计数时间均为 2.49 至 2.51 秒。

协议通过状态 `0x41` 达到空闲状态，该状态在任何克隆具有未确认的数据令牌时等待（`0x51b0f0`、`0x5180cc`），然后是 `0x42`，该状态发送克隆退出（0x32）并等待每个站的0x41。在其克隆 0 发布后（克隆类型 3 上为 0x83），游戏机大约每 100 毫秒持续发布其克隆类型 2 副本。一个对等点用自己的副本回答每个人都不会确认它们：游戏机不发送 0x32 并在完整计数后离开。一个对等点在克隆类型 1 上回答每个 0xe3，站 0xFD，携带发布者的站和时钟，为每个克隆在克隆类型 2 上获得 0x83，一个 0x32，并在游戏机最后一次发布后 0.11 和 0.29 秒发出离开请求；游戏机主机在上次发布后 0.13 秒发送其迁移开始。 `pokeldn.ldn.clone.Participant` 在对等方的克隆 0 释放后进行确认。
### 主机对不包含克隆数据的加入方有何作用

给出 0x3C 字节连接响应（无网络 id，无玩家）的游戏机主机应答克隆公告并公告其自己的公告，从不发送克隆的数据（无 0xb1），并在网格加入后几秒钟离开克隆会话（0x32）。发送完整响应的方加入会在参与后获取克隆的数据（测量 1.1 秒）。
### 过了门

一旦门通过，主机就会从状态 4 进入已确定的状态 8：状态 6 发送第一条消息（来自 `obj+0x450` 的 0x168 字节），状态 7 将其自己的环回和加入方计数到 `obj+0x470` 中，在恰好 2 处留下 8（`b.ne`）并且不再接收。然后主机屏幕上会显示已找到玩家。第一条消息的标题：

    01000000 68010000 01000000 00ff0000    kind 1, 0x168 bytes, step 1
    02000000 e8000000 02000000 00ff0000    kind 2, 0xe8 bytes, step 2
    02000000 e8000000 03000000 00ff0000    kind 2, 0xe8 bytes, step 3
 在工作会话中，类型 1 消息被确认，克隆 ID 2 和 3 被公布，然后类型 2 消息（相隔 70 毫秒、3.2 秒和 0.4 秒）。状态 8 是 `0x349200` 的终端：虽然模式字 `+0x8C` 保持为 0，但克隆 ID 2 和 3 永远不会被公布。
### 门上面的状态机

`0x349200`的状态3在`+0xB8`处分配会话子对象，通过thunk调用`0x11aec0`
`0x11b4c0`（对象`[x0+0x20]`，克隆id `[x0+0x18]`），并无条件设置状态4；状态 4 通过 `0x11b4d0` 调用门并在 true 上前进。状态 3 和 4 不从网络读取任何内容。同一后卫的三个 setter 位于连续的 vtable 槽位中，只能通过 vtable 到达：
`0x154f648` -> `0x3495e0`（状态 3，来自除 9、10、11 之外的任何状态），`0x154f650` -> `0x349600`（状态 2），`0x154f658` -> `0x349620`（状态 11，然后中止 `0x4d8b00`); `0x349650`, `0x3497d0`,
`0x349880`、`0x3498e0`、`0x349940` 跟随。

`0x11aec0`在一帧中注册并宣布一个电台的整个克隆集：第 1 类克隆`game+0x90`从`game+0x678`，4型克隆在`game+0x1258`从`game+0x13f0`，然后每个队伍成员一个（跨步0x118从`game+0x218`, 源步长0x260从`game+0x8d8`）。每个去`0x51a550`或者`0x51a510`，将播音员排入元素列表中`+0xD8`。扫地机`0x51b380`稍后将其从表中排出类型字节`0xf46acc` (0x81, 0xa1, 0x83, 0xb1）按排队对象的种类：因此`0x81`对于 2 型克隆，`0xa1`关于类型 4 和`0xa1`在一帧中的类型 1 上。

公告出现在大门前：发出该三元组的电台已通过状态 3；一个从不发出它的状态还没有达到状态 3，并且没有针对门输入的消息对其有帮助。游戏机主机仅从克隆 ID 1 的交换状态机发出三元组； ID 2 和 3 来自第二个发布者（`0x349a90`，如下）。加入时，它不发出 `0x81`，仅发出接管突发。工作站对每个克隆 ID 运行 `0x11aec0` 一次，依次为 1、2 和 3。
### 第二个出版商及其模式词

`0x11aec0` 有两个呼叫者。交换状态机在状态 3 中为克隆 ID 1 调用它一次。ID 2 和 3 大约 3.2 秒后来自另一个每帧调度程序：`0x13a780` -> `0x13a160` ->
`0x886530` -> `0x344510` -> `0x349bf0` -> `0x349a90`，每个队伍宝可梦一个游戏对象，0x1680 分开，状态字保持 8。

`0x886530` 运行来自主世界的每一帧，并在模式字 `+0x8C` (`0x886ed0..0x886ee8`) 上分支：1 或 2 战斗场景 (`0x886ef8`)，3 发布臂 (`0x886f24`)，其他任何内容都停在 8。 `0x344510` 是一次性的：当 `[x19+0x68]` 为非空时，它会提前返回，否则分配 0x278 字节并调用 `0x349bf0`。

设置器 `0x7c4530`（模式 1）、`0x7c4580`（模式 2）和 `0x7c45d0`（模式 3；最后两个然后调用
`0x147c90` 带0）通过`[singleton+0x288]`写入字；类 vtable `0x15afa68`（插槽 9 = `0x886530`）由 `0xe13388` 周围的重定位填充。从主世界追踪到已确定的交换，当模式字从 0 移动到 3 时，三个 setter 和 `0x5a733c` 从未触发。没有类方法存储到 `+0x8C`，并且 `.text` 中的 `+0x8C` 的 16 个常量存储中没有一个写入 3：作者未知。
### 接管必须执行的顺序

宣布克隆的电台会分配一个序列并将其标记在其公告上。`0x520c30`，请求方，当克隆的时候提前返回`+0x38`为零，`+0x110`已设置，或`+0xB0`和`+0xB8`两者都非空；否则它将序列分配到`+0x10C`并将播音员加入队列。`0x520ce0`，完成后，将播音员取消排队并将 1 写入`+0x110`仅当`+0xB0`和`+0xB8`是非空的并且`+0x10C`等于给定的值。`+0x110`是门的每站术语：位于的条目`+0x250`是队伍克隆，`station[i]` = `partyClone[i]+0x38`.

方加入的接管（克隆类型上的 `0x91`）与对等方公告的时钟相呼应；它自己的副本的公告带有自己的时钟：

    host   0xa1 clone type 4   00000cfe 01 2808ab      the sequence it allocated
    host   0xa1 clone type 1   00000cfe 01 2808ab
    joiner 0x91 clone type 4   00000cfe               echoed
    joiner 0x91 clone type 2   00000cfe               echoed
    joiner 0xa1 clone type 4   00000d21 01 2808ab      its own clock, the host's content
    joiner 0xa1 clone type 1   00000d21 01 2808ab

`+0xB0` 和 `+0xB8` 是嵌入在以下位置的播音员的列表链接（`sub+0x08`、`sub+0x10`）
`clone+0xA8`（`0x51e790`链接，`0x51e810`取消链接）； null 表示不在公告列表中。在工作会话中，两个克隆都已链接，并且没有分配任何内容；到达的队列克隆未链接分配，并且随后的完成被拒绝。入站 `0x82` 也会使 `0x520c30` 进行分配，因此用携带 `0x82` 的突发应答每个重新通告会为每个突发生成一个序列，大约每秒 30 个。

每个克隆携带一个通告时钟：通告者在 `0xa1` 上标记其网状时钟，对等体的确认和该克隆的下一个 `0xa1` 携带相同的编号，并且 `+0x10C` 持有它。当记录带有克隆的另一站最新`0xa1`的时钟时，记录匹配。
`0x520d30` 处理克隆类型 2 上的 `0x91`（否定确认）和 `0x520ce0`
`0xa2`，相同前提下；两者均取消与播音员的链接，并且只有 `0xa2` 向
`+0x110`。匹配的 `0x91` 取消公告，匹配的 `0xa2` 完成公告； `0xa2` 是根据 加入方自己的时钟缺失构建的。

该序列针对每个队列克隆并重新分配（在 `0x520cb8`），每次分配将 0x34 步进到 0x38。通过接管携带加入方自己的时钟，主机为两个队伍克隆分配了 `0x1114b`；克隆 0 的完成携带 `0x1114b` 并设置 `+0x110`，克隆 1 携带 `0x111b0` 并被拒绝：门 `0x11b080` 保持 false 并且状态字永不离开 4. 仅应答对等方的第一个克隆类型 2 发布并确认其余的将返回到在每次都有新鲜的顺序。
### 每个克隆的接管交换 a 加入方运行一次

接管是所有权转移：`0x520d30` 取消对等方的公告，加入方在自己的时钟下公告克隆。两个队伍克隆的参考交换，主机的公告为零：

```
+0 ms   host    0x81 clone 2, 0x81 clone 3, dest 0x0003
        host    0xa1 x2 per clone                        clock 0x197e, the host's
+5 ms   joiner  0x82, 0x91 x2, 0x82, 0x91 x2, 0x84 x2    echoing 0x197e
+75 ms  joiner  0x81 clone 2, 0xa1 x2                    clock 0x19c1, the joiner's own
        joiner  0x81 clone 3, 0xa1 x2                    clock 0x19c1
+102 ms host    0xa2 per clone                           clock 0x19c1, the joiner's
        host    0xa1 per clone                           clock 0x19e2, the host's own
+141 ms joiner  0xa2 per clone                           clock 0x19e2, the host's
```
 加入方在第一次宣布不拥有的克隆时，将每个克隆接管一次。之后的每一次重播都会得到一个带有该播报时钟的 `0xa2`，位于加入方站下的克隆类型 2 上，地址 `<clock> 00 00 00 02`。第二次接管会取消原本不打算易手的公告，而同行则可以无限制地重新公告。

`0xa2` 推动完成。一个电台自己的播音员在大约6ms内完成对自己的`0xa2`的环回，因此第一个队伍克隆总是完成；第二个需要加入方。工作加入方的突发不携带确认：对等方的 `0xa2` 对在 +37 毫秒时到达，加入方的单个 `0xa2` 在 +72 毫秒时到达，作为答复。从不重新声明的对等点永远不会取消链接（每个滴答构建器的取消链接，链接后大约 30 毫秒）并且不分配任何序列。

仅对等重新通告会在 20 到 60 毫秒后在克隆类型 1 上绘制对等的 `0x82`，并且
`0x82` 绘制主机的 32 个零的 4 型副本，游戏机用其 `1 1 1` 进行回答。在一次重新声明后既没有收到 `0x82` 也没有收到提交克隆的任何后续消息的零售主机将停留在其确认屏幕上，并且交换锁已保存。 `pokeldn.ldn.clone` 每 100 ms 重新发送仅对等的 `0x81`，最多 20 次，直到 `0x82` 到达。

实机在 63、26 和 62 毫秒后回答了提交克隆 4、7 和 10 的第一个仅对等公告。同行首创，仅`0x81`版主（`--withhold-announce 1` on
`bin/lgpe_host.py` 和 `bin/lgpe_join.py`，仅测试），100 毫秒后重发绘制游戏机的
`0x82` 每个角色完成三个交易。
### 公告的目的地字段决定什么

命令头 `0x51f820` 将 `+0x10` 布置为站位图。首次宣布克隆的 0x81 携带整个网格（0x0003）；克隆类型 4 和 1 上其后面的两个 0xa1，以及 35 毫秒后重复的公告，单独携带对等点 (0x0001)。给定网格位图，对等方在其自己的站点下的克隆类型 4 和克隆类型 2 上用两个 0xa2 进行应答；给定对等位图，它既不回答，又继续在克隆类型 1 上发送 0xa1，并且门 `0x11b080` 永远不会看到确认集填充。

克隆类型 1 上 `0xa1` 的重传计数表明工作会话与停滞会话：工作时每个站 9 次，每 0.12 秒一次，每次重播时由对等点接管，没有结束，其游戏静默。

每个克隆消息都是通过协议对象的第九个 vtable 槽 `0x51e3d0` 构建的（第四个返回 0x73）。其调用站点的文字类型：克隆类型 2 上的 0xa2 `0x51cbb8`、0x81 `0x51e92c`、
0xa2 克隆类型 3 `0x51cdd4`、0xc1 `0x51c9e4`、0x82 `0x51c60c` 和 `0x51cd5c`、0xe3 `0x51ad2c`，
0xf3 `0x51ef18`。该游戏在一个元素上包含三个克隆对象，类型 1 为 `game+0x90`，
`game+0x1710`，`game+0x1258` 处的类型 4；消息的克隆类型不会一对一地映射到它们。

|地址 |角色 |
|---|---|
| `0x51ab20` | CloneProtocol::vfunc9，每个元素接收 |
| `0x51c100` |接收调度：表 `0xf7673c` on（类型 - 0x11）将时钟与命令消息分开，`0xf76800` on（类型 - 0x84）到达命令路径 |
| `0xf769c4`，`0xf769e4` |采用高半字节结构；克隆类型|
| `0x51b010` |回复状态机，表 `0xf76674` 上（类型 - 0x21）|
| `0x51b1d0` |时钟驱动的重传调度程序
| `0x51f9b0`、`0x51fab0`、`0x51fbd0`、`0x51f820`、`0x51f4c0` |串行器：时钟请求、时钟回复、参与、命令头、ClockAndCount |
| `0x51c1e0` |删除一条消息，其计数在 [0xC] 不超过发件人的最后 |

元素偏移：+0x34 站、+0x40 状态、+0x50 时钟、+0x7a0 发送时间、+0x32c 结果。
