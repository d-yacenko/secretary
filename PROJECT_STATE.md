# Project state

## Current phase

PHASE 16 — Yandex Mail (corrective applied; awaiting user review)

PHASE 17 — Yandex Calendar (not started; do not start)

## Global invariants (PHASE 14.5+)

See `DECISIONS.md`. PHASE 19.5 (auth + connections) required before PHASE 20 Flutter.

## Working components

- PHASE 00–15: (prior phases)
- PHASE 16: Yandex Mail IMAP sync
  - `yandex_mail_accounts` + migration `0011`
  - MVP auth: encrypted **Mail app password** per user (not main password; OAuth in 19.5)
  - `POST /connectors/yandex/mail/connect`, `POST /connectors/yandex/mail/sync`
  - `objects(kind=email, provider=yandex_mail)` — same model as Gmail
  - UIDVALIDITY from IMAP response code (not SELECT message count)
  - Initial: bounded SINCE backfill, newest N per batch
  - Incremental (same UIDVALIDITY): UID > checkpoint, oldest N per batch
  - UIDVALIDITY change → new bounded backfill
  - DB snapshot before IMAP; no SQL tx during network I/O
  - RFC2047 header decoding; skip attachment parts for body
  - Offline tests: `tests/test_yandex_mail.py`

## Not done

- Live Yandex IMAP smoke (deferred until review acceptance)
- Deploy of PHASE 16 corrective
- PHASE 17+

## Next phase

PHASE 17 — Yandex Calendar (do not start without user go-ahead).
