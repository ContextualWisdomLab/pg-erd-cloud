"""Release-evidence assembly for the first commercial release (issue #953).

This package holds the pure, side-effect-free assemblers that turn facts a
caller has already gathered (from git, CI, the lockfiles, the PR queue) into
the immutable release-evidence artifacts #953 requires. Nothing here runs
git, reaches the network, or touches the filesystem — the caller supplies
every fact, and each function only validates and normalizes it into a
stable, JSON-serializable shape.
"""
