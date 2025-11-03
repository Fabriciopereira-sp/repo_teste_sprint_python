Integrantes:
Fabrício Henrique Pereira RM563237
Leonardo José Pereira RM563065
Ícaro Jose dos Santos RM562403



Documentação de Setup do Sistema CRUD Python + Oracle

Contexto do Projeto (FIAP - Sprint 4)

Este documento visa guiar a configuração e a execução do sistema de Gerenciamento de Dados (CRUD) desenvolvido em Python. O projeto integra operações completas de Inclusão, Consulta, Atualização e Exclusão de registros, utilizando o banco de dados Oracle DB e consumindo a API ViaCEP para enriquecimento de dados.

1. Requisitos de Ambiente

Para a execução bem-sucedida da aplicação, é importante que o ambiente de trabalho atenda aos seguintes pré-requisitos:

Componente

Versão Mínima

Finalidade

Python

3.8+

Linguagem de desenvolvimento principal.

Conta Oracle DB

(Ativa)

Acesso ao esquema do banco de dados da FIAP (RM e Senha válidos).

Oracle Instant Client

(Compatível)

Biblioteca cliente necessária para a comunicação entre o Python e o servidor Oracle. (Configuração Crucial)

Cliente VPN FIAP

(Ativo)

Essencial para estabelecer conexão com a rede interna da FIAP, caso a execução seja remota.

🔑 Nota Crítica sobre o Instant Client: A falha de importação do módulo oracledb frequentemente está relacionada à ausência ou à configuração inadequada do Oracle Instant Client no sistema operacional.

2. Configuração de Dependências Python

O projeto requer a instalação de módulos específicos para manipulação de banco de dados e requisições web. Siga os passos abaixo, executando os comandos no Terminal ou Prompt de Comando na raiz do projeto:

2.1. Conexão com o Banco de Dados Oracle

Instala o driver oficial do Oracle para Python, necessário para todas as interações com o DB:

pip install oracledb


2.2. Integração com API Externa (ViaCEP)

Instala a biblioteca padrão para realizar requisições HTTP, utilizada para consulta de endereços via CEP:

pip install requests


3. Verificação de Acesso ao Banco de Dados

Um dos pontos de falha mais comuns é a conexão. É fundamental que as credenciais sejam validadas antes da execução:

Validação de Credenciais: Assegure-se de que o RM (usuário) e a Senha estejam inseridos corretamente e que a conta do banco de dados esteja ativa. Qualquer erro de digitação resultará no erro ORA-01017: invalid username/password; logon denied.

Ajuste das Constantes: Localize o arquivo de conexão ou o bloco de constantes no código (teste.py ou conexao.py) e confirme os valores:

# Configurações de conexão:
DB_USER = "seu_rm"      # Ex: "RM563237"
DB_PASSWORD = "sua_senha" # Ex: "270604"
DB_CONNECTION_STRING = "oracle.fiap.com.br:1521/ORCL" 


Conectividade: Se não estiver em ambiente de laboratório, garanta que a VPN da FIAP esteja devidamente conectada antes de tentar rodar o programa.

4. Procedimento de Execução

Após a conclusão das instalações e configurações, o sistema pode ser inicializado:

Diretório: Navegue no terminal para o diretório principal do projeto.

Comando de Execução: Inicie o programa principal:

python teste.py


Resultado Esperado: O MENU PRINCIPAL será exibido, permitindo acesso às operações de CRUD e aos Relatórios (incluindo a função de Exportar JSON).