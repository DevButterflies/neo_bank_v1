"""Bilan comptable (Actif/Passif) — additive, read-only view over the shared KvStore.

The package is deliberately self-contained: it never imports a Pillar engine,
never writes on a ``GET``, and is registered on the orchestrator root app by a
single ``app.include_router(bilan_router)`` line in
:mod:`bank.orchestrator.main`. No existing route, lifespan, mount, middleware
or test is modified by it.

Layout
------
:mod:`~bank.orchestrator.bilan.config`    config model + KV key + defaults
:mod:`~bank.orchestrator.bilan.store`     read-only (``mode=ro``) snapshot access
:mod:`~bank.orchestrator.bilan.compute`   pure Actif/Passif computation
:mod:`~bank.orchestrator.bilan.router`    ``GET /bilan``, ``GET|PUT /bilan/config``
"""
