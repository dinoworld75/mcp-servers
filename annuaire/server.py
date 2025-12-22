"""
Annuaire Entreprises MCP Server
French business registry API (data.gouv.fr)
"""

import httpx
from fastmcp import FastMCP

mcp = FastMCP("Annuaire Entreprises")


@mcp.tool
async def annuaire_recherche(query: str, per_page: int = 5) -> dict:
    """
    Recherche une entreprise dans l'Annuaire des Entreprises (API Gouv).

    API gratuite, sans authentification.

    IMPORTANT: Le nom commercial (ex: "Icypeas") est souvent différent du nom légal
    (ex: "VLOUM"). Si 0 résultats, utiliser serp_pappers pour trouver le nom légal.

    Args:
        query: Requête de recherche (nom, SIREN, SIRET, adresse...)
        per_page: Nombre de résultats (défaut: 5)

    Returns:
        Liste des entreprises trouvées avec SIRET, adresse, dirigeants

    Exemples:
        annuaire_recherche("Microsoft 92130")  # Nom + code postal
        annuaire_recherche("919561266")        # SIREN direct
        annuaire_recherche("VLOUM Paris")      # Nom légal + ville
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

    IMPORTANT: Toujours vérifier après annuaire_recherche !
    Les holdings sont des coquilles financières avec 0 salarié.
    Les employés travaillent dans l'entité opérationnelle (GROUP, SAS, etc.).

    Si is_holding=True et has_employees=False:
    → Chercher l'entité opérationnelle du même groupe (ex: "ASMODEE GROUP" au lieu de "ASMODEE HOLDING")

    Args:
        siren: SIREN de l'entreprise à vérifier (9 chiffres)

    Returns:
        is_holding: True si activité 64.20Z
        has_employees: True si effectif > 0
        warning: Message si holding sans salariés

    Exemple:
        check_holding("798660833")  # ASMODEE HOLDING → is_holding=True, warning="..."
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

        # 64.20Z = Activités des sociétés holding
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
