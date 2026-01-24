# 🤖 TrAI Bot - Davet Linki ve Kurulum

## ⚠️ ÖNEMLİ: Slash Komutlar için Yeniden Davet

Botunuzun slash komutlarını (`/` ile başlayan komutlar) kullanabilmesi için **applications.commands** yetkisi gerekiyor. Eğer bot zaten sunucunuzda ama slash komutları görmüyorsanız, aşağıdaki adımları izleyin:

---

## 🔗 Yeni Davet Linki (Slash Komutlar Dahil)

Bot ID'nizi aşağıdaki linkte `BOT_ID_BURAYA` yazan yere yazın ve botu yeniden davet edin:

```
https://discord.com/oauth2/authorize?client_id=BOT_ID_BURAYA&permissions=8&scope=bot%20applications.commands
```

### Bot ID'nizi Bulma

1. Discord Developer Portal'a gidin: https://discord.com/developers/applications
2. Botunuzu seçin
3. **Application ID**'yi kopyalayın
4. Yukarıdaki linkte `BOT_ID_BURAYA` yerine yapıştırın

---

## 📋 Yetkiler

Yukarıdaki link ile bot şu yetkilere sahip olacak:

✅ **Administrator** (permissions=8) - Tüm yetkileri içerir  
✅ **Slash Commands** (scope=applications.commands) - `/` komutları için  
✅ **Bot** (scope=bot) - Normal bot işlevleri için

### Daha Az Yetki İle Davet (Önerilen)

Eğer Administrator yerine spesifik yetkiler vermek isterseniz:

```
https://discord.com/oauth2/authorize?client_id=BOT_ID_BURAYA&permissions=1099511627831&scope=bot%20applications.commands
```

Bu link şu yetkileri içerir:
- ✅ Mesajları Yönet (Silme için)
- ✅ Üyeleri At (Kick için)
- ✅ Üyeleri Yasakla (Ban için)
- ✅ Üyeleri Sustur (Timeout için)
- ✅ Rolleri Yönet
- ✅ Kanalları Yönet
- ✅ Embed Gönder
- ✅ Dosya Yükle
- ✅ Mesaj Geçmişini Oku
- ✅ Tepki Ekle

---

## 🚀 Kurulum Adımları

### 1. Eski Botu Çıkarın (Opsiyonel)

Eğer bot zaten sunucunuzda ama slash komutları çalışmıyorsa:
1. Sunucu Ayarları → Entegrasyonlar
2. TrAI botunu bulun
3. "Kaldır" veya "Kick" yapın

### 2. Yeni Link ile Davet Edin

1. Yukarıdaki davet linkini tarayıcıya yapıştırın
2. Sunucunuzu seçin
3. Yetkileri onaylayın
4. "Yetkilendir" butonuna tıklayın

### 3. Bot Hazır!

Bot sunucunuza eklendikten sonra:
- `/` yazarak tüm komutları görebilirsiniz
- Discord otomatik tamamlama önerecektir
- Parametreler otomatik olarak gösterilecektir

---

## 🎯 Mevcut Slash Komutlar (16 Adet)

### 🎛️ Panel & Ayarlar (2)
- `/panel` - Sunucu ayar panelini açar
- `/ayarlar` - Mevcut ayarları gösterir

### 🛡️ Moderasyon (7)
- `/sil` - Mesajları toplu sil
- `/uyar` - Kullanıcı uyar
- `/ban` - Kullanıcı yasakla
- `/kick` - Kullanıcı at
- `/sustur` - Geçici sustur
- `/susturma-kaldir` - Susturmayı kaldır
- `/uyarilar` - Uyarı listesi

### ℹ️ Genel Bilgi (5)
- `/yardım` - Komut rehberi
- `/ping` - Bot gecikmesi
- `/sunucu-bilgi` - Sunucu istatistikleri
- `/kullanıcı-bilgi` - Kullanıcı profili
- `/avatar` - Avatar göster

### 📊 Level Sistemi (2)
- `/level` - Seviyeni göster
- `/lider-tablosu` - En yüksek seviyeler

### 🎉 Çekiliş (2)
- `/çekiliş-başlat` - Çekiliş başlat
- `/çekiliş-liste` - Aktif çekilişler

---

## ❓ Sorun Giderme

### Slash komutları hala görünmüyor?

**Çözüm 1: Botu yeniden davet edin**
- Eski botu sunucudan çıkarın
- Yukarıdaki linki kullanarak tekrar davet edin
- `applications.commands` scope'unun seçili olduğundan emin olun

**Çözüm 2: Discord cache'i temizleyin**
- Discord'u tamamen kapatın (sistem tepsisinden de)
- Tekrar açın
- `/` yazarak kontrol edin

**Çözüm 3: 1 saat bekleyin**
- Discord slash komutları bazen cache nedeniyle geç görünür
- Genellikle 1 saat içinde aktif hale gelir

**Çözüm 4: Bot loglarını kontrol edin**
```
✅ 16 slash komut Discord'a senkronize edildi!
```
Bu mesajı görüyorsanız, komutlar Discord'a gönderilmiş demektir.

### /sil çalışmıyor?

Botun şu yetkilere sahip olduğundan emin olun:
- ✅ Mesajları Yönet (Manage Messages)
- ✅ Mesaj Geçmişini Oku (Read Message History)

Ayrıca **siz de** bu yetkilere sahip olmalısınız!

### Sadece bazı komutları görüyorum?

Discord, yetkilerinize göre komutları filtreler:
- Moderasyon komutları için yetkili olmalısınız
- `/panel` için Administrator gerekir
- `/yardım`, `/ping` gibi komutlar herkes için görünür

---

## 📊 Teknik Bilgiler

### Senkronizasyon
- Bot her başlatıldığında komutlar otomatik sync edilir
- Log çıktısı: `✅ 16 slash komut Discord'a senkronize edildi!`
- Sync süresi: 1-5 saniye

### Komut Türleri
- **Guild Commands**: Sadece belirli sunucuda (anında aktif)
- **Global Commands**: Tüm sunucularda (1 saat içinde aktif)

Şu an **global** kullanıyoruz, bu yüzden tüm sunucularda 1 saat içinde görünür.

### Yedek Sistem
Slash komutlar çalışmazsa, prefix komutlar hala aktif:
- `!sil 50` → `/sil miktar:50`
- `!uyar @user` → `/uyar uye:@user`
- `!panel` → `/panel`

---

## ✅ Kontrol Listesi

Botu doğru şekilde kurduğunuzdan emin olmak için:

- [ ] Bot davet edilirken `applications.commands` seçildi mi?
- [ ] Bot "Çevrimiçi" durumda mı?
- [ ] Log'da "16 slash komut senkronize edildi" görünüyor mu?
- [ ] Discord'da `/` yazdığınızda bot komutları görünüyor mu?
- [ ] Botun yetkisi var mı? (Rolleri kontrol edin)

---

## 🎉 Başarılı Kurulum!

Tüm adımları tamamladıysanız, artık Discord'da `/` yazarak botunuzun tüm komutlarını görebilir ve modern bir arayüz ile kullanabilirsiniz!

**Not**: İlk kurulumda komutların görünmesi 1-60 dakika sürebilir. Sabırlı olun! 😊
