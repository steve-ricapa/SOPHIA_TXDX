import os
import tkinter as tk
from tkinter import messagebox
import pyaudio
import wave
from pathlib import Path
from openai import OpenAI
import requests
import boto3
from dotenv import load_dotenv
import json
from meraki_utils import listar_organizaciones_y_redes,obtener_datos_red
import re

# Cargar las variables desde el archivo .env
load_dotenv()

# Cargar claves y configuración desde variables de entorno
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")  # Valor por defecto: us-east-1
POLLY_VOICE_ID = os.getenv("POLLY_VOICE_ID", "Lucia")  # Valor por defecto: Lucia
MODEL = os.getenv("OPENAI_MODEL", "gpt-4")  # Valor por defecto: gpt-4-turbo
MERAKI_KEY = os.getenv("MERAKI_KEY")

# Listar organizaciones y redes (dependiendo del uso en tu programa)
listar_organizaciones_y_redes(MERAKI_KEY)

# Verificar que las claves estén cargadas
if not OPENAI_API_KEY:
    raise ValueError("La clave OPENAI_API_KEY no está configurada en el archivo .env.")

if not MERAKI_KEY:
    raise ValueError("La clave MERAKI_KEY no está configurada en el archivo .env.")

# Configuración de OpenAI
client = OpenAI(api_key=OPENAI_API_KEY)

# Leer el contenido del archivo JSON en lugar de los TXT
organizations_and_networks_file = "organizations_and_networks.json"
additional_context = ""

if Path(organizations_and_networks_file).exists():
    try:
        with open(organizations_and_networks_file, "r", encoding="utf-8") as file:
            json_data = json.load(file)
            additional_context = json.dumps(json_data, indent=4, ensure_ascii=False)
            print(f"Archivo {organizations_and_networks_file} cargado correctamente.")
    except Exception as e:
        print(f"Error al cargar el archivo {organizations_and_networks_file}: {e}")
else:
    print(f"Archivo {organizations_and_networks_file} no encontrado.")

# Contexto principal del asistente
ASSISTANT_CONTEXT = (
    "Saluda diciendo tu nombre el cual es SOPHIA, luego presentas quien eres y di Bienvenido al Experience Operacion Center. "
    "Eres la Inteligencia artificial de la empresa TXDX SECURE. "
    "Tu funcion es atender a los clientes que hagan una llamada para monitorear sus equipos, resolver dudas y generar tickets para la resolucion de problemas. "
    "TXDXSECURE es una empresa dedicada a redes y ciberseguridad. "
    "Te haran preguntas de ciberseguridad . "
    "Cuando entregues un informe, interpreta los resultados y proporciona un resumen claro y útil."
    f"\nInformación adicional:\n{additional_context}"  # Incluir el contenido del archivo JSON
)

print(ASSISTANT_CONTEXT)

splunk_json_file = "splunk.json"
meraki_json_file = "network_data.json"
# Audio Configuration
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
CHUNK = 1024
AUDIO_FILE = "mensaje1.wav"

recording = False
frames = []
stream = None
audio_interface = None

# Historial de mensajes
conversation_history = []


def agregar_json_al_contexto(json_file, context_variable):
    try:
        # Abrir y leer el archivo JSON
        with open(json_file, "r", encoding="utf-8") as file:
            json_data = json.load(file)

        # Formatear el contenido JSON como texto legible
        formatted_text = f"\nContenido de {json_file}:\n"
        formatted_text += json.dumps(json_data, indent=4, ensure_ascii=False)

        # Agregar el contenido formateado al contexto
        context_variable += formatted_text
        print(f"Contenido de {json_file} agregado correctamente al contexto.")
        return context_variable
    except Exception as e:
        print(f"Error al procesar el archivo JSON {json_file}: {e}")
        return context_variable


# Function to classify a question using OpenAI
def classify_question(prompt):
    try:
        print("Clasificando la pregunta...")
        classification_response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system",
                 "content": "Eres un experto en redes y ciberseguridad. Tu tarea es clasificar las preguntas con los siguientes casos: "
                            "1. Respuesta con información por Default "
                            "2. Información en tiempo real de Cisco Splunk. "
                            "3. Información en tiempo real de Cisco Meraki."
                            "Dame solo la pregunta seguida del número del caso (por ejemplo: 'Pregunta N - CASO 1'). "
                            "Si la pregunta pertenece al Caso 3 y la pregunta es sobre una red en especifico, que me de la respuesta con el siguiente encabezado:"
                            "Pregunta N - CASO 3 - Red: (Nombre de la red en caso que no se pregunte sobre una red colocar unknown, la red que coloques aca debe ser escrita tal cual como esta en tu info por default, no olvides los espacios(por ejemplo en casos que el texto te diga 'OfficeLima' debes poner'Office Lima'porque asi esta en el json)) "
                            "Para preguntas como que redes tienes disponibles o que organizaciones?, se pueden responder con informacion por default,clasificalas como caso 1 , si te preguntan algo especifico dentro de esa red ahi si serian caso 3"
                 },
                {"role": "user", "content": prompt}
            ]
        )
        classification_result = classification_response.choices[0].message.content.strip()
        print(f"Clasificación recibida: {classification_result}")
        if "CASO 3" in classification_result:
            # Extraer el nombre de la red usando una expresión regular
            match = re.search(r"Red: (.+)", classification_result)
            red_name = match.group(1).strip() if match else "unknown"
            return f"CASO 3 - Red: {red_name}"

        if "CASO 1" in classification_result:
            return 1
        elif "CASO 2" in classification_result:
            return 2
        else:
            print("Clasificación desconocida. Usando CASO 1 por defecto.")
            return 1
    except Exception as e:
        print(f"Error al clasificar la pregunta: {e}")
        return None


# Function to start/stop recording
def toggle_recording():
    global recording, frames, stream, audio_interface
    if not recording:
        try:
            recording = True
            frames = []
            audio_interface = pyaudio.PyAudio()
            stream = audio_interface.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True,
                                          frames_per_buffer=CHUNK)
            print("Grabación iniciada. Puedes hablar ahora.")
            record_audio()
        except Exception as e:
            print(f"No se pudo iniciar la grabación: {e}")
            recording = False
    else:
        try:
            recording = False
            stream.stop_stream()
            stream.close()
            audio_interface.terminate()
            print("Grabación detenida. Procesando el audio...")
            save_audio()
        except Exception as e:
            print(f"No se pudo detener la grabación: {e}")


# Function to record audio
def record_audio():
    global recording, frames, stream
    if recording:
        try:
            data = stream.read(CHUNK, exception_on_overflow=False)
            frames.append(data)
            root.after(10, record_audio)
        except Exception as e:
            print(f"Error durante la grabación: {e}")
            recording = False


# Function to save audio to a file
def save_audio():
    try:
        p = pyaudio.PyAudio()
        wf = wave.open(AUDIO_FILE, 'wb')
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(p.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))
        wf.close()
        print(f"Audio guardado como {AUDIO_FILE}")
        transcribe_and_respond()
    except Exception as e:
        print(f"No se pudo guardar el audio: {e}")


# Function to transcribe audio using Whisper API
def transcribe_audio():
    url = "https://api.openai.com/v1/audio/transcriptions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}"
    }
    files = {
        "file": (AUDIO_FILE, open(AUDIO_FILE, "rb")),
        "model": (None, "whisper-1")
    }
    response = requests.post(url, headers=headers, files=files)
    if response.status_code == 200:
        text = response.json().get("text", "")
        print(f"Transcripción: {text}")
        return text
    else:
        raise Exception(f"Error en la transcripción: {response.text}")


# Function to interact with GPT-4-Turbo and maintain conversation history
def interact_with_gpt4(prompt):
    global conversation_history
    conversation_history.append({"role": "user", "content": prompt})

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": ASSISTANT_CONTEXT},
            *conversation_history
        ],
    )
    assistant_response = response.choices[0].message.content
    print(f"Respuesta del asistente: {assistant_response}")
    conversation_history.append({"role": "assistant", "content": assistant_response})
    return assistant_response


# Function to convert text to speech using Amazon Polly
def text_to_speech_with_polly(text):
    try:
        polly_client = boto3.client('polly', region_name=AWS_REGION)
        response = polly_client.synthesize_speech(
            Text=text,
            OutputFormat="mp3",
            VoiceId=POLLY_VOICE_ID
        )
        audio_file_path = Path("response.mp3")
        with open(audio_file_path, "wb") as audio_file:
            audio_file.write(response['AudioStream'].read())
        print(f"Audio guardado en {audio_file_path}")
        os.system(f"start {audio_file_path}" if os.name == 'nt' else f"open {audio_file_path}")
    except Exception as e:
        print(f"Error en TTS con Amazon Polly: {e}")


# Cargar el archivo JSON de organizaciones y redes
def cargar_organizaciones_y_redes():
    with open("organizations_and_networks.json", "r") as file:
        return json.load(file)


def transcribe_and_respond():
    try:
        prompt = transcribe_audio()
        case_number = classify_question(prompt)

        # Verificar si el caso es "CASO 3 - Red:" y obtener el nombre de la red
        red_name = "unknown"  # Valor por defecto para red_name
        if isinstance(case_number, str) and case_number.startswith("CASO 3 - Red:"):
            red_name = case_number.split("Red:")[1].strip()  # Obtener el nombre de la red
            case_number = 3  # Asignar el valor de case_number a 3
            print(f"Red clasificada: {red_name}")

        # Si es CASO 3 y la red no es 'unknown', obtener los valores de org_id y network_id
        if case_number == 3 and red_name != "unknown":
            # Cargar el JSON de organizaciones y redes
            organizaciones_y_redes = cargar_organizaciones_y_redes()

            # Buscar la organización y la red
            for org in organizaciones_y_redes:
                for network in org['networks']:
                    if network['name'] == red_name:
                        ORGANIZATION_ID = org['org_id']
                        NETWORK_ID = network['network_id']
                        print(f"ORGANIZATION_ID: {ORGANIZATION_ID}")
                        print(f"NETWORK_ID: {NETWORK_ID}")
                        break

        # Definir el contexto en función del caso
        global ASSISTANT_CONTEXT
        if case_number == 1:
            ASSISTANT_CONTEXT += additional_context
        elif case_number == 2:
            ASSISTANT_CONTEXT = agregar_json_al_contexto(splunk_json_file, ASSISTANT_CONTEXT)
        elif case_number == 3:
            # FALTA LLAMAR A LA FUNCION DE MERAKI_UTILS
            print(f"Organization ID{ORGANIZATION_ID}")
            obtener_datos_red(MERAKI_KEY, ORGANIZATION_ID, NETWORK_ID)
            ASSISTANT_CONTEXT = agregar_json_al_contexto(meraki_json_file, ASSISTANT_CONTEXT)

        # Interactuar con GPT-4 y obtener la respuesta
        response = interact_with_gpt4(prompt)

        # Convertir la respuesta a voz
        text_to_speech_with_polly(response)

    except Exception as e:
        print(f"Error en el flujo de transcripción y respuesta: {e}")


# GUI Setup
root = tk.Tk()
root.title("Asistente de Voz - Sophia")
label = tk.Label(root, text="Presiona el botón para hablar")
label.pack(pady=10)
record_button = tk.Button(root, text="Hablar", command=toggle_recording)
record_button.pack(pady=20)
root.mainloop()
