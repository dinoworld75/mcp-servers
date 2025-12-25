"""
Supabase MCP Server
Interact with self-hosted Supabase instances
With Basic Auth protection
"""

import os
import base64
import httpx
from fastmcp import FastMCP

# Auth credentials from env or defaults
AUTH_USERNAME = os.environ.get("AUTH_USERNAME", "ackizit")
AUTH_PASSWORD = os.environ.get("AUTH_PASSWORD", "!Lam3ute!75")

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://supabase.lasupermachine.fr")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

# Create MCP server
mcp = FastMCP("Supabase Self-Hosted")


def get_headers(use_service_key: bool = True) -> dict:
    """Get headers for Supabase API requests."""
    key = SUPABASE_SERVICE_KEY if use_service_key else SUPABASE_ANON_KEY
    return {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json"
    }


class BasicAuthMiddleware:
    """ASGI middleware for Basic Auth."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path == "/" or path == "":
            await self._send_health(send)
            return

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

        await self.app(scope, receive, send)

    async def _send_401(self, send):
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
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [[b"content-type", b"application/json"]]
        })
        await send({
            "type": "http.response.body",
            "body": b'{"status": "ok"}'
        })


@mcp.tool
async def execute_sql(query: str, read_only: bool = True) -> dict:
    """
    Execute a SQL query on the Supabase database via RPC.

    Supports ALL SQL operations:
    - SELECT queries (read_only=True)
    - DDL: CREATE TABLE, ALTER TABLE, DROP TABLE, CREATE INDEX
    - DML: INSERT, UPDATE, DELETE

    Args:
        query: The SQL query to execute
        read_only: Set to False for DDL/DML operations (default True for safety)

    Returns:
        Query results or operation status
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{SUPABASE_URL}/rest/v1/rpc/execute_sql",
                json={"query": query, "read_only": read_only},
                headers=get_headers()
            )

            if response.status_code == 200:
                return {"success": True, "data": response.json()}
            else:
                return {"success": False, "error": response.text, "status": response.status_code}
        except Exception as e:
            return {"success": False, "error": str(e)}


@mcp.tool
async def list_tables(schema: str = "public") -> dict:
    """
    List all tables in a schema.

    Args:
        schema: The schema name (default: public)

    Returns:
        List of table names with their details
    """
    query = f"""
    SELECT table_name, table_type
    FROM information_schema.tables
    WHERE table_schema = '{schema}'
    ORDER BY table_name
    """
    return await execute_sql(query, read_only=True)


@mcp.tool
async def describe_table(table_name: str, schema: str = "public") -> dict:
    """
    Get the structure of a table (columns, types, constraints).

    Args:
        table_name: Name of the table
        schema: Schema name (default: public)

    Returns:
        Table structure with column details
    """
    query = f"""
    SELECT
        column_name,
        data_type,
        is_nullable,
        column_default,
        character_maximum_length
    FROM information_schema.columns
    WHERE table_schema = '{schema}' AND table_name = '{table_name}'
    ORDER BY ordinal_position
    """
    return await execute_sql(query, read_only=True)


@mcp.tool
async def list_users(page: int = 1, per_page: int = 50) -> dict:
    """
    List all users from Supabase Auth.

    Args:
        page: Page number (default: 1)
        per_page: Users per page (default: 50)

    Returns:
        List of users with their details
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                f"{SUPABASE_URL}/auth/v1/admin/users",
                params={"page": page, "per_page": per_page},
                headers=get_headers()
            )

            if response.status_code == 200:
                data = response.json()
                users = data.get("users", [])
                return {
                    "success": True,
                    "count": len(users),
                    "users": [
                        {
                            "id": u.get("id"),
                            "email": u.get("email"),
                            "created_at": u.get("created_at"),
                            "last_sign_in_at": u.get("last_sign_in_at"),
                            "role": u.get("role")
                        }
                        for u in users
                    ]
                }
            else:
                return {"success": False, "error": response.text, "status": response.status_code}
        except Exception as e:
            return {"success": False, "error": str(e)}


@mcp.tool
async def create_user(email: str, password: str, email_confirm: bool = True) -> dict:
    """
    Create a new user in Supabase Auth.

    Args:
        email: User's email address
        password: User's password
        email_confirm: Auto-confirm email (default: True)

    Returns:
        Created user details
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{SUPABASE_URL}/auth/v1/admin/users",
                json={
                    "email": email,
                    "password": password,
                    "email_confirm": email_confirm
                },
                headers=get_headers()
            )

            if response.status_code in [200, 201]:
                user = response.json()
                return {
                    "success": True,
                    "user": {
                        "id": user.get("id"),
                        "email": user.get("email"),
                        "created_at": user.get("created_at")
                    }
                }
            else:
                return {"success": False, "error": response.text, "status": response.status_code}
        except Exception as e:
            return {"success": False, "error": str(e)}


@mcp.tool
async def delete_user(user_id: str) -> dict:
    """
    Delete a user from Supabase Auth.

    Args:
        user_id: The user's UUID

    Returns:
        Deletion status
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.delete(
                f"{SUPABASE_URL}/auth/v1/admin/users/{user_id}",
                headers=get_headers()
            )

            if response.status_code in [200, 204]:
                return {"success": True, "message": f"User {user_id} deleted"}
            else:
                return {"success": False, "error": response.text, "status": response.status_code}
        except Exception as e:
            return {"success": False, "error": str(e)}


@mcp.tool
async def list_buckets() -> dict:
    """
    List all storage buckets.

    Returns:
        List of storage buckets with their details
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                f"{SUPABASE_URL}/storage/v1/bucket",
                headers=get_headers()
            )

            if response.status_code == 200:
                buckets = response.json()
                return {
                    "success": True,
                    "count": len(buckets),
                    "buckets": [
                        {
                            "id": b.get("id"),
                            "name": b.get("name"),
                            "public": b.get("public"),
                            "created_at": b.get("created_at")
                        }
                        for b in buckets
                    ]
                }
            else:
                return {"success": False, "error": response.text, "status": response.status_code}
        except Exception as e:
            return {"success": False, "error": str(e)}


@mcp.tool
async def list_files(bucket_id: str, path: str = "", limit: int = 100) -> dict:
    """
    List files in a storage bucket.

    Args:
        bucket_id: The bucket ID/name
        path: Path prefix to filter (default: root)
        limit: Maximum files to return (default: 100)

    Returns:
        List of files in the bucket
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{SUPABASE_URL}/storage/v1/object/list/{bucket_id}",
                json={"prefix": path, "limit": limit},
                headers=get_headers()
            )

            if response.status_code == 200:
                files = response.json()
                return {
                    "success": True,
                    "count": len(files),
                    "files": files
                }
            else:
                return {"success": False, "error": response.text, "status": response.status_code}
        except Exception as e:
            return {"success": False, "error": str(e)}


@mcp.tool
async def get_database_stats() -> dict:
    """
    Get database statistics (size, connections, etc.).

    Returns:
        Database statistics
    """
    query = """
    SELECT
        pg_database.datname as database,
        pg_size_pretty(pg_database_size(pg_database.datname)) as size,
        numbackends as active_connections
    FROM pg_stat_database
    JOIN pg_database ON pg_database.oid = pg_stat_database.datid
    WHERE pg_database.datname = current_database()
    """
    return await execute_sql(query, read_only=True)


@mcp.tool
async def get_table_row_counts(schema: str = "public") -> dict:
    """
    Get row counts for all tables in a schema.

    Args:
        schema: Schema name (default: public)

    Returns:
        Tables with their row counts
    """
    query = f"""
    SELECT
        schemaname,
        relname as table_name,
        n_live_tup as row_count
    FROM pg_stat_user_tables
    WHERE schemaname = '{schema}'
    ORDER BY n_live_tup DESC
    """
    return await execute_sql(query, read_only=True)


def create_authenticated_app():
    """Wrap FastMCP app with Basic Auth middleware."""
    mcp_app = mcp.http_app(path="/mcp")
    return BasicAuthMiddleware(mcp_app)


# For uvicorn: uvicorn server:app --host 0.0.0.0 --port 8080
app = create_authenticated_app()
