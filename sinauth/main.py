from __future__ import annotations

import json
from pathlib import Path as FilePath
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Path, Request, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
import uvicorn

from sinauth.config import Settings, load_settings
from sinauth.models import (
    ApiRegisterRequest,
    AuthContext,
    CollectionPut,
    DEFAULT_SCOPE,
    LoginRequest,
    TokenResponse,
    UserCreate,
    UserExistsOut,
    UserOut,
    UserPatch,
    UserRecord,
    WebAuthorizeSessionCreate,
    WebAuthorizeSessionOut,
    validate_service,
)
from sinauth.permissions import (
    has_permission,
    require_collections_visible,
    require_service_visible,
    visible_collections,
)
from sinauth.security import create_signed_payload, create_token, decode_signed_payload, decode_token
from sinauth.security import verify_password
from sinauth.storage import PickleStore


WEB_DIR = FilePath(__file__).resolve().parent / "web"
settings = load_settings()
store = PickleStore(settings.data_path)
store.ensure_admin(settings.admin_username, settings.admin_password)
bearer = HTTPBearer()

app = FastAPI(title=settings.service_name, version="0.1.0")

TAG_AUTHORIZATION = "Authorization"
TAG_SERVICE_COLLECTIONS = "Service Collections"
TAG_USERS = "Users"
TAG_SYSTEM = "System"

app.mount("/authorize/web/assets", StaticFiles(directory=WEB_DIR), name="web-assets")


def record_to_out(user: UserRecord, *, token_service: str = DEFAULT_SCOPE) -> UserOut:
    default_collection = user.collections.get(DEFAULT_SCOPE, {})
    display_name = default_collection.get("display_name")
    profile_picture_url = default_collection.get("profile_picture_url")
    return UserOut(
        id=user.id,
        username=user.username,
        display_name=display_name if isinstance(display_name, str) else None,
        profile_picture_url=profile_picture_url if isinstance(profile_picture_url, str) else None,
        permissions=list(user.permissions),
        collections=visible_collections(user.collections, token_service=token_service),
        disabled=user.disabled,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


def get_settings() -> Settings:
    return settings


def get_store() -> PickleStore:
    return store


def auth_context(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer)],
    config: Annotated[Settings, Depends(get_settings)],
    db: Annotated[PickleStore, Depends(get_store)],
) -> AuthContext:
    try:
        payload = decode_token(credentials.credentials, config.auth_secret)
    except ValueError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc

    username = str(payload["sub"])
    service = validate_service(str(payload["service"]))
    user = db.get_user(username)
    if user is None or user.disabled:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user is disabled or does not exist")

    return AuthContext(username=username, service=service, user=record_to_out(user))


def current_record(ctx: AuthContext, db: PickleStore) -> UserRecord:
    user = db.get_user(ctx.username)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user does not exist")
    return user


def require_permission(
    ctx: AuthContext,
    db: PickleStore,
    action: str,
    scope: str = DEFAULT_SCOPE,
) -> None:
    user = current_record(ctx, db)
    if not has_permission(user, action, scope):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"missing permission {action}:{scope}",
        )


def ensure_collection_visible(ctx: AuthContext, service: str) -> None:
    try:
        require_service_visible(ctx.service, service)
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc


def ensure_collections_visible(ctx: AuthContext, collections: dict[str, dict]) -> None:
    try:
        require_collections_visible(ctx.service, set(collections))
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc


def web_flow_payload(web_token: str, config: Settings) -> dict:
    try:
        payload = decode_signed_payload(web_token, config.auth_secret)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    if payload.get("typ") != "web_authorize":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid web authorization token")
    return payload


def issue_access_token(user: UserRecord, service: str, config: Settings) -> TokenResponse:
    token, expires_at = create_token(
        username=user.username,
        service=service,
        secret=config.auth_secret,
        ttl_seconds=config.token_ttl_seconds,
    )
    return TokenResponse(access_token=token, expires_at=expires_at)


def default_profile_collection(display_name: str, profile_picture_url: str | None) -> dict:
    return {
        "display_name": display_name,
        "profile_picture_url": profile_picture_url,
    }


@app.get("/health", tags=[TAG_SYSTEM])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/authorize/api/login", response_model=TokenResponse, tags=[TAG_AUTHORIZATION])
def login(
    payload: LoginRequest,
    config: Annotated[Settings, Depends(get_settings)],
    db: Annotated[PickleStore, Depends(get_store)],
) -> TokenResponse:
    user = db.get_user(payload.username)
    if user is None or user.disabled or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid username or password")
    return issue_access_token(user, payload.service, config)


@app.post(
    "/authorize/api/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    tags=[TAG_AUTHORIZATION],
)
def register(
    payload: ApiRegisterRequest,
    config: Annotated[Settings, Depends(get_settings)],
    db: Annotated[PickleStore, Depends(get_store)],
) -> TokenResponse:
    if not config.registration_enabled:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "registration is disabled")
    try:
        user = db.create_user(
            username=payload.login,
            password=payload.password,
            permissions=[],
            collections={
                DEFAULT_SCOPE: default_profile_collection(
                    payload.display_name,
                    payload.profile_picture_url,
                )
            },
            disabled=False,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return issue_access_token(user, payload.service, config)


@app.get(
    "/authorize/api/users/exists/{identifier}",
    response_model=UserExistsOut,
    tags=[TAG_AUTHORIZATION],
)
def user_exists(
    identifier: str,
    db: Annotated[PickleStore, Depends(get_store)],
) -> UserExistsOut:
    return UserExistsOut(exists=db.user_exists(identifier))


@app.post(
    "/authorize/web/sessions",
    response_model=WebAuthorizeSessionOut,
    tags=[TAG_AUTHORIZATION],
)
def create_web_authorize_session(
    payload: WebAuthorizeSessionCreate,
    request: Request,
    config: Annotated[Settings, Depends(get_settings)],
) -> WebAuthorizeSessionOut:
    web_token, expires_at = create_signed_payload(
        payload={
            "typ": "web_authorize",
            "service": payload.service,
            "on_success_redirect": payload.on_success_redirect,
            "on_error_redirect": payload.on_error_redirect,
        },
        secret=config.auth_secret,
        ttl_seconds=payload.expires_in_seconds or config.web_auth_token_ttl_seconds,
    )
    return WebAuthorizeSessionOut(
        authorize_url=str(request.url_for("get_web_authorize_page", web_token=web_token)),
        expires_at=expires_at,
    )


@app.get("/authorize/web/{web_token}", response_class=HTMLResponse, tags=[TAG_AUTHORIZATION])
def get_web_authorize_page(
    web_token: str,
    config: Annotated[Settings, Depends(get_settings)],
) -> HTMLResponse:
    flow = web_flow_payload(web_token, config)
    index_path = WEB_DIR / "index.html"
    page = index_path.read_text(encoding="utf-8")
    page_config = {
        "serviceName": config.service_name,
        "service": flow["service"],
        "onSuccessRedirect": flow["on_success_redirect"],
        "onErrorRedirect": flow.get("on_error_redirect"),
        "registrationEnabled": config.registration_enabled,
    }
    page = page.replace(
        "{{SINAUTH_WEB_AUTH_CONFIG}}",
        json.dumps(page_config, separators=(",", ":")),
    )
    return HTMLResponse(page)


@app.get("/me", response_model=UserOut, tags=[TAG_AUTHORIZATION])
def me(
    ctx: Annotated[AuthContext, Depends(auth_context)],
    db: Annotated[PickleStore, Depends(get_store)],
) -> UserOut:
    user = current_record(ctx, db)
    return record_to_out(user, token_service=ctx.service)


@app.get("/me/collections", tags=[TAG_SERVICE_COLLECTIONS])
def my_collections(
    ctx: Annotated[AuthContext, Depends(auth_context)],
    db: Annotated[PickleStore, Depends(get_store)],
) -> dict[str, dict]:
    user = current_record(ctx, db)
    return visible_collections(user.collections, token_service=ctx.service)


@app.put("/me/collections/{service_name}", response_model=UserOut, tags=[TAG_SERVICE_COLLECTIONS])
def put_my_collection(
    service_name: Annotated[str, Path()],
    payload: CollectionPut,
    ctx: Annotated[AuthContext, Depends(auth_context)],
    db: Annotated[PickleStore, Depends(get_store)],
) -> UserOut:
    service = validate_service(service_name)
    ensure_collection_visible(ctx, service)
    if service == DEFAULT_SCOPE:
        require_permission(ctx, db, "collections.write", DEFAULT_SCOPE)
    user = db.put_collection(ctx.username, service, payload.data)
    return record_to_out(user, token_service=ctx.service)


@app.post(
    "/users",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    tags=[TAG_USERS],
)
def create_user(
    payload: UserCreate,
    ctx: Annotated[AuthContext, Depends(auth_context)],
    db: Annotated[PickleStore, Depends(get_store)],
) -> UserOut:
    require_permission(ctx, db, "users.create")
    ensure_collections_visible(ctx, payload.collections)
    try:
        user = db.create_user(
            username=payload.username,
            password=payload.password,
            permissions=payload.permissions,
            collections=payload.collections,
            disabled=payload.disabled,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return record_to_out(user, token_service=ctx.service)


@app.get("/users", response_model=list[UserOut], tags=[TAG_USERS])
def list_users(
    ctx: Annotated[AuthContext, Depends(auth_context)],
    db: Annotated[PickleStore, Depends(get_store)],
) -> list[UserOut]:
    require_permission(ctx, db, "users.read")
    return [record_to_out(user, token_service=ctx.service) for user in db.list_users()]


@app.get("/users/{username}", response_model=UserOut, tags=[TAG_USERS])
def get_user(
    username: str,
    ctx: Annotated[AuthContext, Depends(auth_context)],
    db: Annotated[PickleStore, Depends(get_store)],
) -> UserOut:
    require_permission(ctx, db, "users.read")
    user = db.get_user(username)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
    return record_to_out(user, token_service=ctx.service)


@app.patch("/users/{username}", response_model=UserOut, tags=[TAG_USERS])
def update_user(
    username: str,
    payload: UserPatch,
    ctx: Annotated[AuthContext, Depends(auth_context)],
    db: Annotated[PickleStore, Depends(get_store)],
) -> UserOut:
    require_permission(ctx, db, "users.update")
    patch = payload.model_dump(exclude_unset=True)
    if "permissions" in patch:
        require_permission(ctx, db, "permissions.manage")
    if "collections" in patch:
        ensure_collections_visible(ctx, patch["collections"])
    try:
        user = db.update_user(username, **patch)
    except KeyError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found") from exc
    return record_to_out(user, token_service=ctx.service)


@app.delete("/users/{username}", status_code=status.HTTP_204_NO_CONTENT, tags=[TAG_USERS])
def delete_user(
    username: str,
    ctx: Annotated[AuthContext, Depends(auth_context)],
    db: Annotated[PickleStore, Depends(get_store)],
) -> None:
    require_permission(ctx, db, "users.delete")
    try:
        db.delete_user(username)
    except KeyError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found") from exc


@app.get("/users/{username}/collections", tags=[TAG_SERVICE_COLLECTIONS])
def get_user_collections(
    username: str,
    ctx: Annotated[AuthContext, Depends(auth_context)],
    db: Annotated[PickleStore, Depends(get_store)],
) -> dict[str, dict]:
    require_permission(ctx, db, "users.read")
    user = db.get_user(username)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
    return visible_collections(user.collections, token_service=ctx.service)


@app.get("/users/{username}/collections/{service_name}", tags=[TAG_SERVICE_COLLECTIONS])
def get_user_collection(
    username: str,
    service_name: Annotated[str, Path()],
    ctx: Annotated[AuthContext, Depends(auth_context)],
    db: Annotated[PickleStore, Depends(get_store)],
) -> dict:
    service = validate_service(service_name)
    ensure_collection_visible(ctx, service)
    require_permission(ctx, db, "users.read")
    user = db.get_user(username)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
    return user.collections.get(service, {})


@app.put(
    "/users/{username}/collections/{service_name}",
    response_model=UserOut,
    tags=[TAG_SERVICE_COLLECTIONS],
)
def put_user_collection(
    username: str,
    service_name: Annotated[str, Path()],
    payload: CollectionPut,
    ctx: Annotated[AuthContext, Depends(auth_context)],
    db: Annotated[PickleStore, Depends(get_store)],
) -> UserOut:
    service = validate_service(service_name)
    ensure_collection_visible(ctx, service)
    if username != ctx.username or service != ctx.service:
        require_permission(ctx, db, "collections.write", service)
    try:
        user = db.put_collection(username, service, payload.data)
    except KeyError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found") from exc
    return record_to_out(user, token_service=ctx.service)


def create_app() -> FastAPI:
    return app


def run() -> None:
    uvicorn.run("sinauth.main:app", host=settings.host, port=settings.port, reload=False)
