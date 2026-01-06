# cogs/duel.py

from dataclasses import dataclass, field
from typing import Dict, Optional

import discord
from discord.ext import commands

from database import db
from questions import Question
from ui import Theme, Emojis, base_embed, progress_bar


@dataclass
class DuelState:
    channel_id: int
    player1_id: int
    player2_id: int
    max_rounds: int = 5
    current_round: int = 1
    current_player_id: int = 0
    scores: Dict[int, int] = field(default_factory=dict)

    def __post_init__(self):
        self.scores.setdefault(self.player1_id, 0)
        self.scores.setdefault(self.player2_id, 0)
        if self.current_player_id == 0:
            self.current_player_id = self.player1_id

    def other_player_id(self) -> int:
        return self.player2_id if self.current_player_id == self.player1_id else self.player1_id

    def next_turn(self):
        self.current_round += 1
        self.current_player_id = self.other_player_id()

    def is_finished(self) -> bool:
        return self.current_round > self.max_rounds


class DuelManager:
    def __init__(self):
        self.duels: Dict[int, DuelState] = {}

    def has_duel(self, channel_id: int) -> bool:
        return channel_id in self.duels

    def get_duel(self, channel_id: int) -> Optional[DuelState]:
        return self.duels.get(channel_id)

    def start_duel(self, channel_id: int, p1: int, p2: int, max_rounds: int = 5) -> DuelState:
        duel = DuelState(channel_id, p1, p2, max_rounds=max_rounds)
        self.duels[channel_id] = duel
        return duel

    def end_duel(self, channel_id: int):
        self.duels.pop(channel_id, None)


duel_manager = DuelManager()


class DuelQuestionView(discord.ui.View):
    def __init__(self, duel: DuelState, question: Question):
        super().__init__(timeout=30)
        self.duel = duel
        self.question = question
        self.answered = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.duel.current_player_id:
            await interaction.response.send_message(
                "Ce n'est pas ton tour dans ce duel.", ephemeral=True
            )
            return False
        return True

    async def handle_answer(self, interaction: discord.Interaction, choice_index: int):
        if self.answered:
            return
        self.answered = True

        channel_id = interaction.channel.id if interaction.channel else self.duel.channel_id
        duel = duel_manager.get_duel(channel_id)
        if not duel:
            await interaction.response.send_message("Le duel n'existe plus.", ephemeral=True)
            return

        correct = (choice_index == self.question.correct_index)

        db.update_after_answer(
            discord_id=interaction.user.id,
            username=str(interaction.user),
            correct=correct,
            question_id=self.question.id,
            mode="duel",
        )

        if correct:
            duel.scores[interaction.user.id] += 1

        # Désactiver les boutons
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True

        # Style avancé pour le résultat
        color = Theme.SUCCESS if correct else Theme.ERROR
        title = (
            f"{Emojis.SUCCESS} Bonne réponse !"
            if correct
            else f"{Emojis.FAIL} Mauvaise réponse…"
        )
        correct_letter = ["A", "B", "C", "D"][self.question.correct_index]
        correct_text = self.question.choices[self.question.correct_index]

        p1_score = duel.scores[duel.player1_id]
        p2_score = duel.scores[duel.player2_id]

        description = (
            f"La bonne réponse était **{correct_letter}. {correct_text}**.\n\n"
            f"**Score :**\n"
            f"- <@{duel.player1_id}> : **{p1_score}** pts\n"
            f"- <@{duel.player2_id}> : **{p2_score}** pts\n"
        )
        if self.question.explanation:
            description += f"\n{Emojis.INFO} {self.question.explanation}"

        embed = base_embed(
            title=title,
            description=description,
            color=color,
        )
        await interaction.response.edit_message(embed=embed, view=self)

        await self._continue_or_end(interaction, duel)

    async def _continue_or_end(self, interaction: discord.Interaction, duel: DuelState):
        channel = interaction.channel
        if not channel:
            return

        # Fin du duel
        if duel.is_finished():
            p1_score = duel.scores[duel.player1_id]
            p2_score = duel.scores[duel.player2_id]
            if p1_score > p2_score:
                txt = (
                    f"{Emojis.TROPHY} <@{duel.player1_id}> gagne le duel "
                    f"**{p1_score}** à **{p2_score}** !"
                )
            elif p2_score > p1_score:
                txt = (
                    f"{Emojis.TROPHY} <@{duel.player2_id}> gagne le duel "
                    f"**{p2_score}** à **{p1_score}** !"
                )
            else:
                txt = f"🤝 Égalité parfaite : **{p1_score}** - **{p2_score}**."
            duel_manager.end_duel(duel.channel_id)
            await interaction.followup.send(txt)
            return

        # Manche suivante
        duel.next_turn()
        next_q = db.get_random_question()
        if not next_q:
            await interaction.followup.send("Plus de questions disponibles pour le duel 😢")
            duel_manager.end_duel(duel.channel_id)
            return

        current_mention = f"<@{duel.current_player_id}>"
        title = f"{Emojis.DUEL} Duel — Manche {duel.current_round}/{duel.max_rounds}"
        desc = (
            f"C'est au tour de {current_mention} !\n\n"
            f"**Question :** {next_q.question}\n\n"
            f"{progress_bar(duel.current_round, duel.max_rounds)}"
        )

        embed = base_embed(
            title=title,
            description=desc,
            color=Theme.WARNING,
        )

        letters = ["A", "B", "C", "D"]
        for i, choice in enumerate(next_q.choices):
            embed.add_field(name=f"{letters[i]}.", value=choice, inline=False)

        view = DuelQuestionView(duel, next_q)
        await interaction.followup.send(embed=embed, view=view)

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


class DuelCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="duel")
    async def duel(self, ctx: commands.Context, opponent: Optional[discord.Member] = None, rounds: int = 5):
        """
        Duel 1v1.
        Plus tard : on pourra étendre pour 2v2 / 3v3 en ajoutant d'autres commandes.
        """
        if opponent is None:
            await ctx.send("Utilisation : `!duel @joueur [nombre_de_manches]`")
            return

        if opponent.bot:
            await ctx.send("Tu ne peux pas défier un bot.")
            return

        if opponent.id == ctx.author.id:
            await ctx.send("Tu ne peux pas te défier toi-même 😅")
            return

        channel_id = ctx.channel.id
        if duel_manager.has_duel(channel_id):
            await ctx.send("Un duel est déjà en cours dans ce salon.")
            return

        if rounds <= 0:
            rounds = 5

        duel = duel_manager.start_duel(channel_id, ctx.author.id, opponent.id, max_rounds=rounds)

        intro = (
            f"{Emojis.DUEL} **DUEL LANCÉ !**\n"
            f"{ctx.author.mention} défie {opponent.mention} en Culture G.\n"
            f"Le duel se joue en **{rounds} manches**.\n"
            f"{ctx.author.mention} commence.\n\n"
            f"{progress_bar(1, rounds)}"
        )
        await ctx.send(intro)

        q = db.get_random_question()
        if not q:
            await ctx.send("Aucune question disponible pour démarrer le duel.")
            duel_manager.end_duel(channel_id)
            return

        title = f"{Emojis.DUEL} Duel — Manche {duel.current_round}/{duel.max_rounds}"
        desc = (
            f"C'est au tour de {ctx.author.mention} !\n\n"
            f"**Question :** {q.question}\n\n"
            f"{progress_bar(duel.current_round, duel.max_rounds)}"
        )

        embed = base_embed(
            title=title,
            description=desc,
            color=Theme.WARNING,
        )

        letters = ["A", "B", "C", "D"]
        for i, choice in enumerate(q.choices):
            embed.add_field(name=f"{letters[i]}.", value=choice, inline=False)

        view = DuelQuestionView(duel, q)
        await ctx.send(embed=embed, view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(DuelCog(bot))
