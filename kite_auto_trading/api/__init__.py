"""
API integration layer for the Kite Auto-Trading application.

This module handles all external API communications, primarily with
Zerodha's Kite Connect API.
"""

from .base import APIClient, TradingAPIClient, MarketDataAPIClient

__all__ = [
    'APIClient',
    'TradingAPIClient', 
    'MarketDataAPIClient',
]