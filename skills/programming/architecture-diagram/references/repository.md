# Repository extraction

Read project instructions, manifests, entry points, routing, service wiring, persistence adapters and deployment configuration. Follow representative execution paths across boundaries before naming components. Use targeted searches rather than loading the entire repository.

Group by responsibility and runtime ownership; directories are supporting evidence, not automatic architecture boundaries. Include external services and storage where the inspected code proves their use. Distinguish imports, calls, events and data access through edge labels.

For each claim, retain repository-relative path and symbol or line range plus a short explanation of what it proves. Record revision and dirty-working-tree status. Treat generated/vendor code as external unless the user's question requires examining it. Record inaccessible submodules and unresolved dynamic wiring as gaps.
