import discord
from discord import app_commands
from discord.ext import commands
import json
import os
from utils import db
from utils.logger import get_logger

SETTINGS_FILE = "settings.json"

class Dashboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = get_logger(__name__)

    @commands.command(name="komutlar", aliases=["commands_list"])
    async def komutlar(self, ctx):
        """Botta yüklü tüm komutları listeler."""
        komutlar = [c.name for c in self.bot.commands]
        await ctx.send(f"Yüklü komutlar: {', '.join(komutlar)}")

    def can_user_edit(self, guild: discord.Guild, user: discord.Member) -> bool:
        try:
            self.logger.info(f"DEBUG: owner_id={guild.owner_id}, author_id={user.id}, is_owner={user.id == guild.owner_id}, is_admin={getattr(user, 'guild_permissions', None) and user.guild_permissions.administrator}")
            if user.id == guild.owner_id:
                return True
            veriler = self.ayar_yukle()
            guild_conf = veriler.get(str(guild.id), {})
            # admin bypass if enabled
            if guild_conf.get("allow_admin_edit", False) and getattr(user, "guild_permissions", None) and user.guild_permissions.administrator:
                return True
            allowed = guild_conf.get("panel_edit_roles", []) or []
            user_role_ids = {r.id for r in getattr(user, "roles", [])}
            if any(int(r) in user_role_ids for r in allowed):
                return True
        except Exception:
            self.logger.exception("can_user_edit kontrolü hata")
        return False

    async def _delayed_delete(self, msg: discord.Message, delay: int = 8):
        import asyncio
        try:
            await asyncio.sleep(delay)
            try:
                await msg.delete()
            except Exception:
                pass
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Allow natural-language (Turkish) panel changes when the bot is mentioned.

        Examples (Turkish):
        - @Bot uyarı eşiğini 4 yap
        - @Bot uyarı süresini 15 dakika yap
        - @Bot otomatik susturmayı kapat/aç
        - @Bot uyarı dm kapat/aç
        - @Bot panel rol ekle @rol
        """
        # ignore DMs and bots
        if not message.guild or message.author.bot:
            return

        # must mention bot
        if not self.bot.user.mentioned_in(message):
            return

        # check permission (owner or panel editor)
        author = message.author
        if not self.can_user_edit(message.guild, author):
            # allow owner-only reply
            try:
                await message.channel.send("❌ Bu işlemi yapmak için panel düzenleyici olmanız veya sunucu sahibi olmanız gerekir.")
            except Exception:
                pass
            return

        # strip mention and normalize (keep original for role-name detection)
        content = message.content.replace(f"<@{self.bot.user.id}>", "").replace(f"<@!{self.bot.user.id}>", "").strip()
        lc = content.lower()

        import re, asyncio

        # helper: convert Turkish/English number words to int (supports 0-99 approx)
        def word_to_int(s: str) -> int | None:
            s = s.strip().lower()
            # direct digits
            m = re.search(r"(\d+)", s)
            if m:
                return int(m.group(1))

            ones = {
                'sıfır':0,'bir':1,'iki':2,'üç':3,'dört':4,'bes':5,'beş':5,'altı':6,'alti':6,'yedi':7,'sekiz':8,'dokuz':9,
                'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'nine':9,'zero':0
            }
            teens = {
                'on':10,'onbir':11,'on bir':11,'oniki':12,'on iki':12,'onüç':13,'on üç':13,'ondört':14,'on dört':14,
                'onbes':15,'on beş':15,'onbeş':15,'onaltı':16,'on altı':16,'onyedi':17,'on yedi':17,'onsekiz':18,'on sekiz':18,'ondokuz':19,'on dokuz':19
            }
            tens = {'yirmi':20,'otuz':30,'kırk':40,'kirk':40,'elli':50,'altmış':60,'altmis':60}

            # try direct word maps
            if s in ones:
                return ones[s]
            if s in teens:
                return teens[s]
            if s in tens:
                return tens[s]

            # combined forms like 'yirmi bir' or 'yirmibir'
            for tword, tval in tens.items():
                if s.startswith(tword):
                    rest = s[len(tword):].strip()
                    if not rest:
                        return tval
                    # rest may be a ones word
                    if rest in ones:
                        return tval + ones[rest]
                    # numeric suffix
                    mm = re.match(r"(\d+)", rest)
                    if mm:
                        return tval + int(mm.group(1))

            # try splitting by space
            parts = s.split()
            total = 0
            found = False
            for p in parts:
                if p in tens:
                    total += tens[p]
                    found = True
                elif p in teens:
                    total += teens[p]
                    found = True
                elif p in ones:
                    total += ones[p]
                    found = True
                else:
                    mm = re.match(r"(\d+)", p)
                    if mm:
                        total += int(mm.group(1))
                        found = True
            if found:
                return total
            return None

        # Helper to send ephemeral-like confirmation (message auto-deletes) and DM user
        async def confirm(text: str):
            try:
                m = await message.channel.send(f"{message.author.mention} {text}")
                cfg = self.ayar_yukle().get(str(message.guild.id), {})
                ttl = int(cfg.get("panel_message_ttl", 8))
                asyncio.create_task(self._delayed_delete(m, ttl))
            except Exception:
                pass

        # 1) THRESHOLD: many variants
        m = re.search(r"(?:(uyarı\s*eşiği|eşik|threshold|limit|puan)\b.*?(\d+|[\w\s]+))|(?:\bset\b.*?\bthreshold\b.*?(\d+))|(?:\b(eşik)\s*(?:[:=])\s*(\d+|[\w\s]+))", lc)
        if m:
            # try numeric first
            val = None
            # capture any digits
            mm = re.search(r"(\d+)", lc)
            if mm:
                val = int(mm.group(1))
            else:
                # try to parse word numbers from the whole content
                w = word_to_int(lc)
                if w is not None:
                    val = w
            if val is None:
                await confirm("❌ Eşik değeri bulunamadı. Örnek: `@Bot uyarı eşiğini 3 yap`")
                return
            try:
                veriler = self.ayar_yukle()
                veriler.setdefault(str(message.guild.id), {})["auto_mute_threshold"] = int(val)
                self.ayar_kaydet(veriler)
                await confirm(f"✅ Uyarı eşiği {val} olarak ayarlandı.")
            except Exception:
                self.logger.exception("Doğal dil eşik ayarlanamadı")
                await message.channel.send("❌ Eşik ayarlanamadı.")
            return

        # 2) DURATION
        m = re.search(r"(uyarı\s*süresi|süre|duration)\s*(?:[:=\s]*)?(\d+|[\w\s]+)\s*(dakika|dk)?", lc)
        if m:
            # try digits then words
            mm = re.search(r"(\d+)", lc)
            if mm:
                val = int(mm.group(1))
            else:
                w = word_to_int(lc)
                if w is None:
                    await confirm("❌ Süre değeri bulunamadı. Örnek: `@Bot uyarı süresini 10 dakika yap`")
                    return
                val = w
            try:
                veriler = self.ayar_yukle()
                veriler.setdefault(str(message.guild.id), {})["auto_mute_minutes"] = val
                self.ayar_kaydet(veriler)
                await confirm(f"✅ Otomatik mute süresi {val} dakika olarak ayarlandı.")
            except Exception:
                self.logger.exception("Doğal dil süre ayarlanamadı")
                await message.channel.send("❌ Süre ayarlanamadı.")
            return

        # 3) ENABLE/DISABLE auto mute
        if re.search(r"otomatik\s*sustur|otomatik\s*susturma|auto[- ]?mute|otomatik", lc):
            if re.search(r"kapat|devre\s*dışı|pasif|kapalı|off|disable", lc):
                veriler = self.ayar_yukle()
                veriler.setdefault(str(message.guild.id), {})["auto_mute_enabled"] = False
                self.ayar_kaydet(veriler)
                await confirm("✅ Otomatik susturma kapatıldı.")
                return
            if re.search(r"aç|aktif|başlat|on|enable", lc):
                veriler = self.ayar_yukle()
                veriler.setdefault(str(message.guild.id), {})["auto_mute_enabled"] = True
                self.ayar_kaydet(veriler)
                await confirm("✅ Otomatik susturma açıldı.")
                return

        # 4) DM toggle
        if re.search(r"\b(dm|mesaj|uyarı\s*dm|uyarı\s*mesaj)\b", lc):
            if re.search(r"kapat|devre\s*dışı|kapalı|off|disable", lc):
                veriler = self.ayar_yukle()
                veriler.setdefault(str(message.guild.id), {})["send_warn_dm"] = False
                self.ayar_kaydet(veriler)
                await confirm("✅ Uyarı DM'leri kapatıldı.")
                return
            if re.search(r"aç|aktif|on|enable", lc):
                veriler = self.ayar_yukle()
                veriler.setdefault(str(message.guild.id), {})["send_warn_dm"] = True
                self.ayar_kaydet(veriler)
                await confirm("✅ Uyarı DM'leri açıldı.")
                return

        # 5) panel role add/remove via mention or role name
        m = re.search(r"panel\s+rol\s+ekle\s+(?:<@&?(\d+)>|@?([\w\sĞÜŞİÖÇğüşıöç-]+))", message.content)
        if m:
            rid = None
            if m.group(1):
                rid = int(m.group(1))
            else:
                # search by name
                name = (m.group(2) or "").strip()
                for r in message.guild.roles:
                    if r.name.lower() == name.lower():
                        rid = r.id
                        break
            if not rid:
                await message.channel.send(f"❌ Rol bulunamadı. Lütfen rolü mentionlayın veya tam rol adını kullanın.")
                return
            try:
                veriler = self.ayar_yukle()
                lst = veriler.setdefault(str(message.guild.id), {}).setdefault("panel_edit_roles", [])
                if rid in lst:
                    await message.channel.send("⚠️ Bu rol zaten listede.")
                    return
                lst.append(rid)
                self.ayar_kaydet(veriler)
                await confirm("✅ Rol panele düzenleyici olarak eklendi.")
            except Exception:
                self.logger.exception("Doğal dil rol ekleme başarısız")
                await message.channel.send("❌ Rol eklenemedi.")
            return

        m = re.search(r"panel\s+rol\s+(?:sil|kaldır)\s+(?:<@&?(\d+)>|@?([\w\sĞÜŞİÖÇğüşıöç-]+))", message.content)
        if m:
            rid = None
            if m.group(1):
                rid = int(m.group(1))
            else:
                name = (m.group(2) or "").strip()
                for r in message.guild.roles:
                    if r.name.lower() == name.lower():
                        rid = r.id
                        break
            if not rid:
                await message.channel.send(f"❌ Rol bulunamadı. Lütfen rolü mentionlayın veya tam rol adını kullanın.")
                return
            try:
                veriler = self.ayar_yukle()
                lst = veriler.setdefault(str(message.guild.id), {}).setdefault("panel_edit_roles", [])
                if rid not in lst:
                    await message.channel.send("⚠️ Bu rol listede değil.")
                    return
                lst = [r for r in lst if r != rid]
                veriler[str(message.guild.id)]["panel_edit_roles"] = lst
                self.ayar_kaydet(veriler)
                await confirm("✅ Rol panele düzenleyiciden kaldırıldı.")
            except Exception:
                self.logger.exception("Doğal dil rol silme başarısız")
                await message.channel.send("❌ Rol kaldırılamadı.")
            return

        # fallback: personalized help in channel + DM the user, and show ephemeral-like hint
        try:
            hint = (
                "Merhaba! Sanırım isteğinizi anlayamadım. Doğal dil komut örnekleri:\n"
                "• `@Bot uyarı eşiğini 3 yap`\n"
                "• `@Bot uyarı süresini 10 dakika yap`\n"
                "• `@Bot otomatik susturmayı kapat` veya `aç`\n"
                "• `@Bot uyarı dm kapat` veya `aç`\n"
                "• `@Bot panel rol ekle @Rol` veya `panel rol sil @Rol`\n"
                "Yapmak istediğiniz işlemi bu örneklere benzeterek tekrar yazabilirsiniz.")
            # channel personalized message (not persistent)
            ch_msg = await message.channel.send(f"{message.author.mention} {hint}")
            asyncio.create_task(self._delayed_delete(ch_msg, 18))
        except Exception:
            pass

    @commands.command(name="panel_set_ttl", aliases=["panel_ttl"]) 
    @commands.guild_only()
    async def panel_set_ttl(self, ctx, seconds: int):
        """Sunucu sahibi: panel ephemeral kanal mesaj TTL'sini saniye olarak ayarlar."""
        if ctx.author.id != ctx.guild.owner_id:
            await ctx.send("❌ Bu komutu yalnızca sunucu sahibi kullanabilir.")
            return
        if seconds < 1:
            await ctx.send("⚠️ TTL en az 1 saniye olmalı.")
            return
        veriler = self.ayar_yukle()
        if str(ctx.guild.id) not in veriler:
            veriler[str(ctx.guild.id)] = {}
        veriler[str(ctx.guild.id)]["panel_message_ttl"] = int(seconds)
        self.ayar_kaydet(veriler)
        await ctx.send(f"✅ Panel mesaj TTL'si {seconds} saniye olarak ayarlandı.")

    def ayar_yukle(self):
        return db.kv_get("settings", {}) or {}

    def ayar_kaydet(self, veri):
        try:
            db.kv_set("settings", veri)
        except Exception:
            self.logger.exception("Ayar kaydedilemedi")

    @commands.command(name="panel", aliases=["ayarlar", "dashboard"])
    async def panel(self, ctx):
        """
        Modern ve Orantılı Sunucu Yönetim Paneli
        """
        if not ctx.guild:
            await ctx.send("Bu komutu yalnızca sunucularda kullanabilirsin.")
            return
        embed = discord.Embed(
            title=f"✨ {ctx.guild.name} • Yönetim Paneli",
            description="Butonları kullanarak ayarları düzenleyin. (🔒 Sadece sunucu sahibi değişiklik yapabilir, yöneticiler görüntüleyebilir)",
            color=discord.Color.blurple()
        )
        thumb = ctx.guild.icon.url if ctx.guild.icon else self.bot.user.avatar.url
        embed.set_thumbnail(url=thumb)
        embed.add_field(name="👑 Yetki", value="Düzenleme: Sunucu sahibi\nGörüntüleme: Yönetici", inline=True)
        embed.add_field(name="⚡ Hızlı Bilgi", value="Butonlar: Aç/Kapat • Seçici: Komut ayarları", inline=True)
        embed.add_field(name="⠀", value="⠀", inline=False)
        embed.add_field(
            name="Özellikler",
            value=(
                "• Link/Caps/Küfür engeli\n"
                "• Resimli hoşgeldin, Level sistemi\n"
                "• Otomatik susturma, Uyarı eşiği/süresi/DM\n"
                "• Komut ayarları (aç/kapat, DM, özel metin)\n"
                "• Varsayılanları sıfırla (sadece sahibi)"
            ),
            inline=False
        )
        embed.set_footer(text="TrAI • Panel", icon_url=self.bot.user.avatar.url)

        view = DashboardView(self, str(ctx.guild.id))
        await ctx.send(embed=embed, view=view)


class DashboardView(discord.ui.View):
    def __init__(self, cog, guild_id):
        super().__init__(timeout=None)
        self.cog = cog
        self.guild_id = guild_id
        self.veriler = self.cog.ayar_yukle()
        if self.guild_id not in self.veriler:
            self.veriler[self.guild_id] = {}

        self.butonlari_guncelle()

    def butonlari_guncelle(self):
        self.clear_items()
        # Header: Moderasyon
        hdr_mod = discord.ui.Button(label="— Moderasyon —", style=discord.ButtonStyle.gray, disabled=True)
        self.add_item(hdr_mod)

        ayarlar = [
            ("link_engel", "Link Engel", "🔗"),
            ("caps_engel", "Caps Engel", "🔠"),
            ("kufur_engel", "Küfür Engel", "🤬")
        ]

        for key, label, emoji in ayarlar:
            durum = self.veriler[self.guild_id].get(key, False)
            style = discord.ButtonStyle.success if durum else discord.ButtonStyle.danger
            btn = discord.ui.Button(label=label, style=style, custom_id=key, emoji=emoji)
            btn.callback = self.create_callback(key, label)
            self.add_item(btn)

        guild_settings = self.veriler[self.guild_id]
        auto_enabled = guild_settings.get("auto_mute_enabled", True)
        auto_style = discord.ButtonStyle.success if auto_enabled else discord.ButtonStyle.danger
        btn_auto = discord.ui.Button(label="Otomatik Susturma", style=auto_style, custom_id="auto_mute_enabled", emoji="🤖")
        btn_auto.callback = self.create_toggle_callback("auto_mute_enabled", "Otomatik Susturma")
        self.add_item(btn_auto)

        btn_thresh = discord.ui.Button(label="Uyarı Eşiği", style=discord.ButtonStyle.secondary, custom_id="auto_mute_threshold", emoji="⚖️")
        btn_thresh.callback = self.create_modal_callback("auto_mute_threshold", "Uyarı Eşiği (adet)")
        self.add_item(btn_thresh)

        btn_dur = discord.ui.Button(label="Uyarı Süresi", style=discord.ButtonStyle.secondary, custom_id="auto_mute_minutes", emoji="⏱️")
        btn_dur.callback = self.create_modal_callback("auto_mute_minutes", "Uyarı Süresi (dakika)")
        self.add_item(btn_dur)

        dm_enabled = guild_settings.get("send_warn_dm", True)
        dm_style = discord.ButtonStyle.success if dm_enabled else discord.ButtonStyle.danger
        btn_dm = discord.ui.Button(label="Uyarı DM", style=dm_style, custom_id="send_warn_dm", emoji="✉️")
        btn_dm.callback = self.create_toggle_callback("send_warn_dm", "Uyarı DM")
        self.add_item(btn_dm)

        # Header: Çekiliş
        hdr_give = discord.ui.Button(label="— Çekiliş —", style=discord.ButtonStyle.gray, disabled=True)
        self.add_item(hdr_give)
        btn_give = discord.ui.Button(label="Çekiliş Komutları", style=discord.ButtonStyle.secondary, custom_id="giveaway_help", emoji="🎉")
        async def give_cb(interaction: discord.Interaction):
            await interaction.response.send_message(
                "Çekiliş komutları: `!çekiliş başlat`, `!çekiliş bitir`, `!çekiliş reroll` gibi komutları kullanabilirsin.",
                ephemeral=True,
            )
        btn_give.callback = give_cb
        self.add_item(btn_give)

        # Header: Bilet
        hdr_ticket = discord.ui.Button(label="— Bilet (Ticket) —", style=discord.ButtonStyle.gray, disabled=True)
        self.add_item(hdr_ticket)
        btn_ticket = discord.ui.Button(label="Bilet Komutları", style=discord.ButtonStyle.secondary, custom_id="ticket_help", emoji="🎫")
        async def ticket_cb(interaction: discord.Interaction):
            await interaction.response.send_message(
                "Bilet açmak için: `@Bot ticket kur` yaz, çıkan butona tıkla.",
                ephemeral=True,
            )
        btn_ticket.callback = ticket_cb
        self.add_item(btn_ticket)

        # Header: Sohbet
        hdr_chat = discord.ui.Button(label="— Sohbet —", style=discord.ButtonStyle.gray, disabled=True)
        self.add_item(hdr_chat)

        sohbet_ayarlar = [
            ("hosgeldin_resmi", "Resimli Hoşgeldin", "🖼️"),
            ("level_sistemi", "Level Sistemi", "📈")
        ]
        for key, label, emoji in sohbet_ayarlar:
            durum = self.veriler[self.guild_id].get(key, False)
            style = discord.ButtonStyle.success if durum else discord.ButtonStyle.danger
            btn = discord.ui.Button(label=label, style=style, custom_id=key, emoji=emoji)
            btn.callback = self.create_callback(key, label)
            self.add_item(btn)

        # Komut Ayarları (Sohbet altında)
        hdr_cmds = discord.ui.Button(label="— Komut Ayarları —", style=discord.ButtonStyle.gray, disabled=True)
        self.add_item(hdr_cmds)

        komut_aciklamalari = {
            "sil": "Belirtilen kadar mesajı siler.",
            "uyar": "Bir kullanıcıya uyarı verir.",
            "ban": "Kullanıcıyı sunucudan yasaklar.",
            "kick": "Kullanıcıyı sunucudan atar.",
            "mute": "Kullanıcıyı belirli süre susturur.",
            "unmute": "Susturulan kullanıcının susturmasını kaldırır.",
            "warns": "Uyarıları listeler.",
            "unwarn": "Belirtilen uyarı ID'sini siler.",
            "clearwarns": "Kullanıcının veya tüm uyarıları temizler.",
            "set_warn_threshold": "Otomatik susturma uyarı eşiğini ayarlar.",
            "set_warn_duration": "Otomatik susturma süresini ayarlar.",
            "get_warn_settings": "Otomatik susturma ayarlarını gösterir.",
            "panel": "Sunucu yönetim panelini açar.",
            "panel_rol_ekle": "Panel düzenleyici rol ekler.",
            "panel_rol_sil": "Panel düzenleyici rolü kaldırır.",
            "panel_roller": "Panel düzenleyici rolleri listeler.",
            "panel_admin_duzenle": "Yöneticilere panel düzenleme izni verir/kaldırır.",
            "panel_debug": "Panel debug bilgilerini gösterir.",
            "komutlar": "Botta yüklü tüm komutları listeler.",
            "yardim": "Botun yardım menüsünü gösterir.",
            "ping": "Botun gecikme süresini gösterir.",
            "unut": "Botun hafızasını sıfırlar.",
            "rank": "Kullanıcı seviyesini gösterir."
        }
        options = []
        for cmd in sorted(self.cog.bot.commands, key=lambda c: c.name):
            label = cmd.name.replace("_", " ").title()
            desc = komut_aciklamalari.get(cmd.name, "Kısa açıklama bulunamadı.")
            options.append(discord.SelectOption(label=label, description=desc, value=cmd.name))

        if options:
            select = discord.ui.Select(placeholder="Ayarlarını düzenlemek istediğiniz komutu seçin...", min_values=1, max_values=1, options=options)
            async def sel_callback(interaction: discord.Interaction):
                cmd_name = select.values[0]
                aciklama = komut_aciklamalari.get(cmd_name, "Kısa açıklama bulunamadı.")
                embed = discord.Embed(title=f"Komut Ayarları: {cmd_name}", description=aciklama, color=discord.Color.blurple())
                await interaction.response.send_message(embed=embed, view=CommandSettingsView(self.cog, self.guild_id, cmd_name), ephemeral=True)

            select.callback = sel_callback
            self.add_item(select)

        # Header: Yardım & Sıfırlama
        hdr_help = discord.ui.Button(label="— Yardım & Sıfırlama —", style=discord.ButtonStyle.gray, disabled=True)
        self.add_item(hdr_help)

        btn_help = discord.ui.Button(label="Yardım", style=discord.ButtonStyle.secondary, custom_id="help_btn", emoji="❓")
        async def help_cb(interaction: discord.Interaction):
            await interaction.response.send_message(
                "Panel: Düzenlemeler yalnızca sunucu sahibine aittir. Komut ayarlarını buradan açıp düzenleyebilirsiniz.\n"
                "- Otomatik Susturma: uyarı eşiği ve süresi.\n"
                "- Komut Ayarları: komutu kapatma, DM gönderme veya özel metin ekleme.", ephemeral=True)

        btn_help.callback = help_cb
        self.add_item(btn_help)

        btn_reset = discord.ui.Button(label="Varsayılanları Sıfırla", style=discord.ButtonStyle.danger, custom_id="reset_defaults", emoji="♻️")
        async def reset_cb(interaction: discord.Interaction):
            guild = self.cog.bot.get_guild(int(self.guild_id))
            owner_id = guild.owner_id if guild else None
            if interaction.user.id != owner_id:
                await interaction.response.send_message("❌ Bu işlemi sadece sunucu sahibi yapabilir.", ephemeral=True)
                return
            modal = ResetConfirmModal(self.cog, self.guild_id)
            await interaction.response.send_modal(modal)

        btn_reset.callback = reset_cb
        self.add_item(btn_reset)

    @commands.command(name="panel_rol_ekle", aliases=["panel_add_role"]) 
    @commands.guild_only()
    async def panel_rol_ekle(self, ctx, role: discord.Role):
        """Sunucu sahibi: panele düzenleme yetkisi verecek rol ekle."""
        if ctx.author.id != ctx.guild.owner_id:
            await ctx.send("❌ Bu komutu yalnızca sunucu sahibi kullanabilir.")
            return
        veriler = self.ayar_yukle()
        if str(ctx.guild.id) not in veriler:
            veriler[str(ctx.guild.id)] = {}
        lst = veriler[str(ctx.guild.id)].get("panel_edit_roles", []) or []
        if role.id in lst:
            await ctx.send("⚠️ Bu rol zaten yetkili.")
            return
        lst.append(role.id)
        veriler[str(ctx.guild.id)]["panel_edit_roles"] = lst
        self.ayar_kaydet(veriler)
        await ctx.send(f"✅ {role.mention} rolü panele düzenleme yetkisi olarak eklendi.")

    @commands.command(name="panel_rol_sil", aliases=["panel_remove_role"]) 
    @commands.guild_only()
    async def panel_rol_sil(self, ctx, role: discord.Role):
        """Sunucu sahibi: panele düzenleme yetkisi veren rolü kaldır."""
        if ctx.author.id != ctx.guild.owner_id:
            await ctx.send("❌ Bu komutu yalnızca sunucu sahibi kullanabilir.")
            return
        veriler = self.ayar_yukle()
        lst = veriler.get(str(ctx.guild.id), {}).get("panel_edit_roles", []) or []
        if role.id not in lst:
            await ctx.send("⚠️ Bu rol yetkili listesinde değil.")
            return
        lst = [r for r in lst if r != role.id]
        veriler[str(ctx.guild.id)]["panel_edit_roles"] = lst
        self.ayar_kaydet(veriler)
        await ctx.send(f"✅ {role.mention} rolü panel düzenleyicilerinden kaldırıldı.")

    @commands.command(name="panel_roller", aliases=["panel_roles"]) 
    @commands.guild_only()
    async def panel_roller(self, ctx):
        """Panel düzenleyici rollerini listeler."""
        veriler = self.ayar_yukle()
        lst = veriler.get(str(ctx.guild.id), {}).get("panel_edit_roles", []) or []
        if not lst:
            await ctx.send("🔎 Henüz panel için özel bir düzenleyici rol tanımlanmamış.")
            return
        mentions = []
        for rid in lst:
            role = ctx.guild.get_role(int(rid))
            if role:
                mentions.append(role.mention)
        await ctx.send("Panel düzenleyici roller: " + (", ".join(mentions) if mentions else "(roller silinmiş veya bulunamadı)"))

    @commands.command(name="panel_admin_duzenle", aliases=["panel_admin_edit"]) 
    @commands.guild_only()
    async def panel_admin_duzenle(self, ctx, allow: bool):
        """Sunucu sahibi: yöneticilere panel düzenleme izni ver/kaldır (True/False)."""
        if ctx.author.id != ctx.guild.owner_id:
            await ctx.send("❌ Bu komutu yalnızca sunucu sahibi kullanabilir.")
            return
        veriler = self.ayar_yukle()
        if str(ctx.guild.id) not in veriler:
            veriler[str(ctx.guild.id)] = {}
        veriler[str(ctx.guild.id)]["allow_admin_edit"] = bool(allow)
        self.ayar_kaydet(veriler)
        await ctx.send(f"✅ Yöneticilerin panel düzenleme izni {'verildi' if allow else 'kaldırıldı'}. ")

    @commands.command(name="panel_debug", aliases=["panel_debug_info"]) 
    @commands.guild_only()
    async def panel_debug(self, ctx):
        """Sahip/izin debug: Owner ID, sizin ID'niz, can_user_edit sonucu ve panel ayarlarını gösterir."""
        try:
            guild = ctx.guild
            owner = guild.owner_id if guild else None
            author_id = ctx.author.id
            can_edit = self.can_user_edit(guild, ctx.author)
            veriler = self.ayar_yukle()
            guild_conf = veriler.get(str(guild.id), {}) if guild else {}
            panel_roles = guild_conf.get("panel_edit_roles", [])
            allow_admin = guild_conf.get("allow_admin_edit", False)

            msg = (
                f"Sunucu sahibi ID: {owner}\n"
                f"Senin ID: {author_id}\n"
                f"can_user_edit sonucu: {can_edit}\n"
                f"panel_edit_roles: {panel_roles}\n"
                f"allow_admin_edit: {allow_admin}\n"
            )
            await ctx.author.send(f"`panel_debug` bilgileri (gizli):\n{msg}")
            await ctx.send("✅ Panel debug bilgilerini DM ile gönderdim.")
        except Exception:
            await ctx.send("❌ Debug bilgileri alınamadı.")

    def create_callback(self, key, label):
        async def callback(interaction: discord.Interaction):
            # only owner or allowed panel editors can interact
            guild = self.cog.bot.get_guild(int(self.guild_id))
            if not self.cog.can_user_edit(guild, interaction.user):
                await interaction.response.send_message("❌ Bu paneli düzenleme yetkiniz yok.", ephemeral=True)
                return

            mevcut = self.veriler[self.guild_id].get(key, False)
            self.veriler[self.guild_id][key] = not mevcut
            self.cog.ayar_kaydet(self.veriler)

            self.butonlari_guncelle()
            await interaction.response.edit_message(view=self)

            durum_text = "✅ AÇILDI" if not mevcut else "❌ KAPATILDI"
            await interaction.followup.send(f"⚙️ **{label}** sistemi {durum_text}!", ephemeral=True)

        return callback

    def create_toggle_callback(self, key, label):
        async def callback(interaction: discord.Interaction):
            guild = self.cog.bot.get_guild(int(self.guild_id))
            if not self.cog.can_user_edit(guild, interaction.user):
                await interaction.response.send_message("❌ Bu paneli düzenleme yetkiniz yok.", ephemeral=True)
                return

            mevcut = self.veriler[self.guild_id].get(key, False)
            self.veriler[self.guild_id][key] = not mevcut
            self.cog.ayar_kaydet(self.veriler)

            self.butonlari_guncelle()
            await interaction.response.edit_message(view=self)
            durum_text = "✅ AÇILDI" if not mevcut else "❌ KAPATILDI"
            await interaction.followup.send(f"⚙️ **{label}** ayarı {durum_text}!", ephemeral=True)

        return callback

    def create_modal_callback(self, key, field_label):
        async def callback(interaction: discord.Interaction):
            guild = self.cog.bot.get_guild(int(self.guild_id))
            if not self.cog.can_user_edit(guild, interaction.user):
                await interaction.response.send_message("❌ Bu paneli düzenleme yetkiniz yok.", ephemeral=True)
                return

            modal = SettingsModal(self.cog, self.guild_id, key, field_label)
            await interaction.response.send_modal(modal)

        return callback


class SettingsModal(discord.ui.Modal):
    def __init__(self, cog, guild_id, key, field_label: str):
        super().__init__(title=field_label)
        self.cog = cog
        self.guild_id = guild_id
        self.key = key
        self.add_item(discord.ui.TextInput(label=field_label, placeholder="Sadece sayı giriniz", required=True, style=discord.TextStyle.short))

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # take first child value
            val = self.children[0].value.strip()
            num = int(val)
        except Exception:
            await interaction.response.send_message("❌ Geçersiz değer, sayı giriniz.", ephemeral=True)
            return

        try:
            veriler = self.cog.ayar_yukle()
            if self.guild_id not in veriler:
                veriler[self.guild_id] = {}
            veriler[self.guild_id][self.key] = num
            self.cog.ayar_kaydet(veriler)
            # refresh view if message exists
            # find the previous message and update view - interaction.message is the modal trigger message
            await interaction.response.send_message(f"✅ Ayar kaydedildi: {num}", ephemeral=True)
        except Exception:
            self.cog.logger.exception("Ayar modalı kaydedilemedi")
            await interaction.response.send_message("❌ Ayar kaydedilemedi.", ephemeral=True)


class CommandSettingsView(discord.ui.View):
    def __init__(self, cog, guild_id: str, command_name: str):
        super().__init__(timeout=None)
        self.cog = cog
        self.guild_id = guild_id
        self.command_name = command_name
        self.veriler = self.cog.ayar_yukle()
        if self.guild_id not in self.veriler:
            self.veriler[self.guild_id] = {}
        if "commands" not in self.veriler[self.guild_id]:
            self.veriler[self.guild_id]["commands"] = {}
        if self.command_name not in self.veriler[self.guild_id]["commands"]:
            # defaults
            self.veriler[self.guild_id]["commands"][self.command_name] = {
                "enabled": True,
                "send_dm": True,
                "custom_text": ""
            }
        self.cmd_conf = self.veriler[self.guild_id]["commands"][self.command_name]
        self.build_items()

    def build_items(self):
        self.clear_items()
        enabled = bool(self.cmd_conf.get("enabled", True))
        dm = bool(self.cmd_conf.get("send_dm", True))

        btn_enable = discord.ui.Button(label=("Etkin" if enabled else "Kapalı"), style=(discord.ButtonStyle.success if enabled else discord.ButtonStyle.danger), custom_id="cmd_enable")
        btn_enable.callback = self.toggle_enable
        self.add_item(btn_enable)

        btn_dm = discord.ui.Button(label=("DM Gönder" if dm else "DM Kapalı"), style=(discord.ButtonStyle.success if dm else discord.ButtonStyle.danger), custom_id="cmd_dm")
        btn_dm.callback = self.toggle_dm
        self.add_item(btn_dm)

        btn_edit = discord.ui.Button(label="Özel Metni Düzenle", style=discord.ButtonStyle.secondary, custom_id="cmd_edit")
        btn_edit.callback = self.open_edit_modal
        self.add_item(btn_edit)

        # summary button (disabled) to show current custom text length
        txt = self.cmd_conf.get("custom_text", "")
        info = discord.ui.Button(label=f"Metin: {len(txt)} karakter", style=discord.ButtonStyle.gray, disabled=True)
        self.add_item(info)

    async def toggle_enable(self, interaction: discord.Interaction):
        try:
            # permission check
            guild = self.cog.bot.get_guild(int(self.guild_id))
            if not self.cog.can_user_edit(guild, interaction.user):
                await interaction.response.send_message("❌ Bu komutu düzenleme yetkiniz yok.", ephemeral=True)
                return

            cur = bool(self.cmd_conf.get("enabled", True))
            self.cmd_conf["enabled"] = not cur
            self.cog.ayar_kaydet(self.veriler)
            self.build_items()
            await interaction.response.edit_message(view=self)
            await interaction.followup.send(f"✅ `{self.command_name}` komutu {'etkinleştirildi' if not cur else 'devre dışı bırakıldı'}.", ephemeral=True)
        except Exception:
            self.cog.logger.exception("Komut ayarı değiştirilemedi")
            await interaction.response.send_message("❌ Hata oluştu.", ephemeral=True)

    async def toggle_dm(self, interaction: discord.Interaction):
        try:
            guild = self.cog.bot.get_guild(int(self.guild_id))
            if not self.cog.can_user_edit(guild, interaction.user):
                await interaction.response.send_message("❌ Bu komutu düzenleme yetkiniz yok.", ephemeral=True)
                return

            cur = bool(self.cmd_conf.get("send_dm", True))
            self.cmd_conf["send_dm"] = not cur
            self.cog.ayar_kaydet(self.veriler)
            self.build_items()
            await interaction.response.edit_message(view=self)
            await interaction.followup.send(f"✅ `{self.command_name}` için DM {'açıldı' if not cur else 'kapatıldı'}.", ephemeral=True)
        except Exception:
            self.cog.logger.exception("DM ayarı değiştirilemedi")
            await interaction.response.send_message("❌ Hata oluştu.", ephemeral=True)

    async def open_edit_modal(self, interaction: discord.Interaction):
        guild = self.cog.bot.get_guild(int(self.guild_id))
        if not self.cog.can_user_edit(guild, interaction.user):
            await interaction.response.send_message("❌ Bu komutu düzenleme yetkiniz yok.", ephemeral=True)
            return
        modal = CommandTextModal(self.cog, self.guild_id, self.command_name)
        await interaction.response.send_modal(modal)


class CommandTextModal(discord.ui.Modal):
    def __init__(self, cog, guild_id: str, command_name: str):
        super().__init__(title=f"{command_name} - Özel Metin")
        self.cog = cog
        self.guild_id = guild_id
        self.command_name = command_name
        # current value
        veriler = self.cog.ayar_yukle()
        cur = ""
        if guild_id in veriler and "commands" in veriler[guild_id] and command_name in veriler[guild_id]["commands"]:
            cur = veriler[guild_id]["commands"][command_name].get("custom_text", "")
        self.add_item(discord.ui.TextInput(label="Özel Mesaj (kullanıcıya gönderilecek)", style=discord.TextStyle.paragraph, default=cur, required=False))

    async def on_submit(self, interaction: discord.Interaction):
        try:
            val = self.children[0].value
            veriler = self.cog.ayar_yukle()
            if self.guild_id not in veriler:
                veriler[self.guild_id] = {}
            if "commands" not in veriler[self.guild_id]:
                veriler[self.guild_id]["commands"] = {}
            if self.command_name not in veriler[self.guild_id]["commands"]:
                veriler[self.guild_id]["commands"][self.command_name] = {}
            veriler[self.guild_id]["commands"][self.command_name]["custom_text"] = val
            self.cog.ayar_kaydet(veriler)
            await interaction.response.send_message("✅ Özel metin kaydedildi.", ephemeral=True)
        except Exception:
            self.cog.logger.exception("Özel metin kaydedilemedi")
            await interaction.response.send_message("❌ Kaydedilemedi.", ephemeral=True)


class ResetConfirmModal(discord.ui.Modal):
    def __init__(self, cog, guild_id: str):
        super().__init__(title="Varsayılanları Sıfırla")
        self.cog = cog
        self.guild_id = guild_id
        self.add_item(discord.ui.TextInput(label="Onaylamak için 'SIFIRLA' yazın", placeholder="SIFIRLA", required=True))

    async def on_submit(self, interaction: discord.Interaction):
        try:
            txt = self.children[0].value.strip()
            if txt.upper() != "SIFIRLA":
                await interaction.response.send_message("İşlem iptal edildi: yanlış onay.", ephemeral=True)
                return
            veriler = self.cog.ayar_yukle()
            if self.guild_id in veriler:
                veriler.pop(self.guild_id, None)
                self.cog.ayar_kaydet(veriler)
            await interaction.response.send_message("✅ Sunucu ayarları varsayılanlara sıfırlandı.", ephemeral=True)
        except Exception:
            self.cog.logger.exception("Varsayılan sıfırlama başarısız")
            await interaction.response.send_message("❌ Sıfırlama sırasında hata oluştu.", ephemeral=True)

    # =========================================================================
    # SLASH KOMUTLAR (Discord / Menüsü için)
    # =========================================================================

    @app_commands.command(name="panel", description="🎛️ Sunucu ayar panelini açar (moderasyon, çekiliş, bilet, sohbet)")
    @app_commands.checks.has_permissions(administrator=True)
    async def panel_slash(self, interaction: discord.Interaction):
        """Slash komut ile panel açar."""
        view = DashboardView(self, str(interaction.guild.id))
        embed = discord.Embed(
            title="🎛️ Sunucu Kontrol Paneli",
            description=(
                "**Kategoriler:**\n"
                "━━━━━━━━━━━━━━━━\n"
                "🛡️ **Moderasyon** - Link/Caps/Küfür engel, Uyarı sistemi\n"
                "🎉 **Çekiliş** - Çekiliş komutları\n"
                "🎫 **Bilet** - Ticket sistemi\n"
                "💬 **Sohbet** - Hoşgeldin mesajı, Level sistemi\n\n"
                "Aşağıdaki butonlarla ayarları düzenleyin!"
            ),
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Sunucu: {interaction.guild.name} | Komut kullanan: {interaction.user.name}")
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="ayarlar", description="⚙️ Sunucu ayarlarını gösterir")
    async def ayarlar_slash(self, interaction: discord.Interaction):
        """Mevcut sunucu ayarlarını gösterir."""
        veriler = self.ayar_yukle()
        guild_conf = veriler.get(str(interaction.guild.id), {})
        
        if not guild_conf:
            await interaction.response.send_message("❌ Bu sunucu için henüz ayar yapılmamış.", ephemeral=True)
            return
        
        embed = discord.Embed(title="⚙️ Sunucu Ayarları", color=discord.Color.green())
        
        # Moderasyon
        mod_text = []
        mod_text.append(f"🔗 Link Engel: {'✅ Açık' if guild_conf.get('link_engel') else '❌ Kapalı'}")
        mod_text.append(f"🔠 Caps Engel: {'✅ Açık' if guild_conf.get('caps_engel') else '❌ Kapalı'}")
        mod_text.append(f"🤬 Küfür Engel: {'✅ Açık' if guild_conf.get('kufur_engel') else '❌ Kapalı'}")
        mod_text.append(f"🤖 Otomatik Susturma: {'✅ Açık' if guild_conf.get('auto_mute_enabled', True) else '❌ Kapalı'}")
        mod_text.append(f"⚖️ Uyarı Eşiği: {guild_conf.get('auto_mute_threshold', 3)} adet")
        mod_text.append(f"⏱️ Uyarı Süresi: {guild_conf.get('auto_mute_minutes', 10)} dakika")
        embed.add_field(name="🛡️ Moderasyon", value="\n".join(mod_text), inline=False)
        
        # Sohbet
        chat_text = []
        hosg_msg = guild_conf.get('hosgeldin_mesaji', 'Varsayılan')
        if len(hosg_msg) > 50:
            hosg_msg = hosg_msg[:50] + "..."
        chat_text.append(f"👋 Hoşgeldin: {hosg_msg}")
        aktif_kanal = guild_conf.get('aktif_kanal')
        if aktif_kanal:
            chat_text.append(f"💬 AI Kanal: <#{aktif_kanal}>")
        embed.add_field(name="💬 Sohbet", value="\n".join(chat_text) if chat_text else "Ayar yok", inline=False)
        
        embed.set_footer(text=f"Ayarları değiştirmek için: /panel")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Dashboard(bot))
