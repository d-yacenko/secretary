# Personal Secretary OS — build playbook for a small-context coding agent

> Purpose: build a minimal personal task/context system that synchronizes mail, calendars, files and other sources; stores a typed graph; uses an LLM secretary to correlate events and propose actions; exposes the core through REST + MCP; and provides one Flutter client for Android and Linux desktop.
>
> This file is intentionally organized as short execution stages. Do **one stage at a time**. Do not load or reason about the whole plan on every step.

---

# 0. Agent operating rules

## 0.1 Main rule

Build the **smallest working system** that satisfies the current stage.

Do not add:
- microservices;
- Kafka/RabbitMQ;
- Redis/Celery;
- Neo4j;
- Qdrant;
- Kubernetes;
- event sourcing;
- CQRS;
- multiple LLM agents;
- plugin frameworks;
- elaborate abstractions without an immediate use.

Use:
- one repository;
- one FastAPI backend;
- one PostgreSQL database with pgvector;
- one simple worker process using the same PostgreSQL database;
- one Flutter codebase for Android and Linux;
- one Secretary LLM service;
- one MCP server exposing the same domain services as the REST API.

## 0.2 Context discipline

The coding agent has a limited context window.

At the start of every work cycle read only:

1. `PROJECT_STATE.md`
2. `CURRENT_TASK.md`
3. files directly needed for the current task

Do **not** read this whole playbook into active context.

For bootstrap, read only:
- sections `0` through `4`;
- the current `PHASE NN` section.

When moving to another phase, locate that phase heading in this file and read only that section until the next `# PHASE` heading. Copy its compact instructions into `CURRENT_TASK.md`.

At the end of every stage:
1. run tests;
2. fix failures;
3. update `PROJECT_STATE.md`;
4. replace `CURRENT_TASK.md` with the next stage;
5. commit working code;
6. continue automatically unless blocked by a secret, account credential, or irreversible external action.

Keep `PROJECT_STATE.md` below about 150 lines.

Keep `CURRENT_TASK.md` below about 80 lines.

If a design decision matters later, append one short entry to `DECISIONS.md`.

## 0.3 Failure rule

If something fails:
1. inspect the exact error;
2. make the smallest fix;
3. rerun the failed check;
4. do not redesign unrelated code.

If an external API cannot be tested because credentials are missing:
- finish the implementation behind an interface;
- add a deterministic fake;
- test the fake;
- document the missing credential;
- continue.

## 0.4 Definition of done for every stage

A stage is done only when:
- code runs;
- tests for that stage pass;
- no obvious TODO is required for that stage;
- `PROJECT_STATE.md` is updated;
- changes are committed.

Use small commits such as:

```text
phase 03: add graph CRUD
phase 04: add vector search
```

---

# 1. Product definition

Build a **Personal Secretary OS**.

The system must:

- synchronize external sources such as email, calendar and files;
- represent tasks, projects, people, messages, events and documents as objects;
- store typed relations between objects;
- preserve provenance to the original source;
- store embeddings for semantic retrieval;
- create compact representations for large resources;
- build a task-specific context pack;
- use an LLM to detect relevance, commitments, deadlines and missing events;
- create notifications and proposed actions;
- let the user accept, edit or ignore proposals;
- expose graph/task/context operations through REST;
- expose the same important operations through MCP;
- provide Inbox, Today, Search, Graph and Assistant screens;
- support text and push-to-talk interaction;
- run the same Flutter UI on Android and Linux desktop.

The system is **single-user first**.

Do not build multi-tenancy.

---

# 2. Minimal architecture

```text
External sources
    |
    v
Connectors
    |
    v
PostgreSQL + pgvector
    |
    +--> Graph services
    +--> Search
    +--> Resource representations
    +--> Context resolver
    +--> Job queue
    |
    v
Secretary LLM
    |
    +--> proposals
    +--> notifications
    +--> internal actions
    |
    +--> REST API
    +--> MCP
    |
    v
Flutter Android + Linux
```

There is only one source of truth: PostgreSQL.

External systems remain authoritative for their native objects, but the local database stores normalized copies and references.

---

# 3. Technology choices

Backend:
- Python 3.12+
- FastAPI
- Pydantic
- SQLAlchemy 2
- Alembic
- psycopg
- PostgreSQL
- pgvector
- `httpx`
- `openai`
- `pytest`
- `ruff`

Worker:
- same Python package as backend;
- a `jobs` table in PostgreSQL;
- worker claims jobs with `FOR UPDATE SKIP LOCKED`;
- no Redis in v1.

MCP:
- official Python MCP SDK;
- Streamable HTTP for remote use;
- expose a small tool set only.

Client:
- Flutter stable;
- one codebase;
- Android + Linux first;
- use `InteractiveViewer` + `CustomPainter` for the first graph view;
- do not add a complex graph editor library until required.

Deployment:
- Docker Compose;
- PostgreSQL container;
- API container;
- worker container;
- Caddy or an equivalent simple HTTPS reverse proxy.

Use environment variables for model IDs and external credentials.
Do not hard-code a particular current LLM model.

Recommended embedding default:
- `text-embedding-3-small`;
- keep the embedding model configurable.

---

# 4. Repository layout

Create:

```text
personal-secretary/
  README.md
  AGENTS.md
  PROJECT_STATE.md
  CURRENT_TASK.md
  DECISIONS.md
  .env.example
  .gitignore

  backend/
    pyproject.toml
    alembic.ini
    app/
      api/
      core/
      db/
      domain/
      services/
      connectors/
      llm/
      mcp/
      worker/
    tests/

  client/
    pubspec.yaml
    lib/
    test/

  infra/
    compose.yaml
    Caddyfile

  docs/
    architecture.md
    api.md
```

Keep packages shallow.

Do not create a directory for every class.

---

# PHASE 00 — bootstrap the repository

## Goal

Create the repo skeleton and the agent memory files.

## Do

1. Initialize Git.
2. Create the layout above.
3. Put a short product description in `README.md`.
4. Create `PROJECT_STATE.md` with:
   - current phase;
   - working components;
   - known blockers;
   - next phase.
5. Create `DECISIONS.md`.
6. Create `CURRENT_TASK.md` containing PHASE 01 only.
7. Add common Python, Flutter, IDE and secret files to `.gitignore`.

## Accept

- repo is clean;
- files exist;
- Git commit succeeds.

---

# PHASE 01 — local infrastructure

## Goal

Run PostgreSQL with pgvector and an empty FastAPI service.

## Do

1. Create Docker Compose with:
   - `db`;
   - `api`;
   - `worker`.
2. Enable pgvector in the database.
3. Add `/health`.
4. Add database connection settings.
5. Add Alembic.
6. Worker may initially only log that it is alive.
7. Add `.env.example`.

## Accept

```text
docker compose up
GET /health -> 200
database connection works
pytest passes
```

Do not add Redis.

---

# PHASE 02 — core database model

## Goal

Create the smallest useful graph schema.

## Create table `objects`

Required fields:

```text
id UUID PK
kind TEXT
title TEXT
body TEXT NULL
provider TEXT NULL
external_id TEXT NULL
canonical_uri TEXT NULL
status TEXT NULL
start_at TIMESTAMPTZ NULL
due_at TIMESTAMPTZ NULL
metadata JSONB
origin TEXT
confidence REAL NULL
embedding VECTOR NULL
created_at
updated_at
```

Typical `kind` values:

```text
task
project
person
organization
email
calendar_event
file
document
dataset
web_page
note
goal
course
```

Do not create separate tables for every kind.

## Create table `edges`

```text
id UUID PK
source_id UUID
target_id UUID
type TEXT
origin TEXT
confidence REAL NULL
state TEXT
metadata JSONB
created_at
updated_at
```

Typical edge types:

```text
parent_of
depends_on
blocks
related_to
mentioned_in
scheduled_for
assigned_to
produces
references
```

Typical edge state:

```text
observed
proposed
confirmed
rejected
```

## Constraints

Add useful uniqueness for external objects:

```text
(provider, kind, external_id)
```

when these values are non-null.

Add indexes for:
- `kind`;
- `status`;
- `due_at`;
- edge source;
- edge target;
- edge type.

## Accept

Tests create:
- project;
- task;
- email;
- `task related_to email`;
- `task parent_of task`.

---

# PHASE 03 — graph CRUD API

## Goal

Make the graph usable without any LLM.

## Add REST endpoints

Minimum:

```text
POST   /objects
GET    /objects/{id}
PATCH  /objects/{id}
DELETE /objects/{id}

POST   /edges
DELETE /edges/{id}

GET /objects/{id}/neighbors
GET /objects/{id}/context
```

Deletion must be safe:
- default to soft delete if simple;
- otherwise reject deletion when uncertain.

## Add service layer

API handlers call domain services.
Do not put SQL directly in route handlers.

## Accept

Integration test creates and links objects through HTTP.

---

# PHASE 04 — views and map persistence

## Goal

Allow the same object to appear in several maps.

## Create `views`

```text
id
name
view_type
root_object_id NULL
settings JSONB
created_at
updated_at
```

`view_type`:

```text
tree
dependency
timeline
context
freeform
```

## Create `view_items`

```text
view_id
object_id NULL
visual_id NULL
x
y
width
height
collapsed
settings JSONB
```

A visual-only annotation may have no `object_id`.

Important rule:

**coordinates belong to the view, not to the object.**

## Accept

One task can appear with different coordinates in two views.

---

# PHASE 05 — vector search

## Goal

Add semantic retrieval without a second database.

## Do

1. Add embedding service.
2. Default embedding model comes from env.
3. Embed searchable object text:
   - title;
   - body;
   - useful metadata.
4. Store embeddings in pgvector.
5. Add semantic search service.
6. Add lexical fallback using PostgreSQL text search or `ILIKE`.
7. Combine exact filters + semantic ranking.

## Endpoint

```text
GET /search?q=...
```

Optional filters:

```text
kind
provider
project_id
limit
```

## Rule

Vector similarity is a candidate generator, not proof of a relation.

## Accept

A semantically similar query finds a test object with different wording.

---

# PHASE 06 — resource representations

## Goal

Handle tiny files and huge documents/datasets without placing everything in LLM context.

## Create `representations`

```text
id
object_id
kind
part_index NULL
text NULL
metadata JSONB
embedding VECTOR NULL
created_at
```

Representation kinds:

```text
full
summary
chunk
sample
schema
statistics
```

## Policy

For a small resource:
- store/use `full`.

For a medium text resource:
- keep source reference;
- extract text;
- create chunks;
- create summary.

For a large document:
- summary;
- embeddings over chunks;
- retrieve only relevant chunks.

For a dataset:
- never serialize the entire dataset into an LLM prompt;
- store URI/path;
- schema;
- row/column counts when cheap;
- basic statistics when cheap;
- representative sample;
- provide query/sample tools.

## First supported files

Keep scope small:

```text
.txt
.md
.pdf
.docx
.csv
.parquet
```

Use straightforward libraries.
Do not build a universal document engine.

## Accept

Tests demonstrate:
- small text -> `full`;
- long text -> chunks;
- CSV -> schema + sample;
- original resource URI remains available.

---

# PHASE 07 — context resolver

## Goal

Build a compact context pack for one task or question.

## Implement

```python
build_context(
    object_id=None,
    query=None,
    max_chars=...
)
```

Candidate sources:

1. target object;
2. direct graph neighbors;
3. parent project;
4. blockers/dependencies;
5. recent related source objects;
6. semantic matches;
7. useful resource representations.

## Ranking preference

Prefer:
1. explicit confirmed edges;
2. direct source references;
3. recent objects;
4. semantic matches.

## Context item must contain

```text
object_id
kind
title
short content/representation
why included
canonical_uri if available
```

## Hard rule

Never send an entire large dataset or document just because it is related.

## Accept

A task linked to a long document receives:
- task;
- relation;
- document summary;
- top relevant chunks;
- document reference.

---

# PHASE 08 — provenance and inference states

## Goal

Never confuse source facts with LLM guesses.

## Use states

For agent-created facts/relations:

```text
observed
proposed
confirmed
rejected
```

Use `origin`:

```text
source
user
agent
system
```

Store confidence for inferred items.

## Example

Email text says:
`Let's meet tomorrow at 13:30`.

Store:
- email = observed source;
- possible meeting relation = proposed;
- possible calendar event = proposed;
- after user approval = confirmed;
- after external API call = store external ID and execution audit.

## Accept

Every proposal can answer:
- what source caused it;
- what was inferred;
- confidence;
- whether user approved it.

---

# PHASE 09 — Secretary LLM

## Goal

Add one LLM agent, not many.

## Create service

```text
SecretaryService
```

Use OpenAI Responses API.

The model ID must come from env.

Use structured outputs for analysis.

## Secretary responsibilities

Given a context pack, detect:

```text
importance
urgency
possible task
possible deadline
possible meeting
missing calendar event
possible relation to existing objects
suggested next action
```

## LLM must not

- write SQL;
- access the database directly;
- invent IDs;
- execute external write actions without policy approval;
- treat semantic similarity as certainty.

## Output

Return typed Pydantic structures.

## Accept

A fixture email:
`Let's meet tomorrow at 13:30 and send the budget before that.`

produces:
- possible meeting;
- possible task;
- deadline relation;
- confidence;
- source object ID.

---

# PHASE 10 — domain tools for the agent

## Goal

Give the Secretary a small stable tool vocabulary.

Implement functions:

```text
search_objects
get_object
get_context
create_task
update_task
link_objects
list_neighbors
search_calendar
propose_calendar_event
create_notification
```

Do not expose raw database tools.

Separate tool classes:

```text
read-only
internal-write
external-write
```

External write tools require approval by default.

## Accept

LLM can call tools in a test loop and cannot call arbitrary SQL.

---

# PHASE 11 — MCP server

## Goal

Expose the Personal Secretary core to external LLM clients.

Use the official Python MCP SDK.

Expose only these initial MCP tools:

```text
search
get_object
get_context
create_task
update_task
link_objects
get_today
list_notifications
```

Keep external write actions out of MCP until approval handling is complete.

Use the same domain services as REST.
Do not duplicate business logic.

Prefer Streamable HTTP for remote access.

Protect MCP with authentication.

## Accept

MCP Inspector or a small MCP client can:
1. search;
2. read context;
3. create a task;
4. link it to an existing object.

---

# PHASE 12 — PostgreSQL job queue

## Goal

Run synchronization and LLM analysis asynchronously without Redis.

## Create `jobs`

```text
id
type
payload JSONB
status
attempts
run_after
locked_at
last_error
created_at
updated_at
```

Worker algorithm:

1. open transaction;
2. select next due job using `FOR UPDATE SKIP LOCKED`;
3. mark running;
4. commit;
5. execute;
6. mark done or failed;
7. retry with bounded backoff.

Initial job types:

```text
sync_connector
embed_object
build_representations
analyze_object
send_notification
reconcile_connector
```

## Accept

Two worker processes cannot claim the same test job.

---

# PHASE 13 — notifications

## Goal

Turn important inferred events into actionable inbox items.

## Create `notifications`

```text
id
title
body
priority
status
source_object_id NULL
related_object_id NULL
proposal JSONB
created_at
read_at NULL
```

Priority:

```text
low
normal
high
urgent
```

Status:

```text
new
read
accepted
ignored
resolved
```

## Rule

Low-confidence suggestions should not interrupt the user.

## API

```text
GET  /notifications
POST /notifications/{id}/accept
POST /notifications/{id}/ignore
```

## Accept

A proposed missing meeting creates a notification with source provenance.

---

# PHASE 14 — Google OAuth and Gmail

## Goal

Synchronize Gmail into graph objects.

## Do

1. Implement Google OAuth web flow.
2. Store refresh/access tokens encrypted at rest.
3. Create `GoogleAccount`.
4. Initial full sync should be bounded:
   - recent messages first;
   - configurable history window.
5. Normalize each email into `objects(kind=email)`.
6. Preserve:
   - Gmail message ID;
   - thread ID;
   - sender;
   - recipients;
   - subject;
   - timestamp;
   - canonical link when possible.
7. Create/update `person` objects conservatively.
8. Queue embedding + analysis.

## Push

Support Gmail watch through Google Cloud Pub/Sub.

Important:
- renew Gmail watch regularly;
- use history IDs;
- include periodic reconciliation because notifications can be delayed or dropped.

## Accept

With credentials:
- new Gmail message appears as one object;
- repeated sync is idempotent;
- source ID is preserved.

Without credentials:
- fake connector passes equivalent tests.

---

# PHASE 15 — Google Calendar

## Goal

Synchronize Google Calendar and detect absent meetings.

## Do

1. Reuse Google OAuth account where possible.
2. Import calendar events as `calendar_event`.
3. Preserve external ID and calendar ID.
4. Add `search_calendar(start, end, text, people)`.
5. Support Calendar watch channels.
6. Re-fetch changed resources after a notification.
7. Periodically reconcile.

## Missing meeting flow

When the Secretary detects a possible meeting:
1. parse proposed date/time;
2. search calendar near that interval;
3. compare attendees/title/context;
4. if no likely match, create a proposal notification.

Do not create the event automatically in v1.

## Accept

Email fixture with a meeting + empty calendar creates a missing-event proposal.

---

# PHASE 16 — Yandex Mail

## Goal

Synchronize Yandex Mail with minimal provider-specific code.

Use IMAP.

Prefer OAuth when available.
Allow app-password configuration for development if needed.

## Do

1. Add `YandexMailConnector`.
2. Store UID + UIDVALIDITY for safe incremental sync.
3. Normalize messages into the same `email` object shape used by Gmail.
4. Preserve original provider metadata in JSONB.
5. Queue embeddings and analysis.
6. Implement periodic sync first.
7. Add IMAP IDLE only if it is easy and reliable.

## Rule

Do not create a second mail domain model.

Gmail and Yandex must feed the same normalized object type.

## Accept

Fake IMAP test and, when credentials exist, real mailbox smoke test pass.

---

# PHASE 17 — Yandex Calendar

## Goal

Synchronize Yandex Calendar using CalDAV.

## Do

1. Add `YandexCalendarConnector`.
2. Discover configured calendars.
3. Import events to the same `calendar_event` object model.
4. Keep CalDAV URL/UID metadata.
5. Implement incremental or bounded periodic reconciliation.
6. Add event search using local normalized objects.

## Accept

Google and Yandex calendar events appear in the same search endpoint.

---

# PHASE 18 — files, cloud resources and web links

## Goal

Allow tasks to reference documents without copying all content into context.

## Generic resource registration

Add endpoint:

```text
POST /resources/register
```

Input:

```text
kind
title
canonical_uri
optional local path metadata
optional uploaded file
optional text
metadata
```

## Google Drive / Yandex Disk

Keep the first implementation minimal:
- store provider object ID;
- name;
- MIME type;
- size;
- modified time;
- canonical link;
- fetch content only when needed and allowed.

Do not mirror entire drives.

## Web links

Allow creation of `web_page` objects from a URL.
Fetch title/text only on explicit ingest or context need.

## Accept

A task can link to:
- Google Drive file;
- Yandex Disk file;
- web URL;
- uploaded document;
- local-device resource reference.

---

# PHASE 19 — local files and huge datasets

## Goal

Register local desktop resources without forcing upload.

## Model

A local file can have a URI such as:

```text
personal://device/<device-id>/file/<resource-id>
```

Server stores:
- device ID;
- path or opaque local reference;
- filename;
- size;
- hash if cheap;
- modified time;
- extracted representation if allowed.

## Policies

Per resource choose one:

```text
metadata_only
index_text
upload_copy
```

Default:
`metadata_only`.

## Dataset tools

For CSV/Parquet add server or desktop-side functions:

```text
get_schema
get_sample
get_basic_stats
query_columns
```

Never put a huge dataset into an LLM prompt.

## Accept

A large CSV can be registered and produces schema + sample without full prompt ingestion.

---

# PHASE 20 — Flutter application bootstrap

## Goal

Create one Flutter application for Android and Linux.

Flutter currently supports native Linux desktop; therefore do not create a separate Qt/Tkinter application.

## Do

1. `flutter create`.
2. Enable Android and Linux.
3. Add environment/config handling for server URL.
4. Create typed API client.
5. Add simple auth token storage.
6. Build adaptive navigation.

Screens:

```text
Inbox
Today
Graph
Search
Assistant
```

No design system work beyond clean Material UI.

## Accept

```text
flutter analyze
flutter test
flutter run -d linux
```

Android build must compile when Android toolchain is available.

---

# PHASE 21 — Flutter Inbox and Today

## Goal

Make the application useful before the graph editor exists.

## Inbox

Show:
- notification title;
- source;
- priority;
- reason;
- proposed action.

Actions:

```text
Accept
Ignore
Open context
```

## Today

Show:
- due tasks;
- calendar events;
- high-priority unresolved notifications.

## Object detail

Show:
- title;
- status;
- notes;
- source links;
- neighbors/relations;
- recent context.

## Accept

User can accept a proposed task and see it in Today.

---

# PHASE 22 — Search and Assistant UI

## Goal

Let the user find anything and talk to the Secretary.

## Search

One box over:
- object title/body;
- semantic search;
- optional kind filters.

## Assistant

Text conversation with backend Secretary endpoint.

The backend, not Flutter, decides what context to send to the LLM.

Support messages like:

```text
What is pending for Project Alpha?
Add this notification as a task.
What did I promise Ivan?
Show everything related to the course launch.
```

## Accept

Assistant can answer using object IDs and source provenance.

---

# PHASE 23 — voice input

## Goal

Add push-to-talk commands.

Keep v1 simple:

1. Flutter records short audio.
2. Upload audio to backend.
3. Backend calls configured transcription service.
4. Transcript is sent to the same Secretary command endpoint.
5. Current screen/notification/object ID is included as UI context.

Example:

```text
"Add this to Project Alpha and make it due Friday."
```

If spoken from notification `N`, backend knows what "this" refers to.

Do not build full realtime voice conversation yet.

## Accept

Voice command can create a task from an existing notification.

---

# PHASE 24 — graph/mind-map UI

## Goal

Render different projections of the same graph.

Do not build a full draw.io clone.

## Initial projections

```text
Hierarchy
Dependencies
Context
Freeform
```

Timeline can remain a normal list in v1.

## Flutter implementation

Start with:
- `InteractiveViewer`;
- `CustomPainter`;
- simple node widgets or overlay;
- pan;
- zoom;
- tap node;
- drag node in freeform view.

Server returns:
- nodes;
- edges;
- saved coordinates when relevant.

For automatic layout:
- implement a small deterministic tree layout first;
- dependency layout can be simple layered rows;
- do not introduce Graphviz/ELK unless the simple layout is inadequate.

## Edge creation

When linking A to B, choose:

```text
parent_of
depends_on
blocks
related_to
references
```

## Accept

The same task appears in:
- hierarchy view;
- dependency view;
- another freeform view;
without duplicating the task object.

---

# PHASE 25 — Secretary correlation pipeline

## Goal

Process new source objects cheaply before asking the LLM.

Pipeline:

```text
new object
  ->
normalize
  ->
exact candidate lookup
  ->
people/thread/time matching
  ->
vector candidate search
  ->
small candidate set
  ->
Context Resolver
  ->
Secretary LLM
  ->
proposals/relations/notifications
```

## Candidate rules before LLM

Use cheap deterministic signals:
- same sender/person;
- same email thread;
- same provider IDs;
- dates close to existing events;
- explicit project name;
- existing direct edges;
- semantic similarity.

Pass only a bounded candidate list to the model.

## Accept

The LLM never receives the full object database to decide what one email relates to.

---

# PHASE 26 — action permissions

## Goal

Prevent accidental external actions.

Define levels:

```text
READ
INTERNAL_WRITE
EXTERNAL_PROPOSE
EXTERNAL_WRITE
COMMUNICATE
```

Default policy:

```text
READ            allowed
INTERNAL_WRITE  allowed
EXTERNAL_PROPOSE allowed
EXTERNAL_WRITE  approval required
COMMUNICATE     approval required
```

Examples requiring approval:
- create/change external calendar event;
- send email;
- delete external object.

Store every external write in an audit log.

## Accept

A Secretary tool call cannot send an email without an approval token/state.

---

# PHASE 27 — audit log and security

## Goal

Make sensitive automation inspectable.

## Create `audit_log`

Record:
- actor;
- action;
- object IDs;
- tool;
- result;
- timestamp;
- approval reference if any.

## Secrets

- never commit credentials;
- encrypt OAuth refresh tokens at rest;
- keep encryption key outside the DB;
- HTTPS only in deployment;
- client authenticates to backend;
- MCP endpoint authenticates separately or with scoped token.

## Privacy

Only send required context to the LLM.

For large or sensitive resources:
- prefer summary/chunks;
- exclude irrelevant attachments;
- keep original resource on your server/provider.

## Accept

A user can trace:
`notification -> inference -> source -> approved action -> external result`.

---

# PHASE 28 — deployment on VPS

## Goal

Run the project as a small reliable service.

## Deploy

Docker Compose:

```text
db
api
worker
caddy
```

Persistent volumes:
- PostgreSQL data;
- optional uploaded resources.

Requirements:
- automatic restart;
- HTTPS;
- health check;
- environment secrets outside Git;
- daily DB backup;
- simple log rotation.

Do not add orchestration beyond Compose.

## Accept

After VPS reboot:
- DB starts;
- API starts;
- worker starts;
- HTTPS health endpoint works.

---

# PHASE 29 — Android and Linux packaging

## Goal

Produce usable clients.

## Android

Create a release build.
Document:
- API base URL;
- signing setup;
- microphone permission;
- notification permission if used.

## Linux

Build Flutter Linux release bundle.

Add:
- `.desktop` entry;
- app icon;
- optional `.deb` or tarball packaging.

Do not create a second Linux UI toolkit.

## Accept

User can install:
- Android build on phone;
- Linux build on desktop;
and both connect to the same VPS.

---

# PHASE 30 — final end-to-end scenarios

Do not call the project MVP-complete until these pass.

## Scenario A — mail to task

1. New email arrives.
2. Email is synchronized.
3. System finds related project.
4. Secretary proposes a task.
5. User accepts.
6. Task retains a link to the email.

## Scenario B — missing meeting

1. Email says there is a meeting tomorrow at 13:30.
2. Local calendar search finds no matching event.
3. User receives a high-priority proposal.
4. User sees the source email.
5. User may approve creation of the event.

## Scenario C — large document

1. User links a long document to a task.
2. Original document remains external or stored once.
3. Representations are built.
4. `get_context(task)` returns summary + relevant chunks, not the whole file.

## Scenario D — dataset

1. User links a large CSV/Parquet dataset.
2. System stores URI + schema + sample + basic statistics.
3. Secretary can answer questions using bounded dataset tools.
4. Full dataset is never inserted into a prompt.

## Scenario E — graph projections

One task exists once but appears in:
- project hierarchy;
- dependency graph;
- context graph;
- freeform map.

## Scenario F — MCP

An external MCP-compatible LLM client can:
1. search objects;
2. retrieve task context;
3. create a task;
4. link it to a source object.

## Scenario G — voice

On Android:
1. open a notification;
2. press microphone;
3. say `Add this to Project Alpha for Friday`;
4. transcription succeeds;
5. task is created with the notification source attached.

---

# 31. Minimal API surface target

Do not expand this casually.

```text
GET    /health

POST   /objects
GET    /objects/{id}
PATCH  /objects/{id}
GET    /objects/{id}/neighbors
GET    /objects/{id}/context

POST   /edges
DELETE /edges/{id}

GET    /search

GET    /views
POST   /views
GET    /views/{id}
PATCH  /views/{id}

GET    /notifications
POST   /notifications/{id}/accept
POST   /notifications/{id}/ignore

POST   /assistant/message
POST   /assistant/transcribe

POST   /resources/register

GET    /connectors
POST   /connectors/{provider}/sync

GET    /auth/google/start
GET    /auth/google/callback
```

Provider-specific webhook endpoints may be added as needed.

---

# 32. Minimal MCP surface target

Initial MCP tools:

```text
search(query, kind?, limit?)
get_object(object_id)
get_context(object_id?, query?)
get_today()
create_task(title, body?, due_at?, project_id?)
update_task(task_id, ...)
link_objects(source_id, target_id, relation_type)
list_notifications(status?)
```

Later, only after permission handling is solid:

```text
propose_calendar_event(...)
create_calendar_event(...)
draft_email(...)
send_email(...)
```

Prefer a few clear tools over dozens of tiny ones.

---

# 33. Context packing policy

Use a fixed budget.

A context pack should roughly contain:

```text
1 target object
<= 10 strong graph neighbors
<= 10 semantic candidates
<= 5 recent source items
<= 8 resource chunks
summaries instead of full large resources
```

These are defaults, not laws.

Every included item must carry:

```text
id
kind
title
reason for inclusion
source/reference
```

If the context is too large, remove in this order:

1. weak semantic candidates;
2. old source items;
3. low-confidence relations;
4. extra chunks.

Never remove the direct source that triggered the current action.

---

# 34. Large resource policy

Use this decision tree:

```text
Is it small enough?
  yes -> full representation
  no
   |
   +-> ordinary document?
   |     -> summary + chunks + embeddings
   |
   +-> structured dataset?
   |     -> schema + stats + sample + query tool
   |
   +-> remote/cloud object?
         -> metadata + URI + on-demand fetch
```

The LLM receives a **representation plus a retrieval path**, not necessarily the resource itself.

---

# 35. Correlation policy

When a new source object arrives:

## Step 1 — deterministic evidence

Look for:
- identical provider/thread IDs;
- exact people;
- exact project names;
- URLs;
- dates;
- known relations.

## Step 2 — semantic candidates

Use pgvector to retrieve a small set.

## Step 3 — LLM judgment

Ask the Secretary only about that bounded set.

## Step 4 — confidence

High confidence:
- create internal relation if policy permits.

Medium confidence:
- create proposal.

Low confidence:
- store analysis only or ignore.

Do not notify for every weak relation.

---

# 36. Notification policy

Notify immediately when all are true:

```text
important
time-sensitive
actionable
sufficient confidence
not duplicate
```

Examples:
- probable missed meeting;
- commitment due today;
- blocker requiring user input;
- important mail related to an active task.

Batch or suppress:
- weak semantic matches;
- low-value FYI mail;
- duplicate reminders.

Notifications must contain:
- why it matters;
- source;
- proposed action.

---

# 37. Coding style rules for the agent

Backend:
- prefer plain functions/services;
- async only where useful;
- Pydantic at API boundaries;
- SQLAlchemy for persistence;
- explicit transactions;
- small modules;
- type hints on public functions;
- no metaprogramming.

Flutter:
- keep state management simple;
- use built-in mechanisms or one lightweight package;
- no complex clean-architecture layers;
- separate API models, screens and small services;
- adaptive layout only where Android/Linux differ materially.

Tests:
- test behavior, not implementation details;
- use fakes for external providers;
- no live API in normal CI;
- smoke tests may use real credentials manually.

---

# 38. What not to build in MVP

Do not build these unless an earlier requirement cannot be met without them:

```text
Neo4j
Qdrant
Redis
Celery
Kafka
Kubernetes
multi-user accounts
organization/team permissions
full email client
full calendar client
full file manager
full Notion replacement
full draw.io replacement
autonomous email sending
autonomous calendar writes
realtime voice conversation
multi-agent hierarchy
complex workflow designer
custom local LLM runtime
```

---

# 39. Agent checkpoint template

At the end of every phase rewrite `PROJECT_STATE.md` in this compact format:

```markdown
# Project state

Current phase: 08 complete
Next phase: 09

## Works
- FastAPI health endpoint
- PostgreSQL + pgvector
- object CRUD
- edge CRUD
- semantic search
- resource representations
- context resolver

## Tests
- backend: 42 passed
- flutter: not started

## Blockers
- Google credentials not configured

## Important decisions
- one PostgreSQL DB
- no Redis
- all source and semantic entities use `objects`
- large resources use representations

## Next
Implement Secretary LLM structured analysis.
```

Do not turn this file into a diary.

---

# 40. `CURRENT_TASK.md` template

Only put the next executable stage in it.

Example:

```markdown
# Current task — PHASE 09

Goal: add one Secretary LLM service.

Do:
1. create `SecretaryService`;
2. use Responses API;
3. model ID from env;
4. define Pydantic structured output;
5. pass bounded Context Resolver output;
6. add fixture test for meeting + deadline.

Do not:
- add another agent;
- expose SQL;
- execute external writes.

Done when:
- tests pass;
- sample email produces typed proposals;
- state is updated;
- commit is created.
```

This file is the normal prompt for a small-context coding agent.

---

# 41. Bootstrap prompt to give the coding agent

Copy the repository and this file, then start the coding agent with:

```text
You are implementing the Personal Secretary OS in this repository.

Do NOT read the whole build playbook.

First read only sections 0 through 4 and the PHASE 00 section.
Execute PHASE 00 now.

After PHASE 00, work from PROJECT_STATE.md and CURRENT_TASK.md.
When a phase finishes, locate only the next PHASE section in this playbook, copy a short executable version into CURRENT_TASK.md, then stop reading the playbook.
At the end of every phase, update those files, run tests, commit the working state, and continue with the next phase.

Prefer the smallest correct implementation.
Do not introduce infrastructure or abstractions not required by the current phase.
Do not ask me questions unless you are blocked by missing credentials/secrets, an irreversible external action, or an ambiguity that makes implementation impossible.

If credentials are unavailable, implement and test a fake connector and continue.

Never perform an external destructive/write action during development without explicit approval.
```

---

# 42. Final architectural invariant

If the coding agent forgets everything else, preserve these rules:

```text
PostgreSQL is the source of truth.
Everything is an object or an edge.
Views do not own business data.
Large resources are represented, not dumped into prompts.
Search finds candidates; LLM judges candidates.
LLM uses domain tools, never raw SQL.
Facts, inferences and approvals remain distinguishable.
External writes require approval.
REST and MCP call the same domain services.
Flutter is one codebase for Android and Linux.
Keep the system boring and small.
```

---

# 43. Current implementation notes

When implementation reaches integrations, verify current official documentation instead of trusting old snippets.

At the time this playbook was prepared:

- Flutter has stable native Linux desktop support, so a separate Qt/Tkinter desktop client is unnecessary.
- Gmail supports mailbox push notifications through Google Cloud Pub/Sub; watches expire and should be renewed, and reconciliation is still required.
- Google Calendar supports push notification channels for event changes.
- Yandex Mail supports IMAP and recommends OAuth when the client supports it.
- Yandex Calendar synchronizes through CalDAV.
- OpenAI Responses supports custom function tools and remote MCP servers.
- The OpenAI embedding model `text-embedding-3-small` remains available.
- The official Python MCP SDK supports building MCP servers; prefer the current stable SDK and Streamable HTTP.

Keep provider/model identifiers configurable so future API changes do not require architecture changes.
