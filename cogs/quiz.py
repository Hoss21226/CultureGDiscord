# cogs/quiz.py

import random
from typing import Optional

import discord
from discord.ext import commands

from database import db
from questions import Question
from ui import Theme, Emojis, base_embed, score_lines_from_pairs


class QuizView(discord.ui.View):
    def __init__(self, question: Question, player_id: int, username: str, mode: str = "quiz", timeout: int = 30):
        super().__init__(timeout=timeout)
        self.question = question
        self.player_id = player_id
        self.username = username
        self.mode = mode
        self.answered = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """
        - mode 'quiz' : seul le joueur qui a lancé la commande peut répondre
        - mode 'daily' : tout le monde peut jouer
        """
        if self.mode == "daily":
            return True

        if interaction.user.id != self.player_id:
            await interaction.response.send_message(
                "Ce quiz n'est pas pour toi. Lance ton propre quiz avec `!quiz` 😉",
                ephemeral=True,
            )
            return False
        return True


    async def handle_answer(self, interaction: discord.Interaction, choice_index: int):
        if self.answered:
            return
        self.answered = True

        correct = (choice_index == self.question.correct_index)

        db.update_after_answer(
            discord_id=self.player_id,
            username=self.username,
            correct=correct,
            question_id=self.question.id,
            mode=self.mode,
        )

        # Désactivation des boutons
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True

        # Style avancé pour le résultat
        color = Theme.SUCCESS if correct else Theme.ERROR
        title = f"{Emojis.SUCCESS} Bonne réponse !" if correct else f"{Emojis.FAIL} Mauvaise réponse…"
        correct_letter = ["A", "B", "C", "D"][self.question.correct_index]
        correct_text = self.question.choices[self.question.correct_index]

        description = f"La bonne réponse était **{correct_letter}. {correct_text}**."
        if self.question.explanation:
            description += f"\n\n{Emojis.INFO} {self.question.explanation}"

        embed = base_embed(
            title=title,
            description=description,
            color=color,
        )

        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="A", style=discord.ButtonStyle.primary)
    async def a(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_answer(interaction, 0)

    @discord.ui.button(label="B", style=discord.ButtonStyle.primary)
    async def b(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_answer(interaction, 1)

    @discord.ui.button(label="C", style=discord.ButtonStyle.primary)
    async def c(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_answer(interaction, 2)

    @discord.ui.button(label="D", style=discord.ButtonStyle.primary)
    async def d(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_answer(interaction, 3)


class QuizCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="quiz")
    async def quiz(self, ctx: commands.Context, category: Optional[str] = None, difficulty: Optional[str] = None):
        """
        Question simple de Culture G.
        Optionnel : catégorie / difficulté plus tard (ex : !quiz Histoire facile).
        """
        question = db.get_random_question(category=category, difficulty=difficulty)
        if not question:
            await ctx.send("Aucune question disponible 😢")
            return

        title = f"{Emojis.QUIZ} Quiz — {question.category} ({question.difficulty})"
        embed = base_embed(
            title=title,
            description=question.question,
            color=Theme.PRIMARY,
            footer="Réponds via les boutons ci-dessous",
        )

        letters = ["A", "B", "C", "D"]
        for i, choice in enumerate(question.choices):
            embed.add_field(name=f"{letters[i]}.", value=choice, inline=False)

        view = QuizView(
            question=question,
            player_id=ctx.author.id,
            username=str(ctx.author),
            mode="quiz",
        )
        await ctx.send(embed=embed, view=view)

    @commands.command(name="profil")
    async def profil(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        """
        Affiche le profil culturel (stats) d'un joueur.
        Usage : !profil ou !profil @pseudo
        """
        target = member or ctx.author
        stats = db.get_profile(target.id)
        if not stats:
            await ctx.send("Aucune donnée pour ce joueur. Lance `!quiz` pour commencer.")
            return

        embed = base_embed(
            title=f"{Emojis.CHART} Profil de {target.display_name}",
            color=Theme.PURPLE,
        )

        embed.add_field(name="XP", value=f"{Emojis.STAR} {stats['xp']}", inline=True)
        embed.add_field(name="Précision", value=f"{stats['accuracy']:.1f} %", inline=True)
        embed.add_field(name="Questions répondues", value=str(stats["total_questions"]), inline=True)
        embed.add_field(name="Bonnes réponses", value=str(stats["total_correct"]), inline=True)
        embed.add_field(name="Série actuelle", value=str(stats["streak"]), inline=True)
        embed.add_field(name="Meilleure série", value=str(stats["best_streak"]), inline=True)

        await ctx.send(embed=embed)

    @commands.command(name="top")
    async def top(self, ctx: commands.Context):
        """
        Affiche le classement global des joueurs (XP).
        """
        leaderboard = db.get_leaderboard(limit=10)
        if not leaderboard:
            await ctx.send("Personne n'a encore joué, lance `!quiz` pour commencer.")
            return

        # leaderboard = [(discord_id, username, xp), ...]
        pairs = [(discord_id, xp) for (discord_id, username, xp) in leaderboard]
        lines = score_lines_from_pairs(pairs, fmt="<@{id}> : **{score}** XP")

        embed = base_embed(
            title=f"{Emojis.TROPHY} Classement global",
            description=lines,
            color=Theme.PURPLE,
        )
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(QuizCog(bot))
