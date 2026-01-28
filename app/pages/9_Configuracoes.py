import streamlit as st
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.auth_manager import AuthManager

st.set_page_config(page_title="Configurações", layout="wide")

if "msg_sucesso" in st.session_state:
    st.toast(st.session_state["msg_sucesso"])
    del st.session_state["msg_sucesso"]

st.markdown("""
    <style>
        [data-testid="stSidebarNav"] {display: none;}
        [data-testid="stSidebar"] {display: none;}
        [data-testid="collapsedControl"] {display: none;}
        footer {visibility: hidden;}
        [data-testid="stDeployButton"] {display: none !important;}
        [data-testid="stMainMenu"] {visibility: hidden !important;}
        header {background: transparent !important;}
        .block-container {padding-top: 2rem;}
        .stDeployButton {display: none !important;}
    </style>
""", unsafe_allow_html=True)

st.title("Configurações do Sistema")
st.markdown("Gerencie a conexão com a Inteligência Artificial.")

st.divider()

auth = AuthManager()
chave_atual = auth.obter_api_key()

with st.container(border=True):
    col_label, col_val = st.columns([1, 6])
    with col_label:
        st.markdown("**Status:**")
    with col_val:
        if chave_atual:
            st.markdown(":green[**Conectado**]")
        else:
            st.markdown(":red[**Desconectado**]")
            
    st.divider()

    if chave_atual:
        st.markdown(f"Chave configurada: `...{chave_atual[-4:]}`")
        st.caption("O sistema está pronto para uso.")
        
        if st.button("Remover Credenciais", type="secondary"):
            auth.limpar_credenciais()
            st.rerun()
    else:
        st.markdown("O processamento está pausado. Configure a chave de acesso abaixo.")

with st.container(border=True):
    st.subheader("Nova Credencial")
    
    with st.expander("Como obter minha chave de acesso?"):
        st.markdown("""
        1. Acesse o painel da **Groq Cloud** [clicando aqui](https://console.groq.com/keys).
        2. Faça login com sua conta **(escolha qualquer opção disponível na tela de login)**.
        3. Clique no botão **"Create API Key"**.
        4. Defina um nome para a chave (ex: `Franq-Ingestao`) e clique em Submit.
        5. Copie o código gerado (começa com `gsk_`) e cole no campo abaixo.
        """)
    
    with st.form("form_auth", clear_on_submit=True):
        col_input, col_btn = st.columns([4, 1], vertical_alignment="bottom")
        
        with col_input:
            nova_chave = st.text_input("Chave API", type="password", placeholder="gsk_...")
            
        with col_btn:
            submit = st.form_submit_button("Conectar", type="primary", width='stretch')

    if submit:
        if not nova_chave:
            st.error("O campo de chave não pode estar vazio.")
        else:
            with st.spinner("Validando conexão..."):
                valida, msg = auth.validar_api_key(nova_chave)
                
                if valida:
                    salvou, msg_save = auth.salvar_api_key(nova_chave)
                    st.session_state["msg_sucesso"] = "Conexão realizada com sucesso."
                    st.rerun()
                else:
                    st.error(f"Não foi possível conectar: {msg}")

st.divider()

col_vazio, col_voltar = st.columns([4, 1])

with col_voltar:
    origem = st.session_state.get("origem_config", "main.py")
    
    texto_voltar = "Voltar"
    if "main" in origem: texto_voltar = "Voltar ao Início"
    elif "Correção" in origem: texto_voltar = "Voltar à Correção"
    elif "Inserção" in origem: texto_voltar = "Voltar à Inserção"
    elif "Dashboard" in origem: texto_voltar = "Voltar ao Dashboard"

    if st.button(f"{texto_voltar}", width='stretch'):
        st.switch_page(origem)