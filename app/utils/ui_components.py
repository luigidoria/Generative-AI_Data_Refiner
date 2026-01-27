import streamlit as st
import pandas as pd

def formatar_titulo_erro(tipo_erro):
    titulos = {
        'nomes_colunas': 'Nomes das Colunas Incorretos',
        'formato_valor': 'Formato de Valor Monetário Inválido',
        'formato_data': 'Formato de Data Inválido',
        'colunas_faltando': 'Colunas Obrigatórias Ausentes'
    }
    return titulos.get(tipo_erro, 'Erro de Validação')

def exibir_preview(df):
    col1, col2, col3 = st.columns(3)
    col1.metric("Total de Registros", len(df))
    col2.metric("Colunas", len(df.columns))
    
    if "valor" in df.columns:
        valor_total = df["valor"].sum()
        col3.metric("Valor Total", f"R$ {valor_total:,.2f}")

    st.divider()
    st.caption("Visualização completa dos dados (role para ver mais):")

    st.dataframe(
        df,
        width='stretch',
        height=400,
        hide_index=True,
        column_config={
            "valor": st.column_config.NumberColumn(
                "Valor", format="R$ %.2f"
            )
        }
    )    
    st.divider()

def exibir_relatorio(resultado, duracao):
    registros_inseridos = resultado.get("registros_inseridos", 0)
    
    if registros_inseridos > 0:
        st.success("Dados processados com sucesso!")
    else:
        st.warning("O processo rodou, mas nenhum registro novo foi inserido.")

    st.divider()
    st.subheader("Relatório de Inserção")

    duplicados = resultado.get("registros_duplicados", 0)
    erros_lista = resultado.get("erros", [])

    erros_reais = [e for e in erros_lista if "duplicado" not in str(e.get("erro", "")).lower()]
    duplicados_lista = [e for e in erros_lista if "duplicado" in str(e.get("erro", "")).lower()]

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Processado", resultado.get("total_registros", 0))
    c2.metric("Inseridos", registros_inseridos)
    c3.metric("Rejeitados", len(erros_lista))

    c4, c5, c6 = st.columns(3)
    c4.metric("Arquivo", resultado.get("nome_arquivo", "N/A"))
    
    origem_script = resultado.get("origem_script", "Não utilizado")
    c5.metric("Origem do Script", origem_script)
    
    c6.metric("Tempo", f"{duracao:.2f}s")

    st.divider()

    if duplicados_lista:
        st.info(f"{len(duplicados_lista)} registros já existiam no banco e foram ignorados.")
        with st.expander("Ver Registros Duplicados"):
            st.dataframe(pd.DataFrame(duplicados_lista), width='stretch')

    if erros_reais:
        st.error(f"{len(erros_reais)} registros falharam na inserção.")
        with st.expander("Ver Detalhes dos Erros", expanded=True):
            st.dataframe(
                pd.DataFrame(erros_reais),
                width='stretch',
                column_config={
                    "erro": st.column_config.TextColumn("Motivo do Erro", width="large")
                }
            )

def preparar_retorno_ia(arquivo, msg_erro):
    st.session_state[f"ignore_cache_{arquivo.id}"] = True
    st.session_state["erro_anterior"] = f"Falha na inserção: {msg_erro}"
    
    if f"code_gen_{arquivo.id}" in st.session_state:
        st.session_state["script_anterior"] = st.session_state[f"code_gen_{arquivo.id}"]
    
    if "erro_insercao_critico" in st.session_state:
        del st.session_state["erro_insercao_critico"]
        
    arquivo.status = "PENDENTE_CORRECAO"
    st.switch_page("pages/2_Correção_IA.py")

def ir_para_dashboard():
    st.session_state["fila_arquivos"] = []
    st.session_state["pagina_anterior"] = "main.py"
    st.switch_page("pages/4_Dashboard.py")