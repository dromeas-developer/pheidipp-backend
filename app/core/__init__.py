"""Cross-cutting platform primitives.

Currently houses the security package (password hashing, token issuance
and verification). Future cross-cutting modules — rate limiting, audit
log helpers, etc. — belong here only when they are platform concerns, not
domain concerns.
"""
