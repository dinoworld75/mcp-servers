"""
LinkedIn MCP Server
Scrape LinkedIn profiles and company pages
With Basic Auth protection
"""

import os
import base64
import httpx
from fastmcp import FastMCP

# Auth credentials from env or defaults
AUTH_USERNAME = os.environ.get("AUTH_USERNAME", "ackizit")
AUTH_PASSWORD = os.environ.get("AUTH_PASSWORD", "!Lam3ute!75")

# Create MCP server
mcp = FastMCP("LinkedIn Scraper")

# Internal API auth
BASIC_AUTH = "YWNraXppdDohTGFtM3V0ZSE3NQ=="
HEADERS = {
    "Authorization": f"Basic {BASIC_AUTH}",
    "Content-Type": "application/json"
}


class BasicAuthMiddleware:
    """ASGI middleware for Basic Auth."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
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


@mcp.tool
async def linkedin_profile(url: str) -> dict:
    """
    Extrait les informations d'un profil LinkedIn.

    Args:
        url: URL du profil LinkedIn (ex: linkedin.com/in/john-doe)

    Returns:
        Infos du profil: nom, company, company_url, location, etc.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        api_url = f"https://scrap-lk-profile.lasupermachine.fr/api/extract?url={url}&method=combined"
        response = await client.get(api_url, headers=HEADERS)

        if response.status_code != 200:
            return {"error": f"HTTP {response.status_code}", "details": response.text}

        data = response.json()
        profile = data.get("profile", {})

        return {
            "name": profile.get("name"),
            "company": profile.get("company"),
            "company_url": profile.get("company_url"),
            "location": profile.get("location"),
            "headline": profile.get("headline"),
            "raw": profile
        }


@mcp.tool
async def linkedin_company(url: str, timeout: int = 25) -> dict:
    """
    Extrait les informations d'une page company LinkedIn.

    Args:
        url: URL de la page company LinkedIn
        timeout: Timeout en secondes (défaut: 25)

    Returns:
        Infos de l'entreprise: nom, website, adresse, code postal, etc.
    """
    async with httpx.AsyncClient(timeout=float(timeout) + 5) as client:
        api_url = "https://scrap-lk-company.lasupermachine.fr/api/scrape"
        payload = {"url": url, "timeout": timeout}

        response = await client.post(api_url, json=payload, headers=HEADERS)

        if response.status_code != 200:
            return {"error": f"HTTP {response.status_code}", "details": response.text}

        data = response.json()

        return {
            "company_name": data.get("company_name"),
            "website": data.get("website"),
            "postal_code": data.get("postal_code"),
            "headquarters": data.get("headquarters"),
            "industry": data.get("industry"),
            "company_size": data.get("company_size"),
            "locations_secondary": data.get("locations_secondary", []),
            "raw": data
        }


def create_authenticated_app():
    """Wrap FastMCP app with Basic Auth middleware."""
    mcp_app = mcp.http_app(path="/mcp")
    return BasicAuthMiddleware(mcp_app)


# For uvicorn: uvicorn server:app --host 0.0.0.0 --port 8080
app = create_authenticated_app()
