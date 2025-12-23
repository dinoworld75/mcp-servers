# MCP Servers

Monorepo contenant les serveurs MCP pour la recherche de SIRET d'entreprises françaises.

## Architecture

```
mcp-servers/
├── docker-compose.yml    # Tous les services + Traefik config
├── linkedin/             # Scraping LinkedIn
│   ├── Dockerfile
│   ├── server.py
│   └── requirements.txt
├── annuaire/             # API Annuaire Entreprises
├── serp/                 # Recherche Google (Pappers, etc.)
├── rdap/                 # WHOIS domaines .fr
└── siret-extractor/      # Extraction SIRET mentions légales
```

## Déploiement

Déployé sur Coolify avec routing Traefik par sous-domaine.

**Endpoints (protégés par Basic Auth) :**
- `https://linkedin.mcp.lasupermachine.fr/mcp`
- `https://annuaire.mcp.lasupermachine.fr/mcp`
- `https://serp.mcp.lasupermachine.fr/mcp`
- `https://rdap.mcp.lasupermachine.fr/mcp`
- `https://siret-extractor.mcp.lasupermachine.fr/mcp`

## Authentification

Tous les endpoints sont protégés par Basic Auth via Traefik middleware.

**Credentials :** `ackizit:!Lam3ute!75`

## Configuration MetaMCP

```json
{
  "mcpServers": {
    "linkedin": {
      "url": "https://linkedin.mcp.lasupermachine.fr/mcp",
      "type": "streamable_http",
      "description": "Scraping LinkedIn - Profils et pages Company",
      "headers": {
        "Authorization": "Basic YWNraXppdDohTGFtM3V0ZSE3NQ=="
      }
    },
    "annuaire": {
      "url": "https://annuaire.mcp.lasupermachine.fr/mcp",
      "type": "streamable_http",
      "description": "API Annuaire Entreprises (data.gouv.fr)",
      "headers": {
        "Authorization": "Basic YWNraXppdDohTGFtM3V0ZSE3NQ=="
      }
    },
    "serp": {
      "url": "https://serp.mcp.lasupermachine.fr/mcp",
      "type": "streamable_http",
      "description": "Recherche Google (Pappers, Societe.com, LinkedIn)",
      "headers": {
        "Authorization": "Basic YWNraXppdDohTGFtM3V0ZSE3NQ=="
      }
    },
    "rdap": {
      "url": "https://rdap.mcp.lasupermachine.fr/mcp",
      "type": "streamable_http",
      "description": "RDAP/WHOIS - Données domaines .fr",
      "headers": {
        "Authorization": "Basic YWNraXppdDohTGFtM3V0ZSE3NQ=="
      }
    },
    "siret-extractor": {
      "url": "https://siret-extractor.mcp.lasupermachine.fr/mcp",
      "type": "streamable_http",
      "description": "Extraction SIRET mentions légales",
      "headers": {
        "Authorization": "Basic YWNraXppdDohTGFtM3V0ZSE3NQ=="
      }
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

1. Créer un sous-dossier avec `Dockerfile`, `server.py` et `requirements.txt`
2. Ajouter le service dans `docker-compose.yml` avec les labels Traefik
3. Commit et push → Coolify redéploie automatiquement
