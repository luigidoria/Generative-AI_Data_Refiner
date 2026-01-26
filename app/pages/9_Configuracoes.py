import streamlit as st
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.auth_manager import AuthManager

st.set_page_config(
    page_title="Franq | Ingestão de Dados",
    page_icon=":bar_chart:",
    layout="wide"
)

st.markdown("""
    <style>
        [data-testid="stSidebarNav"] {
            display: none;
        }
    </style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("""
    **Como funciona:**
    1. Suba os arquivos CSV.
    2. O sistema valida os dados.
    3. A IA corrige erros automaticamente.
    4. Dados corrigidos são inseridos no banco.
    """)

    st.divider()
    origem = st.session_state.get("origem_config", "main.py")
    
    if "main" in origem:
        texto_botao = "Voltar para Início"
    elif "Correção" in origem:
        texto_botao = "Voltar para Correção"
    elif "Inserção" in origem:
        texto_botao = "Voltar para Inserção"
    else:
        texto_botao = "Voltar"

    if st.button(f"{texto_botao}", use_container_width=True):
        st.switch_page(origem)

st.title("Configurações do Sistema")
st.divider()

auth = AuthManager()
chave_atual = auth.obter_api_key()

if "msg_sucesso" in st.session_state:
    st.toast(st.session_state["msg_sucesso"], icon="✅", duration='short')
    del st.session_state["msg_sucesso"]

st.subheader("Credenciais da API (Groq)")

if chave_atual:
    st.success("API Key está configurada e ativa.")
    
    with st.expander("Gerenciar Chave"):
        st.info(f"Chave carregada: ...{chave_atual[-4:]}")
        if st.button("Remover Credenciais"):
            auth.limpar_credenciais()
            st.rerun()
else:
    st.warning("Nenhuma API Key encontrada.")

st.markdown("---")
st.write("### Atualizar Chave")

with st.form("form_auth"):
    nova_chave = st.text_input(
        "Insira sua Groq API Key", 
        type="password", 
        help="A chave será validada com uma requisição de teste."
    )
    submit = st.form_submit_button("Validar e Salvar")

if submit:
    if not nova_chave:
        st.error("Insira uma chave para continuar.")
    else:
        with st.spinner("Validando chave..."):
            valida, msg = auth.validar_api_key(nova_chave)
            
            if valida:
                salvou, msg_save = auth.salvar_api_key(nova_chave)
                st.session_state["msg_sucesso"] = f"{msg} | {msg_save}"
                st.rerun()
            else:
                st.error(f"Falha na validação: {msg}")