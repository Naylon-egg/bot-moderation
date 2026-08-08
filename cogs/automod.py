"""
cogs/automod.py
Sistema de moderação automática: filtro de palavras, bloqueio de menções em
massa, bloqueio de links de convite e detecção de flood/spam de mensagens.
"""

import re
import time
from collections import defaultdict

import discord
from discord.ext import commands

import database

INVITE_REGEX = re.compile(r"(discord\.gg|discordapp\.com/invite|discord\.com/invite)/\S+", re.IGNORECASE)

SPAM_MESSAGE_LIMIT = 5   # mensagens...
SPAM_TIME_WINDOW = 5     # ...em X segundos é considerado flood
MENTION_LIMIT = 5        # menções (usuário + cargo) permitidas em uma única mensagem


class AutoMod(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # guarda os horários das últimas mensagens de cada usuário, por servidor, para detectar flood
        self.spam_tracker: dict[tuple[int, int], list[float]] = defaultdict(list)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return
        if message.author.guild_permissions.manage_messages:
            return  # moderadores não são afetados pelo automod

        config = await database.get_guild_config(message.guild.id)
        if not config["automod_enabled"]:
            return

        if await self._checar_palavras_proibidas(message):
            return
        if await self._checar_mencoes_em_massa(message):
            return
        if config["block_invites"] and await self._checar_convites(message):
            return
        await self._checar_spam(message)

    async def _registrar_violacao(self, message: discord.Message, motivo: str, apagar: bool = True):
        if apagar:
            try:
                await message.delete()
            except (discord.Forbidden, discord.NotFound):
                pass

        try:
            aviso = await message.channel.send(f"⚠️ {message.author.mention}, {motivo}")
            await aviso.delete(delay=6)
        except discord.Forbidden:
            pass

        await database.add_warning(message.guild.id, message.author.id, self.bot.user.id, f"[AutoMod] {motivo}")

        mod_cog = self.bot.get_cog("Moderation")
        if mod_cog:
            await mod_cog.log_action(message.guild, "AutoMod", message.author, self.bot.user, motivo)

    async def _checar_palavras_proibidas(self, message: discord.Message) -> bool:
        palavras = await database.get_filtered_words(message.guild.id)
        if not palavras:
            return False
        conteudo = message.content.lower()
        for palavra in palavras:
            if palavra in conteudo:
                await self._registrar_violacao(message, "sua mensagem continha uma palavra não permitida.")
                return True
        return False

    async def _checar_mencoes_em_massa(self, message: discord.Message) -> bool:
        total = len(message.mentions) + len(message.role_mentions)
        if total >= MENTION_LIMIT:
            await self._registrar_violacao(message, f"muitas menções em uma única mensagem ({total}).")
            return True
        return False

    async def _checar_convites(self, message: discord.Message) -> bool:
        if INVITE_REGEX.search(message.content):
            await self._registrar_violacao(message, "links de convite não são permitidos aqui.")
            return True
        return False

    async def _checar_spam(self, message: discord.Message):
        chave = (message.guild.id, message.author.id)
        agora = time.time()
        historico = self.spam_tracker[chave]
        historico.append(agora)
        # descarta mensagens antigas, fora da janela de tempo observada
        historico[:] = [t for t in historico if agora - t <= SPAM_TIME_WINDOW]

        if len(historico) >= SPAM_MESSAGE_LIMIT:
            self.spam_tracker[chave] = []
            try:
                await message.channel.purge(limit=20, check=lambda m: m.author.id == message.author.id)
            except discord.Forbidden:
                pass
            await self._registrar_violacao(message, "envio de mensagens em excesso (flood).", apagar=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(AutoMod(bot))
