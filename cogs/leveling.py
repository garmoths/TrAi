import discord
from discord.ext import commands
import json
import random
import os
# DÜZELTME: 'Load' yerine 'load_image_async'
from easy_pil import Editor, Canvas, Font, load_image_async

LEVELS_FILE = "levels.json"
SETTINGS_FILE = "settings.json"


class Leveling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def sistem_acik_mi(self, guild_id):
        if not os.path.exists(SETTINGS_FILE): return False
        with open(SETTINGS_FILE, "r") as f:
            data = json.load(f)
        return data.get(str(guild_id), {}).get("level_sistemi", False)

    def xp_islemleri(self, guild_id, user_id):
        if not os.path.exists(LEVELS_FILE):
            data = {}
        else:
            with open(LEVELS_FILE, "r") as f:
                data = json.load(f)

        if guild_id not in data: data[guild_id] = {}
        if user_id not in data[guild_id]: data[guild_id][user_id] = {"xp": 0, "level": 1}

        return data

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild: return
        if not self.sistem_acik_mi(message.guild.id): return

        guild_id = str(message.guild.id)
        user_id = str(message.author.id)

        data = self.xp_islemleri(guild_id, user_id)
        data[guild_id][user_id]["xp"] += random.randint(10, 20)

        current_xp = data[guild_id][user_id]["xp"]
        current_lvl = data[guild_id][user_id]["level"]
        next_lvl_xp = int(5 * (current_lvl ** 2) + 50 * current_lvl + 100)

        if current_xp >= next_lvl_xp:
            data[guild_id][user_id]["level"] += 1
            await message.channel.send(f"🎉 Helal {message.author.mention}! **Level {current_lvl + 1}** oldun!")

        with open(LEVELS_FILE, "w") as f:
            json.dump(data, f, indent=4)

    @commands.command(name="rank", aliases=["seviye"])
    async def rank(self, ctx, member: discord.Member = None):
        if not self.sistem_acik_mi(ctx.guild.id):
            return await ctx.send("❌ Level sistemi kapalı. `!panel`den açın.")

        member = member or ctx.author
        data = self.xp_islemleri(str(ctx.guild.id), str(member.id))

        if str(ctx.guild.id) not in data or str(member.id) not in data[str(ctx.guild.id)]:
            return await ctx.send("Henüz XP kazanmadın.")

        user_data = data[str(ctx.guild.id)][str(member.id)]
        xp = user_data["xp"]
        lvl = user_data["level"]
        next_xp = int(5 * (lvl ** 2) + 50 * lvl + 100)

        background = Editor(Canvas((930, 280), color="#23272a"))
        background.rectangle((20, 20), width=890, height=240, fill="#2c2f33", radius=30)

        try:
            # DÜZELTME BURADA:
            profile_image = await load_image_async(str(member.avatar.url))
            profile = Editor(profile_image).resize((190, 190)).circle_image()
            background.paste(profile, (50, 45))
        except:
            pass

        try:
            font = Font.poppins(size=40, variant="bold")
        except:
            font = None

        background.text((270, 120), f"{member.name}", font=font, color="#ffffff")
        background.text((270, 180), f"Level: {lvl}  |  XP: {xp}/{next_xp}", font=font, color="#00ffcc")

        percentage = min((xp / next_xp) * 100, 100)
        background.bar((270, 230), max_width=600, height=30, percentage=percentage, fill="#00ffcc", radius=20)

        file = discord.File(fp=background.image_bytes, filename="rank.png")
        await ctx.send(file=file)


async def setup(bot):
    await bot.add_cog(Leveling(bot))