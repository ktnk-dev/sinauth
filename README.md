# sinauth

Small FastAPI authorization service with a pickle-backed store.

## Run locally

```bash
uv sync
uv run uvicorn sinauth.main:app --reload
```

The service creates a default admin on first start:

- username: `ADMIN_USERNAME`, default `admin`
- password: `ADMIN_PASSWORD`, default `admin`
- permissions: `["*"]`

Set `AUTH_SECRET` before using real data. Tokens are signed with this secret.
Registration is enabled by default. Set `REGISTRATION_ENABLED=false` to disable it.
Set `SERVICE_NAME` to change the Swagger title and the hosted login page name.

Users have a generated UUIDv4 `id`. It is created when the account is created
and returned in user API responses.
If `collections.default` contains `display_name` and `profile_picture_url`,
they are also returned as top-level user fields next to `id` and `username`.

Requests for known secret/config paths such as `.env`, `.git`, SSH keys, SQL
dumps and common config backups permanently ban the caller IP. Banned IPs are
stored in the pickle file and receive `403` on every route.

## Docker Compose

```bash
AUTH_SECRET='replace-this' ADMIN_PASSWORD='replace-this-too' docker compose up --build
```

Data is stored in the `sinauth-data` volume at `/data/sinauth.pkl`.

## Permissions

Permissions are strings:

- `*` allows everything.
- `users.read`, `users.create`, `users.update`, `users.delete`.
- `permissions.manage` allows changing another user's permissions.
- `collections.write:<service>` allows editing another user's service collection.
- `collections.write:*` allows editing all service collections.

The scope separator is `:`. The default collection/scope is `default`.

Examples:

```json
["users.read:default", "users.create:default", "collections.write:billing"]
```

Unscoped values like `users.read` also work and mean the default scope.

## Service collections

A login request includes `service`. The token is bound to that service.

```bash
curl -s http://localhost:8000/authorize/api/login \
  -H 'content-type: application/json' \
  -d '{"username":"admin","password":"admin","service":"default"}'
```

If a token was issued for service `billing`, API responses expose only:

- the default collection `default`
- the `billing` collection

This keeps a service from seeing another service's collection.

Update the current user's current-service collection:

```bash
curl -X PUT http://localhost:8000/me/collections/billing \
  -H "authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' \
  -d '{"data":{"plan":"pro","customer_id":"cus_123"}}'
```

## User API

Create a user:

```bash
curl -X POST http://localhost:8000/users \
  -H "authorization: Bearer $ADMIN_TOKEN" \
  -H 'content-type: application/json' \
  -d '{
    "username": "alice",
    "password": "secret",
    "permissions": ["users.read:default"],
    "collections": {
      "default": {"display_name": "Alice"}
    }
  }'
```

Patch a user:

```bash
curl -X PATCH http://localhost:8000/users/alice \
  -H "authorization: Bearer $ADMIN_TOKEN" \
  -H 'content-type: application/json' \
  -d '{"disabled": false, "permissions": ["users.read:default"]}'
```

Delete a user:

```bash
curl -X DELETE http://localhost:8000/users/alice \
  -H "authorization: Bearer $ADMIN_TOKEN"
```

## Browser authorization

A service can create a temporary browser authorization link. This endpoint is public:

```bash
curl -X POST http://localhost:8000/authorize/web/sessions \
  -H 'content-type: application/json' \
  -d '{
    "service": "billing",
    "on_success_redirect": "https://billing.example/auth/success",
    "on_error_redirect": "https://billing.example/auth/error"
  }'
```

The response contains:

```json
{
  "authorize_url": "http://localhost:8000/authorize/web/<temporary-token>",
  "expires_at": 1794140000
}
```

Open `authorize_url` in the browser. It serves the files from `sinauth/web/`.
The page uses the regular `/authorize/api/login` and `/authorize/api/register`
endpoints, passing the service from the temporary web link.

On successful login or registration, the user is redirected to `on_success_redirect` with:

- `access_token`
- `token_type`
- `expires_at`
- `username`
- `service`

On failed login/registration, the user is redirected to `on_error_redirect` with:

- `error`
- `error_description`

Registration creates a user with no permissions and this default collection:

```json
{
  "default": {
    "display_name": "Alice",
    "profile_picture_url": "https://example.com/alice.png"
  }
}
```

Disable registration:

```bash
REGISTRATION_ENABLED=false docker compose up --build
```

## Authorization API

Login:

```bash
curl -s http://localhost:8000/authorize/api/login \
  -H 'content-type: application/json' \
  -d '{"username":"alice","password":"secret","service":"billing"}'
```

Register:

```bash
curl -X POST http://localhost:8000/authorize/api/register \
  -H 'content-type: application/json' \
  -d '{
    "login": "alice",
    "password": "secret",
    "display_name": "Alice",
    "profile_picture_url": "https://example.com/alice.png",
    "service": "billing"
  }'
```

Registration returns a bearer token on success and is disabled when
`REGISTRATION_ENABLED=false`.

Check whether a user exists by login or user id:

```bash
curl -s http://localhost:8000/authorize/api/users/exists/alice
curl -s http://localhost:8000/authorize/api/users/exists/0f3cefa2-7d4c-4381-a899-2a0f2c910857
```

Response:

```json
{"exists": true}
```
