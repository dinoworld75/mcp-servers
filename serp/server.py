"""
SERP MCP Server
Google search with specialized queries
With Basic Auth protection
"""

import os
import base64
import httpx
import re
from fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.routing import Mount

AUTH_USERNAME = os.environ.get("AUTH_USERNAME", "ackizit")
AUTH_PASSWORD = os.environ.get("AUTH_PASSWORD", "!Lam3ute!75")

mcp = FastMCP("SERP Search")

SERP_API_KEY = "089e2741-9760-4b19-90d3-f4bedba01640"
SERP_URL = "http://176.154.220.83/query"
SERP_HEADERS = {
    "Content-Type": "application/json",
    "X-API-KEY": SERP_API_KEY
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
async def serp_search(query: str) -> dict:
    """
    Effectue une recherche Google générale.

    Args:
        query: Requête de recherche

    Returns:
        Liste des résultats avec titre, URL et snippet
    """
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(SERP_URL, json={"q": query}, headers=SERP_HEADERS)

        if response.status_code != 200:
            return {"error": f"HTTP {response.status_code}", "details": response.text}

        data = response.json()

        return {
            "query": query,
            "results": data.get("results", []),
            "total": len(data.get("results", []))
        }


@mcp.tool
async def serp_pappers(company_name: str) -> dict:
    """
    Recherche sur Pappers et extrait le SIREN de l'URL.

    Pappers URLs: pappers.fr/entreprise/{nom-legal}-{SIREN}

    Args:
        company_name: Nom de l'entreprise à rechercher

    Returns:
        Résultats Pappers avec SIREN extrait des URLs
    """
    query = f"{company_name} pappers"

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(SERP_URL, json={"q": query}, headers=SERP_HEADERS)

        if response.status_code != 200:
            return {"error": f"HTTP {response.status_code}", "details": response.text}

        data = response.json()
        results = data.get("results", [])

        pappers_results = []
        for r in results:
            url = r.get("url", "")
            if "pappers.fr/entreprise/" in url:
                match = re.search(r'/entreprise/([a-z0-9\-]+)-(\d{9})(?:/|$)', url)
                if match:
                    pappers_results.append({
                        "url": url,
                        "title": r.get("title"),
                        "nom_legal_extrait": match.group(1).replace('-', ' ').upper(),
                        "siren_extrait": match.group(2)
                    })

        return {
            "query": query,
            "pappers_results": pappers_results,
            "all_results": results
        }


@mcp.tool
async def serp_societe_com(company_name: str) -> dict:
    """
    Recherche sur Societe.com.

    Args:
        company_name: Nom de l'entreprise à rechercher

    Returns:
        Résultats Societe.com
    """
    query = f"{company_name} societe.com"

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(SERP_URL, json={"q": query}, headers=SERP_HEADERS)

        if response.status_code != 200:
            return {"error": f"HTTP {response.status_code}", "details": response.text}

        data = response.json()
        results = data.get("results", [])

        societe_results = [r for r in results if "societe.com" in r.get("url", "")]

        return {
            "query": query,
            "societe_results": societe_results,
            "all_results": results
        }


@mcp.tool
async def serp_linkedin_company(company_name: str) -> dict:
    """
    Trouve la page LinkedIn Company via SERP.

    Args:
        company_name: Nom de l'entreprise à rechercher

    Returns:
        URL de la page LinkedIn Company si trouvée
    """
    query = f"site:linkedin.com/company {company_name}"

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(SERP_URL, json={"q": query}, headers=SERP_HEADERS)

        if response.status_code != 200:
            return {"error": f"HTTP {response.status_code}", "details": response.text}

        data = response.json()
        results = data.get("results", [])

        linkedin_urls = [
            r.get("url") for r in results
            if "linkedin.com/company/" in r.get("url", "")
        ]

        return {
            "query": query,
            "linkedin_company_url": linkedin_urls[0] if linkedin_urls else None,
            "all_linkedin_urls": linkedin_urls
        }


def create_authenticated_app():
    mcp_app = mcp.http_app()
    app = Starlette(
        routes=[Mount("/mcp", app=mcp_app)],
        middleware=[Middleware(BasicAuthMiddleware)]
    )
    return app


app = create_authenticated_app()
