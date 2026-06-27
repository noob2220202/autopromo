import os

from dotenv import load_dotenv

load_dotenv()


def _split_ids(raw: str) -> set[int]:
    return {int(x) for x in raw.split(",") if x.strip()}


TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
ADMIN_IDS = _split_ids(os.environ.get("ADMIN_IDS", ""))

TRONGRID_API_KEY = os.environ["TRONGRID_API_KEY"]
USDT_CONTRACT = os.environ.get("USDT_CONTRACT", "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t")

OWNER_WALLET_ADDRESS = os.environ["OWNER_WALLET_ADDRESS"]
PRO_PLAN_USDT_PRICE = float(os.environ.get("PRO_PLAN_USDT_PRICE", "5.0"))
PRO_PLAN_DAYS = int(os.environ.get("PRO_PLAN_DAYS", "30"))

POLL_INTERVAL_SECONDS = int(os.environ.get("POLL_INTERVAL_SECONDS", "60"))
PRICE_CHECK_INTERVAL_SECONDS = int(os.environ.get("PRICE_CHECK_INTERVAL_SECONDS", "300"))

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./bot.db")

FREE_PLAN_WALLET_LIMIT = 1
PRO_PLAN_WALLET_LIMIT = 5

TRONGRID_BASE_URL = "https://api.trongrid.io"
TRONSCAN_TOKEN_API_URL = "https://apilist.tronscanapi.com/api/token_trc20"
COINGECKO_API_URL = "https://api.coingecko.com/api/v3/simple/price"

TRON_ADDRESS_RE = r"^T[A-Za-z0-9]{33}$"
TX_HASH_RE = r"^[a-fA-F0-9]{64}$"

KST_OFFSET_HOURS = 9
