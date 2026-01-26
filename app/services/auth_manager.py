import os
from pathlib import Path
import streamlit as st
from dotenv import load_dotenv, set_key
from openai import OpenAI

ENV_PATH = Path(__file__).parent.parent / "secrets.env"

class AuthManager:
    def __init__(self):
        self.api_key = self.obter_api_key()

    def obter_api_key(self):
        if "GROQ_API_KEY" in st.session_state and st.session_state["GROQ_API_KEY"]:
            return st.session_state["GROQ_API_KEY"]
        
        load_dotenv(ENV_PATH, override=True)
        env_key = os.getenv("GROQ_API_KEY")
        
        if env_key:
            st.session_state["GROQ_API_KEY"] = env_key
            return env_key

        return None

    def validar_api_key(self, api_key_candidata=None):
        chave_teste = api_key_candidata if api_key_candidata else self.api_key

        if not chave_teste:
            return False, "Nenhuma chave fornecida para validação"

        try:
            client = OpenAI(
                base_url="https://api.groq.com/openai/v1",
                api_key=chave_teste
            )

            client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {
                        "role": "system",
                        "content": "Voce gera apenas codigo Python puro, sem formatacao Markdown."
                    },
                    {
                        "role": "user",
                        "content": "Teste de conexao"
                    }
                ],
                temperature=0.1,
                max_tokens=1, 
            )
            return True, "Chave valida e funcional"
            
        except Exception as e:
            msg = str(e)
            if "401" in msg:
                return False, "Erro 401: Chave invalida ou nao autorizada"
            return False, f"Erro de conexao: {msg}"

    def salvar_api_key(self, nova_api_key):
        self.api_key = nova_api_key
        st.session_state["GROQ_API_KEY"] = nova_api_key
        
        try:
            if not os.path.exists(ENV_PATH):
                open(ENV_PATH, 'a').close()
                
            set_key(ENV_PATH, "GROQ_API_KEY", nova_api_key)
            return True, "Chave salva na sessao e no arquivo secrets.env"
        except Exception:
            return False, "Chave salva apenas na sessao (sem permissao de escrita no arquivo)"

    def limpar_credenciais(self):
        self.api_key = None
        if "GROQ_API_KEY" in st.session_state:
            del st.session_state["GROQ_API_KEY"]