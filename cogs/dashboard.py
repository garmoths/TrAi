import discord
from discord.ext import commands
import json
import os

SETTINGS_FILE = "settings.json"


class Dashboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def ayar_yukle(self):
        if not os.path.exists(SETTINGS_FILE): return {}
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    def ayar_kaydet(self, veri):
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(veri, f, indent=4)

    @commands.command(name="panel", aliases=["ayarlar", "dashboard"])
    @commands.has_permissions(administrator=True)
    async def panel(self, ctx):
        """Sunucu Yönetim Paneli"""
        embed = discord.Embed(
            title=f"⚙️ {ctx.guild.name} Kontrol Merkezi",
            description="Bot özelliklerini yönetmek için butonları kullan.",
            color=discord.Color.from_rgb(47, 49, 54)  # Discord koyu tema rengi
        )
        embed.set_thumbnail(url=self.bot.user.avatar.url)
        embed.add_field(name="Durum", value="🟢 Yeşil: Açık\n🔴 Kırmızı: Kapalı", inline=False)

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

        # Senin settings.json ile %100 uyumlu anahtarlar:
        ayarlar = [
            ("link_engel", "Link Engel", "🔗"),
            ("caps_engel", "Caps Engel", "🔠"),
            ("kufur_engel", "Küfür Engel", "🤬"),
            ("hosgeldin_resmi", "Resimli Hoşgeldin", "🖼️"),
            ("level_sistemi", "Level Sistemi", "📈")
        ]

        for key, label, emoji in ayarlar:
            durum = self.veriler[self.guild_id].get(key, False)
            # Açıksa Yeşil (Success), Kapalıysa Gri/Kırmızı (Secondary/Danger)
            style = discord.ButtonStyle.success if durum else discord.ButtonStyle.danger

            btn = discord.ui.Button(label=label, style=style, custom_id=key, emoji=emoji)
            btn.callback = self.create_callback(key, label)
            self.add_item(btn)

    def create_callback(self, key, label):
        async def callback(interaction: discord.Interaction):
            mevcut = self.veriler[self.guild_id].get(key, False)
            self.veriler[self.guild_id][key] = not mevcut
            self.cog.ayar_kaydet(self.veriler)

            self.butonlari_guncelle()
            await interaction.response.edit_message(view=self)

            durum_text = "✅ AÇILDI" if not mevcut else "❌ KAPATILDI"
            await interaction.followup.send(f"⚙️ **{label}** sistemi {durum_text}!", ephemeral=True)

        return callback


async def setup(bot):
    await bot.add_cog(Dashboard(bot))