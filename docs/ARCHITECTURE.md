# Architecture

## Current local controlled release

Browser UI (HTML/CSS/JavaScript)
        |
        | localhost HTTP / JSON
        v
Python standard-library application (`app.py`)
        |
        +-- deterministic governance routing and validation
        +-- no external AI API
        +-- security headers / request limits / local-origin checks
        +-- rotating system log + privacy-minimised audit log
        |
        v
Excel OOXML data layer (`xlsx_store.py`)
        |
        +-- AI Register
        +-- assessment evidence
        +-- decision log
        +-- rolling pre-write backups

Controlled configuration lives in `config/`. Governance source documents live in `documents/`. System documentation lives in `docs/`.

## Why no generative-AI API is used in the decision engine
A governance route should be reproducible and auditable. The platform therefore uses explicit deterministic rules derived from the controlled BUV source drafts. Generative AI may assist future evidence research or summarisation, but it should not silently determine approval, legal status or delegated institutional authority.

## Future central production architecture
For simultaneous multi-user use, the local Excel architecture should be replaced by a BUV-managed web service with SSO, role-based access, central relational database, server-side audit trails, concurrency/transaction controls, managed secrets, monitoring, backup/restore testing and environment separation (development/test/production).
