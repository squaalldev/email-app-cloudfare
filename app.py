import time
import os
import uuid
import traceback
import joblib
import streamlit as st
from dotenv import load_dotenv
from streamlit.runtime.scriptrunner import get_script_run_ctx
from system_prompts import get_unified_email_prompt
from session_state import (
    SessionState,
    DEFAULT_GEMINI_MODEL,
    DATA_DIR,
)

# Inicializar el estado de la sesión
state = SessionState()
STREAM_SETTINGS = {'batch_size': 1, 'delay_seconds': 0.01}
user_past_chats_list_path = None

def get_user_namespace():
    """
    Obtiene un namespace para persistencia.
    - Si CHATBOT_USER_NAMESPACE está definido, se usa ese valor (recomendado para app de un solo usuario).
    - Si MULTI_USER_MODE=true, usa session_id para aislar por sesión.
    - Caso contrario, usa un user_id persistente en query params para aislar por usuario y sobrevivir reinicios.
    """
    configured_namespace = os.environ.get('CHATBOT_USER_NAMESPACE')
    if configured_namespace:
        return configured_namespace

    is_multi_user_mode = os.environ.get('MULTI_USER_MODE', 'false').strip().lower() == 'true'
    if is_multi_user_mode:
        context = get_script_run_ctx()
        if context and getattr(context, 'session_id', None):
            return context.session_id

    user_id = st.query_params.get('uid')
    if not user_id:
        user_id = uuid.uuid4().hex
        st.query_params['uid'] = user_id
    return f'user_{user_id}'

# Función para detectar saludos y generar respuestas personalizadas
def is_greeting(text):
    """Detecta si el texto es un saludo simple"""
    text = text.lower().strip()
    greetings = ['hola', 'hey', 'saludos', 'buenos días', 'buenas tardes', 'buenas noches', 'hi', 'hello']
    
    # Solo considerar como saludo si es el primer mensaje del usuario
    # y es un saludo simple
    is_simple_greeting = any(greeting in text for greeting in greetings) and len(text.split()) < 4
    return is_simple_greeting and len(state.messages) == 0

# Función para procesar mensajes (unifica la lógica de procesamiento)
def process_message(prompt, is_example=False):
    """Procesa un mensaje del usuario, ya sea directo o de un ejemplo"""
    handle_chat_title(prompt)
    
    with st.chat_message('user', avatar=USER_AVATAR_ICON):
        st.markdown(prompt)
    
    state.add_message('user', prompt, USER_AVATAR_ICON)
    
    # Obtener el prompt mejorado primero
    enhanced_prompt = get_enhanced_prompt(prompt, is_example)
    
    # Mover la respuesta del modelo después del mensaje del usuario
    with st.chat_message(MODEL_ROLE, avatar=AI_AVATAR_ICON):
        try:
            message_placeholder = st.empty()
            typing_indicator = st.empty()
            typing_indicator.markdown("*Generando respuesta...*")
            
            response = state.send_message(enhanced_prompt)
            full_response = stream_response(response, message_placeholder, typing_indicator, STREAM_SETTINGS)
            
            if full_response:
                state.add_message(MODEL_ROLE, full_response, AI_AVATAR_ICON)
                if hasattr(state.chat, 'get_history'):
                    state.gemini_history = state.chat.get_history()
                else:
                    state.gemini_history = getattr(state.chat, 'history', [])
                state.save_chat_history()
                
        except Exception as e:
            show_detailed_error("process_message", e)
            return

def show_detailed_error(context, error):
    """Muestra errores con contexto y traza para facilitar debug en producción."""
    st.error(f"Ocurrió un error en {context}. Intenta de nuevo.")
    with st.expander("Ver detalles técnicos del error"):
        st.code(f"{type(error).__name__}: {error}\n\n{traceback.format_exc()}")

def handle_chat_title(prompt):
    """Maneja la lógica del título del chat"""
    if state.chat_id not in past_chats:
        temp_title = f'SesiónChat-{state.chat_id}'
        generated_title = state.generate_chat_title(prompt)
        state.chat_title = generated_title or temp_title
        past_chats[state.chat_id] = state.chat_title
    else:
        state.chat_title = past_chats[state.chat_id]
    joblib.dump(past_chats, user_past_chats_list_path)

def get_enhanced_prompt(prompt, is_example):
    """Genera el prompt mejorado según el tipo de mensaje"""
    if is_greeting(prompt):
        return (
            "Responde ÚNICAMENTE con esta frase, sin agregar nada más: "
            "\"¡Perfecto! Empecemos por la primera: "
            "¿Quién es tu audiencia ideal para este correo? "
            "Descríbela con detalle (contexto, problema principal, deseo y nivel de conciencia).\""
        )
    elif is_example:
        return (
            f"El usuario seleccionó esta pregunta del menú: '{prompt}'. "
            "Respóndela de forma directa, útil y conversacional, con ejemplos concretos. "
            "Después de responder, invita al usuario a iniciar el flujo de 5 preguntas en este orden: audiencia, producto, nombre, CTA y ángulo."
        )
    return prompt

def stream_response(response, message_placeholder, typing_indicator, stream_settings):
    """Maneja el streaming de la respuesta"""
    full_response = ''
    batch_size = max(1, int(stream_settings.get('batch_size', 24)))
    delay_seconds = max(0.0, float(stream_settings.get('delay_seconds', 0.0)))
    pending_chars = 0

    try:
        for chunk in response:
            if chunk.text:
                for ch in chunk.text:
                    full_response += ch
                    pending_chars += 1
                    if pending_chars >= batch_size:
                        if delay_seconds:
                            time.sleep(delay_seconds)
                        message_placeholder.markdown(full_response + '▌')
                        pending_chars = 0
    except Exception as e:
        show_detailed_error("stream_response", e)
        return ''

    if pending_chars > 0:
        if delay_seconds:
            time.sleep(delay_seconds)
        message_placeholder.markdown(full_response + '▌')

    typing_indicator.empty()
    message_placeholder.markdown(full_response)
    return full_response

# Función para cargar CSS personalizado
def load_css(file_path):
    with open(file_path) as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

# Intentar cargar el CSS personalizado con ruta absoluta para mayor seguridad
try:
    css_path = os.path.join(os.path.dirname(__file__), 'static', 'css', 'style.css')
    load_css(css_path)
except Exception as e:
    print(f"Error al cargar CSS: {e}")
    # Si el archivo no existe, crear un estilo básico en línea
    st.markdown("""
    <style>
    .robocopy-title {
        color: white !important;
        font-weight: bold;
        font-size: clamp(2.5em, 5vw, 4em);
        line-height: 1.2;
    }
    </style>
    """, unsafe_allow_html=True)

# Función de utilidad para mostrar la carátula inicial
def display_initial_header():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        # Centrar la imagen
        st.markdown("""
            <style>
                div.stImage {
                    text-align: center;
                    display: block;
                    margin-left: auto;
                    margin-right: auto;
                }
            </style>
        """, unsafe_allow_html=True)
        st.image("robocopy_logo.png", width=300, use_container_width=True)
        
        # Título con diseño responsivo (eliminado el símbolo ∞)
        st.markdown("""
            <div style='text-align: center; margin-top: -35px; width: 100%;'>
                <h1 class='robocopy-title' style='width: 100%; text-align: center; color: white !important; font-size: clamp(2.5em, 5vw, 4em); line-height: 1.2;'>Email Story Creator</h1>
            </div>
        """, unsafe_allow_html=True)
        
        # Subtítulo con margen superior ajustado a -30px
        st.markdown("""
            <div style='text-align: center; width: 100%;'>
                <p style='font-size: 16px; color: white; width: 100%; text-align: center; margin-top: -20px;'>By Jesús Cabrera</p>
            </div>
        """, unsafe_allow_html=True)
    
    # Descripción con fondo eliminado y margen superior ajustado a -20px
    st.markdown("""
        <div style='text-align: center; width: 100%;'>
            <p style='font-size: 16px; background-color: transparent; padding: 12px; border-radius: 8px; margin-top: -20px; color: white; width: 100%; text-align: center;'>
                ✉️ Experto en emails narrativos que conectan historias con ventas de forma natural
            </p>
        </div>
    """, unsafe_allow_html=True)

# Función para mostrar ejemplos de preguntas
def display_examples():
    ejemplos = [
        {"texto": "Definir audiencia 🎯", "prompt": "Ayúdame a definir una audiencia concreta para este correo: dolor principal, deseo y nivel de conciencia."},
        {"texto": "Propuesta de valor 💎", "prompt": "Convierte mi producto en una promesa clara de transformación sin listar características aburridas."},
        {"texto": "CTA que convierte 🚀", "prompt": "Dame 3 opciones de CTA claras para este email, con baja fricción y orientadas a una sola acción."},
        {"texto": "Asunto + gancho ✉️", "prompt": "Propón 5 asuntos y 3 ganchos de apertura para aumentar aperturas y clics de este correo."}
    ]

    # Crear los botones de ejemplo
    cols = st.columns(4)
    for idx, ejemplo in enumerate(ejemplos):
        with cols[idx]:
            if st.button(ejemplo["texto"], key=f"ejemplo_{idx}", help=ejemplo["prompt"]):
                st.session_state.pending_example_prompt = ejemplo["prompt"]
                st.session_state.hide_initial_menu = True
                st.rerun()

# Cargar variables de entorno
load_dotenv()
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
if not GOOGLE_API_KEY:
    st.error("Falta la variable de entorno GOOGLE_API_KEY. Configúrala para continuar.")
    st.stop()

# Configuración de la aplicación
state.user_namespace = get_user_namespace()
user_past_chats_list_path = f'{DATA_DIR}/{state.user_namespace}/past_chats_list'
new_chat_id = f'{time.time()}'
MODEL_ROLE = 'ai'
AI_AVATAR_ICON = '🤖'  # Cambia el emoji por uno de robot para coincidir con tu logo
USER_AVATAR_ICON = '👤'  # Añade un avatar para el usuario

# Crear carpeta de datos si no existe
os.makedirs(f'{DATA_DIR}/{state.user_namespace}', exist_ok=True)

# Cargar chats anteriores
try:
    past_chats = joblib.load(user_past_chats_list_path)
except (FileNotFoundError, EOFError):
    past_chats = {}

# Sidebar para seleccionar chats anteriores
with st.sidebar:
    st.write('# Chats Anteriores')

    if state.chat_id is None:
        state.chat_id = new_chat_id

    if st.button('＋ Nuevo chat', key='new_chat_sidebar', use_container_width=True):
        state.chat_id = new_chat_id
        st.session_state.pending_example_prompt = None
        st.session_state.hide_initial_menu = False
        st.session_state.editing_chat_id = None
        st.rerun()

    st.caption('Sesiones')
    if 'editing_chat_id' not in st.session_state:
        st.session_state.editing_chat_id = None

    def chat_sort_key(chat_id):
        try:
            return float(chat_id)
        except (TypeError, ValueError):
            return 0.0

    sorted_chat_ids = sorted(past_chats.keys(), key=chat_sort_key, reverse=True)
    for index, chat_id in enumerate(sorted_chat_ids):
        chat_title = past_chats.get(chat_id, f'SesiónChat-{chat_id}')
        is_active_chat = chat_id == state.chat_id
        button_label = f'● {chat_title}' if is_active_chat else chat_title

        if st.button(
            button_label,
            key=f'chat_session_{index}_{chat_id}',
            use_container_width=True,
            type='primary' if is_active_chat else 'secondary',
        ):
            if state.chat_id != chat_id:
                state.chat_id = chat_id
                st.rerun()

    state.chat_title = past_chats.get(state.chat_id, f'SesiónChat-{state.chat_id}')

# Cargar historial del chat
state.load_chat_history()

if 'pending_example_prompt' not in st.session_state:
    st.session_state.pending_example_prompt = None

if 'hide_initial_menu' not in st.session_state:
    st.session_state.hide_initial_menu = False

if 'active_chat_id' not in st.session_state:
    st.session_state.active_chat_id = state.chat_id
elif st.session_state.active_chat_id != state.chat_id:
    st.session_state.active_chat_id = state.chat_id
    st.session_state.pending_example_prompt = None
    st.session_state.hide_initial_menu = state.has_messages()
    st.session_state.editing_chat_id = None

# Inicializar el modelo y el chat
system_prompt = get_unified_email_prompt()
if (
    st.session_state.get('initialized_model_name') != DEFAULT_GEMINI_MODEL
    or getattr(state, 'client', None) is None
):
    try:
        state.initialize_model(DEFAULT_GEMINI_MODEL, api_key=GOOGLE_API_KEY)
        st.session_state.initialized_model_name = DEFAULT_GEMINI_MODEL
    except Exception as e:
        show_detailed_error("initialize_model", e)
        st.stop()

should_reinitialize_chat = (
    state.chat is None
    or st.session_state.get('initialized_chat_id') != state.chat_id
    or st.session_state.get('initialized_system_prompt') != system_prompt
)
if should_reinitialize_chat:
    try:
        state.initialize_chat(system_instruction=system_prompt)
        st.session_state.initialized_chat_id = state.chat_id
        st.session_state.initialized_system_prompt = system_prompt
    except Exception as e:
        show_detailed_error("initialize_chat", e)
        st.stop()

# Mostrar mensajes del historial
for message in state.messages:
    with st.chat_message(
        name=message['role'],
        avatar=message.get('avatar'),
    ):
        st.markdown(message['content'])

# Capturar entrada del usuario antes de renderizar el menú inicial
user_prompt = st.chat_input('Escribe aquí tus instrucciones')

if state.has_messages():
    st.session_state.hide_initial_menu = True

# Renderizar menú inicial en un contenedor limpiable
initial_menu_container = st.container()
if (
    not st.session_state.hide_initial_menu
    and not state.has_messages()
    and not user_prompt
    and not st.session_state.pending_example_prompt
):
    with initial_menu_container:
        display_initial_header()
        display_examples()

# Procesar entrada del usuario (oculta el menú inmediatamente)
if user_prompt:
    st.session_state.hide_initial_menu = True
    initial_menu_container.empty()
    process_message(user_prompt, is_example=False)
    st.rerun()

# Procesar ejemplo seleccionado (oculta el menú inmediatamente)
if st.session_state.pending_example_prompt:
    initial_menu_container.empty()
    process_message(st.session_state.pending_example_prompt, is_example=True)
    st.session_state.pending_example_prompt = None
    st.rerun()
