"""
SERP MCP Server
Google search with specialized queries
"""

import httpx
import re
from fastmcp import FastMCP

mcp = FastMCP("SERP Search")

SERP_API_KEY = "089e2741-9760-4b19-90d3-f4bedba01640"
SERP_URL = "http://176.154.220.83/query"
HEADERS = {
    "Content-Type": "application/json",
    "X-API-KEY": SERP_API_KEY
}


@mcp.tool
async def serp_search(query: str) -> dict:
    """
    Effectue une recherche Google générale.

    QUAND UTILISER: Recherche libre quand les outils spécialisés ne suffisent pas.
    Préférer serp_pappers ou serp_societe_com pour trouver des SIRET.

    Args:
        query: Requête de recherche libre

    Returns:
        results: Liste des résultats avec titre, URL et snippet

    Exemples de requêtes utiles:
        "{nom} SIRET France"
        "site:{website} mentions légales"
        "{nom} infogreffe"
    """
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(SERP_URL, json={"q": query}, headers=HEADERS)

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

    QUAND UTILISER: Si annuaire_recherche retourne 0 résultats avec le nom commercial.
    C'est LE MOYEN de trouver le nom légal quand il diffère du nom commercial.

    Pappers URLs contiennent le nom légal et SIREN: pappers.fr/entreprise/{nom-legal}-{SIREN}

    Args:
        company_name: Nom commercial de l'entreprise (ex: "Icypeas", "Delamaison")

    Returns:
        pappers_results: Liste avec nom_legal_extrait et siren_extrait

    Workflow:
        1. annuaire_recherche("Icypeas") → 0 résultats
        2. serp_pappers("Icypeas") → {nom_legal: "VLOUM", siren: "919561266"}
        3. annuaire_recherche("VLOUM") → SIRET trouvé !

    Exemple:
        serp_pappers("Icypeas")
        # → {pappers_results: [{nom_legal_extrait: "VLOUM", siren_extrait: "919561266"}]}
    """
    query = f"{company_name} pappers"

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(SERP_URL, json={"q": query}, headers=HEADERS)

        if response.status_code != 200:
            return {"error": f"HTTP {response.status_code}", "details": response.text}

        data = response.json()
        results = data.get("results", [])

        pappers_results = []
        for r in results:
            url = r.get("url", "")
            if "pappers.fr/entreprise/" in url:
                # Extract SIREN from URL: /entreprise/nom-legal-123456789
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

    Alternative à serp_pappers. Societe.com affiche aussi les infos légales
    mais l'extraction automatique du SIREN est moins fiable que Pappers.

    PRÉFÉRER serp_pappers qui extrait automatiquement le SIREN de l'URL.

    Args:
        company_name: Nom de l'entreprise à rechercher

    Returns:
        societe_results: Liens vers pages Societe.com
    """
    query = f"{company_name} societe.com"

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(SERP_URL, json={"q": query}, headers=HEADERS)

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

    QUAND UTILISER: Quand on a un nom d'entreprise mais pas l'URL LinkedIn.
    Permet ensuite d'utiliser linkedin_company pour récupérer website et CP.

    Args:
        company_name: Nom de l'entreprise à rechercher

    Returns:
        linkedin_company_url: URL de la page LinkedIn Company

    Workflow:
        1. serp_linkedin_company("Icypeas") → linkedin_company_url
        2. linkedin_company(url) → website, postal_code
        3. annuaire_recherche(nom + postal_code) → SIRET

    Exemple:
        serp_linkedin_company("Microsoft France")
        # → {linkedin_company_url: "https://linkedin.com/company/microsoft"}
    """
    query = f"site:linkedin.com/company {company_name}"

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(SERP_URL, json={"q": query}, headers=HEADERS)

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
