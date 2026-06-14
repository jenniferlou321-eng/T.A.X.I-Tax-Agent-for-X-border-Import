"""Payment channel abstraction — PaymentChannel ABC + core types."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class PaymentAuthResult:
    """Result of payment channel authentication."""
    success: bool
    access_token: Optional[str] = None
    expires_at: Optional[datetime] = None
    error: Optional[str] = None


@dataclass
class PaymentTransaction:
    """A single payment transaction record from a payment gateway."""
    transaction_id: str
    amount: str
    currency: str
    status: str
    timestamp: datetime
    payer_email: str = ""
    raw_data: dict = field(default_factory=dict)


class PaymentChannel(ABC):
    """Abstract base class for payment gateway integrations.

    All payment channels (PayPal, Stripe, etc.) implement this interface.
    Separate from FilingChannel — payment gateways have fundamentally
    different operations (list transactions, pull refunds) than tax
    filing channels (submit return, get receipt status).
    """

    channel_name: str = ""

    @abstractmethod
    async def authenticate(self) -> PaymentAuthResult:
        """Authenticate with the payment gateway and obtain an access token."""
        ...

    @abstractmethod
    async def list_transactions(
        self, start_date: str, end_date: str, page_size: int = 50
    ) -> list[PaymentTransaction]:
        """List transactions within a date range."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Quick connectivity check — credentials valid and API reachable."""
        ...
