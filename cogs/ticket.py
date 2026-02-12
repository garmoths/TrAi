import discord
from discord.ext import commands
import asyncio
import io
import datetime
from utils.helpers import is_recent_message, mark_recent_message
from utils.logger import get_logger
from utils import db


class Ticket(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = get_logger(__name__)

    def ayar_getir(self, guild_id):
        try:
            data = db.kv_get("settings", {}) or {}
            return data.get(str(guild_id), {})
        except Exception:
            self.logger.exception("Ayar getirilemedi")
            return {}

    class TicketCreateView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=None)

        @discord.ui.button(label="Destek Talebi Oluştur", style=discord.ButtonStyle.blurple, emoji="📩",
                           custom_id="ticket_create_btn")
        async def create_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
            # Zaten var mı kontrolü
            for channel in interaction.guild.text_channels:
                if channel.topic == str(interaction.user.id) and "ticket" in channel.name:
                    await interaction.response.send_message(f"❌ Zaten açık: {channel.mention}", ephemeral=True)
                    return

            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True,
                                                              attach_files=True),
                interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True,
                                                                  manage_channels=True)
            }

            channel = await interaction.guild.create_text_channel(
                name=f"ticket-{interaction.user.name}",
                overwrites=overwrites,
                topic=str(interaction.user.id),
                reason="Ticket Oluşturuldu"
            )

            await interaction.response.send_message(f"✅ Talebin açıldı: {channel.mention}", ephemeral=True)

            embed = discord.Embed(
                title="👋 Destek Talebi",
                description=f"Merhaba {interaction.user.mention}!\n\nYetkililer birazdan burada olacak.\nLütfen sorununuzu yazın.",
                color=discord.Color.green()
            )
            # Yönetici Paneli Butonlarını Ekliyoruz
            await channel.send(embed=embed, view=Ticket.TicketControlView())

    class TicketControlView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=None)

        @discord.ui.button(label="Kapat", style=discord.ButtonStyle.red, emoji="🔒", custom_id="ticket_close_btn")
        async def close_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_message("❓ Emin misin?", view=Ticket.TicketConfirmView(), ephemeral=True)

        # B) CLAIM (ÜSTLENME) BUTONU
        @discord.ui.button(label="İlgileniyorum", style=discord.ButtonStyle.green, emoji="🙋‍♂️",
                           custom_id="ticket_claim_btn")
        async def claim_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
            # Sadece yetkililer basabilir
            if not interaction.user.guild_permissions.manage_channels:
                await interaction.response.send_message("⛔ Bunu sadece yetkililer yapabilir.", ephemeral=True)
                return

            # Embed güncelleme
            embed = interaction.message.embeds[0]
            if "Yetkili:" in str(embed.footer.text):
                await interaction.response.send_message("❌ Bu talep zaten biri tarafından üstlenilmiş!", ephemeral=True)
                return

            embed.color = discord.Color.orange()
            embed.set_footer(text=f"Yetkili: {interaction.user.name} | İlgileniyor 🛠️",
                             icon_url=interaction.user.display_avatar.url)

            button.disabled = True  # Butonu kilitle
            button.label = f"Üstlenildi ({interaction.user.name})"

            await interaction.message.edit(embed=embed, view=self)
            await interaction.response.send_message(
                f"✅ {interaction.user.mention} bu talebi üstlendi! Diğer yetkililer, lütfen araya girmeyin.")

        # C) PING (ÇAĞIRMA) BUTONU
        @discord.ui.button(label="Ses Ver", style=discord.ButtonStyle.secondary, emoji="🔔", custom_id="ticket_ping_btn")
        async def ping_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
            # Kanal sahibini bul
            try:
                user_id = int(interaction.channel.topic)
                await interaction.channel.send(f"🔔 <@{user_id}>, yetkili seni bekliyor! Lütfen cevap ver.")
                await interaction.response.send_message("Bildirim gönderildi.", ephemeral=True)
            except Exception as e:
                cog = interaction.client.get_cog("Ticket")
                if cog:
                    cog.logger.debug("Ticket ping failed: %s", e)
                await interaction.response.send_message("Kullanıcı bulunamadı.", ephemeral=True)
        
        # D) TRANSKRİPT KAYDET BUTONU - YENİ!
        @discord.ui.button(label="Transcript", style=discord.ButtonStyle.secondary, emoji="📄", custom_id="ticket_transcript_btn")
        async def transcript_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.defer(ephemeral=True)
            
            channel = interaction.channel
            transcript = f"--- TICKET: {channel.name} ---\nKaydeden: {interaction.user.name}\nTarih: {datetime.datetime.now()}\n\n"
            
            messages = [msg async for msg in channel.history(limit=500, oldest_first=True)]
            for msg in messages:
                transcript += f"[{msg.created_at.strftime('%H:%M:%S')}] {msg.author.name}: {msg.content}\n"
            
            f = discord.File(io.BytesIO(transcript.encode("utf-8")), filename=f"{channel.name}.txt")
            await interaction.followup.send("📄 Transcript kayıt edildi:", file=f, ephemeral=True)

    # --- 3. ONAY VE LOGLAMA (Aynı Kalıyor) ---
    class TicketConfirmView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=60)

        @discord.ui.button(label="Evet, Kapat", style=discord.ButtonStyle.danger, emoji="✅")
        async def confirm_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
            channel = interaction.channel
            await interaction.response.send_message("🔒 Kayıt alınıyor ve kapatılıyor...")

            # Transcript Oluştur
            transcript = f"--- TICKET: {channel.name} ---\nKapatan: {interaction.user.name}\nTarih: {datetime.datetime.now()}\n\n"
            messages = [msg async for msg in channel.history(limit=500, oldest_first=True)]
            for msg in messages:
                transcript += f"[{msg.author.name}]: {msg.content}\n"

            f = discord.File(io.BytesIO(transcript.encode("utf-8")), filename=f"{channel.name}.txt")

            # Loglama
            try:
                cog = interaction.client.get_cog("Ticket")
                ayarlar = cog.ayar_getir(interaction.guild.id)
                if ayarlar.get("log_kanali"):
                    log_ch = interaction.guild.get_channel(ayarlar["log_kanali"])
                    f_copy = discord.File(io.BytesIO(transcript.encode("utf-8")), filename=f"{channel.name}.txt")
                    await log_ch.send(f"🎫 **{channel.name}** kapatıldı.", file=f_copy)
            except Exception as e:
                import logging
                logging.getLogger(__name__).exception("Failed to log ticket transcript: %s", e)

            await asyncio.sleep(2)
            await channel.delete()

    # --- KOMUT ---
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild: return
        if is_recent_message(message.id): return
        if not self.bot.user.mentioned_in(message): return
        if not message.author.guild_permissions.administrator: return

        if "ticket" in message.content.lower() and "kur" in message.content.lower():
            embed = discord.Embed(title="🎫 Destek", description="Destek almak için butona tıkla.",
                                  color=discord.Color.blue())
            await message.channel.send(embed=embed, view=self.TicketCreateView())
            mark_recent_message(message.id)
            await message.delete()

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(self.TicketCreateView())
        self.bot.add_view(self.TicketControlView())


async def setup(bot):
    await bot.add_cog(Ticket(bot))