# Secrets

Agent Runtime supports a secret-provider boundary. The built-in file provider:

- resolves relative references beneath an explicit secret root;
- rejects path escape;
- rejects missing and empty files;
- returns secret values without adding them to logs or configuration errors.

Recommended layout:

```text
$AGENT_RUNTIME_HOME/
├── config/
├── certs/
├── trust/
├── secrets/
└── runtime/
```

Do not place API keys, private keys, tokens, or assertions directly in INI files. Cloud secret-manager adapters are not included in the current release; hosts can implement the `SecretProvider` port.
