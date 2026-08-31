# Current task — PHASE 26B awaiting architect review

## Status

PHASE 26B — Source Navigation, Attachments & Client-assisted File Intake: **implementation complete (closure corrective applied), awaiting architect review**

Branch: `review/phase-26b-source-file-intake`

Do **not** merge, deploy, or start PHASE 26C until review accepts.

## PHASE 26B delivered

- Client-assisted mechanical extraction (`.txt`, `.md`, `.csv`) with bounded representations
- Metadata-only registration for unsupported formats
- `POST /local/files/client-intake` typed contract
- `GET /objects/{id}/open-target` source navigation resolver
- Gmail / Yandex Mail attachment objects + `email --contains--> attachment`
- Flutter: device identity, file/folder picker, Linux drag-and-drop, source actions, email attachments UI
- Assistant/Capture context via object IDs (no raw file upload by default)

## Known limitations (documented)

- Android persistent reopen of picked files: best-effort; SAF layer deferred
- Yandex Mail: no exact per-message browser deep link from IMAP UID; mailbox-level fallback

## Next subphase (after 26B acceptance)

PHASE 26C — Graph Topology & Search Ordering
