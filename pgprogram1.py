import streamlit as st
import sqlite3
import pandas as pd

# Konfiguracja strony
st.set_page_config(page_title="Zarządzanie Produktami", layout="wide")

# Funkcja łącząca z bazą
def get_connection():
    conn = sqlite3.connect('magazyn.db', check_same_thread=False)
    return conn

conn = get_connection()
cursor = conn.cursor()

# Inicjalizacja tabel (jeśli nie istnieją)
cursor.execute('''CREATE TABLE IF NOT EXISTS Kategoria 
                  (id INTEGER PRIMARY KEY, nazwa TEXT, opis TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS produkty 
                  (id INTEGER PRIMARY KEY, nazwa TEXT, liczba INTEGER, Cena REAL, kategoria_id INTEGER)''')
conn.commit()

st.title("📦 System Zarządzania Magazynem")

# --- BOCZNY PANEL: DODAWANIE DANYCH ---
st.sidebar.header("Dodaj nowe dane")

# Formularz Kategorii
with st.sidebar.expander("Dodaj Kategorię"):
    kat_nazwa = st.text_input("Nazwa Kategorii")
    kat_opis = st.text_area("Opis Kategorii")
    if st.button("Zapisz Kategorię"):
        cursor.execute("INSERT INTO Kategoria (nazwa, opis) VALUES (?, ?)", (kat_nazwa, kat_opis))
        conn.commit()
        st.success("Dodano kategorię!")

# Formularz Produktu
with st.sidebar.expander("Dodaj Produkt"):
    # Pobieramy aktualne kategorie do listy wyboru
    kategorie_df = pd.read_sql_query("SELECT id, nazwa FROM Kategoria", conn)
    
    prod_nazwa = st.text_input("Nazwa Produktu")
    prod_liczba = st.number_input("Liczba", min_value=0, step=1)
    prod_cena = st.number_input("Cena", min_value=0.0, step=0.01)
    
    if not kategorie_df.empty:
        opcje_kat = dict(zip(kategorie_df['nazwa'], kategorie_df['id']))
        wybrana_kat = st.selectbox("Wybierz Kategorię", options=opcje_kat.keys())
        
        if st.button("Zapisz Produkt"):
            cursor.execute("INSERT INTO produkty (nazwa, liczba, Cena, kategoria_id) VALUES (?, ?, ?, ?)",
                           (prod_nazwa, prod_liczba, prod_cena, opcje_kat[wybrana_kat]))
            conn.commit()
            st.info("Dodano produkt!")
    else:
        st.warning("Najpierw dodaj kategorię!")

# --- GŁÓWNY PANEL: WYŚWIETLANIE ---
st.header("Aktualny stan magazynowy")

# Zapytanie SQL z JOIN, aby połączyć tabele
query = '''
    SELECT p.id, p.nazwa AS Produkt, p.liczba, p.Cena, k.nazwa AS Kategoria
    FROM produkty p
    LEFT JOIN Kategoria k ON p.kategoria_id = k.id
'''
df = pd.read_sql_query(query, conn)

if not df.empty:
    st.dataframe(df, use_container_width=True)
    
    # Małe podsumowanie (Wykres)
    st.subheader("Wartość produktów w kategoriach")
    df['Suma'] = df['liczba'] * df['Cena']
    chart_data = df.groupby('Kategoria')['Suma'].sum()
    st.bar_chart(chart_data)
else:
    st.write("Baza jest pusta. Dodaj dane w panelu bocznym.")

conn.close()
