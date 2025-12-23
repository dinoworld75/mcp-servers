"""
SIRET Extractor MCP Server
Extract SIRET from website legal pages
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

mcp = FastMCP("SIRET Extractor")

# Internal API auth
INTERNAL_AUTH = "YWNraXppdDohTGFtM3V0ZSE3NQ=="
INTERNAL_HEADERS = {
    "Authorization": f"Basic {INTERNAL_AUTH}",
    "Content-Type": "application/json"
}


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
async def siret_extractor(url: str) -> dict:
    """
    Extrait le SIRET des mentions légales d'un site web.

    Args:
        url: URL du site web à analyser

    Returns:
        SIRET, SIREN et TVA si trouvés (~38% des sites les publient)
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        api_url = "https://siretextractor.lasupermachine.fr/api/extract"
        payload = {"url": url}

        response = await client.post(api_url, json=payload, headers=INTERNAL_HEADERS)

        if response.status_code != 200:
            return {"error": f"HTTP {response.status_code}", "details": response.text}

        data = response.json()

        return {
            "found": data.get("found", False),
            "siret": data.get("siret"),
            "siren": data.get("siren"),
            "tva": data.get("tva"),
            "source_page": data.get("source_page"),
            "raw": data
        }


def create_authenticated_app():
    mcp_app = mcp.http_app(path="/mcp")
    app = Starlette(
        routes=[Mount("/", app=mcp_app)],
        middleware=[Middleware(BasicAuthMiddleware)]
    )
    return app


app = create_authenticated_app()
