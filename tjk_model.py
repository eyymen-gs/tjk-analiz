import sys
sys.stdout.reconfigure(encoding='utf-8')
import json
import re
from collections import defaultdict

# ─── Veri Temizleme ───────────────────────────────────────────────────

def temizle(metin):
    if not metin:
        return ""
    return re.sub(r'\s+', ' ', str(metin)).strip()

def en_iyi_sure_cek(en_iyi_ham):
    """'1.26.71  Bu derece...' → 1.26.71"""
    if not en_iyi_ham:
        return None
    eslesme = re.search(r'(\d+\.\d+\.\d+)', en_iyi_ham)
    return eslesme.group(1) if eslesme else None

def sure_saniyeye_cevir(sure_str):
    """1.26.71 → 86.71 saniye"""
    if not sure_str:
        return None
    try:
        parcalar = sure_str.split(".")
        if len(parcalar) == 3:
            return int(parcalar[0]) * 60 + int(parcalar[1]) + int(parcalar[2]) / 100
        elif len(parcalar) == 2:
            return int(parcalar[0]) * 60 + float(parcalar[1])
    except:
        return None

def agf_yukde_cek(agf_ham):
    """%7(5) → 7.0"""
    if not agf_ham:
        return None
    eslesme = re.search(r'%(\d+)', agf_ham)
    return float(eslesme.group(1)) if eslesme else None

def agf_sira_cek(agf_ham):
    """%7(5) → 5"""
    if not agf_ham:
        return None
    eslesme = re.search(r'\((\d+)\)', agf_ham)
    return int(eslesme.group(1)) if eslesme else None

def son6_parse(son6_ham):
    """'111585' → [1,1,1,5,8,5] (son 6 derece)"""
    if not son6_ham:
        return []
    rakamlar = re.findall(r'\d', son6_ham)
    return [int(r) for r in rakamlar[-6:]]

def at_no_temizle(at_no_ham):
    """'KUBAT KASIRGASI\r\n  (5)' → 'KUBAT KASIRGASI', 5"""
    at_adi = temizle(at_no_ham.split("(")[0])
    eslesme = re.search(r'\((\d+)\)', at_no_ham)
    program_no = int(eslesme.group(1)) if eslesme else None
    return at_adi, program_no

def veri_temizle(ham_veri):
    """Ham JSON verisini temizle ve zenginleştir"""
    temiz = {}
    
    for sehir, atlar in ham_veri.items():
        temiz[sehir] = []
        
        for at in atlar:
            at_adi_temiz, program_no = at_no_temizle(at.get("at_adi", ""))
            en_iyi_ham   = at.get("en_iyi", "")
            en_iyi_sure  = en_iyi_sure_cek(en_iyi_ham)
            agf_ham      = at.get("agf", "")
            son6         = son6_parse(at.get("son6", ""))
            
            # Fazla kilo hesapla
            siklet_ham = temizle(at.get("siklet", ""))
            fazla_kilo = 0.0
            siklet     = 0.0
            if "+" in siklet_ham:
                parca = siklet_ham.split("+")
                try:
                    siklet     = float(parca[0].replace(",", "."))
                    fazla_kilo = float(parca[1].split("F")[0].strip().replace(",", "."))
                except:
                    pass
            else:
                try:
                    siklet = float(siklet_ham.replace(",", "."))
                except:
                    pass
            
            toplam_kilo = siklet + fazla_kilo
            
            temiz[sehir].append({
                "sehir":       sehir,
                "tarih":       at.get("tarih", ""),
                "kosu_no":     at.get("kosu_no", 0),
                "at_no":       at.get("at_no", ""),
                "program_no":  program_no,
                "at_adi":      at_adi_temiz,
                "at_id":       at.get("at_id", ""),
                "yas":         temizle(at.get("yas", "")),
                "siklet":      siklet,
                "fazla_kilo":  fazla_kilo,
                "toplam_kilo": toplam_kilo,
                "jokey":       temizle(at.get("jokey", "")),
                "antrenor":    temizle(at.get("antrenor", "")),
                "start_no":    at.get("start", ""),
                "hp":          int(at.get("hp", 0)) if str(at.get("hp","")).isdigit() else 0,
                "son6":        son6,
                "kgs":         int(at.get("kgs", 0)) if str(at.get("kgs","")).isdigit() else 0,
                "en_iyi_sure": en_iyi_sure,
                "en_iyi_sn":   sure_saniyeye_cevir(en_iyi_sure),
                "gny": float(str(at.get("gny","0")).replace(",",".")) if at.get("gny") and at.get("gny") != "-" else 0,
                "agf_yuzde":   agf_yukde_cek(agf_ham),
                "agf_sira":    agf_sira_cek(agf_ham),
            })
    
    return temiz

# ─── Model ───────────────────────────────────────────────────────────

def form_skoru(son6):
    """Son 6 yarıştan form skoru üret (1. = 6 puan, 2. = 4, 3. = 3...)"""
    if not son6:
        return 0
    agirliklar = [1.0, 1.2, 1.5, 1.8, 2.2, 2.8]  # en son yarış en ağır
    puan_tablosu = {0: 0, 1: 6, 2: 4, 3: 3, 4: 2, 5: 1, 6: 0.5,
                    7: 0.3, 8: 0.2, 9: 0.1}
    
    skor = 0
    for i, derece in enumerate(son6[-6:]):
        agirlik = agirliklar[i] if i < len(agirliklar) else 1.0
        puan    = puan_tablosu.get(derece, 0)
        skor   += puan * agirlik
    
    return round(skor, 2)

def hiz_skoru(en_iyi_sn, mesafe=None):
    """En iyi süreyi hız skoruna çevir (düşük süre = yüksek skor)"""
    if not en_iyi_sn or en_iyi_sn <= 0:
        return 50.0  # bilinmiyorsa orta skor ver
    # Referans: 1400m için ~85 saniye ortalama
    referans = 85.0
    skor = (referans / en_iyi_sn) * 100
    return round(skor, 2)

def kilo_cezasi(toplam_kilo, baz_kilo=56.0):
    """Her fazla kilo için hafif ceza"""
    fark = toplam_kilo - baz_kilo
    return round(max(0, fark * 0.5), 2)

def kgs_skoru(kgs):
    """Kaç gündür koşmadı — optimal 14-28 gün"""
    if kgs <= 0:
        return 80
    elif kgs <= 7:
        return 70   # çok yorgun olabilir
    elif kgs <= 14:
        return 90   # iyi form
    elif kgs <= 28:
        return 100  # ideal dinlenme
    elif kgs <= 45:
        return 85
    elif kgs <= 90:
        return 70
    else:
        return 55   # çok uzun ara

def guc_skoru_hesapla(at):
    """Her at için toplam güç skoru"""
    form   = form_skoru(at["son6"])
    hiz    = hiz_skoru(at["en_iyi_sn"])
    kilo_c = kilo_cezasi(at["toplam_kilo"])
    kgs    = kgs_skoru(at["kgs"])
    agf    = at["agf_yuzde"] or 0
    
    # Ağırlıklı toplam
    skor = (
        form  * 3.0  +   # form en kritik
        hiz   * 2.0  +   # hız ikinci kritik
        agf   * 1.5  +   # TJK'nın kendi AGF hesabı
        kgs   * 0.5  -   # dinlenme süresi
        kilo_c * 1.0     # kilo cezası
    )
    
    return round(skor, 2)

def kosu_analiz(atlar):
    """Bir koşudaki tüm atları analiz et ve sırala"""
    skorlu = []
    
    for at in atlar:
        skor = guc_skoru_hesapla(at)
        skorlu.append({**at, "guc_skoru": skor})
    
    # Skora göre sırala
    skorlu.sort(key=lambda x: x["guc_skoru"], reverse=True)
    
    # Kazanma ihtimalini hesapla
    toplam_skor = sum(a["guc_skoru"] for a in skorlu)
    if toplam_skor > 0:
        for at in skorlu:
            at["kazanma_ihtimali"] = round((at["guc_skoru"] / toplam_skor) * 100, 1)
    else:
        for at in skorlu:
            at["kazanma_ihtimali"] = round(100 / len(skorlu), 1)
    
    return skorlu

def alti_ganyan_analiz(sehir_adi, kosular_listesi):
    """6 koşuyu analiz et, kombinasyon öner"""
    kosu_gruplari = defaultdict(list)
    for at in kosular_listesi:
        kosu_gruplari[at["kosu_no"]].append(at)
    
    kosu_nolari = sorted(kosu_gruplari.keys())
    
    # Altılı gruplarını bul (6 ardışık koşu)
    alti_gruplar = []
    for i in range(len(kosu_nolari) - 5):
        grup = kosu_nolari[i:i+6]
        if grup[-1] - grup[0] == 5:  # ardışık mı
            alti_gruplar.append(grup)
    
    sonuclar = {}
    
    for grup_idx, grup in enumerate(alti_gruplar):
        grup_adi  = f"Altılı {grup_idx+1} ({grup[0]}.koşu - {grup[5]}.koşu)"
        analizler = {}
        
        for kosu_no in grup:
            atlar     = kosu_gruplari[kosu_no]
            skorlu    = kosu_analiz(atlar)
            analizler[kosu_no] = skorlu
        
        sonuclar[grup_adi] = analizler
    
    return sonuclar

def rapor_yazdir(sehir, analizler):
    print(f"\n{'='*60}")
    print(f"🏇 {sehir} — Altılı Ganyan Analizi")
    print(f"{'='*60}")
    
    for grup_adi, kosular in analizler.items():
        print(f"\n🎯 {grup_adi}")
        print("-" * 50)
        
        kombinasyon_atlar = []
        
        for kosu_no, atlar in kosular.items():
            print(f"\n  {kosu_no}. Koşu:")
            
            # İlk 3 atı göster
            onerilen = []
            for i, at in enumerate(atlar[:5]):
                isaretler = "⭐" if i == 0 else ("✅" if i <= 1 else "")
                print(f"    {isaretler} {at['at_adi']:<25} "
                      f"Skor:{at['guc_skoru']:>6.1f}  "
                      f"İhtimal:%{at['kazanma_ihtimali']:>4.1f}  "
                      f"Gny:{at['gny']:>5.2f}  "
                      f"AGF:{at['agf_yuzde'] or 0:>3.0f}%  "
                      f"Form:{at['son6']}")
                if i < 2:
                    onerilen.append(at['at_adi'])
            
            kombinasyon_atlar.append(onerilen)
        
        # Kombinasyon sayısı
        kombin_sayi = 1
        for atlar in kombinasyon_atlar:
            kombin_sayi *= len(atlar)
        
        print(f"\n  💡 Önerilen kombinasyon: {kombin_sayi} kupon")
        print(f"  💰 Minimum yatırım: {kombin_sayi * 3} TL (3 TL/kupon)")

# ─── Ana çalıştırma ──────────────────────────────────────────────────

if __name__ == "__main__":
    # Temizlenmiş veriyi yükle
    with open("tjk_bugun.json", "r", encoding="utf-8") as f:
        ham_veri = json.load(f)
    
    print("🧹 Veri temizleniyor...")
    temiz_veri = veri_temizle(ham_veri)
    
    # Temizlenmiş veriyi kaydet
    with open("tjk_temiz.json", "w", encoding="utf-8") as f:
        json.dump(temiz_veri, f, ensure_ascii=False, indent=2)
    
    print("✅ tjk_temiz.json oluşturuldu\n")
    
    # Her şehir için analiz yap
    for sehir, atlar in temiz_veri.items():
        print(f"\n📊 {sehir} analiz ediliyor...")
        analizler = alti_ganyan_analiz(sehir, atlar)
        
        if analizler:
            rapor_yazdir(sehir, analizler)
        else:
            print(f"  ❌ {sehir} için altılı grubu bulunamadı")
    
    print(f"\n\n✅ Analiz tamamlandı!")