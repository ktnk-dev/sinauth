from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


DEFAULT_SCOPE = "default"


def utcnow() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class UserRecord:
    username: str
    password_hash: str
    id: str = field(default_factory=lambda: str(uuid4()))
    permissions: list[str] = field(default_factory=list)
    collections: dict[str, dict[str, Any]] = field(default_factory=dict)
    disabled: bool = False
    created_at: str = field(default_factory=utcnow)
    updated_at: str = field(default_factory=utcnow)


def validate_name(value: str, field_name: str) -> str:
    if not value or not value.strip():
        raise ValueError(f"{field_name} must not be empty")
    value = value.strip()
    if len(value) > 128:
        raise ValueError(f"{field_name} must be 128 characters or less")
    return value


def validate_service(value: str) -> str:
    value = validate_name(value, "service")
    if value != DEFAULT_SCOPE and not all(ch.isalnum() or ch in "._-" for ch in value):
        raise ValueError("service may contain only letters, digits, dot, underscore and dash")
    return value


class LoginRequest(BaseModel):
    username: str
    password: str
    service: str = DEFAULT_SCOPE

    @field_validator("username")
    @classmethod
    def _username(cls, value: str) -> str:
        return validate_name(value, "username")

    @field_validator("service")
    @classmethod
    def _service(cls, value: str) -> str:
        return validate_service(value)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: int


class UserExistsOut(BaseModel):
    exists: bool


class ApiRegisterRequest(BaseModel):
    login: str
    password: str = Field(min_length=1)
    display_name: str
    profile_picture_url: str | None = None
    service: str = DEFAULT_SCOPE

    @field_validator("login")
    @classmethod
    def _login(cls, value: str) -> str:
        return validate_name(value, "login")

    @field_validator("display_name")
    @classmethod
    def _display_name(cls, value: str) -> str:
        return validate_name(value, "display_name")

    @field_validator("profile_picture_url")
    @classmethod
    def _profile_picture_url(cls, value: str | None) -> str | None:
        return validate_redirect_url(value) if value else None

    @field_validator("service")
    @classmethod
    def _service(cls, value: str) -> str:
        return validate_service(value)


class UserCreate(BaseModel):
    username: str
    password: str = Field(min_length=1)
    permissions: list[str] = Field(default_factory=list)
    collections: dict[str, dict[str, Any]] = Field(default_factory=dict)
    disabled: bool = False

    @field_validator("username")
    @classmethod
    def _username(cls, value: str) -> str:
        return validate_name(value, "username")

    @field_validator("collections")
    @classmethod
    def _collections(cls, value: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
        for service in value:
            validate_service(service)
        return value


class UserPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    password: str | None = Field(default=None, min_length=1)
    permissions: list[str] | None = None
    collections: dict[str, dict[str, Any]] | None = None
    disabled: bool | None = None

    @field_validator("collections")
    @classmethod
    def _collections(
        cls, value: dict[str, dict[str, Any]] | None
    ) -> dict[str, dict[str, Any]] | None:
        if value is not None:
            for service in value:
                validate_service(service)
        return value


class UserOut(BaseModel):
    id: str
    username: str
    display_name: str | None = None
    profile_picture_url: str | None = None
    permissions: list[str]
    collections: dict[str, dict[str, Any]]
    disabled: bool
    created_at: str
    updated_at: str


class CollectionPut(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)


class AuthContext(BaseModel):
    username: str
    service: str
    user: UserOut


def validate_redirect_url(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("redirect url must not be empty")
    if len(value) > 2048:
        raise ValueError("redirect url must be 2048 characters or less")
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("redirect url must be an absolute http or https URL")
    return value


class WebAuthorizeSessionCreate(BaseModel):
    service: str = DEFAULT_SCOPE
    on_success_redirect: str
    on_error_redirect: str | None = None
    expires_in_seconds: int | None = Field(default=None, ge=60, le=3600)

    @field_validator("service")
    @classmethod
    def _service(cls, value: str) -> str:
        return validate_service(value)

    @field_validator("on_success_redirect", "on_error_redirect")
    @classmethod
    def _redirect(cls, value: str | None) -> str | None:
        return validate_redirect_url(value) if value is not None else None


class WebAuthorizeSessionOut(BaseModel):
    authorize_url: str
    expires_at: int
