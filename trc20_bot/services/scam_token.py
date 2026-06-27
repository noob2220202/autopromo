import logging

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from config import TRONSCAN_TOKEN_API_URL, USDT_CONTRACT
from db import crud

logger = logging.getLogger(__name__)

_SCAM_TAGS = {"scam", "risk", "fake", "phishing"}
_TIMEOUT = 10.0


async def _check_tronscan_tag(contract_address: str) -> tuple[bool, str | None]:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.get(TRONSCAN_TOKEN_API_URL, params={"contract": contract_address})
        response.raise_for_status()
        data = response.json()
        tokens = data.get("trc20_tokens") or []
        if not tokens:
            return False, None
        tag = (tokens[0].get("tag") or "").lower()
        for keyword in _SCAM_TAGS:
            if keyword in tag:
                return True, tag
        return False, tag
    except httpx.TimeoutException:
        logger.warning("TronScan timeout checking %s", contract_address)
        return False, None


async def is_scam_token(
    session: AsyncSession, token_contract: str, token_name: str | None = None, token_symbol: str | None = None
) -> bool:
    if token_contract == USDT_CONTRACT:
        return False

    cached = await crud.get_scam_token(session, token_contract)
    if cached is not None:
        return True

    is_scam, tag = await _check_tronscan_tag(token_contract)
    await crud.cache_scam_token(
        session,
        contract_address=token_contract,
        is_scam=is_scam,
        token_name=token_name,
        token_symbol=token_symbol,
        source="tronscan",
        reason=tag,
    )
    return is_scam
