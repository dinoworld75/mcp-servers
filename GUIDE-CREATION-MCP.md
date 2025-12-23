# Guide Complet : Créer un MCP Server avec FastMCP 2.0

Ce guide permet à une IA (ou un humain) de créer des serveurs MCP déployables en production avec authentification Basic Auth.

---

## Table des matières

1. [Concepts fondamentaux](#1-concepts-fondamentaux)
2. [Structure d'un MCP Server](#2-structure-dun-mcp-server)
3. [Template complet avec Basic Auth](#3-template-complet-avec-basic-auth)
4. [Déploiement Docker](#4-déploiement-docker)
5. [Déploiement Coolify](#5-déploiement-coolify)
6. [Configuration clients](#6-configuration-clients)
7. [Analyse de sécurité](#7-analyse-de-sécurité)
8. [Patterns avancés](#8-patterns-avancés)
9. [Pièges et erreurs courantes](#9-pièges-et-erreurs-courantes)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Concepts fondamentaux

### Qu'est-ce qu'un MCP Server ?

MCP (Model Context Protocol) est un protocole permettant aux LLMs d'interagir avec des outils externes. Un MCP Server expose des **tools** (fonctions) que le LLM peut appeler.

### Deux modes de transport

| Mode | Description | Use case |
|------|-------------|----------|
| **STDIO** | Communication via stdin/stdout | Local, Claude Desktop |
| **HTTP** | Communication via HTTP/SSE | Distant, MetaMCP, multi-clients |

### FastMCP 2.0

FastMCP est un framework Python qui simplifie la création de MCP servers. Version 2.0 supporte nativement le transport HTTP avec `streamable-http`.

```bash
pip install fastmcp>=2.0.0
```

---

## 2. Structure d'un MCP Server

### Structure minimale

```
mon-mcp/
├── server.py          # Code du serveur
├── requirements.txt   # Dépendances Python
└── Dockerfile         # Pour déploiement
```

### Exemple minimal (sans auth)

```python
from fastmcp import FastMCP

mcp = FastMCP("Mon MCP")

@mcp.tool
async def mon_outil(param: str) -> dict:
    """Description de l'outil pour le LLM."""
    return {"result": f"Traitement de {param}"}

# Pour STDIO
if __name__ == "__main__":
    mcp.run()
```

### Lancement

```bash
# Mode STDIO
python server.py

# Mode HTTP
fastmcp run server.py:mcp --transport streamable-http --port 8080
```

---

## 3. Template complet avec Basic Auth

Ce template est prêt pour la production avec :
- Basic Auth sur tous les endpoints
- Healthcheck public pour monitoring
- Logging structuré
- Gestion d'erreurs

```python
"""
MCP Server Template avec Basic Auth
Prêt pour déploiement Coolify/Docker
"""

import os
import base64
import httpx
from fastmcp import FastMCP

# ============================================
# CONFIGURATION
# ============================================

# Auth - TOUJOURS utiliser des variables d'environnement en prod
AUTH_USERNAME = os.environ.get("AUTH_USERNAME", "admin")
AUTH_PASSWORD = os.environ.get("AUTH_PASSWORD", "changeme")

# Créer l'instance MCP
mcp = FastMCP("Nom Du MCP")


# ============================================
# MIDDLEWARE BASIC AUTH
# ============================================

class BasicAuthMiddleware:
    """
    Middleware ASGI pour Basic Auth.

    - Protège tous les endpoints sauf "/"
    - "/" retourne 200 OK pour les healthchecks
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        # Ignorer les connexions non-HTTP (WebSocket, etc.)
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Healthcheck sur "/" - pas d'auth requise
        path = scope.get("path", "")
        if path == "/" or path == "":
            await self._send_health(send)
            return

        # Vérifier l'auth pour tous les autres paths
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

        # Auth OK - passer la requête à l'app
        await self.app(scope, receive, send)

    async def _send_401(self, send):
        """Retourne 401 Unauthorized."""
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

    async def _send_health(self, send):
        """Retourne 200 OK pour healthcheck."""
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [[b"content-type", b"application/json"]]
        })
        await send({
            "type": "http.response.body",
            "body": b'{"status": "ok"}'
        })


# ============================================
# OUTILS MCP
# ============================================

@mcp.tool
async def exemple_outil(param1: str, param2: int = 10) -> dict:
    """
    Description claire de l'outil pour le LLM.

    Le LLM utilisera cette docstring pour comprendre
    quand et comment utiliser l'outil.

    Args:
        param1: Description du premier paramètre
        param2: Description du second paramètre (défaut: 10)

    Returns:
        Un dictionnaire avec les résultats
    """
    # Logique de l'outil
    result = f"Traitement de {param1} avec {param2}"

    return {
        "success": True,
        "result": result,
        "params": {
            "param1": param1,
            "param2": param2
        }
    }


@mcp.tool
async def outil_avec_api_externe(query: str) -> dict:
    """
    Exemple d'outil appelant une API externe.

    Args:
        query: La requête à envoyer

    Returns:
        Les données de l'API externe
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                f"https://api.exemple.com/search?q={query}"
            )

            if response.status_code != 200:
                return {
                    "error": f"API returned {response.status_code}",
                    "details": response.text
                }

            return response.json()

        except httpx.TimeoutException:
            return {"error": "Timeout lors de l'appel API"}
        except Exception as e:
            return {"error": str(e)}


# ============================================
# POINT D'ENTRÉE
# ============================================

def create_authenticated_app():
    """Crée l'app ASGI avec Basic Auth."""
    mcp_app = mcp.http_app(path="/mcp")
    return BasicAuthMiddleware(mcp_app)


# Pour uvicorn: uvicorn server:app --host 0.0.0.0 --port 8080
app = create_authenticated_app()
```

---

## 4. Déploiement Docker

### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Copier les dépendances
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier le code
COPY server.py .

# Variables d'environnement (override en production)
ENV AUTH_USERNAME=admin
ENV AUTH_PASSWORD=changeme

# Port exposé
EXPOSE 8080

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/ || exit 1

# Lancement
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080"]
```

### requirements.txt

```
fastmcp>=2.0.0
httpx>=0.27.0
uvicorn>=0.30.0
```

### Build et run local

```bash
# Build
docker build -t mon-mcp .

# Run avec credentials custom
docker run -d \
  -p 8080:8080 \
  -e AUTH_USERNAME=monuser \
  -e AUTH_PASSWORD=monpassword \
  mon-mcp
```

---

## 5. Déploiement Coolify

### Option A : Multi-services docker-compose

Pour déployer plusieurs MCPs sur un même serveur avec des sous-domaines :

```yaml
# docker-compose.yml
services:
  mcp-linkedin:
    build: ./linkedin
    environment:
      - AUTH_USERNAME=${AUTH_USERNAME}
      - AUTH_PASSWORD=${AUTH_PASSWORD}
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.mcp-linkedin.rule=Host(`linkedin.mcp.exemple.com`)"
      - "traefik.http.routers.mcp-linkedin.entrypoints=https"
      - "traefik.http.routers.mcp-linkedin.tls=true"
      - "traefik.http.routers.mcp-linkedin.tls.certresolver=letsencrypt"
      - "traefik.http.services.mcp-linkedin.loadbalancer.server.port=8080"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/"]
      interval: 30s
      timeout: 10s
      retries: 3

  mcp-autre:
    build: ./autre
    environment:
      - AUTH_USERNAME=${AUTH_USERNAME}
      - AUTH_PASSWORD=${AUTH_PASSWORD}
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.mcp-autre.rule=Host(`autre.mcp.exemple.com`)"
      - "traefik.http.routers.mcp-autre.entrypoints=https"
      - "traefik.http.routers.mcp-autre.tls=true"
      - "traefik.http.routers.mcp-autre.tls.certresolver=letsencrypt"
      - "traefik.http.services.mcp-autre.loadbalancer.server.port=8080"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/"]
      interval: 30s
      timeout: 10s
      retries: 3

networks:
  default:
    external: true
    name: coolify
```

### Option B : Service unique

Dans Coolify :
1. Créer un nouveau service "Docker Compose"
2. Pointer vers le repo Git
3. Configurer les variables d'environnement
4. Configurer le domaine avec wildcard DNS

### DNS Wildcard

Pour `*.mcp.exemple.com`, créer un enregistrement DNS :

| Type | Nom | Valeur |
|------|-----|--------|
| A | *.mcp | IP_DU_SERVEUR |

---

## 6. Configuration clients

### Claude Desktop (claude_desktop_config.json)

**Emplacement du fichier :**
- **macOS** : `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Linux** : `~/.config/Claude/claude_desktop_config.json`
- **Windows** : `%APPDATA%\Claude\claude_desktop_config.json`

**Format pour un MCP HTTP :**
```json
{
  "mcpServers": {
    "mon-mcp": {
      "url": "https://mon-mcp.exemple.com/mcp",
      "headers": {
        "Authorization": "Basic BASE64_CREDENTIALS"
      }
    }
  }
}
```

**Format pour un MCP STDIO :**
```json
{
  "mcpServers": {
    "mon-mcp": {
      "command": "npx",
      "args": ["-y", "@package/mcp-server", "--option", "value"],
      "env": {
        "API_KEY": "xxx"
      }
    }
  }
}
```

**Import complet** : Tu peux copier-coller directement le contenu d'un fichier JSON de config. Claude Desktop fusionnera les `mcpServers`.

> **Astuce** : Après modification, redémarrer Claude Desktop pour que les changements prennent effet.

### MetaMCP

MetaMCP est un **agrégateur de MCPs**. Au lieu de configurer chaque MCP dans chaque client, tu configures tout dans MetaMCP et tu connectes les clients à MetaMCP.

```
┌─────────────────┐
│  Claude Desktop │
│     Cursor      │───► MetaMCP ───► linkedin, annuaire, serp, ...
│   Claude Code   │    (1 seul)      (tous les MCPs)
└─────────────────┘
```

#### Configurer un MCP dans MetaMCP (interface web)

MetaMCP utilise un champ `type` supplémentaire :

```json
{
  "mcpServers": {
    "mon-mcp-http": {
      "url": "https://mon-mcp.exemple.com/mcp",
      "type": "streamable_http",
      "description": "MCP déployé en HTTP",
      "headers": {
        "Authorization": "Basic BASE64_CREDENTIALS"
      }
    },
    "mon-mcp-stdio": {
      "type": "STDIO",
      "description": "MCP local via npx",
      "command": "npx",
      "args": ["-y", "@package/mcp-server"]
    }
  }
}
```

#### Connecter Claude Desktop à MetaMCP

Une seule config dans Claude Desktop :

```json
{
  "mcpServers": {
    "MetaMCP": {
      "command": "npx",
      "args": ["-y", "@metamcp/mcp-server-metamcp@latest"],
      "env": {
        "METAMCP_API_KEY": "<ta clé API MetaMCP>",
        "METAMCP_API_BASE_URL": "https://ton-metamcp.exemple.com"
      }
    }
  }
}
```

Tous les MCPs configurés dans MetaMCP deviennent accessibles via cette unique connexion.

#### API Admin MetaMCP

| Feature | Status |
|---------|--------|
| API pour ajouter/supprimer des MCPs | Roadmap (pas encore dispo) |
| Interface Web | ✅ Disponible |
| Backend tRPC | Utilisé mais non documenté |

> **Note** : La feature "Headless Admin API" est prévue mais pas encore implémentée.

**Différence clé avec Claude Desktop :**
- Claude Desktop : pas besoin du champ `type`
- MetaMCP : nécessite `type: "streamable_http"` ou `type: "STDIO"`

### Cursor

Dans les settings Cursor, ajouter :
```json
{
  "mon-mcp": {
    "url": "https://mon-mcp.exemple.com/mcp",
    "headers": {
      "Authorization": "Basic BASE64_CREDENTIALS"
    }
  }
}
```

### Générer le Base64

```bash
echo -n "username:password" | base64
# Exemple: echo -n "admin:secret123" | base64
# Résultat: YWRtaW46c2VjcmV0MTIz
```

---

## 7. Analyse de sécurité

### Surface d'attaque

Quand tu déploies un MCP HTTP, voici ce qui est exposé à Internet :

| Endpoint | Protection | Risque |
|----------|------------|--------|
| `/` | Aucune (healthcheck) | NUL - retourne juste `{"status":"ok"}` |
| `/mcp` | Basic Auth | Protégé - 401 sans credentials |

### Vecteurs d'attaque et évaluation

#### 1. Accès direct sans credentials
```bash
curl https://mon-mcp.exemple.com/mcp
# → 401 Unauthorized
```
**Risque : NUL** - Le middleware bloque tout accès non authentifié.

#### 2. Brute force du mot de passe
- **Risque : FAIBLE à MOYEN** selon la force du mot de passe
- Pas de rate limiting natif dans notre middleware
- Mitigation : utiliser un mot de passe fort (12+ caractères, spéciaux)

#### 3. Vol de credentials
- Le Base64 dans les configs est facilement décodable
- **Risque : MOYEN** - Si quelqu'un accède aux fichiers de config
- Mitigation : garder les configs privées, ne pas les commiter en public

#### 4. Man-in-the-middle
- **Risque : TRÈS FAIBLE** - HTTPS via Let's Encrypt protège le transit

### Résumé sécurité

| Question | Réponse |
|----------|---------|
| Peut-on hacker de l'extérieur sans credentials ? | **NON** |
| Peut-on brute-forcer ? | Possible mais très long avec bon password |
| Si credentials volés ? | Accès total aux outils MCP |

### Recommandations pour renforcer

1. **Rate limiting** - Ajouter un middleware Traefik ou dans le code
2. **Env vars only** - Ne jamais mettre de defaults dans le code en prod
3. **Rotation** - Changer les credentials périodiquement
4. **Logs** - Logger les tentatives d'auth échouées
5. **IP Whitelist** - Si possible, restreindre les IPs sources

---

## 8. Patterns avancés

### Appeler une API interne avec auth

```python
# Headers pour API interne
INTERNAL_AUTH = "BASE64_CREDENTIALS"
INTERNAL_HEADERS = {"Authorization": f"Basic {INTERNAL_AUTH}"}

@mcp.tool
async def mon_outil(param: str) -> dict:
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            f"https://api-interne.exemple.com/endpoint?q={param}",
            headers=INTERNAL_HEADERS
        )
        return response.json()
```

### Validation des paramètres

```python
from typing import Literal

@mcp.tool
async def outil_avec_validation(
    action: Literal["create", "update", "delete"],
    id: int,
    data: str = ""
) -> dict:
    """
    Outil avec paramètres typés et validés.

    Args:
        action: Action à effectuer (create/update/delete)
        id: ID de l'objet
        data: Données optionnelles
    """
    if action == "delete" and data:
        return {"error": "data ne doit pas être fourni pour delete"}

    # ... logique
```

### Gestion d'erreurs robuste

```python
@mcp.tool
async def outil_robuste(url: str) -> dict:
    """Outil avec gestion d'erreurs complète."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            return {"success": True, "data": response.json()}

    except httpx.TimeoutException:
        return {"success": False, "error": "timeout", "message": "La requête a expiré"}
    except httpx.HTTPStatusError as e:
        return {"success": False, "error": "http", "status": e.response.status_code}
    except httpx.RequestError as e:
        return {"success": False, "error": "request", "message": str(e)}
    except Exception as e:
        return {"success": False, "error": "unknown", "message": str(e)}
```

### Plusieurs outils liés

```python
@mcp.tool
async def rechercher_entreprise(query: str) -> dict:
    """Recherche une entreprise par nom."""
    # ...

@mcp.tool
async def details_entreprise(siren: str) -> dict:
    """Obtient les détails d'une entreprise par SIREN."""
    # ...

@mcp.tool
async def verifier_siret(siret: str) -> dict:
    """Vérifie la validité d'un SIRET."""
    # ...
```

---

## 9. Pièges et erreurs courantes

### Piège #1 : Starlette Mount au lieu de middleware ASGI pur

**Ne PAS faire :**
```python
from starlette.applications import Starlette
from starlette.routing import Mount

# ❌ ERREUR - Cause des 500 Internal Server Error
app = Starlette(routes=[
    Mount("/", app=mcp.http_app(path="/mcp"))
])
```

**Faire :**
```python
# ✅ CORRECT - Middleware ASGI pur
def create_authenticated_app():
    mcp_app = mcp.http_app(path="/mcp")
    return BasicAuthMiddleware(mcp_app)

app = create_authenticated_app()
```

**Explication** : FastMCP 2.0 avec `mcp.http_app(path="/mcp")` crée une app ASGI complète. L'envelopper dans Starlette Mount cause des conflits de routing.

### Piège #2 : Healthcheck qui échoue (401)

**Problème** : Docker healthcheck sur "/" retourne 401

**Solution** : Le middleware doit bypasser l'auth sur "/" :
```python
path = scope.get("path", "")
if path == "/" or path == "":
    await self._send_health(send)
    return
```

### Piège #3 : Branch Git incorrecte

**Problème** : Coolify déploie depuis `main` mais le code est sur `master`

**Solution** :
```bash
git push origin master:main
```

### Piège #4 : MCPs STDIO avec chemins locaux dans MetaMCP

**Problème** : Config avec chemin local ne fonctionne pas dans MetaMCP distant
```json
{
  "command": "python",
  "args": ["/home/user/.local/share/mcp/server.py"]  // ❌ N'existe pas sur MetaMCP
}
```

**Solution** : Utiliser des packages npm ou déployer en HTTP
```json
{
  "command": "npx",
  "args": ["-y", "@package/mcp-server"]  // ✅ Installé à la volée
}
```

### Piège #5 : Confondre type de transport

| Type | Déploiement | Config client |
|------|-------------|---------------|
| STDIO | Local (processus) | `command` + `args` |
| HTTP | Distant (serveur web) | `url` + `headers` |

Un MCP HTTP déployé sur Coolify utilise `url`, pas `command`.

---

## 10. Troubleshooting

### Erreur 406 Not Acceptable

**Normal !** Le protocole MCP nécessite le header `Accept: text/event-stream`. Sans ce header, le serveur retourne 406.

```bash
# Test qui retourne 406 (normal)
curl https://mon-mcp.exemple.com/mcp

# Test correct avec SSE
curl -H "Accept: text/event-stream" \
     -H "Authorization: Basic BASE64" \
     https://mon-mcp.exemple.com/mcp
```

### Erreur 401 Unauthorized

Vérifier :
1. Le header Authorization est présent
2. Le format est `Basic BASE64`
3. Les credentials sont corrects

```bash
# Générer le bon Base64
echo -n "user:pass" | base64
```

### Erreur 500 Internal Server Error

Vérifier les logs du container :
```bash
docker logs <container_id>
```

Causes fréquentes :
- Import manquant dans requirements.txt
- Erreur de syntaxe Python
- Variable d'environnement manquante

### Healthcheck failing

Le healthcheck doit pointer sur "/" qui retourne 200 sans auth :
```bash
curl http://localhost:8080/
# Doit retourner: {"status": "ok"}
```

### MCP non détecté par Claude Desktop

1. Redémarrer Claude Desktop après modification de la config
2. Vérifier le format JSON (pas de virgule trailing)
3. Vérifier que l'URL se termine par `/mcp`

---

## Checklist de déploiement

- [ ] Code server.py avec Basic Auth middleware
- [ ] requirements.txt avec toutes les dépendances
- [ ] Dockerfile avec healthcheck
- [ ] Variables d'environnement configurées
- [ ] DNS configuré (ou wildcard)
- [ ] Test healthcheck : `curl https://xxx/` → 200
- [ ] Test sans auth : `curl https://xxx/mcp` → 401
- [ ] Test avec auth : `curl -H "Authorization: Basic xxx" https://xxx/mcp` → 406
- [ ] Config client ajoutée et testée

---

## Ressources

- [FastMCP Documentation](https://github.com/jlowin/fastmcp)
- [MCP Protocol Specification](https://modelcontextprotocol.io/)
- [Coolify Documentation](https://coolify.io/docs)

---

## Exemple concret : Nos MCPs déployés

Voici les MCPs que nous avons déployés avec ce guide :

| MCP | URL | Description |
|-----|-----|-------------|
| linkedin | https://linkedin.mcp.lasupermachine.fr/mcp | Scraping profils et pages company |
| annuaire | https://annuaire.mcp.lasupermachine.fr/mcp | API Annuaire Entreprises (data.gouv) |
| serp | https://serp.mcp.lasupermachine.fr/mcp | Recherche Google (Pappers, Societe.com) |
| rdap | https://rdap.mcp.lasupermachine.fr/mcp | RDAP/WHOIS pour domaines .fr |
| siret-extractor | https://siret-extractor.mcp.lasupermachine.fr/mcp | Extraction SIRET depuis mentions légales |

**Architecture :**
```
┌────────────────────────────────────────────────────────┐
│                    Internet                            │
└────────────────────────┬───────────────────────────────┘
                         │ HTTPS
                         ▼
┌────────────────────────────────────────────────────────┐
│                  Traefik (Coolify)                     │
│         *.mcp.lasupermachine.fr → containers          │
└────────────────────────┬───────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
   ┌─────────┐     ┌─────────┐     ┌─────────┐
   │linkedin │     │annuaire │     │  serp   │
   │  :8080  │     │  :8080  │     │  :8080  │
   └─────────┘     └─────────┘     └─────────┘
```

---

## Changelog

| Date | Modification |
|------|--------------|
| 2024-12 | Création initiale avec 5 MCPs |
| 2024-12 | Ajout Basic Auth ASGI middleware |
| 2024-12 | Fix healthcheck pour Coolify |
| 2024-12 | Documentation sécurité et pièges courants |
| 2024-12 | Ajout section MetaMCP (agrégateur + connexion Claude Desktop) |
| 2024-12 | Clarification API Admin MetaMCP (roadmap, pas encore dispo) |
