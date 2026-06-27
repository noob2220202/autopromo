import re

from config import TRON_ADDRESS_RE, TX_HASH_RE

_ADDRESS_PATTERN = re.compile(TRON_ADDRESS_RE)
_TX_HASH_PATTERN = re.compile(TX_HASH_RE)


def is_tron_address(text: str) -> bool:
    return bool(_ADDRESS_PATTERN.match(text.strip()))


def is_tx_hash(text: str) -> bool:
    return bool(_TX_HASH_PATTERN.match(text.strip()))
