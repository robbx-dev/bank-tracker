import streamlit as st
import pandas as pd
import plotly.express as px
import pdfplumber
import re

# 1. Mobile-optimierte Konfiguration
st.set_page_config(page_title="DKB Finanz-Tracker", page_icon="💶", layout="centered", initial_sidebar_state="auto")

st.title("💶 Mein DKB Tracker")
st.markdown("Mobile-ready: Lade deine Auszüge hoch, filtere Daten und exportiere sie.")

# 2. Hilfsfunktion zur Kategorisierung
def kategorisieren(text):
    text = str(text).lower()
    if 'mosolf' in text: return 'Gehalt'
    if 'kindergeld' in text: return 'Kindergeld'
    if 'miete' in text or 'wbg' in text: return 'Wohnen'
    if 'eprimo' in text: return 'Energie'
    if 'telecom' in text or 'telefonica' in text or 'waiputv' in text: return 'Kommunikation & Medien'
    if 'bankil' in text or 'bank11' in text or 'barclays' in text or 'darl.' in text or 'kredit' in text: return 'Kredite & Finanzierung'
    if 'visa' in text: return 'Kreditkarte'
    if 'taschengeld' in text or 'unterhalt' in text: return 'Kind'
    if 'urlaub' in text or 'ausgleich' in text or 'sparen' in text: return 'Umbuchungen/Sparen'
    if 'reiten' in text or 'amateursportclub' in text: return 'Freizeit'
    return 'Sonstiges'

# 3. Daten einlesen (PDF oder CSV)
@st.cache_data
def lade_daten(uploaded_file):
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file, sep=';', encoding='latin1', skiprows=4)
        df = df.rename(columns={'Buchungstag': 'Datum', 'Umsatzart': 'Beschreibung', 'Betrag (EUR)': 'Betrag'})
        df['Betrag'] = pd.to_numeric(df['Betrag'].astype(str).str.replace(',', '.'), errors='coerce')
    
    elif uploaded_file.name.endswith('.pdf'):
        records = []
        with pdfplumber.open(uploaded_file) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if not text: continue
                
                for line in text.split('\n'):
                    match = re.search(r'^(\d{2}\.\d{2}\.\d{4})\s+(.+?)\s+(-?\d{1,3}(?:\.\d{3})*,\d{2}|-?\d+\.\d{2})$', line.strip())
                    if match:
                        datum = match.group(1)
                        beschreibung = match.group(2)
                        betrag_str = match.group(3).replace('.', '').replace(',', '.')
                        try:
                            betrag = float(betrag_str)
                            records.append({'Datum': datum, 'Beschreibung': beschreibung, 'Betrag': betrag})
                        except:
                            pass
        df = pd.DataFrame(records)
    else:
        return pd.DataFrame()

    if not df.empty:
        df['Datum'] = pd.to_datetime(df['Datum'], format='%d.%m.%Y', errors='coerce')
        df = df.dropna(subset=['Datum', 'Betrag'])
        df['Kategorie'] = df['Beschreibung'].apply(kategorisieren)
        df['Monat_Jahr'] = df['Datum'].dt.to_period('M').astype(str)
    
    return df

# 4. Upload Widget
uploaded_file = st.file_uploader("Kontoauszug (.pdf oder .csv) hochladen", type=['csv', 'pdf'])

if uploaded_file is not None:
    df = lade_daten(uploaded_file)
    
    if df.empty:
        st.error("Konnte keine Daten aus der Datei extrahieren.")
    else:
        # 5. Mobile-freundliche Filter
        with st.expander("🔍 Filter einstellen", expanded=False):
            monate = sorted(df['Monat_Jahr'].unique())
            gewaehlte_monate = st.multiselect("Monat(e) wählen:", monate, default=monate)
            
            kategorien = sorted(df['Kategorie'].unique())
            gewaehlte_kategorien = st.multiselect("Kategorien wählen:", kategorien, default=kategorien)
            
            suchtext = st.text_input("Freitextsuche (z.B. 'Mosolf'):")

        mask = (df['Monat_Jahr'].isin(gewaehlte_monate)) & (df['Kategorie'].isin(gewaehlte_kategorien))
        if suchtext:
            mask = mask & (df['Beschreibung'].str.contains(suchtext, case=False, na=False))
        
        df_filtered = df[mask]

        # 6. Übersichtliche Tabs für Mobile
        tab1, tab2, tab3 = st.tabs(["📊 Graphen", "📝 Daten", "💾 Export"])

        with tab1:
            st.subheader("Auswertungen")
            if not df_filtered.empty:
                df_ausgaben = df_filtered[df_filtered['Betrag'] < 0].copy()
                df_ausgaben['Betrag (Absolut)'] = df_ausgaben['Betrag'].abs()
                
                summary = df_filtered.copy()
                summary['Typ'] = summary['Betrag'].apply(lambda x: 'Einnahme' if x > 0 else 'Ausgabe')
                summary['Absolut'] = summary['Betrag'].abs()
                df_group = summary.groupby(['Monat_Jahr', 'Typ'])['Absolut'].sum().reset_index()
                
                fig_bar = px.bar(df_group, x='Monat_Jahr', y='Absolut', color='Typ', barmode='group',
                                 color_discrete_map={'Einnahme': '#2ecc71', 'Ausgabe': '#e74c3c'},
                                 title="Cashflow pro Monat")
                fig_bar.update_layout(xaxis_title="Monat", yaxis_title="Betrag (€)", legend_title="")
                st.plotly_chart(fig_bar, use_container_width=True)

                if not df_ausgaben.empty:
                    fig_pie = px.pie(df_ausgaben, values='Betrag (Absolut)', names='Kategorie', 
                                     title="Wohin fließt das Geld?", hole=0.4)
                    fig_pie.update_traces(textposition='inside', textinfo='percent')
                    st.plotly_chart(fig_pie, use_container_width=True)

        with tab2:
            st.subheader("Detail-Tabelle")
            st.dataframe(df_filtered[['Datum', 'Kategorie', 'Beschreibung', 'Betrag']].sort_values('Datum', ascending=False), use_container_width=True)

        with tab3:
            st.subheader("Export")
            st.write(f"{len(df_filtered)} gefilterte Datensätze bereit zum Download.")
            csv = df_filtered.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig')
            st.download_button(
                label="📥 Gefilterte Daten als CSV herunterladen",
                data=csv,
                file_name='dkb_auswertung.csv',
                mime='text/csv',
            )
else:
    st.info("Bitte lade eine Datei hoch, um zu starten.")
