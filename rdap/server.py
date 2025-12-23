"""
RDAP/WHOIS MCP Server
Query domain registration data
With Basic Auth protection
"""

import os
import base64
import httpx
from fastmcp import FastMCP

AUTH_USERNAME = os.environ.get("AUTH_USERNAME", "ackizit")
AUTH_PASSWORD = os.environ.get("AUTH_PASSWORD", "!Lam3ute!75")

mcp = FastMCP("RDAP WHOIS")

# Internal API auth
INTERNAL_AUTH = "YWNraXppdDohTGFtM3V0ZSE3NQ=="
INTERNAL_HEADERS = {"Authorization": f"Basic {INTERNAL_AUTH}"}


class BasicAuthMiddleware:
    """ASGI middleware for Basic Auth."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Allow healthcheck on root path without auth
        path = scope.get("path", "")
        if path == "/" or path == "":
            await self._send_health(send)
            return

        headers = dict(scope.get("headers", []))
        auth_header = headers.get(b"authorization", b"").decode("utf-8")

        if not auth_header.startswith("Basic "):
            await self._send_401(send)
            return

        try:
            encoded = auth_header[6:]
            decoded = base64.b64decode(encoded).decode("utf-8")
            username, password = decoded.split(":", 1)

            if username != AUTH_USERNAME or password != AUTH_PASSWORD:
                await self._send_401(send)
                return
        except Exception:
            await self._send_401(send)
            return

        await self.app(scope, receive, send)

    async def _send_401(self, send):
        await send({
            "type": "http.response.start",
            "status": 401,
            "headers": [
                [b"content-type", b"application/json"],
                [b"www-authenticate", b'Basic realm="MCP Server"']
            ]
        })
        await send({
            "type": "http.response.body",
            "body": b'{"error": "Unauthorized"}'
        })

    async def _send_health(self, send):
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [[b"content-type", b"application/json"]]
        })
        await send({
            "type": "http.response.body",
            "body": b'{"status": "ok"}'
        })


@mcp.tool
async def rdap_whois(domain: str) -> dict:
    """
    Interroge les données RDAP/WHOIS d'un domaine.

    Note: Fonctionne surtout pour les .fr (AFNIC expose les données).
    Les .com ont souvent le WHOIS masqué (GDPR).

    Args:
        domain: Nom de domaine à interroger (ex: example.fr)

    Returns:
        Infos registrant: organisation, adresse, email
    """
    async with httpx.AsyncClient(timeout=15.0) as client:
        api_url = f"https://rdap.lasupermachine.fr/api/whois?domain={domain}"

        response = await client.get(api_url, headers=INTERNAL_HEADERS)

        if response.status_code != 200:
            return {"error": f"HTTP {response.status_code}", "details": response.text}

        data = response.json()

        return {
            "registrant_organization": data.get("registrant_organization"),
            "registrant_name": data.get("registrant_name"),
            "registrant_address": data.get("registrant_address"),
            "registrant_email": data.get("registrant_email"),
            "registrar": data.get("registrar"),
            "creation_date": data.get("creation_date"),
            "expiration_date": data.get("expiration_date"),
            "raw": data
        }


def create_authenticated_app():
    """Wrap FastMCP app with Basic Auth middleware."""
    mcp_app = mcp.http_app(path="/mcp")
    return BasicAuthMiddleware(mcp_app)


app = create_authenticated_app()
