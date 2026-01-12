import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
from streamlit_option_menu import option_menu
import qrcode
from io import BytesIO
from datetime import datetime

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="NexGen Warehouse", page_icon="🏢", layout="wide")

# --- STYLE CSS ---
st.markdown("""
    <style>
        .block-container {padding-top: 1rem; padding-bottom: 5rem;}
        div[data-testid="stMetric"] {
            background-color: #ffffff;
            border: 1px solid #e6e6e6;
            padding: 15px;
            border-radius: 10px;
            color: #31333F;
            box-shadow: 0px 2px 4px rgba(0,0,0,0.05);
        }
        div[data-testid="stMetricLabel"] {color: #6c757d; font-weight: bold;}
        div[data-testid="stMetricValue"] {color: #000000;}
    </style>
""", unsafe_allow_html=True)

# --- BAZA DANYCH ---
@st.cache_resource
def get_connection():
    conn = sqlite3.connect('magazyn_pro.db', check_same_thread=False)
    return conn

conn = get_connection()
cursor = conn.cursor()

# Inicjalizacja tabel
cursor.execute('''CREATE TABLE IF NOT EXISTS Kategorie (id INTEGER PRIMARY KEY, nazwa TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS Produkty 
                  (id INTEGER PRIMARY KEY, nazwa TEXT, ilosc INTEGER, cena REAL, kategoria_id INTEGER, 
                   min_stan INTEGER DEFAULT 5, kod_sku TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS Historia 
                  (id INTEGER PRIMARY KEY, data TEXT, produkt TEXT, akcja TEXT, ilosc INTEGER, opis TEXT)''')
conn.commit()

# --- FUNKCJE POMOCNICZE ---
def log_action(produkt, akcja, ilosc, opis):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("INSERT INTO Historia (data, produkt, akcja, ilosc, opis) VALUES (?, ?, ?, ?, ?)",
                   (now, produkt, akcja, ilosc, opis))
    conn.commit()

def generate_qr(data):
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    return img

# --- MENU BOCZNE ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2897/2897785.png", width=50)
    st.title("NexGen WMS")
    selected = option_menu(
        menu_title=None,
        options=["Dashboard", "Magazyn", "Operacje", "Raporty", "Dodaj Nowy"],
        icons=["speedometer2", "box-seam", "arrow-left-right", "file-earmark-bar-graph", "plus-circle"],
        menu_icon="cast",
        default_index=0,
        styles={
            "container": {"padding": "0!important", "background-color": "#fafafa"},
            "icon": {"color": "orange", "font-size": "20px"}, 
            "nav-link": {"font-size": "16px", "text-align": "left", "margin":"0px", "--hover-color": "#eee"},
            "nav-link-selected": {"background-color": "#ff4b4b"},
        }
    )
    st.info("System w wersji v2.4")

# --- POBRANIE DANYCH ---
df_prod = pd.read_sql_query('''
    SELECT p.id, p.nazwa AS Produkt, p.ilosc AS Stan, p.cena AS Cena, k.nazwa AS Kategoria, p.min_stan, p.kod_sku
    FROM Produkty p LEFT JOIN Kategorie k ON p.kategoria_id = k.id
''', conn)
df_prod['Wartość'] = df_prod['Stan'] * df_prod['Cena']

# ================= DASHBOARD =================
if selected == "Dashboard":
    st.header(f"Witaj! Przegląd magazynu")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📦 Łącznie Produktów", f"{df_prod['Stan'].sum()} szt")
    col2.metric("💰 Wartość Magazynu", f"{df_prod['Wartość'].sum():,.2f} PLN")
    col3.metric("📉 Niskie Stany", f"{len(df_prod[df_prod['Stan'] <= df_prod['min_stan']])}")
    col4.metric("📂 Kategorie", f"{df_prod['Kategoria'].nunique()}")

    st.markdown("---")

    c1, c2 = st.columns([2, 1])
    with c1:
        st.subheader("Struktura Wartości")
        if not df_prod.empty:
            fig = px.sunburst(
                df_prod, 
                path=['Kategoria', 'Produkt'], 
                values='Wartość', 
                color='Kategoria',
                color_discrete_sequence=px.colors.qualitative.Pastel
            )
            fig.update_layout(margin=dict(t=0, l=0, r=0, b=0))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("Brak danych do wykresu.")
    
    with c2:
        st.subheader("Ostatnie operacje")
        df_hist = pd.read_sql_query("SELECT data, produkt, akcja, ilosc FROM Historia ORDER BY id DESC LIMIT 5", conn)
        st.dataframe(df_hist, use_container_width=True, hide_index=True)

# ================= MAGAZYN =================
elif selected == "Magazyn":
    st.header("📋 Pełny stan magazynowy")
    st.caption("Kliknij dwukrotnie w komórkę tabeli, aby edytować dane.")

    edited_df = st.data_editor(
        df_prod[['id', 'Produkt', 'Stan', 'Cena', 'Kategoria', 'min_stan', 'kod_sku']],
        key="editor",
        num_rows="dynamic",
        disabled=["id", "Wartość"],
        use_container_width=True
    )
    
    if st.button("💾 Zapisz zmiany (Demo)"):
        st.success("W wersji demonstracyjnej edycja bezpośrednia tabeli nie zapisuje zmian w SQL (użyj Operacji lub Dodaj Nowy).")

    st.markdown("---")
    st.subheader("🖨️ Generator Etykiet QR")
    wybor_qr = st.selectbox("Wybierz produkt:", df_prod['Produkt'].unique())
    
    if wybor_qr:
        row = df_prod[df_prod['Produkt'] == wybor_qr].iloc[0]
        col_qr1, col_qr2 = st.columns([1, 4])
        info_str = f"ID: {row['id']}\nProdukt: {row['Produkt']}\nCena: {row['Cena']} PLN\nSKU: {row['kod_sku']}"
        img = generate_qr(info_str)
        with col_qr1:
            buf = BytesIO()
            img.save(buf)
            st.image(buf, width=150)
        with col_qr2:
            st.info(f"**Dane:**\n{info_str}")

# ================= OPERACJE =================
elif selected == "Operacje":
    st.header("🔄 Przyjęcia i Wydania")
    
    col_op1, col_op2 = st.columns(2)
    
    with col_op1:
        st.subheader("Wybierz towar")
        
        product_map = {f"{row['Produkt']} (ID: {row['id']})": row['id'] for index, row in df_prod.iterrows()}
        selected_label = st.selectbox("Produkt", options=list(product_map.keys()))
        
        selected_id = None
        current_prod_name = ""
        
        if selected_label:
            selected_id = product_map[selected_label]
            current_prod_name = df_prod[df_prod['id'] == selected_id]['Produkt'].values[0]

        ilosc_op = st.number_input("Ilość", min_value=1, step=1)
        opis_op = st.text_input("Komentarz / Nr dokumentu")
    
    with col_op2:
        st.subheader("Rodzaj operacji")
        
        if selected_id:
            curr_stock_val = cursor.execute("SELECT ilosc FROM Produkty WHERE id = ?", (selected_id,)).fetchone()[0]
            st.metric("Aktualny stan (wybranego ID)", f"{curr_stock_val} szt.")
        
            c_btn1, c_btn2 = st.columns(2)
            
            if c_btn1.button("📥 PRZYJĘCIE (+)", use_container_width=True, type="primary"):
                cursor.execute("UPDATE Produkty SET ilosc = ilosc + ? WHERE id = ?", (ilosc_op, selected_id))
                log_action(current_prod_name, "PRZYJĘCIE", ilosc_op, opis_op)
                conn.commit()
                st.success(f"Zaktualizowano stan dla ID: {selected_id}")
                st.rerun()
                
            if c_btn2.button("📤 WYDANIE (-)", use_container_width=True):
                if curr_stock_val >= ilosc_op:
                    cursor.execute("UPDATE Produkty SET ilosc = ilosc - ? WHERE id = ?", (ilosc_op, selected_id))
                    log_action(current_prod_name, "WYDANIE", ilosc_op, opis_op)
                    conn.commit()
                    st.warning(f"Wydano towar z ID: {selected_id}")
                    st.rerun()
                else:
                    st.error("Brak wystarczającej ilości towaru!")

# ================= RAPORTY =================
elif selected == "Raporty":
    st.header("📑 Historia Operacji")
    search_hist = st.text_input("Szukaj...", placeholder="Nazwa produktu...")
    
    query_hist = "SELECT * FROM Historia ORDER BY id DESC"
    df_history = pd.read_sql_query(query_hist, conn)
    
    if search_hist:
        df_history = df_history[df_history['produkt'].str.contains(search_hist, case=False) | 
                                df_history['akcja'].str.contains(search_hist, case=False)]
    
    st.dataframe(df_history, use_container_width=True)

# ================= DODAWANIE =================
elif selected == "Dodaj Nowy":
    st.header("➕ Rejestracja nowego asortymentu")
    
    with st.form("new_prod"):
        c1, c2 = st.columns(2)
        n_nazwa = c1.text_input("Nazwa Produktu")
        n_sku = c2.text_input("Kod SKU")
        
        c3, c4, c5 = st.columns(3)
        n_ilosc = c3.number_input("Stan początkowy", 0)
        n_cena = c4.number_input("Cena (PLN)", 0.0)
        n_min = c5.number_input("Min. stan", 5)
        
        cats = pd.read_sql_query("SELECT id, nazwa FROM Kategorie", conn)
        new_cat_txt = st.text_input("Nowa kategoria (opcjonalnie)")
        
        selected_cat_id = None
        if not cats.empty:
            cat_name = st.selectbox("Wybierz kategorię", cats['nazwa'])
            selected_cat_id = cats[cats['nazwa'] == cat_name]['id'].values[0]
        
        submitted = st.form_submit_button("Zapisz w bazie")
        
        if submitted:
            exists = cursor.execute("SELECT id FROM Produkty WHERE nazwa = ?", (n_nazwa,)).fetchone()
            
            if exists:
                st.error(f"BŁĄD: Produkt o nazwie '{n_nazwa}' już istnieje w bazie!")
            elif not n_nazwa:
                st.error("Podaj nazwę produktu.")
            else:
                if new_cat_txt:
                    cursor.execute("INSERT INTO Kategorie (nazwa) VALUES (?)", (new_cat_txt,))
                    conn.commit()
                    selected_cat_id = cursor.lastrowid
                
                if selected_cat_id:
                    cursor.execute("""
                        INSERT INTO Produkty (nazwa, ilosc, cena, kategoria_id, min_stan, kod_sku) 
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (n_nazwa, n_ilosc, n_cena, selected_cat_id, n_min, n_sku))
                    
                    log_action(n_nazwa, "UTWORZENIE", n_ilosc, "Inicjalizacja")
                    conn.commit()
                    st.success(f"Dodano nowy produkt: {n_nazwa}")
                    st.rerun()
                else:
                    st.error("Wybierz lub dodaj kategorię.")
