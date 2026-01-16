---
sidebar_position: 6
---

# Secrets
Secrets is a configuration management module within an Orbit designed for the secure storage, administration, and rotation of sensitive information, such as API keys, database access tokens, or access tokens.
Technically, a Secret represents a Key-Value pair that is injected into a deployment’s execution environment as an environment variable, allowing applications to consume sensitive data securely without hardcoding it into source code or configuration files.

## Operating Principles
1. **Data Abstraction**  
The module implements the principle of separating knowledge from usage. Value: The actual secret string (e.g., sk-proj-...) is visible and editable exclusively by Organization Administrators. Reference: Other Orbit users see only the public name of the secret (e.g., OPENAI_API_KEY). They can attach this secret to their deployments or notebooks without having physical access to the key itself. This prevents data leaks caused by unauthorized copying.
2. **Centralized Management**  
A Secret is a "live" object referenced by dependent services. The key is stored as a single instance at the Orbit level. When a secret's value changes (e.g., during key rotation), the update is automatically applied to all deployments and environments where the secret is utilized. There is no need to manually reconfigure each individual service.
3. **Scope**  
Secrets are strictly scoped to an Orbit. This ensures context isolation: secrets created for one project are technically inaccessible in other workspaces, even within the same Organization.