"""
cogs/settings.py
Comandos de configuração do bot, restritos a administradores: canal de log,
lista de palavras filtradas, ativar/desativar automod e limite de advertências.
"""

import discord
from discord import app_commands
from discord.ext import commands

import database


class Settings(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_check(self, ctx: commands.Context) -> bool:
        if ctx.guild is None:
            raise commands.NoPrivateMessage("Esse comando só pode ser usado em servidores.")
        return True

    @commands.hybrid_command(name="setmodlog", description="Define o canal de log de moderação.")
    @app_commands.describe(canal="Canal onde as ações de moderação serão registradas")
    @commands.has_permissions(administrator=True)
    async def setmodlog(self, ctx: commands.Context, canal: discord.TextChannel):
        await database.set_mod_log_channel(ctx.guild.id, canal.id)
        await ctx.send(f"✅ Canal de log definido para {canal.mention}.")

    @commands.hybrid_command(name="automod", description="Ativa ou desativa o sistema de automod.")
    @app_commands.describe(ativado="True para ativar, False para desativar")
    @commands.has_permissions(administrator=True)
    async def automod_toggle(self, ctx: commands.Context, ativado: bool):
        await database.set_automod_enabled(ctx.guild.id, ativado)
        estado = "ativado" if ativado else "desativado"
        await ctx.send(f"✅ AutoMod {estado}.")

    @commands.hybrid_command(name="blockinvites", description="Ativa ou desativa o bloqueio de links de convite.")
    @app_commands.describe(ativado="True para bloquear, False para permitir")
    @commands.has_permissions(administrator=True)
    async def blockinvites(self, ctx: commands.Context, ativado: bool):
        await database.set_block_invites(ctx.guild.id, ativado)
        estado = "ativado" if ativado else "desativado"
        await ctx.send(f"✅ Bloqueio de convites {estado}.")

    @commands.hybrid_command(name="setmaxwarnings", description="Define quantas advertências acionam ação automática.")
    @app_commands.describe(quantidade="Número de advertências até a ação automática")
    @commands.has_permissions(administrator=True)
    async def setmaxwarnings(self, ctx: commands.Context, quantidade: app_commands.Range[int, 1, 20]):
        await database.set_max_warnings(ctx.guild.id, quantidade)
        await ctx.send(f"✅ Limite de advertências definido para {quantidade}.")

    @commands.hybrid_command(name="addword", description="Adiciona uma palavra à lista de proibidas.")
    @app_commands.describe(palavra="Palavra a ser filtrada")
    @commands.has_permissions(administrator=True)
    async def addword(self, ctx: commands.Context, palavra: str):
        await database.add_filtered_word(ctx.guild.id, palavra)
        await ctx.send("✅ Palavra adicionada à lista de filtradas.", ephemeral=True)

    @commands.hybrid_command(name="removeword", description="Remove uma palavra da lista de proibidas.")
    @app_commands.describe(palavra="Palavra a ser removida do filtro")
    @commands.has_permissions(administrator=True)
    async def removeword(self, ctx: commands.Context, palavra: str):
        removida = await database.remove_filtered_word(ctx.guild.id, palavra)
        if removida:
            await ctx.send("✅ Palavra removida da lista de filtradas.", ephemeral=True)
        else:
            await ctx.send("❌ Essa palavra não estava na lista.", ephemeral=True)

    @commands.hybrid_command(name="listwords", description="Mostra a lista de palavras filtradas.")
    @commands.has_permissions(administrator=True)
    async def listwords(self, ctx: commands.Context):
        palavras = await database.get_filtered_words(ctx.guild.id)
        if not palavras:
            texto = "A lista de palavras filtradas está vazia."
        else:
            texto = "Palavras filtradas: " + ", ".join(f"`{p}`" for p in palavras)
        await ctx.send(texto, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Settings(bot))
