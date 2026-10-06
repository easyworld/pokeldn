---
title: ESP32 radio
parent: Hardware and setup
nav_order: 1
---

# ESP32 收音机

USB 串行上的 ESP32 板是无线收发设备。运行`firmware/esp32/`，承载LDN的供应商动作帧和以太网帧；广告加密、LDN 身份验证、IP 和 Pia 保留在主机上。 `pokeldn.ldn.esp32_wlan` 为 LDN 库提供了一个由板卡支持的工厂，因此 `ldn.scan`，
`ldn.connect` 和 `ldn.create_network` 运行不变，主机不需要 Wi-Fi 驱动程序。
## 支持的板卡

|芯片| 主机连接 |合并图像|
|---|---|---|
|经典ESP32（ESP32-D0WD、WROOM-32E）|通过 USB 串行桥接 UART0 | `pokeldn-radio.bin` |
| ESP32-S3 |原生 USB 串行/JTAG | `pokeldn-radio-s3.bin` |
| ESP32-C3 |原生 USB 串行/JTAG | `pokeldn-radio-c3.bin` |
| ESP32-C6 |原生 USB 串行/JTAG | `pokeldn-radio-c6.bin` |

所有目标均使用 2.4 GHz。不支持 ESP32-S2。 Seeed Studio XIAO ESP32C3 和 XIAO ESP32S3 没有板载天线，需要连接随附的外部天线；较大的 S3 板（例如 N8R2 和 N16R8）带有板载天线。具有独立 UART 和本机 USB 插槽的 S3、C3 或 C6 板需要本机插槽进行无线收发设备通信。 USB 串行/JTAG 使用 GPIO19 (D-) 和 GPIO20 (D+)，如 [Espressif 的 USB 指南](https://docs.espressif.com/projects/esp-idf/en/v5.2/esp32s3/api-guides/usb-serial-jtag-console.html) 中所述。在 C3 上，本机 USB 使用 GPIO18 (D-) 和 GPIO19 (D+)，如 [Espressif 的 C3 USB 指南](https://docs.espressif.com/projects/esp-idf/en/latest/esp32c3/api-guides/usb-serial-jtag-console.html) 中所述。 USB标识符`303a:1001`被多个芯片共享；刷机用esptool检测芯片。通过其 UART 套接字（DevKitC 上的 WCH CH343 桥）刷新 S3 成功，然后固件在该套接字上永远不会应答。当没有固件通过 USB 串行桥接应答时，桌面应用程序会从 ROM 引导加载程序（esptool `detect_chip`，然后硬重置）读取芯片类型，并将在那里找到的 S3、C3 或 C6 命名为插入了错误的插槽。

Seeed Studio XIAO ESP32C3 使用其 USB-C 插座来实现本机 USB 串行/JTAG。使用无线收发设备之前，请安装随附的外部天线。 BOOT 为 GPIO9，板载 LED 为充电指示灯（[Seeed 的开发板指南](https://wiki.seeedstudio.com/XIAO_ESP32C3_Getting_Started/)）。 C3 版本的运行频率为 160 MHz。电线和按钮任务在核心 0 上运行；双核目标将这些任务保留在核心 1 上。

XIAO ESP32C3 版本 0.4 在 macOS 上通过本机 USB 进行 2,000,000 字节的 BENCH 传输，作为 1429 条消息，没有丢失且没有错误的校验和，主机波特率设置为 115200 时速度为 880.1 KB/s，主机波特率设置为 1500000 时速度为 878.3 KB/s：主机波特率设置不会改变 USB 速度。启动时其空闲堆为 152656 字节。

Seeed Studio XIAO ESP32C6（ESP32-C6FH4，4 MB 嵌入式闪存）使用其 USB-C 插槽来实现本机 USB 串行/JTAG。当 GPIO3 为低电平时，其 RF 开关上电，GPIO14 选择陶瓷天线（低）或 U.FL 插座（高）（[Seeed 的板指南](https://wiki.seeedstudio.com/xiao_esp32c6_getting_started/)）； C6 固件在 Wi-Fi 启动之前将两者驱动为低电平，因此该板从其陶瓷天线辐射。每个 C6 板的图像都是相同的，并且不需要连接天线。在 ESP32-C6-DevKitC-1 上，GPIO3 和 GPIO15 仅到达引脚接头，GPIO14 未断开，可寻址 RGB LED 位于 GPIO8 上（[Espressif 的用户指南](https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32c6/esp32-c6-devkitc-1/user_guide.html)），因此 XIAO 引脚设置使该板的无线收发设备和部件保持不变。 BOOT为GPIO9； GPIO15 上的黄色用户 LED（低电平时亮起）显示 LED 外观；红色LED是充电指示灯。构建运行频率为 160 MHz，核心 0 上的连线和按钮任务与 C3 上一样。

C6是一款Wi-Fi 6芯片。它的站点保持在 11b/g/n，因此它的关联请求不携带 HE 元素，就像其他目标一样。其接收头（`esp_wifi_he_types.h`）没有`sig_mode`，
`mcs` 或 `cwb`；固件从 `cur_bb_format` 派生 RX_SNIFF 和 RX_CENSUS `sig_mode`，并从 `he_siga1` 中的 HT-SIG 派生 HT MCS 字节。它的速率字节是 OFDM 帧的 L-SIG 速率代码，而不是 `wifi_phy_rate_t`。 ESP-IDF v6.1 C6 Wi-Fi 库导出固件使用的每个私有符号，与 C3 具有相同的 `lmacConfMib` 偏移量。

XIAO ESP32C6 版本 0.2 在 macOS 上通过本机 USB 以 824.6 KB/s 的速度以 1429 条消息的形式进行 2,000,000 字节的 BENCH 传输，没有丢失也没有错误的校验和，并接受 5000 个上行链路命令中的 5000 个，没有丢失。启动时其空闲堆为 255196 字节。其陶瓷天线的火红加入方会话计数了板上 5155 个主机 ETH_TX 命令中的 5155 个，没有坏线框，也没有 USB 重新同步。

下面的经典 ESP32 测量使用 ELEGOO ESP32-D0WD-V3 板，除非指定了其他板。每盘已完成交易见[按盘交易](#trades-by-board)。
### 重置后的 USB 链接（C6、S3）

打开端口会通过 USB 串行/JTAG 重置 C6 或 S3（重置原因 11，核心重置）。与
`CONFIG_ESP_SYSTEM_BBPLL_RECALIB=y`，两个芯片上的 ESP-IDF 默认值，应用程序的启动运行 `recalib_bbpll()`（`esp_system/port/soc/esp32c6/clk.c`，在 S3 上相同）：在除 CPU 复位之外的任何复位上，它都会调用 `rtc_clk_cpu_freq_set_xtal()`，这会停止 BBPLL 而不检查其 USB 消费者，然后重新启动它。当主机与其通信时，USB 串行/JTAG 从该 PLL 获取 48 MHz 时钟。在 XIAO ESP32C6 上，链接有时会出现乱码，并一直保持这种状态，直到拔掉板：固件继续运行，SOF 帧号在启动后从未移动，
`USB_SERIAL_JTAG_INT_RAW` 存在 PID、CRC5 和位填充错误（`0000b5b2` 与 `0000b50a` 正常），答复卡在 IN FIFO 中，时钟使能、pad 和 PCR 寄存器与正常板匹配，GET_CONFIGURATION over EP0 失败，esptool 的 USB 重置没有答复。

| C6图像|端口打开（重置和启动）|链接失效，直到拔掉插头|
|---|---|---|
|重新校准 | 113 | 113 1、开113|
|重新校准关闭| 900 | 900 0 |

C6 和 S3 构建集 `CONFIG_ESP_SYSTEM_BBPLL_RECALIB=n`；它的 Kconfig 帮助允许使用 ESP-IDF v5.2 或更高版本构建的引导加载程序，并且每个合并的映像都带有自己的 v6.1 引导加载程序。 S3 设置未在 S3 上进行测试。 C3没有这个选项，也没有显示任何故障。关闭重新校准后，在 macOS 重新枚举设备（“设备未配置”）后，C6 上的 600 个打开中的 4 个一次没有找到答案，并且在下一次打开时找到工作链接。

C6 版本还带有 USB 手表 (`usbwatch.c`)：它每 5 ms 对 SOF 帧编号进行一次采样，一旦帧计数或主机发送了一个字节，就会在 2 s 停顿后重新启动芯片，并在下一个 HELLO 上将其前后的 USB 和时钟寄存器报告为 LOG 行。在 `idf.py` 环境中使用 `POKELDN_USB_BEACON=1` 构建，C6 映像还将这些寄存器、它看到的 SOF 更改以及它每秒读取一次的主机字节作为供应商操作帧（类别 127，OUI `02:55:53`）发送到组地址 `03:55:53:42:57:00`；当 USB 链路断开时，嗅探板将它们与 `esp32_sniff.py --mac 03:55:53:42:57:00` 保持在一起。 4 字节供应商标头之后的帧主体是 u32 小端：正常运行时间 ms、SOF 更改、主机字节、`wire_dropped`、停顿计数，然后是 `usbwatch.c` 中列出的 16 个寄存器。
## 角色

|角色 |董事会的职责 |
|---|---|
|闲置|在一个频道上混杂；每个带有 Nintendo LDN 前缀 `7f 00 22 aa` 的动作帧都会转到主机 |
|车站|通过 BSSID 和主机派生的 CCMP 密钥加入游戏机的网络 |
|接入点|主机 BSSID 上的隐藏 SSID WPA2 网络，以相同方式键入 |

游戏机的网络没有四次握手：两端均从广告服务器随机获取 CCMP 密钥。该固件替换了 ESP-IDF 私有 `struct wpa_funcs` 表 (`esp_wifi_driver.h`) 的四个条目。布局是 v6.1 blob 的 ABI；该固件拒绝针对另一个版本进行构建。

- `wpa_sta_connect` 在股票回调之前和之后安装开关站发送的 RSN 元素（CCMP、PSK、功能 `0x000c`），从而重建它。
- `wpa_sta_rx_eapol` 删除 EAPOL；一旦看到关联响应，站密钥就会进入 `esp_wifi_set_sta_key_internal`，然后 `esp_wifi_auth_done_internal` 打开端口。
- `wpa_ap_join` 将站添加到 hostapd 的表中，并在没有验证器状态机的情况下发送关联响应 (`esp_send_assoc_resp`)，因此没有 EAPOL-Key 消息 1 发出（`AP_START` 标志位 0 保持股票连接）。它对站的 MAC 进行排队；主循环安装成对密钥（`esp_wifi_set_ap_key_internal(CCMP, mac, 0, key)`）并打开端口（`esp_wifi_wpa_ptk_init_done_internal(mac)`），hostapd的`PTKINITDONE`命令（`wpa_auth.c:2290-2332`）。组密钥位于 `WIFI_EVENT_AP_START`，索引为 1。
- `esp_wifi_wpa_ptk_init_done_internal` 是 WPA2 站的 `WIFI_EVENT_AP_STACONNECTED`（事件 14，`ieee80211_supplicant.o`）的唯一海报。永远不要等待该事件来安装密钥：如果没有四次握手，它永远不会出现，并且游戏机的第一个加密帧会被丢弃。
## 接入点的帧

SoftAP的信标、探测响应和关联响应内置于封闭的环境中。
`libnet80211.a`。根据 `vendor/LDN` 的接入点发送 Switch 的内容，从 v6.1 blob（`ieee80211_output.o` 偏移量）中读取：

|领域 |切换形式| ESP32 软AP |可设置|
|---|---|---|---|
|隐藏 SSID 元素 | 32 个零字节 |长度 0 (`ieee80211_beacon_construct` 0xc4) |没有|
|支持的价格 | `82 84 8B 96 0C 12 18 24` | `8B 96 82 84 0C 18 30 60` |不;相同的 12 个速率和基本位，扩展 | 中的 9 和 18
|延长价格 | `30 48 60 6C` | `6C 12 24 48` |没有|
|能力，灯塔| `0x0511` | `0x0431`（短前导码常量，`ieee80211_getcapinfo` 0x7b）|没有|
| HT 元件 |无 |存在于 11b/g/n |删除：固件设置 11b/g |
| RSN 功能 | `0x000c` | hostapd 自己的 | set: `wpa_ap_get_wpa_ie` 返回 Switch 的元素 |
|世界MM |无 |存在于 11g |仅 11b-only 将其删除 |

隐藏的 softAP 仅应答定向探测，并在探测响应中包含真实的 SSID。没有配置 SSID 的关联请求将被丢弃 (0x9c6)。 `esp_wifi_80211_tx`接受信标并拒绝关联响应（`ieee80211_raw_frame_sanity_check` 0xf9）；该团块自己的信标无法被阻止。
## 串行协议

一个框架是`COBS(type | payload | crc32-le(type | payload))`然后是`0x00`； CRC 为 CRC-32/ISO-HDLC (`zlib.crc32`)。 115200 波特率下的经典 ESP32 启动； `BAUD` 开关两端。在 S3 上，
`BAUD` 在不改变 USB 传输速率的情况下被确认。 `0x00` 之前的任何内容（包括 ROM 的引导文本）都无法通过校验和并被丢弃。

|类型 |方向 | 厦门 |
|---|---|---|
|您好 | `0x01` 主机 |没有任何;回答为 CREDIT 0，然后为 INFO |
| `0x02` 波特率 | 主机 | u32 波特率；以旧速率结果，然后切换，等待 UART 耗尽最多 3 秒（在 115200 时，环保持 RX_MGMT 超过一秒）。 1500000 处的第一个 HELLO 有时会丢失（测量到的四个中大约有一个是开放的）； `open_serial` 重试 |
| `0x03` 频道 | 主机 | u8频道；仅闲置|
| `0x04` STA_JOIN | 主机 | u8 通道、6 个 BSSID、32 个 SSID（LDN SSID 的十六进制文本）、16 个密钥、6 个站 MAC（零 = 随机）；可选：u8 固定数据速率（AP_START 位 3..5 表），u8 最大 TX 功率为 0.25 dBm（`esp_wifi_set_max_tx_power`，8 至 84，驱动程序上限为 61），u8 标志：1 每帧前有 RTS，2 重试前无 RTS（`esp_wifi_internal_set_rts`）|
| `0x05` 停止 | 主机 |没有任何;回到空闲状态，按键已清除|
| `0x06` AP_START | 主机 | u8 通道，6 个 BSSID，32 个 SSID，16 个密钥，u8 最大站，u8 标志：1 股票关联和 4 路握手，2 站无 QoS，4 每个站数据帧没有 40 字节副本，位 3..5 固定数据速率，`0x40` 每 1000 TU 有一个信标， `0x80` 无混杂接收；可选的第二个标志字节： 1 驱动器的本底噪声检查， 2 其间隔 250， 4 每个 40 字节副本头部的接收时间， 8 重试限制 7 和 4， `0x10` RX_CENSUS 对于除其站的良好数据帧之外的每个帧；然后可选最大 TX 功率为 0.25 dBm |
| `0x07` AP_KICK | 主机 | 6 MAC，u16原因；取消验证 |
| `0x08` ETH_TX | 主机 |以太网帧，由驱动程序使用站密钥或组密钥进行加密。完整的驱动程序队列 (`ESP_ERR_NO_MEM`) 每 1 毫秒重试一次，最多 100 毫秒；发往离开站的帧立即失败，并显示 `0x3015` (`ESP_ERR_WIFI_NOT_ASSOC`)。站点将以太网源作为其 802.11 发送器地址发送：LINK 中除 MAC 之外的源永远不会得到确认 (49 of 49) |
| `0x09` RAW_TX | 主机 |没有 FCS 的 802.11 帧 (`esp_wifi_80211_tx`)；广告|
| `0x0A` 嗅探 | 主机 | u8通道，6个MAC；每个管理和数据帧到或来自它，整体，如RX_SNIFF； MAC ff:ff:ff:ff:ff:ff 将通道上的每个帧发送为 RX_CENSUS |
| `0x0B` 状态 | 主机 |没有任何;状态 | 回答
| `0x0C` 长凳 | 主机 | u32字节，u16消息大小（8到1600）；结果，然后 BENCH 消息的速度与 UART 接收消息的速度一样快 |
| `0x0D` LED | 主机 | u8模式、u8峰值亮度、u16周期ms（0：模式默认）、u16持续时间ms（0：直到下一个LED）；结果。较旧的固件答案 `0x106` |
| `0x0E` 显示器 | 主机 |屏幕命令（[屏幕](#the-screen)）；结果 `0x105` (`ESP_ERR_NOT_FOUND`) 无屏幕，`0x106` 来自旧固件 |
| `0x0F` 活着 | 主机 |没有，没有回复；武器[主机看门狗](#the-host-watchdog)。 1.4.0之前的固件回答`0x106`，因此主机只将其发送到1.4.0及更高版本 |
| `0x81` 信息 |董事会| u8协议版本（一）、6站MAC、6AP MAC、u8芯片改版，正文|
| `0x82` 结果 |董事会| u8 命令，i32 `esp_err_t` |
| `0x83` 日志 |董事会|文字|
| `0x84` RX_MGMT |董事会| u8通道，i8 RSSI，不带FCS的帧：LDN动作帧；同时还托管一个到板的 BSSID 的管理帧、一个数据帧的前 40 个字节以及一个站的 no-DS 广播整体 |
| `0x85` RX_ETH |董事会|驱动程序解密的以太网帧 |
| `0x86` 链接 |董事会| u8向上，u16原因，6 MAC；原因 `0xFFFF` 在 15 秒内没有关联，`0xFFFE` 密钥被拒绝 |
| `0x87` STA_JOINED |董事会| 6 MAC、u8 AID、i8 密钥安装结果、u8 端口打开 |
| `0x88` STA_LEFT |董事会| 6 MAC、u16原因|
| `0x89` 状态 |董事会|文本计数器（下）；托管期间每 2 秒自动发送一次，每 5 秒由主机轮询一次写入跟踪 |
| `0x8A` 长凳 |董事会| u32 序列和发票字节；最后一个携带序列 `0xFFFFFFFF` 和板花费的 u32 微秒 |
| `0x8B` 信用 |董事会| u32 自上次 HELLO 以来读取和处理的主机字节数，从其分隔符后的字节开始计数；当线路空闲时，每 1024 字节在 HELLO 上发送一次，并且在空闲时每 100 毫秒发送一次，在任何排队的消息之前 |
| `0x8C` RX_SNIFF |董事会| u8 通道、i8 RSSI、u8 `sig_mode`（0 传统、1 HT）、u8 传统速率代码 (`wifi_phy_rate_t`)、u8 HT MCS（40 MHz 的第 7 位）、无 FCS 的帧；还有通道上的每个 10 字节 ACK |
| `0x8D` TX_DONE |董事会|驱动程序的一帧、站或接入点的 TX 完成：u32 板时间 µs、自 ETH_TX 完成以来的 u32 µs（如果没有则全部为 1）、由对等无线收发设备确认的 u8、u8 接口、u16 长度、帧的前 24 个字节（其 802.11 标头）|
| `0x8E` 按钮 |董事会| BOOT 按下，去抖超过 30 ms：u32 板时间 µs，u16 自启动以来按下计数；主机打印 `BOOT button, mark N` 并且跟踪保留它 |
| `0x8F` RX_CENSUS |董事会|每个接收到的帧，FCS 故障和控制帧包括：u32 接收时间 µs、i8 RSSI、i8 本底噪声、u8 `rx_state`（0 好）、u8 数据包类型（0 管理、1 控制、2 数据、3 其他）、u8 `sig_mode`、u8 速率代码、u8 MCS（40 MHz 的位 7）、u16 `sig_len` 带 FCS，帧的前 16 个字节 |

`rx_state` 98 标记双流 HT（MCS 8 到 15），单流 ESP32 永远不会解码（一次普查中 79 个中的 79 个）； 65 标记任何其他调制的损坏帧（5605 中的 1397）。

|状态计数器|这算什么？
|---|---|
| `tx_acked`，`tx_unacked` |驾驶员的 TX 完成结果 |
| `tx_eth`、`tx_eth_failed`、`tx_eth_retried` | ETH_TX 发送、失败、发现驱动程序队列已满的呼叫 |
| `tx_queued_max_us`、`_total_us`、`_n`、`_pending` | ETH_TX 至 TX 完成，过度匹配 TX_DONEs |
| `wire_dropped`，`wire_rx_bad` |板到主机消息被丢弃； 主机命令失败 COBS 或 CRC |
| `uart_fifo_ovf`、`uart_buffer_full`、`uart_overflow` | 128 字节硬件 FIFO 和 16 KB 环溢出及其总和 |
| `uart_frame_err`，`uart_events_full` |成帧、奇偶校验和中断事件； UART 事件队列满时滴答（计数器可能计数不足）|
| `read_max_us`、`write_max_us`、`handler_max_us`、`handler_max_type` |最长的主机链接读取轮次（包括 20 毫秒超时）、写入等待和命令及其类型 |
| `heap_min`、`queue_max`、`refused_heap`、`refused_queue` |最少的可用堆、最深的传出队列、在堆层和满队列上拒绝消息 |
| `tx_eth_max_us`、`tx_eth_total_us`、`tx_eth_slow` | ETH_TX 中的 `esp_wifi_internal_tx`，重试包括：最长、总和、计数超过 5 ms |

EtherType `0x88B7`帧是LDN认证； `esp32_wlan` 将它们变成LDN图书馆的
`CustomFrameEvent`。每个其他以太网帧都会进入由 `POKELDN_L2=tap|userspace` 选择的 L2 端口：

|港口|哪里 |发射器插座|
|---|---|---|
| `userspace_ip` 堆栈 |默认，每个平台| `userspace_ip.udp_socket` 和 `packet_socket` |
|以接口命名的内核TAP |仅 Linux，`POKELDN_L2=tap` |内核套接字，`SO_BINDTODEVICE` 和 `AF_PACKET` 不变 |
| `MemoryPort` |测试|无 |

创建TAP需要`CAP_NET_ADMIN`。桌面应用程序以用户身份运行，因此在 Linux 上，TAP 默认在板加入任何内容之前失败。
### 主机看门狗

从固件 1.4.0 开始，主机每秒发送 ALIVE (`esp32.ALIVE_EVERY`)，从 INFO 中选择
`version=` 文本。 HELLO 后的第一个 ALIVE 武装手表； HELLO 会解除它，因此从不发送 ALIVE 的主机永远不会被观看。准备好后，一块处于空闲状态且在 5 秒内没有读取主机命令的板 (`HOST_SILENT_US`) 会运行 STOP 的拆卸：接入点停止信标发送，其站点断开连接，站点断开连接。然后，它会丢弃主机的每条消息（未计数），直到主机再次发送命令：主机从 USB 板消失，否则会将每个排队或无意中听到的消息变成 500 毫秒写入和 `wire_dropped`，并且 LED 警报变成恒定的 `flash3`。

在 `frlg_trade_host.py` 交换室中带有零售火红且主机被 SIGKILL 杀死的 XIAO ESP32C6 上，游戏机显示 2318-0006，后来的 JOIN 搜索没有列出主机，并且 LED 返回到空闲状态。如果没有丢弃，LED 仍保持在 `flash3` 上。
## 串行上限

在 921600 波特率、8N1 的经典 ESP32 UART 上，板到主机线路传输 92.16 KB/s。消息的开销加上类型字节、四字节 CRC、COBS 开销（每 254 和定界符一个字节），对于 RX_MGMT，还需要两个字节的通道和 RSSI。 Pia 有效负载是 AES-GCM 密文并且不压缩。

|交通 |线路费用是多少？
|---|---|
|一个站的数据框，托管|帧为 RX_ETH，40 字节 RX_MGMT 副本为 48 字节，除非设置了 AP 标志 4 (`POKELDN_ESP32_AP_FLAGS=4`) |
|一个站的数据框，加入 |仅框架为RX_ETH；站模式单独传递管理帧|
|附近有LDN 广告|整个动作帧，每个网络每秒大约十个|

传出队列可容纳 384 条消息，并拒绝低于 64 KB 空闲堆的消息；朱主机的开放爆发导致 128 条目的队列溢出（测量时丢弃了 337 条消息）。游戏机以线路速率将堆保留在该层（`heap_min` 63976、`queue_max` 95、`refused_heap` 219）：堆在队列填满之前拒绝 RX_ETH。
### 波特率

`POKELDN_ESP32_BAUD` 设置 `open_serial` 切换的速率，默认为 921600。 ESP32 UART 运行至 5 Mbaud； USB 桥接器设置了限制。 `tools/ldn/esp32_bench.py --port PORT --bauds
921600,1500000,2000000,3000000` 以每种速率传输 BENCH。 macOS 上的 ELEGOO 板桥（“CP2102 USB 转 UART 桥控制器”、idProduct 60000、bcdDevice 0x100）：

|波特率|测量|留言 |迷失|错误的校验和
|---|---|---|---|---|
| 921600 | 921600 91.7 KB/秒 | 1429 共 1400 字节 | 0 | 0 |
| 1000000 | 99.4 KB/秒 | 1429 共 1400 字节 | 0 | 0 |
| 1500000 | 149.1 KB/秒 | 4286 共 1400 字节 | 0 | 0 |
| 1500000 | 140.2 KB/秒 | 20000 个 100 字节 | 0 | 0 |
| 2000000, 3000000 |董事会从未以新的费率回答“HELLO”| | | |

传说中位于 921600 的 Z-A 席位与 CREDIT 没有拒绝关联，其第一条消息位于 1.68 秒（1500000 处为 1.7 秒），并且计算了 695 个 ETH_TX 中的 695 个消息。
### 主机到板命令丢失和信用

在游戏机泛滥的情况下，主机命令可能会在处理程序之前丢失：一个在 7.5 秒内将主板 660 ETH_TX 交给主板的朱座计有 92 个（`tx_eth + tx_eth_failed`），其余的没有花费 CCMP 数据包编号，`tx_eth_retried` 0。每个原因，在没有对策的情况下测量，以及固件是什么做：

|原因 |无对策测量|固件|
|---|---|---|
|核心 0 上的 UART 中断与 Wi-Fi 任务 |上面的座位|从阅读器任务安装驱动程序，核心 1 |
| ETH_TX 在读取器任务中等待完整的 Wi-Fi 队列； 16 KB 环已满，FIFO 溢出 | `esp32_bench.py --uplink 5000`（5000广播ETH_TX到空网络）在1500000：369到429丢失，`uart_fifo_ovf` 305，`wire_rx_bad` 169； 921600 没有 |信用： 5000 人中的 0 人以任何比率损失 |
| FIFO 在 120 字节时耗尽 (`UART_FULL_THRESH_DEFAULT`)，在 1500000 时从满需要 53 µs |朱座，信用：1901 年的约 210 号丢失，`uart_fifo_ovf` 235 |阈值 32 (`uart_set_rx_full_threshold`)，640 µs：1691 中的 10，`uart_fifo_ovf` 0 |
| `uart_read_bytes` (IDF 6.1 `uart.c:1738`) 再次等待每个环项目的超时，直到它有 `length` |每 15 ms 读取一个 21 字节命令，延迟 461 ms (`--trickle 5`)；朱座 `read_max_us` 311644 |等待一个字节，然后取`uart_get_buffered_data_len`：20.3 ms |
| `uart_write_bytes` 在整个 TX 环上忙环 (`uart.c:1662`)；作者（优先级 20）与读者（19）共享核心 1 |朱洪水持有ETH_TX长达707毫秒； `esp32_pair_bench.py AP STA --flood 0 --send 20 --bench`：`read_max_us` 7982767，74 次发送被拒绝 |作者睡眠直到框架适合（`uart_get_tx_buffer_free_size`）：30382 µs，没有人拒绝（[朱和紫](sv.md#the-retail-acknowledgement-and-a-flood-of-retransmits)）|
|每 32 个字节将一个 `UART_DATA` 事件发送到携带溢出事件（`uart.c:1369`、`1543`）的 64 条目队列中，在 1500000 时在 14 毫秒内满 |长命令期间的溢出可能无法计数读者上面的任务每次都会耗尽它的精力； `uart_events_full` |

忽略窗口 (`--uplink 5000 --no-flow`)，每个 `uart_fifo_ovf` 丢失 136.5 个字节，大约一个 FIFO，并且 `uart_events_full` 保持 0：完整的环停止 `UART_DATA` 事件。

信用：一旦主板发送了一个，主机将写入和未报告的写入线程保持在 8 KB 以下（`esp32.FLOW_WINDOW`），因此启动器的三重循环仅排队，并在超过 512 个排队帧（`Radio.tx_dropped`）后丢弃 ETH_TX 和 RAW_TX。如果窗口关闭时没有 CREDIT 移动，则计数重复 0.3 秒不变，意味着线路上丢失了字节，并且主机重新打开窗口 (`Radio.flow_resyncs`)；不发送计数的板正忙并获得 5 秒。切勿仅在静默状态下重新同步：繁忙的读取器最多可等待 0.7 秒，然后重新同步会将 16 KB 的数据与 16 KB 的环进行传输。注销的字节保持注销状态；超过损失允许范围的信用会缩小损失。 CREDIT 跳过传出队列（最多排队一个），但比朱座位的 150 KB/s 延迟大约 0.5 秒到达
RX_ETH。没有 CREDIT 的板永远不会打开窗口，主机也不会受到限制。该板记录命令的时间超过 50 毫秒 (`slow command`)，读取器翻转时间超过 100 毫秒 (`reader held`)。

利用队列前面的空闲计数和 CREDIT，主板对主机交给它的每个 ETH_TX 进行计数：228 个主板会话中的 520315 个中的 520315 个（经典 ESP32 直至固件 1.2.0、C3、C6 1.0.0），每个溢出和线路计数器为 0，每个重复的空闲计数等于写入的字节。其中六个会话的主机每秒写入超过 500 ETH_TX，而板到主机线路的运行速度为 148 到 152 KB/s。

空闲计数之前的固件丢失了一些未计数的主机命令：921600 处的 2333 条命令中的 6 个没有 CREDIT，1500000 处的 1691 条命令中有 10 个命令位于队列后面，每个命令都有
`wire_rx_bad` 1 和 `tx_eth_retried` 0。主机到主机线路达到上限时，主机第一次突发时损耗下降（921600 处一秒 91.4 KB）。该固件的写入器在读取器上方的完整 TX 环上旋转，并且只有读取器耗尽 UART 事件队列，因此饥饿读取期间的溢出不计在内。用于多个丢失命令的一个 `wire_rx_bad` 适合一个连续的丢失范围。哪个缓冲区丢弃了字节是无法测量的：这些跟踪不携带任何信用。

HELLO 会重新启动这两个计数，因此主机会保留它，直到没有任何内容在运行，并保持窗口关闭，直到板的 CREDIT 0。在会话中期 HELLO（扫描发送一个，`EspFactory.create_monitor`）后不受限制地写入的主机超出了保持 0.5 秒的模拟 16 KB 环 76423 字节； `tests/test_esp32.py::test_a_hello_mid_session_does_not_open_the_window` 将其固定。
`tools/ldn/esp32_cmd_loss.py TRACE` 协调跟踪：针对 `tx_eth +
tx_eth_failed` 写入的 ETH_TX，自 HELLO 以来针对最后一个 CREDIT 写入的字节。
### 传输时序

在一个平静的朱座上，ETH_TX平均花费0.12毫秒，在驱动程序中最多花费1.57毫秒，游戏机在发送后0.35秒内保存了所有44条加入方的记录。

TX_DONE 将板与对等板分开。在洪水朱座上，从 ETH_TX 到 TX-done，一帧平均等待 1.0 毫秒，最多 6.8 毫秒，游戏机的无线收发设备确认了 1267 个中的 1267 个。
TX_DONEs 在他们的主板时间平静后 15 毫秒到达主机，最糟糕的一秒达到了 446 毫秒（最多 590 毫秒）：主板到主机线路在洪水下备份。线路时间减去最小到达偏移量就得到了消息在线路上的延迟。

双板工作台（`tools/ldn/esp32_pair_bench.py`，200 字节站帧）传送每个站帧：每秒 20 个站帧中的 187 个（ETH_TX 到 TX 完成的平均时间为 1.6 毫秒，最多 10.7 毫秒），每秒从接入点广播 100 个 1200 字节广播，每秒传输 1227 个站帧中的 1227 个点，大约 96% 的空气（平均 26.8 毫秒，最多 218 毫秒）。

测量陷阱：嗅探器板的线路像任何板一样以突发方式备份，因此它报告的帧可能会在播出后一秒到达主机；以 1500000 运行，并按同行确认的时间交付。当它自己的线路饱和时，它对另一块板的帧的计数被低估。 BENCH 填满其发票一次； RNG 补注将其保持在该线的速率以下。该板作为接入点发送的洪水以 1 Mbit/s 的速度广播，并以每秒约 90 帧的速度在空中传播。
## 保持并接收失误
### 火红持有

五个火红交易，以棋盘为接入点，每次交易一行；游戏机承认每一帧。等待ETH_TX到TX-完成；重试是嗅探器看到的带有重试位的数据帧的份额。

|频道 |框架|等待中位数|等等 p99 |等待最大 |保持超过 100 毫秒 |重试 AP / 游戏机 |
|---|---|---|---|---|---|---|
| 1 | 7489 | 1.24 毫秒 | 116 毫秒 | 261 毫秒 | 5 | 13.3% / 12.8% |
| 6 | 13670 | 0.85 毫秒 | 18 毫秒 | 108 毫秒 | 1 | 10.5% / 7.7% |
| 11 | 11 7069 | 7069 0.86 毫秒 | 9 毫秒 | 46 毫秒 | 0 | 15.0% / 5.7% |
| 1 | 7332 | 1.03 毫秒 | 25 毫秒 | 88 毫秒 | 0 | 20.6% / 9.4% |
| 1、24 Mbit/s 固定 | 6892 | 0.73 毫秒 | 69 毫秒 | 185 毫秒 | 5 | 2.8% / 14.3% |

主机到板的中值增加了 0.12 到 0.47 毫秒（写入 ETH_TX 的套接字）和 3.1 到 3.4 毫秒（ETH_TX 到板）。每次超过 100 毫秒的等待都是队头：游戏机尚未确认的一帧将持续 108 到 261 毫秒，其后面的帧会突发完成（5 毫秒内最多 10 个），并且接入点的操作帧继续进行。嗅探器以 54 或 48 Mbit/s 的速度看到一到三个头帧副本，游戏机的帧位于它们之间，所有电源管理位均已清除：游戏机在通道上保持唤醒状态。通道决定保留（通道），重试共享则不决定。

|发件人 |首次尝试 54 Mbit/s |重试 |
|---|---|---|
|板（接入点）| 91% 至 100% | 54 Mbit/s 为 77% 至 92%，然后为 48，很少为 6 或 36 |
| 游戏机 | 92% 至 99% | 48、36、24、18，低至 1 Mbit/s |

接入点标志字节的位 3 至 5 引脚其数据速率（`esp_wifi_internal_set_fix_rate`；0 是速率控制）。 `POKELDN_ESP32_AP_FLAGS=0x28` 引脚 24 Mbit/s：重试份额降至 2.8%，保留状态保持不变。

|位 3..5 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|
|速率，兆比特/秒 | 1 | 11 | 11 6 | 12 | 12 24 | 36 | 36 54 | 54

是什么让主板在副本之间等待大约 100 毫秒尚不清楚。 `tools/ldn/esp32_hold.py CAPTURE
TRACE` 将每个等待分为几个阶段，按长度配对 TX-done（它们完成时乱序）；
`tools/ldn/esp32_hold_air.py` 列出了嗅探器在每次保持期间看到的内容。
### CPU时钟

固件以 240 MHz 运行 CPU（`CONFIG_ESP_DEFAULT_CPU_FREQ_MHZ_240`；IDF 的默认值为 160）。通道 1 上有 6 个火红交易，每次交易一行；错过的是董事会没有听到的游戏机第一批副本的份额：

|中央处理器 | RX 缓冲器 |框架| p90 | p90 | p99 | p99 | p99.9 | p99.9超过 5 毫秒 |超过 40 毫秒 |超过 80 毫秒 |持有|错过了| 游戏机重试 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 160兆赫| 16 | 16 6744 | 4.7 毫秒 | 30.4 毫秒 | 91.7 毫秒 | 605 | 605 41 | 41 10 | 10 1 | | 8.8% |
| 160兆赫| 25 | 25 6999 | 4.6 毫秒 | 34.4 毫秒 | 106.5 毫秒 | 615 | 615 57 | 57 19 | 19 1 | 6.8% | 13.0% |
| 240兆赫| 25 | 25 7425 | 3.1 毫秒 | 13.5 毫秒 | 34.3 毫秒 | 322 | 322 5 | 0 | 0 | 5.2% | 12.4% |
| 240兆赫| 25 | 25 7235 | 3.0 毫秒 | 15.7 毫秒 | 66.3 毫秒 | 242 | 242 16 | 16 3 | 0 | 4.9% | 11.9% |
| 160兆赫| 25 | 25 8349 | 4.3 毫秒 | 27.5 毫秒 | 82.3 毫秒 | 666 | 666 41 | 41 9 | 0 | 5.3% | 10.2% |
| 240兆赫| 25 | 25 7021| 5.0 毫秒 | 31.7 毫秒 | 109.6 毫秒 | 708 | 708 57 | 57 16 | 16 1 | 8.5% | 18.9% |

一种设置的运行之间的差异与时钟的差异一样大。
### 频道

频道被占用后，需要等待很长时间。在测量这些交易时，频道 1 还承载游戏机的家庭接入点并进行漫长的等待：

|频道 |交易 |等等 p99 |等待最大 |交易持有时间超过 100 毫秒 |董事会错过了，游戏机第一个副本|
|---|---|---|---|---|---|
| 1 | 9 | 13.5 至 116 毫秒 | 65 至 261 毫秒 | 5 | 4.9% 至 8.5% |
| 6 | 1 | 18 毫秒 | 108 毫秒 | 1 | |
| 11 | 11 4 | 9 至 11.2 毫秒 | 19 至 46 毫秒 | 0 | 3.3%、5.5%、6.0% |

在通道 11 上，主板在相同的 p90 等待（4.5 ms）下错过了同样多的第一个副本；只有尾部不同（20 毫秒内有 8 帧和 9 帧，而 42 到 137 帧）：接收未命中不会保持。 `config/host.local.toml`取`[host] channel`；游戏机加入 1、6 或 11 上的主机。
### 董事会是聋方

嗅探板将每个 ACK 保存为 10 字节 RX_SNIFF； ACK 仅命名其接收者，因此
`tools/ldn/esp32_hold_air.py` 将其与之前的数据副本配对；副本被确认并再次发送意味着其发送者错过了 ACK。通道 1 上的一次火红交换（6744 帧）：

|发件人 |第一份副本| | 之后没有 ACK |确认并再次发送 |
|---|---|---|---|
|董事会| 6514 | 490 (7.5%) | 56 | 56
| 游戏机 | 4517 | 4517 428 (9.5%) | 2 |

在那次交换中，董事会错过的 ACK 远多于游戏机（56 对 2）。在保持期间，板既不会听到游戏机的数据，也不会听到其 ACK：其所保持帧的副本每隔大约 40 ms 发出，并且游戏机的 42% 到 66% 的帧携带重试位（整个会话中的 11% 到 14%），而嗅探器以 -19 到 -21 dBm 听到双方的声音。

游戏机的重试是主板的接收未命中。通过与嗅探器（`tools/ldn/esp32_rx_copies.py HOST_TRACE SNIFF_TRACE --ap BSSID --sta MAC`）的序列号匹配，游戏机多次发送的帧到达主板的RX_MGMT头，将重试位复制为一份，重试位位于1027中的1008；这样的副本没有更早的序列号，仅从电路板的跟踪上就可以看出它的缺失。该主板在 54 和 48 Mbit/s、-20 dBm 下错过了游戏机第一个副本的 4.5% 到 12.1%。错过第一个副本的概率为 37% 到 52%，听到一个副本的概率为 28% 到 32%； RSSI、速率和长度没有不同。
### 在两个板上接收未命中

`tools/ldn/esp32_pair_bench.py AP STA --flood 0 --burst N --send R` 让站板发送 200 字节帧，并根据接入点的标头副本计算其第一个副本丢失的帧。任一板都会在空闲空气中作为接入点丢失，以 -43 至 -48 dBm 收听电台：每秒 20 至 100 帧时为 5.5 至 22.2%，相同的 30 秒运行范围为 6.1 至 43.7%。站等待确认的最长等待时间在通道 1 上为 89 到 100 毫秒，在通道 11 上为 8 到 22 毫秒。随着标头副本中的接收时间（RSSI 之后的第二个 AP_START 标志字节位 2、`rx_ctrl.timestamp`、u32 µs），丢失率在 102.4、51.2、25.6 和50 和 100 Hz 时为 1024 毫秒。

|变量|第一份错过了|
|---|---|
|站速率（STA_JOIN 速率字节，`--sta-rate N`），通道 11 | 54 Mbit/s OFDM 2.3 至 4.0%、6 Mbit/s OFDM 1.9 至 5.4%、1 Mbit/s DSSS 0.04 至 0.2% |
|站功率（`--sta-power`，0.25 dBm），54 Mbit/s | 78（默认，19.5 dBm）1.5 至 3.1%，28：4.5 至 12.9%，12：15.3 至 20.8%；接入点从 17 到 61 的读数为 -33 到 -35 dBm |
|通道，54 Mbit/s | 1：3.7～9.7%、3：0.8%、5～9：0.8～2.3%、11：2.1～5.7%； 13 拒绝 (`0x102`) |
| ESP-IDF 驱动程序，通道 3 | v5.5.5 5.0%，v6.1 4.1% |
| STA_JOIN 标志 1，每帧之前的 RTS | 2.1%至2.3%对4.6%至4.8%；标志 2，重试前无 RTS，3.7 至 4.9% |

没有变化：每 1000 TU 一个信标 (AP `0x40`)；混杂接收关闭（AP `0x80`）；噪声基底检查（第二个字节位 0，清除 `g_pm+21`，因此 libpp 的 `pm_noise_check` 提前返回）或其 `NoiseTimerInterval`（`pp.o` `.data`，u16 100）在 250（位 1）； 25 个静态接收缓冲区 (`CONFIG_ESP_WIFI_STATIC_RX_BUFFER_NUM`) 与 16 个； 240兆赫； `CONFIG_ESP_WIFI_EXTRA_IRAM_OPT=y`；接入点的功率为 19.5、10 或 3.5 dBm； Switch 在蓝牙关闭的情况下进入睡眠状态。丢失次数取决于调制和信道，而不是信号余量：6 Mbit/s 丢失次数与 54 次一样多，DSSS 几乎从不丢失。两个驱动程序逐字节共享`libphy.a`和`hal_mac_rx.o`，相同的寄存器写入、接收中断、缓冲区回收和发送完成代码； v6.1 在每帧路径上添加 `wifi_assert` 并传递 `wpa_ap_join` 一个结构，而 v5.5.5 传递 9 个参数。

通道 1 和 11 繁忙率为 8.7 至 13%，每秒有 44 至 107 个相邻帧，通道 3 至 9 繁忙率为 0.3 至 1.7%，所有本底噪声为 -96 dBm (`tools/ldn/esp32_census.py`)。接入点自身的普查（第二个标志字节 `0x10`）在 13.1% 的时间丢失之前的 3 毫秒内找到邻居帧，在听到副本之前的概率为 11.0%；在未命中 0.0 或 1.1% 与 0.0 或 0.1% 之前的 2 或 5 毫秒内发出探测请求。 85% 到 91% 的失误不会在接入点留下任何痕迹，甚至 FCS 故障也不会留下。

该板最常错过其自身传输后的帧。火红游戏机在 RTS/CTS 之后发送每个数据帧，尽管该板的信标携带 ERP 字节 0；数据跟随板卡的 6 Mbit/s CTS 滞后 60 µs（44 µs 加 SIFS），一次交换中丢失了 4034 个数据中的 329 个。在替补席上，以 54 Mbit/s 的速度突发 4 次：第一帧 0.5 至 3.0%，第二帧 2.4 至 4.6%，第三帧 4.7 至 8.7%（通常是最多），第四帧 2.6 至 7.6%。

ESP32 站在数据之前的 RTS 128 µs 后发送每次重试（`lmacConfMib` +42，RTS 之前重试，0；RTS 阈值 2346 在 +22）； `esp_wifi_internal_get_rts` 和 `_set_rts` 均通过打包的 `{u16 threshold, u8 retries before RTS, u8 long, u8 short}` 进行访问。 ACK 和 CTS 速率表位于 `0x3ff73400`..`0x3ff7341c`。接入点在 90 秒内听到的 8527 个 RTS 中，有 311 个（3.6%）得到应答，CTS 后的数据丢失；上面的计数忽略了这些。驱动程序在软件中重试：`lmacRetryTxFrame`（libpp `lmac.o`）重新发送通过
`lmacTxFrame` 最高至 `lmacConfMib` 限制（短 +21，长 +20，默认为 32），由
`esp_wifi_internal_set_retry_counter(short, long)`。以每秒 100 个单播帧的速度从接入点 (`--flood 100 --unicast`) 帧等待最多 24 毫秒；两块板无法重现 100 毫秒的保持时间。

无论信标间隔如何 (`tools/ldn/esp32_bench_fold.py FILE
PERIOD_US`)，站板的慢速发送（超过 3 毫秒，`--done-out`）都会聚集成 102.4 毫秒周期的二十分之二（29% 到 43% 对 2% 到 12%）。
`tools/ldn/esp32_bench_drift.py` 根据主机测量两个板的时钟（600 秒内间隔 1.9 ppm）并扫描折叠周期。
## 用户空间堆栈

`pokeldn.ldn.userspace_ip` 在主机进程内携带 IPv4、UDP 和 ARP，用于接口后面没有内核的接口。当端口存在时，堆栈会在调用者的接口名称下注册（对于加入者为 `ldnclient`，对于接入点为 `ldn-tap`）； `userspace_ip.lookup(name)` 对于内核接口返回 None，这是每个启动器选择其路径的方式。

- 地址和邻居来自 LDN 图书馆的 `add_address` 和 `add_neighbor`；任何接收到的帧上的源地址都会被学习为邻居。
- 以 `.255` 或等于广播地址结尾的目的地将转到 `ff:ff:ff:ff:ff:ff`。没有邻居条目的单播目的地发送 ARP 请求并丢弃数据报。对堆栈自身地址的 ARP 请求得到应答。
- 超过1472字节的数据报被分段；重新组装传入的片段（5 秒超时）。计算 UDP 校验和。
- `udp_socket(port)` 代表绑定到接口的 UDP 套接字，`packet_socket()` 代表传送整个 IPv4 以太网帧的 `AF_PACKET` 套接字。每个都使用一个套接字对，每个排队数据报一个字节，因此 `select` 和 `trio.lowlevel.wait_readable` 可在 macOS、Linux 和 Windows 上工作。   TCP 套接字对禁用 Nagle 缓冲，因此就绪字节会立即到达读取器。
- 板的框架通过启动器自己的三重奏循环中的三重奏任务到达堆栈。该循环内的阻塞 `select` 会使它们挨饿，并且每个数据报都会等待完整的超时；在 `trio.move_on_after` 下等待 `trio.lowlevel.wait_readable`。 `select(0.05)` 中的朱加入方每 50 毫秒处理一条消息，同时游戏机重新发送其记录（测量为 50 到 70 秒）。
## 开发板的 LED 和按钮

LED 模式驱动经典 ESP32 板上的 GPIO2 和 C6 上反转的 GPIO15（XIAO ESP32C6 的黄色 LED）。 S3 和 C3 固件保留 LED 引脚。 BOOT 跟踪标记在经典 ESP32 和 S3 上使用 GPIO0，在 C3 和 C6 上使用 GPIO9。

ELEGOO ESP-32 Type-C 板（CP2102、ESP32-D0WD-V3）带有带有 PCB 天线的无品牌模块，并且没有 Espressif 模块名称：

|部分|连线至|可控|
|---|---|---|
|红色LED | 3.3V 电源轨 |不，只要板通电就会亮起|
|蓝色 LED | GPIO2，高电平时亮起|是的 |
| EN 按钮 |芯片复位|没有|
|启动按钮| GPIO0 | yes: 每次按下都会发送 BUTTON (`0x8E`)，闪烁 LED 并唤醒屏幕 |

GPIO2 和 GPIO0 是捆绑引脚（在下载模式下复位时为低电平或悬空）；固件仅在启动后驱动 GPIO2。从 ROM 引导加载程序，通过写入 GPIO2 的 IO_MUX（`0x3FF49040`、`MCU_SEL` 2）、其输出选择（`0x3FF44538` = `0x100`）、`GPIO_ENABLE_W1TS` 和
`GPIO_OUT_W1TS`（位 2）。

固件每 10 毫秒从内核 1 上的优先级 1 任务中使用 LEDC PWM（13 位，5 kHz）驱动蓝色 LED。职责为2.2次方；外观的变化交叉淡入淡出超过 150 毫秒。

|图案|编号 |默认期限|形状|
|---|---|---|---|
|汽车 | 0 | |该模式的外观如下 |
|关、开| 1, 2 | | |
|呼吸| 3 | 3000 毫秒 |升余弦|
|眨眼| 4 | 1000 毫秒 |开启一半周期，80 毫秒缓和边缘 |
|闪3 | 5 | 1000 毫秒 |在此期间的前 60% 中闪烁 3 次 |
|斜坡上升、斜坡下降 | 6, 7 | 1000 毫秒 |一次，立方缓入，然后保持|
|脉搏| 8 | 1200 毫秒 |快速膨胀，缓慢立方下降|

|模式 |自动查找|
|---|---|
|启动|一个脉冲，900 毫秒 |
|闲置|呼吸，昏暗，4 s |
|加入游戏机 |快速闪烁，250 毫秒 |
|托管，无站|呼吸，更明亮，1.5 秒 |
|加入或主持电台 |开，暗 |
|嗅探|关闭 |

收到或完成的每一帧都会使顶部的 LED 闪烁。加入失败（LINK `0xFFFF`、`0xFFFE`）、拒绝按键、丢失板到主机消息或丢失主机命令会播放 flash3 1.5 秒。一次完成的交换或神秘礼物的交付时间会达到 800 毫秒以上，并持续 3 秒 (`pokeldn.ldn.show_done`)；剑礼物主机，一个没有回读的灯塔，没有这样的时刻。 `tools/ldn/esp32_led.py --port PORT PATTERN` 套装外观； `--demo` 显示每个。
## 屏幕

I2C 上的 SSD1306 128x64 一位 OLED 是可选的。启动时，固件探测 0x3C，然后探测 0x3D；当两者都没有回答时，它会释放引脚并且不启动任何操作。对于屏幕，最后一个核心上的优先级 1 任务每 50 毫秒绘制一帧，并以 400 kHz（1031 字节，约 23 毫秒）发送该帧。

|目标| SDA | SCL |板针|
|---|---|---|---|
| ESP32 | GPIO21 | GPIO22 |开发套件 V1 D21、D22 |
| ESP32-S3 | GPIO8 | GPIO9 | |
| ESP32-C3 | GPIO6 | GPIO7 |肖D4、D5 |
| ESP32-C6 | GPIO22 | GPIO23 |肖D4、D5 |

VCC 连接至 3V3，GND 连接至 GND。常见的四引脚模块（GND、VCC、SCL、SDA）在SCL和SDA上带有自己的3.3V稳压器和4.7k上拉电阻；其地址电阻选择0x3C（丝印
0x78) 或 0x3D (0x7A)。其面板将段 127 映射到第 1 列，将 COM0 映射到第 63 行，因此固件设置段重新映射 (`A1`)、反向 COM 扫描 (`C8`) 和替代 COM 引脚 (`DA 12`)。

如果没有主机命令，屏幕会显示无线收发设备的状态：空闲、加入或托管（在 Poke Ball 周围响铃）和链接，其中游戏机和 Poke Ball 之间的电缆每帧携带一位数字，无线收发设备在每个方向上计数，每 70 毫秒最多一位，总数如下。

OLED 像素会随着点亮时间的推移而老化，因此屏幕限制了静态图像的停留时间。当无线收发设备正在加入、加入、主持或嗅探时，当播放交易或赠送动画时，以及在最后一个动画、显示命令、HELLO 或 BOOT 按下后的 60 秒内，它处于全亮度状态。之后，它通过 2+2 时钟预充电变暗至对比 1 (`81 01 D9 22`)，并在 600 秒后关闭 (`AE`)；面板保留其 RAM。这些事件中的下一个将在下一个帧上点亮它，该帧是在
`AF`。空闲场景每 60 秒围绕 2x2 正方形移动 2 个像素。 `scene_draw` 返回亮度； `tests/test_esp32_screen.py` 保存时序。

四引脚 0.96 英寸模块上的对比度、预充电和 VCOMH 设置，通过 INIT 的肉眼判断
`81 CF D9 F1 DB 40`：

|设置 |见过|
|---|---|
|对比 `80` |没有变化|
|对比 `40`、`20` |每一步调光|
|对比 `10` 至 `01` |没有进一步的改变，可读 |
|对比 `00` |黑色|
|对比`01`，预充电`22` |再次调光，可读，稳定 |
|对比`01`，预充电`11` |闪烁；与 VCOMH `20` 或 `00`，不可读 |
|对比`01`、VCOMH `00` |看起来正常、稳定|

DISPLAY（`0x0E`）携带一项操作：

|操作|布局|
|---|---|
| `0` 显示 | u8显示，u16保持s（0：直到下一个显示），标题，NUL，行，NUL；每个文本最多 21 个 ASCII 字符 |
| `1` 雪碧 | u8 插槽（0 个我们的，1 个他们的，2 个礼物），u8 宽度 <= 64，u8 高度 <= 64，`(width + 7) / 8` 字节行，MSB 在前；宽度 0 清空插槽 |

|显示|编号 |绘制|
|---|---|---|
|汽车 | 0 |收音机的状态 |
| 交换 | 1 |插槽 0 位于右半部分，“产品”，左边的线，下面的电缆 |
|交易| 2 |插槽 0 闪烁并返回其球，球离开（2.1 秒），数据包交叉直至保持（至少 3.1 秒），球到达并打开（1.6 秒），然后插槽 1 发出“已接收”消息，线路持续 10 秒：棋盘一侧，因为“提供”是 |
|礼物| 3 | a 神奇反馈 持有槽2（空时为礼盒），其旁边的线 |
|有天赋| 4 |卡片离开右侧，然后“已交付！” |
|到达 | 5 |没有场景：仍在等待的交易节目现在开始了 |

在交易或礼品表演结束之前发送的交换或礼品表演等待其结束。当收音机在激活后返回空闲状态时，交换或礼物展示结束；广播开始前发送的一封会保留下来。 HELLO 将屏幕重置为带有空插槽的无线收发设备状态。

`pokeldn.app.screen` 是启动器一侧：`offer`、`received`、`arrived`、`gift` 和 `delivered` 立即返回并在一个线程上按顺序运行。每个发射器在游戏机的交换动画之前的交换的最后一步调用 `received`，并保留从该步骤到收到的宝可梦出现在游戏机上的标题测量时间，少于 2.5 秒，因此球以游戏机的开头：

|标题 |来自|在游戏机上收到宝可梦|动画后的第一条消息|
|---|---|---|---|
| 火红／叶绿 | START_TRADE | 22.7 秒 | READY_FINISH_TRADE ([火红链接](frlg_link.md)) |
|我们走吧|步骤 `0e` | 15.3 秒 |类型 4 发票 ([Let's Go session](lgpe_session.md#the-trade-animation)) |
| 剑／盾 |最后的同步命令 40 | 15.0 秒 |无 ([剑交换](swsh_trade.md#the-trade-animation)) |
| BD/SP | `tradeState` 5 | 18.6 秒 |无 ([BDSP 交换](bdsp_trade.md#the-completed-trade)) |
| 传说阿尔宙斯 | `01 0e` | 28.5 秒 |盒子消息 `00 02` ([传说阿尔宙斯](pla.md#the-completed-trade)) |
| 朱／紫 | `8001010e` | 19.8 秒 |无 ([朱和紫](sv.md#the-trade)) |
| 传说 Z-A |第四步 | 26.2 秒 |下一个 `01 01` 预览 ([传说 Z-A](za.md#a-trade-with-a-retail-console)) |

每次都是在一个会话中手工标记的，最多可能会延迟 2 秒。当游戏机在动画结束后发送消息时，启动器会在那里调用 `arrived`。通过 PKHeX 助手记录其国家物种和名称；精灵是 PokeAPI 的火红／叶绿之一 (64x64)，最多为 386 种，之后为默认精灵，通过应用程序的精灵缓存及其下载设置。精灵变成每像素一位：

1.裁剪至其可见像素；大于 64（卡上为 40）时，它会按面积缩小，每个输出像素占据其框的较暗的三分之一。
2. 亮度超过截止值的地方点亮：可见像素最暗的八分之一处的亮度加6，钳位到20..60，因此轮廓很暗，而黑暗的宝可梦的身体保持点亮。
3. 暗，其中亮像素比其最亮的四个相邻像素低 40 以上或 0.72 以下：内线。

`tools/ldn/esp32_screen.py --port PORT` 在棋盘上进行交换和礼物，没有无线收发设备流量。
`tools/ldn/screen_preview.py OUT.gif` 为主机构建 `scene.c` 和 `screen.c` 并离线渲染脚本会话。
## 构建和闪烁

固件版本在 `firmware/esp32/version.txt` 中使用 `major.minor.patch`，由 ESP32、S3、C3 和 C6 共享。在构建版本之前，增量补丁用于修复，次要补丁用于兼容功能，主要补丁用于不兼容的更改。 ESP-IDF 将版本嵌入应用程序描述符中； INFO 将其报告为 `version=...`，Boards 在对主板的检查返回后显示它。无版本化版本显示 `version unknown`，并在串行协议匹配时保持可用。串口协议和桌面应用版本独立；当其电汇合同发生变化时，增加协议号。

ESP-IDF v6.1（标签 `v6.1`，提交 `fff9895c82d744c7237be8847347bdd1b07c6643`）构建所有四个目标。使用 `install.sh esp32,esp32s3,esp32c3,esp32c6` 安装其工具，然后激活 IDF 环境。

    cd firmware/esp32
    idf.py set-target esp32   # esp32s3, esp32c3 or esp32c6 for those chips
    idf.py build
    idf.py -p <port> flash
 控制台输出关闭（`CONFIG_ESP_CONSOLE_NONE`、`CONFIG_ESP_CONSOLE_SECONDARY_NONE`）。在经典 ESP32 上，UART0 是主机链路，因此固件自行分配 GPIO1 和 GPIO3 (`uart_set_pin`)。在 S3 上，固件在核心 1 上安装 USB 串行/JTAG 驱动程序； C3和C6将其安装在核心0上。

桌面应用程序在用于刷新的同一连接上使用 esptool 检测芯片。它在写入之前在芯片的闪存偏移量（ESP32：`0x1000`、S3、C3 和 C6：`0x0`）处验证合并映像的引导加载程序，包括自定义映像。当合并图像以填充开始时，esptool 5.4.0 的 `write_flash` 可以跳过其芯片检查。切勿从 USB 桥 ID 选择固件。 [桌面版本](gui.md) 涵盖了所有四个图像的打包。
### USB 主机链接

S3、C3 和 C6 通过 USB 串行/JTAG 使用相同的 COBS、CRC 和 CREDIT 协议。两个驱动环均为 16 KB。 IDF v6.1的`usb_serial_jtag_write_bytes`将整个帧入队或超时后返回零；作者等待 20 毫秒重试，并在 500 毫秒后没有进展地计算丢弃的消息。 `write_max_us` 包括此等待。读取器在 20 毫秒超时后获取可用字节。 UART 溢出和帧计数器在此路径上保持为零；它们不测量 USB 丢失情况。当 16 KB RX 环已满且不计数时，接收中断会丢弃 64 字节数据包（`usb_serial_jtag.c:144` 忽略 `xRingbufferSendFromISR` 的结果）。 CREDIT 窗口可防止环被填满；那里的损失仅显示为写入超过董事会最后一个信用的字节。
`POKELDN_ESP32_BAUD` 在所有目标上均被接受，并且仅更改经典 ESP32 的线路速率。
## 跑步

> 本节已随上游更新，以下内容暂保留英文。

`POKELDN_RADIO=esp32:<port>` puts every launcher's `ldn` calls on the board. `esp32:auto` takes the
only USB serial port present (`/dev/cu.usbserial-*`, `/dev/cu.SLAB_USBtoUART*`,
`/dev/cu.wchusbserial*`, `/dev/cu.usbmodem*`, `/dev/ttyUSB*`, `/dev/ttyACM*`; USB COM ports on Windows)
and refuses to choose between several, since opening a port can reset its board. The port is opened once
per process with DTR and RTS released; a CP2102 board on macOS resets on open regardless, so the host
retries HELLO for 5 s before switching to 921600. Windows opens a COM port exclusively: a second open
while any handle is held, in this process or another, fails with `PermissionError(13, 'Access is
denied.')`, so a board that never answers HELLO closes its port before the launcher retries.

On the board the launchers skip every nl80211 step: `--phy auto` resolves to `esp32`, no vif is
deleted, no `iw`, `ip`, `nmcli` or `sysctl` runs, and a joiner's `--mac` becomes the board station's
address. No root is needed on macOS. A scan skips 5 GHz channels (36 and up): the board is 2.4 GHz
only, so a console hosting on 5 GHz cannot be reached. The FRLG hosts inject no beacons; the board's
access point beacons itself.

`POKELDN_ESP32_TRACE=FILE` appends every serial message, one line each: Unix time, `>` (host) or `<`
(board), type and payload in hex.

| tool | what it does |
|---|---|
| `tools/ldn/esp32_first_contact.py` | first run against a new board: `--flash` writes the build with esptool, then HELLO, STATUS, an idle scan counting LDN action frames per channel and source, and with `--keys` the LDN library's scan, decrypting each network |
| `tools/ldn/esp32_sniff.py` | a second board as a sniffer (SNIFF) |
| `tests/test_esp32.py` | the LDN library's host and station on two simulated boards (`pokeldn.ldn.esp32_sim`), from scan to fragmented UDP through two userspace stacks |

A CH9102 or CH343 USB bridge enumerates as CDC ACM: `/dev/ttyACM0` on Linux, `/dev/cu.usbmodem*` on
macOS.

### 不解码 OFDM 的板

游戏机的广告是 HT MCS 3 ([Discovery](ldn.md#discovery))，因此无法解调 OFDM 的板会听到其 DSSS 信标，但不会听到任何广告：`esp32_first_contact.py` 在每个通道上计数 0 个 LDN 操作帧。两项检查可将其与固件或主机故障区分开来：

|检查 |工作板|不解码 OFDM 的板 |
|---|---|---|
| `tools/ldn/esp32_census.py` 靠近游戏机或繁忙的接入点 | `OFDM` 和 `HT` 属于好镜架 |好镜架全部为`DSSS`； OFDM 帧失败并显示 `rx_state` 65 |
|作为站加入接入点，接入点向其发送的单播帧的速率 | HT MCS 5 至 7（HT40 接入点）| DSSS 5.5 Mbit/s 时约为 97%，从未高于 OFDM 6 或 HT MCS 1 |

站关联和 ping 在这样的板上成功：接入点的速率自适应回落到 DSSS。通用 ESP32-WROOM-32 DevKit（ESP32-D0WD-V3 版本 3.1，CP2102）未通过 pokeldn 以外的固件的两项检查；具有相同芯片的WROOM-32E板通过了两者，听到了Sword的礼物网络并交付了一份神秘礼物（[问题1](https://github.com/Decryptu/pokeldn/issues/1)）。
## 董事会交易

ELEGOO 板（其无品牌模块上的 ESP32-D0WD-V3 版本 3.1、CP2102、macOS、921600 波特）可与零售 Switch 2 控制台进行交易：

|角色 |标题 |结果 |
|---|---|---|
|车站| 火红 | 交换；每路每秒 38 至 42 个“T”槽 |
|接入点| 火红、叶绿 | 交换和奇迹卡；下面是游戏机的协会 |
|车站| 朱 | 交换，一个座位上不止一个；下面 |
|接入点| 朱 | 交换：游戏机的类型 3 加入以类型 9 接受应答，密钥 `0x80` 打开，加入后 11.4 秒发送提议 |
|站、接入点| 传说 Z-A | 交换两个角色 |
|站、接入点|我们走吧| 交换两个角色 |
|接入点| 传说阿尔宙斯 | 通过四个主机阶段（3、6、11、14）进行交换 |
|车站|剑| 交换；延迟确认重新发送无序到达 ([Sword session](swsh_session.md)) |
|接入点|剑| 交换和神秘礼物|
|车站| 晶灿钻石 | 联合房间交换以节省费用。一个停下来但没有离开的客户会在房间里停留一站；游戏机拒绝相同的变量 id（结果 7），直到玩家重新进入房间或使用新的 id（[Pia 层](pia.md#the-version-9-connection-request)）|
|接入点| 晶灿钻石 | a 明亮珍珠 进入托管房间并交易至存档 ([托管](bdsp_session.md#hosting)) |

其他董事会及其交易：

|董事会|角色 |标题 |结果 |
|---|---|---|---|
|肖ESP32C3 |车站| 火红 | 交换，有效的 PK3 校验和；零丢失 ETH_TX、坏线框和 USB 重新同步 |
|肖ESP32C3 |接入点|剑| 通过打包的 macOS 应用进行交换，合法 PK8 |
| XIAO ESP32C6（陶瓷天线）|车站| 火红 | 交换，干净的游戏机出发|
| XIAO ESP32C6（陶瓷天线）|接入点|朱剑 | 交换，有效PK8记录，干净游戏机出发|
| ESP32-S3（Windows，[PR 2](https://github.com/Decryptu/pokeldn/pull/2) 中报告）|车站| 火红 | 交换 |

加入板卡接入点的火红游戏机列出网络（它接受零长度隐藏 SSID、速率顺序、功能 `0x0431` 和 WMM 元素），验证打开并在验证后 24 毫秒发送一个关联请求：功能 `0x0431`，侦听间隔 10，SSID 为 32 个十六进制字符，速率 `02 04 0b 16 0c 12 18 24`和 `30 48 60 6c`、功率能力 `00 14`、RSN 能力 `0x0000`、WMM 信息元素、供应商元素 `00 22 aa 10 01 02`。其LDN认证请求在`STA_JOINED`之后40毫秒到达`RX_ETH`。其首次广播需要固件转发（[A站广播](ldn.md#a-stations-broadcasts)）。

朱作为加入方：董事会在第一次关联尝试中就座，从 `STA_JOIN` 到 0.35 秒
`LINK`;会话加入在 0.93 秒内得到应答，并且在入座后 5.8 至 7.7 秒内发布公告。游戏机首次突发 46 条记录（约 50 KB），板到主机的速度达到 92 KB/s。
### 加入

`STA_JOIN` 进行一次关联尝试：快速扫描给定通道和 BSSID，然后打开身份验证和关联。零售 Sword 的匹配网络在 10 次板连接中有 2 次尝试失败，`LINK` 因 `0xc9` 原因而关闭（未找到接入点，`STA_JOIN` 后 2.4 秒）或
`0x2`（身份验证过期，1.3 秒后），而董事会继续在该频道上听到其广告；同一搜索上有一个新的 `STA_JOIN` 关联。成功连接报告 `LINK` 在 `STA_JOIN` 后增加 0.23 到 0.34 秒。主机在加入超时时间内发送 `STA_JOIN` 最多 3 次 (`pokeldn.ldn.esp32_wlan.JOIN_ATTEMPTS`)。为什么游戏机的网络会错过给定的尝试尚不清楚。
## 未解决

- softAP 协商 WMM，而交换机主机则不协商；有或没有它的交易都完整。   `POKELDN_ESP32_AP_FLAGS=2` (`AP_FLAG_NO_QOS`) 关联后清除站点的 QoS 标志：然后板发送明文数据，而游戏机继续发送 QoS 数据。 Z-A、传说阿尔宙斯、Let's Go 和叶绿与之交易。两次嗅探 Z-A 交易重试了 11.9% 的主板帧和 11.5% 的游戏机帧（没有 QoS 数据），以及 1.3% 的游戏机帧（有 QoS 数据）；没有什么可以将差异归因于设置。
- ESP32-S3 吞吐量以及主机角色中的 S3 交易或火红以外的标题在本地主板上无法测量。
- 加入到主板接入点的朱游戏机已确认该公告，并且从未发送其端口 2 连接。原因不明。
- 接入点接收路径中的哪些内容会丢失站点 OFDM 第一个副本的 1% 到 22%，以及火红保持期间的 ACK 尚不清楚；排除的设置在[两块板上的接收未命中](#receive-misses-on-two-boards)中。
- Espressif ESP32-WROOM-32E 模块作为接入点是否比 ELEGOO 板的无品牌模块丢失的帧更少尚未进行测量。 Easyworld 报道称，经典的 ESP32 必定是 ESP32-WROOM-32E，而较旧的 ESP32-WROOM-32 无法可靠交换；一个 WROOM-32 DevKit 根本无法解码 OFDM（[一块无法解码 OFDM 的板](#a-board-that-decodes-no-ofdm)）。这是模块还是那块板尚不清楚。乐鑫的 ESP32-DevKitC-32E 搭载 WROOM-32E 模块；它的盾牌上写着 ESP32-WROOM-32E 和 Espressif 徽标。
