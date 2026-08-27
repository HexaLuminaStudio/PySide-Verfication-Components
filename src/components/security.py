"""Local challenge lifecycle controls.

This module improves retry behaviour and user feedback, but it is deliberately
not presented as a security boundary. Attackers control desktop clients; the
trusted service must independently enforce expiry, replay protection and rate
limits.
"""

from __future__ import annotations

import secrets
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QObject, QTimer, Signal


@dataclass(frozen=True, slots=True)
class AttemptPolicy:
    """Client-side retry and challenge-lifetime policy."""

    max_failures: int = 5
    window_seconds: float = 60.0
    cooldown_seconds: float = 30.0
    challenge_ttl_seconds: float = 120.0


class AttemptGuard:
    """Track challenge expiry and retry cooldowns using a monotonic clock."""

    def __init__(
        self,
        policy: AttemptPolicy | None = None,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.policy = policy or AttemptPolicy()
        self._clock = clock
        self._failures: deque[float] = deque()
        self._blocked_until = 0.0
        self._expires_at = 0.0
        self.start_challenge()

    def start_challenge(self, ttl_seconds: float | None = None) -> None:
        ttl = (
            self.policy.challenge_ttl_seconds
            if ttl_seconds is None
            else max(0.0, float(ttl_seconds))
        )
        self._expires_at = self._clock() + ttl

    def _prune(self, now: float) -> None:
        cutoff = now - max(0.0, self.policy.window_seconds)
        while self._failures and self._failures[0] < cutoff:
            self._failures.popleft()

    def can_attempt(self) -> tuple[bool, str, float]:
        now = self._clock()
        self._prune(now)
        if now < self._blocked_until:
            remaining = self._blocked_until - now
            return False, f"操作过于频繁，请在 {max(1, round(remaining))} 秒后重试", remaining
        if now >= self._expires_at:
            return False, "验证已过期，请刷新后重试", 0.0
        return True, "", 0.0

    def record_failure(self) -> tuple[bool, float]:
        now = self._clock()
        self._prune(now)
        self._failures.append(now)
        if len(self._failures) >= max(1, self.policy.max_failures):
            self._blocked_until = max(
                self._blocked_until,
                now + max(0.0, self.policy.cooldown_seconds),
            )
            return True, self._blocked_until - now
        return False, 0.0

    def record_success(self) -> None:
        self._failures.clear()
        self._blocked_until = 0.0

    @property
    def expires_at(self) -> float:
        return self._expires_at


class ChallengeLifecycleController(QObject):
    """Own the reusable lifecycle of one local or server-backed challenge.

    Widgets remain responsible for presenting pending, success and failure
    states.  This controller owns the state that must behave identically for
    every challenge type: expiry, cooldowns, opaque server tokens, outstanding
    attempt IDs and server timeouts.
    """

    serverTimedOut = Signal()

    def __init__(
        self,
        *,
        require_server_verification: bool = False,
        challenge_token: str | None = None,
        challenge_ttl_seconds: float | None = None,
        attempt_policy: AttemptPolicy | None = None,
        server_timeout_seconds: float = 10.0,
        clock: Callable[[], float] = time.monotonic,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.require_server_verification = bool(require_server_verification)
        self._challenge_token = str(challenge_token) if challenge_token else None
        self._pending_attempt_id: str | None = None
        self._guard = AttemptGuard(attempt_policy, clock=clock)
        if challenge_ttl_seconds is not None:
            self._guard.start_challenge(challenge_ttl_seconds)

        self._server_timer = QTimer(self)
        self._server_timer.setSingleShot(True)
        self._server_timer.setInterval(
            max(1000, round(float(server_timeout_seconds) * 1000))
        )
        self._server_timer.timeout.connect(self._handle_server_timeout)

    @property
    def guard(self) -> AttemptGuard:
        return self._guard

    @property
    def pending_attempt_id(self) -> str | None:
        return self._pending_attempt_id

    @property
    def has_challenge_token(self) -> bool:
        return self._challenge_token is not None

    def can_attempt(self) -> tuple[bool, str, float]:
        return self._guard.can_attempt()

    def start_challenge(self, ttl_seconds: float | None = None) -> None:
        self._guard.start_challenge(ttl_seconds)

    def record_failure(self) -> tuple[bool, float]:
        return self._guard.record_failure()

    def record_success(self) -> None:
        self._guard.record_success()

    def set_challenge_token(
        self, token: str, *, expires_in: float | None = None
    ) -> None:
        self._server_timer.stop()
        self._pending_attempt_id = None
        self._challenge_token = str(token) if token else None
        self.start_challenge(expires_in)

    def begin_server_attempt(self) -> tuple[dict[str, str] | None, str]:
        """Start one authoritative verification request.

        The returned values are transport-neutral, so the host application can
        submit them through its own asynchronous network layer.
        """

        if not self.require_server_verification:
            return None, "当前验证码未启用服务端验证"
        if self._pending_attempt_id:
            return None, "服务端正在验证，请稍候"
        if not self._challenge_token:
            return None, "缺少有效的服务端挑战，验证已拒绝"

        attempt_id = secrets.token_urlsafe(18)
        self._pending_attempt_id = attempt_id
        self._server_timer.start()
        return {
            "attemptId": attempt_id,
            "challengeToken": self._challenge_token,
        }, ""

    def resolve_server_attempt(self, attempt_id: str) -> bool:
        """Consume a matching pending attempt and reject stale responses."""

        if not self._pending_attempt_id or attempt_id != self._pending_attempt_id:
            return False
        self.invalidate_server_challenge()
        return True

    def invalidate_server_challenge(self) -> None:
        self._server_timer.stop()
        self._pending_attempt_id = None
        self._challenge_token = None

    def reset(self) -> None:
        self._server_timer.stop()
        self._pending_attempt_id = None
        if self.require_server_verification:
            self._challenge_token = None
        self.start_challenge()

    def _handle_server_timeout(self) -> None:
        if not self._pending_attempt_id:
            return
        self.invalidate_server_challenge()
        self.serverTimedOut.emit()
