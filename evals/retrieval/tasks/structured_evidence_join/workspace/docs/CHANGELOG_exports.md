# Orders export changelog

## 2026-09-29

- `promised_at` now carries the storefront offset (`+02:00` for the EU site). It is no longer UTC.
- `ship_confirmed_at` is now a rollup refreshed hourly from the event logs. The event logs are the system of record
  for shipping.
- Shipment corrections (`shipment_corrected` events) are applied in the event logs. The export does not apply them
  until the next rollup.
- Dictionary rev 2026-05 is out of date for these fields.
