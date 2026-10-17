#if POKELDN_BLE
#include "ble.h"

#include <stdatomic.h>
#include <string.h>

#include "esp_bt.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/stream_buffer.h"
#include "freertos/task.h"
#include "host/ble_hs.h"
#include "nimble/nimble_port.h"
#include "nimble/nimble_port_freertos.h"
#include "services/gap/ble_svc_gap.h"
#include "services/gatt/ble_svc_gatt.h"

/* 7a1e0101-5d2c-4c3e-9f4b-504f4b454c44 service, ...0102 RX (host writes), ...0103 TX (notify).
   pokeldn/ldn/esp32_ble.py carries the same UUIDs. */
#define UUID(b) BLE_UUID128_INIT(0x44, 0x4c, 0x45, 0x4b, 0x4f, 0x50, 0x4b, 0x9f, 0x3e, 0x4c, 0x2c, \
                                 0x5d, b, 0x01, 0x1e, 0x7a)
static const ble_uuid128_t svc_uuid = UUID(0x01), rx_uuid = UUID(0x02), tx_uuid = UUID(0x03);

static StreamBufferHandle_t s_rx;
static uint8_t s_own_addr_type;
static uint16_t s_tx_handle;
static atomic_int s_conn = -1;
static atomic_bool s_subscribed;
static atomic_uint s_mtu = 23;
static atomic_uint s_interval_us;   /* the connection interval the central granted; STATUS ble_itvl_us */

static int rx_access(uint16_t conn, uint16_t attr, struct ble_gatt_access_ctxt *ctxt, void *arg)
{
    if (ctxt->op != BLE_GATT_ACCESS_OP_WRITE_CHR) return BLE_ATT_ERR_UNLIKELY;
    for (const struct os_mbuf *om = ctxt->om; om; om = SLIST_NEXT(om, om_next)) {
        /* The host's credit window keeps it under half this buffer; a short send is a lost byte the
           CRC then catches. */
        xStreamBufferSend(s_rx, om->om_data, om->om_len, 0);
    }
    return 0;
}

static int tx_access(uint16_t conn, uint16_t attr, struct ble_gatt_access_ctxt *ctxt, void *arg)
{
    return BLE_ATT_ERR_READ_NOT_PERMITTED;
}

static const struct ble_gatt_svc_def services[] = {
    {
        .type = BLE_GATT_SVC_TYPE_PRIMARY,
        .uuid = &svc_uuid.u,
        .characteristics = (struct ble_gatt_chr_def[]){
            {.uuid = &rx_uuid.u, .access_cb = rx_access,
             .flags = BLE_GATT_CHR_F_WRITE | BLE_GATT_CHR_F_WRITE_NO_RSP},
            {.uuid = &tx_uuid.u, .access_cb = tx_access, .val_handle = &s_tx_handle,
             .flags = BLE_GATT_CHR_F_NOTIFY},
            {0},
        },
    },
    {0},
};

static void advertise(void);

/* Apple's accessory rules allow min = max = 15 ms as the one exception to max >= min + 15 ms;
   every link-loop message waits for a connection event. */
static void ask_fast_interval(uint16_t conn)
{
    struct ble_gap_upd_params p = {.itvl_min = 12, .itvl_max = 12, .latency = 0, .supervision_timeout = 400};
    ble_gap_update_params(conn, &p);
}

static int gap_event(struct ble_gap_event *event, void *arg)
{
    switch (event->type) {
    case BLE_GAP_EVENT_CONNECT:
        if (event->connect.status != 0) { advertise(); break; }
        atomic_store(&s_conn, event->connect.conn_handle);
        ask_fast_interval(event->connect.conn_handle);
        /* 251-byte link-layer packets instead of 27 (data length extension). */
        ble_gap_set_data_len(event->connect.conn_handle, 251, 2120);
        ble_gap_set_prefered_le_phy(event->connect.conn_handle, BLE_GAP_LE_PHY_2M_MASK,
                                    BLE_GAP_LE_PHY_2M_MASK, BLE_GAP_LE_PHY_CODED_ANY);
        break;
    case BLE_GAP_EVENT_DISCONNECT:
        atomic_store(&s_subscribed, false);
        atomic_store(&s_conn, -1);
        atomic_store(&s_mtu, 23);
        xStreamBufferReset(s_rx);
        advertise();
        break;
    case BLE_GAP_EVENT_SUBSCRIBE:
        if (event->subscribe.attr_handle == s_tx_handle) {
            atomic_store(&s_subscribed, event->subscribe.cur_notify != 0);
            /* A request at connect is refused while the central still discovers services: ask again. */
            if (event->subscribe.cur_notify) ask_fast_interval(event->subscribe.conn_handle);
        }
        break;
    case BLE_GAP_EVENT_CONN_UPDATE: {
        struct ble_gap_conn_desc desc;
        if (ble_gap_conn_find(event->conn_update.conn_handle, &desc) == 0)
            atomic_store(&s_interval_us, desc.conn_itvl * 1250u);
        break;
    }
    case BLE_GAP_EVENT_MTU:
        atomic_store(&s_mtu, event->mtu.value);
        break;
    case BLE_GAP_EVENT_ADV_COMPLETE:
        advertise();
        break;
    }
    return 0;
}

static void advertise(void)
{
    struct ble_hs_adv_fields fields = {0};
    const char *name = ble_svc_gap_device_name();
    fields.flags = BLE_HS_ADV_F_DISC_GEN | BLE_HS_ADV_F_BREDR_UNSUP;
    fields.name = (uint8_t *)name;
    fields.name_len = strlen(name);
    fields.name_is_complete = 1;
    if (ble_gap_adv_set_fields(&fields) != 0) return;
    struct ble_gap_adv_params params = {.conn_mode = BLE_GAP_CONN_MODE_UND,
                                        .disc_mode = BLE_GAP_DISC_MODE_GEN};
    ble_gap_adv_start(s_own_addr_type, NULL, BLE_HS_FOREVER, &params, gap_event, NULL);
}

static void on_sync(void)
{
    if (ble_hs_id_infer_auto(0, &s_own_addr_type) == 0) advertise();
}

static void host_task(void *param)
{
    nimble_port_run();
    nimble_port_freertos_deinit();
}

void ble_start(void)
{
    /* FLOW_WINDOW (8 KB) plus one frame: the host never has more in flight. */
    s_rx = xStreamBufferCreate(10240, 1);
#if CONFIG_IDF_TARGET_ESP32
    esp_bt_controller_mem_release(ESP_BT_MODE_CLASSIC_BT);
#endif
    ESP_ERROR_CHECK(nimble_port_init());
    ble_hs_cfg.sync_cb = on_sync;
    ble_svc_gap_init();
    ble_svc_gatt_init();
    ble_gatts_count_cfg(services);
    ble_gatts_add_svcs(services);
    ble_att_set_preferred_mtu(247);
    ble_svc_gap_device_name_set("POKELDN-RADIO");
    nimble_port_freertos_init(host_task);
}

bool ble_linked(void) { return atomic_load(&s_subscribed); }

uint32_t ble_interval_us(void) { return atomic_load(&s_interval_us); }

int ble_read(uint8_t *out, size_t size, uint32_t ticks)
{
    return xStreamBufferReceive(s_rx, out, size, ticks);
}

bool ble_write(const uint8_t *p, size_t n)
{
    const int64_t started = esp_timer_get_time();
    while (n) {
        const int conn = atomic_load(&s_conn);
        if (conn < 0 || !atomic_load(&s_subscribed)) return false;
        const size_t piece = n < atomic_load(&s_mtu) - 3 ? n : atomic_load(&s_mtu) - 3;
        struct os_mbuf *om = ble_hs_mbuf_from_flat(p, piece);
        /* NimBLE refuses a notification when its mbuf pool is out (BLE_HS_ENOMEM): wait a tick. */
        const int rc = om ? ble_gatts_notify_custom(conn, s_tx_handle, om) : -1;
        if (rc == 0) {
            p += piece;
            n -= piece;
            continue;
        }
        if (esp_timer_get_time() - started > 500000) return false;
        vTaskDelay(1);
    }
    return true;
}
#endif
