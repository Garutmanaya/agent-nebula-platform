# Discovery and Lifecycle

## Discovery

The discovery integration exposes transport-neutral access to Agent Nebula discovery through the injected connector. It does not implement ranking or registry persistence locally.

## Lifecycle

The current lifecycle integration provides explicit workload deregistration. Agent Nebula remains authoritative for state transitions and linked-resource handling.

Future synchronization jobs can be attached through the scheduler, but automatic heartbeat and full lifecycle polling are not built-in business jobs in the current release.
