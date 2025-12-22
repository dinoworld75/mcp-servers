"""
LinkedIn MCP Server
Scrape LinkedIn profiles and company pages
"""

import httpx
from fastmcp import FastMCP
from typing import Optional

mcp = FastMCP("LinkedIn Scraper")

BASIC_AUTH = "YWNraXppdDohTGFtM3V0ZSE3NQ=="
HEADERS = {
    "Authorization": f"Basic {BASIC_AUTH}",
    "Content-Type": "application/json"
}


@mcp.tool
async def linkedin_profile(url: str) -> dict:
    """
    Extrait les informations d'un profil LinkedIn.

    ATTENTION: Le profil LinkedIn peut être OBSOLÈTE !
    La personne peut avoir changé d'entreprise sans mettre à jour son profil.
    Croiser avec l'email professionnel (domaine) pour vérifier.

    Args:
        url: URL du profil LinkedIn (ex: linkedin.com/in/john-doe)

    Returns:
        name: Nom complet
        company: Entreprise actuelle (peut être obsolète)
        company_url: URL LinkedIn de l'entreprise
        location: Localisation

    Workflow:
        1. linkedin_profile(url) → company_url
        2. linkedin_company(company_url) → website, postal_code
        3. annuaire_recherche(company + postal_code) → SIRET

    Exemple:
        linkedin_profile("https://linkedin.com/in/pierre-dupont")
        # → {company: "Icypeas", company_url: "https://linkedin.com/company/icypeas"}
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
        company_name: Nom commercial (peut différer du nom légal !)
        website: Site web de l'entreprise
        postal_code: Code postal du siège
        headquarters: Adresse du siège

    IMPORTANT: Le company_name est le nom COMMERCIAL, pas le nom légal.
    Utiliser le postal_code pour affiner la recherche dans annuaire_recherche.

    Exemple:
        linkedin_company("https://linkedin.com/company/icypeas")
        # → {company_name: "Icypeas", website: "icypeas.com", postal_code: "75009"}
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
