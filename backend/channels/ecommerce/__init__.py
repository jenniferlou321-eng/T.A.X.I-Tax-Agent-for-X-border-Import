"""Ecommerce channel abstraction — EcommerceChannel ABC + core types."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class EcommerceOrder:
    """A single order from an ecommerce platform."""
    order_id: str
    order_name: str
    created_at: datetime
    financial_status: str
    amount: str
    currency: str
    customer_name: str = ""
    customer_email: str = ""
    raw_data: dict = field(default_factory=dict)


@dataclass
class EcommerceHealth:
    """Result of an ecommerce platform health check."""
    connected: bool
    store_name: str = ""
    plan_name: str = ""
    country: str = ""
    error: str = ""


class EcommerceChannel(ABC):
    """Abstract base class for ecommerce platform integrations.

    All ecommerce channels (Shopify, WooCommerce, Magento, etc.) implement
    this interface. Separate from FilingChannel — ecommerce platforms have
    fundamentally different operations (list orders, get order details) than
    tax filing channels (submit return, get receipt status).
    """

    channel_name: str = ""

    @abstractmethod
    async def health_check(self) -> EcommerceHealth:
        """Verify connectivity to the ecommerce platform."""
        ...

    @abstractmethod
    async def list_recent_orders(self, limit: int = 10) -> list[EcommerceOrder]:
        """List recent orders from the platform."""
        ...

    @abstractmethod
    async def get_order(self, order_id: str) -> Optional[EcommerceOrder]:
        """Get a single order by ID."""
        ...
