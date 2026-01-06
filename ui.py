# ui.py

import datetime
from typing import Iterable, Tuple, Optional

import discord


# ========= PALETTE DE COULEURS =========

class Theme:
    PRIMARY = discord.Color.from_rgb(88, 101, 242)     # bleu Discord
    SUCCESS = discord.Color.from_rgb(46, 204, 113)     # vert
    ERROR = discord.Color.from_rgb(231, 76, 60)        # rouge
    WARNING = discord.Color.from_rgb(241, 196, 15)     # jaune
    INFO = discord.Color.from_rgb(52, 152, 219)        # bleu clair
    PURPLE = discord.Color.from_rgb(155, 89, 182)      # violet
    DARK = discord.Color.from_rgb(44, 47, 51)          # gris foncé


# ========= ÉMOJIS GLOBAUX =========

class Emojis:
    QUIZ = "🧠"
    DUEL = "⚔️"
    BR = "🔥"
    DAILY = "📅"
    TROPHY = "🏆"
    CHART = "📊"
    SUCCESS = "✅"
    FAIL = "❌"
    INFO = "ℹ️"
    STAR = "⭐"
    MEDAL_GOLD = "🥇"
    MEDAL_SILVER = "🥈"
    MEDAL_BRONZE = "🥉"
    DOT = "▫️"


# ========= FONCTIONS UTILITAIRES =========

def base_embed(
    title: str,
    description: str = "",
    *,
    color: discord.Color = Theme.PRIMARY,
    icon: Optional[str] = None,
    footer: Optional[str] = None,
) -> discord.Embed:
    """Embed standard du bot, avec style cohérent partout."""
    if icon:
        title = f"{icon}  {title}"

    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=datetime.datetime.utcnow(),
    )

    if footer:
        embed.set_footer(text=footer)

    return embed


def score_lines_from_pairs(
    pairs: Iterable[Tuple[int, int]],
    *,
    fmt: str = "<@{id}> : **{score}** pts",
    limit: Optional[int] = None,
) -> str:
    """
    Transforme une liste [(discord_id, score), ...] en texte formaté.
    """
    lines = []
    for idx, (discord_id, score) in enumerate(pairs, start=1):
        if limit is not None and idx > limit:
            break

        if idx == 1:
            medal = Emojis.MEDAL_GOLD
        elif idx == 2:
            medal = Emojis.MEDAL_SILVER
        elif idx == 3:
            medal = Emojis.MEDAL_BRONZE
        else:
            medal = Emojis.DOT

        lines.append(f"{medal} **#{idx}** — " + fmt.format(id=discord_id, score=score))

    return "\n".join(lines)


def progress_bar(current: int, total: int, length: int = 10) -> str:
    """Petite barre de progression en unicode pour les manches / rounds."""
    if total <= 0:
        total = 1
    ratio = max(0, min(1, current / total))
    filled = int(ratio * length)
    empty = length - filled
    return "▰" * filled + "▱" * empty + f"  ({current}/{total})"
