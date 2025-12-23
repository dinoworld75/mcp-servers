"""
Annuaire Entreprises MCP Server
French business registry API (data.gouv.fr)
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

# Auth credentials from env or defaults
AUTH_USERNAME = os.environ.get("AUTH_USERNAME", "ackizit")
AUTH_PASSWORD = os.environ.get("AUTH_PASSWORD", "!Lam3ute!75")

mcp = FastMCP("Annuaire Entreprises")


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
async def annuaire_recherche(query: str, per_page: int = 5) -> dict:
    """
    Recherche une entreprise dans l'Annuaire des Entreprises (API Gouv).

    API gratuite, sans authentification.

    Args:
        query: Requête de recherche (nom, SIREN, SIRET, adresse...)
        per_page: Nombre de résultats (défaut: 5)

    Returns:
        Liste des entreprises trouvées avec SIRET, adresse, dirigeants
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        url = f"https://recherche-entreprises.api.gouv.fr/search?q={query}&per_page={per_page}"

        response = await client.get(url)

        if response.status_code != 200:
            return {"error": f"HTTP {response.status_code}", "details": response.text}

        data = response.json()
        results = data.get("results", [])

        formatted = []
        for r in results:
            siege = r.get("siege", {})
            formatted.append({
                "siren": r.get("siren"),
                "siret": siege.get("siret"),
                "nom_complet": r.get("nom_complet"),
                "nom_raison_sociale": r.get("nom_raison_sociale"),
                "adresse": siege.get("adresse"),
                "code_postal": siege.get("code_postal"),
                "libelle_commune": siege.get("libelle_commune"),
                "activite_principale": r.get("activite_principale"),
                "tranche_effectif_salarie": r.get("tranche_effectif_salarie"),
                "dirigeants": r.get("dirigeants", [])
            })

        return {
            "query": query,
            "total": data.get("total_results", 0),
            "results": formatted
        }


@mcp.tool
async def check_holding(siren: str) -> dict:
    """
    Vérifie si une entreprise est une holding (64.20Z) sans salariés.

    Les holdings sont des coquilles financières - les employés sont
    dans les entités opérationnelles (GROUP, SAS, etc.).

    Args:
        siren: SIREN de l'entreprise à vérifier

    Returns:
        is_holding: True si holding sans salariés
        warning: Message d'alerte si c'est une holding
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        url = f"https://recherche-entreprises.api.gouv.fr/search?q={siren}&per_page=1"

        response = await client.get(url)

        if response.status_code != 200:
            return {"error": f"HTTP {response.status_code}", "details": response.text}

        data = response.json()
        results = data.get("results", [])

        if not results:
            return {"error": "SIREN non trouvé"}

        entreprise = results[0]
        activite = entreprise.get("activite_principale", "")
        effectif = entreprise.get("tranche_effectif_salarie")

        is_holding = activite == "64.20Z"
        has_employees = effectif and effectif not in ["NN", "00", None, ""]

        result = {
            "siren": siren,
            "nom": entreprise.get("nom_complet"),
            "activite": activite,
            "effectif": effectif,
            "is_holding": is_holding,
            "has_employees": has_employees
        }

        if is_holding and not has_employees:
            result["warning"] = "HOLDING sans salariés détectée. Chercher l'entité opérationnelle du groupe."

        return result


@mcp.tool
def calcul_tva(siren: str) -> dict:
    """
    Calcule le numéro de TVA intracommunautaire depuis un SIREN.

    Formule: FR + clé + SIREN
    Clé = (12 + 3 * (SIREN % 97)) % 97

    Args:
        siren: SIREN de l'entreprise (9 chiffres)

    Returns:
        Numéro de TVA intracommunautaire (FR + 2 chiffres + SIREN)
    """
    if not siren or len(siren) != 9 or not siren.isdigit():
        return {"error": "SIREN invalide (doit être 9 chiffres)"}

    siren_int = int(siren)
    key = (12 + 3 * (siren_int % 97)) % 97
    tva = f"FR{key:02d}{siren}"

    return {
        "siren": siren,
        "tva": tva
    }


def create_authenticated_app():
    mcp_app = mcp.http_app()
    app = Starlette(
        routes=[Mount("/mcp", app=mcp_app)],
        middleware=[Middleware(BasicAuthMiddleware)]
    )
    return app


app = create_authenticated_app()
