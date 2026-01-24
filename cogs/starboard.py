import discord
from discord import app_commands
from discord.ext import commands
from utils.logger import get_logger
from utils import db


class Starboard(commands.Cog):
    """Starboard sistemi - Popüler mesajları özel kanala pinler."""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = get_logger(__name__)
    
    def get_starboard_settings(self, guild_id):
        """Starboard ayarlarını getirir."""
        settings = db.kv_get("settings", {}) or {}
        guild_settings = settings.get(str(guild_id), {})
        
        return {
            "enabled": guild_settings.get("starboard_enabled", False),
            "channel_id": guild_settings.get("starboard_channel"),
            "threshold": guild_settings.get("starboard_threshold", 3),
            "emoji": guild_settings.get("starboard_emoji", "⭐"),
            "self_star": guild_settings.get("starboard_self_star", False),
            "ignore_channels": guild_settings.get("starboard_ignore", []),
        }
    
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        """Reaction eklendiğinde starboard kontrolü."""
        if payload.member.bot:
            return
        
        settings = self.get_starboard_settings(payload.guild_id)
        
        if not settings["enabled"] or not settings["channel_id"]:
            return
        
        if str(payload.emoji) != settings["emoji"]:
            return
        
        if payload.channel_id in settings["ignore_channels"]:
            return
        
        guild = self.bot.get_guild(payload.guild_id)
        channel = guild.get_channel(payload.channel_id)
        
        try:
            message = await channel.fetch_message(payload.message_id)
        except:
            return
        
        # Self-star kontrolü
        if not settings["self_star"] and message.author.id == payload.user_id:
            return
        
        # Reaction sayısını kontrol et
        star_count = 0
        for reaction in message.reactions:
            if str(reaction.emoji) == settings["emoji"]:
                star_count = reaction.count
                break
        
        if star_count < settings["threshold"]:
            return
        
        # Starboard kanalını al
        starboard_channel = guild.get_channel(settings["channel_id"])
        if not starboard_channel:
            return
        
        # Daha önce eklenmiş mi kontrol et
        starboard_data = db.kv_get("starboard_messages", {}) or {}
        message_key = f"{payload.guild_id}_{payload.message_id}"
        
        if message_key in starboard_data:
            # Mesajı güncelle
            try:
                starboard_msg = await starboard_channel.fetch_message(starboard_data[message_key])
                embed = starboard_msg.embeds[0]
                embed.set_footer(text=f"{settings['emoji']} {star_count} | Mesaj ID: {message.id}")
                await starboard_msg.edit(embed=embed)
            except:
                pass
            return
        
        # Yeni starboard mesajı oluştur
        embed = discord.Embed(
            description=message.content or "*Medya mesajı*",
            color=discord.Color.gold(),
            timestamp=message.created_at
        )
        embed.set_author(
            name=message.author.display_name,
            icon_url=message.author.display_avatar.url
        )
        embed.add_field(
            name="Kaynak",
            value=f"[Mesaja Git]({message.jump_url}) | <#{channel.id}>",
            inline=False
        )
        
        # Resim varsa ekle
        if message.attachments:
            embed.set_image(url=message.attachments[0].url)
        
        embed.set_footer(text=f"{settings['emoji']} {star_count} | Mesaj ID: {message.id}")
        
        starboard_msg = await starboard_channel.send(embed=embed)
        
        # Veritabanına kaydet
        starboard_data[message_key] = starboard_msg.id
        db.kv_set("starboard_messages", starboard_data)
    
    @app_commands.command(name="starboard-kur", description="⭐ Starboard'u kurar")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(
        kanal="Starboard kanalı",
        eşik="Kaç yıldız gerekli (varsayılan: 3)",
        emoji="Kullanılacak emoji (varsayılan: ⭐)"
    )
    async def starboard_kur(
        self,
        interaction: discord.Interaction,
        kanal: discord.TextChannel,
        eşik: int = 3,
        emoji: str = "⭐"
    ):
        """Starboard'u kurar."""
        settings = db.kv_get("settings", {}) or {}
        
        if str(interaction.guild.id) not in settings:
            settings[str(interaction.guild.id)] = {}
        
        settings[str(interaction.guild.id)]["starboard_enabled"] = True
        settings[str(interaction.guild.id)]["starboard_channel"] = kanal.id
        settings[str(interaction.guild.id)]["starboard_threshold"] = eşik
        settings[str(interaction.guild.id)]["starboard_emoji"] = emoji
        db.kv_set("settings", settings)
        
        await interaction.response.send_message(
            f"⭐ **Starboard kuruldu!**\n"
            f"📍 Kanal: {kanal.mention}\n"
            f"🔢 Eşik: {eşik} {emoji}\n"
            f"✨ Popüler mesajlar otomatik olarak starboard'a eklenecek!"
        )
    
    @app_commands.command(name="starboard", description="⚙️ Starboard'u aç/kapat")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(durum="Açık/Kapalı")
    async def starboard_toggle(self, interaction: discord.Interaction, durum: bool):
        """Starboard'u açar/kapatır."""
        settings = db.kv_get("settings", {}) or {}
        
        if str(interaction.guild.id) not in settings:
            settings[str(interaction.guild.id)] = {}
        
        settings[str(interaction.guild.id)]["starboard_enabled"] = durum
        db.kv_set("settings", settings)
        
        status = "**açıldı** ✅" if durum else "**kapatıldı** ❌"
        await interaction.response.send_message(f"⭐ Starboard {status}")


async def setup(bot):
    await bot.add_cog(Starboard(bot))
