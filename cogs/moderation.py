import discord
from discord.ext import commands
import datetime
import re
import asyncio


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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
        embed = discord.Embed(title="⚠️ UYARI", description=f"{member.mention}, dikkat etmen gerekiyor!",
                              color=discord.Color.orange())
        embed.add_field(name="Sebep", value=sebep)
        embed.set_footer(text=f"Yetkili: {ctx.author.name}")
        await ctx.send(embed=embed)

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
        await ctx.send(f"😶 **{member.name}** susturuldu.")

    @commands.command(name="unmute", aliases=["ac", "unban"])
    @commands.has_permissions(moderate_members=True)
    async def unmute_komut(self, ctx, member: discord.Member):
        await member.timeout(None)
        await ctx.send(f"🎤 **{member.name}** konuşabilir.")

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
                except:
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


async def setup(bot):
    await bot.add_cog(Moderation(bot))