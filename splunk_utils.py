import requests
import json
import time
import urllib3
import os
import xml.etree.ElementTree as ET
from tqdm import tqdm

# Deshabilitar advertencias de HTTPS no verificadas (solo para desarrollo)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configuración de conexión usando variables de entorno
splunk_url = os.getenv("SPLUNK_URL", "https://192.168.1.148:8089")  # URL del servidor Splunk
username = os.getenv("SPLUNK_USERNAME", "admin")  # Nombre de usuario
password = os.getenv("SPLUNK_PASSWORD", "qx4JYz855.2aPDdH3Hj.58xBK4ce23gb")  # Contraseña

# Función para obtener el Session Key con reintentos
def get_session_key():
    """Autentica en Splunk y obtiene un Session Key, con reintentos en caso de fallo"""
    url = f"{splunk_url}/services/auth/login"
    data = {"username": username, "password": password}
    for attempt in range(3):  # Reintentar hasta 3 veces
        response = requests.post(url, data=data, verify=False)
        if response.status_code == 200:  # Comprobar si la respuesta es exitosa
            session_key = response.text.split("<sessionKey>")[1].split("</sessionKey>")[0]
            print("Autenticación exitosa.")
            return session_key
        else:
            print(f"Intento {attempt + 1}: Error en la autenticación. Reintentando...")
            time.sleep(2)  # Esperar 2 segundos entre intentos
    print("Error: No se pudo autenticar después de 3 intentos.")
    exit()

# Función para crear un Job de búsqueda
def create_search_job(session_key, search_query):
    """Crea un Job de búsqueda en Splunk y devuelve el SID"""
    if not search_query.strip():
        print("Error: La consulta de búsqueda no puede estar vacía.")
        exit()
    url = f"{splunk_url}/services/search/jobs"
    headers = {"Authorization": f"Splunk {session_key}"}  # Agregar Session Key al encabezado
    data = {
        "search": search_query,  # Consulta de búsqueda
        "output_mode": "json"  # Solicitar salida en formato JSON
    }
    response = requests.post(url, headers=headers, data=data, verify=False)  # Enviar solicitud POST

    if response.status_code == 201:  # Comprobar si el Job fue creado
        sid = response.json().get("sid")  # Extraer el SID
        print("Job de búsqueda creado con SID:", sid)
        return sid
    else:
        print("Error al crear el Job de búsqueda:", response.text)
        exit()

# Función para verificar el estado del Job con barra de progreso
def check_job_status(session_key, sid):
    """Verifica si el Job de búsqueda está completo con una barra de progreso"""
    url = f"{splunk_url}/services/search/jobs/{sid}"
    headers = {"Authorization": f"Splunk {session_key}"}
    params = {"output_mode": "json"}  # Forzar salida en JSON

    for _ in tqdm(range(100), desc="Procesando Job", unit="step"):
        response = requests.get(url, headers=headers, params=params, verify=False)
        if response.status_code == 200:
            try:
                content = response.json()
                dispatch_state = content.get("entry", [])[0].get("content", {}).get("dispatchState")
                if dispatch_state == "DONE":
                    print("\nJob completado.")
                    return True
            except json.JSONDecodeError:
                print("\nLa respuesta no está en formato JSON. Intentando parsear XML...")
                root = ET.fromstring(response.text)
                for elem in root.iter("{http://dev.splunk.com/ns/rest}key"):
                    if elem.attrib.get("name") == "dispatchState" and elem.text == "DONE":
                        print("\nJob completado.")
                        return True
        time.sleep(2)
    print("\nError: El Job no se completó dentro del tiempo esperado.")
    exit()

# Función para obtener los resultados del Job
def get_search_results(session_key, sid):
    """Obtiene los resultados de búsqueda usando el SID"""
    url = f"{splunk_url}/services/search/jobs/{sid}/results"
    headers = {"Authorization": f"Splunk {session_key}"}  # Agregar Session Key al encabezado
    params = {
        "output_mode": "json"  # Solicitar resultados en formato JSON
    }
    response = requests.get(url, headers=headers, params=params, verify=False)  # Enviar solicitud GET

    if response.status_code == 200:  # Comprobar si la solicitud fue exitosa
        try:
            results = response.json().get("results", [])  # Obtener los resultados
            print(f"Se recuperaron {len(results)} resultados.")
            return results
        except json.JSONDecodeError:
            print("Error al decodificar los resultados del Job. Respuesta:", response.text)
            exit()
    else:
        print("Error al obtener los resultados. Código de estado:", response.status_code)
        print("Respuesta:", response.text)
        exit()

# Función para filtrar datos innecesarios
def filter_results(results):
    """Filtra los campos relevantes de los resultados"""
    filtered_results = []
    for result in results:
        filtered_results.append({
            "time": result.get("_time"),  # Tiempo del evento
            "host": result.get("host"),  # Host de origen
            "source": result.get("source"),  # Fuente del evento
            "sourcetype": result.get("sourcetype"),  # Tipo de fuente
            "raw": result.get("_raw")  # Registro crudo
        })
    return filtered_results

# Función principal
def main_splunk():
    """Función principal para ejecutar el proceso completo"""
    session_key = get_session_key()  # Obtener el Session Key

    # Consulta predefinida de ejemplo
    default_search_query = "search index=main sourcetype=pan:config | head 10"

    # Solicitar al usuario el criterio de búsqueda o usar el predeterminado
    # use_default = input("¿Deseas usar la búsqueda predeterminada? (s/n): ").strip().lower()

    use_default = "s"
    if use_default == 'n':
        search_query = input("Ingresa tu consulta de búsqueda en Splunk: ").strip()
    else:
        search_query = default_search_query

    # Crear el Job de búsqueda
    sid = create_search_job(session_key, search_query)

    # Verificar el estado del Job
    check_job_status(session_key, sid)

    # Obtener los resultados del Job
    results = get_search_results(session_key, sid)

    # Filtrar los resultados
    filtered_results = filter_results(results)

    # Imprimir los resultados en la consola
    print("Resultados filtrados:")
    print(json.dumps(filtered_results, indent=4))

    # Guardar los resultados en un archivo .json
    output_file = "splunk_results.json"
    with open(output_file, "w") as f:
        json.dump(filtered_results, f, indent=4)

    print(f"Resultados guardados en {output_file}")

if __name__ == "__main__":
    main_splunk()



