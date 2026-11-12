# Character Chat — Complete Documentation (v1.8)

**Single-source documentation for the self-hosted cross-platform Character Chat project.** This README consolidates all Markdown documents from v1.8 into one file. No feature implementation or deployment is implied by this documentation change.

## Documentation index

- [Original project README and version notes](#original-project-readme-and-version-notes)
- [Development roadmap](#development-roadmap)
- [Build preparation (v1.0)](#build-preparation-v10)
- [Integration hardening (v1.1)](#integration-hardening-v11)
- [UI/UX overhaul (v1.2)](#uiux-overhaul-v12)
- [Media and character immersion (v1.3)](#media-and-character-immersion-v13)
- [Voice and audio (v1.4)](#voice-and-audio-v14)
- [Story engine (v1.5)](#story-engine-v15)
- [AI quality and context (v1.6)](#ai-quality-and-context-v16)
- [Performance and scalability (v1.7)](#performance-and-scalability-v17)
- [Offline mode and synchronization (v1.8)](#offline-mode-and-synchronization-v18)
- [Database migrations and upgrade instructions](#database-migrations-and-upgrade-instructions)
- [Piper voice-model installation](#piper-voice-model-installation)

---

## Original project README and version notes


> **v1.8 Offline Mode & Synchronization**: encrypted account-scoped cache, read-only offline history, safe queued title/archive edits, conflict-aware sync, and migration `014_offline_sync.sql`. See [OFFLINE_SYNC_V18.md](#offline-mode-and-synchronization-v18). No application build or deployment performed.

> **v1.6 (source-only):** Token-budgeted prompt assembly, memory ranking, repetition flags, group consistency, local diagnostics, and offline quality evaluations. See [AI_QUALITY_V16.md](#ai-quality-and-context-v16). Existing migrations unchanged.

# Character Chat v1.5 — Advanced Roleplay & Story Engine

**Source-only update. Not built, deployed, or released.**

See [STORY_ENGINE_V15.md](#story-engine-v15) for new roleplay/story endpoints, database migration, Flutter controls, tests, and limitations. The existing v1.4 voice/audio and all earlier features remain included.

# Character Chat v1.4 — Voice & Audio

Version 1.3 extends the v1.2 source **without running a deployment or creating platform builds**.

See [MEDIA_IMMERSION_V13.md](#media-and-character-immersion-v13) for the detailed API, security, and upgrade information.

> **v1.1 — Integration Hardening:** See [INTEGRATION_HARDENING.md](#integration-hardening-v11) and [MIGRATIONS.md](#database-migrations-and-upgrade-instructions). This is source preparation; no deployment or live Flutter/Ollama verification has been performed.

# Character Chat — Self-hosted Starter v1.1

A modular-monolith prototype of a public character-chat service: Flutter client, FastAPI server, PostgreSQL, and **self-hosted Ollama only**. No paid or external AI inference API is used.

> **Prototype, not production-ready.** Do not expose this stack to the public internet until the security and operational checklist below is complete.

## Contents

- `apps/client/`: shared Flutter UI sources for Windows / web / Android / iOS
- `backend/app/api/`: authentication, characters, conversations, SSE chat endpoints
- `backend/app/providers/`: swappable inference interface and Ollama adapter
- `backend/app/models/`: SQLAlchemy schema
- `compose.yaml`: Postgres + Ollama + API, Ollama internal-only
- `scripts/`: model bootstrap utilities

## Prerequisites

- Docker Desktop / Docker Compose v2
- Flutter stable SDK + platform toolchains, for client builds
- Enough memory/disk to run the selected model; GPU inference is optional but recommended for multi-user use

## 1. Start services (PowerShell, in repository root)

```powershell
Copy-Item .env.example .env
# Edit .env and set strong secret values.
docker compose up --build -d
./scripts/pull-model.ps1
Invoke-RestMethod http://localhost:8000/health
```

Model defaults to `llama3.2:3b`, configurable in `.env`. Pulling a model requires internet once. Subsequent inference is local. If you change the model in `.env`, pull that exact model with `./scripts/pull-model.ps1 -Model <name>`. Use `docker compose logs -f api ollama` to inspect errors. API docs: `http://localhost:8000/docs`.

**CPU/GPU:** Compose works with CPU inference. GPU passthrough requires compatible hardware, drivers, and Docker runtime configuration, and is intentionally not enabled by default.

## 2. Generate Flutter platform scaffolding and run

The repository includes the custom Flutter sources but **not** machine-generated Flutter platform runner directories. This is deliberate: generate runners with the installed Flutter SDK and do not overwrite the supplied `lib/main.dart` / `pubspec.yaml`.

```powershell
cd apps/client
flutter create --platforms=android,ios,web,windows --project-name character_chat_client .
flutter pub get
flutter run -d chrome --web-port 8080 --dart-define=API_BASE_URL=http://localhost:8000
```

On Windows desktop:

```powershell
flutter run -d windows --dart-define=API_BASE_URL=http://localhost:8000
```

On an Android emulator, set `API_BASE_URL=http://10.0.2.2:8000` and enable a **development-only** cleartext HTTP exception or use HTTPS. For a physical phone, run the API through an authenticated HTTPS development proxy reachable from the device, and set `API_BASE_URL` accordingly. `localhost` on a phone points to the phone, not your PC.

For iOS compilation, run on macOS with Xcode. Web builds require a Flutter-compatible browser.

## Upgrading an existing v0.1 PostgreSQL volume

**Required for existing installations:** `Base.metadata.create_all()` will not add columns to existing tables. Back up the database first, then apply `backend/migrations/002_character_chat_features.sql` **before** starting the updated API. On Windows PowerShell, from the repository root while Postgres is running:

```powershell
Get-Content -Raw backend/migrations/002_character_chat_features.sql | docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U character -d character_chat
```

Then run `docker compose up --build -d`. On an entirely new database, development startup automatically creates the new schema. This SQL file is a one-time upgrade script, not a complete migration framework; use Alembic for production.

## v0.2 — Profile, conversation management, pinned memory

- **Character profile:** tap a character in Discover or My characters to view their personality, scenario, greeting and visibility. Owners can edit these fields. Starting a chat from a profile opens a new conversation.
- **Conversation management:** Recent Chats now displays human-readable titles. Use the overflow menu to rename, archive/unarchive, or permanently delete a chat with all associated messages and pinned memories. Archived chats remain accessible; archive is not deletion.
- **Pinned memory:** while chatting, tap the brain icon to add/delete conversation-specific memory notes (up to 20 notes of 1,200 characters each). Notes are persisted in PostgreSQL and included in subsequent Ollama prompts. They are *manual notes*, not an automatically learned or semantically retrieved memory system, and are not shared between conversations.
- **Additional API routes:** `GET/PATCH /api/v1/characters/{id}`, `PATCH/DELETE /api/v1/conversations/{id}`, `GET/POST /api/v1/conversations/{id}/memories`, `DELETE /api/v1/conversations/{id}/memories/{memory_id}`.

## v0.4 — Advanced Chat System (source update)

This update adds a **persistent branching message tree**. The active conversation is the path from its root message to `conversations.active_leaf_id`, allowing assistant replies to have multiple alternatives while keeping all branches stored until explicitly deleted.

- **Regenerate:** regenerate the latest selected assistant message without creating another user message. New assistant replies are siblings of the original, and can be selected from the alternatives dialog.
- **Edit:** editing any active-path message creates a replacement message at the same parent and selects it as the new active path (past dialogue remains in its branch). Send another message to continue.
- **Branch:** fork the active conversation up to a chosen message into a **new conversation**, with independent copies of its selected history and manually pinned notes. Automatically learned memories and summaries are not inherited because they can refer to later events.
- **Delete:** deleting a message also deletes **all its descendants**, including alternate branches. This is permanent; the Flutter UI requires confirmation.
- **Response controls:** per-conversation maximum generated token count (64–2048) and roleplay-formatting toggle, included in prompts sent to self-hosted Ollama.
- **Stop / retry:** closing the client HTTP stream requests cancellation of inference. The new user message may persist without a response; a **Retry unanswered message** action completes it without creating duplicate user messages. A partial assistant reply is never saved intentionally.
- **Memory correctness:** changing history or selecting a different response clears automatically learned facts and summaries. Pinned user notes remain. Edits may create forks that are not automatically merged.

### v0.4 API additions

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/v1/conversations/{id}/alternatives/{message_id}` | List alternate assistant replies |
| POST | `/api/v1/conversations/{id}/alternatives/select` | Activate an alternate assistant response |
| PATCH | `/api/v1/conversations/{id}/messages/{message_id}` | Edit selected-path message as new branch |
| DELETE | `/api/v1/conversations/{id}/messages/{message_id}` | Delete selected message and all descendants |
| POST | `/api/v1/conversations/{id}/branch` | Fork a chat at an active message |
| POST | `/api/v1/conversations/{id}/messages/regenerate` | SSE regenerate last active assistant response |
| POST | `/api/v1/conversations/{id}/messages/retry` | SSE retry pending user message |
| PATCH | `/api/v1/conversations/{id}` | Also supports `response_length`, `roleplay_mode` |

### Upgrade existing v0.3 database

Backup PostgreSQL first. Stop the API (`docker compose stop api`), then run the migration against the existing Postgres volume:

```powershell
Get-Content -Raw backend/migrations/004_advanced_chat.sql | docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U character -d character_chat
docker compose up --build -d
```

For upgrading older databases, apply migrations **002 → 003 → 004 in order**. Fresh databases create the v0.4 schema automatically. Migration 004 links old linear messages chronologically, then sets the active leaf to the last saved message.

**Concurrency limitation:** this remains an offline-development prototype. Multiple simultaneous generation requests on a single conversation are not globally serialized. Optimistic active-leaf checking prevents overwriting the selected path after concurrent changes, but a production deployment needs distributed generation locks, disconnect handling tests, idempotency keys, and reliable job cancellation. Generation cancels on stream disconnect only when propagated by the server and HTTP stack. SSE responses and history mutation require integration tests against a running database and Ollama service.

**Roleplay formatting is a prompt convention**, not a guaranteed parser or specialized Markdown renderer; the UI currently displays it as plaintext.

## 3. Try it

1. Register an account (10+ character password).
2. Create a character and set **Public** on.
3. Select it from Discover to see the character profile, and tap **Start new conversation**.
4. Send a message. Ollama streams its reply; messages are persisted in PostgreSQL.
5. Tap the brain icon in the chat header to pin a memory, then send another message to test its influence.
6. Return to Conversations to rename, archive, resume or delete a chat.

The user password is hashed using Argon2. JWTs are valid for 12 hours. **The Flutter client holds tokens in memory only**; signing in again after app restart is expected until secure session storage/refresh flows are implemented.

## Backend local tests

```bash
cd backend
python -m venv .venv
# activate venv
pip install -r requirements-dev.txt
python -m pytest -q
python -m compileall -q app
```

## API examples

`POST /api/v1/auth/register` with `{ "email": "demo@example.com", "password": "strong-password-123", "display_name": "Demo" }` returns a bearer token. Authorized endpoints require `Authorization: Bearer <token>`.

`POST /api/v1/characters` creates characters. `GET /api/v1/characters` lists public characters; `GET /api/v1/characters/mine` lists owned characters. `POST /api/v1/conversations` accepts `{ "character_id": "..." }`. `POST /api/v1/conversations/{id}/messages/stream` accepts `{ "content": "Hello" }` and streams SSE events `token`, `done`, `error`.

## v0.3 — Advanced memory (self-hosted only)

- Automatic memory is **OFF by default** for every conversation. In a chat, open **Memory center** and enable it. The Ollama model processes the completed exchange and proposes up to three durable details per turn, categorized as `fact`, `relationship`, `preference`, or `story`. A maximum of 80 learned notes are stored per conversation. These are model-generated interpretations and may be wrong; users can review, edit, or delete them.
- The model creates a rolling **conversation summary** every eighth completed user message when auto-memory is on. Users can view and clear the summary. It is included in future prompts along with relevant previously learned facts.
- Retrieval is a small keyword-overlap approach (up to eight relevant facts), not embeddings or true semantic search. Relationship tracking is categorized notes, not a structured relationship graph.
- **Lorebooks** are defined on character profiles; the character owner can create, edit and remove up to 100 keyword-triggered world entries. Other users can view lorebooks for public characters. A maximum of four keyword-matched entries is added to the AI prompt for a turn.
- Existing pinned memories remain supported. Learned memories, summaries and pins are scoped to the particular user's conversation, never global across users.
- Only Ollama is contacted. Auto-memory extraction runs after streaming a reply and can delay the final `done` event; failure to extract does not invalidate the reply.

### Existing database upgrade from v0.2

**Back up your database first.** Apply `backend/migrations/003_advanced_memory.sql` once while PostgreSQL is running, before bringing up the v0.3 API:

```powershell
Get-Content -Raw backend/migrations/003_advanced_memory.sql | docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U character -d character_chat
docker compose up --build -d
```

If upgrading from v0.1, apply migration `002` before `003`. Fresh databases are created by the local development bootstrap. A production system still needs a migration framework (e.g. Alembic).

### v0.3 API additions

- `GET /api/v1/conversations/{id}/learned-memories`
- `PATCH/DELETE /api/v1/conversations/{id}/learned-memories/{memory_id}`
- `GET/DELETE /api/v1/conversations/{id}/summary`
- `GET/POST /api/v1/characters/{id}/lorebook`
- `PATCH/DELETE /api/v1/characters/{id}/lorebook/{entry_id}`
- `PATCH /api/v1/conversations/{id}` with `{ "auto_memory": true }`

See `DEVELOPMENT_ROADMAP.md` for the complete saved feature sequence.

## v0.5 — Advanced Character Creator

Creator editing is available under **Create character** and **Edit character** on an owned character profile:

- **Presets:** Custom, Adventurer, Mystery, Friendly Companion and Sci-fi Explorer. Applying a preset fills editable personality/scenario fields.
- **Greeting variations:** Up to eight first messages. The user chooses a greeting when starting a new chat. The chosen greeting becomes the initial persisted assistant message, and will appear in the normal chat history.
- **Example dialogue:** Up to 16 sample turns, in `user:` or `assistant:` format, used as style examples by Ollama.
- **Tags:** Up to 10 unique, normalized tags. Discovery currently displays tags but does not yet provide tag search/filtering.
- **Advanced definition:** Up to 10,000 characters of creator-supplied roleplay reference information, included in the system message as **untrusted reference**. Do not put passwords or secrets here; the current character API exposes this text to readers of a public character.
- **Creator preview/test:** A temporary one-turn Ollama request with up to 250 output tokens. Preview sends the draft character definition and user message to the locally configured Ollama service. It does not persist a chat or character.
- **Import/export:** Owner-only JSON export, copyable to the clipboard, and JSON paste import. Import verifies format `character-chat-v1`, validates all fields, strips original ownership and IDs, and **always creates a private character**. No attached media is imported.

### API additions

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/character-templates` | Built-in starter templates |
| POST | `/api/v1/characters/preview` | Stateless local model preview (login required) |
| GET | `/api/v1/characters/{id}/export` | Export an owned character definition |
| POST | `/api/v1/characters/import` | Import validated definition as private character |
| POST | `/api/v1/conversations` | New optional `greeting_index` (default 0) |

The character create/edit endpoints include `template_key`, `advanced_definition`, `greetings`, `example_dialogue` and `tags`. Existing v0.4 payloads continue to work, with the legacy `greeting` fallback.

### Upgrade from v0.4

Back up the database, stop the API, and run the v0.5 SQL upgrade before restarting the backend:

```powershell
# From repository root; Postgres must be running
Get-Content -Raw backend/migrations/005_advanced_character_creator.sql | docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U character -d character_chat
docker compose up --build -d
```

For older databases apply **002 → 003 → 004 → 005** in order. Brand-new development databases automatically create all current tables/columns. There is still no production-ready automated migration framework.

**Development / validation status:** Python tests and syntax checks were run. Flutter compilation, PostgreSQL migration execution, Docker runtime, and live Ollama preview were not verified in this environment. Preview inference requires a healthy local model. This is still a non-production prototype: preview needs rate limits and model quotas before a public beta.

## What is intentionally not implemented

- Email verification, password reset, refresh-token rotation, MFA, account deletion
- Rate limiting, billing/quotas, abuse monitoring, content policy enforcement, moderation/reporting
- Character deleting, avatars/media uploads, advanced search/filtering, favorites, personas
- Robust distributed conversation locking/idempotency and guaranteed cancel-on-disconnect semantics
- Embedding-based semantic memory search, relationship graph, global cross-chat memory, comprehensive token budgeting
- Full migration automation (a one-time SQL upgrade script is included; auto-create tables is **development-only**)
- Persistent login and production-ready token storage in Flutter
- Distributed jobs, scale-out inference, live monitoring, backups, tests of integrated inference
- Load balancing, TLS termination, production networking and origin security

## Before public deployment

1. Replace the dev JWT/password defaults; set `ENVIRONMENT=production` after adding a proper migration workflow.
2. Add persistent migrations with Alembic and a rollback/backup strategy.
3. Implement email verification, secure refresh/session revocation, account deletion, and privacy exports.
4. Add quotas, per-user request concurrency guards, and distributed conversation locks; SSE cancellation must not leave partial state incorrectly.
5. Add moderation workflow and clear platform/community policies, including safety review for character content and AI output.
6. Restrict CORS and configure TLS, reverse proxy, audit logs, observability, monitoring, and incident response.
7. Plan for inference hardware saturation and denial-of-service resistance; never expose Ollama directly.
8. Deploy Flutter web with HTTPS and use authenticated service endpoints for all clients.

## Model interface

Implement another class conforming to `app.providers.base.ChatProvider.stream_chat(messages)` to swap self-hosted inference backends later. The only current implementation is `OllamaProvider`.

## Development note

The starter was generated without a Flutter/Docker SDK available in the generation environment. Source syntax and basic Python tests are checked when possible, but actual Docker containers, Flutter compilation, and Ollama output cannot be asserted as tested here.


## v0.6 — Personas and multi-character group roleplay

- **Private personas:** create, edit, and delete named roleplay identities with biographies and optional HTTPS avatar URLs. They belong exclusively to the current user and never become public character profiles. Avatars are URL references (not uploaded image storage).
- **Per-chat identity:** select or clear the persona in chat via the badge icon. One-on-one and group prompts use the selected name/biography as *untrusted roleplay context*, not model system authority. Deleting a persona detaches it from existing chats without removing history.
- **Group creation:** the Home screen group icon starts a roleplay with 2–6 distinct accessible characters (public or characters you own), an optional scenario, optional persona, and a title. Participant order is saved.
- **Group AI turns:** after you send a message, the server generates a character reply. Tap *Next character speaks* for another character's reply without an additional user message. You can select a specific participant or choose automatic round-robin rotation. Replies persist the speaker's character ID so the interface labels each turn correctly.
- **Existing chat features:** message editing, branching, regeneration, alternative replies, history, and memory remain available. Branches copy the group's roster, scenario, persona association, and speaker identity.
- **Inference:** all responses continue through the existing local Ollama adapter. There is no external inference provider.
- **New API endpoints:** `GET/POST /api/v1/personas`, `PATCH/DELETE /api/v1/personas/{id}`, `POST /api/v1/conversations/groups`, `GET /api/v1/conversations/{id}/participants`, `PUT /api/v1/conversations/{id}/persona`, `POST /api/v1/conversations/{id}/group/turn`. The group-turn endpoint streams SSE.

### Upgrading v0.5 PostgreSQL database

Back up your database, start the Postgres container if needed, and apply the new migration after `005_advanced_character_creator.sql`:

```powershell
Get-Content -Raw backend/migrations/006_personas_group_chats.sql | docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U character -d character_chat
docker compose up --build -d
```

For fresh installations, `Base.metadata.create_all()` creates the new tables during development; existing tables *require* the migration. Use Alembic and proper migration bookkeeping before production.

### Current limitations

The selected user persona is conversation-wide; changing it affects the prompt for future turns, not historical ones. Group chats are private interactions with several AI characters, **not** chats shared by multiple human users. Speaker selection is sequential and user-invoked; background character simulations and autonomous turn scheduling are not included. Live Flutter/Docker/Ollama integration and cross-platform compilation remain to be verified.


## v0.7 — Discovery & Community (source upgrade)

This source upgrade extends v0.6. Earlier features, local Ollama inference, character importing, personas, memory, and branching chat are retained.

**Flutter:** `community_ui.dart` adds Explore (search/filters/sort/pagination), My Library (favorites/collections), public creator pages, following, and a character-profile community panel (favorite, collection, rating, report, share). Old Home/Chat/Creator screens are preserved. You can open the Explore and Library views from the new toolbar buttons.

**Community API** (prefix `/api/v1`):

| Route | Purpose |
|---|---|
| `GET /characters/discover?q=&tag=&category=&sort=&limit=&offset=` | Public search; sort `trending`, `popular`, `newest`, `rating`; bounded pagination |
| `GET /favorites`, `POST/DELETE /favorites/{id}` | Private favorite list and toggles (auth) |
| `GET/POST /collections`, `PATCH/DELETE /collections/{id}` | Private collections (auth) |
| `GET /collections/{id}/characters`, `POST/DELETE /collections/{id}/characters/{character_id}` | Manage private membership |
| `GET /creators/{id}`, `GET /creators/{id}/characters` | Public creator profile and public characters only |
| `PUT /creators/me` | Set unique handle, bio, optional HTTPS avatar URL |
| `POST/DELETE /creators/{id}/follow` | Follow/unfollow creator (auth) |
| `GET /characters/{id}/community` | Favorites and rating summary / personal state (auth) |
| `PUT/DELETE /characters/{id}/rating` | Upsert/delete 1–5 star rating (auth; no self-rating) |
| `POST /characters/{id}/reports` | Submit one report per user per public character |

**Discovery metrics:** Popular = favorites×2 + distinct single-character chat owners×3 + rating count. Trending = favorites gained over the past seven days×3 plus distinct chat owners (all-time), so this is *a simple approximation*, not a personalized/recent-interactions algorithm. Category uses creator-assigned tags (not a separate curated taxonomy). Character view/open counts are not tracked. Privacy: public search/creator pages exclude private characters; private favorites and collections only return public or user-owned characters. Reports are retained for moderation workflows; v0.9 added admin report and appeal review.

**Shareable links:** Profile Share copies `<PUBLIC_WEB_URL>/?character=<uuid>`; if not provided, browser-origin is used. For a future public web deployment, configure the build with `--dart-define=PUBLIC_WEB_URL=https://your-domain.example` and serve the Flutter web app with single-page-app fallback to `index.html`. The home screen recognizes `?character=<uuid>` after login and opens the profile. On mobile/desktop, universal links and OS app-link association are **not configured** yet. Private characters have no public share path.

**v0.7 PostgreSQL upgrade** (existing v0.6 volume only): back up PostgreSQL; stop API while applying migration; keep DB running.

```powershell
docker compose stop api
Get-Content -Raw backend/migrations/007_discovery_community.sql | docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U character -d character_chat
docker compose up --build -d
```

If upgrading from older than v0.6, apply each missing prior migration sequentially (002 through 007). Fresh development databases are created using SQLAlchemy models on API startup. **This is not a production migration framework**; move to managed Alembic migrations before release.

**Testing:** `cd backend; python -m pytest -q` and `python -m compileall -q app`. v0.7 adds DB-free tests of schemas, SQL construction, route availability, public/private access helpers, and migration structure. These don't substitute for live auth/DB/Flutter/HTTP/inference integration tests. Run `flutter analyze` and `flutter test` after installing Flutter SDK. The Flutter platform runner code is still generated with `flutter create`, as in the earlier README sections.

### Public-release blockers remain

- Implement production moderation UI and action audit trail for submitted reports.
- Server-side rate limits, email confirmation, anti-bot controls, ownership/security integration testing, appropriate user age handling, and durable auth session storage.
- Real migration framework, backup restore testing, database query optimization/indexing, deployment logging/observability, and capacity controls for self-hosted Ollama.
- Verify Flutter web deep links and the official mobile app-link setup before describing mobile share links as ready.

**No build or deployment has been performed as part of this v0.7 update.**

## v0.8 — Self-hosted AI Model Control

This is a **source-only** update; the application has not been compiled or deployed as part of this milestone.

### Features

- `GET /api/v1/ai/models` lists installed Ollama models using the server-side `/api/tags` endpoint. Clients do not connect directly to Ollama.
- `GET /api/v1/ai/health` checks Ollama `/api/version` and `/api/ps`, plus local API inference queue counts and generation presets. `/api/ps` provides loaded-model size and `size_vram` *when supported*. These **are not GPU utilization, temperature, or hardware monitoring metrics**.
- `GET /api/v1/ai/presets` exposes Balanced, Creative, Precise, Roleplay, and Custom profiles.
- `PUT /api/v1/characters/{id}/model` allows an owner to select a currently installed model for their character (`{"model":"llama3.2:3b"}`) or revert to the server default (`{"model":null}`).
- `PUT /api/v1/conversations/{id}/inference` lets the conversation owner override model, preset, `temperature` (0–2), `top_p` (0.05–1), context size (512–131072), and max tokens (64–2048). A null model falls back to the character preference, then the server's `OLLAMA_MODEL`. For presets, set temperature/Top-P to null to use preset values.
- Ollama chat streaming receives `model`, `temperature`, `top_p`, `num_ctx`, `num_predict`; fallback is managed server-side.
- The bounded **in-process** inference queue limits simultaneous generation requests and has a configurable admission timeout. Its counters only cover the current API process, not all workers, servers, or Ollama background requests. Multi-worker deployments need a distributed queue/admission coordinator.
- Flutter adds a Local AI status page, character-owner model selection, and per-chat AI settings screen. Inference settings are copied into newly branched conversations.

### Model choice and capacity

Install models manually on the Ollama host, for example `docker compose exec ollama ollama pull llama3.2:3b`. Only currently installed model names may be selected; API endpoints intentionally cannot download/delete models, avoiding uncontrolled model storage and public pull requests. Unsupported models return 422; unreachable Ollama returns 503.

Configure local limits in `.env`:

```dotenv
INFERENCE_CONCURRENCY=2
INFERENCE_WAIT_SECONDS=20
```

The API still requires **rate limiting, user quotas, public moderation and server-level resource safeguards** before public release. A queue cap is not an effective replacement for these controls.

### v0.7 → v0.8 PostgreSQL upgrade

Back up the database and run with Postgres available, from the repository root:

```powershell
Get-Content -Raw backend/migrations/008_ai_model_control.sql | docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U character -d character_chat
```

This migration adds nullable `preferred_model`, `inference_model`, `temperature`, `top_p`, `context_window` and a defaulted `generation_preset`. Existing records retain the Ollama server's configured default model and Balanced preset. On a fresh development database, `create_all` initializes the current schema. Production will require a real migration-management and rollback plan.

### Validation (no build or deployment performed)

Run Python tests and syntax checking:

```powershell
cd backend
python -m pytest -q
python -m compileall -q app
```

These checks do not establish Flutter compilation, live PostgreSQL migrations, Docker compatibility, or Ollama inference on actual hardware. Those remain outstanding until an integration-testing milestone.


## v0.9 — Administration & Security (source milestone)

Upgrade existing v0.8 databases: back up the database and run `backend/migrations/009_administration_security.sql` with `psql -v ON_ERROR_STOP=1` before starting v0.9. The migration introduces admin roles, account restrictions, moderation states, audit logs and appeals. For clean databases SQLAlchemy creates tables in development.

### API additions

- `GET /api/v1/admin/dashboard`, `/admin/users`, `/admin/reports`, `/admin/appeals`, `/admin/audit` require the `admin` role.
- `PUT /api/v1/admin/users/{id}/restriction`, `/admin/characters/{id}/moderation`, `/admin/reports/{id}`, `/admin/appeals/{id}` make audited changes.
- `POST /api/v1/appeals`, `GET /api/v1/appeals/mine` allow owner appeals, even while suspended.
- `GET /api/v1/privacy/export` returns account-owned character definitions, conversations, messages, personas and related memories.
- `DELETE /api/v1/privacy/account` performs irreversible deletion. This may also delete conversations that other users had with characters created by the deleted account; **download data first and test on disposable data**.

### Admin bootstrap

Create a normal account, then manually assign `role='admin'` in the database with trusted operator access. Alternatively, from an environment with backend Python dependencies and database access, run `python scripts/promote-admin.py admin@example.test`. Example (substitute actual email):

```sh
docker compose exec -T postgres psql -U character -d character_chat -c "UPDATE users SET role='admin' WHERE email='admin@example.test';"
```

There is no public admin registration API. Store privileged database and host access safely.

### Backups

From the repository root with Compose running: `bash scripts/backup-postgres.sh` (Linux/macOS) or `powershell -File scripts/backup-postgres.ps1` (Windows). Dumps are PostgreSQL custom format. Test restores only to an **empty isolated database**: `scripts/restore-postgres.sh`. Backups should be encrypted, access-controlled, retained per policy, and tested for recovery. Backups may retain data after live deletion until expiry.

### Known limits before a public beta

- The request rate limiter is process-local, keyed by network IP + URL prefix. It is not a substitute for distributed Redis/edge enforcement; NAT/shared users can share limits.
- User content moderation requires a human moderation workflow; there is no automatic model-based scanning and no anti-bot CAPTCHA yet.
- `audit_logs` keeps minimal actor IDs and decisions, not raw private messages. Database archival, retention and external monitoring are not automated.
- Existing JWT tokens last 12 hours and do not provide per-device revocation. Production needs refresh-token/session management and incident response.
- No end-to-end PostgreSQL/Ollama/Docker/Flutter verification has been run in this environment.

## v1.0 — First-build preparation and integration checks (no deploy)

This release retains the v0.9 application source and adds:

- A **frozen v0.1 baseline SQL** (`backend/migrations/001_initial_v01.sql`) generated from the original v0.1 models, solely to exercise the historical upgrade path. It is **not** intended to be run against an existing database.
- A PostgreSQL migration verification job using a real Postgres 17 service. It applies 001 → 009 and compares the resulting tables/columns against current ORM metadata. This catches missing columns but is not an exhaustive semantic migration audit.
- Flutter widget tests for sign-in and switching to registration, plus `flutter analyze` in CI.
- GitHub Actions workflows for Python tests, database upgrade verification, Flutter static analysis/widget tests, and manual-only platform compile checks.
- An operational checklist for Windows, web, Android, and unsigned iOS simulator compilation.

**No platform runners, build binaries, signing keys, model weights, or API credentials are shipped.** Platform folders are generated with Flutter tooling; `flutter create` might change generated files with Flutter version. CI platform compile checks are **manual (`workflow_dispatch`) only** and do not deploy, publish, or upload distributables. The automatic Flutter workflow does run static analysis and widget tests.

### Local source checks

```powershell
cd backend
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m compileall -q app
cd ../apps/client
flutter create --platforms=android,ios,web,windows --project-name character_chat_client .
flutter pub get
flutter analyze
flutter test
```

### Migration verification (in CI, or against a disposable database only)

```bash
export PGPASSWORD=<test-database-password>
export TEST_DATABASE_URL=postgresql+asyncpg://character:<test-database-password>@localhost:5432/character_chat
bash scripts/verify-migrations.sh
```

**WARNING:** `verify-migrations.sh` applies the v0.1 baseline and all subsequent migrations. Use a *new, empty, disposable* PostgreSQL database only. It is **not** the upgrade command for an existing installation. For existing installations, back up data and apply only the missing migrations in order (002–009); do not apply 001.

### Not verified here

No Docker daemon, PostgreSQL server, Flutter SDK, Xcode, or platform toolchains are available in this build environment. Therefore actual compilation, live database upgrades, auth/chat flows, self-hosted Ollama inference, and cross-platform packaging remain **unverified**. The CI workflows provide repeatable ways to check them once run by the project owner. They do **not** certify production security.

The project's security limitations from v0.9 still apply. Do not expose it publicly until end-to-end tests, abuse controls, secrets management, safe migrations, and public-content policies have been addressed.

## v1.2 — Responsive UI/UX overhaul

The client now has a shared theme/design system, adaptive desktop navigation rail, mobile tabs, character discovery grids, chat bubbles, profile header, and improved loading/empty/error states. No backend schema changes are needed. See `UI_UX_V12.md` for the change log, verification commands, responsive rules, and remaining validation work.


## v1.4 Voice & Audio (self-hosted)

Adds private character voice settings, voice playback for saved AI replies, push-to-record speech transcription into the chat composer, a private clip library, and a Piper + faster-whisper worker. No voice weights are bundled. Refer to **VOICE_AUDIO_V14.md** for model setup, microphone permissions, API contracts, tests and security limitations. The database change is `backend/migrations/011_voice_audio.sql`. No build or deployment has been performed.

## v1.7 — Redis coordination, load testing and performance telemetry

v1.7 adds Redis as an **internal** Compose dependency, distributed stream admission, shared rate limiting, scoped model-metadata cache, database query indexes, and admin-only performance metrics. Read `PERFORMANCE_SCALABILITY_V17.md` before enabling multiple API workers. Apply migration `013_performance_indexes.sql` via `backend/scripts/migrate.py` to a database that already has migrations 001–012 tracked.

No user conversations are cached in Redis. No application build or deployment was performed as part of this source update.


---

## Development roadmap

# Character Chat Development Roadmap

The project is a self-hosted public-platform character chat application targeting Windows, web, Android and iOS. Keep expanding source code and running tests before first public deployment.

- [x] v0.1 Foundation — Flutter, FastAPI, PostgreSQL, Docker Compose, Ollama.
- [x] v0.2 Character profiles, conversation management, manually pinned memories.
- [x] v0.3 Advanced Memory — opt-in local extraction, categorized long-term facts, relationship tracking as relationship notes, rolling conversation recaps, keyword-based recall, creator lorebooks, user review/edit/delete.
- [x] v0.4 Advanced Chat — regenerate/swipe, edit, branch, delete messages, response controls, cancellation, roleplay formatting.
- [x] v0.5 Advanced Character Creator — templates, greetings, example dialogue, tags, preview, import/export.
- [x] v0.6 Personas & Group Chat — private persona profiles with optional avatars; per-chat selection; 2–6 characters in a group; manual/round-robin speaker turns; group story prompts.
- [x] v0.7 Character Discovery & Community — search/filter/sort/pagination; favorites and private collections; creator profiles/follows; ratings; reporting queue foundation; shareable web character links.
- [x] v0.8 AI Model Control — installed-model discovery, per-character preferences, chat presets/settings, per-process inference admission queue, and Ollama status/loaded VRAM-residency metadata (not live GPU utilization).
- [x] v0.9 Administration & Security — admin operations, reports/appeals, account restrictions, privacy endpoints, audit records, dev-only rate limit, backup scripts. Live deployment security remains pending.
- [ ] v1.0 Integration tests, build packaging, cross-platform beta readiness.

No public deployment until authentication, moderation, abuse defenses, privacy, infra and scalability are reviewed. Each milestone must include targeted tests and migration steps.

- **v1.0 — Source preparation:** migration baseline verification, Flutter widget tests, platform CI preparations; actual compilation and integration still pending.

- **v1.1 — Integration Hardening:** transactional migration runner, streamed Ollama tests, Flutter SSE parser and widget tests, stronger integration checks (source update).

## v1.2 — UI/UX overhaul (source authored; compilation pending)

Desktop navigation rail, mobile bottom navigation, responsive discovery cards, reusable chat bubbles, light/dark theme support, accessibility and loading/error/empty states. Widget tests added; Flutter compilation and integration remain outstanding. No deployment.

- v1.3 Media & Character Immersion: secure image media API, local storage, visual metadata, background display, roleplay rich text — source preparation.

## v1.4 — Voice & Audio (source authored; runtime verification pending)
- Local Piper TTS, faster-whisper STT, private internal voice worker with shared token.
- Authenticated per-character voice settings, assistant message playback and a private audio clip library.
- Flutter microphone recording, local transcription into the composer, platform microphone-permission setup.
- Migration `011_voice_audio.sql`, API/format/ownership tests, updated Compose.
- **Not deployed.** Flutter compilation, migrations against live PostgreSQL, voice model execution, and Docker runtime have not been validated. See `VOICE_AUDIO_V14.md`.

- **v1.5 — Advanced Roleplay & Story Engine:** source complete (scene and state management, relationship/emotion state, scenarios, branching snapshots, event timeline); live integration pending.

## v1.6 — AI Quality & Context Optimization (source complete)

Context budgeting, deterministic memory ranking, repetition warnings, group speaker consistency, prompt diagnostics, local quality evaluation corpus, and Flutter diagnostics panel. No new database migration. Full Flutter and live server integration still unverified. See `AI_QUALITY_V16.md`.

## v1.7 — Performance & Scalability (source authored)

Redis-based distributed inference admission and fixed-window rate limiting, SQLAlchemy pool sizing, additive index migration 013, bounded Ollama metadata cache, context/output caps, admin-only aggregate performance metrics, bounded load probe and CI Redis integration test. Runtime Redis/Flutter/Ollama/PostgreSQL verification is still pending; see `PERFORMANCE_SCALABILITY_V17.md`.

## v1.8 — Offline Mode & Synchronization (source prepared)

Encrypted per-account cache, offline reading, queued safe title/archive edits, retry and conflict review, versioned server sync, and tests. Full Flutter/runtime checks remain outstanding.


---

## Build preparation (v1.0)

# Character Chat v1.0 — build preparation (not a release)

This source repository has **not** been compiled or deployed in the current delivery. Do not publish it until integration tests and security reviews pass.

## Layout

- `apps/client/lib/`: Flutter application source, with UI modules for communities, admin, and Ollama controls
- `apps/client/test/`: registration/login widget tests (no network needed)
- `backend/`: FastAPI, ORM models, Ollama provider, tests, incremental migration SQL
- `backend/migrations/001_initial_v01.sql`: frozen legacy initial schema for migration tests only
- `.github/workflows/backend-ci.yml`: Python unit tests and compileall
- `.github/workflows/migration-ci.yml`: PostgreSQL 17 upgrade path + HTTP API smoke checks
- `.github/workflows/flutter-ci.yml`: static analysis and widget tests
- `.github/workflows/manual-platform-builds.yml`: optional manually dispatched cross-platform *unsigned compile check*, no deploy

## Preparing targets (execute locally only when you choose to build)

| Target | Requirements | Flutter compile command |
|---|---|---|
| Windows | Windows machine, Visual Studio C++ desktop workload, Flutter SDK | `flutter build windows --release` |
| Web | Flutter SDK, Chromium for local testing | `flutter build web --release` |
| Android | Android SDK and JDK, Flutter SDK, application signing for production | `flutter build appbundle --release` (release signing must be configured) |
| iOS | macOS, Xcode, CocoaPods where needed, Apple signing for device/distribution | `flutter build ios --release` (signing/provisioning required) |

To generate platform runners from this source tree, navigate to `apps/client` and run:

```shell
flutter create --platforms=windows,web,android,ios --project-name character_chat_client .
flutter pub get
flutter analyze
flutter test
```

**API addresses:** `http://localhost:8000` works for Windows and a same-host browser. Android emulator requires `http://10.0.2.2:8000`; physical devices require an HTTPS server accessible from the device. Web requires appropriate CORS settings on the API. Production HTTPS, certificates, app links, mobile platform network policies, and signing are not configured.

## Migration test approach

The v1.0 verification workflow starts an **empty** PostgreSQL 17 instance, executes the historical frozen v0.1 schema, and applies upgrades 002 through 009 sequentially. It then uses SQLAlchemy metadata checks and a live HTTP ASGI smoke test for registration, login, and character creation. This is **not** a simulation of existing user data with production-scale data/constraints and is not a replacement for testing database backups and upgrade rollback.

Do not run `001_initial_v01.sql` against any existing database. Stop the backend, back up your database, and apply only unapplied migrations. The previous bootstrap `create_all()` behavior is still present for development; it cannot upgrade existing columns, so new deployment migrations require separate care.

## Known work before public release

1. Resolve Flutter analyzer and compiler findings on the actual SDK and all target OSes (not run here).
2. Run a full Docker/PostgreSQL/Ollama generation cycle, including interruption, retries, streaming, and migrations with realistic old data.
3. Harden authentication (verification, sessions, revocation), abuse protection, moderation and data deletion/retention behavior.
4. Replace in-process rate limiting and inference queue with distributed controls for multi-instance service operation.
5. Add production media upload storage, privacy controls, model moderation and cost/capacity testing.
6. Configure HTTPS, safe credentials, monitoring, recoverable backups, app identifiers, release signing and store policies.


---

## Integration hardening (v1.1)

# v1.1 Integration Hardening

## Changes
- Extracted Flutter SSE event decoder so event frames are handled independently of TCP chunk boundaries. Unit tests cover chunk splits, multiline JSON, CRLF, comments, malformed data and final unterminated events.
- Improved chat stream HTTP errors by including the server's response body.
- Added simulated Ollama `/api/chat` streaming, health, model listing, transport error, inference option, and concurrency tests; no real Ollama needed for the unit suite.
- Added transactional, checksum-tracked PostgreSQL migration runner and idempotent migration CI path.
- Preserved all v0.1–v1.0 application modules and historical SQL migration files.

## Verification boundaries
- Python unit suite: run `cd backend && python -m pytest -q`.
- Migration suite: run `bash scripts/verify-migrations.sh` against a **fresh disposable PostgreSQL database**.
- Flutter: after installing Flutter, `cd apps/client && flutter create --platforms=android,ios,web,windows --project-name character_chat_client . && flutter pub get && flutter analyze && flutter test`.
- Integration with live Ollama and Flutter platform builds is still required. Do not treat mocked streaming tests as an end-to-end production signoff.
- No deployment, signing, or public publishing is part of this milestone.

## Known limitations
- Client tokens are still held in app memory and must be replaced with secure persistence plus refresh/session management.
- Inference throttling is per-process, not distributed.
- `create_all()` remains a development-only bootstrap and cannot upgrade an existing database.
- Flutter, Docker, live PostgreSQL and Ollama are not available in the authoring runtime. CI will verify them when executed in supported environments.


---

## UI/UX overhaul (v1.2)

# v1.2 UI/UX overhaul (source-only)

This milestone keeps the existing v1.1 FastAPI, database schema/migrations, Ollama gateway, and authenticated endpoints unchanged. There are **no database migrations** for v1.2.

## Changed client source

- `apps/client/lib/design_system.dart`: centralized responsive breakpoints, light/dark color themes, maximum-width content frames, character cards, loading/error/empty states, and chat bubbles.
- `apps/client/lib/main.dart`: responsive home navigation rail (desktop) and bottom tabs (mobile); discovery preview grid, character library grid, conversation list actions, theme cycling, consistent chat bubbles/composer, improved character profile header.
- `apps/client/lib/community_ui.dart`: responsive character discovery grid and retryable network-error state.
- `apps/client/pubspec.yaml`: version bumped to `1.2.0+1`.
- `apps/client/test/design_system_test.dart`: theme, layout thresholds, reusable content states, and chat bubble widget tests.
- `apps/client/test/responsive_navigation_test.dart`: mock-API phone and desktop navigation widget tests.

## Responsive behavior

| Window width | Layout |
|---|---|
| < 520 logical pixels | Single-column character cards |
| 520–849 | Two-column cards |
| 850–1199 | Three-column cards |
| >= 1200 | Four-column cards |
| < 1080 | Bottom tabs (Discover, Chats, My characters) |
| >= 1080 | Expanded navigation rail |

Secondary features remain in the overflow menu: favorites, creator profile, personas, group chat, models, privacy, admin, and logout. Creator editor and other specialized screens are retained from v1.1.

## Accessibility

- Visible field labels/tooltips and controls use Flutter Material semantics.
- Empty and error states have descriptive titles/actions; loading has a live-region semantic label.
- Chat messages use selectable text.
- Themes adapt to light/dark mode (system by default, with menu cycling).
- Responsive layout is based on actual available logical width, not assumed device category.

## Verification

- Run `cd backend && python -m pytest -q` for backend regression tests.
- Run `cd apps/client && flutter create --platforms=android,ios,web,windows --project-name character_chat_client . && flutter pub get && flutter analyze && flutter test` for client checks.
- Run the existing manual platform build workflow later, when you choose to build. It is not triggered by this update.

Flutter SDK is not available in the current environment. Widget tests and analyzer have been authored but **not executed** here. This source archive has not been compiled, built, deployed, or publicly released.


---

## Media and character immersion (v1.3)

# v1.3 — Media & Character Immersion

## Changes

- Character visual description, visual style and hex accent settings are editable and included in character JSON export/import.
- Authorized users can upload avatar/gallery images for owned characters, avatar images for owned personas, and chat backgrounds for owned conversations.
- Gallery and character avatar images appear in character profiles; persona uploads appear in persona lists.
- Uploaded chat backgrounds are shown with low opacity beneath the conversation.
- Character messages support local-only selectable formatting: `*action*` (italic) and `**emphasis**` (bold). No HTML is executed.
- Media manager supports image listing, deletion and uploading from Windows/web/mobile via `file_picker`.
- A private application media storage volume (`media_data`) has been added to Docker Compose.

## HTTP API

All media endpoints require a bearer token.

- `POST /api/v1/media` multipart: `file`, `purpose` (`avatar`, `gallery`, `background`) and precisely one of `character_id`, `conversation_id`, `persona_id`. Owner only.
- `GET /api/v1/media?character_id=...` or `conversation_id=...` or `persona_id=...` — scoped listing. Public characters' images are visible to signed-in users.
- `GET /api/v1/media/{id}` — authorization-controlled PNG download, private `no-store`.
- `DELETE /api/v1/media/{id}` — owner-only image deletion. Active chat background is cleared on deletion.

## Upload security

- JPEG, PNG and WebP still images only; content is decoded and re-encoded as PNG with EXIF removed.
- 5 MiB input limit, 12 million source pixels, 2048px maximum output dimension, 8 MiB output cap.
- Upload files are stored under random server-generated names outside any public static directory.
- 200 media items per account. No SVG, animated image, arbitrary filesystem path, or remote image fetching.
- Uploaded media remains authenticated. Public character media is accessible to signed-in users only if the character is public and active. Personas and conversation backgrounds are private to their owner.
- This local-storage starter is intended for one API host. Production requires media scanning, quotas covering aggregate bytes, object storage, backup/restore tests, reconciliation/orphan cleanup, and anti-abuse controls.
- Conversation deletion and account deletion remove their stored image files. Other database cascades and interrupted filesystem writes can still leave orphans; add a secure garbage-collection job before public deployment.

## Existing database upgrade

Back up PostgreSQL and media first. Migration `backend/migrations/010_media_immersion.sql` adds `media_assets`, appearance fields, and per-chat background media pointers. **Run through** `backend/scripts/migrate.py` for migration-ledger-managed databases. Existing databases without a ledger need the documented reconciliation process in `MIGRATIONS.md`. Never silently apply the baseline to an existing populated database.

If the backend runs in Docker Compose, `media_data:/app/data/media` keeps uploaded content persistent across container replacement. Set `MEDIA_STORAGE_DIR` for standalone execution.

## Tests and limitations

Run `PYTHONPATH=backend python -m pytest backend/tests -q`; the v1.3 suite covers image validation, re-encoding, metadata removal, scopes and authorization, SQLAlchemy schema, and the v1.1 regression suite. Flutter widget tests were added in `apps/client/test/roleplay_media_test.dart`; execute `flutter pub get && flutter test` on an installed Flutter SDK.

No live Docker, Ollama, PostgreSQL or Flutter compilation has been performed in this preparation environment. Verify them before release. The old external `avatar_url` field remains for backwards compatibility; prefer authenticated uploads for privacy-sensitive content.


---

## Voice and audio (v1.4)

# Character Chat v1.4 — Self-hosted Voice & Audio

No cloud inference, cloud voice API, or public deployment is included. Text chat stays functional if the voice service is offline. The application still needs Flutter compilation and full integration testing before use.

## Architecture

- **Flutter:** `record` streams microphone PCM at 16 kHz mono, wraps it in WAV, and sends it only after recording stops; no voice message is sent automatically. `audioplayers` plays private speech clips obtained with the authenticated API.
- **FastAPI:** `/api/v1/voice/` endpoints require JWT authentication. Character voice assignment is creator-only; synthesis only accepts a persisted assistant message belonging to the caller's conversation. Transcription accepts up to 12 MiB and returns *only text*; the upload is not persisted. Audio clips are capped per account, stored as generated WAV, and retrievable only by their owner.
- **Private worker:** `voice-service` has **no published Docker port**. It uses Piper for local TTS and faster-whisper CPU INT8 for local speech recognition. Traffic between API and worker carries an internal shared token; the worker serializes jobs to avoid excess memory use. A model download is required for first use.
- **PostgreSQL:** `011_voice_audio.sql` adds the character voice preference and private voice-clip metadata. Voice bytes live in a separate Docker volume. Chat/account deletion cleans associated voice files; individual clips can be removed from the chat audio library.

## Voice models

The ZIP does **not** include voice weights or pre-trained speech models. Create a `voice-models` directory in the project root (provided with README), then install an authorized Piper voice as:

```
voice-models/voice.onnx
voice-models/voice.onnx.json
```

Additional voices can be installed as `voice-models/<voice_id>.onnx` plus `<voice_id>.onnx.json` and included as a comma-separated `VOICE_IDS=default,voice2`. IDs must consist of letters, numbers, hyphens, and underscores. Download from the official Piper voice model distribution and confirm the license for each voice before using it in a public product. `WHISPER_MODEL=tiny` configures a locally running faster-whisper recognizer. The initial download of the model files requires network access; subsequent inference is local if the models are cached. For air-gapped deployment, preload the model cache.

## API

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/voice/status` | Voice service availability and configured voices |
| PUT | `/api/v1/voice/characters/{character_id}/voice` | Creator-only voice assignment |
| POST | `/api/v1/voice/transcribe` | Multipart `file`, returns `{text}` (not persisted) |
| POST | `/api/v1/voice/conversations/{chat_id}/messages/{message_id}/synthesize` | Generate a WAV for a saved assistant message |
| GET | `/api/v1/voice/conversations/{chat_id}/clips` | Private conversation clip library |
| GET | `/api/v1/voice/clips/{clip_id}` | Authenticated WAV playback |
| DELETE | `/api/v1/voice/clips/{clip_id}` | Delete owned clip |

Audio messages are **playback of text replies**, not a live/full-duplex voice call. User speech is transcribed into the message composer and must be explicitly sent. TTS does not clone voices. Voice selection is owner-configured per character; no voice model is uploaded through the public API.

## Backend development

1. Install backend development dependencies and run `python -m pytest -q` from `backend`.
2. On an **empty** disposable database, use `python backend/scripts/migrate.py` with `DATABASE_URL` set to the test database. For an existing database without a migration ledger, follow `MIGRATIONS.md`; **do not replay baseline migration 001**. Back up before manually applying `011_voice_audio.sql`.
3. Install Piper models in `voice-models/`. Set `VOICE_INTERNAL_TOKEN` to a fresh long random secret, and use matching values in both API and worker configuration. Compose keeps the worker on an internal network.
4. For local-only integration after source checks, start Compose with `docker compose up --build` (this builds containers; not done as part of this source update). Pull the Ollama text model separately.

## Flutter platform permissions

After `flutter create --platforms=android,ios,web,windows --project-name character_chat_client .` inside `apps/client`, run `python scripts/configure-flutter-audio.py` from the project root. This adds `RECORD_AUDIO` to Android manifest and `NSMicrophoneUsageDescription` to iOS Info.plist. GitHub workflows perform the same step. Web microphone capture requires a secure context (HTTPS or localhost) and browser permission. Windows devices need microphone permissions enabled in OS Settings. Then run `flutter pub get`, `flutter analyze`, and `flutter test` when Flutter is available.

## Remaining security/operational work

- Implement distributed rate limits and stricter generation quotas before opening voice features publicly; the baseline project has process-local rate limiting.
- Add content moderation for synthesized output, upload malware scanning as appropriate, and abuse/consent checks around character voice configuration.
- Add asynchronous inference jobs and cancellation. Current synchronous requests can time out on slow CPUs.
- Improve accessibility, microphone device selection, voice speed/pitch controls, and media-catalog browsing in subsequent revisions.
- Test voice engine installation, inference memory, and all target Flutter platforms in a real environment.


---

## Story engine (v1.5)

# v1.5 Advanced Roleplay & Story Engine

This is a **source-only development update**. Nothing has been deployed or publicly released.

## Features

- Private story state per conversation: title, premise, objective, chapter number, and active/paused/completed status.
- Scene library (up to 100 scenes/chat, with scene editing and deletion); one active scene per story, with scene transitions logged to the timeline.
- Character relationship progression: affinity and trust from -100 to +100 with user-authored notes.
- Per-character emotions: named mood, 0–100 intensity, and context notes.
- User-owned reusable scenario templates (up to 100 per user). Applying a template updates the story and creates an opening scene without deleting prior scenes or timeline events.
- Event timeline (up to 1,000 events per chat) of milestones, decisions, discoveries, relationships, and scene transitions. Timeline events are **explicitly recorded**, not silently inferred by AI.
- Story continuity is rendered into Ollama's system-message context as **bounded, untrusted narrative data**; existing conversation history, lorebooks, memories and personas remain intact.
- A chat fork clones the current story state, scene library, emotions, relationships and timeline into independent records. **Important:** it is a snapshot of the source's story state *at fork time*, not an automatic reconstruction of the historical state at the selected message. Rewind and reapply older events manually for accurate historical branches.
- Deleting conversations or accounts removes story records via PostgreSQL `ON DELETE CASCADE`. Account export includes the story and scenario records.

## Relevant files

- `backend/app/models/entities.py`: `StoryState`, `StoryScene`, `StoryRelationship`, `StoryEmotion`, `StoryEvent`, `StoryScenario`.
- `backend/app/api/story.py`: authenticated story/scene/emotion/relationship/timeline/scenario endpoints.
- `backend/app/api/story_schemas.py`: validated request/output models.
- `backend/app/services/story.py`: prompt context, participant checks and independent branch snapshots.
- `backend/migrations/012_story_engine.sql`: forward-only migration.
- `backend/tests/test_story_engine.py`: security, validation, migration, and prompting contracts.
- `apps/client/lib/story_ui.dart`: story workspace, scene activation, relationship/emotion management, timelines, scenario templates.
- `apps/client/test/story_ui_test.dart`: Flutter widget tests (require Flutter SDK).

## Migration workflow

**Back up PostgreSQL first.** For databases already tracked by the v1.1 migration runner:

```bash
cd character_chat_starter
export DATABASE_URL='postgresql+asyncpg://character:YOUR_PASSWORD@localhost:5432/character_chat'
python backend/scripts/migrate.py
python backend/scripts/migrate.py --verify-only
```

The migration runner uses transactional upgrades and hashes. For pre-tracking databases, follow `MIGRATIONS.md`; do not manually mark a migration as applied without inspecting the schema.

## API summary

All `/api/v1/conversations/{id}/story/*` routes require ownership of the conversation; story records never become public because their associated character is public.

| Endpoint | Methods |
| --- | --- |
| `/conversations/{id}/story` | GET, PUT |
| `/conversations/{id}/story/scenes` | GET, POST |
| `/conversations/{id}/story/scenes/{scene_id}/activate` | PUT |
| `/conversations/{id}/story/scenes/{scene_id}` | PATCH, DELETE |
| `/conversations/{id}/story/relationships` | GET |
| `/conversations/{id}/story/relationships/{character_id}` | PUT |
| `/conversations/{id}/story/emotions` | GET |
| `/conversations/{id}/story/emotions/{character_id}` | PUT |
| `/conversations/{id}/story/timeline` | GET, POST |
| `/conversations/{id}/story/timeline/{event_id}` | DELETE |
| `/story/scenarios` | GET, POST |
| `/story/scenarios/{scenario_id}` | DELETE |
| `/conversations/{id}/story/scenarios/{scenario_id}` | POST |

The version prefix `/api/v1` is omitted in the table for readability.

## Test commands

```bash
cd character_chat_starter
PYTHONPATH=backend python -m pytest backend/tests -q
cd apps/client
flutter pub get
flutter analyze
flutter test
```

Live PostgreSQL migration integration, Ollama streaming, Flutter compilation, and widget tests require installed runtimes. They have not been run in this source-preparation environment.

## Known limitations before public use

- Story state is user-managed; there is no autonomous AI state extraction or automatic sentiment scoring, to avoid unauthorized or unreliable state changes.
- The v1.5 Flutter screen is wired to the existing chat; additional accessibility and production navigation testing are outstanding.
- Branches copy story state at fork time, not the selected historical message's timestamp.
- PostgreSQL and Flutter need live integration checks; backend passing tests do not establish readiness for production.


---

## AI quality and context (v1.6)

# v1.6 — AI Quality & Context Optimization

**Status:** Source changes and deterministic tests implemented. Flutter compilation and live Docker/PostgreSQL/Ollama integration were not performed. No deployment.

## Changes

- **Local prompt budgeting:** `backend/app/services/quality.py` assembles character instructions, story continuity, pinned notes, summaries, learned memories, lorebook and recent dialogue under a bounded **estimated** prompt budget. Reserves room for output tokens and headroom. Older history is dropped first and the most recent turn is retained, possibly clipped. The estimator is deliberately conservative, not Ollama's exact model-specific tokenizer; actual Ollama truncation can still vary by model. Context limits are a quality guard, not a security boundary.
- **Memory retrieval:** rank conversation-scoped learned memories by word overlap, exact phrase and story/relationship relevance, with a bounded list of matches. No embeddings, external search, or cross-conversation indexing.
- **Repetition:** the prompt discourages repeating recent language; after generation a local similarity test emits a `quality` SSE event with a warning when very close to an earlier reply. It **does not** automatically retry or block the response, since that could discard user-chosen dialogue and increase inference costs.
- **Character and group consistency:** the system prompt reinforces character identity, forbids speaking on behalf of the user or other group members, and retains named group turn context. Group turn ordering still uses v0.6's controlled round-robin and explicit speaker selection.
- **Diagnostics:** chat streaming emits a `diagnostics` event with estimated token use and truncation by section. An authenticated `GET /api/v1/conversations/{id}/prompt-diagnostics` returns a simpler current-history-only estimate and no prompt text. UI shows the most recent live diagnostics or requests the estimate. **The dry-run endpoint is not a full representation of the live prompt** (it intentionally skips loaded story and memories).
- **Quality evaluations:** `backend/evaluations/run_local_quality.py` runs a small deterministic local corpus. Evaluations cover heuristic repetition only, **not semantic correctness, factuality, model consistency, or user satisfaction**.

## Tests

From the repository root:

```bash
cd backend
PYTHONPATH=. pytest -q tests
python evaluations/run_local_quality.py
```

The backend test suite includes v1.6 budget, unicode, retrieval, repetition, and integration-wiring tests. The Flutter test `apps/client/test/quality_ui_test.dart` checks the diagnostics panel. It requires a Flutter SDK, which was not available during preparation.

## Compatibility and migrations

- No database schema changes are needed in v1.6; all v1.5 migrations `001` through `012` remain present.
- The `diagnostics` and `quality` SSE events are additive; existing clients can ignore them.
- `quality` is emitted after a reply is successfully saved. `done` retains its existing payload and meaning.
- The backend still requires an installed Ollama model, PostgreSQL, and the existing optional voice services. No external inference provider is introduced.

## Limits before a public release

Run real Ollama tests with different models and window sizes; confirm reply cancellation, input token counting and inference latency; test multi-user concurrency, prompt injection resilience and privacy; run Flutter analyzer/widget tests and all PostgreSQL migrations on a clean test database. The source-only tests do not prove release readiness.


---

## Performance and scalability (v1.7)

# Character Chat v1.7 — Performance & Scalability

**Scope:** source-only upgrade from v1.6. No build, deployment, release, public exposure, or infrastructure provisioning was performed.

## What changed

- Added **Redis 7** on the internal Compose network, with no published Redis port. The API requires Redis on startup when `REDIS_URL` is set; production startup requires a shared Redis coordinator.
- Added a **cross-process FIFO admission coordinator** for Ollama response streams. It uses atomic Lua scripts for an ordered waiting set, global active permit set, queue limits, lease expiration, periodic renewal, timeout handling, and cleanup when a stream is cancelled. The inference itself runs in the API worker; **this is not a durable background job queue**. Client disconnects cancel the work.
- Added **Redis fixed-window write-request throttling**, keyed by a SHA-256 digest of client IP/method/route group. Rate limiting **fails closed** when the configured Redis server is unavailable. Note: behind a reverse proxy, the API must receive a securely established true client IP; do not trust arbitrary X-Forwarded-For headers. Edge quotas and authenticated per-user quotas are still recommended before public use.
- Added **bounded SQLAlchemy connection pool** settings (pre-ping, max connections, overflow, timeout, recycling). Each process has its own pool, so total DB connections scale with the number of API workers.
- Added **public Ollama model metadata caching** (Redis TTL 1–60 seconds, 15 seconds by default). Prompts, private conversation data, memories, files, and JWTs are **never** cached.
- Added **context/output caps** for model resource safety. The context maximum defaults to 16,384 and generated output maximum to 2,048. A client request that exceeds a server cap receives HTTP 422. Global concurrent model generation is constrained by Redis admission.
- Added **low-cardinality API metrics** (successful/unsuccessful request counts, total duration, slow request count) and Redis queue metrics. Accessible only to authenticated admins at `GET /api/v1/admin/performance`, and shown in the Flutter admin screen. No user content or URL path is recorded.
- Added `013_performance_indexes.sql` with indexes for common conversation, history, memory, timeline and public-character queries. It **does not change or erase existing data**.
- Added a **bounded opt-in load probe** with health-check mode by default and explicit authenticated streaming mode. Avoid running against servers you do not administer.
- Added unit tests with a scripted Redis test double, plus a real Redis integration test that runs in GitHub Actions where Redis is available.

## Configuration and execution (only when you choose to run the app)

In `.env`:

```dotenv
INFERENCE_CONCURRENCY=2
INFERENCE_WAIT_SECONDS=20
INFERENCE_LEASE_SECONDS=120
INFERENCE_MAX_WAITERS=100
INFERENCE_MAX_CONTEXT=16384
INFERENCE_MAX_OUTPUT=2048
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=5
DATABASE_POOL_TIMEOUT=15
OLLAMA_CACHE_TTL_SECONDS=15
```

Compose provides `REDIS_URL=redis://redis:6379/0` internally. When starting the API directly, install `redis` from `backend/requirements.txt` and set `REDIS_URL` to your own protected Redis instance. A local single-process development API may omit `REDIS_URL` and will use the older local limiter. Production may not.

**Capacity planning:** The Redis concurrency limit is shared across all API workers. Each worker creates its own PostgreSQL pool, so estimate aggregate possible database connections as `workers * (pool_size + max_overflow)` and stay below database limits. AI model GPU memory is not automatically measured; choose limits for your actual models and hardware.

### Migration

Back up the database, then run `python backend/scripts/migrate.py` from the repository root using your own `DATABASE_URL`. This applies migration 013 if migrations 001–012 are already tracked. If the database has no migration ledger from old manual installs, follow `MIGRATIONS.md`; do not force baseline replay.

### Tests

From `backend/`: `python -m pytest -q` and `python -m compileall -q app`.

Full Redis Lua integration test requires `TEST_REDIS_URL`, the `redis` Python package, and a running Redis instance. GitHub Actions `backend-ci.yml` provisions a Redis service and enables this test. A Redis double tests algorithmic behavior offline, but cannot prove Lua integration.

### Controlled load probe

With a local API that **you control**:

```bash
python backend/loadtests/run_load.py --requests 40 --concurrency 4
```

Only if you explicitly want to exercise an inference model:

```bash
python backend/loadtests/run_load.py --mode stream --requests 4 --concurrency 2 --conversation-id YOUR_ID --token YOUR_JWT
```

Never place real tokens in shared logs or source. The probe allows at most 200 requests and 16 concurrent requests. It reports status counts and p50/p95/end-to-end latencies. Streaming can load your GPU significantly; begin with a few requests.

## Important remaining limitations

- No real Redis, PostgreSQL, Ollama, or Flutter runtime integration was verified in the source-generation environment. Redis packages could not be installed there because the package registry was unreachable. Offline tests were executed; live Redis CI checks must run in your own connected runner.
- Admission lease expiry prevents permanent starvation, but Redis failover, process stalls, network partitions and in-flight model streaming require production fault-injection tests. A lost lease is checked during token delivery and before persistence; active Ollama compute cannot be force-stopped on a remote instance just by losing a lock.
- Fixed-window limits have boundary bursts and operate primarily on client IP, not durable user identity. For a public app add authenticated quotas, CDN/edge controls, bot mitigation, credential abuse defenses and carefully configured trusted proxy IP handling.
- Redis caching is best-effort; Redis metrics reset when Redis restarts. Durable metrics, alerting and retention policies are not included.
- Database indexes can take locks during non-concurrent creation; plan an appropriate maintenance window for existing large databases.
- This is source preparation, not verified production readiness. Performance numbers and GPU resource limits depend on your actual host, models, and concurrency testing.


---

## Offline mode and synchronization (v1.8)

# Character Chat v1.8 — Offline Mode & Synchronization

## Overview

This source update extends v1.7 without deploying any service. The Flutter client stores previously opened character and conversation data as an **AES-256-GCM authenticated encrypted** snapshot. The per-account encryption key is stored with `flutter_secure_storage`, separate from the encrypted cache in `shared_preferences`. Local authentication uses a previously issued server token kept in secure storage, and **offline access expires when that token expires** (currently 12 hours). Users must authenticate online at least once, and the device/browser profile must remain trusted.

**Limitations:** On web, secure storage relies on the browser/platform's crypto facilities and browser profile security. This implementation does not provide biometric unlock, an end-to-end encrypted sync protocol, or protection against a fully compromised device. Signed-out account data and its encryption key are cleared locally. Local file and image content are not cached, and offline model inference, uploading media, account creation, group-speaker generation, and message edits are deliberately unavailable.

## What's cached

- Public character listings and previously opened character profiles.
- The signed-in user's owned character list and up to 100 recent conversations.
- Previously loaded conversation messages, including the selected branch.
- A bounded queue of safe local conversation metadata changes.

The cache is per account, encrypted as a whole, and limited to 130 distinct stored API responses. The content can grow with long chats; a future update should impose a byte-size limit and add cache eviction by total size.

## Safe offline editing

Only conversation **title** and **archived/unarchived** status may be queued offline. Destructive operations, messages, permissions, media changes, and AI generations require server access. The client queues at most 100 edits, assigns a UUID to each, stores them locally before any network attempt, and retries when a server connection is restored or on a manual sync request. Retry handling is idempotent on the server.

### Conflict detection

Each conversation has `metadata_revision` (starting at 0). Safe edits send `base_revision`, `operation_id`, and changed values to:

`POST /api/v1/sync/conversations/{id}/metadata`

An atomic compare-and-swap checks that the stored revision matches. On mismatch the server sends HTTP 409 with its latest metadata. **The client does not automatically overwrite this data**: the user chooses **Keep server** or **Apply my edits**. The latter creates fresh operation UUIDs rebased on the server revision. Deletes performed on another device are never automatically recreated. Successful operations receive an idempotency receipt in `sync_mutations`.

`GET /api/v1/sync/conversations/{id}` returns account-owned metadata for explicit comparison. Both endpoints require authentication and enforce ownership.

### Cross-device limitations

This synchronizes **server-owned conversation metadata**, not a general CRDT replicated database. Other devices see new titles and archived status after refetching their conversation list. Message text is always fetched from the authoritative server when online; cached messages are read-only and may be stale. Conflicts in fields outside title/archive use existing online-only API behavior. User logout discards that device's cached content and unsynced operations.

## Migration

`backend/migrations/014_offline_sync.sql` adds the `conversations.metadata_revision` column and `sync_mutations` table. Existing history remains unchanged. Use the checked migration runner, making a database backup before upgrading:

```bash
cd character_chat_starter
# DATABASE_URL must point to a backed-up PostgreSQL instance
python backend/scripts/migrate.py
python backend/scripts/migrate.py --verify-only
```

Never replay `001_` against an existing untracked production database. Consult `MIGRATIONS.md` for ledger adoption.

## Flutter dependencies

The `apps/client/pubspec.yaml` now includes `cryptography`, `flutter_secure_storage`, `shared_preferences`, and `uuid`. Run `flutter pub get` in a capable development environment. On Windows, web, Android, and iOS, verify secure-storage support and platform-specific provisioning before release. The source still needs actual Flutter compilation and plugin-integration tests.

## Verification

- Python regression tests: `PYTHONPATH=backend python -m pytest backend/tests -q`
- Migration verification in PostgreSQL CI: `.github/workflows/migration-ci.yml`
- Flutter widget tests: `flutter test` (not run in this environment)
- End-to-end test plan: log in online → load conversations/messages → disconnect → read cached messages → rename/archive → restart while token is valid → reconnect → sync → edit same chat on another device → review 409 conflict → choose keep server or rebase → log out and verify cache cleared.

The backend tests use mocks for sync races and validation, **not live multi-device PostgreSQL transactions**. Full deployment and production hardening are still outstanding.


---

## Database migrations and upgrade instructions

# Database migrations — v1.4

The repository includes sequential migrations `001`–`011`. Migrations `010` and `011` add images and voice assets. The v1.1 migration runner tracks SHA-256 checksums and applies new migrations transactionally. Do not use the baseline against an existing database without a migration ledger.

## Fresh, disposable development database

Set `DATABASE_URL` to your **own** PostgreSQL instance (and back up any existing data). With the backend Python dependencies installed:

```bash
python backend/scripts/migrate.py
python backend/scripts/migrate.py --verify-only
```

The runner obtains a PostgreSQL advisory lock, runs each unapplied migration inside a transaction, and commits a SHA-256 ledger entry in that same transaction. Rerunning it verifies checksums and skips previously applied migrations. If any old migration is modified, verification fails rather than attempting a repair.

## Existing v0.9 installation upgraded manually

**Do not run the fresh-database migration command on an existing v0.9 database** that has no `schema_migrations` ledger: it would attempt the `001` baseline on an existing schema. Retain the original manual migration workflow until an audited baseline/adoption process has been completed. Take a database backup before any changes. The migration CI workflow exercises a new disposable database, not conversion of an existing v0.9 production database.

The backend still calls `Base.metadata.create_all()` on app startup for development convenience; it does **not** alter existing columns or replace migrations. On deployed installations, use the migration runner before starting the API and remove that bootstrap convenience.

## CI

`bash scripts/verify-migrations.sh` runs initial migration, checksum verification, an idempotent rerun, then schema and API smoke tests against a temporary PostgreSQL service. This is separate from Python unit tests, which do not require a running PostgreSQL instance.

## v1.5
`012_story_engine.sql` adds private conversation-scoped story entities and user-owned scenario templates. Apply through the tracked migration runner after backup.

## v1.7 — Performance indexes

`013_performance_indexes.sql` adds composite/partial indexes for recent user conversations, archived chats, messages, learned memories, story timeline and public discovery. It is fully additive and tracked by the existing transactional migration runner. On large databases, index creation can block writes; plan a maintenance window. This migration is required for the recommended query plan but Redis itself requires no SQL schema changes.

## v1.8

`014_offline_sync.sql` introduces optimistic conversation metadata revisions and the idempotent `sync_mutations` ledger. Apply with the transactional migration runner after backing up PostgreSQL.


---

## Piper voice-model installation

Place a compatible Piper `voice.onnx` and `voice.onnx.json` pair here for the default voice. Additional voices use `<voice_id>.onnx` and `<voice_id>.onnx.json`; include each voice ID in `VOICE_IDS` in `.env`. Download models from the Piper voice project and review individual voice licenses. Models are not bundled.
