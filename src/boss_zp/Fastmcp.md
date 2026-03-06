# http

# `fastmcp.server.http`

## Functions

### `set_http_request` <sup><a href="https://github.com/jlowin/fastmcp/blob/main/src/fastmcp/server/http.py#L77" target="_blank"><Icon icon="github" style="width: 14px; height: 14px;" /></a></sup>

```python  theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
set_http_request(request: Request) -> Generator[Request, None, None]
```

### `create_base_app` <sup><a href="https://github.com/jlowin/fastmcp/blob/main/src/fastmcp/server/http.py#L101" target="_blank"><Icon icon="github" style="width: 14px; height: 14px;" /></a></sup>

```python  theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
create_base_app(routes: list[BaseRoute], middleware: list[Middleware], debug: bool = False, lifespan: Callable | None = None) -> StarletteWithLifespan
```

Create a base Starlette app with common middleware and routes.

**Args:**

* `routes`: List of routes to include in the app
* `middleware`: List of middleware to include in the app
* `debug`: Whether to enable debug mode
* `lifespan`: Optional lifespan manager for the app

**Returns:**

* A Starlette application

### `create_sse_app` <sup><a href="https://github.com/jlowin/fastmcp/blob/main/src/fastmcp/server/http.py#L129" target="_blank"><Icon icon="github" style="width: 14px; height: 14px;" /></a></sup>

```python  theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
create_sse_app(server: FastMCP[LifespanResultT], message_path: str, sse_path: str, auth: AuthProvider | None = None, debug: bool = False, routes: list[BaseRoute] | None = None, middleware: list[Middleware] | None = None) -> StarletteWithLifespan
```

Return an instance of the SSE server app.

**Args:**

* `server`: The FastMCP server instance
* `message_path`: Path for SSE messages
* `sse_path`: Path for SSE connections
* `auth`: Optional authentication provider (AuthProvider)
* `debug`: Whether to enable debug mode
* `routes`: Optional list of custom routes
* `middleware`: Optional list of middleware

Returns:
A Starlette application with RequestContextMiddleware

### `create_streamable_http_app` <sup><a href="https://github.com/jlowin/fastmcp/blob/main/src/fastmcp/server/http.py#L255" target="_blank"><Icon icon="github" style="width: 14px; height: 14px;" /></a></sup>

```python  theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
create_streamable_http_app(server: FastMCP[LifespanResultT], streamable_http_path: str, event_store: EventStore | None = None, auth: AuthProvider | None = None, json_response: bool = False, stateless_http: bool = False, debug: bool = False, routes: list[BaseRoute] | None = None, middleware: list[Middleware] | None = None) -> StarletteWithLifespan
```

Return an instance of the StreamableHTTP server app.

**Args:**

* `server`: The FastMCP server instance
* `streamable_http_path`: Path for StreamableHTTP connections
* `event_store`: Optional event store for session management
* `auth`: Optional authentication provider (AuthProvider)
* `json_response`: Whether to use JSON response format
* `stateless_http`: Whether to use stateless mode (new transport per request)
* `debug`: Whether to enable debug mode
* `routes`: Optional list of custom routes
* `middleware`: Optional list of middleware

**Returns:**

* A Starlette application with StreamableHTTP support

## Classes

### `StreamableHTTPASGIApp` <sup><a href="https://github.com/jlowin/fastmcp/blob/main/src/fastmcp/server/http.py#L32" target="_blank"><Icon icon="github" style="width: 14px; height: 14px;" /></a></sup>

ASGI application wrapper for Streamable HTTP server transport.

### `StarletteWithLifespan` <sup><a href="https://github.com/jlowin/fastmcp/blob/main/src/fastmcp/server/http.py#L70" target="_blank"><Icon icon="github" style="width: 14px; height: 14px;" /></a></sup>

**Methods:**

#### `lifespan` <sup><a href="https://github.com/jlowin/fastmcp/blob/main/src/fastmcp/server/http.py#L72" target="_blank"><Icon icon="github" style="width: 14px; height: 14px;" /></a></sup>

```python  theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
lifespan(self) -> Lifespan[Starlette]
```

### `RequestContextMiddleware` <sup><a href="https://github.com/jlowin/fastmcp/blob/main/src/fastmcp/server/http.py#L85" target="_blank"><Icon icon="github" style="width: 14px; height: 14px;" /></a></sup>

Middleware that stores each request in a ContextVar

# Quickstart

Welcome! This guide will help you quickly set up FastMCP, run your first MCP server, and deploy a server to FastMCP Cloud.

If you haven't already installed FastMCP, follow the [installation instructions](/getting-started/installation).

## Create a FastMCP Server

A FastMCP server is a collection of tools, resources, and other MCP components. To create a server, start by instantiating the `FastMCP` class.

Create a new file called `my_server.py` and add the following code:

```python my_server.py theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
from fastmcp import FastMCP

mcp = FastMCP("My MCP Server")
```

That's it! You've created a FastMCP server, albeit a very boring one. Let's add a tool to make it more interesting.

## Add a Tool

To add a tool that returns a simple greeting, write a function and decorate it with `@mcp.tool` to register it with the server:

```python my_server.py {5-7} theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
from fastmcp import FastMCP

mcp = FastMCP("My MCP Server")

@mcp.tool
def greet(name: str) -> str:
    return f"Hello, {name}!"
```

## Run the Server

The simplest way to run your FastMCP server is to call its `run()` method. You can choose between different transports, like `stdio` for local servers, or `http` for remote access:

<CodeGroup>
  ```python my_server.py (stdio) {9, 10} theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
  from fastmcp import FastMCP

  mcp = FastMCP("My MCP Server")

  @mcp.tool
  def greet(name: str) -> str:
      return f"Hello, {name}!"

  if __name__ == "__main__":
      mcp.run()
  ```

  ```python my_server.py (HTTP) {9, 10} theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
  from fastmcp import FastMCP

  mcp = FastMCP("My MCP Server")

  @mcp.tool
  def greet(name: str) -> str:
      return f"Hello, {name}!"

  if __name__ == "__main__":
      mcp.run(transport="http", port=8000)
  ```
</CodeGroup>

This lets us run the server with `python my_server.py`. The stdio transport is the traditional way to connect MCP servers to clients, while the HTTP transport enables remote connections.

<Tip>
  Why do we need the `if __name__ == "__main__":` block?

  The `__main__` block is recommended for consistency and compatibility, ensuring your server works with all MCP clients that execute your server file as a script. Users who will exclusively run their server with the FastMCP CLI can omit it, as the CLI imports the server object directly.
</Tip>

### Using the FastMCP CLI

You can also use the `fastmcp run` command to start your server. Note that the FastMCP CLI **does not** execute the `__main__` block of your server file. Instead, it imports your server object and runs it with whatever transport and options you provide.

For example, to run this server with the default stdio transport (no matter how you called `mcp.run()`), you can use the following command:

```bash  theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
fastmcp run my_server.py:mcp
```

To run this server with the HTTP transport, you can use the following command:

```bash  theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
fastmcp run my_server.py:mcp --transport http --port 8000
```

## Call Your Server

Once your server is running with HTTP transport, you can connect to it with a FastMCP client or any LLM client that supports the MCP protocol:

```python my_client.py theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
import asyncio
from fastmcp import Client

client = Client("http://localhost:8000/mcp")

async def call_tool(name: str):
    async with client:
        result = await client.call_tool("greet", {"name": name})
        print(result)

asyncio.run(call_tool("Ford"))
```

Note that:

* FastMCP clients are asynchronous, so we need to use `asyncio.run` to run the client
* We must enter a client context (`async with client:`) before using the client
* You can make multiple client calls within the same context

## Deploy to FastMCP Cloud

[FastMCP Cloud](https://fastmcp.cloud) is a hosting service run by the FastMCP team at [Prefect](https://www.prefect.io/fastmcp). It is optimized to deploy authenticated FastMCP servers as quickly as possible, giving you a secure URL that you can plug into any LLM client.

<Info>
  FastMCP Cloud is **free for personal servers** and offers simple pay-as-you-go pricing for teams.
</Info>

To deploy your server, you'll need a [GitHub account](https://github.com). Once you have one, you can deploy your server in three steps:

1. Push your `my_server.py` file to a GitHub repository
2. Sign in to [FastMCP Cloud](https://fastmcp.cloud) with your GitHub account
3. Create a new project from your repository and enter `my_server.py:mcp` as the server entrypoint

That's it! FastMCP Cloud will build and deploy your server, making it available at a URL like `https://your-project.fastmcp.app/mcp`. You can chat with it to test its functionality, or connect to it from any LLM client that supports the MCP protocol.

For more details, see the [FastMCP Cloud guide](/deployment/fastmcp-cloud).

# Quickstart

Welcome! This guide will help you quickly set up FastMCP, run your first MCP server, and deploy a server to FastMCP Cloud.

If you haven't already installed FastMCP, follow the [installation instructions](/getting-started/installation).

## Create a FastMCP Server

A FastMCP server is a collection of tools, resources, and other MCP components. To create a server, start by instantiating the `FastMCP` class.

Create a new file called `my_server.py` and add the following code:

```python my_server.py theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
from fastmcp import FastMCP

mcp = FastMCP("My MCP Server")
```

That's it! You've created a FastMCP server, albeit a very boring one. Let's add a tool to make it more interesting.

## Add a Tool

To add a tool that returns a simple greeting, write a function and decorate it with `@mcp.tool` to register it with the server:

```python my_server.py {5-7} theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
from fastmcp import FastMCP

mcp = FastMCP("My MCP Server")

@mcp.tool
def greet(name: str) -> str:
    return f"Hello, {name}!"
```

## Run the Server

The simplest way to run your FastMCP server is to call its `run()` method. You can choose between different transports, like `stdio` for local servers, or `http` for remote access:

<CodeGroup>
  ```python my_server.py (stdio) {9, 10} theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
  from fastmcp import FastMCP

  mcp = FastMCP("My MCP Server")

  @mcp.tool
  def greet(name: str) -> str:
      return f"Hello, {name}!"

  if __name__ == "__main__":
      mcp.run()
  ```

  ```python my_server.py (HTTP) {9, 10} theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
  from fastmcp import FastMCP

  mcp = FastMCP("My MCP Server")

  @mcp.tool
  def greet(name: str) -> str:
      return f"Hello, {name}!"

  if __name__ == "__main__":
      mcp.run(transport="http", port=8000)
  ```
</CodeGroup>

This lets us run the server with `python my_server.py`. The stdio transport is the traditional way to connect MCP servers to clients, while the HTTP transport enables remote connections.

<Tip>
  Why do we need the `if __name__ == "__main__":` block?

  The `__main__` block is recommended for consistency and compatibility, ensuring your server works with all MCP clients that execute your server file as a script. Users who will exclusively run their server with the FastMCP CLI can omit it, as the CLI imports the server object directly.
</Tip>

### Using the FastMCP CLI

You can also use the `fastmcp run` command to start your server. Note that the FastMCP CLI **does not** execute the `__main__` block of your server file. Instead, it imports your server object and runs it with whatever transport and options you provide.

For example, to run this server with the default stdio transport (no matter how you called `mcp.run()`), you can use the following command:

```bash  theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
fastmcp run my_server.py:mcp
```

To run this server with the HTTP transport, you can use the following command:

```bash  theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
fastmcp run my_server.py:mcp --transport http --port 8000
```

## Call Your Server

Once your server is running with HTTP transport, you can connect to it with a FastMCP client or any LLM client that supports the MCP protocol:

```python my_client.py theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
import asyncio
from fastmcp import Client

client = Client("http://localhost:8000/mcp")

async def call_tool(name: str):
    async with client:
        result = await client.call_tool("greet", {"name": name})
        print(result)

asyncio.run(call_tool("Ford"))
```

Note that:

* FastMCP clients are asynchronous, so we need to use `asyncio.run` to run the client
* We must enter a client context (`async with client:`) before using the client
* You can make multiple client calls within the same context

## Deploy to FastMCP Cloud

[FastMCP Cloud](https://fastmcp.cloud) is a hosting service run by the FastMCP team at [Prefect](https://www.prefect.io/fastmcp). It is optimized to deploy authenticated FastMCP servers as quickly as possible, giving you a secure URL that you can plug into any LLM client.

<Info>
  FastMCP Cloud is **free for personal servers** and offers simple pay-as-you-go pricing for teams.
</Info>

To deploy your server, you'll need a [GitHub account](https://github.com). Once you have one, you can deploy your server in three steps:

1. Push your `my_server.py` file to a GitHub repository
2. Sign in to [FastMCP Cloud](https://fastmcp.cloud) with your GitHub account
3. Create a new project from your repository and enter `my_server.py:mcp` as the server entrypoint

That's it! FastMCP Cloud will build and deploy your server, making it available at a URL like `https://your-project.fastmcp.app/mcp`. You can chat with it to test its functionality, or connect to it from any LLM client that supports the MCP protocol.

For more details, see the [FastMCP Cloud guide](/deployment/fastmcp-cloud).

# Server Composition

> Combine multiple FastMCP servers into a single, larger application using mounting and importing.

export const VersionBadge = ({version}) => {
  return <code className="version-badge-container">
            <p className="version-badge">
                <span className="version-badge-label">New in version:</span> 
                <code className="version-badge-version">{version}</code>
            </p>
        </code>;
};

<VersionBadge version="2.2.0" />

As your MCP applications grow, you might want to organize your tools, resources, and prompts into logical modules or reuse existing server components. FastMCP supports composition through two methods:

* **`import_server`**: For a one-time copy of components with prefixing (static composition).
* **`mount`**: For creating a live link where the main server delegates requests to the subserver (dynamic composition).

## Why Compose Servers?

* **Modularity**: Break down large applications into smaller, focused servers (e.g., a `WeatherServer`, a `DatabaseServer`, a `CalendarServer`).
* **Reusability**: Create common utility servers (e.g., a `TextProcessingServer`) and mount them wherever needed.
* **Teamwork**: Different teams can work on separate FastMCP servers that are later combined.
* **Organization**: Keep related functionality grouped together logically.

### Importing vs Mounting

The choice of importing or mounting depends on your use case and requirements.

| Feature              | Importing                                                  | Mounting                                    |
| -------------------- | ---------------------------------------------------------- | ------------------------------------------- |
| **Method**           | `FastMCP.import_server(server, prefix=None)`               | `FastMCP.mount(server, prefix=None)`        |
| **Composition Type** | One-time copy (static)                                     | Live link (dynamic)                         |
| **Updates**          | Changes to subserver NOT reflected                         | Changes to subserver immediately reflected  |
| **Performance**      | Fast - no runtime delegation                               | Slower - affected by slowest mounted server |
| **Prefix**           | Optional - omit for original names                         | Optional - omit for original names          |
| **Best For**         | Bundling finalized components, performance-critical setups | Modular runtime composition                 |

### Proxy Servers

FastMCP supports [MCP proxying](/servers/proxy), which allows you to mirror a local or remote server in a local FastMCP instance. Proxies are fully compatible with both importing and mounting.

<VersionBadge version="2.4.0" />

You can also create proxies from configuration dictionaries that follow the MCPConfig schema, which is useful for quickly connecting to one or more remote servers. See the [Proxy Servers documentation](/servers/proxy#configuration-based-proxies) for details on configuration-based proxying. Note that MCPConfig follows an emerging standard and its format may evolve over time.

Prefixing rules for tools, prompts, resources, and templates are identical across importing, mounting, and proxies.

## Importing (Static Composition)

The `import_server()` method copies all components (tools, resources, templates, prompts) from one `FastMCP` instance (the *subserver*) into another (the *main server*). An optional `prefix` can be provided to avoid naming conflicts. If no prefix is provided, components are imported without modification. When multiple servers are imported with the same prefix (or no prefix), the most recently imported server's components take precedence.

```python  theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
from fastmcp import FastMCP
import asyncio

# Define subservers
weather_mcp = FastMCP(name="WeatherService")

@weather_mcp.tool
def get_forecast(city: str) -> dict:
    """Get weather forecast."""
    return {"city": city, "forecast": "Sunny"}

@weather_mcp.resource("data://cities/supported")
def list_supported_cities() -> list[str]:
    """List cities with weather support."""
    return ["London", "Paris", "Tokyo"]

# Define main server
main_mcp = FastMCP(name="MainApp")

# Import subserver
async def setup():
    await main_mcp.import_server(weather_mcp, prefix="weather")

# Result: main_mcp now contains prefixed components:
# - Tool: "weather_get_forecast"
# - Resource: "data://weather/cities/supported" 

if __name__ == "__main__":
    asyncio.run(setup())
    main_mcp.run()
```

### How Importing Works

When you call `await main_mcp.import_server(subserver, prefix={whatever})`:

1. **Tools**: All tools from `subserver` are added to `main_mcp` with names prefixed using `{prefix}_`.
   * `subserver.tool(name="my_tool")` becomes `main_mcp.tool(name="{prefix}_my_tool")`.
2. **Resources**: All resources are added with both URIs and names prefixed.
   * URI: `subserver.resource(uri="data://info")` becomes `main_mcp.resource(uri="data://{prefix}/info")`.
   * Name: `resource.name` becomes `"{prefix}_{resource.name}"`.
3. **Resource Templates**: Templates are prefixed similarly to resources.
   * URI: `subserver.resource(uri="data://{id}")` becomes `main_mcp.resource(uri="data://{prefix}/{id}")`.
   * Name: `template.name` becomes `"{prefix}_{template.name}"`.
4. **Prompts**: All prompts are added with names prefixed using `{prefix}_`.
   * `subserver.prompt(name="my_prompt")` becomes `main_mcp.prompt(name="{prefix}_my_prompt")`.

Note that `import_server` performs a **one-time copy** of components. Changes made to the `subserver` *after* importing **will not** be reflected in `main_mcp`. The `subserver`'s `lifespan` context is also **not** executed by the main server.

<Tip>
  The `prefix` parameter is optional. If omitted, components are imported without modification.
</Tip>

#### Importing Without Prefixes

<VersionBadge version="2.9.0" />

You can also import servers without specifying a prefix, which copies components using their original names:

```python  theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}

from fastmcp import FastMCP
import asyncio

# Define subservers
weather_mcp = FastMCP(name="WeatherService")

@weather_mcp.tool
def get_forecast(city: str) -> dict:
    """Get weather forecast."""
    return {"city": city, "forecast": "Sunny"}

@weather_mcp.resource("data://cities/supported")
def list_supported_cities() -> list[str]:
    """List cities with weather support."""
    return ["London", "Paris", "Tokyo"]

# Define main server
main_mcp = FastMCP(name="MainApp")

# Import subserver
async def setup():
    # Import without prefix - components keep original names
    await main_mcp.import_server(weather_mcp)

# Result: main_mcp now contains:
# - Tool: "get_forecast" (original name preserved)
# - Resource: "data://cities/supported" (original URI preserved)

if __name__ == "__main__":
    asyncio.run(setup())
    main_mcp.run()
```

#### Conflict Resolution

<VersionBadge version="2.9.0" />

When importing multiple servers with the same prefix, or no prefix, components from the **most recently imported** server take precedence.

## Mounting (Live Linking)

The `mount()` method creates a **live link** between the `main_mcp` server and the `subserver`. Instead of copying components, requests for components matching the optional `prefix` are **delegated** to the `subserver` at runtime. If no prefix is provided, the subserver's components are accessible without prefixing. When multiple servers are mounted with the same prefix (or no prefix), the most recently mounted server takes precedence for conflicting component names.

```python  theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
import asyncio
from fastmcp import FastMCP, Client

# Define subserver
dynamic_mcp = FastMCP(name="DynamicService")

@dynamic_mcp.tool
def initial_tool():
    """Initial tool demonstration."""
    return "Initial Tool Exists"

# Mount subserver (synchronous operation)
main_mcp = FastMCP(name="MainAppLive")
main_mcp.mount(dynamic_mcp, prefix="dynamic")

# Add a tool AFTER mounting - it will be accessible through main_mcp
@dynamic_mcp.tool
def added_later():
    """Tool added after mounting."""
    return "Tool Added Dynamically!"

# Testing access to mounted tools
async def test_dynamic_mount():
    tools = await main_mcp.get_tools()
    print("Available tools:", list(tools.keys()))
    # Shows: ['dynamic_initial_tool', 'dynamic_added_later']
    
    async with Client(main_mcp) as client:
        result = await client.call_tool("dynamic_added_later")
        print("Result:", result.data)
        # Shows: "Tool Added Dynamically!"

if __name__ == "__main__":
    asyncio.run(test_dynamic_mount())
```

### How Mounting Works

When mounting is configured:

1. **Live Link**: The parent server establishes a connection to the mounted server.
2. **Dynamic Updates**: Changes to the mounted server are immediately reflected when accessed through the parent.
3. **Prefixed Access**: The parent server uses prefixes to route requests to the mounted server.
4. **Delegation**: Requests for components matching the prefix are delegated to the mounted server at runtime.

The same prefixing rules apply as with `import_server` for naming tools, resources, templates, and prompts. This includes prefixing both the URIs/keys and the names of resources and templates for better identification in multi-server configurations.

<Tip>
  The `prefix` parameter is optional. If omitted, components are mounted without modification.
</Tip>

#### Performance Considerations

Due to the "live link", operations like `list_tools()` on the parent server will be impacted by the speed of the slowest mounted server. In particular, HTTP-based mounted servers can introduce significant latency (300-400ms vs 1-2ms for local tools), and this slowdown affects the whole server, not just interactions with the HTTP-proxied tools. If performance is important, importing tools via [`import_server()`](#importing-static-composition) may be a more appropriate solution as it copies components once at startup rather than delegating requests at runtime.

#### Mounting Without Prefixes

<VersionBadge version="2.9.0" />

You can also mount servers without specifying a prefix, which makes components accessible without prefixing. This works identically to [importing without prefixes](#importing-without-prefixes), including [conflict resolution](#conflict-resolution).

### Direct vs. Proxy Mounting

<VersionBadge version="2.2.7" />

FastMCP supports two mounting modes:

1. **Direct Mounting** (default): The parent server directly accesses the mounted server's objects in memory.
   * No client lifecycle events occur on the mounted server
   * The mounted server's lifespan context is not executed
   * Communication is handled through direct method calls
2. **Proxy Mounting**: The parent server treats the mounted server as a separate entity and communicates with it through a client interface.
   * Full client lifecycle events occur on the mounted server
   * The mounted server's lifespan is executed when a client connects
   * Communication happens via an in-memory Client transport

```python  theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
# Direct mounting (default when no custom lifespan)
main_mcp.mount(api_server, prefix="api")

# Proxy mounting (preserves full client lifecycle)
main_mcp.mount(api_server, prefix="api", as_proxy=True)

# Mounting without a prefix (components accessible without prefixing)
main_mcp.mount(api_server)
```

FastMCP automatically uses proxy mounting when the mounted server has a custom lifespan, but you can override this behavior with the `as_proxy` parameter.

#### Interaction with Proxy Servers

When using `FastMCP.as_proxy()` to create a proxy server, mounting that server will always use proxy mounting:

```python  theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
# Create a proxy for a remote server
remote_proxy = FastMCP.as_proxy(Client("http://example.com/mcp"))

# Mount the proxy (always uses proxy mounting)
main_server.mount(remote_proxy, prefix="remote")
```

## Tag Filtering with Composition

<VersionBadge version="2.9.0" />

When using `include_tags` or `exclude_tags` on a parent server, these filters apply **recursively** to all components, including those from mounted or imported servers. This allows you to control which components are exposed at the parent level, regardless of how your application is composed.

```python  theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
import asyncio
from fastmcp import FastMCP, Client

# Create a subserver with tools tagged for different environments
api_server = FastMCP(name="APIServer")

@api_server.tool(tags={"production"})
def prod_endpoint() -> str:
    """Production-ready endpoint."""
    return "Production data"

@api_server.tool(tags={"development"})
def dev_endpoint() -> str:
    """Development-only endpoint."""
    return "Debug data"

# Mount the subserver with production tag filtering at parent level
prod_app = FastMCP(name="ProductionApp", include_tags={"production"})
prod_app.mount(api_server, prefix="api")

# Test the filtering
async def test_filtering():
    async with Client(prod_app) as client:
        tools = await client.list_tools()
        print("Available tools:", [t.name for t in tools])
        # Shows: ['api_prod_endpoint']
        # The 'api_dev_endpoint' is filtered out

        # Calling the filtered tool raises an error
        try:
            await client.call_tool("api_dev_endpoint")
        except Exception as e:
            print(f"Filtered tool not accessible: {e}")

if __name__ == "__main__":
    asyncio.run(test_filtering())
```

### How Recursive Filtering Works

Tag filters apply in the following order:

1. **Child Server Filters**: Each mounted/imported server first applies its own `include_tags`/`exclude_tags` to its components.
2. **Parent Server Filters**: The parent server then applies its own `include_tags`/`exclude_tags` to all components, including those from child servers.

This ensures that parent server tag policies act as a global policy for everything the parent server exposes, no matter how your application is composed.

<Note>
  This filtering applies to both **listing** (e.g., `list_tools()`) and **execution** (e.g., `call_tool()`). Filtered components are neither visible nor executable through the parent server.
</Note>

## Resource Prefix Formats

<VersionBadge version="2.4.0" />

When mounting or importing servers, resource URIs are usually prefixed to avoid naming conflicts. FastMCP supports two different formats for resource prefixes:

### Path Format (Default)

In path format, prefixes are added to the path component of the URI:

```
resource://prefix/path/to/resource
```

This is the default format since FastMCP 2.4. This format is recommended because it avoids issues with URI protocol restrictions (like underscores not being allowed in protocol names).

### Protocol Format (Legacy)

In protocol format, prefixes are added as part of the protocol:

```
prefix+resource://path/to/resource
```

This was the default format in FastMCP before 2.4. While still supported, it's not recommended for new code as it can cause problems with prefix names that aren't valid in URI protocols.

### Configuring the Prefix Format

You can configure the prefix format globally in code:

```python  theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
import fastmcp
fastmcp.settings.resource_prefix_format = "protocol" 
```

Or via environment variable:

```bash  theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
FASTMCP_RESOURCE_PREFIX_FORMAT=protocol
```

Or per-server:

```python  theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
from fastmcp import FastMCP

# Create a server that uses legacy protocol format
server = FastMCP("LegacyServer", resource_prefix_format="protocol")

# Create a server that uses new path format
server = FastMCP("NewServer", resource_prefix_format="path")
```

When mounting or importing servers, the prefix format of the parent server is used.

<Note>
  When mounting servers, custom HTTP routes defined with `@server.custom_route()` are also forwarded to the parent server, making them accessible through the parent's HTTP application.
</Note>

# MCP Context

> Access MCP capabilities like logging, progress, and resources within your MCP objects.

export const VersionBadge = ({version}) => {
  return <code className="version-badge-container">
            <p className="version-badge">
                <span className="version-badge-label">New in version:</span> 
                <code className="version-badge-version">{version}</code>
            </p>
        </code>;
};

When defining FastMCP [tools](/servers/tools), [resources](/servers/resources), resource templates, or [prompts](/servers/prompts), your functions might need to interact with the underlying MCP session or access advanced server capabilities. FastMCP provides the `Context` object for this purpose.

## What Is Context?

The `Context` object provides a clean interface to access MCP features within your functions, including:

* **Logging**: Send debug, info, warning, and error messages back to the client
* **Progress Reporting**: Update the client on the progress of long-running operations
* **Resource Access**: List and read data from resources registered with the server
* **Prompt Access**: List and retrieve prompts registered with the server
* **LLM Sampling**: Request the client's LLM to generate text based on provided messages
* **User Elicitation**: Request structured input from users during tool execution
* **State Management**: Store and share data between middleware and the handler within a single request
* **Request Information**: Access metadata about the current request
* **Server Access**: When needed, access the underlying FastMCP server instance

## Accessing the Context

### Via Dependency Injection

To use the context object within any of your functions, simply add a parameter to your function signature and type-hint it as `Context`. FastMCP will automatically inject the context instance when your function is called.

**Key Points:**

* The parameter name (e.g., `ctx`, `context`) doesn't matter, only the type hint `Context` is important.
* The context parameter can be placed anywhere in your function's signature; it will not be exposed to MCP clients as a valid parameter.
* The context is optional - functions that don't need it can omit the parameter entirely.
* Context methods are async, so your function usually needs to be async as well.
* The type hint can be a union (`Context | None`) or use `Annotated[]` and it will still work properly.
* **Each MCP request receives a new context object.** Context is scoped to a single request; state or data set in one request will not be available in subsequent requests.
* Context is only available during a request; attempting to use context methods outside a request will raise errors. If you need to debug or call your context methods outside of a request, you can type your variable as `Context | None=None` to avoid missing argument errors.

#### Tools

```python {1, 6} theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
from fastmcp import FastMCP, Context

mcp = FastMCP(name="Context Demo")

@mcp.tool
async def process_file(file_uri: str, ctx: Context) -> str:
    """Processes a file, using context for logging and resource access."""
    # Context is available as the ctx parameter
    return "Processed file"
```

#### Resources and Templates

<VersionBadge version="2.2.5" />

```python {1, 6, 12} theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
from fastmcp import FastMCP, Context

mcp = FastMCP(name="Context Demo")

@mcp.resource("resource://user-data")
async def get_user_data(ctx: Context) -> dict:
    """Fetch personalized user data based on the request context."""
    # Context is available as the ctx parameter
    return {"user_id": "example"}

@mcp.resource("resource://users/{user_id}/profile")
async def get_user_profile(user_id: str, ctx: Context) -> dict:
    """Fetch user profile with context-aware logging."""
    # Context is available as the ctx parameter
    return {"id": user_id}
```

#### Prompts

<VersionBadge version="2.2.5" />

```python {1, 6} theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
from fastmcp import FastMCP, Context

mcp = FastMCP(name="Context Demo")

@mcp.prompt
async def data_analysis_request(dataset: str, ctx: Context) -> str:
    """Generate a request to analyze data with contextual information."""
    # Context is available as the ctx parameter
    return f"Please analyze the following dataset: {dataset}"
```

### Via Runtime Dependency Function

<VersionBadge version="2.2.11" />

While the simplest way to access context is through function parameter injection as shown above, there are cases where you need to access the context in code that may not be easy to modify to accept a context parameter, or that is nested deeper within your function calls.

FastMCP provides dependency functions that allow you to retrieve the active context from anywhere within a server request's execution flow:

```python {2,9} theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
from fastmcp import FastMCP
from fastmcp.server.dependencies import get_context

mcp = FastMCP(name="Dependency Demo")

# Utility function that needs context but doesn't receive it as a parameter
async def process_data(data: list[float]) -> dict:
    # Get the active context - only works when called within a request
    ctx = get_context()    
    await ctx.info(f"Processing {len(data)} data points")
    
@mcp.tool
async def analyze_dataset(dataset_name: str) -> dict:
    # Call utility function that uses context internally
    data = load_data(dataset_name)
    await process_data(data)
```

**Important Notes:**

* The `get_context` function should only be used within the context of a server request. Calling it outside of a request will raise a `RuntimeError`.
* The `get_context` function is server-only and should not be used in client code.

## Context Capabilities

FastMCP provides several advanced capabilities through the context object. Each capability has dedicated documentation with comprehensive examples and best practices:

### Logging

Send debug, info, warning, and error messages back to the MCP client for visibility into function execution.

```python  theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
await ctx.debug("Starting analysis")
await ctx.info(f"Processing {len(data)} items") 
await ctx.warning("Deprecated parameter used")
await ctx.error("Processing failed")
```

See [Server Logging](/servers/logging) for complete documentation and examples.

### Client Elicitation

<VersionBadge version="2.10.0" />

Request structured input from clients during tool execution, enabling interactive workflows and progressive disclosure. This is a new feature in the 6/18/2025 MCP spec.

```python  theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
result = await ctx.elicit("Enter your name:", response_type=str)
if result.action == "accept":
    name = result.data
```

See [User Elicitation](/servers/elicitation) for detailed examples and supported response types.

### LLM Sampling

<VersionBadge version="2.0.0" />

Request the client's LLM to generate text based on provided messages, useful for leveraging AI capabilities within your tools.

```python  theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
response = await ctx.sample("Analyze this data", temperature=0.7)
```

See [LLM Sampling](/servers/sampling) for comprehensive usage and advanced techniques.

### Progress Reporting

Update clients on the progress of long-running operations, enabling progress indicators and better user experience.

```python  theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
await ctx.report_progress(progress=50, total=100)  # 50% complete
```

See [Progress Reporting](/servers/progress) for detailed patterns and examples.

### Resource Access

List and read data from resources registered with your FastMCP server, allowing access to files, configuration, or dynamic content.

```python  theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
# List available resources
resources = await ctx.list_resources()

# Read a specific resource
content_list = await ctx.read_resource("resource://config")
content = content_list[0].content
```

**Method signatures:**

* **`ctx.list_resources() -> list[MCPResource]`**: <VersionBadge version="2.13.0" /> Returns list of all available resources
* **`ctx.read_resource(uri: str | AnyUrl) -> list[ReadResourceContents]`**: Returns a list of resource content parts

### Prompt Access

<VersionBadge version="2.13.0" />

List and retrieve prompts registered with your FastMCP server, allowing tools and middleware to discover and use available prompts programmatically.

```python  theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
# List available prompts
prompts = await ctx.list_prompts()

# Get a specific prompt with arguments
result = await ctx.get_prompt("analyze_data", {"dataset": "users"})
messages = result.messages
```

**Method signatures:**

* **`ctx.list_prompts() -> list[MCPPrompt]`**: Returns list of all available prompts
* **`ctx.get_prompt(name: str, arguments: dict[str, Any] | None = None) -> GetPromptResult`**: Get a specific prompt with optional arguments

### State Management

<VersionBadge version="2.11.0" />

Store and share data between middleware and handlers within a single MCP request. Each MCP request (such as calling a tool, reading a resource, listing tools, or listing resources) receives its own context object with isolated state. Context state is particularly useful for passing information from [middleware](/servers/middleware) to your handlers.

To store a value in the context state, use `ctx.set_state(key, value)`. To retrieve a value, use `ctx.get_state(key)`.

<Warning>
  Context state is scoped to a single MCP request. Each operation (tool call, resource read, list operation, etc.) receives a new context object. State set during one request will not be available in subsequent requests. For persistent data storage across requests, use external storage mechanisms like databases, files, or in-memory caches.
</Warning>

This simplified example shows how to use MCP middleware to store user info in the context state, and how to access that state in a tool:

```python {7-8, 16-17} theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
from fastmcp.server.middleware import Middleware, MiddlewareContext

class UserAuthMiddleware(Middleware):
    async def on_call_tool(self, context: MiddlewareContext, call_next):

        # Middleware stores user info in context state
        context.fastmcp_context.set_state("user_id", "user_123")
        context.fastmcp_context.set_state("permissions", ["read", "write"])

        return await call_next(context)

@mcp.tool
async def secure_operation(data: str, ctx: Context) -> str:
    """Tool can access state set by middleware."""

    user_id = ctx.get_state("user_id")  # "user_123"
    permissions = ctx.get_state("permissions")  # ["read", "write"]
    
    if "write" not in permissions:
        return "Access denied"
    
    return f"Processing {data} for user {user_id}"
```

**Method signatures:**

* **`ctx.set_state(key: str, value: Any) -> None`**: Store a value in the context state
* **`ctx.get_state(key: str) -> Any`**: Retrieve a value from the context state (returns None if not found)

**State Inheritance:**
When a new context is created (nested contexts), it inherits a copy of its parent's state. This ensures that:

* State set on a child context never affects the parent context
* State set on a parent context after the child context is initialized is not propagated to the child context

This makes state management predictable and prevents unexpected side effects between nested operations.

### Change Notifications

<VersionBadge version="2.9.1" />

FastMCP automatically sends list change notifications when components (such as tools, resources, or prompts) are added, removed, enabled, or disabled. In rare cases where you need to manually trigger these notifications, you can use the context methods:

```python  theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
@mcp.tool
async def custom_tool_management(ctx: Context) -> str:
    """Example of manual notification after custom tool changes."""
    # After making custom changes to tools
    await ctx.send_tool_list_changed()
    await ctx.send_resource_list_changed()
    await ctx.send_prompt_list_changed()
    return "Notifications sent"
```

These methods are primarily used internally by FastMCP's automatic notification system and most users will not need to invoke them directly.

### FastMCP Server

To access the underlying FastMCP server instance, you can use the `ctx.fastmcp` property:

```python  theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
@mcp.tool
async def my_tool(ctx: Context) -> None:
    # Access the FastMCP server instance
    server_name = ctx.fastmcp.name
    ...
```

### MCP Request

Access metadata about the current request and client.

```python  theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
@mcp.tool
async def request_info(ctx: Context) -> dict:
    """Return information about the current request."""
    return {
        "request_id": ctx.request_id,
        "client_id": ctx.client_id or "Unknown client"
    }
```

**Available Properties:**

* **`ctx.request_id -> str`**: Get the unique ID for the current MCP request
* **`ctx.client_id -> str | None`**: Get the ID of the client making the request, if provided during initialization
* **`ctx.session_id -> str | None`**: Get the MCP session ID for session-based data sharing (HTTP transports only)

<Warning>
  The MCP request is part of the low-level MCP SDK and intended for advanced use cases. Most users will not need to use it directly.
</Warning>

## Runtime Dependencies

### HTTP Requests

<VersionBadge version="2.2.11" />

The recommended way to access the current HTTP request is through the `get_http_request()` dependency function:

```python {2, 3, 11} theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_request
from starlette.requests import Request

mcp = FastMCP(name="HTTP Request Demo")

@mcp.tool
async def user_agent_info() -> dict:
    """Return information about the user agent."""
    # Get the HTTP request
    request: Request = get_http_request()
    
    # Access request data
    user_agent = request.headers.get("user-agent", "Unknown")
    client_ip = request.client.host if request.client else "Unknown"
    
    return {
        "user_agent": user_agent,
        "client_ip": client_ip,
        "path": request.url.path,
    }
```

This approach works anywhere within a request's execution flow, not just within your MCP function. It's useful when:

1. You need access to HTTP information in helper functions
2. You're calling nested functions that need HTTP request data
3. You're working with middleware or other request processing code

### HTTP Headers

<VersionBadge version="2.2.11" />

If you only need request headers and want to avoid potential errors, you can use the `get_http_headers()` helper:

```python {2, 10} theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_headers

mcp = FastMCP(name="Headers Demo")

@mcp.tool
async def safe_header_info() -> dict:
    """Safely get header information without raising errors."""
    # Get headers (returns empty dict if no request context)
    headers = get_http_headers()
    
    # Get authorization header
    auth_header = headers.get("authorization", "")
    is_bearer = auth_header.startswith("Bearer ")
    
    return {
        "user_agent": headers.get("user-agent", "Unknown"),
        "content_type": headers.get("content-type", "Unknown"),
        "has_auth": bool(auth_header),
        "auth_type": "Bearer" if is_bearer else "Other" if auth_header else "None",
        "headers_count": len(headers)
    }
```

By default, `get_http_headers()` excludes problematic headers like `host` and `content-length`. To include all headers, use `get_http_headers(include_all=True)`.

### Access Tokens

<VersionBadge version="2.11.0" />

When using authentication with your FastMCP server, you can access the authenticated user's access token information using the `get_access_token()` dependency function:

```python {2, 10} theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
from fastmcp import FastMCP
from fastmcp.server.dependencies import get_access_token, AccessToken

mcp = FastMCP(name="Auth Token Demo")

@mcp.tool
async def get_user_info() -> dict:
    """Get information about the authenticated user."""
    # Get the access token (None if not authenticated)
    token: AccessToken | None = get_access_token()
    
    if token is None:
        return {"authenticated": False}
    
    return {
        "authenticated": True,
        "client_id": token.client_id,
        "scopes": token.scopes,
        "expires_at": token.expires_at,
        "token_claims": token.claims,  # JWT claims or custom token data
    }
```

This is particularly useful when you need to:

1. **Access user identification** - Get the `client_id` or subject from token claims
2. **Check permissions** - Verify scopes or custom claims before performing operations
3. **Multi-tenant applications** - Extract tenant information from token claims
4. **Audit logging** - Track which user performed which actions

#### Working with Token Claims

The `claims` field contains all the data from the original token (JWT claims for JWT tokens, or custom data for other token types):

```python {2, 3, 9, 12, 15} theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
from fastmcp import FastMCP
from fastmcp.server.dependencies import get_access_token

mcp = FastMCP(name="Multi-tenant Demo")

@mcp.tool
async def get_tenant_data(resource_id: str) -> dict:
    """Get tenant-specific data using token claims."""
    token: AccessToken | None = get_access_token()
    
    # Extract tenant ID from token claims
    tenant_id = token.claims.get("tenant_id") if token else None
    
    # Extract user ID from standard JWT subject claim
    user_id = token.claims.get("sub") if token else None
    
    # Use tenant and user info to authorize and filter data
    if not tenant_id:
        raise ValueError("No tenant information in token")
    
    return {
        "resource_id": resource_id,
        "tenant_id": tenant_id,
        "user_id": user_id,
        "data": f"Tenant-specific data for {tenant_id}",
    }
```

# User Elicitation

> Request structured input from users during tool execution through the MCP context.

export const VersionBadge = ({version}) => {
  return <code className="version-badge-container">
            <p className="version-badge">
                <span className="version-badge-label">New in version:</span> 
                <code className="version-badge-version">{version}</code>
            </p>
        </code>;
};

<VersionBadge version="2.10.0" />

User elicitation allows MCP servers to request structured input from users during tool execution. Instead of requiring all inputs upfront, tools can interactively ask for missing parameters, clarification, or additional context as needed.

<Tip>
  Most of the examples in this document assume you have a FastMCP server instance named `mcp` and show how to use the `ctx.elicit` method to request user input from an `@mcp.tool`-decorated function.
</Tip>

## What is Elicitation?

Elicitation enables tools to pause execution and request specific information from users. This is particularly useful for:

* **Missing parameters**: Ask for required information not provided initially
* **Clarification requests**: Get user confirmation or choices for ambiguous scenarios
* **Progressive disclosure**: Collect complex information step-by-step
* **Dynamic workflows**: Adapt tool behavior based on user responses

For example, a file management tool might ask "Which directory should I create?" or a data analysis tool might request "What date range should I analyze?"

### Basic Usage

Use the `ctx.elicit()` method within any tool function to request user input:

```python {14-17} theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
from fastmcp import FastMCP, Context
from dataclasses import dataclass

mcp = FastMCP("Elicitation Server")

@dataclass
class UserInfo:
    name: str
    age: int

@mcp.tool
async def collect_user_info(ctx: Context) -> str:
    """Collect user information through interactive prompts."""
    result = await ctx.elicit(
        message="Please provide your information",
        response_type=UserInfo
    )
    
    if result.action == "accept":
        user = result.data
        return f"Hello {user.name}, you are {user.age} years old"
    elif result.action == "decline":
        return "Information not provided"
    else:  # cancel
        return "Operation cancelled"
```

## Method Signature

<Card icon="code" title="Context Elicitation Method">
  <ResponseField name="ctx.elicit" type="async method">
    <Expandable title="Parameters">
      <ResponseField name="message" type="str">
        The prompt message to display to the user
      </ResponseField>

      <ResponseField name="response_type" type="type" default="None">
        The Python type defining the expected response structure (dataclass, primitive type, etc.) Note that elicitation responses are subject to a restricted subset of JSON Schema types. See [Supported Response Types](#supported-response-types) for more details.
      </ResponseField>
    </Expandable>

    <Expandable title="Response">
      <ResponseField name="ElicitationResult" type="object">
        Result object containing the user's response

        <Expandable title="properties">
          <ResponseField name="action" type="Literal['accept', 'decline', 'cancel']">
            How the user responded to the request
          </ResponseField>

          <ResponseField name="data" type="response_type | None">
            The user's input data (only present when action is "accept")
          </ResponseField>
        </Expandable>
      </ResponseField>
    </Expandable>
  </ResponseField>
</Card>

## Elicitation Actions

The elicitation result contains an `action` field indicating how the user responded:

* **`accept`**: User provided valid input - data is available in the `data` field
* **`decline`**: User chose not to provide the requested information and the data field is `None`
* **`cancel`**: User cancelled the entire operation and the data field is `None`

```python {5, 7} theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
@mcp.tool
async def my_tool(ctx: Context) -> str:
    result = await ctx.elicit("Choose an action")

    if result.action == "accept":
        return "Accepted!"
    elif result.action == "decline":
        return "Declined!"
    else:
        return "Cancelled!"
```

FastMCP also provides typed result classes for pattern matching on the `action` field:

```python {1-5, 12, 14, 16} theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
from fastmcp.server.elicitation import (
    AcceptedElicitation, 
    DeclinedElicitation, 
    CancelledElicitation,
)

@mcp.tool
async def pattern_example(ctx: Context) -> str:
    result = await ctx.elicit("Enter your name:", response_type=str)
    
    match result:
        case AcceptedElicitation(data=name):
            return f"Hello {name}!"
        case DeclinedElicitation():
            return "No name provided"
        case CancelledElicitation():
            return "Operation cancelled"
```

## Response Types

The server must send a schema to the client indicating the type of data it expects in response to the elicitation request. If the request is `accept`-ed, the client must send a response that matches the schema.

The MCP spec only supports a limited subset of JSON Schema types for elicitation responses. Specifically, it only supports JSON  **objects** with **primitive** properties including `string`, `number` (or `integer`), `boolean` and `enum` fields.

FastMCP makes it easy to request a broader range of types, including scalars (e.g. `str`) or no response at all, by automatically wrapping them in MCP-compatible object schemas.

### Scalar Types

You can request simple scalar data types for basic input, such as a string, integer, or boolean.

When you request a scalar type, FastMCP automatically wraps it in an object schema for MCP spec compatibility. Clients will see a corresponding schema requesting a single "value" field of the requested type. Once clients respond, the provided object is "unwrapped" and the scalar value is returned to your tool function as the `data` field of the `ElicitationResult` object.

As a developer, this means you do not have to worry about creating or accessing a structured object when you only need a scalar value.

<CodeGroup>
  ```python {4} title="Request a string" theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
  @mcp.tool
  async def get_user_name(ctx: Context) -> str:
      """Get the user's name."""
      result = await ctx.elicit("What's your name?", response_type=str)
      
      if result.action == "accept":
          return f"Hello, {result.data}!"
      return "No name provided"
  ```

  ```python {4} title="Request an integer" theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
  @mcp.tool
  async def pick_a_number(ctx: Context) -> str:
      """Pick a number."""
      result = await ctx.elicit("Pick a number!", response_type=int)
      
      if result.action == "accept":
          return f"You picked {result.data}"
      return "No number provided"
  ```

  ```python {4} title="Request a boolean" theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
  @mcp.tool
  async def pick_a_boolean(ctx: Context) -> str:
      """Pick a boolean."""
      result = await ctx.elicit("True or false?", response_type=bool)
      
      if result.action == "accept":
          return f"You picked {result.data}"
      return "No boolean provided"
  ```
</CodeGroup>

### No Response

Sometimes, the goal of an elicitation is to simply get a user to approve or reject an action. In this case, you can pass `None` as the response type to indicate that no response is expected. In order to comply with the MCP spec, the client will see a schema requesting an empty object in response. In this case, the `data` field of the `ElicitationResult` object will be `None` when the user accepts the elicitation.

```python {4} title="No response" theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
@mcp.tool
async def approve_action(ctx: Context) -> str:
    """Approve an action."""
    result = await ctx.elicit("Approve this action?", response_type=None)

    if result.action == "accept":
        return do_action()
    else:
        raise ValueError("Action rejected")
```

### Constrained Options

Often you'll want to constrain the user's response to a specific set of values. You can do this by using a `Literal` type or a Python enum as the response type, or by passing a list of strings to the `response_type` parameter as a convenient shortcut.

<CodeGroup>
  ```python {6} title="Using a list of strings" theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
  @mcp.tool
  async def set_priority(ctx: Context) -> str:
      """Set task priority level."""
      result = await ctx.elicit(
          "What priority level?", 
          response_type=["low", "medium", "high"],
      )
      
      if result.action == "accept":
          return f"Priority set to: {result.data}"
  ```

  ```python {1, 8} title="Using a Literal type" theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
  from typing import Literal

  @mcp.tool
  async def set_priority(ctx: Context) -> str:
      """Set task priority level."""
      result = await ctx.elicit(
          "What priority level?", 
          response_type=Literal["low", "medium", "high"]
      )
      
      if result.action == "accept":
          return f"Priority set to: {result.data}"
      return "No priority set"
  ```

  ```python {1, 11} title="Using a Python enum" theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
  from enum import Enum

  class Priority(Enum):
      LOW = "low"
      MEDIUM = "medium"
      HIGH = "high"   

  @mcp.tool
  async def set_priority(ctx: Context) -> str:
      """Set task priority level."""
      result = await ctx.elicit("What priority level?", response_type=Priority)
      
      if result.action == "accept":
          return f"Priority set to: {result.data.value}"
      return "No priority set"
  ```
</CodeGroup>

### Structured Responses

You can request structured data with multiple fields by using a dataclass, typed dict, or Pydantic model as the response type. Note that the MCP spec only supports shallow objects with scalar (string, number, boolean) or enum properties.

```python {1, 16, 20} theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
from dataclasses import dataclass
from typing import Literal

@dataclass
class TaskDetails:
    title: str
    description: str
    priority: Literal["low", "medium", "high"]
    due_date: str

@mcp.tool
async def create_task(ctx: Context) -> str:
    """Create a new task with user-provided details."""
    result = await ctx.elicit(
        "Please provide task details",
        response_type=TaskDetails
    )
    
    if result.action == "accept":
        task = result.data
        return f"Created task: {task.title} (Priority: {task.priority})"
    return "Task creation cancelled"
```

## Multi-Turn Elicitation

Tools can make multiple elicitation calls to gather information progressively:

```python {6, 11, 16-19} theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
@mcp.tool
async def plan_meeting(ctx: Context) -> str:
    """Plan a meeting by gathering details step by step."""
    
    # Get meeting title
    title_result = await ctx.elicit("What's the meeting title?", response_type=str)
    if title_result.action != "accept":
        return "Meeting planning cancelled"
    
    # Get duration
    duration_result = await ctx.elicit("Duration in minutes?", response_type=int)
    if duration_result.action != "accept":
        return "Meeting planning cancelled"
    
    # Get priority
    priority_result = await ctx.elicit(
        "Is this urgent?", 
        response_type=Literal["yes", "no"]
    )
    if priority_result.action != "accept":
        return "Meeting planning cancelled"
    
    urgent = priority_result.data == "yes"
    return f"Meeting '{title_result.data}' planned for {duration_result.data} minutes (Urgent: {urgent})"
```

## Client Requirements

Elicitation requires the client to implement an elicitation handler. See [Client Elicitation](/clients/elicitation) for details on how clients can handle these requests.

If a client doesn't support elicitation, calls to `ctx.elicit()` will raise an error indicating that elicitation is not supported.

# Storage Backends

> Configure persistent and distributed storage for caching and OAuth state management

export const VersionBadge = ({version}) => {
  return <code className="version-badge-container">
            <p className="version-badge">
                <span className="version-badge-label">New in version:</span> 
                <code className="version-badge-version">{version}</code>
            </p>
        </code>;
};

<VersionBadge version="2.13.0" />

FastMCP uses pluggable storage backends for caching responses and managing OAuth state. By default, all storage is in-memory, which is perfect for development but doesn't persist across restarts. FastMCP includes support for multiple storage backends, and you can easily extend it with custom implementations.

<Tip>
  The storage layer is powered by **[py-key-value-aio](https://github.com/strawgate/py-key-value)**, an async key-value library maintained by a core FastMCP maintainer. This library provides a unified interface for multiple backends, making it easy to swap implementations based on your deployment needs.
</Tip>

## Available Backends

### In-Memory Storage

**Best for:** Development, testing, single-process deployments

In-memory storage is the default for all FastMCP storage needs. It's fast, requires no setup, and is perfect for getting started.

```python  theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
from key_value.aio.stores.memory import MemoryStore

# Used by default - no configuration needed
# But you can also be explicit:
cache_store = MemoryStore()
```

**Characteristics:**

* ✅ No setup required
* ✅ Very fast
* ❌ Data lost on restart
* ❌ Not suitable for multi-process deployments

### Disk Storage

**Best for:** Single-server production deployments, persistent caching

Disk storage persists data to the filesystem, allowing it to survive server restarts.

```python  theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
from key_value.aio.stores.disk import DiskStore
from fastmcp.server.middleware.caching import ResponseCachingMiddleware

# Persistent response cache
middleware = ResponseCachingMiddleware(
    cache_storage=DiskStore(directory="/var/cache/fastmcp")
)
```

Or with OAuth token storage:

```python  theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
from fastmcp.server.auth.providers.github import GitHubProvider
from key_value.aio.stores.disk import DiskStore

auth = GitHubProvider(
    client_id="your-id",
    client_secret="your-secret",
    base_url="https://your-server.com",
    client_storage=DiskStore(directory="/var/lib/fastmcp/oauth")
)
```

**Characteristics:**

* ✅ Data persists across restarts
* ✅ Good performance for moderate load
* ❌ Not suitable for distributed deployments
* ❌ Filesystem access required

### Redis

**Best for:** Distributed production deployments, shared caching across multiple servers

<Note>
  Redis support requires an optional dependency: `pip install 'py-key-value-aio[redis]'`
</Note>

Redis provides distributed caching and state management, ideal for production deployments with multiple server instances.

```python  theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
from key_value.aio.stores.redis import RedisStore
from fastmcp.server.middleware.caching import ResponseCachingMiddleware

# Distributed response cache
middleware = ResponseCachingMiddleware(
    cache_storage=RedisStore(host="redis.example.com", port=6379)
)
```

With authentication:

```python  theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
from key_value.aio.stores.redis import RedisStore

cache_store = RedisStore(
    host="redis.example.com",
    port=6379,
    password="your-redis-password"
)
```

For OAuth token storage:

```python  theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
import os
from fastmcp.server.auth.providers.github import GitHubProvider
from key_value.aio.stores.redis import RedisStore

auth = GitHubProvider(
    client_id=os.environ["GITHUB_CLIENT_ID"],
    client_secret=os.environ["GITHUB_CLIENT_SECRET"],
    base_url="https://your-server.com",
    jwt_signing_key=os.environ["JWT_SIGNING_KEY"],
    client_storage=RedisStore(host="redis.example.com", port=6379)
)
```

**Characteristics:**

* ✅ Distributed and highly available
* ✅ Fast in-memory performance
* ✅ Works across multiple server instances
* ✅ Built-in TTL support
* ❌ Requires Redis infrastructure
* ❌ Network latency vs local storage

### Other Backends from py-key-value-aio

The py-key-value-aio library includes additional implementations for various storage systems:

* **DynamoDB** - AWS distributed database
* **MongoDB** - NoSQL document store
* **Elasticsearch** - Distributed search and analytics
* **Memcached** - Distributed memory caching
* **RocksDB** - Embedded high-performance key-value store
* **Valkey** - Redis-compatible server

For configuration details on these backends, consult the [py-key-value-aio documentation](https://github.com/strawgate/py-key-value).

<Warning>
  Before using these backends in production, review the [py-key-value documentation](https://github.com/strawgate/py-key-value) to understand the maturity level and limitations of your chosen backend. Some backends may be in preview or have specific constraints that make them unsuitable for production use.
</Warning>

## Use Cases in FastMCP

### Server-Side OAuth Token Storage

The [OAuth Proxy](/servers/auth/oauth-proxy) and OAuth auth providers use storage for persisting OAuth client registrations and upstream tokens. **By default, storage is automatically encrypted using `FernetEncryptionWrapper`.** When providing custom storage, wrap it in `FernetEncryptionWrapper` to encrypt sensitive OAuth tokens at rest.

**Development (default behavior):**

By default, FastMCP automatically manages keys and storage based on your platform:

* **Mac/Windows**: Keys are auto-managed via system keyring, storage defaults to disk. Suitable **only** for development and local testing.
* **Linux**: Keys are ephemeral, storage defaults to memory.

No configuration needed:

```python  theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
from fastmcp.server.auth.providers.github import GitHubProvider

auth = GitHubProvider(
    client_id="your-id",
    client_secret="your-secret",
    base_url="https://your-server.com"
)
```

**Production:**

For production deployments, configure explicit keys and persistent network-accessible storage with encryption:

```python  theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
import os
from fastmcp.server.auth.providers.github import GitHubProvider
from key_value.aio.stores.redis import RedisStore
from key_value.aio.wrappers.encryption import FernetEncryptionWrapper
from cryptography.fernet import Fernet

auth = GitHubProvider(
    client_id=os.environ["GITHUB_CLIENT_ID"],
    client_secret=os.environ["GITHUB_CLIENT_SECRET"],
    base_url="https://your-server.com",
    # Explicit JWT signing key (required for production)
    jwt_signing_key=os.environ["JWT_SIGNING_KEY"],
    # Encrypted persistent storage (required for production)
    client_storage=FernetEncryptionWrapper(
        key_value=RedisStore(host="redis.example.com", port=6379),
        fernet=Fernet(os.environ["STORAGE_ENCRYPTION_KEY"])
    )
)
```

Both parameters are required for production. **Wrap your storage in `FernetEncryptionWrapper` to encrypt sensitive OAuth tokens at rest** - without it, tokens are stored in plaintext. See [OAuth Token Security](/deployment/http#oauth-token-security) and [Key and Storage Management](/servers/auth/oauth-proxy#key-and-storage-management) for complete setup details.

### Response Caching Middleware

The [Response Caching Middleware](/servers/middleware#caching-middleware) caches tool calls, resource reads, and prompt requests. Storage configuration is passed via the `cache_storage` parameter:

```python  theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
from fastmcp import FastMCP
from fastmcp.server.middleware.caching import ResponseCachingMiddleware
from key_value.aio.stores.disk import DiskStore

mcp = FastMCP("My Server")

# Cache to disk instead of memory
mcp.add_middleware(ResponseCachingMiddleware(
    cache_storage=DiskStore(directory="cache")
))
```

For multi-server deployments sharing a Redis instance:

```python  theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
from fastmcp.server.middleware.caching import ResponseCachingMiddleware
from key_value.aio.stores.redis import RedisStore
from key_value.aio.wrappers.prefix_collections import PrefixCollectionsWrapper

base_store = RedisStore(host="redis.example.com")
namespaced_store = PrefixCollectionsWrapper(
    key_value=base_store,
    prefix="my-server"
)

middleware = ResponseCachingMiddleware(cache_storage=namespaced_store)
```

### Client-Side OAuth Token Storage

The [FastMCP Client](/clients/client) uses storage for persisting OAuth tokens locally. By default, tokens are stored in memory:

```python  theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
from fastmcp.client.auth import OAuthClientProvider
from key_value.aio.stores.disk import DiskStore

# Store tokens on disk for persistence across restarts
token_storage = DiskStore(directory="~/.local/share/fastmcp/tokens")

oauth_provider = OAuthClientProvider(
    mcp_url="https://your-mcp-server.com/mcp/sse",
    token_storage=token_storage
)
```

This allows clients to reconnect without re-authenticating after restarts.

## Choosing a Backend

| Backend  | Development | Single Server | Multi-Server | Cloud Native |
| -------- | ----------- | ------------- | ------------ | ------------ |
| Memory   | ✅ Best      | ⚠️ Limited    | ❌            | ❌            |
| Disk     | ✅ Good      | ✅ Recommended | ❌            | ⚠️           |
| Redis    | ⚠️ Overkill | ✅ Good        | ✅ Best       | ✅ Best       |
| DynamoDB | ❌           | ⚠️            | ✅            | ✅ Best (AWS) |
| MongoDB  | ❌           | ⚠️            | ✅            | ✅ Good       |

**Decision tree:**

1. **Just starting?** Use **Memory** (default) - no configuration needed
2. **Single server, needs persistence?** Use **Disk**
3. **Multiple servers or cloud deployment?** Use **Redis** or **DynamoDB**
4. **Existing infrastructure?** Look for a matching py-key-value-aio backend

## More Resources

* [py-key-value-aio GitHub](https://github.com/strawgate/py-key-value) - Full library documentation
* [Response Caching Middleware](/servers/middleware#caching-middleware) - Using storage for caching
* [OAuth Token Security](/deployment/http#oauth-token-security) - Production OAuth configuration
* [HTTP Deployment](/deployment/http) - Complete deployment guide

# Running Your Server

> Learn how to run your FastMCP server locally for development and testing

FastMCP servers can be run in different ways depending on your needs. This guide focuses on running servers locally for development and testing. For production deployment to a URL, see the [HTTP Deployment](/deployment/http) guide.

## The `run()` Method

Every FastMCP server needs to be started to accept connections. The simplest way to run a server is by calling the `run()` method on your FastMCP instance. This method starts the server and blocks until it's stopped, handling all the connection management for you.

<Tip>
  For maximum compatibility, it's best practice to place the `run()` call within an `if __name__ == "__main__":` block. This ensures the server starts only when the script is executed directly, not when imported as a module.
</Tip>

```python {9-10} my_server.py theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
from fastmcp import FastMCP

mcp = FastMCP(name="MyServer")

@mcp.tool
def hello(name: str) -> str:
    return f"Hello, {name}!"

if __name__ == "__main__":
    mcp.run()
```

You can now run this MCP server by executing `python my_server.py`.

## Transport Protocols

MCP servers communicate with clients through different transport protocols. Think of transports as the "language" your server speaks to communicate with clients. FastMCP supports three main transport protocols, each designed for specific use cases and deployment scenarios.

The choice of transport determines how clients connect to your server, what network capabilities are available, and how many clients can connect simultaneously. Understanding these transports helps you choose the right approach for your application.

### STDIO Transport (Default)

STDIO (Standard Input/Output) is the default transport for FastMCP servers. When you call `run()` without arguments, your server uses STDIO transport. This transport communicates through standard input and output streams, making it perfect for command-line tools and desktop applications like Claude Desktop.

With STDIO transport, the client spawns a new server process for each session and manages its lifecycle. The server reads MCP messages from stdin and writes responses to stdout. This is why STDIO servers don't stay running - they're started on-demand by the client.

```python  theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
from fastmcp import FastMCP

mcp = FastMCP("MyServer")

@mcp.tool
def hello(name: str) -> str:
    return f"Hello, {name}!"

if __name__ == "__main__":
    mcp.run()  # Uses STDIO transport by default
```

STDIO is ideal for:

* Local development and testing
* Claude Desktop integration
* Command-line tools
* Single-user applications

### HTTP Transport (Streamable)

HTTP transport turns your MCP server into a web service accessible via a URL. This transport uses the Streamable HTTP protocol, which allows clients to connect over the network. Unlike STDIO where each client gets its own process, an HTTP server can handle multiple clients simultaneously.

The Streamable HTTP protocol provides full bidirectional communication between client and server, supporting all MCP operations including streaming responses. This makes it the recommended choice for network-based deployments.

To use HTTP transport, specify it in the `run()` method along with networking options:

```python  theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
from fastmcp import FastMCP

mcp = FastMCP("MyServer")

@mcp.tool
def hello(name: str) -> str:
    return f"Hello, {name}!"

if __name__ == "__main__":
    # Start an HTTP server on port 8000
    mcp.run(transport="http", host="127.0.0.1", port=8000)
```

Your server is now accessible at `http://localhost:8000/mcp`. This URL is the MCP endpoint that clients will connect to. HTTP transport enables:

* Network accessibility
* Multiple concurrent clients
* Integration with web infrastructure
* Remote deployment capabilities

For production HTTP deployment with authentication and advanced configuration, see the [HTTP Deployment](/deployment/http) guide.

### SSE Transport (Legacy)

Server-Sent Events (SSE) transport was the original HTTP-based transport for MCP. While still supported for backward compatibility, it has limitations compared to the newer Streamable HTTP transport. SSE only supports server-to-client streaming, making it less efficient for bidirectional communication.

```python  theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
if __name__ == "__main__":
    # SSE transport - use HTTP instead for new projects
    mcp.run(transport="sse", host="127.0.0.1", port=8000)
```

We recommend using HTTP transport instead of SSE for all new projects. SSE remains available only for compatibility with older clients that haven't upgraded to Streamable HTTP.

### Choosing the Right Transport

Each transport serves different needs. STDIO is perfect when you need simple, local execution - it's what Claude Desktop and most command-line tools expect. HTTP transport is essential when you need network access, want to serve multiple clients, or plan to deploy your server remotely. SSE exists only for backward compatibility and shouldn't be used in new projects.

Consider your deployment scenario: Are you building a tool for local use? STDIO is your best choice. Need a centralized service that multiple clients can access? HTTP transport is the way to go.

## The FastMCP CLI

FastMCP provides a powerful command-line interface for running servers without modifying the source code. The CLI can automatically find and run your server with different transports, manage dependencies, and handle development workflows:

```bash  theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
fastmcp run server.py
```

The CLI automatically finds a FastMCP instance in your file (named `mcp`, `server`, or `app`) and runs it with the specified options. This is particularly useful for testing different transports or configurations without changing your code.

### Dependency Management

The CLI integrates with `uv` to manage Python environments and dependencies:

```bash  theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
# Run with a specific Python version
fastmcp run server.py --python 3.11

# Run with additional packages
fastmcp run server.py --with pandas --with numpy

# Run with dependencies from a requirements file
fastmcp run server.py --with-requirements requirements.txt

# Combine multiple options
fastmcp run server.py --python 3.10 --with httpx --transport http

# Run within a specific project directory
fastmcp run server.py --project /path/to/project
```

<Note>
  When using `--python`, `--with`, `--project`, or `--with-requirements`, the server runs via `uv run` subprocess instead of using your local environment.
</Note>

### Passing Arguments to Servers

When servers accept command line arguments (using argparse, click, or other libraries), you can pass them after `--`:

```bash  theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
fastmcp run config_server.py -- --config config.json
fastmcp run database_server.py -- --database-path /tmp/db.sqlite --debug
```

This is useful for servers that need configuration files, database paths, API keys, or other runtime options.

For more CLI features including development mode with the MCP Inspector, see the [CLI documentation](/patterns/cli).

### Async Usage

FastMCP servers are built on async Python, but the framework provides both synchronous and asynchronous APIs to fit your application's needs. The `run()` method we've been using is actually a synchronous wrapper around the async server implementation.

For applications that are already running in an async context, FastMCP provides the `run_async()` method:

```python {10-12} theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
from fastmcp import FastMCP
import asyncio

mcp = FastMCP(name="MyServer")

@mcp.tool
def hello(name: str) -> str:
    return f"Hello, {name}!"

async def main():
    # Use run_async() in async contexts
    await mcp.run_async(transport="http", port=8000)

if __name__ == "__main__":
    asyncio.run(main())
```

<Warning>
  The `run()` method cannot be called from inside an async function because it creates its own async event loop internally. If you attempt to call `run()` from inside an async function, you'll get an error about the event loop already running.

  Always use `run_async()` inside async functions and `run()` in synchronous contexts.
</Warning>

Both `run()` and `run_async()` accept the same transport arguments, so all the examples above apply to both methods.

## Custom Routes

When using HTTP transport, you might want to add custom web endpoints alongside your MCP server. This is useful for health checks, status pages, or simple APIs. FastMCP lets you add custom routes using the `@custom_route` decorator:

```python  theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import PlainTextResponse

mcp = FastMCP("MyServer")

@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> PlainTextResponse:
    return PlainTextResponse("OK")

@mcp.tool
def process(data: str) -> str:
    return f"Processed: {data}"

if __name__ == "__main__":
    mcp.run(transport="http")  # Health check at http://localhost:8000/health
```

Custom routes are served by the same web server as your MCP endpoint. They're available at the root of your domain while the MCP endpoint is at `/mcp/`. For more complex web applications, consider [mounting your MCP server into a FastAPI or Starlette app](/deployment/http#integration-with-web-frameworks).

## Alternative Initialization Patterns

The `if __name__ == "__main__"` pattern works well for standalone scripts, but some deployment scenarios require different approaches. FastMCP handles these cases automatically.

### CLI-Only Servers

When using the FastMCP CLI, you don't need the `if __name__` block at all. The CLI will find your FastMCP instance and run it:

```python  theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
# server.py
from fastmcp import FastMCP

mcp = FastMCP("MyServer")  # CLI looks for 'mcp', 'server', or 'app'

@mcp.tool
def process(data: str) -> str:
    return f"Processed: {data}"

# No if __name__ block needed - CLI will find and run 'mcp'
```

### ASGI Applications

For ASGI deployment (running with Uvicorn or similar), you'll want to create an ASGI application object. This approach is common in production deployments where you need more control over the server configuration:

```python  theme={"theme":{"light":"snazzy-light","dark":"dark-plus"}}
# app.py
from fastmcp import FastMCP

def create_app():
    mcp = FastMCP("MyServer")
    
    @mcp.tool
    def process(data: str) -> str:
        return f"Processed: {data}"
    
    return mcp.http_app()

app = create_app()  # Uvicorn will use this
```

See the [HTTP Deployment](/deployment/http) guide for more ASGI deployment patterns.


