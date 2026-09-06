# OAuth Client Registration

This module composes OAuth 2.0 Dynamic Client Registration for Agent Runtime callers.

## Standards

RFC 7591 defines Dynamic Client Registration. The Runtime delegates the wire protocol and
registration response validation to `agent-nebula-sdk.oauth.rfc7591`.

## AGENT NEBULA ADDITIONAL FUNCTIONALITY

Enterprise Agent Nebula clients first enroll with the Registry. When the onboarding result contains
a `client_enrollment_id`, Runtime adds the `nebula_enrollment_id` metadata extension and sends the
Provider onboarding API key in `X-API-Key`. The standalone Agent Nebula Authorization Server uses
that information to verify Registry ownership and the registered public-key thumbprint.

Standards-only OAuth clients remain valid: when no Agent Nebula enrollment exists, Runtime performs
ordinary RFC 7591 registration without Nebula-specific headers or extensions.
