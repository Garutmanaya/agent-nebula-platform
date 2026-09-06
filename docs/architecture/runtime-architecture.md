
## Lifecycle Logging

The Python logging event sink renders deterministic event attributes in the message. Plugin lifecycle entries therefore include `plugin=<runtime-plugin-name>` and `phase=<phase>` without requiring a custom formatter to expose `LogRecord.extra` fields.
