# Integration-heavy change

Request: Add a versioned field produced by one service, persisted in shared storage, and consumed by two clients.

Clarification risks: identify downstream consumers, schema propagation, authorization, lifecycle, compatibility, and failure modes.

Planning needs: name dependencies between producer, storage, migrations, and consumers; slice rollout so compatibility and verification are observable at each boundary.

