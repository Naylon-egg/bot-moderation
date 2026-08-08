# Bot de Moderação para Discord

Bot completo de moderação feito com discord.py 2.x, com comandos híbridos
(funcionam como `/comando` ou `!comando`), sistema de advertências persistente
em SQLite e moderação automática (AutoMod).

> Requer **Python 3.10+** (o código usa a sintaxe moderna de type hints, tipo `str | None`).

## Funcionalidades

- **Moderação:** kick, ban, unban, timeout, untimeout, warn, warnings,
  clearwarnings, clear (purge), lock, unlock, slowmode
- **AutoMod:** filtro de palavras, bloqueio de menções em massa, bloqueio de
  links de convite, detecção de flood/spam
- **Advertências com escalonamento:** ficam salvas no banco; ao atingir o
  limite configurado, o bot aplica um timeout automático
- **Log de moderação:** toda ação é registrada em um canal configurável
- **Hierarquia de cargos:** ninguém modera quem tem cargo igual ou superior
  ao seu (nem o dono do servidor) — e o bot também respeita essa regra

## Estrutura do projeto

```
discord-mod-bot/
├── bot.py              # ponto de entrada
├── database.py         # acesso ao SQLite (assíncrono, via aiosqlite)
├── cogs/
│   ├── moderation.py    # comandos de moderação
│   ├── automod.py       # moderação automática
│   └── settings.py      # comandos de configuração (admin)
├── requirements.txt
└── .env.example
```

## Passo a passo

### 1. Criar o bot no Discord Developer Portal
1. Acesse https://discord.com/developers/applications → **New Application**.
2. Vá em **Bot** → **Add Bot**.
3. Em **Privileged Gateway Intents**, ative **Server Members Intent** e
   **Message Content Intent** — sem eles o bot não roda (kick/ban/warn e o
   filtro de palavras dependem disso).
4. Clique em **Reset Token**, copie o token (você só verá ele uma vez).

### 2. Gerar o link de convite
Em **OAuth2 → URL Generator**, marque os escopos `bot` e `applications.commands`.
Nas permissões, marque pelo menos: `Kick Members`, `Ban Members`,
`Moderate Members`, `Manage Messages`, `Manage Channels`, `Read Message History`,
`Send Messages`, `Embed Links`. Copie o link e abra no navegador para convidar
o bot ao seu servidor.

### 3. Instalar as dependências
```bash
pip install -r requirements.txt
```
As dependências foram escolhidas de forma bem enxuta (nada que precise
compilar), pensando em rodar tranquilo no seu servidor caseiro.

### 4. Configurar o `.env`
Copie `.env.example` para `.env` e cole o token:
```
DISCORD_TOKEN=seu_token_aqui
```
`TEST_GUILD_ID` é opcional — coloque o ID do seu servidor ali para os
comandos de barra (`/`) aparecerem instantaneamente durante os testes. Sem
isso, comandos globais podem levar até 1h para propagar.

### 5. Rodar o bot
```bash
python bot.py
```
Na primeira execução, o arquivo `moderation.db` é criado automaticamente com
as tabelas necessárias.

## Lista de comandos

| Comando | Permissão necessária | Descrição |
|---|---|---|
| `/kick <membro> [motivo]` | Kick Members | Expulsa um membro |
| `/ban <membro> [dias] [motivo]` | Ban Members | Bane um membro |
| `/unban <user_id> [motivo]` | Ban Members | Remove um banimento |
| `/timeout <membro> <duração> [motivo]` | Moderate Members | Silencia (ex: `10m`, `2h`, `1d`) |
| `/untimeout <membro>` | Moderate Members | Remove o silenciamento |
| `/warn <membro> [motivo]` | Moderate Members | Aplica advertência |
| `/warnings <membro>` | Moderate Members | Lista advertências |
| `/clearwarnings <membro>` | Administrator | Limpa advertências |
| `/clear <quantidade> [membro]` | Manage Messages | Apaga mensagens |
| `/lock [canal]` | Manage Channels | Bloqueia o canal |
| `/unlock [canal]` | Manage Channels | Libera o canal |
| `/slowmode <segundos> [canal]` | Manage Channels | Define modo lento |
| `/setmodlog <canal>` | Administrator | Define canal de log |
| `/automod <true/false>` | Administrator | Ativa/desativa o AutoMod |
| `/blockinvites <true/false>` | Administrator | Ativa/desativa bloqueio de convites |
| `/setmaxwarnings <quantidade>` | Administrator | Define limite de warns |
| `/addword <palavra>` | Administrator | Adiciona palavra filtrada |
| `/removeword <palavra>` | Administrator | Remove palavra filtrada |
| `/listwords` | Administrator | Lista palavras filtradas |

## Rodando de forma permanente

Para o bot continuar rodando depois de fechar o terminal (e reiniciar sozinho
se cair, ou quando a máquina reiniciar), o caminho mais simples no Linux é
criar um serviço systemd. 


## Notas
- `moderation.db` guarda advertências e configurações por servidor é só um
  arquivo, vale copiar de vez em quando como backup.
- Moderadores (quem tem permissão `Manage Messages`) não são afetados pelo AutoMod.
