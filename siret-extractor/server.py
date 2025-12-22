"""
SIRET Extractor MCP Server
Extract SIRET from website legal pages
"""

import httpx
from fastmcp import FastMCP

mcp = FastMCP("SIRET Extractor")

BASIC_AUTH = "YWNraXppdDohTGFtM3V0ZSE3NQ=="
HEADERS = {
    "Authorization": f"Basic {BASIC_AUTH}",
    "Content-Type": "application/json"
}


@mcp.tool
async def siret_extractor(url: str) -> dict:
    """
    Extrait le SIRET des mentions légales d'un site web.

    QUAND UTILISER: Après linkedin_company pour récupérer le website.
    Taux de succès: ~38% des sites français publient leur SIRET.

    Si found=True, c'est la source la plus fiable (données officielles publiées).
    Si found=False, utiliser annuaire_recherche avec le nom + code postal.

    Args:
        url: URL du site web à analyser (ex: "https://icypeas.com")

    Returns:
        found: True si SIRET trouvé
        siret: SIRET (14 chiffres)
        siren: SIREN (9 chiffres)
        tva: Numéro TVA intracommunautaire

    Workflow:
        1. linkedin_company(url) → website: "icypeas.com"
        2. siret_extractor("https://icypeas.com") → siret si trouvé
        3. Si non trouvé → annuaire_recherche(nom + CP)

    Exemple:
        siret_extractor("https://rwe.com/fr")
        # → {found: True, siret: "88470667200026", siren: "884706672"}
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        api_url = "https://siretextractor.lasupermachine.fr/api/extract"
        payload = {"url": url}

        response = await client.post(api_url, json=payload, headers=HEADERS)

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
