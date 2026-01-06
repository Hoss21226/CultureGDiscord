# cogs/scheduler.py

import datetime

import discord
from discord.ext import commands, tasks

from database import db
from config import (
    DAILY_CHANNEL_ID,
    REPORT_CHANNEL_ID,
    DIRECTION_ROLE_ID,
    DAILY_QUESTION_HOUR,
    REPORT_WEEKDAY,
    REPORT_HOUR,
)

from cogs.quiz import QuizView  # on réutilise la même vue que pour !quiz
from ui import Theme, Emojis, base_embed, score_lines_from_pairs


class SchedulerCog(commands.Cog):
    """
    - Question quotidienne (mode 'daily') dans un salon précis
    - Rapport hebdomadaire (top 5 semaine) avec ping de la direction
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.daily_question_task.start()
        self.weekly_report_task.start()

    def cog_unload(self):
        self.daily_question_task.cancel()
        self.weekly_report_task.cancel()

    # ========== QUESTION QUOTIDIENNE ==========

    @tasks.loop(minutes=1)
    async def daily_question_task(self):
        """
        Toutes les minutes, on vérifie si on est à l'heure prévue.
        C'est plus simple qu'un système ultra précis avec timezones.
        """
        now = datetime.datetime.now()
        if now.hour != DAILY_QUESTION_HOUR or now.minute != 0:
            return

        channel = self.bot.get_channel(DAILY_CHANNEL_ID)
        if channel is None:
            return

        question = db.get_random_question()
        if not question:
            await channel.send("Aucune question disponible pour la question quotidienne 😢")
            return

        title = f"{Emojis.DAILY} Question quotidienne — {question.category} ({question.difficulty})"
        embed = base_embed(
            title=title,
            description=question.question,
            color=Theme.INFO,
            footer="Réponds via les boutons pour gagner des points (mode quotidien)",
        )

        letters = ["A", "B", "C", "D"]
        for i, choice in enumerate(question.choices):
            embed.add_field(name=f"{letters[i]}.", value=choice, inline=False)

        # Ici, on réutilise QuizView mais en mode 'daily'
        view = QuizView(
            question=question,
            player_id=0,           # 0 = utilisé comme “pas de joueur unique”
            username="daily",
            mode="daily",
        )

        await channel.send(embed=embed, view=view)

    @daily_question_task.before_loop
    async def before_daily_question(self):
        await self.bot.wait_until_ready()

    # ========== RAPPORT HEBDOMADAIRE ==========

    @tasks.loop(minutes=10)
    async def weekly_report_task(self):
        """
        Toutes les 10 minutes, on regarde si on est le bon jour + l'heure du rapport.
        Si oui, on génère le classement de la semaine.
        """
        now = datetime.datetime.now()
        if now.weekday() != REPORT_WEEKDAY:
            return
        if now.hour != REPORT_HOUR:
            return
        # on limite aux minutes proches de l'heure pour éviter doublons
        if now.minute not in (0, 1, 2):
            return

        channel = self.bot.get_channel(REPORT_CHANNEL_ID)
        if channel is None:
            return

        top = db.get_weekly_top(limit=5)
        if not top:
            await channel.send(f"{Emojis.CHART} Aucun joueur n'a répondu cette semaine.")
            return

        # top = [(discord_id, score), ...]
        lines = score_lines_from_pairs(
            top,
            fmt="<@{id}> : **{score}** bonnes réponses",
        )

        direction_ping = f"<@&{DIRECTION_ROLE_ID}>"

        embed = base_embed(
            title=f"{Emojis.CHART} Rapport hebdomadaire — Top 5 joueurs",
            description=lines,
            color=Theme.SUCCESS,
        )
        embed.set_footer(text="Basé sur toutes les réponses (quiz, duel, battle royale, daily).")

        await channel.send(
            content=f"{direction_ping} — voici le classement de la semaine :",
            embed=embed,
        )

    @weekly_report_task.before_loop
    async def before_weekly_report(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(SchedulerCog(bot))
