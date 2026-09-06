# Server-ready lifecycle

Agent Nebula onboarding may fetch the agent's hosted Agent Card and Protected Resource Metadata. The agent HTTPS listener must therefore accept connections before onboarding begins.

Agent Runtime separates startup into two phases:

1. `PRE_SERVER` initializes local configuration, skill registries, documents, health, and FastAPI routes.
2. The host starts its HTTPS listener and confirms that the listener is accepting traffic.
3. `POST_SERVER` initializes Agent Nebula onboarding and other callback-dependent integrations.

Standalone agents use `UvicornRuntimeServer`, which waits for Uvicorn's listener-ready signal before calling `initialize_post_server()`. Embedded hosts call `initialize_pre_server()` during their application startup and must call `initialize_post_server()` after their server manager confirms listener readiness.

The compatibility method `initialize()` initializes both phases sequentially and remains suitable for tests and runtimes without callback-dependent plugins.
