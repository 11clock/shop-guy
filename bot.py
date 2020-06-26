#! /usr/bin/python3

import os
import discord
import random
from discord.ext import tasks, commands
from enum import Enum, auto
from asyncio import sleep
from datetime import datetime


class Phase(Enum):
    DAY = auto()
    NIGHT = auto()


TOKEN = "NzIwMTQxNzk4MTcyOTE3Nzkx.XuU7gA.CivIWybJ0Kftp03RJrAy9mKtDGg"
GUILD = "Stick Mafia Neo"

ROLE_HOST_ID = 721480223740133417

ROLE_ALIVE_ID = 720136439894900856
ROLE_DEAD_ID = 720135248200859698

GAME_ROLE_IDS = [
    ROLE_ALIVE_ID,
    ROLE_DEAD_ID
]

GAME_CHANNEL_ID = 725584064094011432

DAY_END_WARNING_HOUR = 2
DAY_END_WARNING_MINUTE = 59

bot = commands.Bot(command_prefix='!')

players = []

phase = Phase.NIGHT


class Player:
    def __init__(self, member: discord.Member):
        self.member_id = member.id
        self.vote_id = None

    def get_member(self) -> discord.Member:
        return get_guild().get_member(self.member_id)

    def get_vote_member(self):
        return get_guild().get_member(self.vote_id)

    def get_vote_count(self):
        return list(map(lambda p: p.vote_id, players)).count(self.member_id)

    def get_display(self):
        return self.get_member().display_name

    def get_vote_display(self):
        if self.vote_id is not None:
            return f"{self.get_display()}: {self.get_vote_member().display_name}"
        else:
            return f"{self.get_display()}:"


class DayEndCog(commands.Cog):
    def __init__(self):
        self.stopping_day = False
        self.check_phase.start()

    def cog_unload(self):
        pass

    @tasks.loop(seconds=1)
    async def check_phase(self):
        if self.stopping_day or phase != Phase.DAY:
            return

        current_time = datetime.utcnow()
        if current_time.hour == DAY_END_WARNING_HOUR and current_time.minute == DAY_END_WARNING_MINUTE:
            self.stopping_day = True
            await get_guild().get_channel(GAME_CHANNEL_ID).send(wrap("THE DAY IS ENDING IN TWO MINUTES!!!"))
            await sleep(120)
            await start_lynch()
            self.stopping_day = False


def get_guild() -> discord.Guild:
    return discord.utils.get(bot.guilds, name=GUILD)


def get_game_roles():
    return list(filter(lambda r: r.id in GAME_ROLE_IDS, get_guild().roles))


def find_player(member: discord.Member):
    return discord.utils.get(players, member_id=member.id)


def wrap(message: str):
    return f"```{message}```"


async def change_phase(new_phase: Phase):
    global phase
    phase = new_phase

    guild = get_guild()
    game_channel: discord.TextChannel = guild.get_channel(GAME_CHANNEL_ID)
    alive_role = guild.get_role(ROLE_ALIVE_ID)

    if phase == Phase.DAY:
        await game_channel.set_permissions(alive_role,
                                           read_messages=True,
                                           send_messages=True,
                                           send_tts_messages=True,
                                           embed_links=True,
                                           attach_files=True,
                                           read_message_history=True,
                                           use_external_emojis=True,
                                           add_reactions=True)
    elif phase == Phase.NIGHT:
        await game_channel.set_permissions(alive_role,
                                           read_messages=None,
                                           send_messages=None,
                                           send_tts_messages=None,
                                           embed_links=None,
                                           attach_files=None,
                                           read_message_history=None,
                                           use_external_emojis=None,
                                           add_reactions=None)


async def start_lynch():
    await change_phase(Phase.NIGHT)

    channel = get_guild().get_channel(GAME_CHANNEL_ID)

    highest_vote_count = 0

    for player in players:
        highest_vote_count = max(highest_vote_count, player.get_vote_count())

    highest_voted_players = list(filter(lambda p: p.get_vote_count() == highest_vote_count, players))

    highest_voted_string = ", ".join(list(map(lambda p: p.get_display(), highest_voted_players)))

    await channel.send(wrap(f"Verdict: {highest_voted_string}"))

    player_to_lynch = None

    if len(highest_voted_players) == 1:
        player_to_lynch = highest_voted_players[0]
    elif len(highest_voted_players) > 1:
        await channel.send(wrap(f"We have a tie! Give me a minute to find my coin..."))
        await sleep(60)
        player_to_lynch = random.choice(highest_voted_players)

    if player_to_lynch is not None:
        await kill(player_to_lynch)
        await channel.send(wrap(f"{player_to_lynch.get_display()} was lynched! Give the host a moment to post the reveal!"))
    else:
        await channel.send(wrap(f"There was no one to lynch!"))


async def kill(player: Player):
    guild = get_guild()
    alive_role = guild.get_role(ROLE_ALIVE_ID)
    dead_role = guild.get_role(ROLE_DEAD_ID)

    player_member = player.get_member()
    await player_member.remove_roles(alive_role)
    await player_member.add_roles(dead_role)

    players.remove(player)
    for player in players:
        player.vote_id = None


@bot.event
async def on_ready():
    guild = get_guild()

    print(
        f'{bot.user} is connected to the following guild:\n'
        f'{guild.name} (id: {guild.id})'
    )

    print("Guild Members:")
    for member in guild.members:
        print(f' - {member.display_name}')

    await change_phase(Phase.NIGHT)

    bot.add_cog(DayEndCog())


@bot.event
async def on_command_error(ctx, error):
    if ctx.message is not None:
        await ctx.message.add_reaction("❌")


@bot.command(name='add_players')
@commands.has_role(ROLE_HOST_ID)
async def add_players(ctx, *members: discord.Member):
    guild = get_guild()
    for member in members:
        if find_player(member) is None:
            players.append(Player(member))
            await member.add_roles(guild.get_role(ROLE_ALIVE_ID))

    await display_players(ctx)


@bot.command(name='clear_players')
@commands.has_role(ROLE_HOST_ID)
async def clear_players(ctx):
    guild = get_guild()
    for player in players:
        await player.get_member().remove_roles(guild.get_role(ROLE_ALIVE_ID))

    players.clear()

    await display_players(ctx)


@bot.command(name='day')
@commands.has_role(ROLE_HOST_ID)
async def change_to_day(ctx):
    await change_phase(Phase.DAY)
    await ctx.send(wrap("It's day time! Discuss and vote using the vote command!"))


@bot.command(name='night')
@commands.has_role(ROLE_HOST_ID)
async def change_to_night(ctx):
    await change_phase(Phase.NIGHT)
    await ctx.send(wrap("It's night time! Power roles, DM the host your night actions!"))


@bot.command(name='vote')
@commands.has_role(ROLE_ALIVE_ID)
async def cast_vote(ctx, vote: discord.Member):
    if phase == Phase.NIGHT:
        await ctx.send(wrap("It's night time! Go to sleep!"))
    elif ctx.channel.id != GAME_CHANNEL_ID:
        await ctx.send(wrap("You can only vote in #current-game!"))
    else:
        await cast_modvote(ctx, ctx.author, vote)


@bot.command(name='unvote')
@commands.has_role(ROLE_ALIVE_ID)
async def cast_unvote(ctx):
    if phase == Phase.NIGHT:
        await ctx.send(wrap("It's night time! Go to sleep!"))
    elif ctx.channel.id != GAME_CHANNEL_ID:
        await ctx.send(wrap("You can only unvote in #current-game!"))
    else:
        await cast_modunvote(ctx, ctx.author)


@bot.command(name='modvote')
@commands.has_role(ROLE_HOST_ID)
async def cast_modvote(ctx, voter: discord.Member, vote: discord.Member):
    voter_player: Player = find_player(voter)
    voted_player: Player = find_player(vote)

    if voted_player is not None:
        voter_player.vote_id = voted_player.member_id
        await ctx.message.add_reaction("✅")
    else:
        await ctx.send(wrap("That member is not currently in the game!"))


@bot.command(name='modunvote')
@commands.has_role(ROLE_HOST_ID)
async def cast_modunvote(ctx, voter: discord.Member):
    voter_player: Player = find_player(voter)
    voter_player.vote_id = None
    await ctx.message.add_reaction("✅")


@bot.command(name="lynch")
@commands.has_role(ROLE_HOST_ID)
async def force_lynch(ctx):
    await start_lynch()


@bot.command(name="kill")
@commands.has_role(ROLE_HOST_ID)
async def modkill(ctx, target: discord.Member):
    target_player = find_player(target)
    if target_player is not None:
        await kill(target_player)
        await ctx.message.add_reaction("✅")
    else:
        await ctx.message.add_reaction("❌")


@bot.command(name='players')
async def display_players(ctx):
    message = "Current Players:"

    for player in players:
        message += f"\n - {player.get_display()}"

    await ctx.send(wrap(message))


@bot.command(name='votes')
async def display_votes(ctx):
    message = "Current Votes:"

    for player in players:
        message += f"\n - {player.get_vote_display()}"

    vote_tally = "Vote Tally:"

    players_to_review = players.copy()
    while len(players_to_review) > 0:
        highest_vote_count = 0

        for player in players_to_review:
            highest_vote_count = max(highest_vote_count, player.get_vote_count())

        highest_voted_players = list(filter(lambda p: p.get_vote_count() == highest_vote_count, players))
        highest_voted_string = ", ".join(list(map(lambda p: p.get_display(), highest_voted_players)))

        vote_tally += f"\n - {highest_vote_count} Votes: {highest_voted_string}"

        for player in highest_voted_players:
            players_to_review.remove(player)

    await ctx.send(f"{wrap(message)}{wrap(vote_tally)}")


bot.run(TOKEN)
