import discord
from discord.ext import commands
import asyncio
import random
import datetime
import re
import json
import os

DB_FILE = "giveaways.json"


class Giveaway(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.aktif_cekilisler = {}
        self.son_biten_cekilis = {'katilimcilar': [], 'odul': "Bilinmiyor"}
        self.bot.loop.create_task(self.veritabani_yukle())

    # --- VERİTABANI İŞLEMLERİ ---
    def kaydet(self):
        data = {}
        for cid, v in self.aktif_cekilisler.items():
            data[cid] = {
                "bitis": v["bitis"].timestamp(),
                "kanal_id": v["kanal_id"], "mesaj_id": v["mesaj_id"], "odul": v["odul"],
                "katilimcilar": list(v["view"].katilimcilar),
                "kazanan_sayisi": v.get("kazanan_sayisi", 1),
                "rol_sarti": v.get("rol_sarti", None)
            }
        with open(DB_FILE, "w", encoding="utf-8") as f: json.dump(data, f, indent=4)

    async def veritabani_yukle(self):
        await self.bot.wait_until_ready()
        if not os.path.exists(DB_FILE): return
        try:
            with open(DB_FILE, "r") as f:
                data = json.load(f)
            for cid, v in data.items():
                try:
                    kanal = self.bot.get_channel(v["kanal_id"])
                    if not kanal: continue
                    msg = await kanal.fetch_message(v["mesaj_id"])

                    kazanan_sayisi = v.get("kazanan_sayisi", 1)
                    rol_sarti = v.get("rol_sarti", None)
                    bitis = datetime.datetime.fromtimestamp(v["bitis"])
                    kalan = (bitis - datetime.datetime.now()).total_seconds()
                    if kalan <= 0: kalan = 1

                    view = self.CekilisButonu(kalan, msg.embeds[0], rol_sarti)
                    view.katilimcilar = set(v["katilimcilar"])
                    view.guncelle_label()

                    self.aktif_cekilisler[cid] = {
                        "task": asyncio.create_task(self.cekilis_zamanlayici(kalan, cid, kanal)),
                        "view": view, "message": msg, "odul": v["odul"],
                        "kanal_id": v["kanal_id"], "mesaj_id": v["mesaj_id"], "bitis": bitis,
                        "kazanan_sayisi": kazanan_sayisi, "rol_sarti": rol_sarti
                    }
                    self.bot.add_view(view)
                except:
                    pass
        except:
            pass

    # --- BUTON ---
    class CekilisButonu(discord.ui.View):
        def __init__(self, sure_saniye, embed, rol_sarti=None):
            super().__init__(timeout=None)
            self.katilimcilar = set()
            self.embed = embed
            self.rol_sarti = rol_sarti

        def guncelle_label(self):
            for child in self.children:
                if child.custom_id == "cekilis_katil":
                    child.label = f"Çekilişe Katıl ({len(self.katilimcilar)})"

        @discord.ui.button(label="Çekilişe Katıl (0)", style=discord.ButtonStyle.blurple, emoji="🎉",
                           custom_id="cekilis_katil")
        async def katil_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
            if self.rol_sarti:
                user_roles = [r.id for r in interaction.user.roles]
                if self.rol_sarti not in user_roles:
                    rol_obj = interaction.guild.get_role(self.rol_sarti)
                    r_adi = rol_obj.name if rol_obj else "Gerekli Rol"
                    await interaction.response.send_message(f"⛔ Katılmak için **@{r_adi}** rolü lazım!", ephemeral=True)
                    return

            if interaction.user.id in self.katilimcilar:
                await interaction.response.send_message("❌ Zaten katıldın!", ephemeral=True)
            else:
                self.katilimcilar.add(interaction.user.id)
                self.guncelle_label()
                await interaction.response.send_message("✅ Katıldın!", ephemeral=True)
                try:
                    await interaction.message.edit(view=self)
                except:
                    pass
                cog = interaction.client.get_cog("Giveaway")
                if cog: cog.kaydet()

    # --- YARDIMCI ---
    def sure_hesapla(self, metin):
        zaman_regex = re.search(r'(\d+(?:[.,]\d+)?)\s*(saniye|sn|s|dakika|dk|m|saat|sa|h|gün|g|d)', metin)
        if not zaman_regex: return 0
        sayi = float(zaman_regex.group(1).replace(",", "."))
        birim = zaman_regex.group(2)
        if birim in ["saniye", "sn", "s"]:
            return int(sayi)
        elif birim in ["dakika", "dk", "m"]:
            return int(sayi * 60)
        elif birim in ["saat", "sa", "h"]:
            return int(sayi * 3600)
        elif birim in ["gün", "g", "d"]:
            return int(sayi * 86400)
        return 0

    def kazanan_sayisi_bul(self, metin):
        bul = re.search(r'(\d+)\s*(kazanan|kişi|x)', metin)
        if bul: return int(bul.group(1))
        return 1

    # --- BİTİRME ---
    async def cekilisi_bitir(self, cid, channel):
        if cid not in self.aktif_cekilisler: return
        data = self.aktif_cekilisler[cid]
        view = data['view']

        view.stop()
        k_list = list(view.katilimcilar)
        for c in view.children: c.disabled = True
        try:
            await data['message'].edit(view=view)
        except:
            pass

        if not k_list:
            await channel.send(f"😕 Kimse katılmadı, **{data['odul']}** iptal.")
        else:
            kazanan_sayisi = data.get("kazanan_sayisi", 1)
            if len(k_list) <= kazanan_sayisi:
                kazananlar = k_list
            else:
                kazananlar = random.sample(k_list, kazanan_sayisi)

            mentions = " ".join([f"<@{uid}>" for uid in kazananlar])
            embed = discord.Embed(
                title="🎊 KAZANANLAR BELLİ OLDU! 🎊",
                description=f"🎁 **Ödül:** {data['odul']}\n👑 **Kazananlar:** {mentions}",
                color=discord.Color.brand_green()
            )
            await channel.send(content=f"Tebrikler {mentions}! 🥳", embed=embed)
            self.son_biten_cekilis = {'katilimcilar': k_list, 'odul': data['odul']}

        del self.aktif_cekilisler[cid]
        self.kaydet()

    async def cekilis_zamanlayici(self, saniye, cid, channel):
        await asyncio.sleep(saniye)
        if cid in self.aktif_cekilisler: await self.cekilisi_bitir(cid, channel)

    # --- ANA DİNLEYİCİ ---
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild: return
        if not self.bot.user.mentioned_in(message): return
        if not message.author.guild_permissions.manage_messages: return
        icerik = message.content.lower()

        # 🔥 YENİ EKLENEN FİLTRE: SORU SORUYORSA GİRME!
        # "Çekiliş nasıl açarım?" dediğinde burası çalışmayacak.
        soru_kelimeleri = ["nasıl", "nedir", "ne zaman", "kim", "mi", "mu", "mı", "?"]
        if any(s in icerik for s in soru_kelimeleri):
            return  # Soru soruyor, bırak AI cevaplasın.

        # MANUEL KAPATMA
        if "çekiliş" in icerik and ("kapat" in icerik or "bitir" in icerik):
            id_bul = re.search(r'#?(\d{4})', icerik)
            if id_bul and id_bul.group(1) in self.aktif_cekilisler:
                cid = id_bul.group(1)
                self.aktif_cekilisler[cid]['task'].cancel()
                await message.channel.send(f"⏹️ **#{cid}** sonlandırılıyor...")
                await self.cekilisi_bitir(cid, message.channel)
            else:
                await message.reply("❌ ID bulunamadı.")
            return

        # BAŞLATMA
        tetikleyiciler = ["yap", "başlat", "aç", "oluştur"]
        if "çekiliş" in icerik and any(t in icerik for t in tetikleyiciler) and "yeniden" not in icerik:

            saniye = self.sure_hesapla(icerik)
            if not saniye:
                # Soru filtresi yukarıda olduğu için, buraya gelmişse gerçekten komut denemiştir.
                await message.channel.send(
                    embed=discord.Embed(title="❌ Hata", description="Süre belirtmedin! Örn: `10dk`, `1saat`",
                                        color=discord.Color.red()))
                return

            kazanan_sayisi = self.kazanan_sayisi_bul(icerik)
            rol_sarti = message.role_mentions[0].id if message.role_mentions else None

            temiz_odul = icerik.replace(f"<@{self.bot.user.id}>", "")
            for kelime in tetikleyiciler + ["çekiliş", "kazanan", "kişi"]: temiz_odul = temiz_odul.replace(kelime, "")
            temiz_odul = re.sub(r'(\d+(?:[.,]\d+)?)\s*(saniye|sn|s|dakika|dk|m|saat|sa|h|gün|g|d)', '', temiz_odul)
            temiz_odul = re.sub(r'<@&\d+>', '', temiz_odul)
            temiz_odul = re.sub(r'\d+x', '', temiz_odul).strip()
            if len(temiz_odul) < 2: temiz_odul = "Sürpriz Ödül"

            cid = str(random.randint(1000, 9999))
            while cid in self.aktif_cekilisler: cid = str(random.randint(1000, 9999))

            bitis = datetime.datetime.now() + datetime.timedelta(seconds=saniye)
            unix = int(bitis.timestamp())
            sart_metni = f"<@&{rol_sarti}> rolü" if rol_sarti else "Yok"

            embed = discord.Embed(title="🎉 ÇEKİLİŞ VAKTİ! 🎉", color=discord.Color.gold())
            embed.add_field(name="🎁 Ödül", value=temiz_odul.upper(), inline=False)
            embed.add_field(name="👥 Kazanan", value=str(kazanan_sayisi), inline=True)
            embed.add_field(name="👮 Şart", value=sart_metni, inline=True)
            embed.add_field(name="⏱️ Bitiş", value=f"<t:{unix}:R>", inline=False)
            embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/1139/1139982.png")
            embed.set_footer(text=f"ID: #{cid}")

            view = self.CekilisButonu(saniye, embed, rol_sarti)
            msg = await message.channel.send(embed=embed, view=view)

            task = asyncio.create_task(self.cekilis_zamanlayici(saniye, cid, message.channel))
            self.aktif_cekilisler[cid] = {
                'task': task, 'view': view, 'message': msg, 'odul': temiz_odul,
                'kanal_id': message.channel.id, 'mesaj_id': msg.id, 'bitis': bitis,
                'kazanan_sayisi': kazanan_sayisi, 'rol_sarti': rol_sarti
            }
            self.kaydet()


async def setup(bot):
    await bot.add_cog(Giveaway(bot))