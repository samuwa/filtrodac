import pandas as pd
import re
from PyPDF2 import PdfReader
from PyPDF2 import PdfMerger
import streamlit as st

from datetime import datetime


def extraer_lineas_pypdf2(file_path):

    try:
        reader = PdfReader(file_path)
    except Exception as e:
        print(f"Error al leer el PDF: {e}")
        return pd.DataFrame(columns=["Fecha", "Descripción", "Monto", "Saldo total"])

    text = ""
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"

    # Dividir el texto en líneas
    lines = text.split('\n')

    return lines

def extract_account_number(data_list):

    data_list = data_list[0:3]
    # Regex pattern to match the account number format
    pattern = r'\d{2}-\d{2}-\d{2}-\d{6}-\d{1}'

    # Loop through each item in the list
    for item in data_list:
        # Search for the pattern in the current item
        match = re.search(pattern, item)
        if match:
            # If a match is found, return the matched account number
            return match.group(0)
    # Return None if no account number is found
    return None

def convertir_columna_fecha(df, columna_fecha='Fecha'):
    """
    Convierte la columna especificada a formato datetime con el formato correcto de día-mes-año.

    Parámetros:
        df (pd.DataFrame): DataFrame que contiene la columna de fechas.
        columna_fecha (str): Nombre de la columna que contiene las fechas.

    Retorna:
        pd.DataFrame: DataFrame con la columna de fechas convertida a datetime.
    """
    # Especificar el formato de fecha en español (día-mes-año)
    df[columna_fecha] = pd.to_datetime(df[columna_fecha], format='%d-%b-%Y', errors='coerce')
    return df


def extraer_tablas_pypdf2(file_path):
    """
    Extrae datos tabulares de un archivo PDF con transacciones de cuenta usando PyPDF2 y procesamiento línea a línea.

    Parámetros:
        file_path (str): Ruta al archivo PDF.

    Retorna:
        pd.DataFrame: DataFrame con las columnas Fecha, Descripción, Monto y Saldo total.
    """
    try:
        reader = PdfReader(file_path)
    except Exception as e:
        print(f"Error al leer el PDF: {e}")
        return pd.DataFrame(columns=["Fecha", "Descripción", "Monto", "Saldo total"])

    text = ""
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"

    # Dividir el texto en líneas
    lines = text.split('\n')

    transactions = []
    current_transaction = {}
    descripcion = []

    # Patrón para identificar la fecha
    date_pattern = re.compile(r"^\d{2}-[a-zA-Z]{3}-\d{4}", re.IGNORECASE)

    # Patrón para Monto y Saldo
    monto_saldo_pattern = re.compile(r"(-?\$\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s+(-?\$\d{1,3}(?:,\d{3})*(?:\.\d{2})?)")

    for line in lines:
        line = line.strip()
        if not line:
            continue  # Saltar líneas vacías

        if date_pattern.match(line):
            # Si ya hay una transacción en curso, guardarla
            if current_transaction:
                current_transaction["Descripción"] = ' '.join(descripcion).strip()
                transactions.append(current_transaction)
                current_transaction = {}
                descripcion = []

            # Extraer Fecha
            fecha = date_pattern.findall(line)[0]
            current_transaction["Fecha"] = fecha

            # Remover la fecha del inicio de la línea para obtener el resto
            resto = date_pattern.sub('', line).strip()

            # Intentar extraer Monto y Saldo del resto de la línea
            match = monto_saldo_pattern.search(resto)
            if match:
                descripcion_text = monto_saldo_pattern.split(resto)[0].strip()
                descripcion.append(descripcion_text)
                current_transaction["Monto"] = match.group(1)
                current_transaction["Saldo total"] = match.group(2)
            else:
                descripcion.append(resto)
        elif current_transaction:
            # Intentar extraer Monto y Saldo de la línea actual
            match = monto_saldo_pattern.search(line)
            if match:
                current_transaction["Monto"] = match.group(1)
                current_transaction["Saldo total"] = match.group(2)
            else:
                # Agregar línea a la descripción
                descripcion.append(line)

    # Agregar la última transacción
    if current_transaction:
        current_transaction["Descripción"] = ' '.join(descripcion).strip()
        transactions.append(current_transaction)

    if not transactions:
        print("No se encontraron transacciones.")
        return pd.DataFrame(columns=["Fecha", "Descripción", "Monto", "Saldo total"])

    df = pd.DataFrame(transactions)

    # Reemplazar meses en español por inglés
    meses_espanol_a_ingles = {
        'ene': 'Jan', 'feb': 'Feb', 'mar': 'Mar', 'abr': 'Apr',
        'may': 'May', 'jun': 'Jun', 'jul': 'Jul', 'ago': 'Aug',
        'sep': 'Sep', 'oct': 'Oct', 'nov': 'Nov', 'dic': 'Dec'
    }

    df["Fecha"] = df["Fecha"].str.lower()
    for mes_es, mes_en in meses_espanol_a_ingles.items():
        df["Fecha"] = df["Fecha"].str.replace(mes_es, mes_en, regex=False)

    # Convertir a datetime
    df["Fecha"] = pd.to_datetime(df["Fecha"], format="%d-%b-%Y", errors="coerce", dayfirst=True)
    if df["Fecha"].isnull().any():
        print("Algunas fechas no pudieron ser convertidas y se establecieron como NaT.")

    # Limpiar Monto y Saldo total
    for columna in ["Monto", "Saldo total"]:
        df[columna] = df[columna].replace('[\$,]', '', regex=True).replace(',', '', regex=True).astype(float)


    df = df.dropna(subset=["Monto", "Saldo total"])


    return df

def analizar_cuenta_principal(df):
    # Asegurarse de que el formato de los datos sea consistente
    df['Descripción'] = df['Descripción'].str.upper()  # Estandarizar a mayúsculas para facilitar la búsqueda
    df['Monto'] = df['Monto'].replace('[\$,]', '', regex=True).astype(float)  # Convertir el monto a float para análisis

    # 1. Detectar si hay retiros o depósitos que incluyan "ATM" en la descripción
    tiene_atm = df['Descripción'].str.contains("ATM").any()

    # 2. Contar los ingresos y egresos que incluyen "YAPPY" en la descripción
    ingresos_yappy_count = df[(df['Descripción'].str.contains("YAPPY")) & (df['Monto'] > 0)].shape[0]
    egresos_yappy_count = df[(df['Descripción'].str.contains("YAPPY")) & (df['Monto'] < 0)].shape[0]

    return {
        'tiene_atm': tiene_atm,
        'ingresos_yappy_count': ingresos_yappy_count,
        'egresos_yappy_count': egresos_yappy_count
    }

def obtener_ingresos_mensuales_mas_altos(df):
    # Asegurarse de que el formato de los datos sea consistente

    df['Monto'] = df['Monto'].replace('[\$,]', '', regex=True).astype(float)  # Convertir el monto a float

    # Filtrar solo los ingresos (monto positivo)
    ingresos_df = df[df['Monto'] > 0].copy()

    # Crear columnas adicionales para año y mes
    ingresos_df['AñoMes'] = ingresos_df['Fecha'].dt.to_period('M')

    # Agrupar por AñoMes y obtener los 4 ingresos más altos por mes
    ingresos_mas_altos_por_mes = (ingresos_df.groupby('AñoMes')
                                  .apply(lambda x: x.nlargest(4, 'Monto'))
                                  .reset_index(drop=True))

    # Seleccionar solo las columnas necesarias para el análisis
    ingresos_mas_altos_por_mes = ingresos_mas_altos_por_mes[['Fecha', 'Descripción', 'Monto', 'AñoMes']]

    return ingresos_mas_altos_por_mes

st.subheader("Filtro DaC")

uploaded_files = st.file_uploader("Estados de Cuenta", type="pdf", accept_multiple_files=True, key="filtro_dac")

st.divider()

if not uploaded_files:
    pass

elif uploaded_files:

    combined_df = pd.DataFrame()  # DataFrame vacío para almacenar resultados combinados de múltiples archivos

    # Procesar cada archivo PDF subido
    for file in uploaded_files:

        df = extraer_tablas_pypdf2(file)
        combined_df = pd.concat([combined_df, df], ignore_index=True)


    n_cuenta = [extract_account_number(extraer_lineas_pypdf2(file)) for file in uploaded_files]


    # Mostrar el DataFrame final en Streamlit

    col1, col2, col3 = st.columns([4,1,7])

    col1.write("**Cuentas:**")

    for n in n_cuenta:
        col1.write(n)

    if len(set(n_cuenta)) > 1:
        col1.error("Cuentas diferentes!")
    else:
        col1.info("Cuenta única")

    combined_df["Fecha"] = pd.to_datetime(combined_df["Fecha"])

    min_fecha = str(combined_df["Fecha"].min())
    max_fecha = str(combined_df["Fecha"].max())

    min_fecha = min_fecha[0:10]
    max_fecha = max_fecha[0:10]

    col1.write("**Rango de fechas**")
    col1.write(f"{min_fecha} **-** {max_fecha}")



    display_df = combined_df.copy()
    display_df["Fecha"] = display_df["Fecha"].dt.date



    principal = analizar_cuenta_principal(combined_df)

    col1.write("**Cuenta Principal**")

    col1.write(f"Cargos relacionados con ATM: **{principal['tiene_atm']}**")
    col1.write(f"Yappys entrada: **{principal['ingresos_yappy_count']}**")
    col1.write(f"Yappys salida: **{principal['egresos_yappy_count']}**")


    st.divider()

    col3.write("**Ingresos Principales**")

    i_p = obtener_ingresos_mensuales_mas_altos(combined_df)

    i_p["Fecha"] = i_p["Fecha"].dt.date

    col3.dataframe(i_p, use_container_width=True, hide_index=True)
