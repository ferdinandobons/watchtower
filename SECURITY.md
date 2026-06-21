# Security policy

Watchtower processes local development metadata and bounded error output. Privacy or command-execution flaws may still expose sensitive project information.

Do not report suspected vulnerabilities in a public issue. Contact the repository owner privately through the email associated with the GitHub profile, and include:

- affected version or commit;
- operating system;
- reproduction steps;
- expected and observed behavior;
- the smallest safe proof of concept;
- whether secrets, files, or commands were exposed.

Please remove real credentials, proprietary source, and personal data from the report.

## Current trust boundaries

- The HTTP daemon binds to loopback by default.
- Hook input is untrusted and size limited.
- SQLite contains local project metadata and may contain bounded error excerpts.
- Command capture is disabled by default.
- Desktop notifications are best effort.
- Suggested actions are labels only in version 0.1.0.

Binding the daemon to a non-loopback address is not recommended without an authenticated reverse proxy. Authentication is not implemented in the initial release.
