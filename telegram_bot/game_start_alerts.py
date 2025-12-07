# game_alerts.py
from __future__ import annotations

import datetime as dt
from threading import Timer
from typing import Callable, Optional

from telegram_bot.telegram_alerts import send_telegram


def parse_iso_utc(s: str) -> dt.datetime:
    """
    Polymarket gives ISO strings like '2025-09-22T00:00:00Z'.
    Convert to aware UTC datetime.
    """
    if s.endswith("Z"):
        s = s.replace("Z", "+00:00")
    return dt.datetime.fromisoformat(s).astimezone(dt.timezone.utc)


def schedule_game_start_alert(
    game_name: str,
    game_start_iso: str,
    minutes_before: int = 10,
    extra_info: Optional[str] = None,
) -> None:
    """
    Unconditional alert minutes_before game start.
    """
    game_start = parse_iso_utc(game_start_iso)
    alert_time = game_start - dt.timedelta(minutes=minutes_before)

    now = dt.datetime.now(dt.timezone.utc)
    delay = max((alert_time - now).total_seconds(), 0)

    text_lines = [
        f"⏰ Game alert for *{game_name}*",
        f"Starts at: `{game_start.isoformat()}` (UTC)",
        f"Alert offset: {minutes_before} min before start.",
    ]
    if extra_info:
        text_lines.append(extra_info)

    msg = "\n".join(text_lines)

    def _send():
        send_telegram(msg, parse_mode="Markdown")

    Timer(delay, _send).start()





def schedule_position_dependent_game_alert(
    game_name: str,
    game_start_iso: str,
    market_id: str,
    position_checker: Callable[[str], float],
    minutes_before: int = 10,
    extra_info: Optional[str] = None,
) -> None:
    """
    Schedule an alert minutes_before game start,
    BUT only send it if position_checker(market_id) != 0.

    - position_checker: function you provide:
        position = position_checker(market_id)  # net position (float, Decimal, etc.)
    """

    game_start = parse_iso_utc(game_start_iso)
    alert_time = game_start - dt.timedelta(minutes=minutes_before)

    now = dt.datetime.now(dt.timezone.utc)
    delay = max((alert_time - now).total_seconds(), 0)

    def _check_and_alert():
        try:
            pos = position_checker(market_id)
        except Exception as e:
            # Optional: send error to yourself instead
            send_telegram(
                f"⚠️ Error checking position for {game_name} / {market_id}: {e!r}"
            )
            return

        # Treat anything "non-zero" as having a position
        try:
            has_pos = float(pos) != 0.0
        except Exception:
            has_pos = bool(pos)

        if not has_pos:
            # You can uncomment this if you want "no position" info
            # send_telegram(f"ℹ️ No position in {game_name} at alert time.")
            return

        text_lines = [
            f"⏰ *Game starting soon* – you HAVE a position!",
            f"Game: *{game_name}*",
            f"Market ID: `{market_id}`",
            f"Net position: `{pos}`",
            f"Starts at: `{game_start.isoformat()}` (UTC)",
            f"Alert offset: {minutes_before} min before start.",
        ]
        if extra_info:
            text_lines.append(extra_info)

        msg = "\n".join(text_lines)
        send_telegram(msg, parse_mode="Markdown")

    Timer(delay, _check_and_alert).start()



def send_position_check(game_name, minutes_before, market_id, pos, game_start):
    send_telegram(
        f"⚠️ Game starting in {minutes_before} minutes!\n"
        f"*{game_name}*\n"
        f"Market: `{market_id}`\n"
        f"Position: `{pos}`\n"
        f"Start time: `{game_start.isoformat()}`",
        parse_mode="Markdown"
    )