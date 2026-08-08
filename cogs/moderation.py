"""
cogs/moderation.py
Comandos principais de moderação: kick, ban, unban, timeout, warn, clear,
lock/unlock e slowmode.

Todos os comandos são "hybrid commands": funcionam tanto como comando de
barra (/kick) quanto como comando prefixado (!kick), com o mesmo código.
"""

from datetime import datetime, timedelta, timezone
import re

import discord
from discord import app_commands
from discord.ext import commands

import database


def parse_duration(duration_str: str) -> timedelta | None:
    """Converte strings como '10m', '2h', '1d' em um timedelta. Retorna None se o formato for inválido."""
    match = re.match(r"^(\d+)\s*([smhd])$", duration_str.strip().lower())
    if not match:
        return None
    amount, unit = match.groups()
    unidades = {"s": "seconds", "m": "minutes", "h": "hours", "d": "days"}
    return timedelta(**{unidades[unit]: int(amount)})


def check_hierarchy(moderador: discord.Member, alvo: discord.Member) -> tuple[bool, str]:
    """Verifica se `moderador` pode agir sobre `alvo`, respeitando a hierarquia de cargos."""
    if alvo.id == moderador.id:
        return False, "Você não pode usar esse comando em si mesmo."
    if alvo.id == moderador.guild.owner_id:
        return False, "Você não pode moderar o dono do servidor."
    if moderador.id != moderador.guild.owner_id and alvo.top_role >= moderador.top_role:
        return False, "Você não pode moderar alguém com cargo igual ou superior ao seu."
    return True, ""


def check_bot_can_act(bot_membro: discord.Member, alvo: discord.Member) -> tuple[bool, str]:
    """O Discord exige que o cargo do BOT também esteja acima do cargo do alvo."""
    if alvo.top_role >= bot_membro.top_role:
        return False, "Meu cargo precisa estar acima do cargo desse membro para eu poder fazer isso."
    return True, ""


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_check(self, ctx: commands.Context) -> bool:
        # Esse check roda antes de QUALQUER comando deste Cog (prefixado ou de barra).
        if ctx.guild is None:
            raise commands.NoPrivateMessage("Esse comando só pode ser usado em servidores.")
        return True

    # ---------- Funções auxiliares ----------

    async def log_action(self, guild: discord.Guild, acao: str, alvo, moderador, motivo: str):
        """Envia um embed para o canal de log configurado (se houver um definido com /setmodlog)."""
        config = await database.get_guild_config(guild.id)
        canal_id = config.get("mod_log_channel_id")
        if not canal_id:
            return
        canal = guild.get_channel(canal_id)
        if canal is None:
            return

        embed = discord.Embed(title=f"🛡️ {acao}", color=discord.Color.orange(), timestamp=datetime.now(timezone.utc))
        embed.add_field(name="Usuário", value=getattr(alvo, "mention", str(alvo)), inline=True)
        embed.add_field(name="Responsável", value=getattr(moderador, "mention", str(moderador)), inline=True)
        embed.add_field(name="Motivo", value=motivo or "Não especificado", inline=False)
        try:
            await canal.send(embed=embed)
        except discord.Forbidden:
            pass

    async def dm_usuario(self, membro: discord.Member, acao: str, motivo: str, guild_nome: str):
        """Tenta avisar o usuário por DM. Se ele tiver DMs fechadas, apenas ignora o erro."""
        try:
            embed = discord.Embed(
                title=f"Você recebeu uma ação de moderação em {guild_nome}",
                description=f"**Ação:** {acao}\n**Motivo:** {motivo or 'Não especificado'}",
                color=discord.Color.red(),
            )
            await membro.send(embed=embed)
        except (discord.Forbidden, discord.HTTPException):
            pass

    # ---------- Comandos ----------

    @commands.hybrid_command(name="kick", description="Expulsa um membro do servidor.")
    @app_commands.describe(membro="Membro a ser expulso", motivo="Motivo da expulsão")
    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    async def kick(self, ctx: commands.Context, membro: discord.Member, *, motivo: str = "Não especificado"):
        ok, erro = check_hierarchy(ctx.author, membro)
        if not ok:
            return await ctx.send(f"❌ {erro}")
        ok, erro = check_bot_can_act(ctx.guild.me, membro)
        if not ok:
            return await ctx.send(f"❌ {erro}")

        await self.dm_usuario(membro, "Expulsão", motivo, ctx.guild.name)
        await membro.kick(reason=f"{motivo} (por {ctx.author})")

        await ctx.send(embed=discord.Embed(description=f"👢 **{membro}** foi expulso. Motivo: {motivo}", color=discord.Color.orange()))
        await self.log_action(ctx.guild, "Expulsão (kick)", membro, ctx.author, motivo)

    @commands.hybrid_command(name="ban", description="Bane um membro do servidor.")
    @app_commands.describe(membro="Membro a ser banido", apagar_dias="Dias de mensagens para apagar (0-7)", motivo="Motivo do banimento")
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def ban(
        self,
        ctx: commands.Context,
        membro: discord.Member,
        apagar_dias: app_commands.Range[int, 0, 7] = 0,
        *,
        motivo: str = "Não especificado",
    ):
        ok, erro = check_hierarchy(ctx.author, membro)
        if not ok:
            return await ctx.send(f"❌ {erro}")
        ok, erro = check_bot_can_act(ctx.guild.me, membro)
        if not ok:
            return await ctx.send(f"❌ {erro}")

        await self.dm_usuario(membro, "Banimento", motivo, ctx.guild.name)
        # A API do Discord conta a exclusão de mensagens em segundos, não mais em "dias".
        await membro.ban(reason=f"{motivo} (por {ctx.author})", delete_message_seconds=apagar_dias * 86400)

        await ctx.send(embed=discord.Embed(description=f"🔨 **{membro}** foi banido. Motivo: {motivo}", color=discord.Color.red()))
        await self.log_action(ctx.guild, "Banimento (ban)", membro, ctx.author, motivo)

    @commands.hybrid_command(name="unban", description="Remove o banimento de um usuário pelo ID.")
    @app_commands.describe(user_id="ID do usuário a desbanir", motivo="Motivo do desbanimento")
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def unban(self, ctx: commands.Context, user_id: str, *, motivo: str = "Não especificado"):
        try:
            user = await self.bot.fetch_user(int(user_id))
            await ctx.guild.unban(user, reason=f"{motivo} (por {ctx.author})")
        except (ValueError, discord.NotFound):
            return await ctx.send("❌ Não encontrei um banimento com esse ID.")

        await ctx.send(embed=discord.Embed(description=f"✅ **{user}** foi desbanido. Motivo: {motivo}", color=discord.Color.green()))
        await self.log_action(ctx.guild, "Desbanimento (unban)", user, ctx.author, motivo)

    @commands.hybrid_command(name="timeout", description="Silencia um membro por um período (ex: 10m, 2h, 1d).")
    @app_commands.describe(membro="Membro a silenciar", duracao="Duração (ex: 10m, 2h, 1d)", motivo="Motivo")
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    async def timeout(self, ctx: commands.Context, membro: discord.Member, duracao: str, *, motivo: str = "Não especificado"):
        ok, erro = check_hierarchy(ctx.author, membro)
        if not ok:
            return await ctx.send(f"❌ {erro}")
        ok, erro = check_bot_can_act(ctx.guild.me, membro)
        if not ok:
            return await ctx.send(f"❌ {erro}")

        delta = parse_duration(duracao)
        if delta is None:
            return await ctx.send("❌ Duração inválida. Use algo como `10m`, `2h` ou `1d`.")
        if delta > timedelta(days=28):
            return await ctx.send("❌ O Discord permite no máximo 28 dias de timeout.")

        await membro.timeout(delta, reason=f"{motivo} (por {ctx.author})")
        await self.dm_usuario(membro, f"Timeout ({duracao})", motivo, ctx.guild.name)

        await ctx.send(embed=discord.Embed(
            description=f"🔇 **{membro}** foi silenciado por `{duracao}`. Motivo: {motivo}", color=discord.Color.orange()
        ))
        await self.log_action(ctx.guild, f"Timeout ({duracao})", membro, ctx.author, motivo)

    @commands.hybrid_command(name="untimeout", description="Remove o silenciamento de um membro.")
    @app_commands.describe(membro="Membro a remover o timeout")
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    async def untimeout(self, ctx: commands.Context, membro: discord.Member):
        await membro.timeout(None, reason=f"Removido por {ctx.author}")
        await ctx.send(embed=discord.Embed(description=f"🔊 O timeout de **{membro}** foi removido.", color=discord.Color.green()))
        await self.log_action(ctx.guild, "Timeout removido", membro, ctx.author, "-")

    @commands.hybrid_command(name="warn", description="Aplica uma advertência a um membro.")
    @app_commands.describe(membro="Membro a advertir", motivo="Motivo da advertência")
    @commands.has_permissions(moderate_members=True)
    async def warn(self, ctx: commands.Context, membro: discord.Member, *, motivo: str = "Não especificado"):
        ok, erro = check_hierarchy(ctx.author, membro)
        if not ok:
            return await ctx.send(f"❌ {erro}")

        await database.add_warning(ctx.guild.id, membro.id, ctx.author.id, motivo)
        total = len(await database.get_warnings(ctx.guild.id, membro.id))
        config = await database.get_guild_config(ctx.guild.id)

        await self.dm_usuario(membro, "Advertência", motivo, ctx.guild.name)
        await ctx.send(embed=discord.Embed(
            description=f"⚠️ **{membro}** foi advertido ({total}/{config['max_warnings']}). Motivo: {motivo}",
            color=discord.Color.yellow(),
        ))
        await self.log_action(ctx.guild, "Advertência (warn)", membro, ctx.author, motivo)

        # Escalonamento automático: ao atingir o limite configurado, aplica 1h de timeout sozinho.
        if total >= config["max_warnings"]:
            pode_agir, _ = check_bot_can_act(ctx.guild.me, membro)
            if pode_agir:
                try:
                    await membro.timeout(timedelta(hours=1), reason="Limite de advertências atingido")
                    await ctx.send(f"🔇 **{membro}** atingiu o limite de advertências e recebeu 1h de timeout automático.")
                    await self.log_action(ctx.guild, "Timeout automático (limite de warns)", membro, self.bot.user, "Limite de advertências atingido")
                except discord.Forbidden:
                    pass

    @commands.hybrid_command(name="warnings", description="Mostra as advertências de um membro.")
    @app_commands.describe(membro="Membro a consultar")
    @commands.has_permissions(moderate_members=True)
    async def warnings_cmd(self, ctx: commands.Context, membro: discord.Member):
        registros = await database.get_warnings(ctx.guild.id, membro.id)
        if not registros:
            return await ctx.send(f"✅ **{membro}** não tem nenhuma advertência.")

        embed = discord.Embed(title=f"Advertências de {membro}", color=discord.Color.yellow())
        for i, registro in enumerate(registros[:10], start=1):
            embed.add_field(
                name=f"#{i} — {registro['timestamp'][:10]}",
                value=f"Motivo: {registro['reason']}\nModerador: <@{registro['moderator_id']}>",
                inline=False,
            )
        if len(registros) > 10:
            embed.set_footer(text=f"Mostrando as 10 mais recentes de {len(registros)} advertências.")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="clearwarnings", description="Remove todas as advertências de um membro.")
    @app_commands.describe(membro="Membro a limpar advertências")
    @commands.has_permissions(administrator=True)
    async def clearwarnings(self, ctx: commands.Context, membro: discord.Member):
        await database.clear_warnings(ctx.guild.id, membro.id)
        await ctx.send(f"🧹 Advertências de **{membro}** foram limpas.")
        await self.log_action(ctx.guild, "Advertências limpas", membro, ctx.author, "-")

    @commands.hybrid_command(name="clear", description="Apaga mensagens do canal.")
    @app_commands.describe(quantidade="Quantidade de mensagens a apagar (1-100)", membro="Apagar só mensagens desse membro (opcional)")
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def clear(self, ctx: commands.Context, quantidade: app_commands.Range[int, 1, 100], membro: discord.Member = None):
        def checar(m):
            return membro is None or m.author.id == membro.id

        apagadas = await ctx.channel.purge(limit=quantidade, check=checar)
        aviso = await ctx.send(f"🧹 {len(apagadas)} mensagens apagadas.")
        await aviso.delete(delay=5)
        await self.log_action(ctx.guild, "Limpeza de mensagens", membro or ctx.channel, ctx.author, f"{len(apagadas)} mensagens")

    @commands.hybrid_command(name="lock", description="Bloqueia o envio de mensagens no canal.")
    @app_commands.describe(canal="Canal a bloquear (padrão: canal atual)", motivo="Motivo do bloqueio")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def lock(self, ctx: commands.Context, canal: discord.TextChannel = None, *, motivo: str = "Não especificado"):
        canal = canal or ctx.channel
        await canal.set_permissions(ctx.guild.default_role, send_messages=False, reason=motivo)
        await ctx.send(f"🔒 {canal.mention} foi bloqueado. Motivo: {motivo}")
        await self.log_action(ctx.guild, "Canal bloqueado", canal, ctx.author, motivo)

    @commands.hybrid_command(name="unlock", description="Libera o envio de mensagens no canal.")
    @app_commands.describe(canal="Canal a liberar (padrão: canal atual)")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def unlock(self, ctx: commands.Context, canal: discord.TextChannel = None):
        canal = canal or ctx.channel
        await canal.set_permissions(ctx.guild.default_role, send_messages=None)
        await ctx.send(f"🔓 {canal.mention} foi liberado.")
        await self.log_action(ctx.guild, "Canal liberado", canal, ctx.author, "-")

    @commands.hybrid_command(name="slowmode", description="Define o modo lento de um canal, em segundos.")
    @app_commands.describe(segundos="Intervalo em segundos (0 desativa)", canal="Canal (padrão: canal atual)")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def slowmode(self, ctx: commands.Context, segundos: app_commands.Range[int, 0, 21600], canal: discord.TextChannel = None):
        canal = canal or ctx.channel
        await canal.edit(slowmode_delay=segundos)
        if segundos == 0:
            await ctx.send(f"⏱️ Modo lento desativado em {canal.mention}.")
        else:
            await ctx.send(f"⏱️ Modo lento de {segundos}s definido em {canal.mention}.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
