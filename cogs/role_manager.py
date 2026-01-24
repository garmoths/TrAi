"""
Dinamik Rol Yöneticisi
- Uyarı verilen kişiye "Uyarı X" rolü verir
- Susturulan kişiye "Susturulmuş" rolü verir
- Yasaklanan kişiye "Yasaklı" rolü verir
"""

import discord
from discord.ext import commands
from utils.logger import get_logger
from utils import db


class RoleManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = get_logger(__name__)

    async def ayar_getir(self, guild_id, key, default=None):
        """Guild ayarlarından değer al."""
        settings = db.kv_get("settings", {}) or {}
        return settings.get(str(guild_id), {}).get(key, default)

    async def ayar_kur(self, guild_id, key, value):
        """Guild ayarına değer kur."""
        settings = db.kv_get("settings", {}) or {}
        if str(guild_id) not in settings:
            settings[str(guild_id)] = {}
        settings[str(guild_id)][key] = value
        db.kv_set("settings", settings)

    async def rol_oluştur_veya_bul(self, guild: discord.Guild, rol_adı: str, renk: discord.Color = None, hiyerarşi_düzeyi: int = 0):
        """Rolü var mı kontrol et, yoksa oluştur."""
        try:
            # Var olan rolü ara
            for rol in guild.roles:
                if rol.name.lower() == rol_adı.lower():
                    return rol
            
            # Yoksa oluştur
            yeni_rol = await guild.create_role(
                name=rol_adı,
                color=renk or discord.Color.greyple(),
                reason=f"TrAI - Otomatik {rol_adı} rolü oluşturuldu"
            )
            self.logger.info(f"Yeni rol oluşturuldu: {rol_adı} ({guild.name})")
            return yeni_rol
        except Exception as e:
            self.logger.error(f"Rol oluşturma hatası ({rol_adı}): {e}")
            return None

    async def rol_ver(self, member: discord.Member, rol_adı: str, renk: discord.Color = None):
        """Üyeye rol ver."""
        try:
            rol = await self.rol_oluştur_veya_bul(member.guild, rol_adı, renk)
            if rol and rol not in member.roles:
                await member.add_roles(rol, reason=f"TrAI - {rol_adı} rolü verildi")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Rol verme hatası: {e}")
            return False

    async def rol_al(self, member: discord.Member, rol_adı: str):
        """Üyeden rol al."""
        try:
            rol = discord.utils.get(member.guild.roles, name=rol_adı)
            if rol and rol in member.roles:
                await member.remove_roles(rol, reason=f"TrAI - {rol_adı} rolü kaldırıldı")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Rol alma hatası: {e}")
            return False

    async def uyarı_rolleri_güncelle(self, guild: discord.Guild, member: discord.Member, uyarı_sayısı: int):
        """Uyarı sayısına göre rolleri güncelle."""
        try:
            # Önceki uyarı rollerini kaldır
            for i in range(1, 11):  # 1-10 uyarı rolü
                await self.rol_al(member, f"Uyarı {i}")
            
            # Yeni uyarı rolü ver
            if uyarı_sayısı > 0:
                if uyarı_sayısı > 10:
                    uyarı_sayısı = 10
                
                rol_adı = f"Uyarı {uyarı_sayısı}"
                
                # Renkler: Yeşil → Sarı → Kırmızı
                if uyarı_sayısı <= 3:
                    renk = discord.Color.green()
                elif uyarı_sayısı <= 6:
                    renk = discord.Color.gold()
                else:
                    renk = discord.Color.red()
                
                await self.rol_ver(member, rol_adı, renk)
                self.logger.info(f"{member.name} - {rol_adı} verildi")
                return True
        except Exception as e:
            self.logger.error(f"Uyarı rolü güncelleme hatası: {e}")
        return False

    async def susturulmuş_rol_ver(self, guild: discord.Guild, member: discord.Member):
        """Susturulan üyeye "Susturulmuş" rolü ver."""
        return await self.rol_ver(member, "🔇 Susturulmuş", discord.Color.red())

    async def susturulmuş_rol_al(self, guild: discord.Guild, member: discord.Member):
        """Susturulan üyeden "Susturulmuş" rolü al."""
        return await self.rol_al(member, "🔇 Susturulmuş")

    async def yasaklı_rol_ver(self, guild: discord.Guild, member: discord.Member):
        """Yasaklanan üyeye "Yasaklı" rolü ver."""
        return await self.rol_ver(member, "🚫 Yasaklı", discord.Color.darker_grey())

    # --- Discord Events ---
    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """
        Üyenin timeout durumu değiştiğinde çalışır.
        Timeout eklenirse → Susturulmuş rolü ver
        Timeout kaldırılırsa → Susturulmuş rolü al
        """
        if before.timed_out == after.timed_out:
            return  # Timeout değişmediyse çık
        
        if after.timed_out:
            # Timeout eklendi → Susturulmuş rolü ver
            await self.susturulmuş_rol_ver(after.guild, after)
            self.logger.info(f"{after.name} susturuldu - Susturulmuş rolü verildi")
        else:
            # Timeout kaldırıldı → Susturulmuş rolü al
            await self.susturulmuş_rol_al(after.guild, after)
            self.logger.info(f"{after.name} susturulması kaldırıldı - Susturulmuş rolü alındı")


async def setup(bot):
    await bot.add_cog(RoleManager(bot))
