"""
database.py
Camada de acesso ao banco de dados SQLite do bot.

Usamos aiosqlite (em vez do módulo sqlite3 padrão) porque ele é assíncrono:
cada operação usa "await", o que evita travar o loop de eventos do discord.py
enquanto o bot espera o disco responder. Isso é importante mesmo em um banco
pequeno, porque o bot está lidando com vários eventos do Discord ao mesmo tempo.
"""

from datetime import datetime, timezone

import aiosqlite

DB_PATH = "moderation.db"


async def init_db():
    """Cria as tabelas do banco caso ainda não existam. Chamada uma vez, quando o bot inicia."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS warnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                moderator_id INTEGER NOT NULL,
                reason TEXT,
                timestamp TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS guild_config (
                guild_id INTEGER PRIMARY KEY,
                mod_log_channel_id INTEGER,
                automod_enabled INTEGER NOT NULL DEFAULT 1,
                block_invites INTEGER NOT NULL DEFAULT 1,
                max_warnings INTEGER NOT NULL DEFAULT 3
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS filtered_words (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                word TEXT NOT NULL
            )
        """)
        await db.commit()


# ---------- Advertências (warnings) ----------

async def add_warning(guild_id: int, user_id: int, moderator_id: int, reason: str) -> int:
    timestamp = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO warnings (guild_id, user_id, moderator_id, reason, timestamp) VALUES (?, ?, ?, ?, ?)",
            (guild_id, user_id, moderator_id, reason, timestamp),
        )
        await db.commit()
        return cursor.lastrowid


async def get_warnings(guild_id: int, user_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM warnings WHERE guild_id = ? AND user_id = ? ORDER BY timestamp DESC",
            (guild_id, user_id),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def clear_warnings(guild_id: int, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM warnings WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
        await db.commit()


# ---------- Configuração por servidor ----------

async def get_guild_config(guild_id: int) -> dict:
    """Busca a config do servidor. Se ainda não existir, cria uma linha com os valores padrão."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM guild_config WHERE guild_id = ?", (guild_id,))
        row = await cursor.fetchone()
        if row is None:
            await db.execute("INSERT INTO guild_config (guild_id) VALUES (?)", (guild_id,))
            await db.commit()
            cursor = await db.execute("SELECT * FROM guild_config WHERE guild_id = ?", (guild_id,))
            row = await cursor.fetchone()
        return dict(row)


async def set_mod_log_channel(guild_id: int, channel_id: int):
    await get_guild_config(guild_id)  # garante que a linha já existe
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE guild_config SET mod_log_channel_id = ? WHERE guild_id = ?", (channel_id, guild_id))
        await db.commit()


async def set_automod_enabled(guild_id: int, enabled: bool):
    await get_guild_config(guild_id)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE guild_config SET automod_enabled = ? WHERE guild_id = ?", (int(enabled), guild_id))
        await db.commit()


async def set_block_invites(guild_id: int, enabled: bool):
    await get_guild_config(guild_id)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE guild_config SET block_invites = ? WHERE guild_id = ?", (int(enabled), guild_id))
        await db.commit()


async def set_max_warnings(guild_id: int, amount: int):
    await get_guild_config(guild_id)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE guild_config SET max_warnings = ? WHERE guild_id = ?", (amount, guild_id))
        await db.commit()


# ---------- Palavras filtradas ----------

async def add_filtered_word(guild_id: int, word: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO filtered_words (guild_id, word) VALUES (?, ?)", (guild_id, word.lower()))
        await db.commit()


async def remove_filtered_word(guild_id: int, word: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM filtered_words WHERE guild_id = ? AND word = ?", (guild_id, word.lower())
        )
        await db.commit()
        return cursor.rowcount > 0


async def get_filtered_words(guild_id: int) -> list[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT word FROM filtered_words WHERE guild_id = ?", (guild_id,))
        rows = await cursor.fetchall()
        return [row[0] for row in rows]
