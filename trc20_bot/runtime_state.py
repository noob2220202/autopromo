bot_halted = False


def is_halted() -> bool:
    return bot_halted


def set_halted(value: bool) -> None:
    global bot_halted
    bot_halted = value
