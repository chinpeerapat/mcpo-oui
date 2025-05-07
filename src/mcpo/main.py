import json
import os
import re
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Dict, Any, Optional

import uvicorn
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult
from starlette.routing import Mount

# Import the new utility functions from upstream
from mcpo.utils.main import get_model_fields, get_tool_handler
from mcpo.utils.auth import get_verify_api_key, APIKeyMiddleware


def substitute_env_vars(json_obj):
    """Recursively substitute environment variables in a JSON object"""
    if isinstance(json_obj, dict):
        return {k: substitute_env_vars(v) for k, v in json_obj.items()}
    elif isinstance(json_obj, list):
        return [substitute_env_vars(item) for item in json_obj]
    elif isinstance(json_obj, str):
        # Replace ${VAR} with the environment variable value
        pattern = r'\${([A-Za-z0-9_]+)}'
        matches = re.findall(pattern, json_obj)
        result = json_obj
        for var_name in matches:
            if var_name in os.environ:
                placeholder = f'${{{var_name}}}'
                result = result.replace(placeholder, os.environ[var_name])
        return result
    else:
        return json_obj


def process_config_file(config_path):
    """Process a config file and substitute environment variables"""
    with open(config_path, 'r') as f:
        config_data = json.load(f)
    
    processed_config = substitute_env_vars(config_data)
    
    return processed_config


def get_python_type(param_type: str):
    if param_type == "string":
        return str
    elif param_type == "integer":
        return int
    elif param_type == "boolean":
        return bool
    elif param_type == "number":
        return float
    elif param_type == "object":
        return Dict[str, Any]
    elif param_type == "array":
        return list
    else:
        return str  # Fallback
    # Expand as needed. PRs welcome!


def process_tool_response(result: CallToolResult) -> list:
    """Universal response processor for all tool endpoints"""
    response = []
    for content in result.content:
        if isinstance(content, types.TextContent):
            text = content.text
            if isinstance(text, str):
                try:
                    text = json.loads(text)
                except json.JSONDecodeError:
                    pass
            response.append(text)
        elif isinstance(content, types.ImageContent):
            image_data = f"data:{content.mimeType};base64,{content.data}"
            response.append(image_data)
        elif isinstance(content, types.EmbeddedResource):
            # TODO: Handle embedded resources
            response.append("Embedded resource not supported yet.")
    return response


async def create_dynamic_endpoints(app: FastAPI, api_dependency=None):
    session: ClientSession = app.state.session
    if not session:
        raise ValueError("Session is not initialized in the app state.")

    result = await session.initialize()
    server_info = getattr(result, "serverInfo", None)
    if server_info:
        app.title = server_info.name or app.title
        app.description = (
            f"{server_info.name} MCP Server" if server_info.name else app.description
        )
        app.version = server_info.version or app.version

    tools_result = await session.list_tools()
    tools = tools_result.tools

    for tool in tools:
        endpoint_name = tool.name
        endpoint_description = tool.description

        inputSchema = tool.inputSchema
        outputSchema = getattr(tool, "outputSchema", None)

        form_model_fields = get_model_fields(
            f"{endpoint_name}_form_model",
            inputSchema.get("properties", {}),
            inputSchema.get("required", []),
            inputSchema.get("$defs", {}),
        )

        response_model_fields = None
        if outputSchema:
            response_model_fields = get_model_fields(
                f"{endpoint_name}_response_model",
                outputSchema.get("properties", {}),
                outputSchema.get("required", []),
                outputSchema.get("$defs", {}),
            )

        tool_handler = get_tool_handler(
            session,
            endpoint_name,
            form_model_fields,
            response_model_fields,
        )

        app.post(
            f"/{endpoint_name}",
            summary=endpoint_name.replace("_", " ").title(),
            description=endpoint_description,
            response_model_exclude_none=True,
            dependencies=[Depends(api_dependency)] if api_dependency else [],
        )(tool_handler)


@asynccontextmanager
async def lifespan(app: FastAPI):
    server_type = getattr(app.state, "server_type", "stdio")
    command = getattr(app.state, "command", None)
    args = getattr(app.state, "args", [])
    env = getattr(app.state, "env", {})

    args = args if isinstance(args, list) else [args]
    api_dependency = getattr(app.state, "api_dependency", None)

    if (server_type == "stdio" and not command) or (
        server_type == "sse" and not args[0]
    ):
        # Main app lifespan (when config_path is provided)
        async with AsyncExitStack() as stack:
            for route in app.routes:
                if isinstance(route, Mount) and isinstance(route.app, FastAPI):
                    await stack.enter_async_context(
                        route.app.router.lifespan_context(route.app),  # noqa
                    )
            yield
    else:
        if server_type == "stdio":
            server_params = StdioServerParameters(
                command=command,
                args=args,
                env={**env},
            )

            async with stdio_client(server_params) as (reader, writer):
                async with ClientSession(reader, writer) as session:
                    app.state.session = session
                    await create_dynamic_endpoints(app, api_dependency=api_dependency)
                    yield
        if server_type == "sse":
            async with sse_client(url=args[0], sse_read_timeout=None) as (
                reader,
                writer,
            ):
                async with ClientSession(reader, writer) as session:
                    app.state.session = session
                    await create_dynamic_endpoints(app, api_dependency=api_dependency)
                    yield


async def run(
    host: str = "127.0.0.1",
    port: int = 8000,
    api_key: Optional[str] = "",
    cors_allow_origins=["*"],
    **kwargs,
):
    # Server API Key
    api_dependency = get_verify_api_key(api_key) if api_key else None
    strict_auth = kwargs.get("strict_auth", False)

    # MCP Server
    server_type = kwargs.get("server_type")  # "stdio" or "sse" or "http"
    server_command = kwargs.get("server_command")

    # MCP Config
    config_path = kwargs.get("config_path")

    # mcpo server
    name = kwargs.get("name") or "MCP OpenAPI Proxy"
    description = (
        kwargs.get("description") or "Automatically generated API from MCP Tool Schemas"
    )
    version = kwargs.get("version") or "1.0"

    ssl_certfile = kwargs.get("ssl_certfile")
    ssl_keyfile = kwargs.get("ssl_keyfile")
    path_prefix = kwargs.get("path_prefix") or "/"
    main_app = FastAPI(
        title=name,
        description=description,
        version=version,
        ssl_certfile=ssl_certfile,
        ssl_keyfile=ssl_keyfile,
        lifespan=lifespan,
    )

    main_app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_allow_origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add middleware to protect also documentation and spec
    if api_key and strict_auth:
        main_app.add_middleware(APIKeyMiddleware, api_key=api_key)

    if server_type == "sse":
        main_app.state.server_type = "sse"
        main_app.state.args = server_command[0]
        main_app.state.api_dependency = api_dependency

    elif server_command:
        main_app.state.command = server_command[0]
        main_app.state.args = server_command[1:]
        main_app.state.env = os.environ.copy()
        main_app.state.api_dependency = api_dependency

    elif config_path:
        # Use the env processor to handle environment variables
        config_data = process_config_file(config_path)
        mcp_servers = config_data.get("mcpServers", {})
        
        if not mcp_servers:
            raise ValueError("No 'mcpServers' found in config file.")

        main_app.description += "\n\n- **available tools**："
        for server_name, server_cfg in mcp_servers.items():
            sub_app = FastAPI(
                title=f"{server_name}",
                description=f"{server_name} MCP Server\n\n- [back to tool list](/docs)",
                version="1.0",
                lifespan=lifespan,
            )

            sub_app.add_middleware(
                CORSMiddleware,
                allow_origins=cors_allow_origins or ["*"],
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )

            if server_cfg.get("command"):
                # stdio
                sub_app.state.command = server_cfg["command"]
                sub_app.state.args = server_cfg.get("args", [])
                sub_app.state.env = {**os.environ, **server_cfg.get("env", {})}
            if server_cfg.get("url"):
                # SSE
                sub_app.state.server_type = "sse"
                sub_app.state.args = server_cfg["url"]

            # Add middleware to protect also documentation and spec
            if api_key and strict_auth:
                sub_app.add_middleware(APIKeyMiddleware, api_key=api_key)

            sub_app.state.api_dependency = api_dependency

            main_app.mount(f"{path_prefix}{server_name}", sub_app)
            main_app.description += f"\n    - [{server_name}](/{server_name}/docs)"
    else:
        raise ValueError("You must provide either server_command or config.")

    config = uvicorn.Config(
        app=main_app,
        host=host,
        port=port,
        ssl_certfile=ssl_certfile,
        ssl_keyfile=ssl_keyfile,
        log_level="info",
    )
    server = uvicorn.Server(config)

    await server.serve()
