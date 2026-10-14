# Status service contract

Version 1.1 (current). Earlier sections are kept for history and are marked superseded.

## Binding

- Host: `127.0.0.1`
- Port: `18923`
- Protocol: HTTP/1.1

## Endpoints

### GET /health

Returns HTTP 200 with:

- `Content-Type: application/json`
- Body: `{"status": "ok", "version": "1.0"}`

### POST /echo

Reads the raw request body as a UTF-8 string and returns HTTP 200 with:

- `Content-Type: application/json`
- Body: `{"echo": "<request_body>"}`, where `<request_body>` is the exact string received.

### Any other GET path

Returns HTTP 404.

## Lifecycle

- The service binds within 5 seconds of start.
- It keeps running and answering for at least 2 seconds of continuous operation.
- On SIGTERM or SIGINT it shuts down and exits with status 0.
- Standard library only.

## Output

The implementation is `out/service_impl.py`, started as `python3 out/service_impl.py` from the workspace root.

## Changelog

- 1.1: `/echo` must return `application/json`. In 1.0 it returned `text/plain`.
- 1.0: first contract with the endpoints above.

## Superseded (0.9, do not implement)

- Port `18920`.
- `/echo` body key `echoed` instead of `echo`.
- Clean exit on SIGTERM was optional.
