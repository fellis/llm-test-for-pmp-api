# Admin panel and repositories

## Repo separation

| Repo | Contents |
|------|----------|
| **Admin panel** | Only the admin app code: UI (chat, TODO, code preview, Publish). No user-generated content or artifacts. |
| **Target repo** | User-generated output: branches, commits, PRs with widgets, components, customizations (e.g. main app repo or dedicated `user-customizations` repo). |

Generated content must never be committed to the admin panel repo.

## Flow

1. User works in the admin panel (chat, stream, preview).
2. Generated code is shown in the UI (session/temporary state only).
3. On **Publish**, the admin (or orchestrator) uses the **target repo**: clone/pull, create branch, commit generated files, open PR there.
4. The admin panel repo stays unchanged; only the target repo receives the new code.

## Local development

The admin panel must run and work **locally** (e.g. `npm run dev`), not only in Docker on the server. For local runs, the app connects to the LLM API via an env var (e.g. `VITE_LLM_API_URL`), pointing to the public API or to `http://localhost:8000` if pmp-llm is running locally. No Docker required for day-to-day development.

## LLM API auth

The public LLM (`https://llm.aegisalpha.io`) requires **Bearer token** for `/v1/models` and `/v1/chat/completions`. Tokens are listed in **SERVER.md** (section "API auth tokens") or in `api/auth.json` on the server. The admin panel orchestrator sends the token from `LLM_AUTH_TOKEN` in `.env`. Request format: header `Authorization: Bearer <token>`. See **API_BY_DOMAIN.md** in the repo root for curl examples.

## Summary

- **Admin repo** = code of the admin application only.
- **Target repo** = where generated user artifacts go (separate repo, configured at deploy time).
- **Local** = admin runs and works on dev machine; API URL configurable via env.
