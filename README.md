# MCP Servers

Monorepo contenant les serveurs MCP pour la recherche de SIRET d'entreprises françaises.

## Architecture

```
mcp-servers/
├── docker-compose.yml    # Tous les services
├── Dockerfile            # Image commune
├── linkedin/             # Scraping LinkedIn
├── annuaire/             # API Annuaire Entreprises
├── serp/                 # Recherche Google (Pappers, etc.)
├── rdap/                 # WHOIS domaines .fr
└── siret-extractor/      # Extraction SIRET mentions légales
```

## Déploiement

Déployé sur Coolify avec routing Traefik par sous-domaine.

**Endpoints :**
- `https://linkedin.mcp.lasupermachine.fr/mcp`
- `https://annuaire.mcp.lasupermachine.fr/mcp`
- `https://serp.mcp.lasupermachine.fr/mcp`
- `https://rdap.mcp.lasupermachine.fr/mcp`
- `https://siret-extractor.mcp.lasupermachine.fr/mcp`

## Configuration MetaMCP

```json
{
  "mcpServers": {
    "linkedin": {
      "url": "https://linkedin.mcp.lasupermachine.fr/mcp",
      "type": "streamable_http",
      "description": "Scraping LinkedIn - Profils et pages Company"
    },
    "annuaire": {
      "url": "https://annuaire.mcp.lasupermachine.fr/mcp",
      "type": "streamable_http",
      "description": "API Annuaire Entreprises (data.gouv.fr)"
    },
    "serp": {
      "url": "https://serp.mcp.lasupermachine.fr/mcp",
      "type": "streamable_http",
      "description": "Recherche Google (Pappers, Societe.com, LinkedIn)"
    },
    "rdap": {
      "url": "https://rdap.mcp.lasupermachine.fr/mcp",
      "type": "streamable_http",
      "description": "RDAP/WHOIS - Données domaines .fr"
    },
    "siret-extractor": {
      "url": "https://siret-extractor.mcp.lasupermachine.fr/mcp",
      "type": "streamable_http",
      "description": "Extraction SIRET mentions légales"
    }
  }
}
```

## Développement local

```bash
# Lancer un service en local
cd linkedin
pip install -r requirements.txt
fastmcp run server.py:mcp --transport streamable-http --port 8080
```

## Ajouter un nouveau MCP

1. Créer un sous-dossier avec `server.py` et `requirements.txt`
2. Ajouter le service dans `docker-compose.yml`
3. Commit et push → Coolify redéploie automatiquement
