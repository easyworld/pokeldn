/* The host link over Bluetooth LE, for a host with no USB serial (an iPhone). Built only with
   POKELDN_BLE=1; carries the same COBS byte stream as the cable. docs/hardware_esp32.md, Bluetooth. */
#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#if POKELDN_BLE
void ble_start(void);
/* True while a central is subscribed to the TX characteristic: the wire then reads and writes here. */
bool ble_linked(void);
/* Host bytes written to RX, waiting up to `ticks`. */
int ble_read(uint8_t *out, size_t size, uint32_t ticks);
/* Notifies `n` bytes in MTU-sized pieces; false when the link went away or stalled 500 ms. */
bool ble_write(const uint8_t *p, size_t n);
/* The connection interval the central granted, in microseconds; 0 before any update. */
uint32_t ble_interval_us(void);
#else
static inline bool ble_linked(void) { return false; }
#endif
