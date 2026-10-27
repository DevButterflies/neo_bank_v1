"""Pillar 4 - Prudential Capital, Liquidity and Loss-Absorption Layer.

The prudential nervous system of the neo-bank operating system. Pillar 4 owns
whether the whole balance sheet stays safe while Pillar 2 decides who gets a
loan and Pillar 3 executes it.

Built against `claude.md` (Pillar 4 - Complete Technical and Business
Conception). Primary authority for business meaning is that document; this
package conforms to its Part I / Part II split, its component boundaries, its
state machines, its event model, and its governance conventions
(Conventional Mode / Adaptive Mode gate, Four-Event Discipline,
Two-Guarantee-Layer Rule, no per-loan Pillar 3 interface, PENDING
do-not-resolve-in-code discipline).

This package is a self-contained module: no microservices. Part I owns
decisions; Part II owns the accounts. `adaptive_dormant/` is built but gated
behind a governance-controlled mode switch and is inactive by default
("deactivation is not deletion").
"""

from .mode_gate.mode_gate import OperatingMode, ModeGate  # noqa: F401
from .integration.pillar4 import Pillar4  # noqa: F401
from .observability.derivation_register import (  # noqa: F401
    build_default_derivation_register,
    DerivationRegister,
    AuditLedger,
)

__all__ = [
    "OperatingMode",
    "ModeGate",
    "Pillar4",
    "build_default_derivation_register",
    "DerivationRegister",
    "AuditLedger",
]
