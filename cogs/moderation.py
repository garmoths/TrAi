import discord
from discord import app_commands
from discord.ext import commands
import datetime
import re
import asyncio
from utils.logger import get_logger
from utils import warnings as warn_utils
from utils import db


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = get_logger(__name__)

    # --- HİYERARŞİ KONTROLÜ ---
    async def hiyerarsi_kontrol(self, ctx_or_msg, member):
        if isinstance(member, discord.User): return True
        author = ctx_or_msg.author if isinstance(ctx_or_msg, discord.Message) else ctx_or_msg.author
        guild = ctx_or_msg.guild

        if member.id == author.id:
            await ctx_or_msg.channel.send("❌ Kendine işlem yapamazsın!")
            return False
        if member.id == guild.owner_id:
            await ctx_or_msg.channel.send("👑 Sunucu sahibine dokunamam!")
            return False
        if author.id != guild.owner_id and member.top_role >= author.top_role:
            await ctx_or_msg.channel.send(f"🚫 **{member.name}** seninle aynı veya üst rütbede.")
            return False
        if member.top_role >= guild.me.top_role:
            await ctx_or_msg.channel.send(f"🤖 **{member.name}** benim yetkimin üzerinde.")
            return False
        return True

    # =========================================================================
    # 1. BÖLÜM: PREFİX KOMUTLAR (!sil, !ban)
    # =========================================================================

    @commands.command(name="sil", aliases=["temizle", "clear", "purge"])
    @commands.has_permissions(manage_messages=True)
    async def sil_komut(self, ctx, miktar: int):
        """Mesajları siler: !sil 100"""
        try:
            if miktar > 1000: miktar = 1000
            deleted = await ctx.channel.purge(limit=miktar + 1)
            msg = await ctx.send(f"🧹 **{len(deleted) - 1}** mesaj süpürüldü!")
            await msg.delete(delay=3)
        except discord.HTTPException:
            await ctx.send("❌ 14 günden eski mesajları toplu silemem.")

    @commands.command(name="uyar", aliases=["warn"])
    @commands.has_permissions(manage_messages=True)
    async def uyar_komut(self, ctx, member: discord.Member, *, sebep="Sebep Yok"):
        if not await self.hiyerarsi_kontrol(ctx, member): return
        try:
            warn_id = warn_utils.add_warning(ctx.guild.id, member.id, ctx.author.id, sebep)
        except Exception:
            self.logger.exception("Warn kaydedilemedi")
            warn_id = None

        # Uyarı sayısını al ve rol ver
        user_warns = warn_utils.list_warnings(ctx.guild.id, member.id)
        warn_count = len(user_warns)
        
        # RoleManager ile uyarı rolü güncelle
        try:
            role_mgr = self.bot.get_cog("RoleManager")
            if role_mgr:
                await role_mgr.uyarı_rolleri_güncelle(ctx.guild, member, warn_count)
                self.logger.info(f"{member.name} - Uyarı {warn_count} rolü verildi")
        except Exception as e:
            self.logger.warning(f"Uyarı rolü verilemedi: {e}")

        embed = discord.Embed(title="⚠️ UYARI", description=f"{member.mention}, dikkat etmen gerekiyor!",
                              color=discord.Color.orange())
        embed.add_field(name="Sebep", value=sebep)
        embed.add_field(name="Uyarı Sayısı", value=f"{warn_count} adet")
        if warn_id:
            embed.add_field(name="Uyarı ID", value=str(warn_id))
        embed.set_footer(text=f"Yetkili: {ctx.author.name}")
        await ctx.send(embed=embed)
        # DM the user with a rich embed containing details + current warn count
        try:
            # check per-command settings
            ayarlar = db.kv_get("settings", {}) or {}
            cmd_conf = ayarlar.get(str(ctx.guild.id), {}).get("commands", {}).get(ctx.command.name, {})
            send_dm = cmd_conf.get("send_dm", True)
            custom_text = cmd_conf.get("custom_text", "")

            if send_dm:
                dm_embed = discord.Embed(title="⚠️ Sunucu Uyarısı",
                                         description=f"{ctx.guild.name} sunucusunda uyarıldın.",
                                         color=discord.Color.orange())
                dm_embed.add_field(name="Sebep", value=sebep, inline=False)
                dm_embed.add_field(name="Yetkili", value=f"{ctx.author} ({ctx.author.id})", inline=True)
                dm_embed.add_field(name="Uyarı Sayısı", value=f"{warn_count} / {ayarlar.get(str(ctx.guild.id), {}).get('auto_mute_threshold', 3)}", inline=True)
                dm_embed.set_footer(text=f"Uyarı ID: {warn_id if warn_id else '-'}")
                dm_embed.timestamp = discord.utils.utcnow()
                try:
                    # send custom text first if configured
                    if custom_text:
                        try:
                            await member.send(custom_text)
                        except Exception:
                            pass
                    await member.send(embed=dm_embed)
                except Exception:
                    # ignore DM failures
                    pass
        except Exception:
            self.logger.exception("Uyarı DM'i hazırlanırken hata oluştu")

        # Also log to configured log channel if available (handled by cogs/logger listener)
        # Auto-mute: if user has reached 3 warnings, apply 10 minute timeout
        try:
            # read per-guild settings (fallback to defaults)
            ayarlar = db.kv_get("settings", {}) or {}
            guild_settings = ayarlar.get(str(ctx.guild.id), {})
            threshold = int(guild_settings.get("auto_mute_threshold", 3))
            minutes = int(guild_settings.get("auto_mute_minutes", 10))
            auto_enabled = bool(guild_settings.get("auto_mute_enabled", True))

            if auto_enabled and warn_count >= threshold:
                try:
                    delta = datetime.timedelta(minutes=minutes)
                    await member.timeout(discord.utils.utcnow() + delta)
                    await ctx.send(f"🔇 **{member.name}** {threshold} uyarı nedeniyle {minutes} dakika susturuldu.")
                    # log to channel if set
                    try:
                        kanal_id = guild_settings.get("log_kanali")
                        if kanal_id:
                            log_chan = self.bot.get_channel(kanal_id)
                            if log_chan:
                                embed_auto = discord.Embed(title="🔇 Otomatik Susturma",
                                                           description=f"{member.mention} {threshold} uyarı nedeniyle {minutes} dakika susturuldu.",
                                                           color=discord.Color.dark_gold())
                                embed_auto.add_field(name="Uyarı Sayısı", value=str(warn_count))
                                embed_auto.set_footer(text=f"Yetkili: Sistem / Otomatik")
                                await log_chan.send(embed=embed_auto)
                    except Exception:
                        self.logger.exception("Otomatik susturma log kanalı yazılamadı")
                except Exception:
                    self.logger.exception("Otomatik susturma uygulanamadı")
        except Exception:
            self.logger.exception("Uyarı sayısı kontrol edilirken hata")
        try:
            ayarlar = db.kv_get("settings", {}) or {}
            kanal_id = ayarlar.get(str(ctx.guild.id), {}).get("log_kanali")
            if kanal_id:
                log_chan = self.bot.get_channel(kanal_id)
                if log_chan:
                    embed2 = discord.Embed(title="⚠️ Uyarı Kaydı",
                                           description=f"{member.mention} uyarıldı.", color=discord.Color.orange())
                    embed2.add_field(name="Sebep", value=sebep)
                    if warn_id:
                        embed2.add_field(name="Uyarı ID", value=str(warn_id))
                    embed2.set_footer(text=f"Yetkili: {ctx.author.name}")
                    await log_chan.send(embed=embed2)
        except Exception:
            self.logger.exception("Log kanalına uyarı yazılamadı")

    @commands.command(name="ban", aliases=["yasakla"])
    @commands.has_permissions(ban_members=True)
    async def ban_komut(self, ctx, member: discord.Member, *, sebep="Yok"):
        if not await self.hiyerarsi_kontrol(ctx, member): return
        await member.ban(reason=sebep)
        await ctx.send(f"🔨 **{member.name}** yasaklandı.")

    @commands.command(name="kick", aliases=["at"])
    @commands.has_permissions(kick_members=True)
    async def kick_komut(self, ctx, member: discord.Member, *, sebep="Yok"):
        if not await self.hiyerarsi_kontrol(ctx, member): return
        await member.kick(reason=sebep)
        await ctx.send(f"👢 **{member.name}** atıldı.")

    @commands.command(name="mute", aliases=["sustur"])
    @commands.has_permissions(moderate_members=True)
    async def mute_komut(self, ctx, member: discord.Member, sure: int, birim: str = "dk"):
        if not await self.hiyerarsi_kontrol(ctx, member): return
        delta = datetime.timedelta(minutes=10)
        if birim in ["s", "sn"]:
            delta = datetime.timedelta(seconds=sure)
        elif birim in ["dk", "m"]:
            delta = datetime.timedelta(minutes=sure)
        elif birim in ["sa", "h"]:
            delta = datetime.timedelta(hours=sure)
        await member.timeout(discord.utils.utcnow() + delta)
        
        # Susturulmuş rolü ver
        try:
            role_mgr = self.bot.get_cog("RoleManager")
            if role_mgr:
                await role_mgr.susturulmuş_rol_ver(ctx.guild, member)
                self.logger.info(f"{member.name} - Susturulmuş rolü verildi")
        except Exception as e:
            self.logger.warning(f"Susturulmuş rolü verilemedi: {e}")
        
        await ctx.send(f"😶 **{member.name}** susturuldu.")

    @commands.command(name="unmute", aliases=["ac", "unban"])
    @commands.has_permissions(moderate_members=True)
    async def unmute_komut(self, ctx, member: discord.Member):
        await member.timeout(None)
        
        # Susturulmuş rolü al
        try:
            role_mgr = self.bot.get_cog("RoleManager")
            if role_mgr:
                await role_mgr.susturulmuş_rol_al(ctx.guild, member)
                self.logger.info(f"{member.name} - Susturulmuş rolü alındı")
        except Exception as e:
            self.logger.warning(f"Susturulmuş rolü alınamadı: {e}")
        await ctx.send(f"🎤 **{member.name}** konuşabilir.")

    @commands.command(name="warns", aliases=["uyarlar"])
    @commands.has_permissions(manage_messages=True)
    async def warns_komut(self, ctx, member: discord.Member = None):
        """List warnings for a member or the whole guild."""
        try:
            if member:
                items = warn_utils.list_warnings(ctx.guild.id, member.id)
            else:
                items = warn_utils.list_warnings(ctx.guild.id)
        except Exception:
            self.logger.exception("Uyarılar okunamadı")
            await ctx.send("❌ Uyarılar okunamadı.")
            return

        if not items:
            await ctx.send("ℹ️ Uyarı bulunmuyor.")
            return

        lines = []
        for w in items[-25:]:
            ts = w.get("timestamp", "?")
            uid = w.get("user_id")
            mid = w.get("moderator_id")
            rid = w.get("id")
            reason = w.get("reason", "-")
            lines.append(f"ID:{rid} • Kullanıcı:{uid} • Yetkili:{mid} • {reason} • {ts}")

        chunk = "\n".join(lines)
        # If too long, split into multiple messages
        if len(chunk) > 1900:
            for i in range(0, len(chunk), 1900):
                await ctx.send(chunk[i:i+1900])
        else:
            await ctx.send(f"```\n{chunk}\n```")

    @commands.command(name="unwarn", aliases=["removewarn"])
    @commands.has_permissions(manage_messages=True)
    async def unwarn_komut(self, ctx, warn_id: int):
        """Remove a warning by its ID."""
        try:
            ok = warn_utils.remove_warning(ctx.guild.id, warn_id)
        except Exception:
            self.logger.exception("Uyarı silinirken hata")
            await ctx.send("❌ Uyarı silinemedi.")
            return
        if ok:
            await ctx.send(f"✅ Uyarı {warn_id} silindi.")
            try:
                ayarlar = db.kv_get("settings", {}) or {}
                kanal_id = ayarlar.get(str(ctx.guild.id), {}).get("log_kanali")
                if kanal_id:
                    log_chan = self.bot.get_channel(kanal_id)
                    if log_chan:
                        embed = discord.Embed(title="🗑️ Uyarı Silindi",
                                              description=f"Uyarı ID {warn_id} silindi.", color=discord.Color.red())
                        embed.set_footer(text=f"Yetkili: {ctx.author.name}")
                        await log_chan.send(embed=embed)
            except Exception:
                self.logger.exception("Log kanalına uyarı silme yazılamadı")
        else:
            await ctx.send(f"❓ Böyle bir uyarı bulunamadı: {warn_id}")

    @commands.command(name="clearwarns", aliases=["clearuyar"])
    @commands.has_permissions(manage_messages=True)
    async def clearwarns_komut(self, ctx, member: discord.Member = None):
        """Clear warnings for a member or all warnings if no member provided."""
        try:
            if member:
                removed = warn_utils.clear_warnings(ctx.guild.id, member.id)
            else:
                removed = warn_utils.clear_warnings(ctx.guild.id, None)
        except Exception:
            self.logger.exception("Uyarılar temizlenemedi")
            await ctx.send("❌ Temizleme başarısız.")
            return
        await ctx.send(f"🧹 {removed} uyarı temizlendi.")
        try:
            ayarlar = db.kv_get("settings", {}) or {}
            kanal_id = ayarlar.get(str(ctx.guild.id), {}).get("log_kanali")
            if kanal_id:
                log_chan = self.bot.get_channel(kanal_id)
                if log_chan:
                    embed = discord.Embed(title="🧹 Uyarılar Temizlendi",
                                          description=f"{removed} uyarı temizlendi.", color=discord.Color.blue())
                    embed.set_footer(text=f"Yetkili: {ctx.author.name}")
                    await log_chan.send(embed=embed)
        except Exception:
            self.logger.exception("Log kanalına temizleme yazılamadı")

    @commands.command(name="set_warn_threshold", aliases=["uyari_esigi"])
    @commands.has_permissions(administrator=True)
    async def set_warn_threshold(self, ctx, threshold: int):
        """Set the number of warnings that trigger an automatic mute."""
        if threshold < 1:
            await ctx.send("⚠️ Eşik en az 1 olmalı.")
            return
        try:
            ayarlar = db.kv_get("settings", {}) or {}
            if str(ctx.guild.id) not in ayarlar:
                ayarlar[str(ctx.guild.id)] = {}
            ayarlar[str(ctx.guild.id)]["auto_mute_threshold"] = int(threshold)
            db.kv_set("settings", ayarlar)
            await ctx.send(f"✅ Otomatik mute eşiği {threshold} olarak ayarlandı.")
        except Exception:
            self.logger.exception("Eşik kaydedilemedi")
            await ctx.send("❌ Eşik kaydedilemedi.")

    @commands.command(name="set_warn_duration", aliases=["uyari_suresi"])
    @commands.has_permissions(administrator=True)
    async def set_warn_duration(self, ctx, minutes: int):
        """Set the duration (minutes) for automatic mute when threshold is reached."""
        if minutes < 1:
            await ctx.send("⚠️ Süre en az 1 dakika olmalı.")
            return
        try:
            ayarlar = db.kv_get("settings", {}) or {}
            if str(ctx.guild.id) not in ayarlar:
                ayarlar[str(ctx.guild.id)] = {}
            ayarlar[str(ctx.guild.id)]["auto_mute_minutes"] = int(minutes)
            db.kv_set("settings", ayarlar)
            await ctx.send(f"✅ Otomatik mute süresi {minutes} dakika olarak ayarlandı.")
        except Exception:
            self.logger.exception("Süre kaydedilemedi")
            await ctx.send("❌ Süre kaydedilemedi.")

    @commands.command(name="get_warn_settings", aliases=["uyari_ayar"])
    @commands.has_permissions(administrator=True)
    async def get_warn_settings(self, ctx):
        """Show auto-mute settings for this guild."""
        try:
            ayarlar = db.kv_get("settings", {}) or {}
            guild_settings = ayarlar.get(str(ctx.guild.id), {})
            threshold = guild_settings.get("auto_mute_threshold", 3)
            minutes = guild_settings.get("auto_mute_minutes", 10)
            await ctx.send(f"🛠️ Eşik: {threshold} uyarı • Süre: {minutes} dakika")
        except Exception:
            self.logger.exception("Ayarlar okunamadı")
            await ctx.send("❌ Ayarlar okunamadı.")

    # =========================================================================
    # 2. BÖLÜM: DOĞAL DİL İŞLEMCİSİ
    # =========================================================================

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild: return
        if not self.bot.user.mentioned_in(message): return
        if not message.author.guild_permissions.manage_messages: return

        icerik = message.content.lower().replace(f"<@{self.bot.user.id}>", "").strip()

        # KELİME LİSTELERİ
        sil_listesi = ["sil", "temizle", "süpür", "yok et", "kaldır", "clear", "purge", "delete", "sıfırla", "uçur"]
        af_listesi = ["aç", "konuş", "kaldır", "affet", "boz", "çıkardım", "özgür", "unban", "unmute"]
        uyar_listesi = ["uyar", "ikaz", "dikkat", "kız", "uyarı", "sarı kart", "warn"]
        sustur_listesi = ["sustur", "mute", "sessiz", "sus", "kapat", "çenesini", "ağzını", "sesini kes"]
        ban_listesi = ["ban", "yasakla", "uçur", "paketle", "yargı", "fırlat", "engelle", "infaz"]
        kick_listesi = ["kick", "at", "kov", "dışarı", "postala", "sepetle", "şutla", "yolla"]

        # --- A) SİLME İŞLEMİ ---
        if any(k in icerik for k in sil_listesi) and not any(b in icerik for b in ban_listesi):
            # Sayıyı bul (100 mesaj sil)
            sayi_bul = re.search(r'(\d+)', icerik)
            miktar = int(sayi_bul.group(1)) if sayi_bul else 5

            if miktar > 1000:
                await message.channel.send("⚠️ Tek seferde en fazla 1000 mesaj silebilirim.")
                miktar = 1000

            try:
                # bulk=True ile hızlı silme
                deleted = await message.channel.purge(limit=miktar + 1, bulk=True)
                sayi = len(deleted) - 1  # Komut mesajını sayıdan düş
                if sayi < 0: sayi = 0

                msg = await message.channel.send(f"🧹 **{sayi}** mesaj tarihe gömüldü.")
                await msg.delete(delay=3)
            except discord.HTTPException:
                await message.channel.send("❌ 14 günden eski mesajları Discord API gereği silemiyorum.")
            return

        # HEDEF KİŞİ BULMA
        hedef = None
        for user in message.mentions:
            if user.id != self.bot.user.id:
                hedef = user
                break

        # B) BAN KALDIRMA
        if any(k in icerik for k in ["ban", "yasak"]) and any(a in icerik for a in af_listesi):
            if not message.author.guild_permissions.ban_members: return
            async with message.channel.typing():
                try:
                    yasakli_listesi = [entry async for entry in message.guild.bans()]
                except Exception as e:
                    self.logger.debug("Failed to fetch ban list: %s", e)
                    return
                bulunan = None
                for entry in yasakli_listesi:
                    if entry.user.name.lower() in icerik or str(entry.user.id) in icerik:
                        bulunan = entry.user
                        break
                if bulunan:
                    await message.guild.unban(bulunan, reason=f"Yetkili: {message.author.name}")
                    await message.channel.send(f"✅ **{bulunan.name}** aramıza geri döndü.")
                else:
                    await message.channel.send("❓ Bu isimde yasaklı biri yok.")
            return

        if not hedef: return

        # C) DİĞER KOMUTLAR
        if any(k in icerik for k in af_listesi):
            if await self.hiyerarsi_kontrol(message, hedef):
                await hedef.timeout(None)
                await message.channel.send(f"🎤 **{hedef.name}** artık konuşabilir.")
                return

        if any(k in icerik for k in uyar_listesi):
            if await self.hiyerarsi_kontrol(message, hedef):
                embed = discord.Embed(title="⚠️ DİKKAT", description=f"{hedef.mention}, hareketlerine dikkat et!",
                                      color=discord.Color.red())
                embed.set_footer(text=f"Yetkili: {message.author.name}")
                await message.channel.send(embed=embed)
            return

        if any(k in icerik for k in sustur_listesi):
            if await self.hiyerarsi_kontrol(message, hedef):
                zaman = re.search(r'(\d+)\s*(dk|dakika|sn|saniye|sa|saat|gün)', icerik)
                sure = 10;
                birim = "dk"
                if zaman:
                    sure = int(zaman.group(1))
                    birim_str = zaman.group(2)
                    if "sn" in birim_str or "s" in birim_str:
                        delta = datetime.timedelta(seconds=sure); birim = "sn"
                    elif "sa" in birim_str or "h" in birim_str:
                        delta = datetime.timedelta(hours=sure); birim = "saat"
                    else:
                        delta = datetime.timedelta(minutes=sure)
                else:
                    delta = datetime.timedelta(minutes=10)
                await hedef.timeout(discord.utils.utcnow() + delta)
                await message.channel.send(f"😶 **{hedef.name}** {sure} {birim} susturuldu.")
            return

        if any(k in icerik for k in ban_listesi):
            if await self.hiyerarsi_kontrol(message, hedef):
                await hedef.ban(reason=f"Yetkili: {message.author.name}")
                await message.channel.send(f"🔨 **{hedef.name}** paketlendi.")
            return

        if any(k in icerik for k in kick_listesi):
            if await self.hiyerarsi_kontrol(message, hedef):
                await hedef.kick(reason=f"Yetkili: {message.author.name}")
                await message.channel.send(f"👢 **{hedef.name}** atıldı.")
            return

    # =========================================================================
    # SLASH KOMUTLAR (Discord / Menüsü için)
    # =========================================================================

    @app_commands.command(name="sil", description="🧹 Belirtilen sayıda mesajı siler")
    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.describe(miktar="Silinecek mesaj sayısı (max 1000)")
    async def sil_slash(self, interaction: discord.Interaction, miktar: int):
        """Slash komut ile mesaj silme."""
        try:
            if miktar > 1000:
                miktar = 1000
            await interaction.response.defer(ephemeral=True)
            deleted = await interaction.channel.purge(limit=miktar)
            await interaction.followup.send(f"🧹 **{len(deleted)}** mesaj süpürüldü!", ephemeral=True)
        except discord.HTTPException:
            await interaction.followup.send("❌ 14 günden eski mesajları toplu silemem.", ephemeral=True)

    @app_commands.command(name="uyar", description="⚠️ Kullanıcıyı uyarır")
    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.describe(
        uye="Uyarılacak kullanıcı",
        sebep="Uyarı sebebi"
    )
    async def uyar_slash(self, interaction: discord.Interaction, uye: discord.Member, sebep: str = "Sebep Yok"):
        """Slash komut ile uyarı."""
        if not await self.hiyerarsi_kontrol_slash(interaction, uye):
            return
        
        try:
            warn_id = warn_utils.add_warning(interaction.guild.id, uye.id, interaction.user.id, sebep)
        except Exception:
            self.logger.exception("Warn kaydedilemedi")
            warn_id = None

        # Uyarı sayısını al ve rol ver
        user_warns = warn_utils.list_warnings(interaction.guild.id, uye.id)
        warn_count = len(user_warns)
        
        # RoleManager ile uyarı rolü güncelle
        try:
            role_mgr = self.bot.get_cog("RoleManager")
            if role_mgr:
                await role_mgr.uyarı_rolleri_güncelle(interaction.guild, uye, warn_count)
                self.logger.info(f"{uye.name} - Uyarı {warn_count} rolü verildi")
        except Exception as e:
            self.logger.warning(f"Uyarı rolü verilemedi: {e}")

        embed = discord.Embed(
            title="⚠️ UYARI",
            description=f"{uye.mention}, dikkat etmen gerekiyor!",
            color=discord.Color.orange()
        )
        embed.add_field(name="Sebep", value=sebep)
        embed.add_field(name="Uyarı Sayısı", value=f"{warn_count} adet")
        if warn_id:
            embed.add_field(name="Uyarı ID", value=str(warn_id))
        embed.set_footer(text=f"Yetkili: {interaction.user.name}")
        
        await interaction.response.send_message(embed=embed)

        # DM gönderimi
        try:
            ayarlar = db.kv_get("settings", {}) or {}
            guild_settings = ayarlar.get(str(interaction.guild.id), {})
            send_dm = guild_settings.get("send_warn_dm", True)

            if send_dm:
                dm_embed = discord.Embed(
                    title=f"⚠️ {interaction.guild.name} - Uyarı Aldınız",
                    description=f"**Sebep:** {sebep}",
                    color=discord.Color.orange()
                )
                dm_embed.add_field(name="Toplam Uyarı", value=f"{warn_count} adet")
                dm_embed.set_footer(text=f"Yetkili: {interaction.user.name}")
                await uye.send(embed=dm_embed)
        except Exception:
            self.logger.warning("Uyarı DM gönderilemedi")

    @app_commands.command(name="ban", description="🔨 Kullanıcıyı sunucudan yasaklar")
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.describe(
        uye="Yasaklanacak kullanıcı",
        sebep="Yasaklama sebebi"
    )
    async def ban_slash(self, interaction: discord.Interaction, uye: discord.Member, sebep: str = "Yok"):
        """Slash komut ile ban."""
        if not await self.hiyerarsi_kontrol_slash(interaction, uye):
            return
        
        await uye.ban(reason=sebep)
        await interaction.response.send_message(f"🔨 **{uye.name}** yasaklandı. Sebep: {sebep}")

    @app_commands.command(name="kick", description="👢 Kullanıcıyı sunucudan atar")
    @app_commands.checks.has_permissions(kick_members=True)
    @app_commands.describe(
        uye="Atılacak kullanıcı",
        sebep="Atma sebebi"
    )
    async def kick_slash(self, interaction: discord.Interaction, uye: discord.Member, sebep: str = "Yok"):
        """Slash komut ile kick."""
        if not await self.hiyerarsi_kontrol_slash(interaction, uye):
            return
        
        await uye.kick(reason=sebep)
        await interaction.response.send_message(f"👢 **{uye.name}** atıldı. Sebep: {sebep}")

    @app_commands.command(name="sustur", description="🔇 Kullanıcıyı geçici olarak susturur")
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.describe(
        uye="Susturulacak kullanıcı",
        sure="Süre (dakika)",
    )
    async def sustur_slash(self, interaction: discord.Interaction, uye: discord.Member, sure: int):
        """Slash komut ile susturma."""
        if not await self.hiyerarsi_kontrol_slash(interaction, uye):
            return
        
        delta = datetime.timedelta(minutes=sure)
        await uye.timeout(discord.utils.utcnow() + delta)
        
        # Susturulmuş rolü ver
        try:
            role_mgr = self.bot.get_cog("RoleManager")
            if role_mgr:
                await role_mgr.susturulmuş_rol_ver(interaction.guild, uye)
                self.logger.info(f"{uye.name} - Susturulmuş rolü verildi")
        except Exception as e:
            self.logger.warning(f"Susturulmuş rolü verilemedi: {e}")
        
        await interaction.response.send_message(f"🔇 **{uye.name}** {sure} dakika susturuldu.")

    @app_commands.command(name="susturma-kaldir", description="🎤 Kullanıcının susturmasını kaldırır")
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.describe(uye="Susturması kaldırılacak kullanıcı")
    async def susturma_kaldir_slash(self, interaction: discord.Interaction, uye: discord.Member):
        """Slash komut ile unmute."""
        await uye.timeout(None)
        
        # Susturulmuş rolü al
        try:
            role_mgr = self.bot.get_cog("RoleManager")
            if role_mgr:
                await role_mgr.susturulmuş_rol_al(interaction.guild, uye)
                self.logger.info(f"{uye.name} - Susturulmuş rolü alındı")
        except Exception as e:
            self.logger.warning(f"Susturulmuş rolü alınamadı: {e}")
        
        await interaction.response.send_message(f"🎤 **{uye.name}** artık konuşabilir.")

    @app_commands.command(name="uyarilar", description="📋 Kullanıcının veya sunucunun uyarılarını listeler")
    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.describe(uye="Uyarıları görüntülenecek kullanıcı (boş bırakılırsa tüm sunucu)")
    async def uyarilar_slash(self, interaction: discord.Interaction, uye: discord.Member = None):
        """Slash komut ile uyarı listesi."""
        try:
            if uye:
                items = warn_utils.list_warnings(interaction.guild.id, uye.id)
            else:
                items = warn_utils.list_warnings(interaction.guild.id)
        except Exception:
            self.logger.exception("Uyarılar okunamadı")
            await interaction.response.send_message("❌ Uyarılar okunamadı.", ephemeral=True)
            return

        if not items:
            await interaction.response.send_message("ℹ️ Uyarı bulunmuyor.", ephemeral=True)
            return

        lines = []
        for w in items[-25:]:
            ts = w.get("timestamp", "?")
            uid = w.get("user_id")
            mid = w.get("moderator_id")
            rid = w.get("id")
            reason = w.get("reason", "-")
            lines.append(f"ID:{rid} • Kullanıcı:<@{uid}> • Yetkili:<@{mid}> • {reason[:50]}")

        embed = discord.Embed(
            title="📋 Uyarı Listesi",
            description="\n".join(lines),
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="slowmode", description="⏱️ Kanal yavaş modunu ayarlar")
    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.describe(
        saniye="Yavaş mod süresi (0 = kapalı, max 21600)",
        kanal="Yavaş mod uygulanacak kanal (boş = mevcut kanal)"
    )
    async def slowmode_slash(self, interaction: discord.Interaction, saniye: int, kanal: discord.TextChannel = None):
        """Kanal slowmode ayarlar."""
        target_channel = kanal or interaction.channel
        
        if saniye < 0 or saniye > 21600:
            await interaction.response.send_message("❌ Süre 0-21600 saniye arasında olmalı!", ephemeral=True)
            return
        
        await target_channel.edit(slowmode_delay=saniye)
        
        if saniye == 0:
            await interaction.response.send_message(f"✅ {target_channel.mention} kanalında yavaş mod **kapatıldı**.")
        else:
            await interaction.response.send_message(f"⏱️ {target_channel.mention} kanalında yavaş mod **{saniye} saniye** olarak ayarlandı.")

    @app_commands.command(name="lock", description="🔒 Kanalı kilitler (@everyone yazamaz)")
    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.describe(kanal="Kilitlenecek kanal (boş = mevcut kanal)")
    async def lock_slash(self, interaction: discord.Interaction, kanal: discord.TextChannel = None):
        """Kanalı kilitler."""
        target_channel = kanal or interaction.channel
        
        await target_channel.set_permissions(
            interaction.guild.default_role,
            send_messages=False,
            reason=f"Kanal kilitlendi: {interaction.user}"
        )
        
        await interaction.response.send_message(f"🔒 {target_channel.mention} kanalı **kilitlendi**. Sadece yetkililer yazabilir.")

    @app_commands.command(name="unlock", description="🔓 Kanal kilidini açar")
    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.describe(kanal="Kilidi açılacak kanal (boş = mevcut kanal)")
    async def unlock_slash(self, interaction: discord.Interaction, kanal: discord.TextChannel = None):
        """Kanal kilidini açar."""
        target_channel = kanal or interaction.channel
        
        await target_channel.set_permissions(
            interaction.guild.default_role,
            send_messages=None,
            reason=f"Kanal kilidi açıldı: {interaction.user}"
        )
        
        await interaction.response.send_message(f"🔓 {target_channel.mention} kanalının kilidi **açıldı**. Herkes yazabilir.")

    @app_commands.command(name="lockdown", description="🚨 Sunucuyu lockdown moduna alır (tüm kanallar)")
    @app_commands.checks.has_permissions(administrator=True)
    async def lockdown_slash(self, interaction: discord.Interaction):
        """Tüm text kanalları kilitler."""
        await interaction.response.defer()
        
        locked_count = 0
        for channel in interaction.guild.text_channels:
            try:
                await channel.set_permissions(
                    interaction.guild.default_role,
                    send_messages=False,
                    reason=f"Sunucu lockdown: {interaction.user}"
                )
                locked_count += 1
            except Exception:
                continue
        
        embed = discord.Embed(
            title="🚨 LOCKDOWN AKTIF",
            description=f"**{locked_count}** kanal kilitlendi!\n\nSadece yetkililer mesaj gönderebilir.",
            color=discord.Color.red()
        )
        embed.set_footer(text=f"Yetkili: {interaction.user.name}")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="unlockdown", description="✅ Sunucu lockdown'ını kaldırır")
    @app_commands.checks.has_permissions(administrator=True)
    async def unlockdown_slash(self, interaction: discord.Interaction):
        """Tüm kanalların kilidini açar."""
        await interaction.response.defer()
        
        unlocked_count = 0
        for channel in interaction.guild.text_channels:
            try:
                await channel.set_permissions(
                    interaction.guild.default_role,
                    send_messages=None,
                    reason=f"Lockdown kaldırıldı: {interaction.user}"
                )
                unlocked_count += 1
            except Exception:
                continue
        
        embed = discord.Embed(
            title="✅ Lockdown Kaldırıldı",
            description=f"**{unlocked_count}** kanalın kilidi açıldı!\n\nHerkes normal şekilde yazabilir.",
            color=discord.Color.green()
        )
        embed.set_footer(text=f"Yetkili: {interaction.user.name}")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="nuke", description="💣 Kanalı siler ve aynısını yeniden oluşturur")
    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.describe(kanal="Yenilenecek kanal (boş = mevcut kanal)")
    async def nuke_slash(self, interaction: discord.Interaction, kanal: discord.TextChannel = None):
        """Kanalı temizlemek için siler ve yeniden oluşturur."""
        target_channel = kanal or interaction.channel
        
        # Kanal bilgilerini kaydet
        channel_position = target_channel.position
        channel_category = target_channel.category
        channel_topic = target_channel.topic
        channel_nsfw = target_channel.nsfw
        channel_slowmode = target_channel.slowmode_delay
        channel_perms = target_channel.overwrites
        
        await interaction.response.send_message("💣 Kanal yenileniyor...", ephemeral=True)
        
        # Yeni kanal oluştur
        new_channel = await target_channel.clone(reason=f"Nuke komutu: {interaction.user}")
        await new_channel.edit(position=channel_position)
        
        # Eski kanalı sil
        await target_channel.delete(reason=f"Nuke komutu: {interaction.user}")
        
        # Bilgilendirme mesajı
        embed = discord.Embed(
            title="💣 Kanal Yenilendi!",
            description=f"Bu kanal {interaction.user.mention} tarafından temizlendi.",
            color=discord.Color.blue()
        )
        embed.set_image(url="https://media.giphy.com/media/HhTXt43pk1I1W/giphy.gif")
        await new_channel.send(embed=embed)

    @app_commands.command(name="softban", description="🔄 Kullanıcıyı softban yapar (ban sonra unban - mesajlar silinir)")
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.describe(
        uye="Softban yapılacak kullanıcı",
        sebep="Sebep",
        mesaj_sil="Kaç günlük mesaj silinecek (0-7)"
    )
    async def softban_slash(self, interaction: discord.Interaction, uye: discord.Member, sebep: str = "Yok", mesaj_sil: int = 1):
        """Softban - Ban sonra hemen unban, mesajlar silinir."""
        if not await self.hiyerarsi_kontrol_slash(interaction, uye):
            return
        
        if mesaj_sil < 0 or mesaj_sil > 7:
            mesaj_sil = 1
        
        await interaction.guild.ban(uye, reason=f"Softban: {sebep} | Yetkili: {interaction.user}", delete_message_days=mesaj_sil)
        await interaction.guild.unban(uye, reason=f"Softban (otomatik unban)")
        
        await interaction.response.send_message(f"🔄 **{uye.name}** softban yapıldı. {mesaj_sil} günlük mesajları silindi.")

    @app_commands.command(name="nick", description="✏️ Kullanıcının ismini değiştirir")
    @app_commands.checks.has_permissions(manage_nicknames=True)
    @app_commands.describe(
        uye="İsmi değiştirilecek kullanıcı",
        yeni_isim="Yeni isim (boş = eski ismine sıfırla)"
    )
    async def nick_slash(self, interaction: discord.Interaction, uye: discord.Member, yeni_isim: str = None):
        """Kullanıcı ismini değiştirir."""
        if not await self.hiyerarsi_kontrol_slash(interaction, uye):
            return
        
        eski_isim = uye.display_name
        await uye.edit(nick=yeni_isim, reason=f"İsim değişikliği: {interaction.user}")
        
        if yeni_isim:
            await interaction.response.send_message(f"✏️ **{eski_isim}** → **{yeni_isim}**")
        else:
            await interaction.response.send_message(f"✏️ **{eski_isim}**'in ismi sıfırlandı → **{uye.name}**")

    @app_commands.command(name="rol-ver", description="➕ Kullanıcıya rol verir")
    @app_commands.checks.has_permissions(manage_roles=True)
    @app_commands.describe(
        uye="Rol verilecek kullanıcı",
        rol="Verilecek rol"
    )
    async def rol_ver_slash(self, interaction: discord.Interaction, uye: discord.Member, rol: discord.Role):
        """Kullanıcıya rol verir."""
        if rol >= interaction.guild.me.top_role:
            await interaction.response.send_message("❌ Bu rol benim yetkimin üzerinde!", ephemeral=True)
            return
        
        if rol in uye.roles:
            await interaction.response.send_message(f"❌ {uye.mention} zaten {rol.mention} rolüne sahip!", ephemeral=True)
            return
        
        await uye.add_roles(rol, reason=f"Rol verildi: {interaction.user}")
        await interaction.response.send_message(f"➕ {uye.mention} kullanıcısına {rol.mention} rolü verildi.")

    @app_commands.command(name="rol-al", description="➖ Kullanıcıdan rol alır")
    @app_commands.checks.has_permissions(manage_roles=True)
    @app_commands.describe(
        uye="Rol alınacak kullanıcı",
        rol="Alınacak rol"
    )
    async def rol_al_slash(self, interaction: discord.Interaction, uye: discord.Member, rol: discord.Role):
        """Kullanıcıdan rol alır."""
        if rol >= interaction.guild.me.top_role:
            await interaction.response.send_message("❌ Bu rol benim yetkimin üzerinde!", ephemeral=True)
            return
        
        if rol not in uye.roles:
            await interaction.response.send_message(f"❌ {uye.mention} zaten {rol.mention} rolüne sahip değil!", ephemeral=True)
            return
        
        await uye.remove_roles(rol, reason=f"Rol alındı: {interaction.user}")
        await interaction.response.send_message(f"➖ {uye.mention} kullanıcısından {rol.mention} rolü alındı.")

    @app_commands.command(name="uyarı-sil", description="🗑️ Kullanıcının uyarısını siler")
    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.describe(uyari_id="Silinecek uyarı ID'si")
    async def uyari_sil_slash(self, interaction: discord.Interaction, uyari_id: int):
        """Uyarı ID'sine göre uyarıyı siler."""
        try:
            ok = warn_utils.remove_warning(interaction.guild.id, uyari_id)
            if ok:
                await interaction.response.send_message(f"✅ Uyarı ID **#{uyari_id}** silindi.")
            else:
                await interaction.response.send_message(f"❌ Uyarı ID **#{uyari_id}** bulunamadı.", ephemeral=True)
        except Exception:
            self.logger.exception("Uyarı silinemedi")
            await interaction.response.send_message("❌ Uyarı silinirken hata oluştu.", ephemeral=True)

    @app_commands.command(name="uyarı-temizle", description="🧹 Kullanıcının tüm uyarılarını temizler")
    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.describe(uye="Uyarıları temizlenecek kullanıcı")
    async def uyari_temizle_slash(self, interaction: discord.Interaction, uye: discord.Member):
        """Kullanıcının tüm uyarılarını temizler."""
        try:
            warns = warn_utils.list_warnings(interaction.guild.id, uye.id)
            if not warns:
                await interaction.response.send_message(f"❌ {uye.mention} kullanıcısının uyarısı yok.", ephemeral=True)
                return
            
            count = len(warns)
            for w in warns:
                warn_utils.remove_warning(interaction.guild.id, w.get("id"))
            
            await interaction.response.send_message(f"🧹 {uye.mention} kullanıcısının **{count}** uyarısı temizlendi.")
        except Exception:
            self.logger.exception("Uyarılar temizlenemedi")
            await interaction.response.send_message("❌ Uyarılar temizlenirken hata oluştu.", ephemeral=True)

    @app_commands.command(name="unban-all", description="🔓 Tüm yasakları kaldırır")
    @app_commands.checks.has_permissions(administrator=True)
    async def unban_all_slash(self, interaction: discord.Interaction):
        """Sunucudaki tüm banları kaldırır."""
        await interaction.response.defer()
        
        bans = [entry async for entry in interaction.guild.bans()]
        
        if not bans:
            await interaction.followup.send("❌ Sunucuda yasak yok.", ephemeral=True)
            return
        
        unbanned = 0
        for ban_entry in bans:
            try:
                await interaction.guild.unban(ban_entry.user, reason=f"Toplu unban: {interaction.user}")
                unbanned += 1
            except Exception:
                continue
        
        await interaction.followup.send(f"🔓 **{unbanned}** kullanıcının yasağı kaldırıldı.")

    @app_commands.command(name="sil-bot", description="🤖 Botların mesajlarını siler")
    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.describe(miktar="Kontrol edilecek mesaj sayısı (max 100)")
    async def sil_bot_slash(self, interaction: discord.Interaction, miktar: int = 100):
        """Bot mesajlarını siler."""
        if miktar > 100:
            miktar = 100
        
        await interaction.response.defer(ephemeral=True)
        
        def is_bot(m):
            return m.author.bot
        
        deleted = await interaction.channel.purge(limit=miktar, check=is_bot)
        await interaction.followup.send(f"🤖 **{len(deleted)}** bot mesajı silindi.", ephemeral=True)

    @app_commands.command(name="sil-embed", description="📎 Embed içeren mesajları siler")
    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.describe(miktar="Kontrol edilecek mesaj sayısı (max 100)")
    async def sil_embed_slash(self, interaction: discord.Interaction, miktar: int = 100):
        """Embed içeren mesajları siler."""
        if miktar > 100:
            miktar = 100
        
        await interaction.response.defer(ephemeral=True)
        
        def has_embed(m):
            return len(m.embeds) > 0
        
        deleted = await interaction.channel.purge(limit=miktar, check=has_embed)
        await interaction.followup.send(f"📎 **{len(deleted)}** embed mesajı silindi.", ephemeral=True)

    @app_commands.command(name="sil-kullanıcı", description="👤 Belirli kullanıcının mesajlarını siler")
    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.describe(
        uye="Mesajları silinecek kullanıcı",
        miktar="Kontrol edilecek mesaj sayısı (max 100)"
    )
    async def sil_kullanici_slash(self, interaction: discord.Interaction, uye: discord.Member, miktar: int = 100):
        """Belirli kullanıcının mesajlarını siler."""
        if miktar > 100:
            miktar = 100
        
        await interaction.response.defer(ephemeral=True)
        
        def is_user(m):
            return m.author.id == uye.id
        
        deleted = await interaction.channel.purge(limit=miktar, check=is_user)
        await interaction.followup.send(f"👤 {uye.mention}'in **{len(deleted)}** mesajı silindi.", ephemeral=True)

    async def hiyerarsi_kontrol_slash(self, interaction: discord.Interaction, member: discord.Member):
        """Slash komutlar için hiyerarşi kontrolü."""
        if member.id == interaction.user.id:
            await interaction.response.send_message("❌ Kendine işlem yapamazsın!", ephemeral=True)
            return False
        if member.id == interaction.guild.owner_id:
            await interaction.response.send_message("👑 Sunucu sahibine dokunamam!", ephemeral=True)
            return False
        if interaction.user.id != interaction.guild.owner_id and member.top_role >= interaction.user.top_role:
            await interaction.response.send_message(f"🚫 **{member.name}** seninle aynı veya üst rütbede.", ephemeral=True)
            return False
        if member.top_role >= interaction.guild.me.top_role:
            await interaction.response.send_message(f"🤖 **{member.name}** benim yetkimin üzerinde.", ephemeral=True)
            return False
        return True


async def setup(bot):
    await bot.add_cog(Moderation(bot))