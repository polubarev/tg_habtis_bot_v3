## 1. Implementation
- [x] Add localized loading and timeout message templates.
- [x] Define a timeout threshold for long-running operations.
- [x] Send a loading message within 1–2 seconds for user-initiated operations.
- [x] Enforce timeout on external operations and return a timeout message on expiry.
- [x] Ensure success paths still send confirmation and error paths never hang.

## 2. Tests
- [ ] Add handler tests to verify loading and timeout messages are sent.
