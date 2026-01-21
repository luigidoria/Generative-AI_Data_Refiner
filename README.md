Markdown

# Desafio Técnico: Pipeline de Ingestão CSV com IA

Solução desenvolvida para o desafio de automação e ingestão de dados financeiros utilizando Python e Streamlit.

## Estrutura do Projeto

O projeto segue a estrutura modular sugerida para organizar a interface, serviços e utilitários:

```text
app/
├── __init__.py
├── main.py          # Ponto de entrada do Streamlit
├── components/      # Componentes da UI
├── services/        # Lógica de negócio (IA, banco, etc)
└── utils/           # Funções auxiliares
```

## Configuração do Ambiente
Siga os passos abaixo para criar o ambiente virtual isolado e instalar as dependências.

1. Criar e Ativar Ambiente Virtual

    Windows:
    ```Bash
    python -m venv venv
    .\venv\Scripts\activate
    ```

    Linux / macOS:
    ```Bash
    python3 -m venv venv
    source venv/bin/activate
    ```
2. Instalar Dependências
Com o ambiente virtual ativo, instale as bibliotecas listadas no requirements.txt:

    ```Bash
    pip3 install -r requirements.txt
    ```

## Como Executar
Para iniciar a aplicação web, execute o comando abaixo na raiz do projeto:

```Bash
streamlit run app/main.py
```