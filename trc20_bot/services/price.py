import logging

import httpx

from config import COINGECKO_API_URL

logger = logging.getLogger(__name__)

_TIMEOUT = 10.0


async def get_usdt_price() -> dict | None:
    params = {"ids": "tether", "vs_currencies": "usd,krw", "include_24hr_change": "true"}
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.get(COINGECKO_API_URL, params=params)
        response.raise_for_status()
        data = response.json().get("tether")
        if not data:
            return None
        return {
            "usd": data.get("usd"),
            "krw": data.get("krw"),
            "usd_24h_change": data.get("usd_24h_change", 0.0),
        }
    except httpx.TimeoutException:
        logger.warning("CoinGecko timeout")
        return None
