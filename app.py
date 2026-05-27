# ==============================
# 1. IMPORTS
# ==============================
import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import googlemaps
import time

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

from main import (
    get_distance_matrix,
    optimize_routes,
    convert_time_to_minutes,
    generate_google_maps_link
)

# ==============================
# 2. CONFIGURACIÓN
# ==============================
st.set_page_config(
    page_title="Optimización de Rutas",
    page_icon="🚚",
    layout="wide"
)

import os
gmaps = googlemaps.Client(key=os.getenv("GOOGLE_MAPS_API_KEY"))

# ==============================
# 3. SESSION STATE
# ==============================
if "logged" not in st.session_state:
    st.session_state.logged = False

if "optimizado" not in st.session_state:
    st.session_state.optimizado = False

# ==============================
# 4. LOGIN
# ==============================
USERS = {
    "admin": "1234",
    "tierraslatinas": "ruta2026"
}

def login():
    st.title("🔐 Login")

    user = st.text_input("Usuario")
    password = st.text_input("Contraseña", type="password")

    if st.button("Ingresar"):
        if user in USERS and USERS[user] == password:
            st.session_state.logged = True
            st.rerun()
        else:
            st.error("Credenciales incorrectas")

if not st.session_state.logged:
    login()
    st.stop()

# ==============================
# 5. ESTILOS
# ==============================
st.markdown("""
<style>
.main {
    background-color: #f8fafc;
}
h1, h2, h3 {
    color: #1f2937;
}
.stButton button {
    background-color: #2563eb;
    color: white;
    border-radius: 8px;
}
</style>
""", unsafe_allow_html=True)

# ==============================
# 6. FUNCIONES
# ==============================
def draw_map(locations):
    geocoded = [gmaps.geocode(loc)[0]['geometry']['location'] for loc in locations]

    m = folium.Map(location=[geocoded[0]['lat'], geocoded[0]['lng']], zoom_start=11)

    for i, loc in enumerate(geocoded):
        folium.Marker([loc['lat'], loc['lng']], popup=f"Punto {i+1}").add_to(m)

    folium.PolyLine([(loc['lat'], loc['lng']) for loc in geocoded], color="blue").add_to(m)

    return m


def calculate_metrics(distance_matrix, route):
    total_distance = 0
    total_time = 0

    for i in range(len(route) - 1):
        distance = distance_matrix[route[i]][route[i+1]]
        total_distance += distance
        total_time += distance / 1000 / 40 * 60

    return round(total_distance / 1000, 2), int(total_time)


def generate_pdf(routes, locations):
    doc = SimpleDocTemplate("rutas.pdf")
    styles = getSampleStyleSheet()
    content = []

    content.append(Paragraph("Rutas de Entrega", styles["Title"]))
    content.append(Spacer(1, 12))

    for v, route in enumerate(routes):
        content.append(Paragraph(f"Vehículo {v+1}", styles["Heading2"]))

        for i in route:
            content.append(Paragraph(locations[i], styles["Normal"]))

        content.append(Spacer(1, 12))

    doc.build(content)
    return "rutas.pdf"


# ==============================
# 7. SIDEBAR
# ==============================
with st.sidebar:
    st.header("⚙️ Configuración")
    uploaded_file = st.file_uploader("📂 Cargar clientes (Excel)")
    num_vehicles = st.slider("🚚 Número de vehículos", 1, 5, 2)
    optimizar = st.button("🚀 Optimizar rutas")

# ==============================
# 8. UI
# ==============================
st.title("🚚 Optimización de Rutas")

# ==============================
# 9. LÓGICA
# ==============================
FILE_PATH = "clientes.xlsx"

if os.path.exists(FILE_PATH):
    df = pd.read_excel(FILE_PATH)
else:
    df = pd.DataFrame()

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    df.to_excel(FILE_PATH, index=False)
    st.success("Clientes actualizados")
    #st.write("📊 DATA REAL:")
    #st.dataframe(df)

    #st.write("📊 COLUMNA DIA:")
    #st.write(df["dia"])
    df.columns = df.columns.str.strip().str.lower()
    df = df.rename(columns={
    "día": "dia",
    "días": "dia",
    "day": "dia"
})
    df = df.loc[:, ~df.columns.duplicated()]

    df["hora inicio"] = pd.to_datetime(df["hora inicio"], format="%H:%M:%S", errors="coerce")
    df["hora fin"] = pd.to_datetime(df["hora fin"], format="%H:%M:%S", errors="coerce")
    
    st.write("ANTES DROP:", len(df))
    #df = df.dropna(subset=["hora inicio", "hora fin"])
    st.write("DESPUES DROP:", len(df))
    # VALIDAR COLUMNA DIA
# -------------------------------
    if "dia" not in df.columns:
        st.error("❌ El archivo no tiene columna 'dia'")
        st.stop()

# -------------------------------
# LIMPIAR TEXTO
# -------------------------------
    df["dia"] = (
       df["dia"]
       .astype(str)
        .str.strip()
        .str.lower()
)
    
    
    # quitar tildes
    import unicodedata

    def limpiar_texto(texto):
        texto = str(texto)
        texto = texto.strip().lower()
        texto = ''.join(
            c for c in unicodedata.normalize('NFD', texto)
            if unicodedata.category(c) != 'Mn'
    )
        return texto

    df["dia"] = df["dia"].apply(limpiar_texto)


    df = df.dropna(subset=["dia"])

# -------------------------------
# OBTENER DÍAS
# -------------------------------
    dias = df["dia"].dropna().unique()

    st.write("📊 DÍAS DETECTADOS:", dias)

    if len(dias) == 0:
        st.warning("⚠️ No hay días válidos en el archivo")
        st.stop()

# -------------------------------
# SELECT
# -------------------------------
    df["dia"] = df["dia"].astype(str).str.strip().str.lower()

    dias = df["dia"].unique()
    
    dia_seleccionado = st.selectbox("Selecciona el día", dias)

    df_dia = df[df["dia"] == dia_seleccionado]

    locations = df_dia["direccion"].tolist()
    MAX_CLIENTES = 10
    locations = locations[:MAX_CLIENTES]
    time_windows = []
    for i in range(len(df_dia)):
        start = convert_time_to_minutes(df_dia.iloc[i]["hora inicio"])
        end = convert_time_to_minutes(df_dia.iloc[i]["hora fin"])
        time_windows.append((start, end))
    if len(df_dia) > MAX_CLIENTES:
        st.warning(f"⚠️ Solo se procesarán {MAX_CLIENTES} clientes")
    warehouse = "51 Nelson Rd, Yennora NSW 2161, Australia"
    locations = [warehouse] + locations
    time_windows = [(0, 1440)] + time_windows
    
    
    if optimizar:
        st.success("✅ Rutas optimizadas correctamente")
        st.session_state.optimizado = True

    if st.session_state.optimizado:
        st.write("TOTAL LOCATIONS:", len(locations))
        st.write(locations)
    valid_locations = []

    for loc in locations:
        try:
            result = gmaps.geocode(loc)

            if result:
                valid_locations.append(loc)
            else:
                st.warning(f"⚠️ Dirección inválida: {loc}")

        except Exception as e:
            st.warning(f"⚠️ Error con dirección: {loc}")

        locations = valid_locations
        distance_matrix = get_distance_matrix(locations)
        routes = optimize_routes(distance_matrix, time_windows, num_vehicles)

        st.session_state.routes = routes
        st.session_state.locations = locations
        st.session_state.distance_matrix = distance_matrix

# ==============================
# 10. RESUMEN
# ==============================
st.markdown("## 📊 Resumen")

if "routes" in st.session_state:
    total_km = 0

    for route in st.session_state.routes:
        km, _ = calculate_metrics(st.session_state.distance_matrix, route)
        total_km += km

    c1, c2, c3 = st.columns(3)
    c1.metric("🚚 Vehículos", num_vehicles)
    c2.metric("📍 Clientes", len(st.session_state.locations) - 1)
    c3.metric("📏 Km totales", round(total_km, 2))
else:
    st.info("📌 Primero optimiza las rutas")

# ==============================
# 11. FORM CLIENTES
# ==============================
st.markdown("## ➕ Agregar cliente")

with st.form("nuevo_cliente"):
    nombre = st.text_input("Nombre")
    direccion = st.text_input("Dirección")
    dia = st.selectbox("Día", ["lunes","martes","miercoles","jueves","viernes"])
    hora_inicio = st.time_input("Hora inicio")
    hora_fin = st.time_input("Hora fin")

    guardar = st.form_submit_button("Guardar")

    if guardar:
        nuevo = pd.DataFrame([{
            "cliente": nombre,
            "direccion": direccion,
            "dia": dia,
            "hora inicio": hora_inicio,
            "hora fin": hora_fin
        }])

        try:
            df_existente = pd.read_excel("clientes.xlsx")
            df_total = pd.concat([df_existente, nuevo])
        except:
            df_total = nuevo

        for _ in range(3):
            try:
                df_total.to_excel("clientes.xlsx", index=False)
                break
            except PermissionError:
                time.sleep(1)

        st.success("Cliente guardado ✅")

# ==============================
# 12. RESULTADOS
# ==============================
if "routes" in st.session_state:

    st.markdown("""
# 🚚 Optimización de Rutas Logísticas
Optimiza entregas, reduce tiempos y mejora la eficiencia operativa.
""")

    for v, route in enumerate(st.session_state.routes):

        st.markdown(f"### 🚚 Vehículo {v+1}")

        ordered = [st.session_state.locations[i] for i in route]

        km, tiempo = calculate_metrics(st.session_state.distance_matrix, route)

        col1, col2 = st.columns(2)
        col1.metric("📏 km", km)
        col2.metric("⏱ min", tiempo)

        for i, loc in enumerate(ordered):
            st.write(f"{i+1}. {loc}")

        mapa = draw_map(ordered)
        st_folium(mapa, width=900, key=f"mapa_{v}")

        link = generate_google_maps_link(list(range(len(ordered))), ordered)
        st.link_button("🌍 Abrir en Google Maps", link)

    # PDF
    pdf_file = generate_pdf(st.session_state.routes, st.session_state.locations)

    with open(pdf_file, "rb") as f:
        st.download_button(
            "📄 Descargar rutas",
            f,
            file_name="rutas.pdf"
        )

st.caption("Desarrollado por Jeison Villamil 🚀")
