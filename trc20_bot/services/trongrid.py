import asyncio
import logging

import httpx

from config import TRONGRID_API_KEY, TRONGRID_BASE_URL, USDT_CONTRACT

logger = logging.getLogger(__name__)

_HEADERS = {"TRON-PRO-API-KEY": TRONGRID_API_KEY}
_TIMEOUT = 10.0


async def _get(path: str, params: dict | None = None) -> dict | None:
    url = f"{TRONGRID_BASE_URL}{path}"
    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                response = await client.get(url, headers=_HEADERS, params=params)
            if response.status_code == 429 and attempt == 0:
                await asyncio.sleep(2)
                continue
            if response.status_code >= 500:
                logger.warning("TronGrid 5xx for %s: %s", url, response.status_code)
                return None
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException:
            logger.warning("TronGrid timeout for %s", url)
            return None
    return None


async def get_balance(address: str) -> float:
    data = await _get(f"/v1/accounts/{address}")
    if not data or not data.get("data"):
        return 0.0
    account = data["data"][0]
    for entry in account.get("trc20", []):
        if USDT_CONTRACT in entry:
            return int(entry[USDT_CONTRACT]) / 1_000_000
    return 0.0


async def get_trc20_transactions(address: str, limit: int = 20, contract_address: str | None = None) -> list[dict]:
    params = {"limit": limit, "only_confirmed": "true"}
    if contract_address:
        params["contract_address"] = contract_address
    data = await _get(f"/v1/accounts/{address}/transactions/trc20", params=params)
    if not data:
        return []
    return data.get("data", [])


async def get_transaction(tx_id: str) -> dict | None:
    data = await _get(f"/v1/transactions/{tx_id}")
    if not data or not data.get("data"):
        return None
    return data["data"][0]
