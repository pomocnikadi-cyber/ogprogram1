import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px

# --- KONFIGURACJA STRONY ---
st.set_page_config(
    page_title="Magazyn 2.0 - System Zarządzania",
    page_icon="📦",
    layout="wide"
)

# --- CSS (Drobne poprawki wizualne) ---
st.markdown("""
    <style>
    .main {
        background-color: #f5f5f5;
    }
    .stMetric {
        background-color: white;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
    }
    </style>
    """, unsafe_allow_html=True)

# --- BAZA DANYCH ---
@st.cache_resource
def get_connection():
    conn = sqlite3.connect('magazyn.db', check_same_thread=False)
    return conn

conn = get_connection()
cursor = conn.cursor()

# Tworzenie tabel
cursor.execute('''CREATE TABLE IF NOT EXISTS Kategoria 
                  (id INTEGER PRIMARY KEY, nazwa TEXT, opis TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS produkty 
                  (id INTEGER PRIMARY KEY, nazwa TEXT, liczba INTEGER, Cena REAL, kategoria_id INTEGER)''')
conn.commit()

# --- PANEL BOCZNY (SIDEBAR) - OPERACJE DODAWANIA ---
st.sidebar.title("🛠️ Panel Sterowania")
st.sidebar.markdown("---")

opcja = st.sidebar.radio("Wybierz akcję:", ["Dodaj Produkt", "Dodaj Kategorię"])

if opcja == "Dodaj Kategorię":
    st.sidebar.subheader("Nowa Kategoria")
    kat_nazwa = st.sidebar.text_input("Nazwa Kategorii")
    kat_opis = st.sidebar.text_area("Opis Kategorii")
    if st.sidebar.button("Zapisz Kategorię"):
        if kat_nazwa:
            cursor.execute("INSERT INTO Kategoria (nazwa, opis) VALUES (?, ?)", (kat_nazwa, kat_opis))
            conn.commit()
            st.sidebar.success(f"Dodano kategorię: {kat_nazwa}")
            st.rerun()
        else:
            st.sidebar.error("Nazwa nie może być pusta!")

elif opcja == "Dodaj Produkt":
    st.sidebar.subheader("Nowy Produkt")
    kategorie_df = pd.read_sql_query("SELECT id, nazwa FROM Kategoria", conn)
    
    if not kategorie_df.empty:
        prod_nazwa = st.sidebar.text_input("Nazwa Produktu")
        col1, col2 = st.sidebar.columns(2)
        with col1:
            prod_liczba = st.number_input("Ilość (szt)", min_value=0, step=1)
        with col2:
            prod_cena = st.number_input("Cena (PLN)", min_value=0.0, step=0.01)
        
        opcje_kat = dict(zip(kategorie_df['nazwa'], kategorie_df['id']))
        wybrana_kat = st.sidebar.selectbox("Kategoria", options=opcje_kat.keys())
        
        if st.sidebar.button("Zapisz Produkt"):
            if prod_nazwa:
                cursor.execute("INSERT INTO produkty (nazwa, liczba, Cena, kategoria_id) VALUES (?, ?, ?, ?)",
                               (prod_nazwa, prod_liczba, prod_cena, opcje_kat[wybrana_kat]))
                conn.commit()
                st.sidebar.success("Produkt dodany pomyślnie!")
                st.rerun()
            else:
                st.sidebar.error("Podaj nazwę produktu!")
    else:
        st.sidebar.warning("Najpierw dodaj przynajmniej jedną kategorię!")

st.sidebar.markdown("---")
st.sidebar.info("Projekt zaliczeniowy: System Magazynowy v2.0")

# --- GŁÓWNY WIDOK ---
st.title("📦 System Zarządzania Magazynem 2.0")

# Pobranie danych do DataFrame
query = '''
    SELECT p.id, p.nazwa AS Produkt, p.liczba AS Ilość, p.Cena, k.nazwa AS Kategoria
    FROM produkty p
    LEFT JOIN Kategoria k ON p.kategoria_id = k.id
'''
df = pd.read_sql_query(query, conn)
df['Wartość'] = df['Ilość'] * df['Cena']

# Zakładki (Tabs) dla lepszej organizacji
tab1, tab2, tab3 = st.tabs(["📊 Dashboard Analityczny", "📋 Lista Produktów i Edycja", "⚠️ Alerty Magazynowe"])

# --- ZAKŁADKA 1: DASHBOARD ---
with tab1:
    if not df.empty:
        # Metryki KPI (Key Performance Indicators)
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Liczba Produktów", f"{df['Produkt'].count()} szt.")
        col2.metric("Całkowita Ilość", f"{df['Ilość'].sum()} szt.")
        col3.metric("Wartość Magazynu", f"{df['Wartość'].sum():.2f} PLN")
        col4.metric("Średnia Cena", f"{df['Cena'].mean():.2f} PLN")
        
        st.markdown("---")
        
        # Wykresy w dwóch kolumnach
        c1, c2 = st.columns(2)
        
        with c1:
            st.subheader("Wartość w Kategoriach")
            # Wykres kołowy (Donut chart) z Plotly
            fig_pie = px.pie(df, values='Wartość', names='Kategoria', hole=0.4, 
                             color_discrete_sequence=px.colors.sequential.RdBu)
            st.plotly_chart(fig_pie, use_container_width=True)
            
        with c2:
            st.subheader("Ilość produktów")
            # Wykres słupkowy
            fig_bar = px.bar(df, x='Produkt', y='Ilość', color='Kategoria',
                             text_auto=True)
            st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.info("Brak danych do wyświetlenia. Dodaj produkty w panelu bocznym.")

# --- ZAKŁADKA 2: LISTA I USUWANIE ---
with tab2:
    st.subheader("Pełny stan magazynowy")
    
    # Wyświetlanie tabeli z kolorowaniem (gradient dla ceny)
    st.dataframe(df.style.background_gradient(subset=['Cena'], cmap="Greens"), use_container_width=True)
    
    st.markdown("---")
    
    # Sekcja usuwania
    col_del1, col_del2 = st.columns([2, 1])
    with col_del1:
        st.warning("🗑️ **Strefa usuwania**")
        produkty_do_usuniecia = st.multiselect("Wybierz produkty do usunięcia:", df['Produkt'].unique())
    
    with col_del2:
        st.write("") # Odstęp
        st.write("") 
        if st.button("Usuń wybrane", type="primary"):
            if produkty_do_usuniecia:
                # Konwersja nazw na listę do SQL
                placeholders = ', '.join(['?'] * len(produkty_do_usuniecia))
                cursor.execute(f"DELETE FROM produkty WHERE nazwa IN ({placeholders})", produkty_do_usuniecia)
                conn.commit()
                st.success("Usunięto wybrane produkty!")
                st.rerun()
            else:
                st.error("Nie wybrano nic do usunięcia.")

    # Eksport danych
    st.markdown("---")
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Pobierz dane do CSV (Excel)",
        data=csv,
        file_name='stan_magazynowy.csv',
        mime='text/csv',
    )

# --- ZAKŁADKA 3: ALERTY ---
with tab3:
    st.subheader("⚠️ Produkty z niskim stanem")
    limit = st.slider("Ustal próg ostrzegawczy (ilość sztuk):", 1, 50, 5)
    
    low_stock = df[df['Ilość'] < limit]
    
    if not low_stock.empty:
        st.error(f"Uwaga! Znaleziono {len(low_stock)} produktów poniżej progu {limit} sztuk.")
        for index, row in low_stock.iterrows():
            st.markdown(f"- **{row['Produkt']}**: Zostało tylko {row['Ilość']} szt. (Kategoria: {row['Kategoria']})")
    else:
        st.success("Wszystkie stany magazynowe są w normie! ✅")
