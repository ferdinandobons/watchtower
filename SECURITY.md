# Security policy

Watchtower processes local development metadata and bounded error output. Privacy, hook-installation, database, or action flaws may expose sensitive project information.

Do not report suspected vulnerabilities in a public issue. Contact the repository owner privately through the email associated with the GitHub profile, and include:

- affected version or commit;
- operating system;
- reproduction steps;
- expected and observed behavior;
- the smallest safe proof of concept;
- whether secrets, files, commands, hook configuration, or checkpoints were exposed.

Remove real credentials, proprietary source, and personal data from the report.

## Current trust boundaries

- The HTTP daemon binds to loopback by default.
- Hook input is untrusted and size limited.
- SQLite contains local project metadata and may contain bounded error excerpts.
- Command capture is disabled by default.
- Desktop notifications are best effort.
- Structured feedback remains local.
- Hook configuration is parsed as untrusted JSON.
- The installer refuses symlinked configuration files and writes atomically after backup.
- Checkpoint creation requires explicit confirmation.
- Checkpoints may contain bounded local error excerpts and changed-file names.
- Checkpoint reads verify configured-root containment and SHA-256 integrity.
- Suggested actions other than context checkpoint creation are labels only in version `0.2.0`.

Binding the daemon to a non-loopback address is not recommended without an authenticated reverse proxy. Authentication is not implemented in the current release.

## Out of scope for the current action boundary

Version `0.2.0` does not provide generic shell execution, autonomous source modification, network-enabled action adapters, automatic Git commits, or unattended agent launches. A contribution adding those capabilities requires a threat model, capability checks, explicit preview and approval, timeout handling, redacted audit records, and security-focused tests.
