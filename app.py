# app.py - Kompletna verzija SA PODRŠKOM ZA ADRESU I JKP

import streamlit as st
import pandas as pd
import datetime
import requests
import re
from docxtpl import DocxTemplate
from io import BytesIO
import os
import base64
import traceback

st.set_page_config(page_title="Generator Obavestenja", page_icon="📄", layout="wide")

st.title("📄 Generator obaveštenja-Advokati Popović/Botorić ")
st.markdown("")
st.markdown("---")

# ============================================
# REČNIK GRADOVA I JKP
# ============================================

JKP_PO_GRADOVIMA = {
    'KRALJEVO': 'JKP "Čistoća Kraljevo" Kraljevo',
    'VALJEVO': 'JKP "Vidrak Valjevo" Valjevo',
    'LAZAREVAC': 'JKP "Parking Servis" Lazarevac',
    'GORNJI MILANOVAC': 'JKP "JP za izgradnju opštine Gornji Milanovac" Gornji Milanovac',
    'IVANJICA': 'JKP "Ivanjica" Ivanjica',
    
    # Dodaj ostale gradove po potrebi
}
POSTANSKI_BROJEVI = {
    'KRALJEVO': '36000',
    'VALJEVO': '14000',
    'LAZAREVAC': '11550',
    'GORNJI MILANOVAC': '32300',
    'IVANJICA': '32250',
}

# ============================================
# FUNKCIJA ZA OBRAČUN KAMATE
# ============================================

def izracunaj_kamatu(glavnica, datum_pocetka, datum_zavrsetka, kamatna_stopa):
    if glavnica <= 0 or datum_pocetka is None:
        return 0.0
    
    if isinstance(datum_pocetka, str):
        for fmt in ['%d.%m.%Y.', '%d.%m.%Y', '%Y-%m-%d', '%m.%d.%Y.', '%m/%d/%Y']:
            try:
                datum_pocetka = datetime.datetime.strptime(datum_pocetka.strip(), fmt).date()
                break
            except:
                continue
        if isinstance(datum_pocetka, str):
            return 0.0
    elif isinstance(datum_pocetka, datetime.datetime):
        datum_pocetka = datum_pocetka.date()
    
    if isinstance(datum_zavrsetka, datetime.datetime):
        datum_zavrsetka = datum_zavrsetka.date()
    else:
        datum_zavrsetka = datetime.date.today()
    
    if datum_pocetka > datum_zavrsetka:
        return 0.0
    
    def je_prestupna(godina):
        return (godina % 4 == 0 and godina % 100 != 0) or (godina % 400 == 0)
    
    ukupna_kamata = 0.0
    trenutni_datum = datum_pocetka
    preostali_dani = (datum_zavrsetka - datum_pocetka).days
    
    if preostali_dani <= 0:
        return 0.0
    
    while preostali_dani > 0:
        godina = trenutni_datum.year
        broj_dana_u_godini = 366 if je_prestupna(godina) else 365
        kraj_godine = datetime.date(godina, 12, 31)
        
        if trenutni_datum <= kraj_godine:
            if datum_zavrsetka <= kraj_godine:
                dani_u_periodu = preostali_dani
            else:
                dani_u_periodu = (kraj_godine - trenutni_datum).days + 1
        else:
            dani_u_periodu = 0
        
        if dani_u_periodu > 0:
            kamata_za_godinu = (glavnica * kamatna_stopa * dani_u_periodu) / (100 * broj_dana_u_godini)
            ukupna_kamata += kamata_za_godinu
        
        preostali_dani -= dani_u_periodu
        trenutni_datum = datetime.date(godina + 1, 1, 1)
    
    return ukupna_kamata

def dohvati_kamatnu_stopu():
    try:
        url = "https://www.nbs.rs/sr_RS/druge/instrumenti-politike/kamatne-stope/"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            text = response.text
            match = re.search(r'(\d+,\d+)\s*%', text)
            if match:
                referentna_stopa = float(match.group(1).replace(',', '.'))
                zakonska_stopa = referentna_stopa + 8.0
                return zakonska_stopa
        return 13.75
    except:
        return 13.75 
    
def formatiraj_iznos(iznos):
    if iznos is None:
        iznos = 0
    return f"{iznos:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def parsiraj_broj_iz_stringa(vrednost):
    """
    Parsira broj iz stringa bez obzira na format.
    Radi za: 1200, 1200.0, 1.500,00, 1,500.00, 1.500, itd.
    """
    if vrednost is None:
        return None
    
    # Ako je već broj, vrati ga
    if isinstance(vrednost, (int, float)):
        return float(vrednost)
    
    # Pretvori u string
    vrednost = str(vrednost).strip()
    if not vrednost:
        return None
    
    # Ukloni sve razmake
    vrednost = vrednost.replace(" ", "")
    
    # Ako je prazno posle uklanjanja razmaka
    if not vrednost:
        return None
    
    # ====== PARSIRANJE ======
    # 1. Format: 1.500,00 (srpski - tačka za hiljade, zarez za decimale)
    if "." in vrednost and "," in vrednost:
        if vrednost.index(".") < vrednost.index(","):
            # Ukloni tačke (separatori hiljada)
            vrednost = vrednost.replace(".", "")
            # Zameni zarez sa tačkom (decimalni separator)
            vrednost = vrednost.replace(",", ".")
            try:
                return float(vrednost)
            except:
                pass
    
    # 2. Format: 1,500.00 (engleski - zarez za hiljade, tačka za decimale)
    if "," in vrednost and "." in vrednost:
        if vrednost.index(",") < vrednost.index("."):
            # Ukloni zareze (separatori hiljada)
            vrednost = vrednost.replace(",", "")
            try:
                return float(vrednost)
            except:
                pass
    
    # 3. Format: 1234,56 (srpski - samo zarez kao decimalni separator)
    if "," in vrednost:
        if vrednost.count(",") == 1:
            # To je verovatno decimalni separator
            vrednost = vrednost.replace(",", ".")
            try:
                return float(vrednost)
            except:
                pass
        else:
            # Više zareza - verovatno separator hiljada
            vrednost = vrednost.replace(",", "")
            try:
                return float(vrednost)
            except:
                pass
    
    # 4. Format: 1.500 (samo tačke kao separator hiljada)
    if "." in vrednost:
        if vrednost.count(".") > 1:
            vrednost = vrednost.replace(".", "")
            try:
                return float(vrednost)
            except:
                pass
    
    # 5. Pokušaj direktno
    try:
        return float(vrednost)
    except:
        pass
    
    # 6. Poslednji pokušaj - izvuci sve brojeve i tačke
    import re
    cleaned = re.sub(r'[^\d.]', '', vrednost)
    try:
        if cleaned:
            return float(cleaned)
    except:
        pass
    
    return None

def ucitaj_sve_sheetove(fajl):
    ignore_sheets = ['SVI PREDMETI', 'ROČIŠTA', 'BEXX BALKAN', 'UNIQA', 'OSIGURANJE', 'BANKE', 'IZVRŠENJE-BALKAN']
    try:
        excel_file = pd.ExcelFile(fajl)
        sheets = [s for s in excel_file.sheet_names if s not in ignore_sheets]
        return excel_file, sheets
    except Exception as e:
        st.error(f"Greška: {e}")
        return None, []

def ucitaj_duznike_iz_sheeta(excel_file, sheet_name):
    """Učitava sve dužnike iz jednog sheet-a UKLJUČUJUĆI ADRESU I JKP"""
    try:
        # Učitaj sve kao string - OVO JE KLJUČNO!
        df = excel_file.parse(sheet_name, dtype=str, keep_default_na=False)
        
        # Pronađi kolonu sa imenom
        kolona_ime = None
        for col in df.columns:
            col_str = str(col).strip().lower()
            if 'ime' in col_str and ('dužn' in col_str or 'duzn' in col_str):
                kolona_ime = col
                break
        
        # Pronađi kolonu sa iznosom osnovnog duga
        kolona_dug = None
        for col in df.columns:
            col_str = str(col).strip().lower()
            if 'osnovnog' in col_str and ('dug' in col_str or 'iznos' in col_str):
                kolona_dug = col
                break
        
        # Ako nije pronađeno po nazivu, koristi poziciju (kolona C = indeks 3)
        if kolona_dug is None and len(df.columns) > 3:
            kolona_dug = df.columns[3]
        
        # Pronađi kolonu sa datumom (ako postoji)
        kolona_datum = None
        for col in df.columns:
            col_str = str(col).strip().lower()
            if 'datum' in col_str or 'naloga' in col_str:
                kolona_datum = col
                break
        
        # Pronađi kolonu sa ulicom/adresom
        kolona_ulica = None
        for col in df.columns:
            col_str = str(col).strip().lower()
            if 'ulica' in col_str or 'adresa' in col_str:
                kolona_ulica = col
                break
        
        # ===== DODAJ JKP ZA OVAJ SHEET =====
        jkp = JKP_PO_GRADOVIMA.get(sheet_name.upper(), f'JKP "{sheet_name}"')
        # ===== DODAJ POŠTANSKI BROJ ZA OVAJ SHEET =====
        postanski_broj = POSTANSKI_BROJEVI.get(sheet_name.upper(), '')
        
        duznici = []
        
        for idx, row in df.iterrows():
            # Preskoči redove koji su prazni
            if all(str(v).strip() == '' for v in row):
                continue
            
            # Preskoči prva 2 reda (zaglavlje)
            if idx < 2:
                continue
            
            # Uzmi ime
            ime = ''
            if kolona_ime and kolona_ime in row:
                ime = str(row[kolona_ime]).strip()
            elif len(df.columns) > 1:
                ime = str(row.iloc[1]).strip()
            
            # Preskoči ako nema ime ili je to zaglavlje
            if not ime or len(ime) < 2:
                continue
            
            # Preskoči redove koji su zaglavlja
            if ime.lower() in ['ime dužnika', 'ime duznika', 'no.', 'redni broj', 'nan']:
                continue
            
            # Uzmi iznos
            iznos_raw = None
            if kolona_dug and kolona_dug in row:
                iznos_raw = str(row[kolona_dug]).strip()
            
            # Ako nema vrednosti, preskoči
            if not iznos_raw or iznos_raw == '' or iznos_raw.lower() == 'nan':
                continue
            
            # Parsiraj iznos
            iznos = parsiraj_broj_iz_stringa(iznos_raw)
            
            # Ako nije uspešno parsiranje, preskoči
            if iznos is None or iznos <= 0:
                continue
            
            # Uzmi datum (ako postoji)
            datum_obj = None
            if kolona_datum and kolona_datum in row:
                datum_raw = str(row[kolona_datum]).strip()
                if datum_raw and datum_raw.lower() != 'nan':
                    datum_obj = parsiraj_datum(datum_raw)
            
            # Uzmi ulicu
            ulica = ''
            if kolona_ulica and kolona_ulica in row:
                ulica = str(row[kolona_ulica]).strip()
                if ulica.lower() == 'nan':
                    ulica = ''
            
            duznici.append({
                'ime_prezime': ime,
                'iznos_osnovnog_duga': iznos,
                'datum_naloga': datum_obj,
                'ulica': ulica,
                'grad': sheet_name.upper(),
                'sheet': sheet_name,
                'jkp': jkp,  # <--- DODATO JKP\
                'postanski_broj': postanski_broj,
            })
        
        return duznici
    except Exception as e:
        st.warning(f"Greška pri učitavanju {sheet_name}: {e}")
        st.code(traceback.format_exc())
        return []

def parsiraj_datum(datum):
    if datum is None:
        return None
    if isinstance(datum, (datetime.datetime, datetime.date)):
        return datum.date() if isinstance(datum, datetime.datetime) else datum
    if isinstance(datum, str):
        datum = datum.strip()
        formati = ['%d.%m.%Y.', '%d.%m.%Y', '%Y-%m-%d', '%m.%d.%Y.', '%m/%d/%Y']
        for fmt in formati:
            try:
                return datetime.datetime.strptime(datum.split()[0], fmt).date()
            except:
                continue
    return None

def generisi_word_duzniku(duznik, kamatna_stopa, template_putanja):
    try:
        danas = datetime.date.today()
        
        ime = duznik['ime_prezime']
        iznos = duznik['iznos_osnovnog_duga']
        datum = duznik['datum_naloga']
        ulica = duznik.get('ulica', '')
        grad = duznik.get('grad', '')
        jkp = duznik.get('jkp', 'JKP')  # <--- DODATO JKP
        postanski_broj = duznik.get('postanski_broj', '')

        if iznos is None or iznos <= 0:
            return None, "Nedostaje iznos duga"
        
        if datum:
            kamata = izracunaj_kamatu(iznos, datum, danas, kamatna_stopa)
            datum_str = datum.strftime('%d.%m.%Y.')
        else:
            kamata = 0
            datum_str = "_____"
        
        ukupan_dug = iznos + kamata + 5000.0
        
        podaci = {
            'ime_prezime': ime,
            'ulica': ulica if ulica else "_______________",
            'grad': grad,
            'postanski_broj': postanski_broj,
            'jkp': jkp,  # <--- DODATO JKP
            'iznos_osnovnog_duga': formatiraj_iznos(iznos),
            'datum_naloga': datum_str,
            'obracun_kamate': formatiraj_iznos(kamata),
            'iznos_ukupnog_duga': formatiraj_iznos(ukupan_dug),
            'datum': datetime.date.today().strftime('%d.%m.%Y.')
        }
        
        if os.path.exists(template_putanja):
            doc = DocxTemplate(template_putanja)
            doc.render(podaci)
            
            for i, paragraph in enumerate(doc.paragraphs[:3]):
                for run in paragraph.runs:
                    run.bold = True
            
            doc_bytes = BytesIO()
            doc.save(doc_bytes)
            doc_bytes.seek(0)
            return doc_bytes, None
        else:
            return None, "Template fajl nije pronađen"
    except Exception as e:
        return None, str(e)

def generisi_sve_duznike(duznici, kamatna_stopa, template_putanja, progress_bar):
    rezultati = []
    for i, duznik in enumerate(duznici):
        doc_bytes, greska = generisi_word_duzniku(duznik, kamatna_stopa, template_putanja)
        if doc_bytes:
            rezultati.append((duznik['ime_prezime'], doc_bytes))
        progress_bar.progress((i + 1) / len(duznici))
    return rezultati

# ============================================
# GLAVNI DEO APLIKACIJE
# ============================================

def main():
    with st.sidebar:
        st.header("📂 1. Upload Excel fajla")
        uploaded_file = st.file_uploader("Izaberite Excel fajl", type=['xlsx', 'xls'])
        
        if uploaded_file:
            excel_file, sheets = ucitaj_sve_sheetove(uploaded_file)
            st.session_state['excel_file'] = excel_file
            st.session_state['sheets'] = sheets
            st.success(f"Pronađeno {len(sheets)} sheet-ova")
        
        st.markdown("---")
        st.header("⚙️ 2. Podešavanja")
        
        nacin_kamate = st.radio("Kamatna stopa:", ["Automatski (NBS)", "Ručno"])
        
        if nacin_kamate == "Ručno":
            kamatna_stopa = st.number_input("Stopa (%)", min_value=0.0, max_value=50.0, value=6.0, step=0.25)
        else:
            kamatna_stopa = dohvati_kamatnu_stopu()
            st.info(f"📊 Trenutna stopa: {kamatna_stopa}%")
            if st.button("🔄 Osveži"):
                st.rerun()
        
        st.markdown("---")
        st.header("🎯 3. Način rada")
        mode = st.radio("Izaberite način rada:", ["Pojedinačni dužnik", "Batch (više dužnika)"])
    
    if uploaded_file is None:
        st.info("👈 **Korak 1:** Izaberite Excel fajl sa leve strane")
        st.markdown("""
        ### Kolone koje program prepoznaje:
        - **Ime dužnika** (kolona sa rečju 'ime' i 'dužnik')
        - **Iznos osnovnog duga** (kolona sa rečju 'osnovnog' i 'dug')
        - **Datum naloga** (kolona sa rečju 'datum') - opciono
        - **Ulica dužnika** (kolona sa rečju 'ulica' ili 'adresa')
        
        ### JKP po gradovima:
        """)
        # Prikaži tabelu JKP po gradovima
        jkp_df = pd.DataFrame(list(JKP_PO_GRADOVIMA.items()), columns=['Grad', 'JKP'])
        st.dataframe(jkp_df, use_container_width=True)
        return
    
    excel_file = st.session_state.get('excel_file')
    sheets = st.session_state.get('sheets', [])
    
    if not sheets:
        st.error("Nema dostupnih sheet-ova!")
        return
    
    st.header("🏙️ 4. Izaberite grad (sheet)")
    izabrani_sheet = st.selectbox("Grad:", sheets)
    
    # Prikaži koji JKP se koristi za ovaj grad
    jkp_za_grad = JKP_PO_GRADOVIMA.get(izabrani_sheet.upper(), f'JKP "{izabrani_sheet}"')
    st.info(f"🏢 JKP za {izabrani_sheet}: **{jkp_za_grad}**")
    
    with st.spinner(f"Učitavam dužnike iz {izabrani_sheet}..."):
        duznici = ucitaj_duznike_iz_sheeta(excel_file, izabrani_sheet)
        st.session_state['duznici'] = duznici
    
    duznici = st.session_state.get('duznici', [])
    
    if not duznici:
        st.warning(f"Nema podataka o dužnicima u sheet-u '{izabrani_sheet}'")
        return
    
    if mode == "Pojedinačni dužnik":
        st.header("👤 5. Izbor dužnika")
        
        opcije = [f"{d['ime_prezime']} ({formatiraj_iznos(d['iznos_osnovnog_duga'])})" for d in duznici]
        izabrani_index = st.selectbox("Izaberite dužnika:", range(len(opcije)), format_func=lambda x: opcije[x])
        duznik = duznici[izabrani_index].copy()
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📋 Podaci iz Excel-a")
            st.write(f"**Ime i prezime:** {duznik['ime_prezime']}")
            st.write(f"**Iznos osnovnog duga:** {formatiraj_iznos(duznik['iznos_osnovnog_duga'])} RSD")
            st.write(f"**JKP:** {duznik.get('jkp', 'Nije definisano')}")
            
            if duznik.get('ulica'):
                st.write(f"**Ulica:** {duznik['ulica']}")
            else:
                st.info("ℹ️ Adresa nije pronađena u Excel-u. Možete je uneti ručno.")
            
            if duznik['datum_naloga']:
                st.write(f"**Datum naloga:** {duznik['datum_naloga'].strftime('%d.%m.%Y.')}")
            else:
                st.warning("⚠️ Datum naloga nije pronađen!")
                datum_rucno = st.date_input("Unesite datum naloga:", value=datetime.date.today())
                duznik['datum_naloga'] = datum_rucno
                st.info("✏️ Datum unet ručno")
        
        with col2:
            st.subheader("🏠 Adresa")
            default_ulica = duznik.get('ulica', '')
            ulica = st.text_input("Ulica i broj:", value=default_ulica, placeholder="Npr. Kralja Petra 10")
            grad = st.text_input("Grad:", value=izabrani_sheet.upper())
            duznik['ulica'] = ulica
            duznik['grad'] = grad
        
        st.markdown("---")
        st.header("💰 Obračun kamate")
        
        danas = datetime.date.today()
        if duznik['datum_naloga'] and duznik['iznos_osnovnog_duga'] > 0:
            kamata = izracunaj_kamatu(duznik['iznos_osnovnog_duga'], duznik['datum_naloga'], danas, kamatna_stopa)
        else:
            kamata = 0
        
        ukupan_dug = duznik['iznos_osnovnog_duga'] + kamata + 5000.0
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Osnovni dug", f"{formatiraj_iznos(duznik['iznos_osnovnog_duga'])} RSD")
        with col2:
            st.metric("Obračunata kamata", f"{formatiraj_iznos(kamata)} RSD", delta=f"stopa: {kamatna_stopa}%", delta_color="off")
        with col3:
            st.metric("Troškovi", "5.000,00 RSD")
        
        st.markdown("---")
        st.markdown(f"## 💰 UKUPNO ZA UPLATU: {formatiraj_iznos(ukupan_dug)} RSD")
        
        if st.button("📄 GENERIŠI I PREUZMI", type="primary", use_container_width=True):
             with st.spinner("Generišem dokument..."):
                doc_bytes, greska = generisi_word_duzniku(duznik, kamatna_stopa, "template.docx")
                if doc_bytes:
                    st.success("✅ Dokument generisan - preuzimanje počinje!")
                    st.download_button(
                        label="💾 PREUZMI DOKUMENT",
                        data=doc_bytes,
                        file_name=f"obavestenje_{duznik['ime_prezime'].replace(' ', '_')}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        use_container_width=True
                    )
                else:
                    st.error(f"Greška: {greska}")
    
    else:
        st.header("📦 Batch generisanje")
        
        st.subheader("Izaberite dužnike:")
        
        izabrani_duznici = []
        for i, d in enumerate(duznici[:100]):
            col1, col2, col3, col4 = st.columns([5, 2, 2, 2])
            with col1:
                selected = st.checkbox(f"{d['ime_prezime']} - {formatiraj_iznos(d['iznos_osnovnog_duga'])} RSD", key=f"batch_{i}")
            with col2:
                if d['datum_naloga']:
                    st.write(d['datum_naloga'].strftime('%d.%m.%Y.'))
                else:
                    st.write("bez datuma")
            with col3:
                if d.get('ulica'):
                    st.write("📍 ima adresu")
                else:
                    st.write("")
            with col4:
                st.write(d.get('jkp', '')[:20] + '...' if len(d.get('jkp', '')) > 20 else d.get('jkp', ''))
            if selected:
                d['grad'] = izabrani_sheet.upper()
                izabrani_duznici.append(d)
        
        if len(duznici) > 100:
            st.info(f"Prikazano prvih 100 od {len(duznici)} dužnika.")
        
        if izabrani_duznici:
            st.info(f"Izabrano {len(izabrani_duznici)} dužnika")
            
            batch_ulica = st.text_input("Ulica (zajednička za sve):", placeholder="Ostavi prazno za ulicu iz Excel-a")
            
            if st.button("🚀 GENERIŠI SVE", type="primary", use_container_width=True):
                with st.spinner(f"Generišem {len(izabrani_duznici)} dokumenata..."):
                    for d in izabrani_duznici:
                        if batch_ulica:
                            d['ulica'] = batch_ulica
                    
                    from zipfile import ZipFile
                    zip_bytes = BytesIO()
                    uspesno = 0
                    
                    with ZipFile(zip_bytes, 'w') as zipf:
                        for i, duznik in enumerate(izabrani_duznici):
                            doc_bytes, greska = generisi_word_duzniku(duznik, kamatna_stopa, "template.docx")
                            if doc_bytes:
                                zipf.writestr(f"obavestenje_{duznik['ime_prezime'].replace(' ', '_')}.docx", doc_bytes.getvalue())
                                uspesno += 1
                    
                    if uspesno > 0:
                        zip_bytes.seek(0)
                        st.success(f"✅ Uspešno generisano {uspesno} od {len(izabrani_duznici)} dokumenata")
                        
                        b64 = base64.b64encode(zip_bytes.getvalue()).decode()
                        href = f'<a href="data:application/zip;base64,{b64}" download="obavestenja_{izabrani_sheet}_{datetime.date.today()}.zip" id="download-link" style="display:none">Download</a>'
                        st.markdown(href, unsafe_allow_html=True)
                        st.markdown("""
                            <script>
                                document.getElementById('download-link').click();
                            </script>
                        """, unsafe_allow_html=True)
                        st.stop()
                    else:
                        st.error("Nijedan dokument nije uspešno generisan!")
        else:
            st.info("Izaberite dužnike za generisanje")

if __name__ == "__main__":
    main()