"""Buffer Service (claude.md §8.9).

The single aggregation point that lets Part I compute portfolio-level truths
from micro-level events without Pillar 3 ever computing anything itself.
Holds four separately-balanced accounts; exposes balances to Part I; declares
(but does NOT arm) Stage-2 CASS-consumption sockets.

Part I reads balances via `balances()`/`sub_account()`. This service is the
owner of the mutable ledger state (claude.md §6: "Part II owns all mutable
ledger state; Part I read-mostly against it").
"""

from __future__ import annotations

from ..domain.buffer_account import BufferAccount, SubAccountId, SubAccount, CassComponent
from ..domain.events import IntraP4Event, IntraP4EventType


class BufferService:
    """Owns the buffer ledger and exposes balances/sockets to Part I."""

    def __init__(self, account: BufferAccount | None = None, event_sink=None):
        self.account = account or BufferAccount()
        self._event_sink = event_sink or (lambda ev: None)

    def _emit(self, ev):
        self._event_sink(ev)

    def sub_account(self, sid: SubAccountId) -> SubAccount:
        return self.account.sub_account(sid)

    def balances(self) -> dict[SubAccountId, float]:
        return self.account.balances()

    def cass_socket_for(self, sid: SubAccountId) -> CassComponent:
        """Dormant socket declaration (register II-d); not armed in Stage 1.

        The socket merely declares which CASS component will consume this
        sub-account's balance at Stage 2. No CASS methodology lives here.
        """
        return self.account.sub_account(sid).cass_socket

    def declare_socket_arm(self, sid: SubAccountId, armed: bool):
        """Reserved: Stage-2 readiness seam (claude.md §5.4).

        Arming is a Part III concern and stays dormant; this merely toggles the
        reservation flag and must not activate any logic.
        """
        self.account.sub_account(sid).stage2_socket_active = armed

    def announce_balance_change(self):
        self._emit(IntraP4Event(IntraP4EventType.SUB_ACCOUNT_BALANCE_CHANGED, self.balances()))
