# Migration Overview

The intended migration path is incremental:

1. retain existing business handlers;
2. inject existing configuration, logging, HTTP, and persistence through runtime ports;
3. adopt onboarding and lifecycle integration;
4. adopt SDK-backed OAuth caller or protected-resource behavior;
5. register existing operations as skills;
6. attach REST/A2A/A2UI routes only where needed;
7. migrate process ownership to standalone mode only when desired.

Do not rewrite an established agent merely to adopt Agent Runtime. The runtime exists to reduce migration cost.
