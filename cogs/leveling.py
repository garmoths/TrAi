import discord
from discord import app_commands
from discord.ext import commands
import json
import random
import os
from utils.helpers import safe_load_json
from utils import db
# easy_pil (optional)
try:
    from easy_pil import Editor, Canvas, Font, load_image_async
    HAS_EASY_PIL = True
except ImportError:
    HAS_EASY_PIL = False
from utils.logger import get_logger

LEVELS_FILE = "levels.json"
SETTINGS_FILE = "settings.json"


class Leveling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = get_logger(__name__)

    def sistem_acik_mi(self, guild_id):
        data = safe_load_json(SETTINGS_FILE, {})
        return data.get(str(guild_id), {}).get("level_sistemi", False)

    def xp_islemleri(self, guild_id, user_id):
        # Use SQLite-backed key/value store for levels (prototype)
        data = db.kv_get("levels", {}) or {}

        if guild_id not in data:
            data[guild_id] = {}
        if user_id not in data[guild_id]:
            data[guild_id][user_id] = {"xp": 0, "level": 1}

        return data

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild: return
        if not self.sistem_acik_mi(message.guild.id): return

        guild_id = str(message.guild.id)
        user_id = str(message.author.id)

        data = self.xp_islemleri(guild_id, user_id)
        data[guild_id][user_id]["xp"] += random.randint(5, 12)

        current_xp = data[guild_id][user_id]["xp"]
        current_lvl = data[guild_id][user_id]["level"]
        next_lvl_xp = int(25 * (current_lvl ** 2) + 100 * current_lvl + 150)

        if current_xp >= next_lvl_xp:
            data[guild_id][user_id]["level"] += 1
            # 3. seviye ve sonrası için ara mesaj ver; daha düşük seviyelerde sessiz geçiş
            if data[guild_id][user_id]["level"] % 3 == 0:
                await message.channel.send(f"🎉 Tebrikler {message.author.mention}! **Level {current_lvl + 1}** oldun!")

        # Persist to SQLite store
        db.kv_set("levels", data)

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
        next_xp = int(25 * (lvl ** 2) + 100 * lvl + 150)

        background = Editor(Canvas((930, 280), color="#23272a"))
        background.rectangle((20, 20), width=890, height=240, fill="#2c2f33", radius=30)

        try:
            # DÜZELTME BURADA:
            profile_image = await load_image_async(str(member.avatar.url))
            profile = Editor(profile_image).resize((190, 190)).circle_image()
            background.paste(profile, (50, 45))
        except Exception as e:
            self.logger.debug("Failed to load/paste profile image for rank card: %s", e)

        try:
            font = Font.poppins(size=40, variant="bold")
        except Exception as e:
            self.logger.debug("Failed to load font for rank card: %s", e)
            font = None

        background.text((270, 120), f"{member.name}", font=font, color="#ffffff")
        background.text((270, 180), f"Level: {lvl}  |  XP: {xp}/{next_xp}", font=font, color="#00ffcc")

        percentage = min((xp / next_xp) * 100, 100)
        background.bar((270, 230), max_width=600, height=30, percentage=percentage, fill="#00ffcc", radius=20)

        file = discord.File(fp=background.image_bytes, filename="rank.png")
        await ctx.send(file=file)

    # =========================================================================
    # SLASH KOMUTLAR
    # =========================================================================

    @app_commands.command(name="level", description="📊 Seviyeni ve XP'ni gösterir")
    @app_commands.describe(kullanıcı="Seviyesi görüntülenecek kullanıcı (boş bırakılırsa kendin)")
    async def level_slash(self, interaction: discord.Interaction, kullanıcı: discord.Member = None):
        """Slash komut ile level kartı gösterir."""
        member = kullanıcı or interaction.user
        
        if not self.sistem_acik_mi(interaction.guild.id):
            await interaction.response.send_message("❌ Level sistemi bu sunucuda kapalı.", ephemeral=True)
            return

        data = db.kv_get("levels", {}) or {}
        if str(interaction.guild.id) not in data or str(member.id) not in data[str(interaction.guild.id)]:
            await interaction.response.send_message("❌ Henüz XP kazanmadın.", ephemeral=True)
            return

        await interaction.response.defer()

        user_data = data[str(interaction.guild.id)][str(member.id)]
        xp = user_data["xp"]
        lvl = user_data["level"]
        next_xp = int(25 * (lvl ** 2) + 100 * lvl + 150)

        background = Editor(Canvas((930, 280), color="#23272a"))
        background.rectangle((20, 20), width=890, height=240, fill="#2c2f33", radius=30)

        try:
            profile_image = await load_image_async(str(member.avatar.url))
            profile = Editor(profile_image).resize((190, 190)).circle_image()
            background.paste(profile, (50, 45))
        except Exception as e:
            self.logger.debug("Failed to load/paste profile image for rank card: %s", e)

        try:
            font = Font.poppins(size=40, variant="bold")
        except Exception as e:
            self.logger.debug("Failed to load font for rank card: %s", e)
            font = None

        background.text((270, 120), f"{member.name}", font=font, color="#ffffff")
        background.text((270, 180), f"Level: {lvl}  |  XP: {xp}/{next_xp}", font=font, color="#00ffcc")

        percentage = min((xp / next_xp) * 100, 100)
        background.bar((270, 230), max_width=600, height=30, percentage=percentage, fill="#00ffcc", radius=20)

        file = discord.File(fp=background.image_bytes, filename="rank.png")
        await interaction.followup.send(file=file)

    @app_commands.command(name="lider-tablosu", description="🏆 Sunucudaki en yüksek seviyeleri gösterir")
    async def lider_tablosu_slash(self, interaction: discord.Interaction):
        """Leaderboard gösterir."""
        if not self.sistem_acik_mi(interaction.guild.id):
            await interaction.response.send_message("❌ Level sistemi bu sunucuda kapalı.", ephemeral=True)
            return

        data = db.kv_get("levels", {}) or {}
        if str(interaction.guild.id) not in data:
            await interaction.response.send_message("❌ Henüz kimse XP kazanmamış.", ephemeral=True)
            return

        guild_data = data[str(interaction.guild.id)]
        sorted_users = sorted(guild_data.items(), key=lambda x: (x[1]["level"], x[1]["xp"]), reverse=True)[:10]

        embed = discord.Embed(
            title=f"🏆 {interaction.guild.name} - Lider Tablosu",
            description="En yüksek seviyeli 10 kullanıcı:",
            color=discord.Color.gold()
        )

        medals = ["🥇", "🥈", "🥉"]
        for idx, (user_id, user_data) in enumerate(sorted_users, start=1):
            medal = medals[idx - 1] if idx <= 3 else f"**{idx}.**"
            lvl = user_data["level"]
            xp = user_data["xp"]
            embed.add_field(
                name=f"{medal} Level {lvl}",
                value=f"<@{user_id}> - {xp} XP",
                inline=False
            )

        embed.set_footer(text=f"İsteyen: {interaction.user.name}")
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Leveling(bot))