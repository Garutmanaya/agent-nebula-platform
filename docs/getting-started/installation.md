# Installation

## Local multi-repository workspace

Until `agent-nebula-sdk` is published, keep the SDK and runtime as sibling repositories:

```text
workspace/
├── agent-nebula-sdk/
└── agent-runtime/
```

`agent-runtime/pyproject.toml` uses a local editable `uv` source for the SDK.

```bash
cd agent-runtime
uv sync --extra test
uv run pytest -q
```

For standalone server support:

```bash
uv sync --extra standalone --extra test
```

## Python version

The current package targets Python 3.12.

## Public-package future

After `agent-nebula-sdk` is published, the local source mapping can be replaced by the declared compatible SDK version range. See [Roadmap](../reference/roadmap.md).
