import discord
from discord.ext import commands
import datetime
import json
import os

SETTINGS_FILE = "settings.json"


class Logger(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def ayar_getir(self, guild_id):
        if not os.path.exists(SETTINGS_FILE): return {}
        with open(SETTINGS_FILE, "r") as f:
            return json.load(f).get(str(guild_id), {})

    def ayar_kaydet(self, guild_id, kanal_id):
        if not os.path.exists(SETTINGS_FILE):
            data = {}
        else:
            with open(SETTINGS_FILE, "r") as f:
                data = json.load(f)

        if str(guild_id) not in data: data[str(guild_id)] = {}
        data[str(guild_id)]["log_kanali"] = kanal_id

        with open(SETTINGS_FILE, "w") as f:
            json.dump(data, f, indent=4)

    # 🗣️ LOG KANALINI AYARLAMA (Doğal Dil)
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild: return
        # Sadece Yönetici
        if not message.author.guild_permissions.administrator: return
        # Bot etiketlenmeli
        if not self.bot.user.mentioned_in(message): return

        icerik = message.content.lower()

        # Komut: "@TrAI log kanalı burası olsun" veya "kayıtları buraya at"
        if "log" in icerik or "kayıt" in icerik:
            if "burası" in icerik or "kanal" in icerik or "olsun" in icerik:
                self.ayar_kaydet(message.guild.id, message.channel.id)
                await message.channel.send(
                    f"🕵️‍♂️ Anlaşıldı! Bundan sonra sunucuda uçan kuşu bile **{message.channel.mention}** kanalına raporlayacağım.")

    # ------------------ OLAYLAR (EVENTS) ------------------

    # 1. MESAJ SİLİNDİĞİNDE
    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.author.bot: return

        ayarlar = self.ayar_getir(message.guild.id)
        if "log_kanali" not in ayarlar: return

        log_channel = self.bot.get_channel(ayarlar["log_kanali"])
        if not log_channel: return

        embed = discord.Embed(title="🗑️ Mesaj Silindi", color=discord.Color.red())
        embed.add_field(name="Yazan", value=message.author.mention, inline=True)
        embed.add_field(name="Kanal", value=message.channel.mention, inline=True)
        embed.add_field(name="İçerik", value=message.content if message.content else "Resim/Dosya", inline=False)
        embed.set_footer(text=f"ID: {message.author.id}")
        embed.timestamp = datetime.datetime.now()

        await log_channel.send(embed=embed)

    # 2. MESAJ DÜZENLENDİĞİNDE
    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if before.author.bot or before.content == after.content: return

        ayarlar = self.ayar_getir(before.guild.id)
        if "log_kanali" not in ayarlar: return

        log_channel = self.bot.get_channel(ayarlar["log_kanali"])
        if not log_channel: return

        embed = discord.Embed(title="✏️ Mesaj Düzenlendi", color=discord.Color.orange())
        embed.add_field(name="Yazan", value=before.author.mention)
        embed.add_field(name="Kanal", value=before.channel.mention)
        embed.add_field(name="Eski", value=before.content, inline=False)
        embed.add_field(name="Yeni", value=after.content, inline=False)

        await log_channel.send(embed=embed)

    # 3. BİRİ BANLANDIĞINDA
    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        ayarlar = self.ayar_getir(guild.id)
        if "log_kanali" not in ayarlar: return
        log_channel = self.bot.get_channel(ayarlar["log_kanali"])

        embed = discord.Embed(title="🔨 Biri Yasaklandı (Ban)", description=f"**{user.name}** sunucudan postalandı.",
                              color=discord.Color.dark_red())
        embed.set_thumbnail(url=user.display_avatar.url)
        await log_channel.send(embed=embed)

    # 4. BİRİ BANINI AÇTIĞINDA (UNBAN)
    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        ayarlar = self.ayar_getir(guild.id)
        if "log_kanali" not in ayarlar: return
        log_channel = self.bot.get_channel(ayarlar["log_kanali"])

        embed = discord.Embed(title="🔓 Yasak Kaldırıldı", description=f"**{user.name}** kullanıcısının banı açıldı.",
                              color=discord.Color.green())
        await log_channel.send(embed=embed)

    # 5. SES KANALINA GİRİŞ/ÇIKIŞ
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        ayarlar = self.ayar_getir(member.guild.id)
        if "log_kanali" not in ayarlar: return
        log_channel = self.bot.get_channel(ayarlar["log_kanali"])

        # Kanala Girdi
        if before.channel is None and after.channel is not None:
            embed = discord.Embed(description=f"🔊 **{member.name}**, `{after.channel.name}` ses kanalına girdi.",
                                  color=discord.Color.blue())
            await log_channel.send(embed=embed)

        # Kanaldan Çıktı
        elif before.channel is not None and after.channel is None:
            embed = discord.Embed(description=f"🔇 **{member.name}**, `{before.channel.name}` ses kanalından çıktı.",
                                  color=discord.Color.greyple())
            await log_channel.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Logger(bot))