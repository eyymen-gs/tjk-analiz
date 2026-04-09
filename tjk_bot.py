import sys
sys.stdout.reconfigure(encoding='utf-8')

import json
import os
import subprocess
import asyncio
from datetime import time
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, JobQueue

TOKEN    = os.environ.get("TOKEN") or "8653911412:AAHP9AWee0f60aNy_qNmTRUx_LRq9B05Kcs"
ADMIN_ID = 6424297442

onaylı_kullanicilar = set([ADMIN_ID])

def analiz_calistir():
    try:
        r1 = subprocess.run(
            ["python", "tjk_veri.py"],
            check=True, capture_output=True, text=True,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        print("veri.py:", r1.stdout)
        r2 = subprocess.run(
            ["python", "tjk_model.py"],
            check=True, capture_output=True, text=True,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        print("model.py:", r2.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Hata: {e.stderr}")
        return False
    except Exception as e:
        print(f"Genel hata: {e}")
        return False

def temiz_veri_yukle():
    try:
        with open("tjk_temiz.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def alti_ganyan_mesaj(sehir, atlar, baslangic_kosu=1):
    from collections import defaultdict

    def form_skoru(son6):
        if not son6:
            return 0
        agirliklar   = [1.0, 1.2, 1.5, 1.8, 2.2, 2.8]
        puan_tablosu = {0:0, 1:6, 2:4, 3:3, 4:2, 5:1, 6:0.5, 7:0.3, 8:0.2, 9:0.1}
        skor = 0
        for i, d in enumerate(son6[-6:]):
            skor += puan_tablosu.get(d, 0) * (agirliklar[i] if i < len(agirliklar) else 1.0)
        return round(skor, 2)

    def guc_skoru(at):
        form   = form_skoru(at.get("son6", []))
        agf    = at.get("agf_yuzde") or 0
        kgs    = at.get("kgs", 30)
        kgs_p  = 100 if 14<=kgs<=28 else (90 if kgs<=14 else (85 if kgs<=45 else 70))
        kilo_c = max(0, (at.get("toplam_kilo", 56) - 56) * 0.5)
        en_iyi_sn = at.get("en_iyi_sn")
        hiz = (85.0 / en_iyi_sn * 100) if en_iyi_sn and en_iyi_sn > 0 else 50.0
        return round(form*3.0 + hiz*2.0 + agf*1.5 + kgs_p*0.5 - kilo_c, 2)

    def kosu_aciklik(skorlu):
        if len(skorlu) < 2:
            return 1
        toplam = sum(a["guc_skoru"] for a in skorlu)
        if toplam == 0:
            return 2
        birinci_yuzde = (skorlu[0]["guc_skoru"] / toplam) * 100
        ikinci_yuzde  = (skorlu[1]["guc_skoru"] / toplam) * 100
        fark = birinci_yuzde - ikinci_yuzde
        if birinci_yuzde >= 20 and fark >= 4:
            return 1
        elif fark <= 1:
            return 3
        else:
            return 2

    # Koşuları grupla
    kosu_gruplari = defaultdict(list)
    for at in atlar:
        kosu_gruplari[at["kosu_no"]].append(at)

    kosu_nolari  = sorted(kosu_gruplari.keys())
    alti_kosular = kosu_nolari[baslangic_kosu-1 : baslangic_kosu+5]

    if len(alti_kosular) < 6:
        return "❌ 6 koşu bulunamadı."

    mesaj_satirlar    = [f"🏇 *{sehir} — Altılı Ganyan Analizi*\n{'='*30}"]
    kombinasyon_atlar = []
    onerilen_kuponlar = []

    for kosu_no in alti_kosular:
        kosu_atlari = kosu_gruplari[kosu_no]

        skorlu = []
        for at in kosu_atlari:
            skor = guc_skoru(at)
            skorlu.append({**at, "guc_skoru": skor})
        skorlu.sort(key=lambda x: x["guc_skoru"], reverse=True)

        toplam = sum(a["guc_skoru"] for a in skorlu)
        for at in skorlu:
            at["ihtimal"] = round((at["guc_skoru"]/toplam)*100, 1) if toplam > 0 else 0

        kac_at = kosu_aciklik(skorlu)

        if kac_at == 1:
            etiket = "🔒 Net favori"
        elif kac_at == 3:
            etiket = "🔓 Açık koşu"
        else:
            etiket = "⚖️ Normal koşu"

        mesaj_satirlar.append(f"\n*{kosu_no}. Koşu* — {etiket}")

        onerilen = []
        for i, at in enumerate(skorlu[:4]):
            secildi   = i < kac_at
            isaretler = "⭐" if i == 0 else ("✅" if i == 1 else ("🔵" if i == 2 else "▪️"))
            kupon_isa = "◀️" if secildi else "  "
            son6_str  = "".join(str(d) for d in at.get("son6", []))
            mesaj_satirlar.append(
                f"{kupon_isa}{isaretler} {at['at_adi']} "
                f"| %{at['ihtimal']} "
                f"| Gny:{at['gny']} "
                f"| AGF:{at.get('agf_yuzde') or 0:.0f}% "
                f"| Form:{son6_str}"
            )
            if secildi:
                onerilen.append(at['at_adi'])

        kombinasyon_atlar.append(onerilen)
        onerilen_kuponlar.append({
            "kosu_no": kosu_no,
            "secilen": onerilen,
            "kac_at":  kac_at,
            "etiket":  etiket
        })

    # Kombinasyon sayısını hesapla
    kombin_sayi = 1
    for grup in kombinasyon_atlar:
        kombin_sayi *= len(grup)

    # Maksimum 108 kupona sınırla
    while kombin_sayi > 108 and any(len(g) > 1 for g in kombinasyon_atlar):
        max_idx = max(range(len(kombinasyon_atlar)), key=lambda i: len(kombinasyon_atlar[i]))
        if len(kombinasyon_atlar[max_idx]) > 1:
            kombinasyon_atlar[max_idx].pop()
            onerilen_kuponlar[max_idx]["secilen"].pop()
            onerilen_kuponlar[max_idx]["kac_at"] -= 1
        kombin_sayi = 1
        for grup in kombinasyon_atlar:
            kombin_sayi *= len(grup)

    # Kupon özeti
    mesaj_satirlar.append(f"\n{'='*30}")
    mesaj_satirlar.append(f"🎯 *Kupon Önerisi:*")
    for k in onerilen_kuponlar:
        atlar_str = " + ".join(k["secilen"])
        gercek_kac = len(k["secilen"])
        mesaj_satirlar.append(f"  {k['kosu_no']}. Koşu ({gercek_kac} at): {atlar_str}")

    mesaj_satirlar.append(f"\n💡 *Toplam:* {kombin_sayi} kupon")
    mesaj_satirlar.append(f"💰 *Min. yatırım:* {kombin_sayi * 3} TL")
    mesaj_satirlar.append(f"\n⚠️ _Bu analiz istatistiksel bir modeldir, kesin sonuç garantisi vermez._")

    return "\n".join(mesaj_satirlar)

# ─── Telegram Handler'ları ─────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏇 *TJK Altılı Ganyan Analiz Botu*\n\n"
        "Komutlar:\n"
        "`/bugun` — Bugünkü altılı analizini göster\n"
        "`/guncelle` — Verileri güncelle (Admin)\n",
        parse_mode="Markdown"
    )

async def bugun(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kullanici_id = update.message.from_user.id
    if kullanici_id not in onaylı_kullanicilar:
        await update.message.reply_text("⛔ Yetkin yok.")
        return

    await update.message.reply_text("🔍 Analiz hazırlanıyor...")

    veri = temiz_veri_yukle()
    if not veri:
        await update.message.reply_text("❌ Veri bulunamadı. Önce /guncelle komutunu dene.")
        return

    for sehir, atlar in veri.items():
        if not atlar:
            continue
        mesaj = alti_ganyan_mesaj(sehir, atlar, baslangic_kosu=1)
        if len(mesaj) > 4096:
            mesaj = mesaj[:4090] + "..."
        await update.message.reply_text(mesaj, parse_mode="Markdown")

async def guncelle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kullanici_id = update.message.from_user.id
    if kullanici_id != ADMIN_ID:
        await update.message.reply_text("⛔ Sadece admin kullanabilir.")
        return

    await update.message.reply_text("⏳ Veriler güncelleniyor, biraz bekle...")
    basari = analiz_calistir()

    if basari:
        await update.message.reply_text("✅ Veriler güncellendi! /bugun ile analizi görebilirsin.")
    else:
        await update.message.reply_text("❌ Güncelleme sırasında hata oluştu.")
async def otomatik_guncelle(context):
    """Her sabah 08:00'de otomatik çalışır"""
    print("⏰ Otomatik güncelleme başladı...")
    basari = analiz_calistir()
    if basari:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text="✅ Sabah güncellemesi tamamlandı! /bugun ile analizi görebilirsin."
        )
        print("✅ Otomatik güncelleme tamamlandı")
    else:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text="❌ Sabah güncellemesi sırasında hata oluştu."
        )
# ─── Botu başlat ──────────────────────────────────────────────────────

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start",    start))
app.add_handler(CommandHandler("bugun",    bugun))
app.add_handler(CommandHandler("guncelle", guncelle))

# Her sabah 08:00'de otomatik güncelle (Türkiye saati UTC+3)
job_queue = app.job_queue
job_queue.run_daily(
    otomatik_guncelle,
    time=time(hour=5, minute=0, second=0),  # UTC 05:00 = Türkiye 08:00
)

print("🤖 TJK Bot çalışıyor...")
print("⏰ Otomatik güncelleme: Her sabah 08:00 (Türkiye saati)")
app.run_polling()
