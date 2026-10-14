# Orders export: data dictionary (rev 2026-05)

- `order_id`: warehouse order id.
- `promised_at`: promised delivery time, UTC (`Z`).
- `ship_confirmed_at`: time the shipment was confirmed. This export is the system of record for ship time.
  The event logs are a nightly mirror of it.
- `status`: `shipped`, `cancelled` or `pending`.
