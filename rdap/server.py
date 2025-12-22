"""
RDAP/WHOIS MCP Server
Query domain registration data
"""

import httpx
from fastmcp import FastMCP

mcp = FastMCP("RDAP WHOIS")

BASIC_AUTH = "YWNraXppdDohTGFtM3V0ZSE3NQ=="
HEADERS = {
    "Authorization": f"Basic {BASIC_AUTH}"
}


@mcp.tool
async def rdap_whois(domain: str) -> dict:
    """
    Interroge les données RDAP/WHOIS d'un domaine.

    QUAND UTILISER: Pour les domaines .fr quand on n'a pas le code postal.
    Le registrant_organization peut donner le NOM LÉGAL de l'entreprise.

    LIMITATION: Les .com/.net ont souvent le WHOIS masqué (GDPR).
    Ne fonctionne de manière fiable que pour les .fr (AFNIC expose les données).

    Args:
        domain: Nom de domaine à interroger (ex: "example.fr")

    Returns:
        registrant_organization: Nom légal de l'entreprise propriétaire
        registrant_address: Adresse (peut contenir le code postal)
        registrant_email: Email du contact

    Workflow:
        1. linkedin_company → website: "example.fr"
        2. rdap_whois("example.fr") → registrant_organization, adresse
        3. annuaire_recherche(registrant_organization) → SIRET

    Exemple:
        rdap_whois("icypeas.fr")
        # → {registrant_organization: "VLOUM", registrant_address: "75009 Paris"}
    """
    async with httpx.AsyncClient(timeout=15.0) as client:
        api_url = f"https://rdap.lasupermachine.fr/api/whois?domain={domain}"

        response = await client.get(api_url, headers=HEADERS)

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
