import streamlit as st
import pandas as pd
import plotly.express as px
from PIL import Image
import os
import gc
import base64
import math
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import streamlit.components.v1 as components
import fitz  # PyMuPDF
import re
import io
import pytesseract
from supabase import create_client, Client

# Configuración de página
st.set_page_config(page_title="Control ESD BCS-AIS", layout="wide")

# --- CONEXIÓN A SUPABASE ---
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase: Client = init_connection()

# --- NUEVA LECTURA DE DATOS UNIFICADA (Mapeada a tus viejos nombres para no romper la UI) ---
@st.cache_data(ttl=10) 
def cargar_datos_cloud():
    try:
        # 1. Traer inventario
        resp_inv = supabase.table("inventario_esd").select("*").execute()
        df_inv = pd.DataFrame(resp_inv.data)
        
        if not df_inv.empty:
            rename_map = {
                "id_producto": "Id de producto",
                "linea_ubicacion": "Línea",
                "clasificacion": "Clasificación",
                "fabricante": "Fabricante",
                "limite_minimo": "Mínimo",
                "limite_maximo": "Maximo",
                "unidad_medida": "Unidad",
                "valor_actual": "Valor de verificación",
                "balance_ionizador": "Balance",
                "metodo_prueba": "Método",
                "fecha_ultima_verif": "Fecha de verificación",
                "fecha_proxima_verif": "Fecha de próxima verificación",
                "frecuencia": "Frecuencia de verificación",
                "estatus_verificacion": "Estatus de verificación",
                "estatus_operativo": "Estatus operativo",
                "comentarios": "Notas",
                "auditor_responsable": "Auditor"
            }
            df_inv = df_inv.rename(columns=rename_map)
            df_mob = df_inv[df_inv['categoria'] == 'Mobiliario']
            df_ion = df_inv[df_inv['categoria'] == 'Ionizador']
            df_piso = df_inv[df_inv['categoria'] == 'Piso']
        else:
            df_mob, df_ion, df_piso = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

        # 2. Traer Event Meter
        resp_em = supabase.table("event_meter").select("*").execute()
        df_em = pd.DataFrame(resp_em.data) if resp_em.data else pd.DataFrame()
        if not df_em.empty:
            em_rename_map = {
                "linea_ubicacion": "Línea",
                "id_operacion": "Id de Operación",
                "tipo_contacto": "Tipo de contacto",
                "cantidad_eventos": "Detección (Cantidad)",
                "voltaje_maximo": "Voltaje máximo",
                "estatus_verificacion": "Estatus de verificación",
                "notas": "Notas",
                "auditor": "Auditor"
            }
            df_em = df_em.rename(columns=em_rename_map)
        else:
            df_em = pd.DataFrame(columns=['Línea', 'Id de Operación'])

        return df_piso, df_mob, df_ion, df_em
        
    except Exception as e:
        st.error(f"Error conectando a la base de datos: {e}")
        return None, None, None, None


# ==========================================
# FUNCIONES AUXILIARES
# ==========================================
def codificar_sesion(nombre):
    return base64.b64encode(nombre.encode('utf-8')).decode('utf-8')

def decodificar_sesion(token):
    try:
        return base64.b64decode(token.encode('utf-8')).decode('utf-8')
    except:
        return None

def limpiar_url_escaneo():
    if "qr_id" in st.query_params:
        del st.query_params["qr_id"]
    if "ocr_val" in st.query_params:
        del st.query_params["ocr_val"]
    if "qr_baja" in st.query_params:
        del st.query_params["qr_baja"]

def procesar_imagen_b64(img_file):
    if img_file is not None:
        try:
            img = Image.open(img_file)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            max_size = (500, 500)
            img.thumbnail(max_size)
            quality = 60
            buffered = io.BytesIO()
            img.save(buffered, format="JPEG", quality=quality)
            b64_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
            while len(b64_str) > 48000 and quality > 10:
                quality -= 10
                if quality <= 30:
                    max_size = (int(max_size[0] * 0.8), int(max_size[1] * 0.8))
                    img = img.resize(max_size, Image.Resampling.LANCZOS)
                buffered = io.BytesIO()
                img.save(buffered, format="JPEG", quality=quality)
                b64_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
            if len(b64_str) > 49500:
                return "ERROR_IMAGEN_MUY_PESADA"
            return b64_str
        except Exception as e:
            return ""
    return ""

def safe_str(val, default="N/D"):
    if pd.isna(val) or str(val).strip().lower() == 'nan' or str(val).strip() == '':
        return default
    return str(val).strip()

def generar_html_reporte_esd(row, index):
    med1 = safe_str(row.get('Medición 1', ''), '')
    med_extra = safe_str(row.get('Mediciones Extra', ''), '')
    mediciones = [med1] if med1 else []
    if med_extra and med_extra != 'N/D':
        mediciones.extend([m.strip() for m in med_extra.split(',') if m.strip()])
    
    valid_nums = []
    for m in mediciones:
        try:
            valid_nums.append(float(m))
        except: pass
            
    promedio = sum(valid_nums) / len(valid_nums) if valid_nums else 0
    promedio_str = f"{promedio:.2E}" if promedio > 0 else "N/A"
    
    ref_raw = safe_str(row.get('Referencia'))
    try:
        ref_num = float(ref_raw)
        ref_str = f"{ref_num:.2E}"
    except:
        ref_str = ref_raw
    
    html_rows = ""
    for i, val in enumerate(mediciones, 1):
        try:
            val_num = float(val)
            val_str = f"{val_num:.2E}" if val_num > 1000 or val_num < 0.01 else str(val)
        except:
            val_str = val
            
        html_rows += f"""
        <tr class="border-b border-gray-200 hover:bg-blue-50 print:hover:bg-transparent text-center">
            <td class="p-1 border-r border-gray-300 font-bold">{i}</td>
            <td class="p-1 border-r border-gray-300 font-mono">{ref_str}</td>
            <td class="p-1 border-r border-gray-300 bg-yellow-50 print:bg-transparent font-mono font-bold">{val_str}</td>
            <td class="p-1 border-r border-gray-300">{safe_str(row.get('Método'))}</td>
            <td class="p-1 border-r border-gray-300">{safe_str(row.get('Unidad'))}</td>
            <td class="p-1 border-r border-gray-300">{safe_str(row.get('Ubicación'))}</td>
        </tr>
        """
        
    img_b64 = safe_str(row.get('Imagen (Base64)'), '')
    if img_b64 == 'N/D' or not img_b64:
        img_tag = "<span class='text-gray-400 flex flex-col items-center'><br><br>Sin evidencia fotográfica</span>"
    else:
        img_tag = f'<img src="data:image/png;base64,{img_b64}" style="height: 190px; width: auto; max-width: 100%; object-fit: contain; margin: 0 auto;" />'
        
    fecha_ejecucion = safe_str(row.get('Fecha')).split(' ')[0]
    año_actual = datetime.today().strftime("%y")
    
    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Reporte de Validación S20.20</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>@media print {{ body {{ -webkit-print-color-adjust: exact; }} }}</style>
</head>
<body class="bg-gray-100 p-4 md:p-8 font-sans text-sm print:bg-white print:p-0">
    <div class="max-w-5xl mx-auto mb-6 bg-white p-4 rounded-lg shadow flex justify-end print:hidden">
        <button onclick="window.print()" class="bg-blue-600 text-white px-6 py-2 rounded font-bold shadow-sm">🖨️ Imprimir / Guardar PDF</button>
    </div>
    <div class="max-w-5xl mx-auto bg-white shadow-xl print:shadow-none print:w-full">
        <div class="border-b-2 border-gray-800 p-6 flex items-start justify-between">
            <div class="w-1/3">
                <img src="https://github.com/aldoaoa/Visualizador-BCS-IDS/blob/main/BCS%20LOGO.png?raw=true" alt="BCS Logo" class="h-16 object-contain" />
            </div>
            <div class="w-1/3 text-center">
                <h1 class="text-lg font-bold text-gray-800">FORMATO DE VALIDACIÓN DE PRODUCTO (ESD)</h1>
                <p class="text-xs text-gray-600">ANSI/ESD S20.20-2021</p>
            </div>
            <div class="w-1/3 text-right text-sm">
                <div class="font-bold text-red-700 text-lg mb-2">Reporte: BCS-PV-{index:03d}-{año_actual}</div>
                <div class="flex justify-end gap-2 mb-1">
                    <span class="font-bold">Fecha de Ejecución:</span><span>{fecha_ejecucion}</span>
                </div>
            </div>
        </div>
        <div class="p-6 space-y-6">
            <div class="grid grid-cols-2 gap-6">
                <div>
                    <div class="bg-gray-800 text-white font-bold px-2 py-1 uppercase text-xs">Datos del Elemento de Control</div>
                    <table class="w-full text-sm border-collapse border border-gray-300">
                        <tr class="border-b border-gray-300"><td class="w-1/3 font-bold bg-gray-100 p-1 border-r border-gray-300">ID:</td><td class="p-1">{safe_str(row.get('ID Elemento'))}</td></tr>
                        <tr class="border-b border-gray-300"><td class="w-1/3 font-bold bg-gray-100 p-1 border-r border-gray-300">Elemento:</td><td class="p-1">{safe_str(row.get('Elemento S20.20'))}</td></tr>
                    </table>
                </div>
            </div>
            <div>
                <div class="bg-gray-800 text-white font-bold px-2 py-1 uppercase text-xs">Resultados (ANSI/ESD S20.20)</div>
                <table class="w-full text-sm border-collapse border border-gray-300 text-center">
                    <tr class="bg-gray-100 border-b border-gray-300">
                        <th class="p-2 border-r border-gray-300">No.</th>
                        <th class="p-2 border-r border-gray-300">Referencia</th>
                        <th class="p-2 border-r border-gray-300">Resultado Obtenido</th>
                        <th class="p-2 border-r border-gray-300">Método de Prueba</th>
                        <th class="p-2 border-r border-gray-300">Unidad</th>
                        <th class="p-2 border-r border-gray-300">Punto de Colocación</th>
                    </tr>
                    {html_rows}
                    <tr class="border-t-2 border-gray-400 bg-gray-50">
                        <td colspan="2" class="p-2 font-bold text-right border-r border-gray-300">Promedio / Final:</td>
                        <td class="p-2 font-mono font-bold text-center border-r border-gray-300">{promedio_str}</td>
                        <td colspan="3"></td>
                    </tr>
                </table>
            </div>
            <div class="grid grid-cols-2 gap-6 h-64">
                <div class="border border-gray-300 flex flex-col items-center justify-center bg-gray-50 overflow-hidden relative">
                    <div class="absolute top-0 left-0 bg-gray-800 text-white font-bold px-2 py-1 uppercase text-xs w-full text-left z-10">Evidencia</div>
                    <div class="mt-8 flex-1 flex items-center justify-center p-2">{img_tag}</div>
                </div>
                <div class="border border-gray-300 flex flex-col relative">
                    <div class="bg-gray-800 text-white font-bold px-2 py-1 uppercase text-xs w-full">Comentarios / Observaciones</div>
                    <div class="p-2 text-sm">{safe_str(row.get('Notas'), 'Sin observaciones adicionales.')}</div>
                    <div class="absolute bottom-2 right-2 text-lg font-bold text-gray-700">{safe_str(row.get('Resultado'))}</div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>"""
    return html

# ==========================================
# SEGURIDAD Y ACCESO
# ==========================================
if "usuario_nombre" not in st.session_state:
    st.session_state.usuario_nombre = None
if "modo_lectura" not in st.session_state:
    st.session_state.modo_lectura = False

token_actual = st.query_params.get("auth_token")

if token_actual:
    if token_actual == "consulta_mode":
        st.session_state.usuario_nombre = "Usuario de Consulta"
        st.session_state.modo_lectura = True
    else:
        usuario_decodificado = decodificar_sesion(token_actual)
        if usuario_decodificado:
            st.session_state.usuario_nombre = usuario_decodificado
            st.session_state.modo_lectura = False 

if st.session_state.usuario_nombre is None and not st.session_state.modo_lectura:
    col_img1, col_img2, col_img3 = st.columns([1, 1, 1])
    with col_img2:
        st.image("https://raw.githubusercontent.com/aldoaoa/Visualizador-BCS-IDS/refs/heads/main/Logo_BCS_transparent%20(1).png", use_container_width=True)
    st.markdown("<h2 style='text-align: center;'>🛡️ Sistema de Gestión ESD BCS-AIS</h2>", unsafe_allow_html=True)
    col_v1, col_c, col_v2 = st.columns([1, 1.2, 1])
    with col_c:
        tab_login, tab_monitor = st.tabs(["🔒 Ingreso de Auditor", "👁️ Modo Consulta"])
        with tab_login:
            with st.form("login_form"):
                user_input = st.text_input("Usuario (ID)")
                pwd_input = st.text_input("Contraseña", type="password")
                if st.form_submit_button("Ingresar y Editar", use_container_width=True):
                    try:
                        usuarios_db = st.secrets["usuarios"]
                        if user_input in usuarios_db and usuarios_db[user_input]["password"] == pwd_input:
                            nombre_real = usuarios_db[user_input]["nombre"]
                            st.query_params["auth_token"] = codificar_sesion(nombre_real)
                            st.rerun()
                        else:
                            st.error("❌ Credenciales incorrectas")
                    except KeyError:
                        st.error("⚠️ Error en configuración de usuarios.")
        with tab_monitor:
            st.info("El Modo Consulta es de solo lectura.")
            if st.button("👁️ Entrar en Modo Consulta", use_container_width=True):
                st.query_params["auth_token"] = "consulta_mode"
                st.rerun()
else:
    # ==========================================
    # APLICACIÓN PRINCIPAL
    # ==========================================
    RUTA_MAPA = "mapa.jpg" 
    RUTA_COORDENADAS = "coordenadas.csv"

    with st.sidebar:
        st.image("https://raw.githubusercontent.com/aldoaoa/Visualizador-BCS-IDS/refs/heads/main/Logo_BCS_transparent%20(1).png", use_container_width=True)
        st.divider()
        if st.session_state.modo_lectura:
            st.warning("👁️ Modo Consulta Activo")
        else:
            st.success(f"👤 Auditor: {st.session_state.usuario_nombre}")
        if st.button("Salir al Menú Principal", use_container_width=True):
            st.session_state.usuario_nombre = None
            st.session_state.modo_lectura = False
            st.query_params.clear() 
            st.rerun()

    def calcular_proxima_fecha(fecha_actual, frecuencia):
        frecuencia = str(frecuencia).strip().lower()
        if 'anual' in frecuencia: return fecha_actual + relativedelta(years=1)
        elif 'semestral' in frecuencia: return fecha_actual + relativedelta(months=6)
        elif 'trimestral' in frecuencia: return fecha_actual + relativedelta(months=3)
        elif 'mensual' in frecuencia: return fecha_actual + relativedelta(months=1)
        else: return fecha_actual + relativedelta(years=1)

    st.title("Sistema de Gestión ESD BCS-AIS Querétaro")
    
    df_piso_local, df_mob_local, df_ion_local, df_em_local = cargar_datos_cloud()
    
    if df_mob_local is None:
        st.error("Falla al conectar con el servidor SQL.")
        st.stop()

    if "vista_actual" not in st.session_state:
        st.session_state.vista_actual = "Escáner" 

    id_escaneado_url = st.query_params.get("qr_id", "")
    valor_ocr_detectado = st.query_params.get("ocr_val", "")
    id_baja_url = st.query_params.get("qr_baja", "")
    
    if id_escaneado_url or valor_ocr_detectado:
        st.session_state.vista_actual = "Escáner"
    elif id_baja_url:
        st.session_state.vista_actual = "Alta"

    if not st.session_state.modo_lectura:
        c_nav1, c_nav2, c_nav3, c_nav4, c_nav5, c_nav6 = st.columns(6)
        with c_nav1:
            if st.button("🗺️ Mapa y Reportes", use_container_width=True, type="primary" if st.session_state.vista_actual == "Mapa" else "secondary"):
                st.session_state.vista_actual = "Mapa"
                limpiar_url_escaneo() 
                st.rerun()
        with c_nav2:
            if st.button("📱 Escáner", use_container_width=True, type="primary" if st.session_state.vista_actual == "Escáner" else "secondary"):
                st.session_state.vista_actual = "Escáner"
                limpiar_url_escaneo()
                st.rerun()
        with c_nav3:
            if st.button("🆕 Alta/Baja", use_container_width=True, type="primary" if st.session_state.vista_actual == "Alta" else "secondary"):
                st.session_state.vista_actual = "Alta"
                limpiar_url_escaneo()
                st.rerun()
        with c_nav4:
            if st.button("⚡ Event Meter", use_container_width=True, type="primary" if st.session_state.vista_actual == "Event Meter" else "secondary"):
                st.session_state.vista_actual = "Event Meter"
                limpiar_url_escaneo()
                st.rerun()
        with c_nav5:
            if st.button("🚶‍♂️ Walking Test", use_container_width=True, type="primary" if st.session_state.vista_actual == "Walking Test" else "secondary"):
                st.session_state.vista_actual = "Walking Test"
                limpiar_url_escaneo()
                st.rerun()
        with c_nav6:
            if st.button("✅ Validación", use_container_width=True, type="primary" if st.session_state.vista_actual == "Validación" else "secondary"):
                st.session_state.vista_actual = "Validación"
                limpiar_url_escaneo()
                st.rerun()
    else:
        st.session_state.vista_actual = "Escáner"

    st.divider()

    # ==========================================
    # VISTA: ALTA Y BAJA DE EQUIPOS
    # ==========================================
    if st.session_state.vista_actual == "Alta" and not st.session_state.modo_lectura:
        st.markdown("### Gestión de Inventario ESD")
        
        with st.expander("📋 Directorio de IDs Existentes (Click para abrir/cerrar)", expanded=False):
            tipo_dir = st.radio("Ver directorio de:", ["Mobiliario", "Ionizadores"], horizontal=True)
            df_dir = df_mob_local if tipo_dir == "Mobiliario" else df_ion_local
            
            st.info("💡 **Tip:** Haz clic en el título de una columna para ordenar (A-Z) o usa la lupa (🔍) para buscar un ID específico.")
            if not df_dir.empty and 'Id de producto' in df_dir.columns and 'Línea' in df_dir.columns:
                if 'Estatus operativo' in df_dir.columns:
                    df_clean = df_dir[df_dir['Estatus operativo'].astype(str).str.strip().str.upper() != 'NO OPERATIVO']
                else:
                    df_clean = df_dir.copy()
                    
                df_clean = df_clean[['Línea', 'Id de producto', 'Clasificación']].dropna(subset=['Id de producto'])
                st.dataframe(df_clean, use_container_width=True, hide_index=True)
            else:
                st.warning("No hay datos disponibles aún en esta categoría.")
        
        st.divider()
        
        if "radio_alta_baja" not in st.session_state:
            st.session_state.radio_alta_baja = "🆕 Registrar Nuevo"
            
        if id_baja_url:
            st.session_state.radio_alta_baja = "🗑️ Dar de Baja"

        accion_seleccionada = st.radio(
            "Selecciona la acción a realizar:",
            ["🆕 Registrar Nuevo", "🗑️ Dar de Baja"],
            horizontal=True, label_visibility="collapsed", key="radio_alta_baja"
        )
        
        # --- SUB-VISTA 1: ALTA ---
        if accion_seleccionada == "🆕 Registrar Nuevo":
            tipo_alta = st.radio("Categoría del Equipo a Registrar:", ["Mobiliario", "Ionizador"], horizontal=True)
            df_target_alta = df_mob_local if tipo_alta == "Mobiliario" else df_ion_local
            
            todas_lineas = set()
            for df_temp in [df_piso_local, df_mob_local, df_ion_local]:
                if not df_temp.empty and 'Línea' in df_temp.columns:
                    todas_lineas.update([str(x).strip() for x in df_temp['Línea'].dropna() if str(x).strip() != ''])
            lineas_disponibles = sorted(list(todas_lineas))

            with st.form("form_alta_equipo"):
                col1, col2 = st.columns(2)
                nueva_linea = col1.selectbox("Línea (Ubicación)", options=lineas_disponibles if lineas_disponibles else ["SMT", "Ensamble"])
                nuevo_id = col2.text_input("ID de Producto (Ej: " + ("MOB-001" if tipo_alta=="Mobiliario" else "ION-001") + ")")
                
                if tipo_alta == "Mobiliario":
                    tipos_disponibles = sorted([str(x).strip() for x in df_target_alta.get('Clasificación', pd.Series()).unique() if pd.notna(x) and str(x).strip() != ''])
                    nuevo_tipo = col1.selectbox("Tipo / Clasificación", options=tipos_disponibles if tipos_disponibles else ["Mesa", "Silla"])
                    
                    with col2:
                        st.caption("Valor inicial (Ohms)")
                        c_b, c_x, c_e = st.columns([2, 1, 2])
                        base_alta = c_b.number_input("Número", value=0.0, format="%.2f")
                        exp_alta = c_e.number_input("Exponente", value=0, step=1, format="%d")
                        valor_alta = base_alta * (10 ** exp_alta) if base_alta != 0 else 0.0
                    
                    fabricante_opc = col1.selectbox("Fabricante", options=["BCS", "Otro", "N/A"])
                    fabricante_final = col1.text_input("Especifique Fabricante") if fabricante_opc == "Otro" else fabricante_opc
                    
                    frecuencia_alta = col2.selectbox("Frecuencia", options=["Anual", "Semestral", "Trimestral", "Mensual"], index=0)
                    col3, col4 = st.columns(2)
                    nuevo_minimo = col3.number_input("Mínimo", value=0.00, format="%.2e")
                    limite_alta = col4.text_input("Límite Maximo", value="1.00E+09")
                    balance_alta = 0.0
                    
                else:
                    nuevo_tipo = col1.selectbox("Clasificación", options=["Ventilador", "Barra", "Pistola"])
                    valor_alta = col2.number_input("Descarga (Seg)", value=0.0, format="%.2f")
                    
                    fabricante_opc = col1.selectbox("Fabricante", options=["SMC", "Panasonic", "Keyence", "SIMCO", "Otro"])
                    fabricante_final = col1.text_input("Especifique Fabricante") if fabricante_opc == "Otro" else fabricante_opc
                    
                    balance_alta = col2.number_input("Balance (V)", value=0.0, format="%.2f")
                    frecuencia_alta = "Trimestral"
                    nuevo_minimo = 0.00
                    limite_alta = "10.00"

                comentarios = st.text_area("Comentarios")
                submit_alta = st.form_submit_button("Registrar en sistema", use_container_width=True)
                
            if submit_alta:
                if not nuevo_id or not fabricante_final:
                    st.error("Por favor complete los campos obligatorios (ID y Fabricante).")
                else:
                    id_limpio_alta = str(nuevo_id).strip().upper()
                    check_exist = supabase.table("inventario_esd").select("id_producto").eq("id_producto", id_limpio_alta).execute()
                    
                    if len(check_exist.data) > 0:
                        st.error(f"El ID {nuevo_id} ya existe en SQL.")
                    else:
                        with st.spinner("Guardando en SQL..."):
                            fecha_hoy = datetime.today().date()
                            dias_map = {"Anual": 360, "Semestral": 180, "Trimestral": 90, "Mensual": 30}
                            proxima = fecha_hoy + timedelta(days=dias_map.get(frecuencia_alta, 360))
                            
                            data_insert = {
                                "id_producto": id_limpio_alta,
                                "categoria": tipo_alta,
                                "linea_ubicacion": nueva_linea,
                                "clasificacion": nuevo_tipo,
                                "fabricante": fabricante_final,
                                "limite_minimo": float(nuevo_minimo),
                                "limite_maximo": float(limite_alta) if "E" not in str(limite_alta).upper() else float(limite_alta), 
                                "unidad_medida": "Segundos" if tipo_alta == "Ionizador" else "Ohms",
                                "valor_actual": float(valor_alta) if valor_alta > 0 else None,
                                "metodo_prueba": "CPM" if tipo_alta == "Ionizador" else "RTG",
                                "fecha_ultima_verif": fecha_hoy.isoformat() if valor_alta > 0 else None,
                                "fecha_proxima_verif": proxima.isoformat() if valor_alta > 0 else None,
                                "frecuencia": frecuencia_alta,
                                "estatus_verificacion": "VIGENTE" if valor_alta > 0 and fecha_hoy < proxima else "PENDIENTE",
                                "estatus_operativo": "OPERATIVO",
                                "comentarios": comentarios,
                                "auditor_responsable": st.session_state.usuario_nombre
                            }
                            if tipo_alta == "Ionizador":
                                data_insert["balance_ionizador"] = float(balance_alta)
                            
                            try:
                                supabase.table("inventario_esd").insert(data_insert).execute()
                                st.success(f"✅ ¡Activo {nuevo_id} registrado!")
                                st.cache_data.clear()
                                st.balloons()
                            except Exception as e:
                                st.error(f"Error SQL: {e}")
                                
        # --- SUB-VISTA 2: BAJA ---
        elif accion_seleccionada == "🗑️ Dar de Baja":
            st.markdown("#### 🗑️ Dar de Baja")
            if not id_baja_url:
                st.write("Escanea o ingresa manualmente el ID.")
                id_manual_baja = st.text_input("Ingresa el ID manual:", key="input_manual_baja")
                if id_manual_baja:
                    st.query_params["qr_baja"] = id_manual_baja
                    st.rerun()
            else:
                colA, colB = st.columns([0.8, 0.2])
                with colA: st.error(f"🗑️ **ID a Procesar:** {id_baja_url}")
                with colB:
                    if st.button("❌ Cancelar"):
                        limpiar_url_escaneo()
                        st.rerun()

                id_limpio_baja = str(id_baja_url).strip().upper()
                
                with st.form("form_confirmacion_baja"):
                    if st.form_submit_button("🗑️ Confirmar Baja (Soft Delete)"):
                        with st.spinner("Actualizando SQL..."):
                            try:
                                supabase.table("inventario_esd").update({
                                    "estatus_operativo": "NO OPERATIVO",
                                    "estatus_verificacion": "BAJA"
                                }).eq("id_producto", id_limpio_baja).execute()
                                
                                st.success(f"✅ ¡Equipo desactivado!")
                                st.cache_data.clear()
                                limpiar_url_escaneo()
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")

    # ==========================================
    # VISTA 1: MAPA Y REPORTES ESD
    # ==========================================
    elif st.session_state.vista_actual == "Mapa" and not st.session_state.modo_lectura:
        st.markdown("### Mapa y Cumplimiento ESD")
        tab_mapa, tab_overview = st.tabs(["📍 Mapa Físico", "📊 Overview (S20.20)"])

        with tab_mapa:
            tipo_mapa = st.radio("Ver en mapa:", ["Mobiliario", "Ionizadores"], horizontal=True)
            df_total = df_mob_local.copy() if tipo_mapa == "Mobiliario" else df_ion_local.copy()
            
            if df_total.empty:
                st.warning(f"No hay datos registrados en {tipo_mapa}.")
            else:
                equipos_activos = df_total[df_total['Estatus operativo'].astype(str).str.upper() != 'NO OPERATIVO']
                total_equipos = len(equipos_activos)
                vencidos = equipos_activos[equipos_activos['Estatus de verificación'].astype(str).str.upper() == 'VENCIDO']
                total_vencidos = len(vencidos)
            
                if total_equipos > 0:
                    porcentaje = ((total_equipos - total_vencidos) / total_equipos) * 100
                else:
                    porcentaje = 100.0

                if not vencidos.empty:
                    st.error(f"🚨 **Cumplimiento:** {porcentaje:.1f}% | **Vencidos:** {total_vencidos} de {total_equipos} activos.")
                    conteo_tipos = vencidos.groupby(['Línea']).size().reset_index(name='Total Vencidos')
                    conteo_tipos['Etiqueta'] = ("M: " if tipo_mapa == "Mobiliario" else "I: ") + conteo_tipos['Total Vencidos'].astype(str)
                
                    if os.path.exists(RUTA_MAPA) and os.path.exists(RUTA_COORDENADAS):
                        img = Image.open(RUTA_MAPA)
                        df_coords = pd.read_csv(RUTA_COORDENADAS)
                        mapa_data = pd.merge(conteo_tipos, df_coords, on='Línea', how='inner')
                        if not mapa_data.empty:
                            fig = px.scatter(mapa_data, x="X", y="Y", color="Total Vencidos", text="Etiqueta")
                            fig.update_traces(textposition='middle center', marker=dict(size=45))
                            fig.update_layout(images=[dict(source=img, xref="x", yref="y", x=0, y=0, sizex=img.size[0], sizey=img.size[1], sizing="stretch", opacity=1, layer="below")], xaxis=dict(visible=False), yaxis=dict(visible=False, autorange="reversed"))
                            st.plotly_chart(fig, use_container_width=True)
                    st.dataframe(vencidos[['Línea', 'Id de producto', 'Clasificación', 'Estatus de verificación']], use_container_width=True, hide_index=True)
                else:
                    st.success(f"✅ **100% Cumplimiento en {tipo_mapa}.**")

        with tab_overview:
            st.markdown("#### Estado Global de Elementos ESD")
            try:
                resp_inv2 = supabase.table("inventario_esd").select("id_producto, clasificacion, linea_ubicacion, estatus_verificacion, fecha_proxima_verif").execute()
                df_ov = pd.DataFrame(resp_inv2.data)
                
                if not df_ov.empty:
                    df_ov['Fecha Prox Validación'] = pd.to_datetime(df_ov['fecha_proxima_verif'], errors='coerce')
                    hoy = pd.Timestamp(datetime.today().date())
                    
                    def estado_validacion(fecha_prox):
                        if pd.isna(fecha_prox): return "Sin Validación"
                        dias = (fecha_prox - hoy).days
                        if dias < 0: return "Vencido"
                        elif dias <= 30: return "Por Vencer"
                        else: return "Vigente"
                            
                    df_ov['Estatus'] = df_ov['Fecha Prox Validación'].apply(estado_validacion)
                    total_vig = len(df_ov[df_ov['Estatus'] == 'Vigente'])
                    total_prx = len(df_ov[df_ov['Estatus'] == 'Por Vencer'])
                    total_ven = len(df_ov[df_ov['Estatus'] == 'Vencido'])
                    
                    col_m1, col_m2, col_m3 = st.columns(3)
                    col_m1.metric("🟢 Vigentes", total_vig)
                    col_m2.metric("🟡 Por Vencer (30 días)", total_prx)
                    col_m3.metric("🔴 Vencidos", total_ven)
                    
                    df_ov['Fecha Prox Validación'] = df_ov['Fecha Prox Validación'].dt.strftime('%d-%b-%Y').fillna("N/D")
                    df_ov = df_ov.rename(columns={'id_producto': 'ID Elemento', 'clasificacion': 'Elemento S20.20', 'linea_ubicacion': 'Ubicación'})
                    st.dataframe(df_ov[['Elemento S20.20', 'ID Elemento', 'Ubicación', 'Estatus', 'Fecha Prox Validación']], use_container_width=True, hide_index=True)
                else:
                    st.warning("Inventario vacío.")
            except Exception as e:
                st.error(f"Error al cargar overview: {e}")

    # ==========================================
    # VISTA 2: ESCÁNER Y DETALLES
    # ==========================================
    elif st.session_state.vista_actual == "Escáner":
        if not id_escaneado_url:
            st.markdown("### 📷 Apunta al Código QR")
            id_manual = st.text_input("O ingresa el ID manual:", key="input_manual")
            if id_manual:
                st.query_params["qr_id"] = id_manual
                st.rerun()

        if id_escaneado_url:
            colA, colB = st.columns([0.8, 0.2])
            with colA: st.info(f"🔍 **ID:** {id_escaneado_url}")
            with colB:
                if st.button("❌ Cerrar"):
                    limpiar_url_escaneo()
                    st.rerun()

            id_limpio = str(id_escaneado_url).strip().upper()
            mob_ids_limpios = df_mob_local.get('Id de producto', pd.Series()).astype(str).str.strip().str.upper()
            ion_ids_limpios = df_ion_local.get('Id de producto', pd.Series()).astype(str).str.strip().str.upper()

            es_mob = id_limpio in mob_ids_limpios.values
            es_ion = id_limpio in ion_ids_limpios.values

            if es_mob or es_ion:
                df_actual = df_mob_local if es_mob else df_ion_local
                serie_busqueda = mob_ids_limpios if es_mob else ion_ids_limpios
                idx = serie_busqueda[serie_busqueda == id_limpio].index[0]
                equipo = df_actual.loc[idx]
                
                estatus_op = str(equipo.get('Estatus operativo', '')).strip().upper()
                texto_check = "✅ REACTIVAR" if estatus_op == "NO OPERATIVO" else "✅ Registrar medición"
                
                st.markdown(f"### 📊 Detalles del Equipo")
                c_linea, c_tipo, c_estatus = st.columns(3)
                c_linea.metric("Ubicación", str(equipo.get('Línea', 'N/A')))
                c_tipo.metric("Clasificación", str(equipo.get('Clasificación', 'N/A')))
                c_estatus.metric("Estatus", str(equipo.get('Estatus de verificación', 'N/A')))
                
                c_val, c_bal = st.columns(2)
                val_previo = equipo.get('Valor de verificación', 0)
                if es_ion:
                    c_val.metric("Descarga", f"{float(val_previo):.2f} s" if pd.notna(val_previo) else "N/A")
                    c_bal.metric("Balance", str(equipo.get('Balance', 'N/A')))
                else:
                    c_val.metric("Resistencia", f"{float(val_previo):.2E} Ω" if pd.notna(val_previo) else "N/A")

                st.divider()

                if not st.session_state.modo_lectura:
                    hacer_medicion = st.checkbox(texto_check)
                    if hacer_medicion:
                        with st.form("form_actualizacion"):
                            lineas_opc = sorted([str(x).strip() for x in df_mob_local['Línea'].dropna().unique()])
                            idx_l = lineas_opc.index(equipo.get('Línea')) if equipo.get('Línea') in lineas_opc else 0
                            nueva_linea_upd = st.selectbox("Línea", lineas_opc, index=idx_l)
                            
                            if es_ion:
                                v_act = st.number_input("Descarga (s)", value=0.0, format="%.2f")
                                bal_act = st.number_input("Balance (V)", value=0.0, format="%.2f")
                                nuevo_valor_final = v_act
                            else:
                                c_b, c_e = st.columns(2)
                                base_upd = c_b.number_input("Base", value=0.0)
                                exp_upd = c_e.number_input("Exp", value=0)
                                nuevo_valor_final = base_upd * (10 ** exp_upd)
                                
                            fecha_hoy = datetime.today().date()
                            nueva_fecha = st.date_input("Fecha", fecha_hoy)
                            
                            if st.form_submit_button("Guardar en SQL"):
                                freq = str(equipo.get('Frecuencia de verificación', 'Anual'))
                                proxy = calcular_proxima_fecha(nueva_fecha, freq)
                                
                                try:
                                    update_data = {
                                        "linea_ubicacion": nueva_linea_upd,
                                        "valor_actual": float(nuevo_valor_final),
                                        "fecha_ultima_verif": nueva_fecha.isoformat(),
                                        "fecha_proxima_verif": proxy.isoformat(),
                                        "estatus_verificacion": "VIGENTE",
                                        "estatus_operativo": "OPERATIVO",
                                        "auditor_responsable": st.session_state.usuario_nombre,
                                    }
                                    if es_ion:
                                        update_data["balance_ionizador"] = float(bal_act)
                                    
                                    supabase.table("inventario_esd").update(update_data).eq("id_producto", id_limpio).execute()
                                    st.success("💾 ¡Guardado correctamente!")
                                    st.cache_data.clear()
                                    limpiar_url_escaneo()
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error actualizando el equipo: {e}")
            else:
                st.error("❌ El ID no se encontró en la base de datos.")

    # ==========================================
    # VISTA 3: EVENT METER
    # ==========================================
    elif st.session_state.vista_actual == "Event Meter" and not st.session_state.modo_lectura:
        st.markdown("### ⚡ Estudio de Event Meter")
        
        c_loc1, c_loc2 = st.columns(2)
        lineas_existentes = sorted([str(x).strip() for x in df_em_local['Línea'].dropna().unique() if str(x).strip() != '']) if not df_em_local.empty else ["N/A"]
        linea_seleccionada = c_loc1.selectbox("Línea", options=lineas_existentes)
        
        nueva_op_check = c_loc2.checkbox("➕ Nueva Línea/Operación")
        if nueva_op_check:
            linea_final = c_loc1.text_input("Nueva Línea")
            id_operacion_final = c_loc2.text_input("Nuevo ID Operación")
        else:
            linea_final = linea_seleccionada
            ops = sorted([str(x).strip() for x in df_em_local[df_em_local['Línea']==linea_seleccionada]['Id de Operación'].dropna().unique()]) if not df_em_local.empty else []
            id_operacion_final = c_loc2.selectbox("Operación", options=ops if ops else ["N/A"])

        with st.form("form_em"):
            col1, col2 = st.columns(2)
            tipo_contacto = col1.selectbox("Tipo de contacto", ["Maquinaria", "Humano", "Herramienta Manual", "Otro"])
            deteccion = col1.number_input("Eventos", value=0)
            voltaje = col2.number_input("Voltaje Máx (V)", value=0.0)
            notas = st.text_area("Notas")
            
            if st.form_submit_button("Guardar en SQL"):
                try:
                    supabase.table("event_meter").insert({
                        "fecha": datetime.now().isoformat(),
                        "linea_ubicacion": linea_final,
                        "id_operacion": id_operacion_final,
                        "tipo_contacto": tipo_contacto,
                        "cantidad_eventos": int(deteccion),
                        "voltaje_maximo": float(voltaje),
                        "estatus_verificacion": "APROBADO" if float(voltaje) <= 100 else "RECHAZADO",
                        "auditor": st.session_state.usuario_nombre,
                        "notas": notas
                    }).execute()
                    st.success("Guardado Exitoso!")
                    st.cache_data.clear()
                except Exception as e:
                    st.error(f"Error SQL: {e}")

    # ==========================================
    # VISTA 4: WALKING TEST
    # ==========================================
    elif st.session_state.vista_actual == "Walking Test" and not st.session_state.modo_lectura:
        st.markdown("### 🚶‍♂️ Análisis de Walking Test")
        st.info("Sube uno o varios archivos PDF generados por el equipo de medición para extraer los datos automáticamente vía OCR y generar un reporte consolidado.")

        archivos_pdf = st.file_uploader("Selecciona los archivos PDF", type=["pdf"], accept_multiple_files=True)

        if archivos_pdf:
            st.markdown("#### Resultados Extraídos")
            datos_extraidos_wt = [] 
            
            for archivo in archivos_pdf:
                with st.expander(f"📄 Reporte: {archivo.name}", expanded=True):
                    try:
                        doc = fitz.open(stream=archivo.read(), filetype="pdf")
                        pagina = doc[0] 
                        imagen_grafica = None
                        texto_ocr = ""
                        img_b64 = "" 

                        imagenes_pdf = pagina.get_images(full=True)
                        if imagenes_pdf:
                            xref = imagenes_pdf[0][0]
                            base_image = doc.extract_image(xref)
                            image_bytes = base_image["image"]
                            imagen_grafica = Image.open(io.BytesIO(image_bytes))

                            with st.spinner("Analizando imagen con OCR..."):
                                texto_ocr = pytesseract.image_to_string(imagen_grafica)
                            
                            buffered = io.BytesIO()
                            imagen_grafica.save(buffered, format="PNG")
                            img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
                        else:
                            st.warning("No se detectó ninguna imagen/gráfica en este PDF para analizar.")
                            continue

                        fecha_hora_match = re.search(r"(\d{2}/\d{2}/\d{2})\s+(\d{2}:\d{2})", texto_ocr)
                        fecha = fecha_hora_match.group(1) if fecha_hora_match else "N/D"
                        hora = fecha_hora_match.group(2) if fecha_hora_match else "N/D"

                        hum_match = re.search(r"(\d{1,3}(?:\.\d+)?)\s*%?\s*RH", texto_ocr, re.IGNORECASE)
                        humedad = f"{hum_match.group(1)} %" if hum_match else "N/D"

                        temp_match = re.search(r"(\d{1,3}(?:\.\d+)?)\s*[^C]*C", texto_ocr, re.IGNORECASE)
                        temperatura = f"{temp_match.group(1)} °C" if temp_match else "N/D"

                        peaks_match = re.search(r"highest peaks:\s*(.*?)(?:\(|Arithmetic|\n|$)", texto_ocr, re.IGNORECASE)
                        picos = peaks_match.group(1).strip() if peaks_match else "N/D"

                        valleys_match = re.search(r"highest valleys:\s*(.*?)(?:\(|Arithmetic|\n|$)", texto_ocr, re.IGNORECASE)
                        valles = valleys_match.group(1).strip() if valleys_match else "N/D"

                        max_abs = 0.0
                        promedio_picos = 0.0
                        try:
                            p_vals = [float(x) for x in re.findall(r"[-+]?\d*\.\d+|\d+", picos)]
                            v_vals = [float(x) for x in re.findall(r"[-+]?\d*\.\d+|\d+", valles)]
                            todos_los_valores = p_vals + v_vals
                            if todos_los_valores:
                                max_abs = max(abs(x) for x in todos_los_valores)
                            if p_vals:
                                promedio_picos = sum(p_vals) / len(p_vals)
                        except:
                            pass

                        col_datos1, col_datos2 = st.columns(2)
                        with col_datos1:
                            st.metric("📅 Fecha", fecha)
                            st.metric("🌡️ Temperatura", temperatura)
                            st.metric("⚡ Voltaje Máx (Absoluto)", f"{max_abs:.2f} V")
                        with col_datos2:
                            st.metric("🕒 Hora", hora)
                            st.metric("💧 Humedad", humedad)
                            st.metric("📊 Promedio Picos", f"{promedio_picos:.2f} V")

                        st.divider()
                        st.markdown("**Gráfica Extraída:**")
                        st.image(imagen_grafica, use_container_width=True)

                        datos_extraidos_wt.append({
                            "archivo": archivo.name, "fecha": fecha, "temp": temperatura,
                            "hum": humedad, "max_abs": max_abs, "promedio_picos": promedio_picos,
                            "img_b64": img_b64
                        })

                    except Exception as e:
                        st.error(f"Ocurrió un error al procesar el archivo {archivo.name}: {e}")

            if datos_extraidos_wt:
                st.divider()
                st.markdown("### 📄 Generar Reporte Oficial Consolidado")
                st.write("Completa la información general para generar un solo reporte con todas las ubicaciones procesadas.")
                
                fecha_defecto = datos_extraidos_wt[0]['fecha'] if datos_extraidos_wt[0]['fecha'] != "N/D" else datetime.today().strftime("%d/%m/%Y")
                temp_defecto = datos_extraidos_wt[0]['temp']
                hum_defecto = datos_extraidos_wt[0]['hum']
                
                with st.form("form_reporte_wt"):
                    st.markdown("#### Datos Generales")
                    col_g1, col_g2, col_g3 = st.columns(3)
                    auditor_wt = col_g1.text_input("Auditor / Técnico", value=st.session_state.usuario_nombre if st.session_state.usuario_nombre else "")
                    operador_wt = col_g2.text_input("Operador de Prueba")
                    periodo_wt = col_g3.selectbox("Periodo de Evaluación", ["Semestre 1", "Semestre 2"])
                    
                    col_g4, col_g5 = st.columns(2)
                    equipo_wt = col_g4.text_input("Equipo de Medición Utilizado", value="DESCO 46006")
                    calzado_wt = col_g5.text_input("Calzado ESD Utilizado", value="Zapato antiestático Workman")
                    
                    st.markdown("#### 🌡️ Condiciones Ambientales (Edítalas si es necesario)")
                    col_amb1, col_amb2, col_amb3 = st.columns(3)
                    fecha_gen = col_amb1.text_input("Fecha de Prueba", value=fecha_defecto)
                    temp_gen = col_amb2.text_input("Temperatura", value=temp_defecto)
                    hum_gen = col_amb3.text_input("Humedad", value=hum_defecto)
                    
                    st.markdown("#### Configuración de Ubicaciones")
                    bloques_ubicaciones = []
                    
                    for i, dato in enumerate(datos_extraidos_wt):
                        st.markdown(f"**Ubicación {i+1} (Archivo: {dato['archivo']})**")
                        c_ub1, c_ub2 = st.columns(2)
                        nombre_ub = c_ub1.text_input(f"Nombre de Línea/Área", value=dato['archivo'].replace(".pdf", ""), key=f"nombre_{i}")
                        tipo_piso = c_ub2.selectbox(f"Tipo de Piso", ["Piso Epóxico ESD", "Loseta Vinílica Conductiva", "Tapete Antifatiga ESD", "Otro"], key=f"piso_{i}")
                        bloques_ubicaciones.append({"nombre": nombre_ub, "piso": tipo_piso, "datos": dato})
                        st.write("") 

                    submit_reporte = st.form_submit_button("Generar Reporte Consolidado en PDF/HTML", use_container_width=True)
                    
                    if submit_reporte:
                        html_ubicaciones = ""
                        for idx, block in enumerate(bloques_ubicaciones, 1):
                            data = block['datos']
                            if data['max_abs'] < 100:
                                res_class, res_text, res_color = "result-pass", "CUMPLE (PASS)", "green"
                                obs = "Ninguna anomalía. Los picos se mantuvieron por debajo del límite de 100V."
                            else:
                                res_class, res_text, res_color = "result-fail", "NO CUMPLE (FAIL)", "red"
                                obs = f"ATENCIÓN: Se registró un pico absoluto de {data['max_abs']:.2f}V, superando el límite permitido de 100V. Se requiere limpieza o revisión."

                            img_tag = f'<img src="data:image/png;base64,{data["img_b64"]}" alt="Gráfica">' if data['img_b64'] else '<i>Sin gráfica disponible</i>'

                            html_ubicaciones += f"""
                            <div class="location-block" style="border: 2px solid #003366; border-radius: 6px; padding: 20px; margin-bottom: 30px; page-break-inside: avoid;">
                                <div class="location-title" style="font-size: 18px; font-weight: bold; color: white; background-color: #003366; padding: 10px; margin: -20px -20px 20px -20px; border-top-left-radius: 4px; border-top-right-radius: 4px;">Ubicación {idx}: {block['nombre']}</div>
                                <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px; font-size: 14px;">
                                    <tr>
                                        <th style="border: 1px solid #ccc; padding: 10px; text-align: left; background-color: #f4f7f6; width: 25%;">Tipo de Piso:</th>
                                        <td style="border: 1px solid #ccc; padding: 10px; text-align: left;">{block['piso']}</td>
                                        <th style="border: 1px solid #ccc; padding: 10px; text-align: left; background-color: #f4f7f6; width: 25%;">Limpieza previa:</th>
                                        <td style="border: 1px solid #ccc; padding: 10px; text-align: left;">Sí</td>
                                    </tr>
                                    <tr>
                                        <th style="border: 1px solid #ccc; padding: 10px; text-align: left; background-color: #f4f7f6;">Voltaje Máx (Abs):</th>
                                        <td style="border: 1px solid #ccc; padding: 10px; text-align: left; font-weight: bold;">{data['max_abs']:.2f} V</td>
                                        <th style="border: 1px solid #ccc; padding: 10px; text-align: left; background-color: #f4f7f6;">Promedio de Picos:</th>
                                        <td style="border: 1px solid #ccc; padding: 10px; text-align: left;">{data['promedio_picos']:.2f} V</td>
                                    </tr>
                                </table>
                                <div class="graph-placeholder" style="width: 100%; height: 250px; background-color: #fafafa; border: 2px dashed #aaa; display: flex; align-items: center; justify-content: center; color: #888; margin: 20px 0; overflow: hidden;">
                                    {img_tag}
                                </div>
                                <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
                                    <tr>
                                        <th style="border: 1px solid #ccc; padding: 10px; text-align: left; background-color: #f4f7f6; width: 20%;">Observaciones:</th>
                                        <td style="border: 1px solid #ccc; padding: 10px; text-align: left;">{obs}</td>
                                        <th style="border: 1px solid #ccc; padding: 10px; text-align: left; background-color: #f4f7f6; width: 20%;">Resultado Final:</th>
                                        <td style="border: 1px solid #ccc; padding: 10px; text-align: left; color: {res_color}; font-weight: bold; font-size: 16px;">{res_text}</td>
                                    </tr>
                                </table>
                            </div>
                            """

                        html_completo = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Reporte de Walking Test</title>
    <style>
        body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #333; margin: 0; padding: 20px; background-color: white; }}
        .container {{ max-width: 900px; margin: 0 auto; padding: 20px; }}
        header {{ text-align: center; border-bottom: 3px solid #003366; padding-bottom: 20px; margin-bottom: 30px; }}
        h1 {{ color: #003366; margin: 0 0 10px 0; font-size: 24px; }}
        h2 {{ font-size: 18px; color: #003366; border-bottom: 1px solid #ccc; padding-bottom: 5px; margin-top: 30px; }}
        table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; font-size: 14px; }}
        th, td {{ border: 1px solid #ccc; padding: 10px; text-align: left; }}
        th {{ background-color: #f4f7f6; font-weight: bold; width: 25%; }}
        .signatures {{ display: flex; justify-content: space-between; margin-top: 50px; page-break-inside: avoid; }}
        .signature-box {{ width: 45%; text-align: center; }}
        .signature-line {{ border-top: 1px solid black; margin-top: 50px; padding-top: 5px; font-size: 14px; }}
        img {{ max-width: 100%; max-height: 100%; object-fit: contain; }}
        @media print {{ body {{ padding: 0; }} .no-print {{ display: none; }} }}
    </style>
</head>
<body>
<div class="container">
    <header>
        <h1>Reporte de Walking Test (Prueba de Caminado)</h1>
        <p style="margin: 0; color: #666; font-size: 14px;">Evaluación de Sistema de Piso y Calzado ESD</p>
        <p style="margin: 0; color: #666; font-size: 14px;"><strong>Estándares aplicables:</strong> ANSI/ESD S20.20 y ANSI/ESD STM97.2</p>
    </header>

    <h2>1. Información General y Condiciones Ambientales</h2>
    <table>
        <tr><th>Fecha de Prueba:</th><td>{fecha_gen}</td><th>Periodo:</th><td>{periodo_wt}</td></tr>
        <tr><th>Auditor / Técnico:</th><td>{auditor_wt}</td><th>Operador de Prueba:</th><td>{operador_wt}</td></tr>
        <tr><th>Temperatura:</th><td>{temp_gen}</td><th>Humedad:</th><td>{hum_gen}</td></tr>
    </table>

    <h2>2. Equipo de Medición y Sistema Evaluado</h2>
    <table>
        <tr><th>Equipo Utilizado:</th><td>{equipo_wt}</td><th>Criterio de Aceptación:</th><td style="font-weight:bold; color:#003366;">&lt; 100 Voltios (Absoluto)</td></tr>
        <tr><th>Calzado ESD:</th><td colspan="3">{calzado_wt}</td></tr>
    </table>

    <h2>3. Resultados por Ubicación</h2>
    {html_ubicaciones}

    <div class="signatures">
        <div class="signature-box"><div class="signature-line"><strong>Realizado por:</strong><br>{auditor_wt}</div></div>
        <div class="signature-box"><div class="signature-line"><strong>Revisado / Aprobado por:</strong><br>Coordinador ESD</div></div>
    </div>
</div>
</body>
</html>"""
                        b64_html = base64.b64encode(html_completo.encode('utf-8')).decode('utf-8')
                        nombre_archivo = f"Walking_Test_{fecha_gen.replace('/', '-')}_{periodo_wt.replace(' ', '')}.html"
                        
                        st.success("✅ ¡Reporte consolidado generado exitosamente!")
                        href = f'<a href="data:text/html;base64,{b64_html}" download="{nombre_archivo}" target="_blank" style="display: block; text-align: center; padding: 15px; background-color: #003366; color: white; text-decoration: none; border-radius: 8px; font-weight: bold; margin-top: 10px; font-size: 16px;">📥 Descargar Reporte Completo (Abrir para imprimir PDF)</a>'
                        st.markdown(href, unsafe_allow_html=True)

    # ==========================================
    # VISTA 5: VALIDACIÓN ESD (SISTEMA INTEGRAL)
    # ==========================================
    elif st.session_state.vista_actual == "Validación" and not st.session_state.modo_lectura:
        st.markdown("### ✅ Validación Integral de Elementos de Control ESD")
        
        # Equipos SQL
        try:
            resp_eq = supabase.table("equipos_medicion").select("*").execute()
            df_equipos = pd.DataFrame(resp_eq.data)
            lista_equipos = df_equipos["id_equipo"].tolist() if not df_equipos.empty else ["N/A"]
        except:
            df_equipos = pd.DataFrame()
            lista_equipos = ["Sin conexión"]

        tab_registro, tab_historial = st.tabs(["📝 Registrar Validación", "🖼️ Visor de Registros"])

        with tab_registro:
            c1, c2 = st.columns(2)
            elemento_sel = c1.selectbox("Elemento a validar:", ["Superficie de trabajo", "Piso ESD", "Ionizador", "Calzado"])
            id_equipo_sel = c2.selectbox("ID del Equipo:", lista_equipos)
            
            with st.form("form_val"):
                id_elemento = st.text_input("ID Elemento")
                medicion_1 = st.number_input("Medición Principal", value=0.0)
                referencia = st.number_input("Límite Permitido", value=1.0e9)
                ubicacion = st.text_input("Ubicación")
                temp = st.text_input("Temp")
                hum = st.text_input("Humedad")
                notas = st.text_area("Notas")
                
                if st.form_submit_button("Guardar Validación en SQL"):
                    resultado = "CUMPLE (APROBADO)" if medicion_1 < referencia else "NO CUMPLE (RECHAZADO)"
                    try:
                        supabase.table("validacion_esd").insert({
                            "fecha_auditoria": datetime.now().isoformat(),
                            "auditor": st.session_state.usuario_nombre,
                            "id_elemento": id_elemento.upper(),
                            "elemento_s20_20": elemento_sel,
                            "temperatura": temp,
                            "humedad": hum,
                            "id_equipo_utilizado": id_equipo_sel,
                            "limite_referencia": float(referencia),
                            "medicion_1": float(medicion_1),
                            "resultado": resultado,
                            "notas": notas,
                            "imagen_url": "Pendiente de Storage"
                        }).execute()
                        st.success("Validación Guardada!")
                        st.cache_data.clear()
                    except Exception as e:
                        st.error(f"Error SQL: {e}")

        with tab_historial:
            st.markdown("#### 🗂️ Historial (Directo de Supabase)")
            try:
                resp_val = supabase.table("validacion_esd").select("*").execute()
                df_val = pd.DataFrame(resp_val.data)
                
                if df_val.empty:
                    st.info("Aún no hay registros de validación.")
                else:
                    df_val = df_val.dropna(subset=['fecha_auditoria', 'elemento_s20_20'], how='all').iloc[::-1]

                    for index, row in df_val.iterrows():
                        resultado_str = str(row.get('resultado', ''))
                        icono_res = "🟢" if "CUMPLE" in resultado_str.upper() else "🔴"
                        
                        with st.expander(f"{icono_res} {str(row.get('fecha_auditoria', ''))[:10]} | {row.get('id_elemento', 'N/D')} ({row.get('elemento_s20_20', '')})"):
                            c_det1, c_det2, c_det3 = st.columns([1, 1, 1])
                            
                            with c_det1:
                                st.markdown("##### 📦 Detalles Generales")
                                st.markdown(f"**Elemento:** {row.get('elemento_s20_20', 'N/D')}")
                                st.markdown(f"**ID:** {row.get('id_elemento', 'N/D')}")
                                st.markdown(f"**Temp/Hum:** {row.get('temperatura', 'N/D')} | {row.get('humedad', 'N/D')}")
                            
                            with c_det2:
                                st.markdown("##### 🛠️ Equipo y Límite")
                                st.markdown(f"**Equipo Utilizado:** {row.get('id_equipo_utilizado', 'N/D')}")
                                st.markdown(f"**Límite S20.20:** `< {row.get('limite_referencia', 'N/D')}`")

                            with c_det3:
                                st.markdown("##### 📊 Resultados")
                                st.markdown(f"**Medición:** `{row.get('medicion_1', 'N/D')}`")
                                st.markdown(f"**Notas:** {row.get('notas', 'Ninguna')}")
                            
                            st.divider()
                            st.info("El visor de imágenes y PDFs se reactivará al implementar Supabase Storage.")
            except Exception as e:
                st.warning(f"Error al cargar historial: {e}")
