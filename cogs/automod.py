import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import time
import datetime
from collections import defaultdict
from utils.logger import get_logger
from utils import db


class AutoMod(commands.Cog):
    """Otomatik moderasyon ve anti-raid sistemi."""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = get_logger(__name__)
        
        self.message_cache = defaultdict(list)  # {user_id: [(message, timestamp), ...]}
        self.spam_violations = defaultdict(int)  # {user_id: violation_count}
        
        self.join_cache = []  # [(user_id, timestamp), ...]
        self.raid_mode = {}  # {guild_id: bool}
        
        self.mention_violations = defaultdict(int)

    def get_automod_settings(self, guild_id):
        """Sunucu automod ayarlarını getirir."""
        settings = db.kv_get("settings", {}) or {}
        guild_settings = settings.get(str(guild_id), {})
        
        return {
            "anti_spam": guild_settings.get("anti_spam", True),
            "spam_threshold": guild_settings.get("spam_threshold", 5),  # 5 mesaj
            "spam_interval": guild_settings.get("spam_interval", 5),    # 5 saniye
            "anti_raid": guild_settings.get("anti_raid", True),
            "raid_threshold": guild_settings.get("raid_threshold", 10),  # 10 kişi
            "raid_interval": guild_settings.get("raid_interval", 10),    # 10 saniye
            "anti_mass_mention": guild_settings.get("anti_mass_mention", True),
            "mention_threshold": guild_settings.get("mention_threshold", 5),  # 5 mention
            "auto_dehoist": guild_settings.get("auto_dehoist", False),  # ! ile başlayan isimler
        }

    @commands.Cog.listener()
    async def on_message(self, message):
        """Anti-spam kontrolü."""
        if message.author.bot or not message.guild:
            return
        
        if message.author.guild_permissions.manage_messages:
            return
        
        settings = self.get_automod_settings(message.guild.id)
        
        if not settings["anti_spam"]:
            return
        
        user_id = message.author.id
        current_time = time.time()
        
        self.message_cache[user_id] = [
            (msg, ts) for msg, ts in self.message_cache[user_id]
            if current_time - ts < settings["spam_interval"]
        ]
        
        self.message_cache[user_id].append((message, current_time))
        
        if len(self.message_cache[user_id]) >= settings["spam_threshold"]:
            self.spam_violations[user_id] += 1
            
            try:
                for msg, _ in self.message_cache[user_id]:
                    try:
                        await msg.delete()
                    except:
                        pass
            except:
                pass
            
            if self.spam_violations[user_id] == 1:
                try:
                    await message.channel.send(
                        f"⚠️ {message.author.mention} Spam yapma! Bu bir uyarı.",
                        delete_after=5
                    )
                except:
                    pass
            elif self.spam_violations[user_id] >= 3:
                try:
                    await message.author.timeout(
                        discord.utils.utcnow() + datetime.timedelta(minutes=10),
                        reason="Otomatik: Spam"
                    )
                    await message.channel.send(
                        f"🔇 {message.author.mention} spam nedeniyle 10 dakika susturuldu.",
                        delete_after=10
                    )
                except:
                    pass
            
            self.message_cache[user_id].clear()
        
        if settings["anti_mass_mention"]:
            mention_count = len(message.mentions)
            if mention_count >= settings["mention_threshold"]:
                self.mention_violations[user_id] += 1
                
                try:
                    await message.delete()
                    await message.channel.send(
                        f"⚠️ {message.author.mention} Aşırı etiketleme yasak!",
                        delete_after=5
                    )
                    
                    if self.mention_violations[user_id] >= 2:
                        await message.author.timeout(
                            discord.utils.utcnow() + datetime.timedelta(minutes=5),
                            reason="Otomatik: Mass mention"
                        )
                except:
                    pass

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Anti-raid kontrolü."""
        settings = self.get_automod_settings(member.guild.id)
        
        if not settings["anti_raid"]:
            return
        
        current_time = time.time()
        
        self.join_cache = [
            (uid, ts) for uid, ts in self.join_cache
            if current_time - ts < settings["raid_interval"]
        ]
        
        self.join_cache.append((member.id, current_time))
        
        if len(self.join_cache) >= settings["raid_threshold"]:
            guild = member.guild
            
            if guild.id not in self.raid_mode or not self.raid_mode[guild.id]:
                self.raid_mode[guild.id] = True
                
                try:
                    await guild.edit(verification_level=discord.VerificationLevel.high)
                except:
                    pass
                
                log_settings = db.kv_get("settings", {}) or {}
                log_channel_id = log_settings.get(str(guild.id), {}).get("log_kanali")
                
                if log_channel_id:
                    log_channel = guild.get_channel(log_channel_id)
                    if log_channel:
                        embed = discord.Embed(
                            title="🚨 RAID TESPİT EDİLDİ!",
                            description=f"{settings['raid_threshold']} kişi {settings['raid_interval']} saniye içinde katıldı!",
                            color=discord.Color.red()
                        )
                        embed.add_field(name="Önlem", value="Doğrulama seviyesi 'Yüksek' olarak ayarlandı.")
                        embed.set_footer(text="Raid Mode: ACTIVE")
                        await log_channel.send(embed=embed)
        
        if settings["auto_dehoist"]:
            if member.display_name.startswith("!") or member.display_name.startswith("?"):
                try:
                    await member.edit(nick="Dehoist", reason="Otomatik: Dehoist")
                except:
                    pass

    @app_commands.command(name="anti-spam", description="🛡️ Anti-spam sistemini açar/kapatır")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(durum="Açık/Kapalı")
    async def anti_spam_slash(self, interaction: discord.Interaction, durum: bool):
        """Anti-spam sistemini ayarlar."""
        settings = db.kv_get("settings", {}) or {}
        
        if str(interaction.guild.id) not in settings:
            settings[str(interaction.guild.id)] = {}
        
        settings[str(interaction.guild.id)]["anti_spam"] = durum
        db.kv_set("settings", settings)
        
        status = "**açıldı** ✅" if durum else "**kapatıldı** ❌"
        await interaction.response.send_message(f"🛡️ Anti-spam sistemi {status}")

    @app_commands.command(name="anti-raid", description="🚨 Anti-raid sistemini açar/kapatır")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(durum="Açık/Kapalı")
    async def anti_raid_slash(self, interaction: discord.Interaction, durum: bool):
        """Anti-raid sistemini ayarlar."""
        settings = db.kv_get("settings", {}) or {}
        
        if str(interaction.guild.id) not in settings:
            settings[str(interaction.guild.id)] = {}
        
        settings[str(interaction.guild.id)]["anti_raid"] = durum
        db.kv_set("settings", settings)
        
        status = "**açıldı** ✅" if durum else "**kapatıldı** ❌"
        await interaction.response.send_message(f"🚨 Anti-raid sistemi {status}")

    @app_commands.command(name="raid-mode", description="🚨 Raid mode'u manuel olarak açar/kapatır")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(durum="Açık/Kapalı")
    async def raid_mode_slash(self, interaction: discord.Interaction, durum: bool):
        """Raid mode'u manuel kontrol."""
        self.raid_mode[interaction.guild.id] = durum
        
        if durum:
            try:
                await interaction.guild.edit(verification_level=discord.VerificationLevel.high)
            except:
                pass
            
            await interaction.response.send_message("🚨 **RAID MODE AKTIF!** Doğrulama seviyesi yükseltildi.")
        else:
            try:
                await interaction.guild.edit(verification_level=discord.VerificationLevel.low)
            except:
                pass
            
            await interaction.response.send_message("✅ Raid mode kapatıldı. Doğrulama seviyesi normale döndü.")

    @app_commands.command(name="spam-ayarları", description="⚙️ Spam tespit ayarlarını düzenler")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        mesaj_sayisi="Kaç mesaj spam sayılır (varsayılan: 5)",
        sure="Kaç saniye içinde (varsayılan: 5)"
    )
    async def spam_ayarlari_slash(self, interaction: discord.Interaction, mesaj_sayisi: int = 5, sure: int = 5):
        """Spam tespit hassasiyetini ayarlar."""
        settings = db.kv_get("settings", {}) or {}
        
        if str(interaction.guild.id) not in settings:
            settings[str(interaction.guild.id)] = {}
        
        settings[str(interaction.guild.id)]["spam_threshold"] = mesaj_sayisi
        settings[str(interaction.guild.id)]["spam_interval"] = sure
        db.kv_set("settings", settings)
        
        await interaction.response.send_message(
            f"⚙️ Spam ayarları güncellendi:\n"
            f"• **{mesaj_sayisi}** mesaj\n"
            f"• **{sure}** saniye içinde"
        )

    @app_commands.command(name="raid-ayarları", description="⚙️ Raid tespit ayarlarını düzenler")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        kisi_sayisi="Kaç kişi raid sayılır (varsayılan: 10)",
        sure="Kaç saniye içinde (varsayılan: 10)"
    )
    async def raid_ayarlari_slash(self, interaction: discord.Interaction, kisi_sayisi: int = 10, sure: int = 10):
        """Raid tespit hassasiyetini ayarlar."""
        settings = db.kv_get("settings", {}) or {}
        
        if str(interaction.guild.id) not in settings:
            settings[str(interaction.guild.id)] = {}
        
        settings[str(interaction.guild.id)]["raid_threshold"] = kisi_sayisi
        settings[str(interaction.guild.id)]["raid_interval"] = sure
        db.kv_set("settings", settings)
        
        await interaction.response.send_message(
            f"⚙️ Raid ayarları güncellendi:\n"
            f"• **{kisi_sayisi}** kişi\n"
            f"• **{sure}** saniye içinde"
        )

    @app_commands.command(name="automod-durum", description="📊 Otomatik moderasyon durumunu gösterir")
    async def automod_durum_slash(self, interaction: discord.Interaction):
        """AutoMod ayarlarını gösterir."""
        settings = self.get_automod_settings(interaction.guild.id)
        
        embed = discord.Embed(
            title="📊 Otomatik Moderasyon Durumu",
            color=discord.Color.blue()
        )
        
        spam_status = "✅ Açık" if settings["anti_spam"] else "❌ Kapalı"
        embed.add_field(
            name="🛡️ Anti-Spam",
            value=f"{spam_status}\n• {settings['spam_threshold']} mesaj / {settings['spam_interval']} saniye",
            inline=True
        )
        
        raid_status = "✅ Açık" if settings["anti_raid"] else "❌ Kapalı"
        raid_mode_active = "🚨 AKTIF" if self.raid_mode.get(interaction.guild.id) else "🟢 Normal"
        embed.add_field(
            name="🚨 Anti-Raid",
            value=f"{raid_status}\n• {settings['raid_threshold']} kişi / {settings['raid_interval']} saniye\n• Mod: {raid_mode_active}",
            inline=True
        )
        
        mention_status = "✅ Açık" if settings["anti_mass_mention"] else "❌ Kapalı"
        embed.add_field(
            name="👥 Anti Mass-Mention",
            value=f"{mention_status}\n• Max {settings['mention_threshold']} mention",
            inline=True
        )
        
        dehoist_status = "✅ Açık" if settings["auto_dehoist"] else "❌ Kapalı"
        embed.add_field(
            name="🔧 Auto-Dehoist",
            value=f"{dehoist_status}\n• ! ve ? ile başlayan isimler düzeltilir",
            inline=True
        )
        
        embed.set_footer(text=f"Sunucu: {interaction.guild.name}")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(AutoMod(bot))
