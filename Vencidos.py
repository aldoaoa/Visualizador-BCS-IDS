import streamlit as st
import pandas as pd
import plotly.express as px
from PIL import Image
import os
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
import time
from werkzeug.security import generate_password_hash, check_password_hash

if "vista_actual" not in st.session_state:
    st.session_state.vista_actual = "Mapa" # O la vista principal que uses por defecto

if "usuario_nombre" not in st.session_state:
    st.session_state.usuario_nombre = None

if "modo_lectura" not in st.session_state:
    st.session_state.modo_lectura = False

if "rol_usuario" not in st.session_state:
    st.session_state.rol_usuario = None

# Agrega aquí cualquier otra llave que uses (ej. val_form_key)
if "val_form_key" not in st.session_state:
    st.session_state.val_form_key = 0

# Configuración de página
st.set_page_config(page_title="Control ESD BCS-AIS", layout="wide")

# ==========================================
# DICCIONARIOS GLOBALES DE REFERENCIA
# ==========================================
INFO_ELEMENTOS_ESD = {
    "Pulsera antiestática": {"limite": "RS < 3.5x10^7 ohms", "ref_num": 3.5e7, "tipo_material": "Banda elástica / Metal", "magnitud": "Resistencia", "metodo": "ANSI/ESD TR53", "frecuencia": "Semestralmente"},
    "Calzado": {"limite": "RS < 1.0x10^9 ohms", "ref_num": 1.0e9, "tipo_material": "Suela disipativa / Talón", "magnitud": "Resistencia", "metodo": "ANSI/ESD TR53", "frecuencia": "Semestralmente"},
    "Piso ESD": {"limite": "RTG < 1.0x10^9 ohms / Walking Test < 100V", "ref_num": 1.0e9, "tipo_material": "Epóxico / Vinílico ESD", "magnitud": "Resistencia", "metodo": "ANSI/ESD TR53 / ANSI/ESD 97.2", "frecuencia": "Semestralmente"},
    "Superficie de trabajo": {"limite": "RTG < 1.0x10^9 ohms", "ref_num": 1.0e9, "tipo_material": "Tapete disipativo / Mesa", "magnitud": "Resistencia", "metodo": "ANSI/ESD TR53", "frecuencia": "Anualmente"},
    "Monitor Continuo": {"limite": "RTG < 2 ohms", "ref_num": 2.0, "tipo_material": "Equipo Electrónico", "magnitud": "Resistencia", "metodo": "Anexo A.1", "frecuencia": "Trimestralmente"},
    "Ionizador": {"limite": "Descarga: <10s, Bal: +-35V", "ref_num": 10.0, "tipo_material": "Ventilador / Barra", "magnitud": "Tiempo", "metodo": "ANSI/ESD SP3.3-2016", "frecuencia": "Trimestralmente"},
    "Bolsa disipativa": {"limite": "RS < 1.0x10^9 ohms", "ref_num": 1.0e9, "tipo_material": "Plástico disipativo", "magnitud": "Resistencia", "metodo": "ANSI/ESD STM11.11", "frecuencia": "Semestralmente"},
    "Cautín / Estación de soldar": {"limite": "RTG < 10 ohms", "ref_num": 10.0, "tipo_material": "Metal / Punta", "magnitud": "Resistencia", "metodo": "ANSI/ESD TR53", "frecuencia": "Semestralmente"},
    "Caja Disipativa": {"limite": "RS < 1.0x10^11 ohms", "ref_num": 1.0e11, "tipo_material": "Plástico / Cartón", "magnitud": "Resistencia", "metodo": "ANSI/ESD STM11.11", "frecuencia": "Anualmente"},
    "Caja conductiva": {"limite": "RS < 1.0x10^4 ohms", "ref_num": 1.0e4, "tipo_material": "Plástico conductivo", "magnitud": "Resistencia", "metodo": "ANSI/ESD STM11.11", "frecuencia": "Anualmente"},
    "Charola conductiva": {"limite": "RS < 1.0x10^4 ohms", "ref_num": 1.0e4, "tipo_material": "Plástico conductivo", "magnitud": "Resistencia", "metodo": "ANSI/ESD STM11.13/11.11", "frecuencia": "Anualmente"},
    "Charola Disipativa": {"limite": "RS < 1.0x10^11 ohms", "ref_num": 1.0e11, "tipo_material": "Plástico disipativo", "magnitud": "Resistencia", "metodo": "ANSI/ESD STM11.13/11.11", "frecuencia": "Anualmente"},
    "Magazine": {"limite": "RS < 1.0x10^11 ohms", "ref_num": 1.0e11, "tipo_material": "Metal / Plástico", "magnitud": "Resistencia", "metodo": "ANSI/ESD STM11.13/11.11", "frecuencia": "Anualmente"},
    "Bata": {"limite": "RPP < 1.0x10^11 ohms", "ref_num": 1.0e11, "tipo_material": "Tela ESD", "magnitud": "Resistencia", "metodo": "ANSI/ESD TR53", "frecuencia": "Semestralmente"},
    "Gorra": {"limite": "RPP < 1.0x10^11 ohms", "ref_num": 1.0e11, "tipo_material": "Tela ESD", "magnitud": "Resistencia", "metodo": "ANSI/ESD TR53", "frecuencia": "Semestralmente"},
    "Rack": {"limite": "RTG < 1.0x10^9 ohms", "ref_num": 1.0e9, "tipo_material": "Metal", "magnitud": "Resistencia", "metodo": "ANSI/ESD STM4.1", "frecuencia": "Anualmente"},
    "Carrito": {"limite": "RTG < 1.0x10^9 ohms", "ref_num": 1.0e9, "tipo_material": "Metal", "magnitud": "Resistencia", "metodo": "ANSI/ESD STM4.1", "frecuencia": "Anualmente"},
    "Silla ESD": {"limite": "RTG < 1.0x10^9 ohms", "ref_num": 1.0e9, "tipo_material": "Tela / Vinil ESD", "magnitud": "Resistencia", "metodo": "ANSI/ESD TR53", "frecuencia": "Semestralmente"},
    "Guantes Nitrilo": {"limite": "RTG < 1.0x10^9 ohms", "ref_num": 1.0e9, "tipo_material": "Nitrilo", "magnitud": "Resistencia", "metodo": "ANSI/ESD TR53", "frecuencia": "Semestralmente"},
    "Guantes Tela": {"limite": "RTG < 1.0x10^9 ohms", "ref_num": 1.0e9, "tipo_material": "Tela ESD", "magnitud": "Resistencia", "metodo": "ANSI/ESD TR53", "frecuencia": "Semestralmente"},
    "Tapete de piso": {"limite": "RTG < 1.0x10^9 ohms", "ref_num": 1.0e9, "tipo_material": "Caucho / Vinil ESD", "magnitud": "Resistencia", "metodo": "ANSI/ESD TR53", "frecuencia": "Semestralmente"},
    "Aislantes - EPA (General)": {"limite": ">30 cm de ESDS", "ref_num": 2000.0, "tipo_material": "Material Aislante", "magnitud": "Voltaje", "metodo": "Anexo A.2", "frecuencia": "Semestralmente"},
    "Aislantes - Conductores Aislados": {"limite": "< 35 Volts", "ref_num": 35.0, "tipo_material": "Conductor Aislado", "magnitud": "Voltaje", "metodo": "Anexo A.2", "frecuencia": "Semestralmente"},
    "Aislantes - Contacto directo": {"limite": "<= 125 Volts/in", "ref_num": 125.0, "tipo_material": "Material Aislante", "magnitud": "Voltaje", "metodo": "Anexo A.2", "frecuencia": "Semestralmente"},
    "Bolsas blindadas": {"limite": "Visual", "ref_num": 0.0, "tipo_material": "Plástico metalizado", "magnitud": "Otro", "metodo": "Inspección visual", "frecuencia": "Trimestralmente"}
}

MAPA_UNIDADES = {
    "Resistencia": "Ohms",
    "Voltaje": "Volts",
    "Tiempo": "Segundos",
    "Longitud": "cm",
    "Otro": "N/A"
}

def ejecutar_automigracion_lineas():
    """Extrae líneas únicas de las tablas históricas y las inserta en catalogo_lineas."""
    lineas_encontradas = set()

    # 1. Extraer ubicaciones de la tabla de validación general
    try:
        resp_val = supabase.table("validacion_esd").select("ubicacion").execute()
        if resp_val.data:
            for reg in resp_val.data:
                linea = str(reg.get("ubicacion", "")).strip().upper()
                if linea and linea not in ["NONE", "NAN", "NULL", "N/D", "", "SIN REGISTROS"]:
                    lineas_encontradas.add(linea)
    except Exception as e:
        st.write(f"Nota informativa (Validación): {e}")

    # 2. Extraer ubicaciones de la tabla de Event Meter
    try:
        resp_em = supabase.table("event_meter").select("linea_ubicacion").execute()
        if resp_em.data:
            for reg in resp_em.data:
                linea = str(reg.get("linea_ubicacion", "")).strip().upper()
                if linea and linea not in ["NONE", "NAN", "NULL", "N/D", "", "SIN REGISTROS"]:
                    lineas_encontradas.add(linea)
    except Exception as e:
        st.write(f"Nota informativa (Event Meter): {e}")

    # 3. Insertar registros en la tabla catálogo maestro
    nuevos_registros = 0
    for linea_nombre in sorted(lineas_encontradas):
        try:
            # Si el registro ya existe, la base de datos lanzará un error por el constraint UNIQUE,
            # lo cual es perfecto ya que el bloque except lo controlará sin detener el ciclo.
            supabase.table("catalogo_lineas").insert({"nombre_linea": linea_nombre}).execute()
            nuevos_registros += 1
        except:
            pass # Ya existía en el catálogo maestro, se omite de forma segura.

    return nuevos_registros, len(lineas_encontradas)
    
def obtener_catalogo_lineas():
    """Descarga el catálogo maestro de líneas de Supabase"""
    try:
        resp = supabase.table("catalogo_lineas").select("nombre_linea").order("nombre_linea").execute()
        return [x['nombre_linea'] for x in resp.data] if resp.data else ["Sin Ubicaciones"]
    except:
        return ["Sin Ubicaciones"]
        
def limpiar_id(texto):
    if not texto: return ""
    # Convierte a texto, quita espacios raros, borra espacios al inicio/fin y lo hace mayúscula
    return str(texto).replace('\xa0', ' ').strip().upper()

def generar_html_reporte_linea(linea, df_linea, auditor, comentarios, db_id):
    año_actual = datetime.today().strftime("%y")
    fecha_hoy = datetime.today().strftime("%d-%b-%Y")
    fecha_pie = datetime.today().strftime("%Y/%m/%d")
    
    # Construir las filas de la tabla
    filas_html = ""
    for i, row in enumerate(df_linea.to_dict('records'), 1):
        categoria = str(row.get('Categoría', 'N/D'))
        id_elem = str(row.get('ID / Nombre', 'N/D'))
        clasif = str(row.get('Clasificación', 'N/D'))
        ultima_val = str(row.get('Última Medición', 'N/D'))  # <--- SE AGREGA LA FECHA DE VALIDACIÓN
        vencimiento = str(row.get('Próximo Vencimiento', 'N/D'))
        estatus_raw = str(row.get('Estatus', '')).upper()
        
        # Limpiar el emoji del estatus si viene con él
        estatus_limpio = estatus_raw.replace('🟢', '').replace('🔴', '').replace('🟡', '').strip()
        color_txt = "text-green-600" if "VIGENTE" in estatus_limpio or "PASA" in estatus_limpio else ("text-red-600" if "VENCIDO" in estatus_limpio or "FALLA" in estatus_limpio else "text-yellow-600")
        
        filas_html += f"""
        <tr class="text-center border-b border-gray-300 print:border-black">
            <td class="border-r border-gray-300 p-2 print:border-black">{i}</td>
            <td class="border-r border-gray-300 p-2 font-bold text-left print:border-black">{id_elem}</td>
            <td class="border-r border-gray-300 p-2 text-left print:border-black">{categoria} - {clasif}</td>
            <td class="border-r border-gray-300 p-2 font-mono text-gray-700 print:border-black">{ultima_val}</td>
            <td class="border-r border-gray-300 p-2 font-mono print:border-black">{vencimiento}</td>
            <td class="p-2 font-bold {color_txt}">{estatus_limpio}</td>
        </tr>
        """
        
    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>BCS-LV-{db_id:03d}-{año_actual}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>@media print {{ body {{ -webkit-print-color-adjust: exact; }} }}</style>
</head>
<body class="bg-gray-100 p-4 md:p-8 font-sans text-sm print:bg-white print:p-0">
    <div class="max-w-5xl mx-auto mb-6 bg-white p-4 rounded-lg shadow flex justify-end print:hidden">
        <button onclick="window.print()" class="bg-blue-600 text-white px-6 py-2 rounded font-bold shadow-sm">🖨️ Imprimir / Guardar PDF</button>
    </div>
    <div class="max-w-5xl mx-auto bg-white shadow-xl print:shadow-none print:w-full print:border print:border-black">
        <div class="border-b-2 border-gray-800 p-6 flex items-start justify-between print:border-black">
            <div class="w-1/3">
                <img src="https://github.com/aldoaoa/Visualizador-BCS-IDS/blob/main/BCS%20LOGO.png?raw=true" alt="BCS Logo" class="h-16 object-contain" />
            </div>
            <div class="w-1/3 text-center">
                <h1 class="text-lg font-bold text-gray-800">REPORTE DE VALIDACIÓN DE LÍNEA (ESD)</h1>
                <p class="text-xs text-gray-600">Cumplimiento Integral ANSI/ESD S20.20</p>
            </div>
            <div class="w-1/3 text-right text-sm">
                <div class="font-bold text-red-700 text-lg mb-2">Folio: BCS-LV-{db_id:03d}-{año_actual}</div>
                <div class="flex justify-end gap-2 mb-1">
                    <span class="font-bold">Fecha de Emisión:</span><span>{fecha_hoy}</span>
                </div>
            </div>
        </div>

        <div class="p-6 space-y-6">
            <div class="bg-gray-100 p-4 border border-gray-300 rounded print:border-black print:bg-transparent">
                <div class="grid grid-cols-2 gap-4">
                    <div><span class="font-bold text-[#003366]">Línea Evaluada:</span> <span class="text-lg font-bold">{linea}</span></div>
                    <div><span class="font-bold text-[#003366]">Auditor Responsable:</span> {auditor}</div>
                </div>
            </div>

            <div>
                <div class="bg-[#003366] text-white font-bold px-2 py-1 uppercase text-xs print:bg-black">Desglose de Activos Operativos en Línea</div>
                <table class="w-full text-sm border-collapse border border-gray-300 print:border-black">
                    <tr class="bg-gray-200 border-b border-gray-300 print:bg-transparent print:border-black">
                        <th class="p-2 border-r border-gray-300 print:border-black w-10">No.</th>
                        <th class="p-2 border-r border-gray-300 print:border-black text-left">ID Elemento</th>
                        <th class="p-2 border-r border-gray-300 print:border-black text-left">Tipo de Equipo</th>
                        <th class="p-2 border-r border-gray-300 print:border-black">Última Validación</th>
                        <th class="p-2 border-r border-gray-300 print:border-black">Próx. Vencimiento</th>
                        <th class="p-2">Estatus Actual</th>
                    </tr>
                    {filas_html}
                </table>
            </div>

            <div class="mt-4 border border-gray-300 p-3 bg-gray-50 print:border-black print:bg-transparent">
                <div class="font-bold text-[#003366] text-xs uppercase mb-1 print:text-black">Comentarios / Observaciones de la Línea:</div>
                <div class="text-sm">{comentarios}</div>
            </div>

            <div class="mt-16 mb-8 pt-8 [page-break-inside:avoid]">
                <div class="w-1/2 mx-auto text-center border-t-2 border-gray-800 pt-2 print:border-black">
                    <div class="font-bold uppercase text-sm mb-1">CERTIFICADO POR:</div>
                    <div class="text-center font-bold text-gray-700 print:text-black">{auditor}</div>
                    <div class="text-xs text-gray-500">Coordinador ESD</div>
                </div>
            </div>
            
            <div class="border-t-[3px] border-b-[3px] border-black mt-16 py-1 text-[11px] font-sans [page-break-inside:avoid]">
                <div class="flex justify-between items-end">
                    <div class="text-left leading-tight">
                        <div>E_310_4_120_QRO_SP_Rev. A</div>
                        <div>Formato de Validación de Línea Integral.</div>
                    </div>
                    <div class="text-center leading-tight">
                        <div>Fecha: {fecha_pie}</div>
                    </div>
                    <div class="text-right leading-tight">
                        <div>Ref.E_310_3_001_QRO_SP</div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>"""
    return html, año_actual

def generar_html_reporte_completo(row, index):
    """Genera el reporte HTML nativo leyendo las columnas individuales de medición en Supabase."""
    
    def get_sql_val(key, default="N/D"):
        v = row.get(key)
        if pd.isna(v) or v is None:
            return default
        return str(v).strip()

    # 1. Extraer las 5 columnas directamente
    mediciones_raw = [
        get_sql_val('medicion_1', ''),
        get_sql_val('medicion_2', ''),
        get_sql_val('medicion_3', ''),
        get_sql_val('medicion_4', ''),
        get_sql_val('medicion_5', '')
    ]
    
    mediciones = []
    for m in mediciones_raw:
        if m and m.lower() not in ['n/d', 'nan', 'none', 'null', '']:
            mediciones.append(m)
    
    # 2. Calcular promedio
    valid_nums = []
    for m in mediciones:
        try:
            valid_nums.append(float(m))
        except: pass
            
    promedio = sum(valid_nums) / len(valid_nums) if valid_nums else 0
    promedio_str = f"{promedio:.2E}" if promedio > 0 else "N/A"
    
    # Formato de Referencia
    ref_raw = get_sql_val('limite_referencia', '')
    try:
        ref_num = float(ref_raw)
        ref_str = f"{ref_num:.2E}" if ref_num > 1000 or ref_num < 0.01 else str(ref_num)
    except:
        ref_str = ref_raw

    metodo_prueba = get_sql_val('metodo', '')
    unidad_medida = get_sql_val('unidad', '')

    # 3. Generar las filas de la tabla
    html_rows = ""
    for i, val in enumerate(mediciones, 1):
        try:
            val_num = float(val)
            val_str = f"{val_num:.2E}" if val_num > 1000 or val_num < 0.01 else str(val)
        except:
            val_str = str(val)
            
        html_rows += f"""
        <tr class="border-b border-gray-200 hover:bg-blue-50 print:hover:bg-transparent text-center">
            <td class="p-1 border-r border-gray-300 font-bold">{i}</td>
            <td class="p-1 border-r border-gray-300">{ref_str}</td>
            <td class="p-1 border-r border-gray-300">0.0</td>
            <td class="p-1 border-r border-gray-300 bg-yellow-50 print:bg-transparent font-mono font-bold">{val_str}</td>
            <td class="p-1 border-r border-gray-300">{metodo_prueba}</td>
            <td class="p-1 border-r border-gray-300">{unidad_medida}</td>
        </tr>
        """
        
    # 4. Procesar Imagen
    img_url = get_sql_val('imagen_url', '')
    if img_url == 'N/D' or not img_url or img_url.lower() in ['nan', 'none', 'null', 'pendiente de storage']:
        img_tag = "<span class='text-gray-400 flex flex-col items-center'><br><br>Sin evidencia fotográfica</span>"
    else:
        img_tag = f'<img src="{img_url}" style="height: 190px; width: auto; max-width: 100%; object-fit: contain; margin: 0 auto;" />'
        
    # 5. Formatear la fecha
    fecha_raw = get_sql_val('fecha_auditoria', '')
    try:
        dt = datetime.fromisoformat(fecha_raw.split('.')[0])
        meses = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
        fecha_ejecucion = f"{dt.day:02d}-{meses[dt.month-1]}-{dt.year}"
    except:
        fecha_ejecucion = fecha_raw.split('T')[0] if 'T' in fecha_raw else fecha_raw

    año_actual = datetime.today().strftime("%y")
    
    # 6. Extraer variables generales
    elemento = get_sql_val('elemento_s20_20', 'N/D')
    magnitud = INFO_ELEMENTOS_ESD.get(elemento, {}).get("magnitud", "N/D")

    id_elemento = get_sql_val('id_elemento')
    fabricante_elem = get_sql_val('fabricante_elem')
    modelo_elem = get_sql_val('modelo_elem')
    sn_elem = get_sql_val('sn_elem')
    
    temperatura = get_sql_val('temperatura')
    humedad = get_sql_val('humedad')
    ubicacion = get_sql_val('ubicacion')
    
    id_equipo = get_sql_val('id_equipo_utilizado')
    tipo_equipo = get_sql_val('tipo_equipo')
    reporte_cal = get_sql_val('reporte_cal')
    resolucion = get_sql_val('resolucion')
    
    fabricante_eq = get_sql_val('fabricante_eq')
    modelo_eq = get_sql_val('modelo_eq')
    sn_eq = get_sql_val('sn_eq')
    fecha_prox_cal = get_sql_val('fecha_prox_cal')
    
    notas = get_sql_val('notas', 'Sin observaciones adicionales.')
    resultado = get_sql_val('resultado')
    auditor = get_sql_val('auditor')

# Generar fecha en formato YYYY/MM/DD para el pie de página
    fecha_pie_str = datetime.today().strftime("%Y/%m/%d")
# --- NUEVO: EXTRAER ID REAL DE LA BASE DE DATOS ---
    db_id = row.get('id', index)
    try:
        db_id = int(db_id)
    except:
        db_id = index
    # --------------------------------------------------
    # --- PLANTILLA HTML ---
    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>BCS-PV-{db_id:03d}-{año_actual}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @media print {{ body {{ -webkit-print-color-adjust: exact; }} }}
    </style>
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
                <div class="font-bold text-red-700 text-lg mb-2">Reporte: BCS-PV-{db_id:03d}-{año_actual}</div>
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
                        <tr class="border-b border-gray-300"><td class="w-1/3 font-bold bg-gray-100 p-1 border-r border-gray-300">ID:</td><td class="p-1">{id_elemento}</td></tr>
                        <tr class="border-b border-gray-300"><td class="w-1/3 font-bold bg-gray-100 p-1 border-r border-gray-300">Elemento:</td><td class="p-1">{elemento}</td></tr>
                        <tr class="border-b border-gray-300"><td class="w-1/3 font-bold bg-gray-100 p-1 border-r border-gray-300">Fabricante:</td><td class="p-1">{fabricante_elem}</td></tr>
                        <tr class="border-b border-gray-300"><td class="w-1/3 font-bold bg-gray-100 p-1 border-r border-gray-300">Modelo:</td><td class="p-1">{modelo_elem}</td></tr>
                        <tr><td class="w-1/3 font-bold bg-gray-100 p-1 border-r border-gray-300">No. Serie:</td><td class="p-1">{sn_elem}</td></tr>
                    </table>
                </div>
                <div>
                    <div class="bg-gray-800 text-white font-bold px-2 py-1 uppercase text-xs">Información General</div>
                    <table class="w-full text-sm border-collapse border border-gray-300 h-full">
                        <tr class="border-b border-gray-300"><td class="w-1/3 font-bold bg-gray-100 p-1 border-r border-gray-300">Temperatura:</td><td class="p-1">{temperatura}</td></tr>
                        <tr class="border-b border-gray-300"><td class="w-1/3 font-bold bg-gray-100 p-1 border-r border-gray-300">Humedad:</td><td class="p-1">{humedad}</td></tr>
                        <tr class="border-b border-gray-300"><td class="w-1/3 font-bold bg-gray-100 p-1 border-r border-gray-300">Ubicación:</td><td class="p-1">{ubicacion}</td></tr>
                        <tr><td class="w-1/3 font-bold bg-gray-100 p-1 border-r border-gray-300">Magnitud:</td><td class="p-1">{magnitud}</td></tr>
                    </table>
                </div>
            </div>

            <div>
                <div class="bg-gray-800 text-white font-bold px-2 py-1 uppercase text-xs">Trazabilidad (Equipo de Medición)</div>
                <div class="grid grid-cols-2 border-l border-t border-gray-300">
                    <div class="border-r border-b border-gray-300">
                        <table class="w-full text-sm">
                            <tr class="border-b border-gray-300"><td class="font-bold bg-gray-100 p-1 w-1/3 border-r border-gray-300">ID:</td><td class="p-1">{id_equipo}</td></tr>
                            <tr class="border-b border-gray-300"><td class="font-bold bg-gray-100 p-1 border-r border-gray-300">Equipo:</td><td class="p-1">{tipo_equipo}</td></tr>
                            <tr class="border-b border-gray-300"><td class="font-bold bg-gray-100 p-1 border-r border-gray-300">Reporte Cal.:</td><td class="p-1">{reporte_cal}</td></tr>
                            <tr><td class="font-bold bg-gray-100 p-1 border-r border-gray-300">Resolución:</td><td class="p-1">{resolucion}</td></tr>
                        </table>
                    </div>
                    <div class="border-b border-gray-300">
                        <table class="w-full text-sm">
                            <tr class="border-b border-gray-300"><td class="font-bold bg-gray-100 p-1 w-1/3 border-r border-gray-300">Fabricante:</td><td class="p-1">{fabricante_eq}</td></tr>
                            <tr class="border-b border-gray-300"><td class="font-bold bg-gray-100 p-1 border-r border-gray-300">Modelo:</td><td class="p-1">{modelo_eq}</td></tr>
                            <tr class="border-b border-gray-300"><td class="font-bold bg-gray-100 p-1 border-r border-gray-300">No. Serie:</td><td class="p-1">{sn_eq}</td></tr>
                            <tr><td class="font-bold bg-gray-100 p-1 border-r border-gray-300">Vigencia Cal.:</td><td class="p-1">{fecha_prox_cal}</td></tr>
                        </table>
                    </div>
                </div>
            </div>

            <div>
                <div class="bg-gray-800 text-white font-bold px-2 py-1 uppercase text-xs">Resultados (ANSI/ESD S20.20)</div>
                <table class="w-full text-sm border-collapse border border-gray-300 text-center">
                    <tr class="bg-gray-100 border-b border-gray-300">
                        <th class="p-2 border-r border-gray-300">No.</th>
                        <th class="p-2 border-r border-gray-300">Referencia</th>
                        <th class="p-2 border-r border-gray-300">Tolerancia</th>
                        <th class="p-2 border-r border-gray-300">Resultado Obtenido</th>
                        <th class="p-2 border-r border-gray-300">Método de Prueba</th>
                        <th class="p-2 border-r border-gray-300">Unidad</th>
                    </tr>
                    {html_rows}
                    <tr class="border-t-2 border-gray-400 bg-gray-50">
                        <td colspan="3" class="p-2 font-bold text-right border-r border-gray-300">Promedio / Final:</td>
                        <td class="p-2 font-mono font-bold text-center border-r border-gray-300">{promedio_str}</td>
                        <td colspan="2"></td>
                    </tr>
                </table>
            </div>

            <div class="grid grid-cols-2 gap-6 h-64">
                <div class="border border-gray-300 flex flex-col items-center justify-center bg-gray-50 overflow-hidden relative">
                    <div class="absolute top-0 left-0 bg-gray-800 text-white font-bold px-2 py-1 uppercase text-xs w-full text-left z-10">Imagen del Producto / Evidencia</div>
                    <div class="mt-8 flex-1 flex items-center justify-center p-2">
                        {img_tag}
                    </div>
                </div>
                <div class="border border-gray-300 flex flex-col relative">
                    <div class="bg-gray-800 text-white font-bold px-2 py-1 uppercase text-xs w-full">Comentarios / Observaciones</div>
                    <div class="p-2 text-sm">{notas}</div>
                    <div class="absolute bottom-2 right-2 text-lg font-bold text-gray-700">{resultado}</div>
                </div>
            </div>

            <div class="mt-12 mb-8 pt-8 [page-break-inside:avoid]">
                <div class="w-1/3 mx-auto text-center border-t border-gray-800 pt-2">
                    <div class="font-bold uppercase text-sm mb-1">APROBADO Y CERTIFICADO POR:</div>
                    <div class="text-center font-bold text-gray-700">{auditor}</div>
                </div>
            </div>
            
            <div class="border-t-[3px] border-b-[3px] border-black mt-16 py-1 text-[11px] font-sans [page-break-inside:avoid]">
                <div class="flex justify-between items-end">
                    <div class="text-left leading-tight">
                        <div>E_310_4_113_QRO_SP_Rev. A</div>
                        <div>Formato de Validación de producto.</div>
                    </div>
                    <div class="text-center leading-tight">
                        <div>Fecha: {fecha_pie_str}</div>
                    </div>
                    <div class="text-right leading-tight">
                        <div>Ref.E_310_3_001_QRO_SP</div>
                    </div>
                </div>
            </div>
            
        </div>
    </div>
</body>
</html>"""
    return html
    
# --- CONEXIÓN A SUPABASE ---
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase: Client = init_connection()

# --- NUEVA LECTURA DE DATOS UNIFICADA ---
@st.cache_data(ttl=10) 
def cargar_datos_cloud():
    try:
        resp_inv = supabase.table("inventario_esd").select("*").limit(3000).execute()
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

        return df_inv, df_piso, df_mob, df_ion, df_em
        
    except Exception as e:
        st.error(f"Error conectando a la base de datos: {e}")
        return None, None, None, None, None


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

def subir_evidencia_storage(img_file, id_elemento):
    """Sube la imagen a Supabase Storage y retorna la URL pública."""
    if img_file is not None:
        try:
            img = Image.open(img_file)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            img.thumbnail((800, 800))
            
            buffered = io.BytesIO()
            img.save(buffered, format="JPEG", quality=75)
            img_bytes = buffered.getvalue()

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_name = f"{id_elemento}_{timestamp}.jpg"
            
            res = supabase.storage.from_("evidencias_esd").upload(
                file=img_bytes,
                path=file_name,
                file_options={"content-type": "image/jpeg"}
            )
            
            url = supabase.storage.from_("evidencias_esd").get_public_url(file_name)
            return url
        except Exception as e:
            st.error(f"Error subiendo imagen a la nube: {e}")
            return ""
    return ""

def safe_str(val, default="N/D"):
    val_str = str(val).strip()
    if pd.isna(val) or val_str.lower() in ['nan', 'none', 'null', '']:
        return default
    return val_str

def generar_html_reporte_esd(row, index):
    """Genera el HTML leyendo los datos de la fila de SQL."""
    med1 = safe_str(row.get('medicion_1', ''), '')
    med_extra = safe_str(row.get('mediciones_extra', ''), '')
    
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
    
    ref_raw = safe_str(row.get('limite_referencia'))
    try:
        ref_num = float(ref_raw)
        ref_str = f"{ref_num:.2E}"
    except:
        ref_str = ref_raw
        
    elemento = safe_str(row.get('elemento_s20_20', ''))
    metodo = INFO_ELEMENTOS_ESD.get(elemento, {}).get("metodo", "N/D")
    magnitud = INFO_ELEMENTOS_ESD.get(elemento, {}).get("magnitud", "")
    unidad = MAPA_UNIDADES.get(magnitud, "")
    
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
            <td class="p-1 border-r border-gray-300">{metodo}</td>
            <td class="p-1 border-r border-gray-300">{unidad}</td>
            <td class="p-1 border-r border-gray-300">N/A</td>
        </tr>
        """
        
    img_url = safe_str(row.get('imagen_url', ''))
    if img_url == 'N/D' or not img_url:
        img_tag = "<span class='text-gray-400 flex flex-col items-center'><br><br>Sin evidencia fotográfica</span>"
    else:
        img_tag = f'<img src="{img_url}" style="height: 190px; width: auto; max-width: 100%; object-fit: contain; margin: 0 auto;" />'
        
    fecha_raw = safe_str(row.get('fecha_auditoria'))
    fecha_ejecucion = fecha_raw.split('T')[0] if 'T' in fecha_raw else fecha_raw
    año_actual = datetime.today().strftime("%y")
    # --- NUEVO: EXTRAER ID REAL DE LA BASE DE DATOS ---
    db_id = row.get('id', index) # Intenta obtener la columna 'id', si falla usa el index como respaldo
    try:
        db_id = int(db_id)
    except:
        db_id = index
    # --------------------------------------------------
    
    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>BCS-PV-{db_id:03d}-{año_actual}</title>
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
                <div class="font-bold text-red-700 text-lg mb-2">Reporte: BCS-PV-{db_id:03d}-{año_actual}</div>
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
                        <tr class="border-b border-gray-300"><td class="w-1/3 font-bold bg-gray-100 p-1 border-r border-gray-300">ID:</td><td class="p-1">{safe_str(row.get('id_elemento'))}</td></tr>
                        <tr class="border-b border-gray-300"><td class="w-1/3 font-bold bg-gray-100 p-1 border-r border-gray-300">Elemento:</td><td class="p-1">{safe_str(row.get('elemento_s20_20'))}</td></tr>
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
                    <div class="p-2 text-sm">{safe_str(row.get('notas'), 'Sin observaciones adicionales.')}</div>
                    <div class="absolute bottom-2 right-2 text-lg font-bold text-gray-700">{safe_str(row.get('resultado'))}</div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>"""
    return html

# ==========================================
# SEGURIDAD Y ACCESO (SIN MURO DE LOGIN)
# ==========================================
token_actual = st.query_params.get("auth_token")

if token_actual and token_actual != "consulta_mode":
    token_decodificado = decodificar_sesion(token_actual)
    if token_decodificado:
        # Separamos el nombre del rol usando un separador especial "||"
        partes = token_decodificado.split("||")
        st.session_state.usuario_nombre = partes[0]
        st.session_state.rol_usuario = partes[1] if len(partes) > 1 else "Auditor"
        st.session_state.modo_lectura = False 
    else:
        st.session_state.usuario_nombre = "Usuario de Consulta"
        st.session_state.rol_usuario = "Consulta"
        st.session_state.modo_lectura = True
else:
    st.session_state.usuario_nombre = "Usuario de Consulta"
    st.session_state.rol_usuario = "Consulta"
    st.session_state.modo_lectura = True

# Al no haber muro, la aplicación principal se ejecuta SIEMPRE
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
        st.markdown("---")
        st.markdown("#### 🔒 Ingreso de Auditor")
        with st.form("login_form_sidebar"):
            user_input = st.text_input("Usuario (ID)")
            pwd_input = st.text_input("Contraseña", type="password")
            if st.form_submit_button("Ingresar", use_container_width=True):
                with st.spinner("Autenticando..."):
                    try:
                        # Consulta directa a Supabase para validar usuario
                        resp_user = supabase.table("usuarios_app").select("*").eq("usuario", user_input).execute()
                        
                        # --- NUEVO: VERIFICACIÓN CON HASH ---
                        if len(resp_user.data) > 0:
                            hash_guardado = resp_user.data[0]["password"]
                            
                            # La función check_password_hash hace la magia de comparar el texto con el hash de forma segura
                            if check_password_hash(hash_guardado, pwd_input):
                                nombre_real = resp_user.data[0]["nombre"]
                                rol_asignado = resp_user.data[0]["rol"]
                                
                                # Guardamos nombre y rol en el token
                                token_str = f"{nombre_real}||{rol_asignado}"
                                st.query_params["auth_token"] = codificar_sesion(token_str)
                                st.rerun()
                            else:
                                st.error("❌ Credenciales incorrectas")
                        else:
                            st.error("❌ Credenciales incorrectas")
                            
                    except Exception as e:
                        st.error(f"⚠️ Error al conectar con la base de usuarios: {e}")
    else:
        st.success(f"👤 Auditor: {st.session_state.usuario_nombre}")

        # --- MENÚ PARA CAMBIAR CONTRASEÑA ---
        with st.expander("🔑 Cambiar mi contraseña"):
            with st.form("form_cambiar_pwd"):
                pwd_actual = st.text_input("Contraseña actual", type="password")
                pwd_nueva = st.text_input("Nueva contraseña", type="password")
                pwd_conf = st.text_input("Confirmar nueva contraseña", type="password")
                
                if st.form_submit_button("Actualizar", use_container_width=True):
                    if not pwd_actual or not pwd_nueva or not pwd_conf:
                        st.error("⚠️ Completa todos los campos.")
                    elif pwd_nueva != pwd_conf:
                        st.error("❌ Las contraseñas nuevas no coinciden.")
                    else:
                        with st.spinner("Actualizando..."):
                            try:
                                # 1. Buscamos al usuario en la BD por su nombre de sesión
                                resp_actual = supabase.table("usuarios_app").select("id, password").eq("nombre", st.session_state.usuario_nombre).execute()
                                
                                if len(resp_actual.data) > 0:
                                    hash_guardado = resp_actual.data[0]["password"]
                                    id_user_db = resp_actual.data[0]["id"]
                                    
                                    # 2. Verificamos que la contraseña actual que ingresó sea correcta
                                    if check_password_hash(hash_guardado, pwd_actual):
                                        # 3. Generamos el nuevo hash y guardamos
                                        nuevo_hash = generate_password_hash(pwd_nueva)
                                        supabase.table("usuarios_app").update({"password": nuevo_hash}).eq("id", id_user_db).execute()
                                        st.success("✅ ¡Contraseña actualizada!")
                                    else:
                                        st.error("❌ La contraseña actual es incorrecta.")
                                else:
                                    st.error("❌ Error al ubicar tu usuario en la base de datos.")
                            except Exception as e:
                                st.error(f"Error de conexión: {e}")
        
        # --- MENÚ EXCLUSIVO PARA ADMINISTRADORES ---
        if st.session_state.rol_usuario == "Admin":
            st.divider()
            if st.button("⚙️ Ajustes y Usuarios", use_container_width=True, type="primary" if st.session_state.vista_actual == "Ajustes" else "secondary"):
                st.session_state.vista_actual = "Ajustes"
                limpiar_url_escaneo()
                st.rerun()

        if st.button("🚪 Cerrar Sesión", use_container_width=True):
            st.session_state.usuario_nombre = None
            st.session_state.modo_lectura = True
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

df_inv_full, df_piso_local, df_mob_local, df_ion_local, df_em_local = cargar_datos_cloud()

if df_inv_full is None:
    st.error("Falla al conectar con el servidor SQL.")
    st.stop()

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
    c_nav1, c_nav2, c_nav3, c_nav4, c_nav5, c_nav6, c_nav7, c_nav8, c_nav9 = st.columns(9)
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
    with c_nav7:
        if st.button("🏭 Maquinaria", use_container_width=True, type="primary" if st.session_state.vista_actual == "Maquinaria" else "secondary"):
            st.session_state.vista_actual = "Maquinaria"
            limpiar_url_escaneo()
            st.rerun()        
    with c_nav8:
        if st.button("📅 Programación", use_container_width=True, type="primary" if st.session_state.vista_actual == "Schedule" else "secondary"):
            st.session_state.vista_actual = "Schedule"
            limpiar_url_escaneo()
            st.rerun()
    with c_nav9:
        if st.button("🔌 Sensibilidad", use_container_width=True, type="primary" if st.session_state.vista_actual == "Sensibilidad" else "secondary"):
            st.session_state.vista_actual = "Sensibilidad"
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
        
        # Llamada directa al catálogo maestro de Supabase
        lineas_disponibles = obtener_catalogo_lineas()

        with st.form("form_alta_equipo"):
            col1, col2 = st.columns(2)
            nueva_linea = col1.selectbox("Línea (Ubicación)", options=lineas_disponibles)
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
                
                # --- NUEVA VERIFICACIÓN GLOBAL DE DUPLICADOS ---
                check_inv = supabase.table("inventario_esd").select("id_producto").eq("id_producto", id_limpio_alta).execute()
                check_maq = supabase.table("mediciones_maquinaria").select("id_maquinaria").eq("id_maquinaria", id_limpio_alta).execute()
                
                if len(check_inv.data) > 0 or len(check_maq.data) > 0:
                    st.error(f"❌ El ID '{nuevo_id}' ya se encuentra registrado en el sistema (Mobiliario, Ionizador o Maquinaria). Usa un ID diferente.")
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
                            
# --- SUB-VISTA 2: BAJA (CON ESCÁNER QR REACTIVO INDEPENDIENTE) ---
    elif accion_seleccionada == "🗑️ Dar de Baja":
        st.markdown("#### 🗑️ Desactivación de Activos ESD")
        
        if not id_baja_url:
            st.markdown("### 📷 Apunta al Código QR del Equipo a Dar de Baja")
            html_code_qr_baja = """
            <script src="https://unpkg.com/html5-qrcode"></script>
            <div id="reader_baja" style="width:100%; max-width:500px; margin:auto; border-radius:10px; overflow:hidden; border: 2px solid #dc3545; background-color: #f9f9f9;"></div>
            
            <div style="text-align:center; margin-top:10px; display:flex; justify-content:center; gap:5px; flex-wrap:wrap;">
                <button type="button" id="cam_wide_baja" style="padding:10px; background:#28a745; color:white; border:none; border-radius:5px; font-weight:bold; cursor:pointer;">📸 LENTE ESTÁNDAR</button>
                <button type="button" id="cam_cycle_baja" style="padding:10px; background:#555; color:white; border:none; border-radius:5px; font-weight:bold; cursor:pointer;">🔄 OTRA CÁMARA</button>
            </div>
            <div style="text-align:center; margin-top:10px; display:flex; justify-content:center; gap:5px;">
                <button type="button" id="zoom_1x_baja" style="padding:10px 20px; background:#dc3545; color:white; border:none; border-radius:5px; font-weight:bold; cursor:pointer;">🔍 1X (NORMAL)</button>
                <button type="button" id="zoom_3x_baja" style="padding:10px 20px; background:#666; color:white; border:none; border-radius:5px; font-weight:bold; cursor:pointer;">🔍 3X (CURVO)</button>
            </div>
            <p id="cam-status-baja" style="text-align:center; color:#666; font-size: 14px; margin-top: 10px;">Buscando cámaras...</p>
            
            <script>
            let html5QrCodeBaja;
            let rearCamsBaja = [];
            let currentIdxBaja = 0;
            let wideIdBaja = null;

            function applyZoomBaja(scale) {
                const vid = document.querySelector("#reader_baja video");
                if (vid) {
                    vid.style.transform = `scale(${scale})`;
                    vid.style.transformOrigin = "center center";
                }
                document.getElementById('zoom_1x_baja').style.background = (scale === 1) ? "#dc3545" : "#666";
                document.getElementById('zoom_3x_baja').style.background = (scale === 3) ? "#dc3545" : "#666";
            }

            function startScannerBaja(camId) {
                if(!html5QrCodeBaja) html5QrCodeBaja = new Html5Qrcode("reader_baja");
                if (html5QrCodeBaja.isScanning) {
                    html5QrCodeBaja.stop().then(() => { runScanBaja(camId); }).catch(e => console.log(e));
                } else {
                    runScanBaja(camId);
                }
            }

            function runScanBaja(camId) {
                html5QrCodeBaja.start(
                    camId, { fps: 15, qrbox: { width: 250, height: 250 }, aspectRatio: 1.0 },
                    (decodedText) => {
                        html5QrCodeBaja.stop();
                        const url = new URL(window.parent.location.href);
                        url.searchParams.set("qr_baja", decodedText);
                        window.parent.history.replaceState({}, "", url);
                        window.parent.location.reload();
                    }, (err) => {} 
                ).then(() => { 
                    let activeCam = rearCamsBaja.find(c => c.id === camId);
                    document.getElementById("cam-status-baja").innerText = "Lente activo: " + (activeCam ? activeCam.label : "Cámara");
                    applyZoomBaja(1);
                }).catch(err => {
                    document.getElementById("cam-status-baja").innerText = "Error iniciando lente. Intenta 'Otra Cámara'.";
                });
            }

            Html5Qrcode.getCameras().then(devices => {
                if (devices && devices.length) {
                    rearCamsBaja = devices.filter(c => c.label.toLowerCase().includes('back') || c.label.toLowerCase().includes('trasera') || c.label.toLowerCase().includes('environment'));
                    if(rearCamsBaja.length === 0) rearCamsBaja = devices;

                    wideIdBaja = rearCamsBaja[0].id;
                    for (let c of rearCamsBaja) {
                        let lbl = c.label.toLowerCase();
                        if (lbl.includes('wide') && !lbl.includes('ultra')) {
                            wideIdBaja = c.id; break;
                        }
                    }

                    currentIdxBaja = rearCamsBaja.findIndex(c => c.id === wideIdBaja);
                    if(currentIdxBaja === -1) currentIdxBaja = 0;

                    startScannerBaja(wideIdBaja);

                    document.getElementById('cam_wide_baja').addEventListener('click', () => {
                        currentIdxBaja = rearCamsBaja.findIndex(c => c.id === wideIdBaja);
                        startScannerBaja(wideIdBaja);
                    });

                    document.getElementById('cam_cycle_baja').addEventListener('click', () => {
                        currentIdxBaja = (currentIdxBaja + 1) % rearCamsBaja.length;
                        startScannerBaja(rearCamsBaja[currentIdxBaja].id);
                    });

                    document.getElementById('zoom_1x_baja').addEventListener('click', () => applyZoomBaja(1));
                    document.getElementById('zoom_3x_baja').addEventListener('click', () => applyZoomBaja(3));
                }
            }).catch(err => { document.getElementById("cam-status-baja").innerText = "Permisos de cámara denegados."; });
            </script>
            """
            components.html(html_code_qr_baja, height=750)
            
            id_manual_baja = st.text_input("O ingresa el ID manual para Baja:", key="input_manual_baja")
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
            
            # --- INICIO DE LÓGICA DE VISUALIZACIÓN Y BAJA SELECTIVA ---
            # 1. Buscar en inventario_esd (Mobiliario / Ionizadores)
            equipo_encontrado_inv = df_inv_full[df_inv_full['Id de producto'].astype(str).str.upper() == id_limpio_baja]
            
            # 2. Buscar en mediciones_maquinaria (Maquinaria)
            try:
                resp_maq_baja = supabase.table("mediciones_maquinaria").select("*").eq("id_maquinaria", id_limpio_baja).order("fecha_medicion", desc=True).limit(1).execute()
                df_maq_baja = pd.DataFrame(resp_maq_baja.data)
            except:
                df_maq_baja = pd.DataFrame()

            if not equipo_encontrado_inv.empty or not df_maq_baja.empty:
                st.markdown(f"### 📋 Detalles del Equipo a Dar de Baja: `{id_limpio_baja}`")
                st.info("Selecciona de qué catálogo deseas dar de baja este ID de forma independiente.")
                
                col_b1, col_b2 = st.columns(2)
                
                # Panel para Inventario (Mobiliario/Ionizadores)
                with col_b1:
                    if not equipo_encontrado_inv.empty:
                        info_eq = equipo_encontrado_inv.iloc[0]
                        st.markdown("#### 🛋️/⚡ Registro en Inventario")
                        st.metric("Clasificación", str(info_eq.get('Clasificación', 'N/D')))
                        st.metric("Estatus Actual", str(info_eq.get('Estatus operativo', 'N/D')))
                        
                        with st.form("form_baja_inv"):
                            if st.form_submit_button("🗑️ Dar de Baja en Inventario", use_container_width=True):
                                with st.spinner("Actualizando SQL..."):
                                    try:
                                        supabase.table("inventario_esd").update({
                                            "estatus_operativo": "NO OPERATIVO",
                                            "estatus_verificacion": "BAJA"
                                        }).eq("id_producto", id_limpio_baja).execute()
                                        st.success("✅ ¡Desactivado de Inventario!")
                                        st.cache_data.clear()
                                        limpiar_url_escaneo()
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Error: {e}")
                    else:
                        st.warning("No existe en el catálogo de Inventario.")
                        
                # Panel para Maquinaria
                with col_b2:
                    if not df_maq_baja.empty:
                        info_maq = df_maq_baja.iloc[0]
                        st.markdown("#### 🏭 Registro en Maquinaria")
                        st.metric("Clasificación", str(info_maq.get('clasificacion', 'N/D')))
                        st.metric("Estatus Actual", str(info_maq.get('status_operativo', 'N/D')))
                        
                        with st.form("form_baja_maq"):
                            # Botón principal en rojo/destacado para maquinaria
                            if st.form_submit_button("🗑️ Dar de Baja en Maquinaria", type="primary", use_container_width=True):
                                with st.spinner("Actualizando SQL..."):
                                    try:
                                        supabase.table("mediciones_maquinaria").update({
                                            "status_operativo": "NO OPERATIVO",
                                            "resultado_estatus": "BAJA"
                                        }).eq("id_maquinaria", id_limpio_baja).execute()
                                        st.success("✅ ¡Desactivado de Maquinaria!")
                                        st.cache_data.clear()
                                        limpiar_url_escaneo()
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Error: {e}")
                    else:
                        st.warning("No existe en el registro de Maquinaria.")

            else:
                st.error(f"❌ No se encontró ningún registro con el ID: {id_limpio_baja}")
                if st.button("🔄 Volver a intentar", use_container_width=True):
                    limpiar_url_escaneo()
                    st.rerun()
            # --- FIN DE LÓGICA SELECTIVA ---
# ==========================================
# VISTA 1: MAPA Y REPORTES ESD
# ==========================================
elif st.session_state.vista_actual == "Mapa" and not st.session_state.modo_lectura:
    st.markdown("### Mapa y Cumplimiento ESD")
    tab_mapa, tab_overview = st.tabs(["📍 Mapa Físico", "📊 Overview (S20.20)"])

    with tab_mapa:
        tipo_mapa = st.radio("Ver en mapa:", ["Mobiliario", "Ionizadores", "Maquinaria"], horizontal=True)
        
        if tipo_mapa == "Mobiliario":
            df_total = df_mob_local.copy()
        elif tipo_mapa == "Ionizadores":
            df_total = df_ion_local.copy()
        else:
            # --- NUEVA LÓGICA: EXTRAER MAQUINARIA ---
            try:
                # Traemos datos ordenados por fecha para que el más reciente quede arriba
                resp_maq_mapa = supabase.table("mediciones_maquinaria").select("*").order("fecha_medicion", desc=True).execute()
                df_maq_mapa = pd.DataFrame(resp_maq_mapa.data)
                if not df_maq_mapa.empty:
                    # Eliminamos duplicados históricos conservando solo el último registro
                    df_maq_mapa = df_maq_mapa.drop_duplicates(subset=['id_maquinaria'], keep='first')
                    
                    # Homologamos las columnas para que el código del mapa las entienda
                    df_total = df_maq_mapa.rename(columns={
                        'status_operativo': 'Estatus operativo',
                        'resultado_estatus': 'Estatus de verificación',
                        'linea_ubicacion': 'Línea',
                        'id_maquinaria': 'Id de producto',
                        'clasificacion': 'Clasificación'
                    })
                else:
                    df_total = pd.DataFrame()
            except:
                df_total = pd.DataFrame()
        
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
                
                # Determinamos el prefijo para la etiqueta (M = Mobiliario, I = Ionizador, MQ = Maquinaria)
                if tipo_mapa == "Mobiliario":
                    prefijo = "M: "
                elif tipo_mapa == "Ionizadores":
                    prefijo = "I: "
                else:
                    prefijo = "MQ: "
                    
                conteo_tipos['Etiqueta'] = prefijo + conteo_tipos['Total Vencidos'].astype(str)
            
                if os.path.exists(RUTA_MAPA) and os.path.exists(RUTA_COORDENADAS):
                    img = Image.open(RUTA_MAPA)
                    width, height = img.size # Obtenemos el tamaño real de la imagen
                    df_coords = pd.read_csv(RUTA_COORDENADAS)
                    mapa_data = pd.merge(conteo_tipos, df_coords, on='Línea', how='inner')
                    
                    if not mapa_data.empty:
                        fig = px.scatter(
                            mapa_data, x="X", y="Y", color="Total Vencidos", text="Etiqueta",
                            hover_data={"X": False, "Y": False, "Etiqueta": False, "Total Vencidos": True},
                            color_continuous_scale="Reds"
                        )
                        
                        # --- DISEÑO DE LOS PUNTOS ---
                        fig.update_traces(
                            textposition='middle center', 
                            textfont=dict(color='white', size=14, weight='bold'), 
                            marker=dict(symbol='circle', size=45, opacity=0.9, line=dict(width=2, color='black'))
                        )
                        
                        # --- CÁLCULO DE PROPORCIÓN PARA EVITAR ESTIRAMIENTO ---
                        aspect_ratio = height / width
                        plot_height = int(1000 * aspect_ratio) # 1000px es el ancho base de uso de Streamlit

                        fig.update_layout(
                            height=plot_height,
                            images=[dict(
                                source=img, xref="x", yref="y", 
                                x=0, y=0, sizex=width, sizey=height, 
                                sizing="stretch", opacity=1, layer="below"
                            )], 
                            xaxis=dict(visible=False, range=[0, width]), 
                            # scaleanchor="x" y scaleratio=1 son la magia que bloquea la proporción
                            yaxis=dict(visible=False, range=[height, 0], scaleanchor="x", scaleratio=1), 
                            margin=dict(l=0, r=0, t=0, b=0),
                            coloraxis_showscale=False
                        )
                        st.plotly_chart(fig, use_container_width=True)
                st.dataframe(vencidos[['Línea', 'Id de producto', 'Clasificación', 'Estatus de verificación']], use_container_width=True, hide_index=True)
            else:
                st.success(f"✅ **100% Cumplimiento en {tipo_mapa}.**")

    with tab_overview:
        st.markdown("#### Estado Global de Elementos ESD")
        try:
            resp_inv2 = supabase.table("inventario_esd").select("id_producto, clasificacion, linea_ubicacion, estatus_verificacion, fecha_proxima_verif").limit(3000).execute()
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
        html_code_qr = """
        <script src="https://unpkg.com/html5-qrcode"></script>
        <div id="reader_main" style="width:100%; max-width:500px; margin:auto; border-radius:10px; overflow:hidden; border: 2px solid #0052cc; background-color: #f9f9f9;"></div>
        
        <div style="text-align:center; margin-top:10px; display:flex; justify-content:center; gap:5px; flex-wrap:wrap;">
            <button type="button" id="cam_wide_main" style="padding:10px; background:#28a745; color:white; border:none; border-radius:5px; font-weight:bold; cursor:pointer;">📸 LENTE ESTÁNDAR</button>
            <button type="button" id="cam_cycle_main" style="padding:10px; background:#555; color:white; border:none; border-radius:5px; font-weight:bold; cursor:pointer;">🔄 OTRA CÁMARA</button>
        </div>
        <div style="text-align:center; margin-top:10px; display:flex; justify-content:center; gap:5px;">
            <button type="button" id="zoom_1x_main" style="padding:10px 20px; background:#0052cc; color:white; border:none; border-radius:5px; font-weight:bold; cursor:pointer;">🔍 1X (NORMAL)</button>
            <button type="button" id="zoom_3x_main" style="padding:10px 20px; background:#666; color:white; border:none; border-radius:5px; font-weight:bold; cursor:pointer;">🔍 3X (CURVO)</button>
        </div>
        <p id="cam-status-main" style="text-align:center; color:#666; font-size: 14px; margin-top: 10px;">Buscando cámaras...</p>
        
        <script>
        let html5QrCodeMain;
        let rearCamsMain = [];
        let currentIdxMain = 0;
        let wideIdMain = null;

        function applyZoomMain(scale) {
            const vid = document.querySelector("#reader_main video");
            if (vid) {
                vid.style.transform = `scale(${scale})`;
                vid.style.transformOrigin = "center center";
            }
            document.getElementById('zoom_1x_main').style.background = (scale === 1) ? "#0052cc" : "#666";
            document.getElementById('zoom_3x_main').style.background = (scale === 3) ? "#0052cc" : "#666";
        }

        function startScannerMain(camId) {
            if(!html5QrCodeMain) html5QrCodeMain = new Html5Qrcode("reader_main");
            if (html5QrCodeMain.isScanning) {
                html5QrCodeMain.stop().then(() => { runScanMain(camId); }).catch(e => console.log(e));
            } else {
                runScanMain(camId);
            }
        }

        function runScanMain(camId) {
            html5QrCodeMain.start(
                camId, { fps: 15, qrbox: { width: 250, height: 250 }, aspectRatio: 1.0 },
                (decodedText) => {
                    html5QrCodeMain.stop();
                    const url = new URL(window.parent.location.href);
                    url.searchParams.set("qr_id", decodedText);
                    window.parent.history.replaceState({}, "", url);
                    window.parent.location.reload();
                }, (err) => {} 
            ).then(() => { 
                let activeCam = rearCamsMain.find(c => c.id === camId);
                document.getElementById("cam-status-main").innerText = "Lente activo: " + (activeCam ? activeCam.label : "Cámara");
                applyZoomMain(1);
            }).catch(err => {
                document.getElementById("cam-status-main").innerText = "Error iniciando lente. Intenta 'Otra Cámara'.";
            });
        }

        Html5Qrcode.getCameras().then(devices => {
            if (devices && devices.length) {
                rearCamsMain = devices.filter(c => c.label.toLowerCase().includes('back') || c.label.toLowerCase().includes('trasera') || c.label.toLowerCase().includes('environment'));
                if(rearCamsMain.length === 0) rearCamsMain = devices;

                wideIdMain = rearCamsMain[0].id;
                for (let c of rearCamsMain) {
                    let lbl = c.label.toLowerCase();
                    if (lbl.includes('wide') && !lbl.includes('ultra')) {
                        wideIdMain = c.id; break;
                    }
                }

                currentIdxMain = rearCamsMain.findIndex(c => c.id === wideIdMain);
                if(currentIdxMain === -1) currentIdxMain = 0;

                startScannerMain(wideIdMain);

                document.getElementById('cam_wide_main').addEventListener('click', () => {
                    currentIdxMain = rearCamsMain.findIndex(c => c.id === wideIdMain);
                    startScannerMain(wideIdMain);
                });

                document.getElementById('cam_cycle_main').addEventListener('click', () => {
                    currentIdxMain = (currentIdxMain + 1) % rearCamsMain.length;
                    startScannerMain(rearCamsMain[currentIdxMain].id);
                });

                document.getElementById('zoom_1x_main').addEventListener('click', () => applyZoomMain(1));
                document.getElementById('zoom_3x_main').addEventListener('click', () => applyZoomMain(3));
            }
        }).catch(err => { document.getElementById("cam-status-main").innerText = "Permisos de cámara denegados."; });
        </script>
        """
        components.html(html_code_qr, height=750) 
        
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

        # --- NUEVO: Búsqueda en tabla de Maquinaria ---
        try:
            resp_maq_scan = supabase.table("mediciones_maquinaria").select("*").eq("id_maquinaria", id_limpio).order("fecha_medicion", desc=True).execute()
            df_maq_scan = pd.DataFrame(resp_maq_scan.data)
            es_maq = not df_maq_scan.empty
        except:
            df_maq_scan = pd.DataFrame()
            es_maq = False
        # ----------------------------------------------

        es_mob = id_limpio in mob_ids_limpios.values
        es_ion = id_limpio in ion_ids_limpios.values

        if es_mob or es_ion or es_maq:
            
            # ==========================================
            # LÓGICA DE VISUALIZACIÓN: MOBILIARIO / IONIZADORES
            # ==========================================
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
                clasificacion_equipo = str(equipo.get('Clasificación', 'N/A'))
                c_tipo.metric("Clasificación", clasificacion_equipo)
                c_estatus.metric("Estatus", str(equipo.get('Estatus de verificación', 'N/A')))
                
                c_val, c_bal = st.columns(2)
                val_previo = equipo.get('Valor de verificación', 0)
                if es_ion:
                    c_val.metric("Descarga", f"{float(val_previo):.2f} s" if pd.notna(val_previo) else "N/A")
                    
                    # --- NUEVO: FORMATEO DEL BALANCE CON UNIDAD DE VOLTS ---
                    bal_previo = equipo.get('Balance')
                    if pd.notna(bal_previo) and str(bal_previo).strip() not in ['', 'N/A', 'nan', 'None']:
                        c_bal.metric("Balance", f"{float(bal_previo):.2f} V")
                    else:
                        c_bal.metric("Balance", "N/A")
                    # -------------------------------------------------------
                else:
                    c_val.metric("Resistencia", f"{float(val_previo):.2E} Ω" if pd.notna(val_previo) else "N/A")

                try:
                    resp_fechas = supabase.table("inventario_esd").select("fecha_ultima_verif, fecha_proxima_verif").eq("id_producto", id_limpio).execute()
                    if resp_fechas.data:
                        f_val_sql = resp_fechas.data[0].get('fecha_ultima_verif', 'N/A')
                        f_venc_sql = resp_fechas.data[0].get('fecha_proxima_verif', 'N/A')
                    else:
                        f_val_sql, f_venc_sql = "N/A", "N/A"
                except Exception as e:
                    f_val_sql, f_venc_sql = "Error", "Error"

                c_fval, c_fvenc = st.columns(2)
                c_fval.metric("Fecha de Validación", str(f_val_sql)[:10] if f_val_sql != "N/A" else "N/A")
                c_fvenc.metric("Fecha de Vencimiento", str(f_venc_sql)[:10] if f_venc_sql != "N/A" else "N/A")
                
                with st.expander("🕰️ Consultar Historial de Mediciones Anteriores"):
                    try:
                        resp_hist = supabase.table("historial_mediciones").select("*").eq("id_equipo", id_limpio).order("fecha_modificacion", desc=True).execute()
                        df_historial = pd.DataFrame(resp_hist.data)
                        if not df_historial.empty:
                            if es_ion and 'balance_ionizador' in df_historial.columns:
                                df_historial = df_historial[['fecha_modificacion', 'valor_actual', 'balance_ionizador', 'fecha_validacion', 'ubicacion', 'auditor']]
                                df_historial.columns = ['Actualizado el', 'T. Descarga (s)', 'Balance (V)', 'Fecha Val.', 'Ubicación', 'Auditor']
                            else:
                                df_historial = df_historial[['fecha_modificacion', 'valor_actual', 'fecha_validacion', 'ubicacion', 'auditor']]
                                df_historial.columns = ['Actualizado el', 'Valor', 'Fecha Val.', 'Ubicación', 'Auditor']
                            
                            st.dataframe(df_historial, use_container_width=True, hide_index=True)
                        else:
                            st.info("No hay mediciones históricas registradas para este equipo aún.")
                    except Exception as e:
                        st.error(f"Error al cargar el historial: {e}")

                st.divider()

                if not st.session_state.modo_lectura:
                    hacer_medicion = st.checkbox(texto_check)
                    if hacer_medicion:
                        with st.form("form_actualizacion"):
                            st.text_input("Clasificación (Tipo de Equipo)", value=clasificacion_equipo, disabled=True)
                            
                            # --- 1. LÍNEA POR DEFECTO ASEGURADA ---
                            if 'obtener_catalogo_lineas' in globals():
                                lineas_opc = obtener_catalogo_lineas()
                            else:
                                lineas_opc = sorted([str(x).strip() for x in df_mob_local['Línea'].dropna().unique()])
                                
                            ub_actual = str(equipo.get('Línea', '')).strip()
                            
                            # Si la ubicación actual no está en la lista del catálogo, la inyectamos para no perder la referencia visual
                            if ub_actual and ub_actual not in lineas_opc:
                                lineas_opc = [ub_actual] + lineas_opc
                                
                            idx_l = lineas_opc.index(ub_actual) if ub_actual in lineas_opc else 0
                            nueva_linea_upd = st.selectbox("Línea / Ubicación", options=lineas_opc, index=idx_l)
                            
                            # --- 2. CAMPOS VACÍOS (value=None) ---
                            if es_ion:
                                c_ion1, c_ion2 = st.columns(2)
                                v_act = c_ion1.number_input("Descarga (s)", value=None, format="%.2f", placeholder="0.0")
                                bal_act = c_ion2.number_input("Balance (V)", value=None, format="%.2f", placeholder="0.0")
                            else:
                                c_b, c_e = st.columns(2)
                                base_upd = c_b.number_input("Base (Ohms)", value=None, placeholder="Ej: 3.5")
                                exp_upd = c_e.number_input("Exponente", value=None, step=1, placeholder="Ej: 6")
                                
                            fecha_hoy = datetime.today().date()
                            nueva_fecha = st.date_input("Fecha de Validación", fecha_hoy)
                            
                            if st.form_submit_button("💾 Guardar Actualización e Historial"):
                                # --- 3. VALIDACIÓN DE CAMPOS ---
                                # Como los campos inician vacíos (None), debemos evitar que el programa truene si le dan a Guardar accidentalmente.
                                if es_ion and (v_act is None or bal_act is None):
                                    st.error("⚠️ Debes ingresar los valores de Descarga y Balance.")
                                elif not es_ion and (base_upd is None or exp_upd is None):
                                    st.error("⚠️ Debes ingresar los valores de Base y Exponente.")
                                else:
                                    with st.spinner("Guardando registro..."):
                                        if es_ion:
                                            nuevo_valor_final = float(v_act)
                                            bal_act = float(bal_act)
                                        else:
                                            nuevo_valor_final = float(base_upd) * (10 ** int(exp_upd))
                                            bal_act = None
                                            
                                        freq = str(equipo.get('Frecuencia de verificación', 'Anual'))
                                        proxy = calcular_proxima_fecha(nueva_fecha, freq)
                                        
                                        try:
                                            # --- 4. GUARDAR EL ESTADO ANTERIOR EN LA TABLA HISTORIAL ---
                                            # Extraemos los valores previos que ya tenemos cargados de la BD
                                            val_previo_hist = str(equipo.get('Valor de verificación', 0))
                                            ubicacion_previa = str(equipo.get('Línea', 'N/D'))
                                            auditor_previo = str(equipo.get('Auditor', st.session_state.usuario_nombre))
                                            
                                            # Solo guardamos en el historial si realmente existía una medición anterior (evita guardar registros vacíos/nuevos)
                                            if f_val_sql != 'N/A' and f_val_sql != 'Error':
                                                historial_data = {
                                                    "id_equipo": id_limpio,
                                                    "tipo_equipo": clasificacion_equipo,
                                                    "ubicacion": ubicacion_previa,
                                                    "valor_actual": val_previo_hist,
                                                    "fecha_validacion": f_val_sql, # <--- FECHA ANTERIOR
                                                    "fecha_vencimiento": f_venc_sql if f_venc_sql != 'N/A' else None,
                                                    "auditor": auditor_previo, # <--- AUDITOR ANTERIOR
                                                    "fecha_modificacion": datetime.now().isoformat() # <--- Cuándo se archivó
                                                }
                                                if es_ion:
                                                    historial_data["balance_ionizador"] = str(equipo.get('Balance', 0))
                                                    
                                                supabase.table("historial_mediciones").insert(historial_data).execute()

                                            # --- 5. ACTUALIZAR EL ESTADO NUEVO EN INVENTARIO MAESTRO ---
                                            update_data = {
                                                "linea_ubicacion": nueva_linea_upd,
                                                "valor_actual": float(nuevo_valor_final),
                                                "fecha_ultima_verif": nueva_fecha.isoformat(), # <--- FECHA NUEVA (HOY)
                                                "fecha_proxima_verif": proxy.isoformat(),
                                                "estatus_verificacion": "VIGENTE",
                                                "estatus_operativo": "OPERATIVO",
                                                "auditor_responsable": st.session_state.usuario_nombre, # <--- AUDITOR NUEVO (TÚ)
                                            }
                                            if es_ion:
                                                update_data["balance_ionizador"] = float(bal_act)
                                            
                                            supabase.table("inventario_esd").update(update_data).eq("id_producto", id_limpio).execute()
                                            
                                            st.success("💾 ¡Equipo actualizado y medición anterior archivada en el historial!")
                                            st.cache_data.clear()
                                            limpiar_url_escaneo()
                                            st.rerun()
                                        except Exception as e:
                                            st.error(f"Error actualizando el equipo en SQL: {e}")
                # --- NUEVO: LISTADO DE OTROS EQUIPOS EN LA MISMA LÍNEA ---
                if es_mob:
                    ub_actual_lista = str(equipo.get('Línea', '')).strip()
                    if ub_actual_lista and ub_actual_lista != 'N/A' and 'df_inv_full' in locals() and not df_inv_full.empty:
                        st.divider()
                        st.markdown(f"#### 📍 Otros equipos en la línea: `{ub_actual_lista}`")
                        
                        # Filtramos el inventario por la misma línea, quitamos el equipo actual y los que estén dados de baja
                        df_otros = df_inv_full[
                            (df_inv_full['Línea'].astype(str).str.strip() == ub_actual_lista) & 
                            (df_inv_full['Id de producto'].astype(str).str.strip().str.upper() != id_limpio) &
                            (df_inv_full['Estatus operativo'].astype(str).str.strip().str.upper() != 'NO OPERATIVO')
                        ]
                        
                        if not df_otros.empty:
                            # Seleccionamos columnas clave para mostrar
                            df_mostrar_otros = df_otros[['Id de producto', 'Clasificación', 'Estatus de verificación', 'Fecha de próxima verificación']].copy()
                            df_mostrar_otros = df_mostrar_otros.rename(columns={
                                'Id de producto': 'ID Equipo', 
                                'Fecha de próxima verificación': 'Vencimiento'
                            })
                            
                            # Formateamos la fecha visualmente para que sea corta
                            df_mostrar_otros['Vencimiento'] = pd.to_datetime(df_mostrar_otros['Vencimiento'], errors='coerce').dt.strftime('%d-%b-%Y').fillna('N/D')
                            
                            # Agregamos emojis de estatus rápido
                            def emoji_estatus(val):
                                v = str(val).upper()
                                if 'VIGENTE' in v: return f"🟢 {val}"
                                if 'VENCIDO' in v: return f"🔴 {val}"
                                return f"🟡 {val}"
                                
                            df_mostrar_otros['Estatus de verificación'] = df_mostrar_otros['Estatus de verificación'].apply(emoji_estatus)
                            
                            st.dataframe(df_mostrar_otros, use_container_width=True, hide_index=True)
                        else:
                            st.info("No hay otros equipos operativos registrados en esta línea.")
                # ---------------------------------------------------------
            # ==========================================
            # LÓGICA DE VISUALIZACIÓN: MAQUINARIA
            # ==========================================
            elif es_maq:
                equipo = df_maq_scan.iloc[0]
                
                st.markdown(f"### 🏭 Detalles de la Maquinaria")
                c_linea, c_tipo, c_estatus = st.columns(3)
                c_linea.metric("Ubicación", str(equipo.get('linea_ubicacion', 'N/A')))
                clasificacion_equipo = str(equipo.get('clasificacion', 'N/A'))
                c_tipo.metric("Clasificación", clasificacion_equipo)
                c_estatus.metric("Estatus", str(equipo.get('resultado_estatus', 'N/A')))
                
                c_val, c_bal = st.columns(2)
                res_tierra = equipo.get('resistencia_tierra')
                c_val.metric("Resistencia a Tierra", f"{float(res_tierra):.2E} Ω" if pd.notna(res_tierra) and res_tierra else "N/D")
                campo_est = equipo.get('campo_estatico_voltaje')
                c_bal.metric("Campo Estático", f"{float(campo_est):.1f} V" if pd.notna(campo_est) else "N/D")

                f_val_sql = str(equipo.get('fecha_medicion', 'N/A'))[:10]
                f_venc_sql = str(equipo.get('fecha_proxima', 'N/A'))[:10]
                
                c_fval, c_fvenc = st.columns(2)
                c_fval.metric("Fecha de Validación", f_val_sql)
                c_fvenc.metric("Fecha de Vencimiento", f_venc_sql)
                
                with st.expander("🕰️ Consultar Historial de Mediciones Anteriores"):
                    df_maq_hist = df_maq_scan[['fecha_medicion', 'resistencia_tierra', 'campo_estatico_voltaje', 'tomacorriente_estatus', 'resultado_estatus', 'auditor']].copy()
                    df_maq_hist.columns = ['Fecha', 'Resistencia (Ω)', 'Campo (V)', 'Toma', 'Estatus', 'Auditor']
                    
                    def formatear_res_hist(val):
                        try:
                            v = float(val)
                            return f"{v:.2f}" if v < 10 else f"{v:.2E}"
                        except:
                            return "N/D"
                            
                    if 'Resistencia (Ω)' in df_maq_hist.columns:
                        df_maq_hist['Resistencia (Ω)'] = df_maq_hist['Resistencia (Ω)'].apply(formatear_res_hist)
                        
                    df_maq_hist['Fecha'] = pd.to_datetime(df_maq_hist['Fecha']).dt.strftime('%d-%b-%Y')
                    st.dataframe(df_maq_hist.fillna("N/D"), use_container_width=True, hide_index=True)

                st.divider()

                if not st.session_state.modo_lectura:
                    st.info("💡 Para registrar una nueva validación, utiliza el módulo de maquinaria.")
                    if st.button("🏭 Ir al Módulo de Maquinaria", use_container_width=True):
                        st.session_state.vista_actual = "Maquinaria"
                        limpiar_url_escaneo()
                        st.rerun()

        else:
            st.error("❌ El ID no se encontró en la base de datos (Mobiliario, Ionizadores o Maquinaria).")
# ==========================================
# VISTA 3: EVENT METER
# ==========================================
elif st.session_state.vista_actual == "Event Meter" and not st.session_state.modo_lectura:
    st.markdown("### ⚡ Estudio de Event Meter (PCBA)")
    st.info("Mide descargas electrostáticas y transitorios durante la operación normal de la maquinaria/proceso.")

    # --- SECCIÓN: GENERADOR DE REPORTE POR LÍNEA (ESTILO WALKING TEST) ---
    with st.expander("📄 Generar Reporte Oficial por Línea (Estilo Walking Test)", expanded=False):
        st.write("Selecciona una línea para consolidar todas sus operaciones guardadas en la base de datos en un único reporte oficial.")
        
        lineas_reporte = []
        if df_em_local is not None and not df_em_local.empty and 'Línea' in df_em_local.columns:
            lineas_reporte = sorted([str(x).strip() for x in df_em_local['Línea'].dropna().unique() if str(x).strip() != ''])
        
        if not lineas_reporte:
            st.warning("⚠️ No hay registros históricos en 'event_meter' para generar reportes consolidados.")
        else:
            linea_rep_sel = st.selectbox("Seleccionar Línea para el Reporte Consolidado:", options=lineas_reporte, key="em_linea_rep_sel")
            
            with st.form("form_reporte_em_consolidado"):
                st.markdown("#### Datos Generales del Estudio")
                col_g1, col_g2 = st.columns(2)
                auditor_em = col_g1.text_input("Auditor / Técnico", value=st.session_state.usuario_nombre if st.session_state.usuario_nombre else "")
                periodo_em = col_g2.selectbox("Periodo de Evaluación", ["Semestre 1", "Semestre 2", "Evaluación Anual"])
                
                col_g3, col_g4 = st.columns(2)
                equipo_em = col_g3.text_input("Equipo de Medición Utilizado", value="SCS EM EYE")
                serial_em = col_g4.text_input("No. de Serie del Equipo", value="2451005")
                
                submit_reporte_em = st.form_submit_button("Generar Reporte Consolidado por Línea", use_container_width=True)
                
                if submit_reporte_em:
                    df_filtrado = df_em_local[df_em_local['Línea'].astype(str).str.strip() == linea_rep_sel].copy()
                    
                    if df_filtrado.empty:
                        st.error("No se encontraron registros en la base de datos para la línea seleccionada.")
                    else:
                        html_rows = ""
                        for i, row in enumerate(df_filtrado.to_dict('records'), 1):
                            op = str(row.get('Id de Operación', 'N/A'))
                            tipo_c = str(row.get('Tipo de contacto', 'N/D'))
                            
                            # --- EXTRACCIÓN SEGURA DE NÚMEROS ---
                            raw_eventos = row.get('Detección (Cantidad)', 0)
                            eventos = int(float(raw_eventos)) if pd.notna(raw_eventos) and str(raw_eventos).strip() != '' else 0
                            
                            raw_vmax = row.get('Voltaje máximo', 0.0)
                            vmax = float(raw_vmax) if pd.notna(raw_vmax) and str(raw_vmax).strip() != '' else 0.0
                            # ------------------------------------
                            
                            estatus = str(row.get('Estatus de verificación', '')).upper()
                            notas = str(row.get('Notas', ''))
                            if notas.lower() in ['nan', 'none', 'null']: 
                                notas = ""
                            
                            color_estatus = "text-green-600" if "APROBADO" in estatus else "text-red-600"
                            pass_fail = "PASA" if "APROBADO" in estatus else "FALLA"
                            
                            html_rows += f"""
                            <tr class="text-center border-b border-gray-300">
                                <td class="border border-gray-800 p-2 font-bold text-gray-600">{i}</td>
                                <td class="border border-gray-800 p-2 text-left">{op}</td>
                                <td class="border border-gray-800 p-2">{tipo_c}</td>
                                <td class="border border-gray-800 p-2 font-mono">{eventos}</td>
                                <td class="border border-gray-800 p-2 font-mono font-bold">{vmax}V</td>
                                <td class="border border-gray-800 p-2 font-bold {color_estatus}">{pass_fail}</td>
                                <td class="border border-gray-800 p-2 text-left text-xs">{notas}</td>
                            </tr>
                            """
                        
                        fecha_hoy_str = datetime.today().strftime("%Y-%m-%d")
                        fecha_pie_str = datetime.today().strftime("%Y/%m/%d")
                        
                        # --- PLANTILLA HTML OFICIAL SIN OPERADOR DE PRUEBA ---
                        html_template = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Reporte Event Meter - {linea_rep_sel}</title>
<script src="https://cdn.tailwindcss.com"></script>
<style>
    @media print {{
        body {{ background-color: white; padding: 0; }}
        .no-print {{ display: none !important; }}
        .print-border {{ border: 1px solid #000; }}
        .shadow-lg {{ box-shadow: none; }}
    }}
</style>
</head>
<body class="bg-gray-100 p-4 md:p-8 text-gray-800 font-sans">
<div class="max-w-5xl mx-auto bg-white p-8 shadow-lg print:shadow-none print:w-full">
    <div class="flex justify-end space-x-4 mb-6 no-print">
        <button onclick="window.print()" class="bg-gray-800 text-white px-4 py-2 rounded shadow hover:bg-gray-900 transition flex items-center font-bold">
            🖨️ Imprimir / Guardar PDF
        </button>
    </div>
    
    <div class="border-2 border-gray-800 mb-6 flex flex-col md:flex-row text-sm print-border">
        <div class="p-4 border-b-2 md:border-b-0 md:border-r-2 border-gray-800 flex items-center justify-center w-full md:w-1/4">
            <img src="https://github.com/aldoaoa/Visualizador-BCS-IDS/blob/main/BCS%20LOGO.png?raw=true" alt="Logo BCS" class="max-h-20 object-contain">
        </div>
        <div class="p-4 flex-1 border-b-2 md:border-b-0 md:border-r-2 border-gray-800 text-center flex flex-col justify-center">
            <h1 class="text-lg font-bold uppercase">Registro de Estudio de Eventos ESD (Event Meter)</h1>
            <p class="text-gray-600 font-semibold">Norma de Referencia: ANSI/ESD S20.20</p>
        </div>
        <div class="p-2 w-full md:w-1/4 flex flex-col justify-center text-xs space-y-1">
            <div class="flex justify-between"><span class="font-bold">Código:</span> <span>F-ESD-001</span></div>
            <div class="flex justify-between"><span class="font-bold">Límite Permitido:</span> <span class="font-bold text-red-600">&lt; 100V</span></div>
        </div>
    </div>
    
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6 text-sm">
        <div class="space-y-2">
            <div class="flex justify-between border-b pb-1"><span class="font-bold">Fecha de Estudio:</span><span>{fecha_hoy_str}</span></div>
            <div class="flex justify-between border-b pb-1"><span class="font-bold">Línea / Área Evaluada:</span><span>{linea_rep_sel}</span></div>
            <div class="flex justify-between border-b pb-1"><span class="font-bold">Auditor / Técnico:</span><span>{auditor_em}</span></div>
        </div>
        <div class="space-y-2">
            <div class="flex justify-between border-b pb-1"><span class="font-bold">Periodo de Evaluación:</span><span>{periodo_em}</span></div>
            <div class="flex justify-between border-b pb-1"><span class="font-bold">Equipo de Medición (SN):</span><span>{equipo_em} ({serial_em})</span></div>
        </div>
    </div>
    
    <div class="overflow-x-auto mb-8">
        <table class="w-full text-sm border-collapse border border-gray-800 print-border">
            <thead>
                <tr class="bg-gray-200 text-center">
                    <th class="border border-gray-800 p-2 w-10">No.</th>
                    <th class="border border-gray-800 p-2 text-left">Operación / Estación</th>
                    <th class="border border-gray-800 p-2">Tipo de Contacto</th>
                    <th class="border border-gray-800 p-2 w-24">Eventos</th>
                    <th class="border border-gray-800 p-2 w-24">Voltaje Máx.</th>
                    <th class="border border-gray-800 p-2 w-24">Resultado</th>
                    <th class="border border-gray-800 p-2 text-left">Observaciones</th>
                </tr>
            </thead>
            <tbody>
                {html_rows}
            </tbody>
        </table>
    </div>
    
    <div class="grid grid-cols-2 gap-8 mt-12 text-sm text-center">
        <div><div class="border-b border-gray-800 w-3/4 mx-auto mb-2 h-8"></div><p class="font-bold">Realizado por: {auditor_em}</p></div>
        <div><div class="border-b border-gray-800 w-3/4 mx-auto mb-2 h-8"></div><p class="font-bold">Revisado / Aprobado por: Coordinador ESD</p></div>
    </div>

    <div class="border-t-[3px] border-b-[3px] border-black mt-16 py-1 text-[11px] font-sans">
        <div class="flex justify-between items-end">
            <div class="text-left leading-tight">
                <div>E_310_4_111_QRO_SP_Rev.A</div>
                <div>Registro de estudio de eventos ESD.</div>
            </div>
            <div class="text-center leading-tight">
                <div>Fecha:{fecha_pie_str}</div>
            </div>
            <div class="text-right leading-tight">
                <div>Ref.E_310_3_001_QRO_SP</div>
            </div>
        </div>
    </div>
</div>
</body>
</html>"""
                        b64_html = base64.b64encode(html_template.encode('utf-8')).decode('utf-8')
                        nombre_archivo = f"Reporte_Consolidado_EventMeter_{linea_rep_sel.replace(' ', '_')}.html"
                        
                        st.success(f"✅ ¡Reporte consolidado para la línea {linea_rep_sel} generado con éxito!")
                        href = f'<a href="data:text/html;base64,{b64_html}" download="{nombre_archivo}" target="_blank" style="display: block; text-align: center; padding: 15px; background-color: #003366; color: white; text-decoration: none; border-radius: 8px; font-weight: bold; margin-top: 10px; font-size: 16px;">📥 Descargar Reporte Completo de la Línea (Abrir para imprimir PDF)</a>'
                        st.markdown(href, unsafe_allow_html=True)

    # --- SECCIÓN DEL TEMPORIZADOR (5 MINUTOS) ---
    st.divider()
    st.markdown("#### ⏱️ Temporizador de Medición")
    st.info("Utiliza este temporizador para asegurar la medición estándar de 5 minutos por estación antes de guardar el registro.")
    
    col_t1, col_t2 = st.columns([1, 2])
    with col_t1:
        iniciar_timer = st.button("▶️ Iniciar 5 Minutos", use_container_width=True)
    with col_t2:
        timer_placeholder = st.empty()
        if iniciar_timer:
            for t in range(300, -1, -1):
                mins, secs = divmod(t, 60)
                timer_placeholder.markdown(f"### ⏳ Tiempo restante: {mins:02d}:{secs:02d}")
                time.sleep(1)
            
            timer_placeholder.success("✅ ¡Tiempo de medición completado! Procede a registrar los datos.")
            st.balloons()

    # --- FORMULARIO DE CAPTURA DE NUEVOS REGISTROS ---
    st.divider()
    st.markdown("#### 📍 Ubicación y Operación")
    c_loc1, c_loc2 = st.columns(2)

    lineas_existentes = obtener_catalogo_lineas()
    linea_seleccionada = c_loc1.selectbox("Línea", options=lineas_existentes, key="em_linea_seleccionada_captura")
    nueva_op_check = c_loc2.checkbox("➕ Registrar nueva Operación o Línea")

    if nueva_op_check:
        linea_final = c_loc1.text_input("Ingresa Nueva Línea", value=linea_seleccionada if linea_seleccionada != "Sin registros" else "")
        id_operacion_final = c_loc2.text_input("Ingresa Nuevo ID de Operación (Ej: OP50-AUDIO)")
    else:
        linea_final = linea_seleccionada
        ops_existentes = []
        if not df_em_local.empty and 'Id de Operación' in df_em_local.columns:
            ops_filtradas = df_em_local[df_em_local['Línea'].astype(str).str.strip() == linea_seleccionada]
            ops_existentes = sorted([str(x).strip() for x in ops_filtradas['Id de Operación'].dropna().unique() if str(x).strip() != ''])
        
        if not ops_existentes:
            id_operacion_final = c_loc2.selectbox("ID de Operación", options=["(Sin operaciones previas)"])
        else:
            id_operacion_final = c_loc2.selectbox("Selecciona ID de Operación", options=ops_existentes)

    with st.form("form_event_meter_captura"):
        col1, col2 = st.columns(2)
        tipo_contacto = col1.selectbox("Tipo de contacto", options=["Maquinaria", "EOLT", "AOI", "Herramienta Manual", "Humano", "Otro"])
        if tipo_contacto == "Otro":
            tipo_contacto = col1.text_input("Especifique Tipo de Contacto")

        st.markdown("#### ⚡ Resultados de Detección")
        col_d1, col_d2 = st.columns(2)
        deteccion_eventos = col_d1.number_input("Cantidad de Eventos Detectados", min_value=0, step=1, value=0)
        voltaje_max = col_d2.number_input("Voltaje máximo de descarga (V)", min_value=0.0, max_value=999.0, step=0.1, value=0.0)

        notas_em = st.text_area("Notas / Observaciones")

        limite_maximo_v = 100.0  
        estatus_verificacion = "APROBADO" if voltaje_max <= limite_maximo_v else "RECHAZADO"
        fecha_hoy = datetime.today().date()
        frecuencia_em = "Semestral" 
        proxima_fecha = calcular_proxima_fecha(fecha_hoy, frecuencia_em)

        submit_em = st.form_submit_button("💾 Guardar Registro de Event Meter", use_container_width=True)

        if submit_em:
            if not id_operacion_final or id_operacion_final == "(Sin operaciones previas)":
                st.error("⚠️ Debes proporcionar un ID de Operación válido.")
            else:
                with st.spinner("Guardando en la tabla EVENT_METER de SQL..."):
                    try:
                        supabase.table("event_meter").insert({
                            "linea_ubicacion": linea_final,
                            "id_operacion": id_operacion_final.upper(),
                            "tipo_contacto": tipo_contacto,
                            "cantidad_eventos": int(deteccion_eventos),
                            "voltaje_maximo": float(voltaje_max),
                            "estatus_verificacion": estatus_verificacion,
                            "notas": notas_em,
                            "auditor": st.session_state.usuario_nombre,
                            "fecha": datetime.now().isoformat()
                        }).execute()
                        
                        st.success(f"✅ ¡Estudio de {id_operacion_final} registrado exitosamente! Estatus: {estatus_verificacion}")
                        st.cache_data.clear()
                        st.balloons()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error SQL al guardar en Event Meter: {e}")

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
                    c_ub1, c_ub2, c_ub3 = st.columns([1.5, 1.5, 1])
                    nombre_ub = c_ub1.text_input(f"Nombre de Línea/Área", value=dato['archivo'].replace(".pdf", ""), key=f"nombre_{i}")
                    tipo_piso = c_ub2.selectbox(f"Tipo de Piso", ["Piso Epóxico ESD", "Loseta Vinílica Conductiva", "Tapete Antifatiga ESD", "Otro"], key=f"piso_{i}")
                    
                    # Control interactivo que no se activa por defecto (asigna 'No')
                    limpieza_chk = c_ub3.checkbox("Limpieza previa", value=False, key=f"limpieza_{i}")
                    
                    bloques_ubicaciones.append({
                        "nombre": nombre_ub, 
                        "piso": tipo_piso, 
                        "limpieza": "Sí" if limpieza_chk else "No",
                        "datos": dato
                    })
                    st.write("") 

                # AHORA ESTÁ DENTRO DEL FORMULARIO Y SE ELIMINÓ EL WARNING USANDO width="stretch"
                submit_reporte = st.form_submit_button("Generar Reporte Consolidado en PDF/HTML", width="stretch")
                
                if submit_reporte:
                    html_ubicaciones = ""
                    for idx, block in enumerate(bloques_ubicaciones, 1):
                        data = block['datos']
                        if data['max_abs'] < 100:
                            res_text, res_color = "CUMPLE (PASS)", "text-green-600"
                            obs = "Ninguna anomalía. Los picos se mantuvieron por debajo del límite normativo de 100V."
                        else:
                            res_text, res_color = "NO CUMPLE (FAIL)", "text-red-600"
                            obs = f"ATENCIÓN: Se registró un pico absoluto de {data['max_abs']:.2f}V, superando el límite permitido de 100V. Se requiere limpieza o revisión."

                        img_tag = f'<img src="data:image/png;base64,{data["img_b64"]}" class="max-w-full max-h-full object-contain" alt="Gráfica">' if data['img_b64'] else '<i class="text-gray-400">Sin gráfica disponible</i>'

                        # --- BLOQUES DINÁMICOS DE UBICACIÓN EN TAILWIND ---
                        html_ubicaciones += f"""
                        <div class="border-2 border-[#003366] rounded-md p-5 mb-8 [page-break-inside:avoid] print:border-black">
                            <div class="text-[18px] font-bold text-white bg-[#003366] p-2.5 -mx-5 -mt-5 mb-5 rounded-t-sm print:bg-black">Ubicación {idx}: {block['nombre']}</div>
                            <table class="w-full text-sm border-collapse mb-5 text-center">
                                <tr>
                                    <th class="border border-gray-300 p-2 text-left bg-gray-50 font-bold w-1/4 print:border-black">Tipo de Piso:</th>
                                    <td class="border border-gray-300 p-2 text-left w-1/4 print:border-black">{block['piso']}</td>
                                    <th class="border border-gray-300 p-2 text-left bg-gray-50 font-bold w-1/4 print:border-black">Limpieza previa:</th>
                                    <td class="border border-gray-300 p-2 text-left w-1/4 print:border-black">{block['limpieza']}</td>
                                </tr>
                                <tr>
                                    <th class="border border-gray-300 p-2 text-left bg-gray-50 font-bold print:border-black">Voltaje Máx (Abs):</th>
                                    <td class="border border-gray-300 p-2 text-left font-mono font-bold print:border-black">{data['max_abs']:.2f} V</td>
                                    <th class="border border-gray-300 p-2 text-left bg-gray-50 font-bold print:border-black">Promedio de Picos:</th>
                                    <td class="border border-gray-300 p-2 text-left font-mono print:border-black">{data['promedio_picos']:.2f} V</td>
                                </tr>
                            </table>
                            <div class="w-full h-64 bg-gray-50 border-2 border-dashed border-gray-300 flex items-center justify-center my-5 overflow-hidden print:border-black">
                                {img_tag}
                            </div>
                            <table class="w-full text-sm border-collapse">
                                <tr>
                                    <th class="border border-gray-300 p-2 text-left bg-gray-50 font-bold w-1/5 print:border-black">Observaciones:</th>
                                    <td class="border border-gray-300 p-2 text-left print:border-black">{obs}</td>
                                    <th class="border border-gray-300 p-2 text-left bg-gray-50 font-bold w-1/5 print:border-black">Resultado Final:</th>
                                    <td class="border border-gray-300 p-2 text-center font-bold text-base print:border-black {res_color}">{res_text}</td>
                                </tr>
                            </table>
                        </div>
                        """
                        
                    fecha_pie_str = datetime.today().strftime("%Y/%m/%d")

                    # --- PLANTILLA MAESTRA CON TAILWIND CSS ---
                    html_completo = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>Reporte de Walking Test</title>
<script src="https://cdn.tailwindcss.com"></script>
<style>
    @media print {{ body {{ -webkit-print-color-adjust: exact; }} }}
</style>
</head>
<body class="bg-gray-100 p-4 md:p-8 font-sans text-sm print:bg-white print:p-0">
<div class="max-w-5xl mx-auto mb-6 bg-white p-4 rounded-lg shadow flex justify-end print:hidden">
    <button onclick="window.print()" class="bg-blue-600 text-white px-6 py-2 rounded font-bold shadow-sm hover:bg-blue-700 transition">🖨️ Imprimir / Guardar PDF</button>
</div>

<div class="max-w-5xl mx-auto bg-white p-8 shadow-lg print:shadow-none print:p-0">
    <div class="border-b-4 border-[#003366] pb-4 mb-6 text-center print:border-black">
        <h1 class="text-2xl font-bold text-[#003366] mb-1 print:text-black">Reporte de Walking Test (Prueba de Caminado)</h1>
        <p class="text-gray-600 text-sm font-medium">Evaluación de Sistema de Piso y Calzado ESD</p>
        <p class="text-gray-500 text-xs mt-1"><strong>Estándares aplicables:</strong> ANSI/ESD S20.20 y ANSI/ESD STM97.2</p>
    </div>

    <h2 class="text-base font-bold text-[#003366] border-b border-gray-300 pb-1 mt-6 mb-3 uppercase tracking-wide print:text-black print:border-black">1. Información General y Condiciones Ambientales</h2>
    <table class="w-full text-sm border-collapse mb-6">
        <tr>
            <th class="border border-gray-300 p-2 bg-gray-50 font-bold w-1/4 print:border-black">Fecha de Prueba:</th>
            <td class="border border-gray-300 p-2 w-1/4 print:border-black">{fecha_gen}</td>
            <th class="border border-gray-300 p-2 bg-gray-50 font-bold w-1/4 print:border-black">Periodo:</th>
            <td class="border border-gray-300 p-2 w-1/4 print:border-black">{periodo_wt}</td>
        </tr>
        <tr>
            <th class="border border-gray-300 p-2 bg-gray-50 font-bold print:border-black">Auditor / Técnico:</th>
            <td class="border border-gray-300 p-2 print:border-black">{auditor_wt}</td>
            <th class="border border-gray-300 p-2 bg-gray-50 font-bold print:border-black">Operador de Prueba:</th>
            <td class="border border-gray-300 p-2 print:border-black">{operador_wt}</td>
        </tr>
        <tr>
            <th class="border border-gray-300 p-2 bg-gray-50 font-bold print:border-black">Temperatura:</th>
            <td class="border border-gray-300 p-2 print:border-black">{temp_gen}</td>
            <th class="border border-gray-300 p-2 bg-gray-50 font-bold print:border-black">Humedad:</th>
            <td class="border border-gray-300 p-2 print:border-black">{hum_gen}</td>
        </tr>
    </table>

    <h2 class="text-base font-bold text-[#003366] border-b border-gray-300 pb-1 mt-6 mb-3 uppercase tracking-wide print:text-black print:border-black">2. Equipo de Medición y Sistema Evaluado</h2>
    <table class="w-full text-sm border-collapse mb-6">
        <tr>
            <th class="border border-gray-300 p-2 bg-gray-50 font-bold w-1/4 print:border-black">Equipo Utilizado:</th>
            <td class="border border-gray-300 p-2 w-1/4 print:border-black">{equipo_wt}</td>
            <th class="border border-gray-300 p-2 bg-gray-50 font-bold w-1/4 print:border-black">Criterio Aceptación:</th>
            <td class="border border-gray-300 p-2 w-1/4 font-bold text-[#003366] print:border-black print:text-black">&lt; 100 Voltios (Absoluto)</td>
        </tr>
        <tr>
            <th class="border border-gray-300 p-2 bg-gray-50 font-bold print:border-black">Calzado ESD Evaluado:</th>
            <td colspan="3" class="border border-gray-300 p-2 print:border-black">{calzado_wt}</td>
        </tr>
    </table>

    <h2 class="text-base font-bold text-[#003366] border-b border-gray-300 pb-1 mt-6 mb-4 uppercase tracking-wide print:text-black print:border-black">3. Resultados Consolidados por Ubicación</h2>
    {html_ubicaciones}

    <div class="flex justify-between mt-12 [page-break-inside:avoid]">
        <div class="w-[45%] text-center">
            <div class="border-t border-black mt-10 pt-1.5 text-sm"><strong>Realizado por:</strong><br>{auditor_wt}</div>
        </div>
        <div class="w-[45%] text-center">
            <div class="border-t border-black mt-10 pt-1.5 text-sm"><strong>Revisado / Aprobado por:</strong><br>Coordinador ESD</div>
        </div>
    </div>

    <div class="border-t-[3px] border-b-[3px] border-black mt-16 py-1 text-[11px] font-sans [page-break-inside:avoid]">
        <div class="flex justify-between items-end">
            <div class="text-left leading-tight">
                <div>E_310_4_116_QRO_EN_Rev. A</div>
                <div>Formato de Walking Test.</div>
            </div>
            <div class="text-center leading-tight">
                <div>Fecha: {fecha_pie_str}</div>
            </div>
            <div class="text-right leading-tight">
                <div>Ref.E_310_3_001_QRO_SP</div>
            </div>
        </div>
    </div>

</div>
</body>
</html>"""
                    
                    b64_html = base64.b64encode(html_completo.encode('utf-8')).decode('utf-8')
                    nombre_archivo = f"Walking_Test_{fecha_gen.replace('/', '-')}_{periodo_wt.replace(' ', '')}.html"
                    
                    st.success("✅ ¡Reporte de Walking Test estandarizado y migrado a Tailwind con éxito!")
                    href = f'<a href="data:text/html;base64,{b64_html}" download="{nombre_archivo}" target="_blank" style="display: block; text-align: center; padding: 15px; background-color: #003366; color: white; text-decoration: none; border-radius: 8px; font-weight: bold; margin-top: 10px; font-size: 16px;">📥 Descargar Reporte Estandarizado (Tailwind)</a>'
                    st.markdown(href, unsafe_allow_html=True)

# ==========================================
# VISTA 5: VALIDACIÓN ESD (SISTEMA INTEGRAL)
# ==========================================
elif st.session_state.vista_actual == "Validación" and not st.session_state.modo_lectura:
    st.markdown("### ✅ Validación Integral de Elementos de Control ESD")
    st.info("Registro de trazabilidad completa. Selecciona el equipo de medición y el elemento para autocompletar la información.")

    if "val_form_key" not in st.session_state:
        st.session_state.val_form_key = 0

    # --- CARGAR EQUIPOS DESDE SQL ---
    try:
        resp_eq = supabase.table("equipos_medicion").select("*").execute()
        df_equipos = pd.DataFrame(resp_eq.data)
        lista_equipos = df_equipos["id_equipo"].dropna().unique().tolist() if not df_equipos.empty else []
    except:
        df_equipos = pd.DataFrame()
        lista_equipos = ["Error de conexión"]

    tab_registro, tab_historial = st.tabs(["📝 Registrar Validación", "🖼️ Visor de Registros"])

    with tab_registro:
        if "val_success_msg" in st.session_state and st.session_state.val_success_msg:
            st.success(st.session_state.val_success_msg)
            st.session_state.val_success_msg = ""

        st.markdown("#### 1. Selección de Parámetros Globales")
        c_dyn1, c_dyn2, c_dyn3 = st.columns(3)
        elemento_sel = c_dyn1.selectbox("Elemento S20.20 a validar:", options=list(INFO_ELEMENTOS_ESD.keys()))
        info = INFO_ELEMENTOS_ESD[elemento_sel]
        
        id_equipo_sel = c_dyn2.selectbox("ID del Equipo de Medición:", options=lista_equipos)
        
        opciones_magnitud = list(MAPA_UNIDADES.keys())
        idx_mag = opciones_magnitud.index(info["magnitud"]) if info["magnitud"] in opciones_magnitud else 0
        magnitud_med = c_dyn3.selectbox("Magnitud Medida:", options=opciones_magnitud, index=idx_mag)
        unidad_auto = MAPA_UNIDADES.get(magnitud_med, "")

        # Obtener metadata del equipo seleccionado
        eq_data = {k: "N/D" for k in ["tipo_equipo", "reporte_calibracion", "resolucion", "fabricante", "modelo", "numero_serie", "fecha_proxima_calibracion"]}
        if not df_equipos.empty and id_equipo_sel in lista_equipos:
            fila_eq = df_equipos[df_equipos["id_equipo"] == id_equipo_sel]
            if not fila_eq.empty:
                eq_data = fila_eq.iloc[0].to_dict()

        with st.form(f"form_validacion_esd_{st.session_state.val_form_key}"):
            st.markdown("#### 2. Datos del Elemento a Validar")
            c1, c2 = st.columns([1, 2])
            id_elemento = c1.text_input("ID del Elemento", placeholder="Ej: SILLA-05")
            tipo_material = c2.text_input("Tipo de Material", value=info["tipo_material"])
            
            c4, c5, c6 = st.columns(3)
            fab_elem = c4.text_input("Fabricante del Elemento")
            mod_elem = c5.text_input("Modelo del Elemento")
            sn_elem = c6.text_input("Número de Serie")

            st.markdown("#### 3. Condiciones Ambientales y Ubicación")
            c7, c8, c9 = st.columns(3)
            ubicacion = st.selectbox("Ubicación de Medición (Línea / Área)", options=obtener_catalogo_lineas())
            temp = c8.text_input("Temperatura", value="23.5 °C")
            humedad = c9.text_input("Humedad Relativa", value="45 %")

            st.markdown("#### 4. Parámetros y Medición")
            cm1, cm2, cm3 = st.columns(3)
            metodo_med = cm1.text_input("Método", value=info["metodo"])
            modo_med = cm2.text_input("Modo de Medición", placeholder="Ej: RTG")
            unidad_med = cm3.text_input("Unidad", value=unidad_auto)

            referencia = st.number_input("Límite Permitido (Referencia)", value=float(info["ref_num"]), format="%g")

            # RE-INCORPORAMOS LAS 5 MEDICIONES ORIGINALES
            st.markdown("##### Resultados")
            cv1, cv2, cv3, cv4, cv5 = st.columns(5)
            medicion_1 = cv1.number_input("Medición 1 (Oblig.)", value=0.0, format="%g")
            med_2 = cv2.number_input("Medición 2 (Opc.)", value=None, format="%g", placeholder="0.0")
            med_3 = cv3.number_input("Medición 3 (Opc.)", value=None, format="%g", placeholder="0.0")
            med_4 = cv4.number_input("Medición 4 (Opc.)", value=None, format="%g", placeholder="0.0")
            med_5 = cv5.number_input("Medición 5 (Opc.)", value=None, format="%g", placeholder="0.0")
            
            notas_val = st.text_area("Notas / Observaciones")

            st.markdown("#### 5. Evidencia")
            col_img1, col_img2 = st.columns(2)
            imagen_camara = col_img1.camera_input("Foto")
            imagen_subida = col_img2.file_uploader("Subir imagen", type=["jpg", "png"])
            imagen_final = imagen_camara if imagen_camara else imagen_subida

            if st.form_submit_button("💾 Evaluar y Guardar Trazabilidad Completa", use_container_width=True):
                if not id_elemento or not ubicacion or not imagen_final:
                    st.error("⚠️ ID, Ubicación y Foto son obligatorios.")
                else:
                    with st.spinner("Procesando..."):
                        resultado_calc = "CUMPLE (APROBADO)" if medicion_1 < referencia else "NO CUMPLE (RECHAZADO)"
                        url_foto = subir_evidencia_storage(imagen_final, id_elemento.upper())
                        
                        # EMPAQUETAMOS LAS MEDICIONES EXTRAS
                        lista_extras = [str(m) for m in [med_2, med_3, med_4, med_5] if pd.notna(m) and m is not None]
                        mediciones_extra_str = ", ".join(lista_extras)

                        try:
                            supabase.table("validacion_esd").insert({
                                "fecha_auditoria": datetime.now().isoformat(),
                                "auditor": st.session_state.usuario_nombre,
                                "elemento_s20_20": elemento_sel,
                                "id_elemento": id_elemento.upper(),
                                "tipo_material": tipo_material,
                                "fabricante_elem": fab_elem,
                                "modelo_elem": mod_elem,
                                "sn_elem": sn_elem,
                                "temperatura": temp,
                                "humedad": humedad,
                                "ubicacion": ubicacion,
                                "id_equipo_utilizado": id_equipo_sel,
                                "tipo_equipo": eq_data.get('tipo_equipo'),
                                "reporte_cal": eq_data.get('reporte_calibracion'),
                                "resolucion": eq_data.get('resolucion'),
                                "fabricante_eq": eq_data.get('fabricante'),
                                "modelo_eq": eq_data.get('modelo'),
                                "sn_eq": eq_data.get('numero_serie'),
                                "fecha_prox_cal": str(eq_data.get('fecha_proxima_calibracion')),
                                "limite_referencia": float(referencia),
                                "medicion_1": float(medicion_1) if medicion_1 else None,
                                "medicion_2": float(med_2) if med_2 is not None else None,
                                "medicion_3": float(med_3) if med_3 is not None else None,
                                "medicion_4": float(med_4) if med_4 is not None else None,
                                "medicion_5": float(med_5) if med_5 is not None else None,
                                "unidad": unidad_med,
                                "metodo": metodo_med,
                                "modo_medicion": modo_med,
                                "resultado": resultado_calc,
                                "notas": notas_val,
                                "imagen_url": url_foto
                            }).execute()
                            
                            st.session_state.val_success_msg = f"✅ Guardado. Resultado: {resultado_calc}"
                            st.session_state.val_form_key += 1
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error SQL: {e}")

    with tab_historial:
        col_h1, col_h2 = st.columns([0.8, 0.2])
        col_h1.markdown("#### 🗂️ Dashboard de Registros Históricos")
        if col_h2.button("🔄 Actualizar Datos", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

        try:
            resp_val = supabase.table("validacion_esd").select("*").limit(10000).execute()
            df_val = pd.DataFrame(resp_val.data)
            
            if df_val.empty:
                st.info("Aún no hay registros.")
            else:
                df_val = df_val.sort_values('fecha_auditoria', ascending=False)

                for index, row in df_val.iterrows():
                    res = safe_str(row.get('resultado', ''))
                    icono = "🟢" if "CUMPLE" in res.upper() else "🔴"
                    fecha_corta = str(row.get('fecha_auditoria'))[:10]
                    
                    with st.expander(f"{icono} {fecha_corta} | {row.get('id_elemento')} ({row.get('elemento_s20_20')}) - {row.get('ubicacion')}"):
                        c_det1, c_det2, c_det3, c_img = st.columns([1, 1, 1, 1.5])
                        
                        with c_det1:
                            st.markdown("##### 📦 Elemento")
                            st.write(f"**ID:** {row.get('id_elemento')}")
                            st.write(f"**Fabricante:** {row.get('fabricante_elem')}")
                            st.write(f"**Modelo:** {row.get('modelo_elem')}")
                            st.write(f"**Material:** {row.get('tipo_material')}")
                        
                        with c_det2:
                            st.markdown("##### 🛠️ Trazabilidad")
                            st.write(f"**Equipo:** {row.get('id_equipo_utilizado')}")
                            st.write(f"**Certificado:** {row.get('reporte_cal')}")
                            st.write(f"**Próx. Cal:** {row.get('fecha_prox_cal')}")
                        
                        with c_det3:
                            st.markdown("##### 📊 Resultados")
                            st.write(f"**Medición:** {row.get('medicion_1')} {row.get('unidad')}")
                            st.write(f"**Límite:** < {row.get('limite_referencia')}")
                            st.write(f"**Resultado:** {res}")

                        with c_img:
                            url = row.get('imagen_url')
                            if url and url.startswith('http'):
                                st.image(url, use_container_width=True)
                            else:
                                st.warning("Sin imagen")

                        st.divider()
                        # GENERADOR DE REPORTE CON FORMATO COMPLETO
                        html_reporte = generar_html_reporte_completo(row, index)
                        b64_html = base64.b64encode(html_reporte.encode('utf-8')).decode('utf-8')
                        
                        # --- NUEVA LÓGICA DE NOMENCLATURA CON ID REAL ---
                        db_id = row.get('id', index)
                        try:
                            db_id = int(db_id)
                        except:
                            db_id = index
                            
                        año_actual_rep = datetime.today().strftime("%y")
                        nombre_oficial = f"BCS-PV-{db_id:03d}-{año_actual_rep}"
                        
                        st.markdown(
                            f'<a href="data:text/html;base64,{b64_html}" download="{nombre_oficial}.html" '
                            f'style="display: block; width: 100%; text-align: center; padding: 12px; '
                            f'background-color: #2563eb; color: white; text-decoration: none; border-radius: 8px; font-weight: bold;">'
                            f'📥 Descargar Reporte Original Completo</a>', 
                            unsafe_allow_html=True
                        )
        except Exception as e:
            st.error(f"Error cargando historial: {e}")

# ==========================================
# VISTA 6: AJUSTES (CATÁLOGOS MAESTROS)
# ==========================================
elif st.session_state.vista_actual == "Ajustes" and not st.session_state.modo_lectura:
    st.markdown("### ⚙️ Ajustes del Sistema (Catálogos)")
    st.info("Administra de forma centralizada las Líneas/Ubicaciones y los Equipos de Medición para que estén disponibles en todos los módulos de captura.")

    tab_ubicaciones, tab_equipos, tab_maquinaria, tab_exportar, tab_usuarios = st.tabs(["📍 Líneas y Ubicaciones", "🛠️ Equipos de Medición", "🏭 Maquinaria (Operaciones)", "💾 Exportar Datos", "🔐 Usuarios"])

# --- PESTAÑA 1: UBICACIONES ---
    with tab_ubicaciones:
        # Panel de herramientas automáticas (Migración del Historial)
        st.markdown("#### 🔄 Herramientas de Inicialización")
        st.caption("Utiliza esta utilidad para escanear de forma automática tus registros anteriores e inicializar el catálogo de líneas.")
        
        if st.button("🔍 Escanear e Importar Líneas del Historial Automáticamente", width="stretch"):
            with st.spinner("Analizando base de datos histórica..."):
                insertados, totales = ejecutar_automigracion_lineas()
                if totales > 0:
                    st.success(f"🎉 ¡Migración completada con éxito! Se detectaron {totales} líneas únicas. Se registraron {insertados} nuevas ubicaciones que no existían en el catálogo.")
                else:
                    st.info("No se detectaron líneas nuevas o el historial se encuentra vacío.")
                st.cache_data.clear()
                st.rerun()
        
        st.divider()
        
        # Formulario manual y visualización
        col_u1, col_u2 = st.columns([1, 1])
        
        with col_u1:
            st.markdown("#### ➕ Agregar Nueva Ubicación Manual")
            with st.form("form_nueva_ubicacion"):
                nueva_ub = st.text_input("Nombre de la Línea o Ubicación", placeholder="Ej: SMT 1, CR3, Metrology Lab")
                if st.form_submit_button("💾 Guardar Ubicación", width="stretch"):
                    if nueva_ub:
                        try:
                            supabase.table("catalogo_lineas").insert({"nombre_linea": nueva_ub.strip().upper()}).execute()
                            st.success(f"✅ Ubicación '{nueva_ub.upper()}' guardada.")
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as e:
                            st.error("⚠️ Error (¿Quizás la ubicación ya existe?).")
                    else:
                        st.error("El nombre no puede estar vacío.")
        
        with col_u2:
            st.markdown("#### 📋 Ubicaciones en el Catálogo Maestro")
            try:
                resp_ub = supabase.table("catalogo_lineas").select("nombre_linea").order("nombre_linea").execute()
                df_ub = pd.DataFrame(resp_ub.data)
                if not df_ub.empty:
                    st.dataframe(df_ub, use_container_width=True, hide_index=True)
                else:
                    st.info("No hay ubicaciones registradas aún.")
            except Exception as e:
                st.error(f"Error al cargar ubicaciones: {e}")
        # --- NUEVA FUNCIÓN: ACTUALIZACIÓN MASIVA DE FRECUENCIAS ---
        st.divider()
        st.markdown("#### ⏱️ Modificar Frecuencia de Validación por Línea")
        st.info("Actualiza masivamente la periodicidad de todos los activos (Mobiliario, Ionizadores y Maquinaria) asignados a una línea específica. El sistema recalculará automáticamente su próxima fecha de vencimiento partiendo de su última medición.")

        with st.form("form_update_frecuencia"):
            c_frec1, c_frec2 = st.columns(2)
            # Reutilizamos tu función maestra de catálogo
            linea_upd = c_frec1.selectbox("Selecciona la Línea a Modificar", options=obtener_catalogo_lineas())
            nueva_frec = c_frec2.selectbox("Nueva Frecuencia Aplicable", options=["Anual", "Semestral", "Trimestral", "Mensual"])

            # Botón destacado por ser una acción que altera muchos registros
            if st.form_submit_button("⚠️ Aplicar Cambio a Toda la Línea", type="primary", use_container_width=True):
                if linea_upd and linea_upd != "Sin Ubicaciones":
                    with st.spinner(f"Actualizando frecuencias y recalculando fechas para {linea_upd}..."):
                        activos_inv_actualizados = 0
                        activos_maq_actualizados = 0
                        
                        try:
                            # 1. ACTUALIZAR INVENTARIO (Mobiliario e Ionizadores)
                            # CORRECCIÓN: Usamos id_producto en lugar de id
                            resp_inv = supabase.table("inventario_esd").select("id_producto, fecha_ultima_verif").eq("linea_ubicacion", linea_upd).execute()
                            
                            for item in resp_inv.data:
                                f_ultima_str = item.get("fecha_ultima_verif")
                                data_update = {"frecuencia": nueva_frec}
                                
                                # Si el equipo tiene una medición previa, recalculamos su próximo vencimiento
                                if f_ultima_str and str(f_ultima_str).lower() not in ['nan', 'none', 'null', '']:
                                    try:
                                        # Parseamos la fecha ignorando la hora si la tiene
                                        f_ultima_date = datetime.fromisoformat(str(f_ultima_str).split('T')[0]).date()
                                        nueva_prox = calcular_proxima_fecha(f_ultima_date, nueva_frec)
                                        data_update["fecha_proxima_verif"] = nueva_prox.isoformat()
                                    except:
                                        pass # Si falla el parseo, solo actualiza la frecuencia
                                        
                                supabase.table("inventario_esd").update(data_update).eq("id_producto", item["id_producto"]).execute()
                                activos_inv_actualizados += 1

                            # 2. ACTUALIZAR MAQUINARIA
                            # CORRECCIÓN: Usamos id_maquinaria en lugar de id
                            resp_maq = supabase.table("mediciones_maquinaria").select("id_maquinaria, fecha_medicion").eq("linea_ubicacion", linea_upd).execute()
                            
                            for maq in resp_maq.data:
                                f_ultima_str = maq.get("fecha_medicion")
                                data_update_maq = {"frecuencia_verificacion": nueva_frec}
                                
                                if f_ultima_str and str(f_ultima_str).lower() not in ['nan', 'none', 'null', '']:
                                    try:
                                        f_ultima_date = datetime.fromisoformat(str(f_ultima_str).split('T')[0]).date()
                                        nueva_prox = calcular_proxima_fecha(f_ultima_date, nueva_frec)
                                        data_update_maq["fecha_proxima"] = nueva_prox.isoformat()
                                    except:
                                        pass
                                        
                                supabase.table("mediciones_maquinaria").update(data_update_maq).eq("id_maquinaria", maq["id_maquinaria"]).execute()
                                activos_maq_actualizados += 1

                            st.success(f"✅ ¡Cambio masivo aplicado con éxito a la línea **{linea_upd}**!")
                            st.info(f"📊 Se recalcularon las fechas de:\n- **{activos_inv_actualizados}** elementos de Mobiliario/Ionizadores.\n- **{activos_maq_actualizados}** equipos de Maquinaria.")
                            
                            # Limpiamos el caché general para que el mapa y los overviews se actualicen al instante
                            st.cache_data.clear()
                            
                        except Exception as e:
                            st.error(f"❌ Ocurrió un error durante la actualización masiva: {e}")
                else:
                    st.error("Por favor, selecciona una línea válida.")

    # --- PESTAÑA 2: EQUIPOS DE MEDICIÓN ---
    with tab_equipos:
        st.markdown("#### ➕ Agregar Nuevo Equipo de Medición")
        with st.form("form_nuevo_equipo"):
            c_eq1, c_eq2, c_eq3 = st.columns(3)
            id_eq = c_eq1.text_input("ID del Equipo (Obligatorio)", placeholder="Ej: BCS-QRO-LAB-01")
            tipo_eq = c_eq2.text_input("Tipo de Equipo", placeholder="Ej: Medidor de Resistencia")
            rep_cal = c_eq3.text_input("Reporte de Calibración")
            
            c_eq4, c_eq5, c_eq6 = st.columns(3)
            res_eq = c_eq4.text_input("Resolución / Alcance")
            fab_eq = c_eq5.text_input("Fabricante")
            mod_eq = c_eq6.text_input("Modelo")
            
            c_eq7, c_eq8 = st.columns(2)
            sn_eq = c_eq7.text_input("Número de Serie")
            venc_cal = c_eq8.date_input("Fecha de Próxima Calibración")
            
            if st.form_submit_button("💾 Guardar Equipo", width="stretch"):
                if id_eq:
                    try:
                        supabase.table("equipos_medicion").insert({
                            "id_equipo": id_eq.strip().upper(),
                            "tipo_equipo": tipo_eq,
                            "reporte_calibracion": rep_cal,
                            "resolucion": res_eq,
                            "fabricante": fab_eq,
                            "modelo": mod_eq,
                            "numero_serie": sn_eq,
                            "fecha_proxima_calibracion": str(venc_cal)
                        }).execute()
                        st.success(f"✅ Equipo '{id_eq.upper()}' guardado exitosamente.")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"⚠️ Error al guardar (¿El ID ya existe?): {e}")
                else:
                    st.error("El ID del equipo es obligatorio.")
        
        st.divider()
        st.markdown("#### 📋 Equipos Registrados")
        try:
            resp_eq_list = supabase.table("equipos_medicion").select("id_equipo, tipo_equipo, fabricante, fecha_proxima_calibracion").order("id_equipo").execute()
            df_eq_list = pd.DataFrame(resp_eq_list.data)
            if not df_eq_list.empty:
                st.dataframe(df_eq_list, use_container_width=True, hide_index=True)
            else:
                st.info("No hay equipos registrados aún.")
        except Exception as e:
            st.error(f"Error al cargar equipos: {e}")

    # --- PESTAÑA 3: MAQUINARIA / OPERACIONES ---
    with tab_maquinaria:
        st.markdown("#### ➕ Asignar Nueva Maquinaria a una Línea")
        st.info("Pre-registra una máquina u operación. Al guardarla, aparecerá automáticamente como 'PENDIENTE' en los menús de la sección de auditoría de Maquinaria.")

        with st.form("form_nueva_maquinaria_catalogo"):
            c_m1, c_m2 = st.columns(2)
            
            # Leemos directamente del catálogo maestro que alimentas en la primera pestaña
            lineas_disponibles_cat = obtener_catalogo_lineas()
            linea_asignada = c_m1.selectbox("1. Línea / Ubicación de destino", options=lineas_disponibles_cat)
            
            id_nueva_maq = c_m2.text_input("2. ID de la Maquinaria / Operación", placeholder="Ej: OP50-AUDIO, EOLT-01")
            
            c_m3, c_m4 = st.columns(2)
            clasif_opciones = ["Maquinaria", "EOLT", "AOI", "Ensamble Manual", "Herramienta", "Otro"]
            clasif_nueva_maq = c_m3.selectbox("3. Clasificación", options=clasif_opciones)
            
            if clasif_nueva_maq == "Otro":
                clasif_nueva_maq = c_m3.text_input("Especifique clasificación de la máquina")
                
            marca_nueva_maq = c_m4.text_input("4. Marca / Fabricante (Opcional)", value="N/D")

            if st.form_submit_button("💾 Pre-registrar Maquinaria", width="stretch"):
                if id_nueva_maq:
                    id_limpio_maq = str(id_nueva_maq).strip().upper()
                    
                    # --- NUEVA VERIFICACIÓN GLOBAL DE DUPLICADOS ---
                    check_inv_maq = supabase.table("inventario_esd").select("id_producto").eq("id_producto", id_limpio_maq).execute()
                    check_maq_maq = supabase.table("mediciones_maquinaria").select("id_maquinaria").eq("id_maquinaria", id_limpio_maq).execute()
                    
                    if len(check_inv_maq.data) > 0 or len(check_maq_maq.data) > 0:
                        st.error(f"❌ El ID '{id_nueva_maq}' ya se encuentra registrado en el sistema. Por favor, usa un ID diferente.")
                    else:
                        with st.spinner("Registrando..."):
                            try:
                                # Creamos un registro semilla para que la vista de Maquinaria lo detecte
                                data_inicial = {
                                    "linea_ubicacion": linea_asignada,
                                    "id_maquinaria": id_limpio_maq,
                                    "clasificacion": clasif_nueva_maq,
                                    "marca": marca_nueva_maq,
                                    "status_operativo": "OPERATIVO",
                                    "frecuencia_verificacion": "Anual",
                                    "fecha_medicion": datetime.now().isoformat(),
                                    "auditor": st.session_state.usuario_nombre,
                                    "resultado_estatus": "PENDIENTE",
                                    "observaciones": "Pre-registro desde módulo de Catálogos."
                                }
                                supabase.table("mediciones_maquinaria").insert(data_inicial).execute()
                            
                                st.success(f"✅ Maquinaria '{id_nueva_maq.upper()}' vinculada exitosamente a la línea '{linea_asignada}'.")
                                st.balloons()
                                time.sleep(1)
                                st.cache_data.clear()
                                st.rerun()
                            except Exception as e:
                                st.error(f"⚠️ Error al registrar maquinaria: {e}")
                else:
                    st.error("❌ El ID de la maquinaria es obligatorio.")
    # --- PESTAÑA 4: EXPORTAR BASES DE DATOS ---
    with tab_exportar:
        st.markdown("#### 📥 Exportar Bases de Datos a CSV")
        st.info("Descarga la información completa de tus inventarios y catálogos en formato CSV para realizar respaldos o análisis en Excel.")
        
        c_exp1, c_exp2 = st.columns(2)
        
        # 1. MOBILIARIO
        with c_exp1:
            st.markdown("**🛋️ Inventario de Mobiliario (y Piso)**")
            if not df_mob_local.empty:
                # Convertimos a CSV
                csv_mob = df_mob_local.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Descargar Mobiliario.csv",
                    data=csv_mob,
                    file_name=f"Mobiliario_ESD_{datetime.today().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            else:
                st.warning("No hay datos de Mobiliario disponibles.")

        # 2. IONIZADORES
        with c_exp2:
            st.markdown("**⚡ Inventario de Ionizadores**")
            if not df_ion_local.empty:
                csv_ion = df_ion_local.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Descargar Ionizadores.csv",
                    data=csv_ion,
                    file_name=f"Ionizadores_ESD_{datetime.today().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            else:
                st.warning("No hay datos de Ionizadores disponibles.")
        
        st.write("") # Espaciador
        c_exp3, c_exp4 = st.columns(2)

        # 3. EQUIPOS DE MEDICIÓN
        with c_exp3:
            st.markdown("**🛠️ Catálogo de Equipos de Medición**")
            try:
                # Hacemos una consulta fresca para traer todos los equipos
                resp_eq_exp = supabase.table("equipos_medicion").select("*").execute()
                df_eq_exp = pd.DataFrame(resp_eq_exp.data)
                
                if not df_eq_exp.empty:
                    csv_eq = df_eq_exp.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Descargar Equipos.csv",
                        data=csv_eq,
                        file_name=f"Equipos_Medicion_{datetime.today().strftime('%Y%m%d')}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                else:
                    st.warning("No hay equipos registrados.")
            except Exception as e:
                st.error(f"Error al obtener equipos: {e}")

        # 4. MAQUINARIA
        with c_exp4:
            st.markdown("**🏭 Historial de Maquinaria**")
            try:
                # Traemos todo el histórico de maquinaria
                resp_maq_exp = supabase.table("mediciones_maquinaria").select("*").order("fecha_medicion", desc=True).execute()
                df_maq_exp = pd.DataFrame(resp_maq_exp.data)
                
                if not df_maq_exp.empty:
                    csv_maq = df_maq_exp.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Descargar Maquinaria.csv",
                        data=csv_maq,
                        file_name=f"Maquinaria_ESD_{datetime.today().strftime('%Y%m%d')}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                else:
                    st.warning("No hay registros de Maquinaria.")
            except Exception as e:
                st.error(f"Error al obtener maquinaria: {e}")
    # --- PESTAÑA 5: USUARIOS (PANEL DE ADMINISTRACIÓN) ---
        with tab_usuarios:
            st.markdown("#### 🔐 Administración de Usuarios")
            st.info("Crea nuevos accesos para tu equipo de auditores. Todos los usuarios creados aquí tendrán acceso instantáneo al sistema.")
            
            c_adm1, c_adm2 = st.columns([1, 1.5])
            
            with c_adm1:
                st.markdown("#### ➕ Crear Nuevo Usuario")
                with st.form("form_crear_usuario"):
                    nuevo_nombre = st.text_input("Nombre Real (Ej: Juan Pérez)")
                    nuevo_user = st.text_input("ID de Usuario de acceso (Ej: jperez)")
                    nuevo_pwd = st.text_input("Contraseña", type="password")
                    nuevo_rol = st.selectbox("Rol en el Sistema", ["Auditor", "Admin"])
                    
                    if st.form_submit_button("💾 Registrar Usuario", use_container_width=True):
                        if nuevo_nombre and nuevo_user and nuevo_pwd:
                            with st.spinner("Registrando..."):
                                try:
                                    # --- NUEVO: HASHEAR LA CONTRASEÑA ANTES DE GUARDAR ---
                                    password_encriptada = generate_password_hash(nuevo_pwd)
                                    
                                    supabase.table("usuarios_app").insert({
                                        "nombre": nuevo_nombre,
                                        "usuario": nuevo_user,
                                        "password": password_encriptada, # Guardamos el hash, no el texto plano
                                        "rol": nuevo_rol
                                    }).execute()
                                    st.success(f"✅ Usuario '{nuevo_user}' creado exitosamente como {nuevo_rol}.")
                                    st.cache_data.clear()
                                    st.rerun()
                                except Exception as e:
                                    st.error("⚠️ Error: El ID de usuario probablemente ya existe.")
                        else:
                            st.error("Todos los campos son obligatorios.")

            with c_adm2:
                st.markdown("#### 👥 Usuarios Activos")
                try:
                    resp_usrs = supabase.table("usuarios_app").select("id, nombre, usuario, rol, fecha_creacion").order("id").execute()
                    df_usrs = pd.DataFrame(resp_usrs.data)
                    if not df_usrs.empty:
                        # Guardamos una copia sin alterar nombres de columnas para usarla en el reseteo
                        df_usrs_raw = df_usrs.copy()
                        
                        # Darle formato a la fecha para que no se vea el Timestamp kilométrico
                        df_usrs['fecha_creacion'] = pd.to_datetime(df_usrs['fecha_creacion']).dt.strftime('%d-%b-%Y')
                        df_usrs.columns = ["ID DB", "Nombre", "User ID", "Rol", "Creado el"]
                        st.dataframe(df_usrs, use_container_width=True, hide_index=True)
                        
                        # --- NUEVO: FUNCIÓN DE RESETEO DE CONTRASEÑA ---
                        st.divider()
                        st.markdown("#### 🔄 Restablecer Contraseña")
                        st.info("Si un usuario olvidó su acceso, selecciona su cuenta para asignarle la contraseña temporal: **`Welcome.123!`**")
                        
                        with st.form("form_reset_password"):
                            # Crear un diccionario para el selectbox {id: "Nombre (Usuario)"}
                            opciones_reset = dict(zip(df_usrs_raw["id"], df_usrs_raw["nombre"] + " (" + df_usrs_raw["usuario"] + ")"))
                            
                            usuario_a_resetear = st.selectbox(
                                "Selecciona el usuario a restablecer:", 
                                options=list(opciones_reset.keys()), 
                                format_func=lambda x: opciones_reset[x]
                            )
                            
                            if st.form_submit_button("⚠️ Restablecer a Default", type="primary", use_container_width=True):
                                with st.spinner("Aplicando nueva contraseña..."):
                                    try:
                                        # Generamos el hash de la contraseña temporal
                                        hash_temporal = generate_password_hash("Welcome.123!")
                                        
                                        # Actualizamos en Supabase usando el ID del usuario seleccionado
                                        supabase.table("usuarios_app").update({"password": hash_temporal}).eq("id", usuario_a_resetear).execute()
                                        
                                        st.success(f"✅ ¡Contraseña restablecida con éxito para **{opciones_reset[usuario_a_resetear]}**!")
                                        st.warning("Pídele al usuario que inicie sesión y utilice la opción '🔑 Cambiar mi contraseña' del menú lateral lo antes posible.")
                                    except Exception as e:
                                        st.error(f"Error al restablecer la contraseña en la base de datos: {e}")
                        # -----------------------------------------------
                except Exception as e:
                    st.error(f"Error cargando usuarios: {e}")        
# ==========================================
# VISTA 7: LÍNEAS DE PRODUCCIÓN Y MAQUINARIA
# ==========================================
elif st.session_state.vista_actual == "Maquinaria" and not st.session_state.modo_lectura:
    st.markdown("### 🏭 Control de Maquinaria en Líneas de Producción")
    
    # 1. Obtenemos datos directamente de la tabla mediciones_maquinaria para los desplegables e histórico
    try:
        resp_med = supabase.table("mediciones_maquinaria").select("*").order("fecha_medicion", desc=True).execute()
        df_med_maq = pd.DataFrame(resp_med.data)
    except Exception:
        df_med_maq = pd.DataFrame()

    # Extraer líneas y clasificaciones únicas basadas exclusivamente en las mediciones registradas
    # Asegurar que las líneas vengan del catálogo maestro
    lineas_disp = obtener_catalogo_lineas()
    
    # Extraer clasificaciones únicas de las mediciones registradas
    if not df_med_maq.empty and 'clasificacion' in df_med_maq.columns:
        clasificaciones_dinamicas = sorted([str(x).strip() for x in df_med_maq['clasificacion'].dropna().unique() if str(x).strip() not in ['None', 'nan', '']])
    else:
        clasificaciones_dinamicas = ["Maquinaria"]

    if not clasificaciones_dinamicas:
        clasificaciones_dinamicas = ["Maquinaria"]

    # SECCIÓN A: SELECCIÓN DE LÍNEA Y VISUALIZACIÓN DEL REGISTRO ANTERIOR
    st.markdown("#### 🔍 Consulta de Mediciones Anteriores")
    linea_sel = st.selectbox("1. Selecciona Línea / Ubicación para revisar historial", options=lineas_disp)

    # Filtrar el histórico de la línea seleccionada
    if not df_med_maq.empty and linea_sel != "Sin registros previos":
        df_historico_linea = df_med_maq[df_med_maq['linea_ubicacion'] == linea_sel].copy()
        
        if not df_historico_linea.empty:
            st.markdown(f"**Historial de operaciones en la línea {linea_sel}:**")
            
            df_mostrar = pd.DataFrame()
            df_mostrar["Operación / ID"] = df_historico_linea.get("id_maquinaria", pd.Series(dtype=str))
            df_mostrar["Clasificación"] = df_historico_linea.get("clasificacion", pd.Series(dtype=str))
            
            # Aplicar formato condicional a la resistencia (2 decimales si es < 10, exponencial si es mayor)
            def formatear_resistencia(val):
                try:
                    v = float(val)
                    return f"{v:.2f} Ω" if v < 10 else f"{v:.2E} Ω"
                except:
                    return "N/D"
            
            if "resistencia_tierra" in df_historico_linea.columns:
                df_mostrar["Resistencia Tierra"] = df_historico_linea["resistencia_tierra"].apply(formatear_resistencia)
            else:
                df_mostrar["Resistencia Tierra"] = "N/D"

            df_mostrar["Estatus Red"] = df_historico_linea.get("tomacorriente_estatus", "N/A")
            
            if "campo_estatico_voltaje" in df_historico_linea.columns:
                df_mostrar["Campo Estático"] = df_historico_linea["campo_estatico_voltaje"].astype(str) + " V"
            else:
                df_mostrar["Campo Estático"] = "0.0 V"
            
            # Ajustado para leer la nueva estructura homologada de estatus dinámicos
            df_mostrar["Estatus Final"] = df_historico_linea.get("resultado_estatus", "PENDIENTE")
            df_mostrar["Frecuencia"] = df_historico_linea.get("frecuencia_verificacion", "Anual")
            
            # Formatear la fecha para que sea legible de forma segura
            if "fecha_medicion" in df_historico_linea.columns:
                df_mostrar["Fecha Medición"] = pd.to_datetime(df_historico_linea["fecha_medicion"]).dt.strftime('%d-%b-%Y %H:%M')
            else:
                df_mostrar["Fecha Medición"] = "N/D"
                
            df_mostrar["Auditor"] = df_historico_linea.get("auditor", "N/D")

            # Limpieza final de NaN
            df_mostrar = df_mostrar.fillna("N/D")

            st.dataframe(df_mostrar, use_container_width=True, hide_index=True)
        else:
            st.info(f"No se encontraron mediciones previas grabadas en la línea {linea_sel}.")
    else:
        st.info("No hay registros históricos disponibles en este momento.")

    st.divider()

    # SECCIÓN B: ACCIÓN DE ACTUALIZAR VALIDACIÓN / NUEVA MEDICIÓN
    st.markdown("#### ➕ Registrar / Actualizar Validación de la Línea")
    
    tab_individual, tab_lote = st.tabs(["📝 Captura Individual", "🚀 Auditoría Rápida por Línea (Lote)"])
    
    # Obtenemos las máquinas de la línea seleccionada (para ambas pestañas)
    maquinas_en_linea = []
    if not df_med_maq.empty and linea_sel != "Sin registros previos" and 'id_maquinaria' in df_med_maq.columns:
        df_filtrado = df_med_maq[df_med_maq['linea_ubicacion'] == linea_sel]
        maquinas_en_linea = sorted([str(x).strip() for x in df_filtrado['id_maquinaria'].dropna().unique() if str(x).strip() != ''])

    with tab_individual:
        if not maquinas_en_linea:
            maquina_sel = st.text_input("Ingresa el ID de la maquinaria manualmente para iniciar registro:")
        else:
            maquina_sel = st.selectbox("Selecciona la Maquinaria específica", options=maquinas_en_linea)

        if maquina_sel:
        # Consultamos el Inventario Maestro solo para traer los límites técnicos fijos
            info_maq = {}
            limite_fijo = 1.0e9
            marca_defecto = ""
            clasif_defecto = clasificaciones_dinamicas[0]

            if 'df_inv_full' in locals() and not df_inv_full.empty:
                df_inv_filtrado = df_inv_full[df_inv_full['Id de producto'] == maquina_sel]
                if not df_inv_filtrado.empty:
                    info_maq = df_inv_filtrado.iloc[0]
                    limite_fijo = float(info_maq.get('Maximo', 1.0e9))
                    marca_defecto = str(info_maq.get('Marca', ''))
                
                    val_clasif = str(info_maq.get('Clasificación', ''))
                    if val_clasif in clasificaciones_dinamicas:
                        clasif_defecto = val_clasif

            try:
                idx_clasif = clasificaciones_dinamicas.index(clasif_defecto)
            except ValueError:
                idx_clasif = 0

            st.markdown(f"##### 📝 Nueva captura para la estación: `{maquina_sel}`")
        
            with st.form("form_medicion_maquinaria"):
                c_eq1, c_eq2, c_eq3 = st.columns(3)
                clasificacion_maq = c_eq1.selectbox("Clasificación", options=clasificaciones_dinamicas, index=idx_clasif)
                marca_maq = c_eq2.text_input("Marca / Fabricante", value=marca_defecto)
                status_maq = c_eq3.selectbox("Estatus Operativo Actual", ["OPERATIVO", "NO OPERATIVO", "MANTENIMIENTO"])
            
                c_amb1, c_amb2, c_amb3 = st.columns(3)
                temperatura_maq = c_amb1.text_input("Temperatura", value="23.5 °C")
                humedad_maq = c_amb2.text_input("Humedad Relativa", value="45 %")
                frecuencia_maq = c_amb3.selectbox("Frecuencia de Verificación", ["Anual", "Semestral", "Trimestral", "Mensual"], index=0)

                st.markdown("---")
                st.markdown("##### ⚡ 1. Resistencia a Tierra")
                col_r1, col_r2 = st.columns(2)
            
                # Inicializar de forma segura el valor en el session_state si no existe
                if "resistencia_maq_val" not in st.session_state:
                    st.session_state.resistencia_maq_val = 0.0

                # SOLUCIÓN AL ERR0R: Validamos el formato usando el session_state existente para evitar ciclos
                formato_dinamico = "%.2f" if st.session_state.resistencia_maq_val < 10.0 else "%.2e"
                step_dinamico = 0.01 if st.session_state.resistencia_maq_val < 10.0 else 1.0

                resistencia = col_r1.number_input(
                    "Valor de Resistencia (Ohms)", 
                    min_value=0.0, 
                    max_value=1e12, 
                    value=st.session_state.resistencia_maq_val,
                    step=step_dinamico,
                    format=formato_dinamico
                )
                # Sincronizar el valor modificado para el siguiente refresco de la app
                st.session_state.resistencia_maq_val = resistencia

                col_r2.text_input("Límite Máximo Permitido (Referencia Fija)", value=f"{limite_fijo:.2e}", disabled=True)
            
                # Validación automática visual e interna PASA / FALLA
                resultado_auto = "PASA" if resistencia <= limite_fijo else "FALLA"
                if resultado_auto == "FALLA":
                    st.error(f"❌ RESULTADO EVALUACIÓN: FALLA (Resistencia {resistencia:.2e} excede el límite de {limite_fijo:.2e})")
                else:
                    st.success(f"✅ RESULTADO EVALUACIÓN: PASA")

                st.markdown("##### 🔌 2. Tomacorriente (Opcional)")
                col_t1, col_t2 = st.columns(2)
                aplica_toma = col_t1.checkbox("Aplica medición a la red", value=True)
                estado_toma = "N/A"
                comentario_toma = ""
                if aplica_toma:
                    estado_toma = col_t1.radio("Estatus de Conexión", ["PASA", "FALLA"], horizontal=True)
                    if estado_toma == "FALLA":
                        comentario_toma = col_t2.text_input("Comentario de Falla (Requerido)", placeholder="Ej: Polaridad invertida...")

                st.markdown("##### 🧲 3. Medición de Campo Electrostático")
                c_campo1, c_campo2 = st.columns(2)
                voltaje_campo = c_campo1.number_input("Voltaje Detectado (V)", min_value=0.0, format="%.2f", step=1.0)
                comentario_campo = ""
                if voltaje_campo > 0:
                    comentario_campo = c_campo2.text_input("Ubicación de la carga (Requerido)", placeholder="Ej: En la banda...")
            
                obs_maq = st.text_area("Notas / Observaciones Generales")
            
                submit_maq = st.form_submit_button("💾 Guardar Nueva Validación en Historial", use_container_width=True)
            
                if submit_maq:
                    if aplica_toma and estado_toma == "FALLA" and not comentario_toma.strip():
                        st.error("⚠️ Debes escribir un comentario justificando la falla del tomacorriente.")
                    elif voltaje_campo > 0 and not comentario_campo.strip():
                        st.error("⚠️ Como detectaste voltaje, debes indicar dónde se encontró la carga electrostática.")
                    else:
                        with st.spinner("Actualizando registro transaccional en SQL..."):
                            try:
                                fecha_hoy = datetime.today().date()
                                proxima_fecha = calcular_proxima_fecha(fecha_hoy, frecuencia_maq)

                                # Implementación de la nueva lógica de negocio
                                if resistencia is None or resistencia == 0.0: 
                                # Si dejas la resistencia vacía o en 0 en el number_input
                                    estatus_calculado = "PENDIENTE"
                                elif proxima_fecha < fecha_hoy:
                                    estatus_calculado = "VENCIDO"
                                else:
                                    estatus_calculado = "VIGENTE"
                            
                                data_insert = {
                                    "linea_ubicacion": linea_sel,
                                    "id_maquinaria": maquina_sel,
                                    "clasificacion": clasificacion_maq,
                                    "marca": marca_maq,
                                    "status_operativo": status_maq,
                                    "temperatura": temperatura_maq,
                                    "humedad":  humedad_maq,
                                    "frecuencia_verificacion": "Anual",              # Forzado a "Anual" como solicitaste
                                    "fecha_proxima": proxima_fecha.isoformat(),
                                    "resistencia_tierra": float(resistencia) if resistencia > 0 else None,
                                    "resistencia_max": limite_fijo, 
                                    "tomacorriente_aplica": aplica_toma,
                                    "tomacorriente_estatus": estado_toma,
                                    "tomacorriente_comentario": comentario_toma,
                                    "campo_estatico_voltaje": float(voltaje_campo),
                                    "campo_estatico_comentario": comentario_campo,
                                    "observaciones": obs_maq,
                                    "fecha_medicion": datetime.now().isoformat(),
                                    "auditor": st.session_state.usuario_nombre,
                                    "resultado_estatus": estatus_calculado           # Tu nueva lógica automatizada
                                }
                            
                                supabase.table("mediciones_maquinaria").insert(data_insert).execute()
                            
                                st.success(f"✅ ¡Medición guardada! Próxima verificación calculada para: {proxima_fecha.strftime('%d-%b-%Y')}")
                                st.balloons()
                                time.sleep(1)
                                st.cache_data.clear()
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error al guardar: {e}")

    # ==========================================
    # MODO 2: CAPTURA EN LOTE (RESPONSIVA PARA TABLET/MÓVIL)
    # ==========================================
    with tab_lote:
        st.info("💡 **Modo Rápido Móvil/Tablet:** Despliega cada estación para registrar sus datos. Las columnas se adaptarán a tu pantalla. Al finalizar, presiona el botón al fondo para guardar toda la línea.")
        
        if not maquinas_en_linea:
            st.warning("Selecciona una línea con máquinas registradas previamente para usar el modo en lote.")
        else:
            with st.form("form_lote_movil"):
                # Diccionario para almacenar los inputs temporales de cada máquina
                resultados_lote = {}
                
                for i, maq in enumerate(maquinas_en_linea):
                    # Extraer clasificación histórica si existe
                    clasif = "Maquinaria"
                    if not df_filtrado[df_filtrado['id_maquinaria'] == maq].empty:
                        clasif = df_filtrado[df_filtrado['id_maquinaria'] == maq].iloc[0].get('clasificacion', 'Maquinaria')
                    
                    # Expandir solo el primer elemento por defecto para no abrumar la pantalla
                    with st.expander(f"⚙️ {maq} ({clasif})", expanded=(i == 0)):
                        # En tablet se ven en fila, en teléfono se apilan en columna
                        col_t, col_r, col_c = st.columns(3)
                        
                        toma_val = col_t.selectbox(
                            "1. Tomacorriente", 
                            ["PASA", "FALLA", "N/A"], 
                            key=f"toma_{maq}"
                        )
                        
                        res_val = col_r.number_input(
                            "2. Res. Tierra (Ω)", 
                            min_value=0.0, step=0.1, format="%.2e", 
                            key=f"res_{maq}"
                        )
                        
                        campo_val = col_c.number_input(
                            "3. Campo Est. (V)", 
                            min_value=0.0, step=1.0, format="%.1f", 
                            key=f"camp_{maq}"
                        )
                        
                        notas_val = st.text_input(f"Observaciones para {maq} (opcional)", key=f"not_{maq}")
                        
                        # Guardamos en el diccionario usando el ID de la máquina como llave
                        resultados_lote[maq] = {
                            "clasificacion": clasif,
                            "tomacorriente": toma_val,
                            "resistencia": res_val,
                            "campo": campo_val,
                            "notas": notas_val
                        }

                st.divider()
                # Botón grande y fácil de presionar en móviles
                submit_lote = st.form_submit_button("💾 Procesar y Guardar Línea Completa", use_container_width=True)
                
                if submit_lote:
                    with st.spinner("Registrando auditoría masiva en SQL..."):
                        errores = 0
                        fecha_hoy = datetime.today().isoformat()
                        proxima_fecha = (datetime.today().date() + relativedelta(years=1)).isoformat() # Asumiendo frecuencia anual
                        limite_fijo = 1.0e9 # Límite estándar, se puede conectar a tu diccionario
                        
                        for maq_id, datos in resultados_lote.items():
                            res = float(datos["resistencia"])
                            
                            # Calcular estatus
                            if res == 0.0:
                                estatus_calculado = "PENDIENTE"
                            elif res <= limite_fijo and datos["tomacorriente"] != "FALLA":
                                estatus_calculado = "VIGENTE"
                            else:
                                estatus_calculado = "FALLA"

                            data_insert = {
                                "linea_ubicacion": linea_sel,
                                "id_maquinaria": maq_id.strip().upper(),
                                "clasificacion": datos["clasificacion"],
                                "marca": "N/D",
                                "status_operativo": "OPERATIVO",
                                "temperatura": "23.5 °C", 
                                "humedad": "45 %",
                                "frecuencia_verificacion": "Anual",
                                "fecha_proxima": proxima_fecha,
                                "resistencia_tierra": res if res > 0 else None,
                                "resistencia_max": limite_fijo, 
                                "tomacorriente_aplica": datos["tomacorriente"] != "N/A",
                                "tomacorriente_estatus": datos["tomacorriente"] if datos["tomacorriente"] != "N/A" else None,
                                "campo_estatico_voltaje": float(datos["campo"]),
                                "observaciones": datos["notas"],
                                "fecha_medicion": fecha_hoy,
                                "auditor": st.session_state.usuario_nombre,
                                "resultado_estatus": estatus_calculado
                            }
                            
                            try:
                                supabase.table("mediciones_maquinaria").insert(data_insert).execute()
                            except Exception as e:
                                errores += 1
                                st.write(f"Error oculto en {maq_id}: {e}") # Útil para debug
                        
                        if errores == 0:
                            st.success(f"✅ ¡Auditoría masiva completada para {len(resultados_lote)} estaciones en {linea_sel}!")
                            st.balloons()
                            time.sleep(1.5)
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.warning(f"Se procesaron los registros, pero hubo {errores} errores en la inserción.")

# ==========================================
# VISTA 8: PROGRAMACIÓN (CRONOGRAMA DE VENCIMIENTOS)
# ==========================================
elif st.session_state.vista_actual == "Schedule" and not st.session_state.modo_lectura:
    st.markdown("### 📅 Cronograma de Verificaciones ESD")
    st.info("Selecciona una línea para visualizar las fechas de medición y vencimiento de Equipos, Mobiliarios e Ionizadores combinados.")
    
    # Obtener datos frescos de maquinaria para consolidar
    try:
        resp_maq = supabase.table("mediciones_maquinaria").select("linea_ubicacion, id_maquinaria, clasificacion, fecha_medicion, fecha_proxima, resultado_estatus").execute()
        df_maq_sched = pd.DataFrame(resp_maq.data)
    except Exception as e:
        df_maq_sched = pd.DataFrame()
        st.warning(f"Error al cargar maquinaria: {e}")

    # Consolidar datos en una sola lista
    lista_registros = []
    
    # 1. Extraer del Inventario (Mobiliario, Ionizadores, Piso, etc.)
    if df_inv_full is not None and not df_inv_full.empty:
        for _, row in df_inv_full.iterrows():
            # OMITIR EQUIPOS DADOS DE BAJA
            if str(row.get('Estatus operativo', '')).strip().upper() == 'NO OPERATIVO':
                continue
                
            lista_registros.append({
                "Línea": str(row.get('Línea', 'N/D')),
                "Categoría": str(row.get('categoria', 'N/D')),
                "ID / Nombre": str(row.get('Id de producto', 'N/D')),
                "Clasificación": str(row.get('Clasificación', 'N/D')),
                "Última Medición": str(row.get('Fecha de verificación', 'N/D'))[:10],
                "Próximo Vencimiento": str(row.get('Fecha de próxima verificación', 'N/D'))[:10],
                "Estatus": str(row.get('Estatus de verificación', 'N/D'))
            })
            
    # 2. Extraer de Maquinaria
    if not df_maq_sched.empty:
        # Mantener solo el registro más reciente por cada id_maquinaria
        df_maq_sched = df_maq_sched.sort_values('fecha_medicion', ascending=False).drop_duplicates(subset=['id_maquinaria'])
        for _, row in df_maq_sched.iterrows():
            # OMITIR MAQUINARIA DADA DE BAJA
            if str(row.get('status_operativo', '')).strip().upper() == 'NO OPERATIVO' or str(row.get('resultado_estatus', '')).strip().upper() == 'BAJA':
                continue
                
            f_med = str(row.get('fecha_medicion', 'N/D'))[:10] if pd.notna(row.get('fecha_medicion')) else 'N/D'
            f_prox = str(row.get('fecha_proxima', 'N/D'))[:10] if pd.notna(row.get('fecha_proxima')) else 'N/D'
            
            lista_registros.append({
                "Línea": str(row.get('linea_ubicacion', 'N/D')),
                "Categoría": "Maquinaria / Equipo",
                "ID / Nombre": str(row.get('id_maquinaria', 'N/D')),
                "Clasificación": str(row.get('clasificacion', 'N/D')),
                "Última Medición": f_med,
                "Próximo Vencimiento": f_prox,
                "Estatus": str(row.get('resultado_estatus', 'PENDIENTE'))
            })

    df_schedule_full = pd.DataFrame(lista_registros)

    if not df_schedule_full.empty:
        # Obtener líneas únicas
        lineas_disponibles = sorted([x for x in df_schedule_full['Línea'].unique() if x not in ['N/D', 'nan', 'None']])
        
        c_filtro1, c_filtro2 = st.columns(2)
        linea_sel = c_filtro1.selectbox("📍 Selecciona la Línea / Ubicación:", ["Todas las Líneas"] + lineas_disponibles)
        categoria_sel = c_filtro2.selectbox("🏷️ Filtrar por Categoría:", ["Todas", "Maquinaria / Equipo", "Mobiliario", "Ionizador", "Piso"])
        
        # Aplicar filtros
        df_filtrado = df_schedule_full.copy()
        if linea_sel != "Todas las Líneas":
            df_filtrado = df_filtrado[df_filtrado['Línea'] == linea_sel]
        if categoria_sel != "Todas":
            df_filtrado = df_filtrado[df_filtrado['Categoría'] == categoria_sel]
        
        # REPARACIÓN DE ORDENACIÓN: Reemplazar N/D por NaT para que no rompa la conversión de fecha
        df_filtrado['Fecha Orden'] = df_filtrado['Próximo Vencimiento'].replace('N/D', None)
        df_filtrado['Fecha Orden'] = pd.to_datetime(df_filtrado['Fecha Orden'], errors='coerce')
        
        # Los NaT (valores sin fecha/PENDIENTES) los mandamos al final para que no estorben la visualización crítica
        df_filtrado = df_filtrado.sort_values(by=['Fecha Orden', 'Línea'], ascending=[True, True], na_position='last').drop(columns=['Fecha Orden'])
        
        # Añadir emojis de estado para mayor claridad visual
        def add_emoji(val):
            val_str = str(val).upper()
            if 'VIGENTE' in val_str or 'PASA' in val_str: return f"🟢 {val}"
            if 'VENCIDO' in val_str or 'FALLA' in val_str or 'RECHAZADO' in val_str: return f"🔴 {val}"
            if 'PENDIENTE' in val_str: return f"🟡 {val}"
            return val
            
        df_filtrado['Estatus'] = df_filtrado['Estatus'].apply(add_emoji)
        
        st.markdown(f"**Mostrando {len(df_filtrado)} registros:**")
        st.dataframe(df_filtrado, use_container_width=True, hide_index=True)
        
        # --- NUEVA SECCIÓN: GENERAR REPORTE DE LÍNEA ---
        if linea_sel != "Todas las Líneas" and not df_filtrado.empty:
            st.divider()
            st.markdown(f"#### 📄 Generar Reporte de Validación: `{linea_sel}`")
            
            with st.form("form_rep_linea"):
                col_r1, col_r2 = st.columns([1, 2])
                auditor_rep = col_r1.text_input("Auditor / Coordinador", value=st.session_state.usuario_nombre)
                comentarios_rep = col_r2.text_area("Observaciones Generales", placeholder="Ej: La línea cumple satisfactoriamente...")
                
                if st.form_submit_button("Generar Reporte Oficial", use_container_width=True):
                    with st.spinner("Generando folio único y construyendo documento..."):
                        try:
                            # 1. Registrar en la bitácora para obtener ID único
                            resp_log = supabase.table("log_reportes_linea").insert({
                                "linea_ubicacion": linea_sel,
                                "auditor": auditor_rep,
                                "comentarios": comentarios_rep
                            }).execute()
                            
                            db_id_linea = resp_log.data[0]['id']
                            
                            # 2. Generar el HTML
                            html_rep_linea, año_rep = generar_html_reporte_linea(
                                linea=linea_sel, 
                                df_linea=df_filtrado, 
                                auditor=auditor_rep, 
                                comentarios=comentarios_rep, 
                                db_id=db_id_linea
                            )
                            
                            # 3. Preparar descarga
                            b64_html = base64.b64encode(html_rep_linea.encode('utf-8')).decode('utf-8')
                            nombre_oficial = f"BCS-LV-{db_id_linea:03d}-{año_rep}"
                            
                            st.success(f"✅ ¡Reporte {nombre_oficial} generado con éxito!")
                            
                            href = f'<a href="data:text/html;base64,{b64_html}" download="{nombre_oficial}.html" target="_blank" style="display: block; text-align: center; padding: 15px; background-color: #003366; color: white; text-decoration: none; border-radius: 8px; font-weight: bold; margin-top: 10px; font-size: 16px;">📥 Descargar / Imprimir Reporte de Línea ({nombre_oficial})</a>'
                            st.markdown(href, unsafe_allow_html=True)
                            
                        except Exception as e:
                            st.error(f"Error generando el reporte: {e}")
    else:
        st.warning("No hay registros disponibles para mostrar en el cronograma.")

# ==========================================
# VISTA 9: SENSIBILIDAD DE COMPONENTES (ESDS)
# ==========================================
elif st.session_state.vista_actual == "Sensibilidad" and not st.session_state.modo_lectura:
    st.markdown("### 🔌 Análisis de Sensibilidad de Componentes (HBM / CDM)")
    st.info("Consulta y gestiona los límites de susceptibilidad de los ensambles. Esencial para justificar los límites de control en la EPA.")

    tab_overview_sen, tab_consulta, tab_importar = st.tabs(["📈 Overview Global", "📊 Consulta de Reportes", "📥 Importar Histórico"])

    # --- PESTAÑA: OVERVIEW GLOBAL ---
    with tab_overview_sen:
        st.markdown("#### 🌍 Resumen Global de Sensibilidad en Planta")
        
        try:
            # Extraer ambas tablas
            resp_cat_ov = supabase.table("catalogo_sensibilidad").select("id, nombre_producto, numero_parte, cliente, nivel_sensibilidad").execute()
            df_cat_ov = pd.DataFrame(resp_cat_ov.data)
            
            resp_comp_ov = supabase.table("componentes_sensibilidad").select("id_producto, esd_hbm, esd_cdm").execute()
            df_comp_ov = pd.DataFrame(resp_comp_ov.data)
            
            if not df_cat_ov.empty and not df_comp_ov.empty:
                # Convertir a numérico para poder calcular mínimos
                df_comp_ov['esd_hbm_num'] = pd.to_numeric(df_comp_ov['esd_hbm'].replace('-', pd.NA), errors='coerce')
                df_comp_ov['esd_cdm_num'] = pd.to_numeric(df_comp_ov['esd_cdm'].replace('-', pd.NA), errors='coerce')
                
                # Obtener el mínimo HBM y CDM por cada ID de producto
                minimos_por_producto = df_comp_ov.groupby('id_producto').agg({
                    'esd_hbm_num': 'min', 
                    'esd_cdm_num': 'min'
                }).reset_index()
                
                # Unir el catálogo de productos con sus voltajes mínimos
                df_consolidado = pd.merge(df_cat_ov, minimos_por_producto, left_on='id', right_on='id_producto', how='inner')
                
                if not df_consolidado.empty:
                    # Cálculos Globales
                    min_hbm_global = df_consolidado['esd_hbm_num'].min()
                    min_cdm_global = df_consolidado['esd_cdm_num'].min()
                    
                    # Identificar el proyecto más sensible evaluando el mínimo absoluto entre HBM y CDM
                    df_consolidado['min_absoluto'] = df_consolidado[['esd_hbm_num', 'esd_cdm_num']].min(axis=1)
                    idx_mas_sensible = df_consolidado['min_absoluto'].idxmin()
                    proyecto_critico = df_consolidado.loc[idx_mas_sensible]
                    
                    # 1. TARJETAS DE MÉTRICAS GLOBALES
                    st.markdown("##### 🚨 Proyecto Más Crítico (Mayor Riesgo ESD)")
                    c_crit1, c_crit2, c_crit3 = st.columns(3)
                    
                    nombre_critico = f"{proyecto_critico['nombre_producto']} ({proyecto_critico['cliente']})"
                    voltaje_critico = f"{proyecto_critico['min_absoluto']:g} V" if pd.notna(proyecto_critico['min_absoluto']) else "N/D"
                    
                    c_crit1.metric("Proyecto Más Sensible", nombre_critico, delta="Requiere máxima atención", delta_color="inverse")
                    c_crit2.metric("Mínimo Global HBM", f"{min_hbm_global:g} V" if pd.notna(min_hbm_global) else "N/D")
                    c_crit3.metric("Mínimo Global CDM", f"{min_cdm_global:g} V" if pd.notna(min_cdm_global) else "N/D")
                    
                    st.divider()
                    
                    # 2. TABLA DE RESUMEN POR CLIENTE
                    st.markdown("##### 🏢 Sensibilidad Mínima por Cliente")
                    
                    # Filtrar productos que tengan al menos un valor de voltaje válido
                    df_validos = df_consolidado.dropna(subset=['min_absoluto'])
                    
                    if not df_validos.empty:
                        # 1. Encontrar el índice (la fila) del registro con el voltaje más bajo para cada cliente
                        idx_min_por_cliente = df_validos.groupby('cliente')['min_absoluto'].idxmin()
                        
                        # 2. Extraer solo esas filas usando los índices localizados y seleccionar las columnas deseadas
                        resumen_cliente = df_validos.loc[idx_min_por_cliente, ['cliente', 'nombre_producto', 'esd_hbm_num', 'esd_cdm_num']].copy()
                        
                        # 3. Limpiar y formatear para la visualización en pantalla
                        resumen_cliente.columns = ['Cliente', 'Producto Más Crítico', 'Mínimo HBM (V)', 'Mínimo CDM (V)']
                        resumen_cliente['Mínimo HBM (V)'] = resumen_cliente['Mínimo HBM (V)'].apply(lambda x: f"{x:g}" if pd.notna(x) else "N/D")
                        resumen_cliente['Mínimo CDM (V)'] = resumen_cliente['Mínimo CDM (V)'].apply(lambda x: f"{x:g}" if pd.notna(x) else "N/D")
                        
                        st.dataframe(resumen_cliente, use_container_width=True, hide_index=True)
                    else:
                        st.info("No hay datos suficientes para generar el resumen por cliente.")
                    
                    # 3. GRÁFICA VISUAL RÁPIDA
                    st.markdown("##### 📊 Comparativa Visual de Riesgo (Voltaje Mínimo Absoluto por Producto)")
                    
                    # Preparamos los datos para la gráfica
                    df_grafica = df_consolidado.dropna(subset=['min_absoluto']).copy()
                    if not df_grafica.empty:
                        df_grafica = df_grafica.sort_values('min_absoluto')
                        
                        import plotly.express as px
                        fig = px.bar(
                            df_grafica, 
                            x='nombre_producto', 
                            y='min_absoluto', 
                            color='cliente',
                            labels={'nombre_producto': 'Producto', 'min_absoluto': 'Límite de Soporte (Volts)', 'cliente': 'Cliente'},
                            text_auto='.0f'
                        )
                        fig.update_traces(textposition='outside')
                        fig.update_layout(yaxis_title="Volts (Menor = Más Crítico)", xaxis_title="")
                        st.plotly_chart(fig, use_container_width=True)

                else:
                    st.info("No se pudieron consolidar los datos de catálogo y componentes.")
            else:
                st.info("Aún no hay suficientes datos procesados para generar el Overview.")
        except Exception as e:
            st.error(f"Error generando el Overview: {e}")

    # --- PESTAÑA: CONSULTA Y EXPORTACIÓN ---
    with tab_consulta:
        # Extraer clientes y productos de la base de datos
        try:
            resp_cat = supabase.table("catalogo_sensibilidad").select("*").execute()
            df_cat = pd.DataFrame(resp_cat.data)
        except Exception as e:
            df_cat = pd.DataFrame()
            st.error(f"Error conectando a la base de datos: {e}")

        if not df_cat.empty:
            c_filtro1, c_filtro2 = st.columns(2)
            clientes_disp = sorted(df_cat['cliente'].dropna().unique())
            cliente_sel = c_filtro1.selectbox("🏢 Selecciona el Cliente:", ["Todos"] + list(clientes_disp))
            
            df_filtrado_cli = df_cat if cliente_sel == "Todos" else df_cat[df_cat['cliente'] == cliente_sel]
            
            # Crear un diccionario para mostrar Nombre + Número de parte bonito en el selector
            opciones_prod = {row['id']: f"{row['nombre_producto']} (PN: {row['numero_parte']})" for _, row in df_filtrado_cli.iterrows()}
            
            if opciones_prod:
                prod_id_sel = c_filtro2.selectbox("📦 Selecciona el Producto:", options=list(opciones_prod.keys()), format_func=lambda x: opciones_prod[x])
                
                # Obtener detalles del producto seleccionado
                prod_info = df_filtrado_cli[df_filtrado_cli['id'] == prod_id_sel].iloc[0]
                numero_parte = str(prod_info['numero_parte']).strip()
                nombre_prod = str(prod_info['nombre_producto']).strip()
                
                # ID ÚNICO DEL REPORTE
                id_reporte_unico = f"BCS-SEN-{numero_parte.replace(' ', '')}-{nombre_prod.replace(' ', '_')}".upper()
                
                # Obtener componentes del producto
                resp_comp = supabase.table("componentes_sensibilidad").select("*").eq("id_producto", prod_id_sel).execute()
                df_comp = pd.DataFrame(resp_comp.data)
                
                if not df_comp.empty:
                    # Limpiar y convertir datos a numéricos para cálculos
                    df_comp['esd_hbm_num'] = pd.to_numeric(df_comp['esd_hbm'].replace('-', pd.NA), errors='coerce')
                    df_comp['esd_cdm_num'] = pd.to_numeric(df_comp['esd_cdm'].replace('-', pd.NA), errors='coerce')
                    
                    min_hbm = df_comp['esd_hbm_num'].min()
                    min_cdm = df_comp['esd_cdm_num'].min()
                    
                    comp_hbm = df_comp.loc[df_comp['esd_hbm_num'] == min_hbm, 'part_number'].iloc[0] if pd.notna(min_hbm) else "N/D"
                    comp_cdm = df_comp.loc[df_comp['esd_cdm_num'] == min_cdm, 'part_number'].iloc[0] if pd.notna(min_cdm) else "N/D"

                    st.markdown(f"#### 📄 ID Reporte: `{id_reporte_unico}`")
                    
                    # Tarjetas de resumen
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Cliente", prod_info['cliente'])
                    m2.metric("Nivel Sensibilidad", prod_info['nivel_sensibilidad'])
                    m3.metric("Voltaje Mín. HBM", f"{min_hbm:g} V" if pd.notna(min_hbm) else "N/D", comp_hbm, delta_color="off")
                    m4.metric("Voltaje Mín. CDM", f"{min_cdm:g} V" if pd.notna(min_cdm) else "N/D", comp_cdm, delta_color="off")
                    
                    st.markdown("##### 🧩 Desglose de Componentes")
                    df_mostrar = df_comp[['part_number', 'descripcion', 'ref_designator', 'qty', 'esd_cdm', 'esd_hbm', 'comentarios']].copy()
                    df_mostrar.columns = ['Part Number', 'Descripción', 'Ref Designator', 'Qty', 'CDM (V)', 'HBM (V)', 'Comentarios']
                    st.dataframe(df_mostrar.fillna("-"), use_container_width=True, hide_index=True)

                    # Exportar a CSV usando el ID único
                    csv_sen = df_mostrar.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Descargar Análisis en CSV",
                        data=csv_sen,
                        file_name=f"{id_reporte_unico}.csv",
                        mime="text/csv",
                        type="primary"
                    )
                else:
                    st.warning("No hay componentes registrados para este producto.")
            else:
                st.warning("No hay productos para este cliente.")
        else:
            st.info("Aún no hay reportes de sensibilidad en el sistema. Utiliza la pestaña 'Importar Histórico'.")

    # --- PESTAÑA: IMPORTACIÓN ---
    with tab_importar:
        st.markdown("#### 📂 Cargar Archivos de Sensibilidad")
        st.write("Sube uno o varios archivos CSV o Excel. El sistema buscará la tabla automáticamente a partir de la cabecera 'Part Number'.")
        
        # Agregamos accept_multiple_files=True
        archivos_sen = st.file_uploader("Selecciona los archivos", type=["csv", "xlsx"], accept_multiple_files=True)
        
        if archivos_sen:
            # Iteramos sobre todos los archivos subidos
            for idx, archivo_sen in enumerate(archivos_sen):
                with st.expander(f"📄 Procesando: {archivo_sen.name}", expanded=True):
                    try:
                        # Leer archivo crudo
                        if archivo_sen.name.endswith('.csv'):
                            df_raw = pd.read_csv(archivo_sen, header=None)
                        else:
                            df_raw = pd.read_excel(archivo_sen, header=None)
                        
                        # Intentar localizar el inicio de la tabla
                        fila_inicio = None
                        for i in range(min(20, len(df_raw))):
                            if df_raw.iloc[i].astype(str).str.contains("Part Number", case=False, na=False).any():
                                fila_inicio = i
                                break
                        
                        if fila_inicio is not None:
                            # Aislar la tabla y forzar TODAS las cabeceras a ser texto
                            df_tabla = df_raw.iloc[fila_inicio+1:].copy()
                            columnas_texto = [str(c) for c in df_raw.iloc[fila_inicio].tolist()]
                            df_tabla.columns = columnas_texto
                            
                            # Encontrar la columna real de "Part Number"
                            col_pn_real = next((c for c in df_tabla.columns if 'part number' in c.lower()), df_tabla.columns[1])
                            
                            # Quitar filas donde el Part Number esté vacío o sea NaN
                            df_tabla = df_tabla.dropna(subset=[col_pn_real])
                            df_tabla = df_tabla[df_tabla[col_pn_real].astype(str).str.strip() != '']
                            df_tabla = df_tabla[df_tabla[col_pn_real].astype(str).str.strip().str.lower() != 'nan']
                            
                            st.success(f"✅ Tabla detectada ({len(df_tabla)} componentes encontrados).")
                            
                            # Asignamos un key único al form usando el índice del archivo
                            with st.form(f"form_guardar_sensibilidad_{idx}"):
                                st.markdown("##### 📝 Confirma los Datos Generales del Producto")
                                # Pre-llenado inteligente
                                sug_pn = df_raw.iloc[4, 4] if len(df_raw) > 4 and len(df_raw.columns) > 4 else ""
                                sug_cliente = df_raw.iloc[5, 8] if len(df_raw) > 5 and len(df_raw.columns) > 8 else ""
                                sug_prod = df_raw.iloc[7, 4] if len(df_raw) > 7 and len(df_raw.columns) > 4 else "" 
                                sug_lvl = df_raw.iloc[7, 8] if len(df_raw) > 7 and len(df_raw.columns) > 8 else ""

                                col_f1, col_f2 = st.columns(2)
                                num_parte_imp = col_f1.text_input("Número de Parte", value=str(sug_pn).replace('nan','').strip())
                                nom_prod_imp = col_f2.text_input("Nombre del Producto", value=str(sug_prod).replace('nan','').strip())
                                
                                col_f3, col_f4 = st.columns(2)
                                cliente_imp = col_f3.text_input("Cliente", value=str(sug_cliente).replace('nan','').strip())
                                nivel_imp = col_f4.text_input("Nivel de Sensibilidad", value=str(sug_lvl).replace('nan','').strip())

                                if st.form_submit_button("💾 Guardar Reporte en Base de Datos", use_container_width=True):
                                    if num_parte_imp and nom_prod_imp and cliente_imp:
                                        with st.spinner("Registrando producto y componentes..."):
                                            # 1. Insertar el producto en el catálogo
                                            resp_ins_prod = supabase.table("catalogo_sensibilidad").insert({
                                                "numero_parte": num_parte_imp.upper(),
                                                "nombre_producto": nom_prod_imp.upper(),
                                                "cliente": cliente_imp.upper(),
                                                "nivel_sensibilidad": nivel_imp
                                            }).execute()
                                            
                                            id_nuevo_prod = resp_ins_prod.data[0]['id']
                                            
                                            # 2. Preparar e insertar componentes mapeando a las columnas de texto
                                            componentes_a_insertar = []
                                            cols = df_tabla.columns.tolist()
                                            pn_col = next((c for c in cols if 'part number' in c.lower()), cols[0])
                                            desc_col = next((c for c in cols if 'description' in c.lower()), cols[1])
                                            ref_col = next((c for c in cols if 'ref' in c.lower()), cols[3] if len(cols)>3 else None)
                                            qty_col = next((c for c in cols if 'qty' in c.lower()), cols[4] if len(cols)>4 else None)
                                            cdm_col = next((c for c in cols if 'cdm' in c.lower()), cols[5] if len(cols)>5 else None)
                                            hbm_col = next((c for c in cols if 'hbm' in c.lower()), cols[6] if len(cols)>6 else None)
                                            com_col = next((c for c in cols if 'comentario' in c.lower()), cols[7] if len(cols)>7 else None)

                                            for _, fila in df_tabla.iterrows():
                                                val_cdm = str(fila[cdm_col]) if cdm_col and pd.notna(fila[cdm_col]) else "-"
                                                val_hbm = str(fila[hbm_col]) if hbm_col and pd.notna(fila[hbm_col]) else "-"
                                                
                                                componentes_a_insertar.append({
                                                    "id_producto": id_nuevo_prod,
                                                    "part_number": str(fila[pn_col]) if pd.notna(fila[pn_col]) else "N/D",
                                                    "descripcion": str(fila[desc_col]) if pd.notna(fila[desc_col]) else "N/D",
                                                    "ref_designator": str(fila[ref_col]) if ref_col and pd.notna(fila[ref_col]) else "",
                                                    "qty": int(fila[qty_col]) if qty_col and pd.notna(fila[qty_col]) and str(fila[qty_col]).isnumeric() else 1,
                                                    "esd_cdm": val_cdm,
                                                    "esd_hbm": val_hbm,
                                                    "comentarios": str(fila[com_col]) if com_col and pd.notna(fila[com_col]) else ""
                                                })
                                            
                                            supabase.table("componentes_sensibilidad").insert(componentes_a_insertar).execute()
                                            
                                            st.success(f"✅ ¡Producto {nom_prod_imp} guardado con éxito! (Puedes continuar con los demás o limpiar los archivos).")
                                    else:
                                        st.error("Por favor completa Número de Parte, Nombre y Cliente.")
                        else:
                            st.error("❌ No se encontró la cabecera 'Part Number' en este archivo. Verifica el formato.")
                    except Exception as e:
                        st.error(f"Error procesando el archivo: {e}")
