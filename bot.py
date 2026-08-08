"""
bot.py
Ponto de entrada do bot: carrega configurações, prepara o banco de dados,
registra os Cogs (módulos de comandos) e conecta ao Discord.
"""

import asyncio
import logging
import os

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

import database

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
TEST_GUILD_ID = os.getenv("TEST_GUILD_ID")  # opcional, veja o README

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("bot")

# Intents dizem ao Discord quais eventos o bot quer receber.
intents = discord.Intents.default()
intents.members = True          # necessário para eventos de membro e checar cargos (hierarquia)
intents.message_content = True  # necessário para o AutoMod conseguir ler o texto das mensagens

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    log.info(f"Conectado como {bot.user} (ID: {bot.user.id})")

    if TEST_GUILD_ID:
        # Sincronizar em um servidor específico é instantâneo — ótimo para testar.
        guild = discord.Object(id=int(TEST_GUILD_ID))
        bot.tree.copy_global_to(guild=guild)
        synced = await bot.tree.sync(guild=guild)
        log.info(f"{len(synced)} comandos sincronizados no servidor de testes.")
    else:
        # Sincronização global pode levar até 1h para propagar em todos os servidores.
        synced = await bot.tree.sync()
        log.info(f"{len(synced)} comandos sincronizados globalmente.")

    log.info(f"Bot ativo em {len(bot.guilds)} servidor(es).")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="o servidor 👀"))


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    """Trata erros de comandos (funciona tanto para os prefixados quanto para os híbridos)."""
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Você não tem permissão para usar esse comando.")
    elif isinstance(error, commands.BotMissingPermissions):
        await ctx.send("❌ Não tenho permissão suficiente para fazer isso. Confira meus cargos/permissões.")
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ Não encontrei esse membro no servidor.")
    elif isinstance(error, commands.NoPrivateMessage):
        await ctx.send("❌ Esse comando só funciona dentro de um servidor.")
    elif isinstance(error, commands.CommandNotFound):
        return  # ignora comandos prefixados inexistentes, sem poluir o chat
    else:
        log.exception("Erro em comando", exc_info=error)
        await ctx.send("❌ Ocorreu um erro ao executar esse comando.")


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    """Rede de segurança extra para erros de comandos de barra que não passam pelo handler acima."""
    if isinstance(error, app_commands.MissingPermissions):
        msg = "❌ Você não tem permissão para usar esse comando."
    else:
        log.exception("Erro em app command", exc_info=error)
        msg = "❌ Ocorreu um erro ao executar esse comando."

    if interaction.response.is_done():
        await interaction.followup.send(msg, ephemeral=True)
    else:
        await interaction.response.send_message(msg, ephemeral=True)


async def load_cogs():
    for extensao in ("cogs.moderation", "cogs.automod", "cogs.settings"):
        await bot.load_extension(extensao)
        log.info(f"Cog carregado: {extensao}")


async def main():
    await database.init_db()
    async with bot:
        await load_cogs()
        await bot.start(TOKEN)


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("Defina DISCORD_TOKEN no arquivo .env antes de iniciar o bot.")
    asyncio.run(main())
