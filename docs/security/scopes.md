# Scope Policy

OAuth scopes are exact, case-sensitive opaque identifiers.

```text
airline.search != airline:search
Parking.Read != parking.read
```

Runtime behavior:

- preserves requested scope values;
- compares method-required scopes exactly;
- validates skill scopes against the selected resource's `scopes_supported`;
- does not create a global Provider-scope allowlist;
- does not infer scopes from names or categories;
- does not treat client registration metadata as an authorization grant by itself.

Business policy may further narrow scopes through injected authorization services.
