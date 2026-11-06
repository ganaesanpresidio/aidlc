"""submit unit: claims, expense lines, receipts, submit, withdraw, retention.

Design: aidlc-docs/design/submit/lld.md. Business logic runs on small interfaces (table, object store,
scanner, policy client, event bus), so the same code runs against in-memory fakes or real AWS.
"""
