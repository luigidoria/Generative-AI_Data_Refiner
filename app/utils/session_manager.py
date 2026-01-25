import streamlit as st

def rest_all_states(state_padroes):
    db_status = st.session_state.get("banco_dados", False)
    st.session_state.clear()
    st.session_state["banco_dados"] = db_status
    for key, value in state_padroes.items():
        if key != "banco_dados":
            st.session_state[key] = value

def limpar_sessao_para_inicio():
    keys_to_clear = [
        "df_original", "df_corrigido", "validacao_aprovada",
        "resultado_validacao", "erros_validacao", "codigo_correcao_gerado",
        "hash_atual", "usou_cache_flag", "resultado_insercao",
        "duracao_insercao", "insercao_concluida", "confirmar_insercao",
        "sem_modficadoes_necessarias", "arquivo_erros", "codigo_gerado",
        "usou_cache", "hash_estrutura", "vezes_utilizado", "script_id_cache",
        "nome_arquivo"
    ]
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]