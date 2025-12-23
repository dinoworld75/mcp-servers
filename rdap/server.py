"""
RDAP/WHOIS MCP Server
Query domain registration data
With Basic Auth protection
"""

import os
import base64
import httpx
from fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.routing import Mount

AUTH_USERNAME = os.environ.get("AUTH_USERNAME", "ackizit")
AUTH_PASSWORD = os.environ.get("AUTH_PASSWORD", "!Lam3ute!75")

mcp = FastMCP("RDAP WHOIS")

# Internal API auth
INTERNAL_AUTH = "YWNraXppdDohTGFtM3V0ZSE3NQ=="
INTERNAL_HEADERS = {"Authorization": f"Basic {INTERNAL_AUTH}"}


class BasicAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        auth_header = request.headers.get("Authorization", "")

        if not auth_header.startswith("Basic "):
            return Response(
                content='{"error": "Unauthorized - Basic Auth required"}',
                status_code=401,
                media_type="application/json",
                headers={"WWW-Authenticate": 'Basic realm="MCP Server"'}
            )

        try:
            encoded = auth_header[6:]
            decoded = base64.b64decode(encoded).decode("utf-8")
            username, password = decoded.split(":", 1)

            if username != AUTH_USERNAME or password != AUTH_PASSWORD:
                return Response(
                    content='{"error": "Invalid credentials"}',
                    status_code=401,
                    media_type="application/json",
                    headers={"WWW-Authenticate": 'Basic realm="MCP Server"'}
                )
        except Exception:
            return Response(
                content='{"error": "Invalid Authorization header"}',
                status_code=401,
                media_type="application/json",
                headers={"WWW-Authenticate": 'Basic realm="MCP Server"'}
            )

        return await call_next(request)


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
    mcp_app = mcp.http_app()
    app = Starlette(
        routes=[Mount("/mcp", app=mcp_app)],
        middleware=[Middleware(BasicAuthMiddleware)]
    )
    return app


app = create_authenticated_app()
