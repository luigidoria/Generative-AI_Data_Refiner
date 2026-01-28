from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from app.utils.data_handler import processar_arquivo
from app.services.logger import LogMonitoramento

class FileSession:
    def __init__(self, uploaded_file, file_id):
        self.id = file_id
        self.uploaded_file = uploaded_file
        self.nome = uploaded_file.name
        self.status = "PROCESSANDO"
        
        self.df_original = None
        self.df_corrigido = None
        self.validacao = None
        self.encoding = None
        self.delimitador = None
        self.cache_verificado = False
        self.resultado_insercao = None
        self.relatorio_visualizado = False
        self.fonte_correcao = None 
        
        self.logger = LogMonitoramento(uploaded_file) 

    def processar(self):
        try:
            self.df_original, self.encoding, self.delimitador, self.validacao = processar_arquivo(self.uploaded_file)
            
            if self.validacao["valido"]:
                self.status = "PRONTO_VALIDO"
                self.df_corrigido = self.df_original
                self.logger.registrar_conclusao(0, 0, 0)
            else:
                self.status = "PENDENTE_CORRECAO"
                self.logger.registrar_pendencia()
                
        except Exception as e:
            self.status = "FALHA_LEITURA"
            self.logger.registrar_erro("UPLOAD", "Excecao", str(e))
            raise e

    def update_ia_stats(self, tokens, fonte, economia=0):
        self.fonte_correcao = fonte
        self.logger.registrar_uso_ia(tokens, fonte, economia)
        
    def finalizar_insercao(self, resultado_dict, duracao):
        total_sucesso = resultado_dict.get("registros_inseridos", 0)
        total_erros_geral = len(resultado_dict.get("erros", []))
        erros_duplicados = resultado_dict.get("registros_duplicados", 0)
        erros_reais = total_erros_geral - erros_duplicados
        
        self.logger.registrar_conclusao(total_sucesso, erros_duplicados, erros_reais)
        
        self.resultado_insercao = resultado_dict
        self.resultado_insercao["duracao"] = duracao
        
        self.resultado_insercao["nome_arquivo"] = self.nome
        self.resultado_insercao["usou_ia"] = (self.fonte_correcao == "IA")
        
        self.status = "CONCLUIDO"

    def cancelar(self):
        self.logger.registrar_cancelamento()

    def __getitem__(self, key):
        return getattr(self, key)