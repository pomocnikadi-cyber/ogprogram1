import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_option_menu import option_menu
import qrcode
from io import BytesIO
from datetime import datetime
from supabase import create_client

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

# --- POŁĄCZENIE Z SUPABASE ---
@st.cache_resource
def init_connection():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error("Brakuje sekretów w .streamlit/secrets.toml lub panelu Streamlit Cloud!")
        st.stop()

supabase = init_connection()

# --- FUNKCJE POMOCNICZE ---
def log_action(produkt, akcja, ilosc, opis):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data = {
        "data": now,
        "produkt": produkt,
        "akcja": akcja,
        "ilosc": int(ilosc),
        "opis": opis
    }
    supabase.table("Historia").insert(data).execute()

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
    st.info("System w wersji v2.4 (Cloud)")

# --- POBRANIE DANYCH (SUPABASE) ---
# Pobieramy produkty
resp_prod = supabase.table("Produkty").select("*").execute()
df_prod_raw = pd.DataFrame(resp_prod.data)

# Pobieramy kategorie
resp_cat = supabase.table("Kategorie").select("*").execute()
df_cat = pd.DataFrame(resp_cat.data)

# Łączenie danych (zamiast SQL JOIN robimy to w Pandas)
if not df_prod_raw.empty:
    if not df_cat.empty:
        # Zmieniamy nazwę kolumny id w kategoriach, żeby się nie gryzła
        df_cat_renamed = df_cat.rename(columns={"id": "cat_id_ref", "nazwa": "Kategoria"})
        df_prod = pd.merge(df_prod_raw, df_cat_renamed, left_on="kategoria_id", right_on="cat_id_ref", how="left")
    else:
        df_prod = df_prod_raw
        df_prod["Kategoria"] = "Brak"
    
    # Formatowanie kolumn do wyświetlania
    df_prod['Wartość'] = df_prod['ilosc'] * df_prod['cena']
    df_prod = df_prod.rename(columns={"nazwa": "Produkt", "ilosc": "Stan", "cena": "Cena"})
else:
    df_prod = pd.DataFrame(columns=["id", "Produkt", "Stan", "Cena", "Kategoria", "min_stan", "kod_sku", "Wartość"])

# ================= DASHBOARD =================
if selected == "Dashboard":
    st.header(f"Witaj! Przegląd magazynu")
    
    col1, col2, col3, col4 = st.columns(4)
    total_items = df_prod['Stan'].sum() if not df_prod.empty else 0
    total_value = df_prod['Wartość'].sum() if not df_prod.empty else 0
    low_stock = len(df_prod[df_prod['Stan'] <= df_prod['min_stan']]) if not df_prod.empty else 0
    total_cats = df_prod['Kategoria'].nunique() if 'Kategoria' in df_prod.columns else 0

    col1.metric("📦 Łącznie Produktów", f"{total_items} szt")
    col2.metric("💰 Wartość Magazynu", f"{total_value:,.2f} PLN")
    col3.metric("📉 Niskie Stany", f"{low_stock}")
    col4.metric("📂 Kategorie", f"{total_cats}")

    st.markdown("---")

    c1, c2 = st.columns([2, 1])
    with c1:
        st.subheader("Struktura Wartości")
        if not df_prod.empty and 'Kategoria' in df_prod.columns:
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
        resp_hist = supabase.table("Historia").select("data, produkt, akcja, ilosc").order("id", desc=True).limit(5).execute()
        df_hist = pd.DataFrame(resp_hist.data)
        st.dataframe(df_hist, use_container_width=True, hide_index=True)

# ================= MAGAZYN =================
elif selected == "Magazyn":
    st.header("📋 Pełny stan magazynowy")
    st.caption("Edycja bezpośrednia w tabeli nie jest obsługiwana w tym widoku (użyj Operacji).")

    if not df_prod.empty:
        st.dataframe(
            df_prod[['id', 'Produkt', 'Stan', 'Cena', 'Kategoria', 'min_stan', 'kod_sku']],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("Magazyn jest pusty.")

    st.markdown("---")
    st.subheader("🖨️ Generator Etykiet QR")
    
    opcje = df_prod['Produkt'].unique() if not df_prod.empty else []
    wybor_qr = st.selectbox("Wybierz produkt:", opcje)
    
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
        
        product_map = {f"{row['Produkt']} (ID: {row['id']})": row['id'] for index, row in df_prod.iterrows()} if not df_prod.empty else {}
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
            # Pobieramy aktualny stan bezpośrednio z bazy, aby uniknąć błędów
            curr_stock_resp = supabase.table("Produkty").select("ilosc").eq("id", selected_id).execute()
            curr_stock_val = curr_stock_resp.data[0]['ilosc']
            
            st.metric("Aktualny stan (Baza)", f"{curr_stock_val} szt.")
            
            c_btn1, c_btn2 = st.columns(2)
            
            if c_btn1.button("📥 PRZYJĘCIE (+)", use_container_width=True, type="primary"):
                new_ilosc = int(curr_stock_val + ilosc_op)
                supabase.table("Produkty").update({"ilosc": new_ilosc}).eq("id", selected_id).execute()
                log_action(current_prod_name, "PRZYJĘCIE", ilosc_op, opis_op)
                st.success(f"Zaktualizowano stan dla ID: {selected_id}")
                st.rerun()
                
            if c_btn2.button("📤 WYDANIE (-)", use_container_width=True):
                if curr_stock_val >= ilosc_op:
                    new_ilosc = int(curr_stock_val - ilosc_op)
                    supabase.table("Produkty").update({"ilosc": new_ilosc}).eq("id", selected_id).execute()
                    log_action(current_prod_name, "WYDANIE", ilosc_op, opis_op)
                    st.warning(f"Wydano towar z ID: {selected_id}")
                    st.rerun()
                else:
                    st.error("Brak wystarczającej ilości towaru!")

# ================= RAPORTY =================
elif selected == "Raporty":
    st.header("📑 Historia Operacji")
    search_hist = st.text_input("Szukaj...", placeholder="Nazwa produktu...")
    
    resp_h = supabase.table("Historia").select("*").order("id", desc=True).execute()
    df_history = pd.DataFrame(resp_h.data)
    
    if not df_history.empty:
        if search_hist:
            df_history = df_history[df_history['produkt'].str.contains(search_hist, case=False) | 
                                    df_history['akcja'].str.contains(search_hist, case=False)]
        st.dataframe(df_history, use_container_width=True)
    else:
        st.info("Brak historii operacji.")

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
        
        # Pobierz kategorie do listy
        cats_resp = supabase.table("Kategorie").select("*").execute()
        cats_df = pd.DataFrame(cats_resp.data)
        
        cat_names = cats_df['nazwa'].tolist() if not cats_df.empty else []
        new_cat_txt = st.text_input("Nowa kategoria (jeśli nie ma na liście)")
        
        selected_cat_name = st.selectbox("Wybierz istniejącą kategorię", ["-- Wybierz --"] + cat_names)
        
        submitted = st.form_submit_button("Zapisz w bazie")
        
        if submitted:
            # Sprawdź czy produkt istnieje
            exists_resp = supabase.table("Produkty").select("id").eq("nazwa", n_nazwa).execute()
            
            if exists_resp.data:
                st.error(f"BŁĄD: Produkt o nazwie '{n_nazwa}' już istnieje w bazie!")
            elif not n_nazwa:
                st.error("Podaj nazwę produktu.")
            else:
                final_cat_id = None
                
                # Obsługa kategorii
                if new_cat_txt:
                    # Dodaj nową kategorię
                    cat_ins = supabase.table("Kategorie").insert({"nazwa": new_cat_txt}).execute()
                    # Supabase zwraca wstawiony wiersz, bierzemy ID
                    final_cat_id = cat_ins.data[0]['id']
                elif selected_cat_name != "-- Wybierz --":
                    # Znajdź ID wybranej kategorii
                    final_cat_id = cats_df[cats_df['nazwa'] == selected_cat_name]['id'].values[0]
                
                if final_cat_id:
                    # Dodaj produkt
                    new_prod_data = {
                        "nazwa": n_nazwa,
                        "ilosc": n_ilosc,
                        "cena": n_cena,
                        "kategoria_id": int(final_cat_id),
                        "min_stan": n_min,
                        "kod_sku": n_sku
                    }
                    supabase.table("Produkty").insert(new_prod_data).execute()
                    
                    log_action(n_nazwa, "UTWORZENIE", n_ilosc, "Inicjalizacja")
                    st.success(f"Dodano nowy produkt: {n_nazwa}")
                    st.rerun()
                else:
                    st.error("Musisz wybrać kategorię z listy lub wpisać nową.")
