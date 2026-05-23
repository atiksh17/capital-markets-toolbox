import json
from ipaddress import ip_address, ip_network
from typing import Iterable

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class TokenEntry(BaseModel):
    name: str
    token: str
    ip_allow: list[str] = []

    def matches_ip(self, client_ip: str) -> bool:
        if not self.ip_allow:
            return True
        try:
            ip = ip_address(client_ip)
        except ValueError:
            return False
        for cidr in self.ip_allow:
            try:
                if ip in ip_network(cidr, strict=False):
                    return True
            except ValueError:
                continue
        return False


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env.prod", ".env.local", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    pg_dsn: str
    tokens_json: str = ""
    bearer_tokens: str = ""
    allowed_schemas: str = "public"
    default_limit: int = 100
    max_limit: int = 10000
    log_level: str = "info"
    log_full_sql: bool = False
    host: str = "0.0.0.0"
    port: int = 8000

    # OAuth
    public_base_url: str = "https://mcp.nubeam.io"
    jwt_secret: str = ""
    jwt_issuer: str = "https://mcp.nubeam.io"
    jwt_audience: str = "https://mcp.nubeam.io/mcp"
    access_token_ttl_seconds: int = 24 * 3600
    auth_code_ttl_seconds: int = 120

    @property
    def schema_set(self) -> set[str]:
        return {s.strip() for s in self.allowed_schemas.split(",") if s.strip()}

    @property
    def token_entries(self) -> list[TokenEntry]:
        if self.tokens_json.strip():
            data = json.loads(self.tokens_json)
            return [TokenEntry(**e) for e in data]
        names = [t.strip() for t in self.bearer_tokens.split(",") if t.strip()]
        return [TokenEntry(name=f"token{i}", token=t) for i, t in enumerate(names)]

    @property
    def token_map(self) -> dict[str, TokenEntry]:
        return {e.token: e for e in self.token_entries}


settings = Settings()
