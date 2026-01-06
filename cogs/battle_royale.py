# cogs/battle_royale.py

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Set

import discord
from discord.ext import commands

from database import db
from questions import Question
from ui import Theme, Emojis, base_embed, score_lines_from_pairs, progress_bar


@dataclass
class BattleRoyaleState:
    channel_id: int
    host_id: int
    max_rounds: int = 5
    current_round: int = 0
    in_progress: bool = False
    participants: Dict[int, int] = field(default_factory=dict)  # discord_id -> score

    def add_participant(self, user_id: int):
        self.participants.setdefault(user_id, 0)

    def is_ready(self) -> bool:
        return len(self.participants) >= 2  # au moins 2 joueurs

    def increment_round(self):
        self.current_round += 1

    def is_finished(self) -> bool:
        return self.current_round >= self.max_rounds


class BattleRoyaleManager:
    """
    Gère les sessions Battle Royale par salon.
    """
    def __init__(self):
        self.sessions: Dict[int, BattleRoyaleState] = {}

    def has_session(self, channel_id: int) -> bool:
        return channel_id in self.sessions

    def get_session(self, channel_id: int) -> Optional[BattleRoyaleState]:
        return self.sessions.get(channel_id)

    def create_session(self, channel_id: int, host_id: int, max_rounds: int = 5) -> BattleRoyaleState:
        state = BattleRoyaleState(
            channel_id=channel_id,
            host_id=host_id,
            max_rounds=max_rounds,
        )
        self.sessions[channel_id] = state
        return state

    def end_session(self, channel_id: int):
        self.sessions.pop(channel_id, None)


br_manager = BattleRoyaleManager()


class BattleRoyaleQuestionView(discord.ui.View):
    def __init__(self, state: BattleRoyaleState, question: Question):
        super().__init__(timeout=30)
        self.state = state
        self.question = question
        self.answered_users: Set[int] = set()
        self.answers: Dict[int, bool] = {}  # discord_id -> correct?
        self.finished_round = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # doit être un participant
        if interaction.user.id not in self.state.participants:
            await interaction.response.send_message(
                "Tu ne participes pas à cette Battle Royale. Utilise `!brjoin` avant le début.",
                ephemeral=True,
            )
            return False
        # si round déjà fini
        if self.finished_round:
            await interaction.response.send_message(
                "Le tour est terminé, attends la prochaine question.",
                ephemeral=True,
            )
            return False
        return True

    async def handle_answer(self, interaction: discord.Interaction, choice_index: int):
        user_id = interaction.user.id

        # déjà répondu
        if user_id in self.answered_users:
            await interaction.response.send_message(
                "Tu as déjà répondu à cette question.",
                ephemeral=True,
            )
            return

        self.answered_users.add(user_id)
        correct = (choice_index == self.question.correct_index)
        self.answers[user_id] = correct

        # log + stats globales
        db.update_after_answer(
            discord_id=user_id,
            username=str(interaction.user),
            correct=correct,
            question_id=self.question.id,
            mode="br",
        )

        # petite réponse perso
        text = f"{Emojis.SUCCESS} Bonne réponse !" if correct else f"{Emojis.FAIL} Mauvaise réponse..."
        await interaction.response.send_message(text, ephemeral=True)

        # Si tout le monde a répondu, on clôture le round
        if len(self.answered_users) == len(self.state.participants):
            await self.finalize_round(interaction)

    async def finalize_round(self, interaction: discord.Interaction):
        if self.finished_round:
            return
        self.finished_round = True

        # mettre à jour les scores du round
        for user_id, correct in self.answers.items():
            if correct:
                self.state.participants[user_id] += 1

        # désactivation des boutons
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True

        # préparation de l'embed récap du round
        correct_letter = ["A", "B", "C", "D"][self.question.correct_index]
        correct_text = self.question.choices[self.question.correct_index]

        sorted_scores = sorted(
            self.state.participants.items(),
            key=lambda kv: kv[1],
            reverse=True,
        )

        score_text = score_lines_from_pairs(
            sorted_scores,
            fmt="<@{id}> : **{score}** pts",
        )

        desc = (
            f"La bonne réponse était **{correct_letter}. {correct_text}**.\n\n"
            f"**Score actuel :**\n{score_text}\n"
        )

        if self.question.explanation:
            desc += f"\n{Emojis.INFO} {self.question.explanation}"

        embed = base_embed(
            title=f"{Emojis.BR} Fin de la manche {self.state.current_round}/{self.state.max_rounds}",
            description=desc,
            color=Theme.WARNING,
        )

        # on édite le message de la question
        await interaction.message.edit(embed=embed, view=self)

        # round suivant ou fin
        await self._continue_or_end(interaction)

    async def _continue_or_end(self, interaction: discord.Interaction):
        channel = interaction.channel
        if not channel:
            return

        # si on a atteint le max de rounds → fin
        if self.state.is_finished():
            sorted_scores = sorted(
                self.state.participants.items(),
                key=lambda kv: kv[1],
                reverse=True,
            )

            if not sorted_scores:
                txt = "Aucun participant n'a marqué de points."
            else:
                txt = f"{Emojis.TROPHY} **Battle Royale terminée !**\n\n"
                txt += score_lines_from_pairs(
                    sorted_scores,
                    fmt="<@{id}> : **{score}** pts",
                )

            br_manager.end_session(self.state.channel_id)
            await interaction.followup.send(txt)
            return

        # sinon, on passe au round suivant
        self.state.increment_round()
        next_question = db.get_random_question()
        if not next_question:
            await interaction.followup.send("Plus de questions disponibles pour continuer la Battle Royale 😢")
            br_manager.end_session(self.state.channel_id)
            return

        title = f"{Emojis.BR} Battle Royale — Manche {self.state.current_round}/{self.state.max_rounds}"
        desc = (
            "Tout le monde joue !\n\n"
            f"**Question :** {next_question.question}\n\n"
            f"{progress_bar(self.state.current_round, self.state.max_rounds)}"
        )

        embed = base_embed(
            title=title,
            description=desc,
            color=Theme.ERROR,
        )

        letters = ["A", "B", "C", "D"]
        for i, choice in enumerate(next_question.choices):
            embed.add_field(name=f"{letters[i]}.", value=choice, inline=False)

        view = BattleRoyaleQuestionView(self.state, next_question)
        await interaction.followup.send(embed=embed, view=view)

    async def on_timeout(self):
        # si tout le monde n'a pas répondu, on clôture quand même (personne ne gagne de point en plus)
        if not self.finished_round and self.state.in_progress:
            self.finished_round = True

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


class BattleRoyaleCog(commands.Cog):
    """
    Mode Battle Royale (FFA) :
    - !brcreate [manches]
    - !brjoin
    - !brstart
    - !brcancel
    """
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="brcreate")
    async def br_create(self, ctx: commands.Context, rounds: Optional[int] = 5):
        channel_id = ctx.channel.id

        if br_manager.has_session(channel_id):
            await ctx.send(
                "Une Battle Royale existe déjà dans ce salon. "
                "Utilise `!brcancel` si tu veux l'annuler."
            )
            return

        try:
            max_rounds = int(rounds)
        except (TypeError, ValueError):
            max_rounds = 5

        if max_rounds <= 0:
            max_rounds = 5

        state = br_manager.create_session(channel_id, host_id=ctx.author.id, max_rounds=max_rounds)
        state.add_participant(ctx.author.id)

        embed = base_embed(
            title=f"{Emojis.BR} Battle Royale créée",
            description=(
                f"Créée par {ctx.author.mention} pour **{max_rounds} manches**.\n\n"
                f"➡️ Utilisez `!brjoin` pour participer.\n"
                f"➡️ L'organisateur lance avec `{self.bot.command_prefix}brstart`."
            ),
            color=Theme.ERROR,
        )
        await ctx.send(embed=embed)

    @commands.command(name="brjoin")
    async def br_join(self, ctx: commands.Context):
        channel_id = ctx.channel.id
        state = br_manager.get_session(channel_id)
        if not state:
            await ctx.send("Aucune Battle Royale en attente dans ce salon. Utilise `!brcreate` pour en créer une.")
            return

        if state.in_progress:
            await ctx.send("Cette Battle Royale a déjà commencé, tu ne peux plus rejoindre.")
            return

        if ctx.author.id in state.participants:
            await ctx.send("Tu participes déjà à cette Battle Royale.")
            return

        state.add_participant(ctx.author.id)
        await ctx.send(
            f"{ctx.author.mention} a rejoint la Battle Royale ! "
            f"Joueurs : **{len(state.participants)}**"
        )

    @commands.command(name="brcancel")
    async def br_cancel(self, ctx: commands.Context):
        channel_id = ctx.channel.id
        state = br_manager.get_session(channel_id)
        if not state:
            await ctx.send("Aucune Battle Royale à annuler dans ce salon.")
            return

        if ctx.author.id != state.host_id:
            await ctx.send("Seul l'organisateur peut annuler la Battle Royale.")
            return

        br_manager.end_session(channel_id)
        await ctx.send(f"{Emojis.FAIL} Battle Royale annulée.")

    @commands.command(name="brstart")
    async def br_start(self, ctx: commands.Context):
        channel_id = ctx.channel.id
        state = br_manager.get_session(channel_id)

        if not state:
            await ctx.send("Aucune Battle Royale créée dans ce salon. Utilise `!brcreate` d'abord.")
            return

        if state.in_progress:
            await ctx.send("Cette Battle Royale est déjà en cours.")
            return

        if ctx.author.id != state.host_id:
            await ctx.send("Seul l'organisateur peut lancer la Battle Royale.")
            return

        if not state.is_ready():
            await ctx.send("Il faut au moins **2 joueurs** pour lancer une Battle Royale.")
            return

        state.in_progress = True
        state.increment_round()

        question = db.get_random_question()
        if not question:
            await ctx.send("Aucune question disponible pour lancer la Battle Royale.")
            br_manager.end_session(channel_id)
            return

        participants_list = ", ".join(f"<@{uid}>" for uid in state.participants.keys())

        intro_embed = base_embed(
            title=f"{Emojis.BR} Battle Royale lancée !",
            description=(
                f"**Joueurs :** {participants_list}\n\n"
                f"On joue en **{state.max_rounds} manches**. Bonne chance à tous !"
            ),
            color=Theme.ERROR,
        )
        await ctx.send(embed=intro_embed)

        title = f"{Emojis.BR} Battle Royale — Manche {state.current_round}/{state.max_rounds}"
        desc = (
            "Tout le monde joue !\n\n"
            f"**Question :** {question.question}\n\n"
            f"{progress_bar(state.current_round, state.max_rounds)}"
        )

        embed = base_embed(
            title=title,
            description=desc,
            color=Theme.ERROR,
        )

        letters = ["A", "B", "C", "D"]
        for i, choice in enumerate(question.choices):
            embed.add_field(name=f"{letters[i]}.", value=choice, inline=False)

        view = BattleRoyaleQuestionView(state, question)
        await ctx.send(embed=embed, view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(BattleRoyaleCog(bot))
