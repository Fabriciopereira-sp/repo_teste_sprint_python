import os
import time
import requests
import json
import oracledb

# ====================================================================================
# CONFIGURAÇÃO DE AMBIENTE (AJUSTAR APENAS ESTE BLOCO)
# ====================================================================================

# -----------------------------------------------------------------------------------------------------
# ** ATENÇÃO: CONFIGURAÇÃO DO ORACLE INSTANT CLIENT **
# O CAMINHO FOI CORRIGIDO PARA O SEU AMBIENTE: C:\instantclient_23_9
try:
    oracledb.init_oracle_client(lib_dir="C:\\instantclient_23_9") 
except Exception as e:
    print("\n\n*** ERRO CRÍTICO NA CONEXÃO ORACLE ***")
    print(f"Não foi possível inicializar o Oracle Instant Client no caminho 'C:\\instantclient_23_9'.")
    print(f"Por favor, verifique se a pasta foi descompactada corretamente.")
    print(f"Detalhe do erro: {e}")
    input("\nPressione ENTER para sair...")
    exit()
# -----------------------------------------------------------------------------------------------------


# --- Constantes de Conexão ORACLE (AJUSTE CONFORME SEU RM) ---
# SUBSTITUA 'USUARIO_FIAP' e 'SENHA_FIAP' PELAS SUAS CREDENCIAIS
DB_USER = "RM563237" 
DB_PASSWORD = "270604"
DB_CONNECTION_STRING = "oracle.fiap.com.br:1521/ORCL" 

# --- Constante para Tabela ---
TABLE_NAME = "REGISTROS"

# ====================================================================================
# FUNÇÕES DE UTILIDADE
# ====================================================================================

def limpar_tela():
    """Limpa o console para melhor visualização."""
    os.system('cls' if os.name == 'nt' else 'clear')

def pausar(mensagem="Pressione ENTER para continuar..."):
    """Pausa a execução até o usuário pressionar ENTER."""
    input(f"\n{mensagem}")

def get_db_connection():
    """Tenta estabelecer e retornar a conexão com o Oracle DB."""
    try:
        connection = oracledb.connect(user=DB_USER, password=DB_PASSWORD, dsn=DB_CONNECTION_STRING)
        return connection
    except oracledb.Error as e:
        limpar_tela()
        print("\n" + "="*50)
        print("  ❌ ERRO FATAL: FALHA NA CONEXÃO COM O BANCO DE DADOS  ")
        print("="*50)
        print(f"Detalhe: {e}")
        print("\nVerifique se as credenciais (DB_USER/DB_PASSWORD) e a string de conexão estão corretas.")
        print("Certifique-se de estar conectado à VPN da FIAP, se necessário.")
        pausar()
        exit() # Encerra o programa se a conexão falhar
    
def consulta_cep(cep):
    """Consulta o ViaCEP para obter logradouro, tratando erros."""
    cep = ''.join(filter(str.isdigit, str(cep)))
    if len(cep) != 8:
        print("CEP inválido (deve ter 8 dígitos).")
        return None, None
    
    url = f"https://viacep.com.br/ws/{cep}/json/"
    print(f"Consultando API... {url}")

    try:
        response = requests.get(url)
        response.raise_for_status() # Lança exceção para códigos 4xx/5xx
        data = response.json()
        
        if data.get('erro'):
            print("❌ CEP não encontrado na base de dados do ViaCEP.")
            return None, None
            
        logradouro = data.get('logradouro', 'Logradouro não informado')
        return cep, logradouro

    except requests.exceptions.RequestException as e:
        print(f"❌ Erro ao consultar a API ViaCEP: {e}")
        return None, None
    except Exception as e:
        print(f"❌ Erro inesperado: {e}")
        return None, None


# ====================================================================================
# FUNÇÕES CRUD (CREATE, READ, UPDATE, DELETE)
# ====================================================================================

# --------------------
# C - CREATE (CADASTRAR)
# --------------------
def cadastrar_registro():
    limpar_tela()
    print("="*30)
    print("  1. CADASTRAR NOVO REGISTRO  ")
    print("="*30)
    
    nome = input("Digite o NOME do registro: ").strip()
    if not nome:
        print("❌ Nome não pode ser vazio.")
        pausar()
        return

    descricao = input("Digite a DESCRIÇÃO: ").strip()
    
    # 1. Consulta à API ViaCEP
    cep_input = input("Digite o CEP (para buscar o Logradouro): ").strip()
    cep, logradouro = consulta_cep(cep_input)

    if not logradouro:
        print("❌ Cadastro cancelado. CEP inválido ou não encontrado.")
        pausar()
        return
        
    print(f"\n✅ Logradouro encontrado: {logradouro}")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 2. Execução do INSERT
    try:
        # SQL para inserir dados e obter o próximo ID da SEQUENCE
        sql = f"""
        INSERT INTO {TABLE_NAME} (ID, NOME, DESCRICAO, CEP, LOGRADOURO, CRIADO_EM, ATUALIZADO_EM)
        VALUES (REGISTROS_SEQ.NEXTVAL, :1, :2, :3, :4, SYSDATE, SYSDATE)
        RETURNING ID INTO :id_saida
        """
        id_saida = cursor.var(oracledb.NUMBER)
        
        cursor.execute(sql, [nome, descricao, cep, logradouro, id_saida])
        conn.commit()
        
        print("\n" + "="*50)
        print(f"✅ REGISTRO CADASTRADO COM SUCESSO! ID: {id_saida.getvalue()[0]}")
        print(f"Logradouro salvo: {logradouro}")
        print("="*50)

    except oracledb.Error as e:
        print(f"❌ Erro ao cadastrar no banco de dados: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()
    
    pausar()

# --------------------
# R - READ (LISTAR/BUSCAR)
# --------------------
def fetch_all_registros(ativo_apenas=False):
    """Busca e retorna todos os registros ou apenas os ATIVOS."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    sql = f"SELECT ID, NOME, DESCRICAO, CEP, LOGRADOURO, ATIVO FROM {TABLE_NAME}"
    
    if ativo_apenas:
        sql += " WHERE ATIVO = 1"
    
    sql += " ORDER BY ID"

    try:
        cursor.execute(sql)
        registros = cursor.fetchall()
        colunas = [col[0] for col in cursor.description]
        
        registros_formatados = []
        for reg in registros:
            registro = dict(zip(colunas, reg))
            # Formatando a coluna ATIVO
            registro['ATIVO'] = 'SIM' if registro['ATIVO'] == 1 else 'NÃO'
            registros_formatados.append(registro)

        return registros_formatados

    except oracledb.Error as e:
        print(f"❌ Erro ao buscar registros: {e}")
        return []
    finally:
        cursor.close()
        conn.close()

def exibir_registros(registros, titulo):
    """Função de utilidade para imprimir a tabela de registros."""
    limpar_tela()
    print("=" * 60)
    print(f"  {titulo.upper()} ({len(registros)} registros)")
    print("=" * 60)
    
    if not registros:
        print("Nenhum registro encontrado.")
        pausar()
        return

    # Cabeçalho da tabela
    print(f"{'ID':<4} | {'ATIVO':<5} | {'NOME':<20} | {'DESCRIÇÃO':<20} | {'LOGRADOURO (ViaCEP)':<30}")
    print("-" * 100)

    for r in registros:
        print(f"{r['ID']:<4} | {r['ATIVO']:<5} | {r['NOME'][:19]:<20} | {r['DESCRICAO'][:19]:<20} | {r['LOGRADOURO'][:29]:<30}")
        
    pausar()


def buscar_registro_menu():
    """Menu para buscar um registro específico por ID."""
    limpar_tela()
    print("="*30)
    print("  4. BUSCAR REGISTRO POR ID  ")
    print("="*30)

    try:
        registro_id = int(input("Digite o ID do registro que deseja buscar: "))
    except ValueError:
        print("❌ ID deve ser um número inteiro.")
        pausar()
        return

    registro = fetch_registro_by_id(registro_id)
    
    if registro:
        limpar_tela()
        print("\n" + "="*50)
        print(f"  ✅ REGISTRO ENCONTRADO (ID: {registro['ID']})")
        print("="*50)
        print(f"Nome: {registro['NOME']}")
        print(f"Descrição: {registro['DESCRICAO']}")
        print(f"CEP: {registro['CEP']}")
        print(f"Logradouro (ViaCEP): {registro['LOGRADOURO']}")
        print(f"Status (Ativo): {'SIM' if registro['ATIVO'] == 1 else 'NÃO'}")
        print("="*50)
    else:
        print(f"❌ Nenhum registro encontrado com o ID: {registro_id}")
    
    pausar()

def fetch_registro_by_id(registro_id):
    """Busca um único registro pelo ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    sql = f"SELECT ID, NOME, DESCRICAO, CEP, LOGRADOURO, ATIVO FROM {TABLE_NAME} WHERE ID = :1"
    
    try:
        cursor.execute(sql, [registro_id])
        registro = cursor.fetchone()
        
        if registro:
            colunas = [col[0] for col in cursor.description]
            return dict(zip(colunas, registro))
        return None

    except oracledb.Error as e:
        print(f"❌ Erro ao buscar registro: {e}")
        return None
    finally:
        cursor.close()
        conn.close()

# --------------------
# U - UPDATE (ATUALIZAR)
# --------------------
def atualizar_registro():
    limpar_tela()
    print("="*30)
    print("  5. ATUALIZAR REGISTRO  ")
    print("="*30)

    try:
        registro_id = int(input("Digite o ID do registro que deseja atualizar: "))
    except ValueError:
        print("❌ ID deve ser um número inteiro.")
        pausar()
        return

    registro = fetch_registro_by_id(registro_id)
    if not registro:
        print(f"❌ Nenhum registro encontrado com o ID: {registro_id}")
        pausar()
        return

    # Exibe dados atuais
    print("\n--- Dados Atuais ---")
    print(f"1. Nome: {registro['NOME']}")
    print(f"2. Descrição: {registro['DESCRICAO']}")
    print(f"3. CEP: {registro['CEP']}")
    print(f"   Logradouro: {registro['LOGRADOURO']}")
    print("--------------------")

    # Coleta novos dados
    novo_nome = input(f"Novo NOME (atual: {registro['NOME']}): ").strip() or registro['NOME']
    nova_descricao = input(f"Nova DESCRIÇÃO (atual: {registro['DESCRICAO']}): ").strip() or registro['DESCRICAO']
    novo_cep = input(f"Novo CEP (deixe em branco para manter {registro['CEP']}): ").strip() or registro['CEP']

    logradouro_final = registro['LOGRADOURO']
    
    # Verifica se o CEP mudou e consulta a API novamente
    if novo_cep != registro['CEP']:
        cep_validado, novo_logradouro = consulta_cep(novo_cep)
        if novo_logradouro:
            novo_cep = cep_validado
            logradouro_final = novo_logradouro
        else:
            print("CEP inválido/não encontrado. Mantendo o CEP e Logradouro anteriores.")
            novo_cep = registro['CEP']
            logradouro_final = registro['LOGRADOURO']

    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Execução do UPDATE
    try:
        sql = f"""
        UPDATE {TABLE_NAME}
        SET NOME = :1, 
            DESCRICAO = :2, 
            CEP = :3, 
            LOGRADOURO = :4,
            ATUALIZADO_EM = SYSDATE
        WHERE ID = :5
        """
        cursor.execute(sql, [novo_nome, nova_descricao, novo_cep, logradouro_final, registro_id])
        conn.commit()
        
        print("\n" + "="*50)
        print(f"✅ REGISTRO ID {registro_id} ATUALIZADO COM SUCESSO!")
        if novo_cep != registro['CEP']:
             print(f"Novo Logradouro salvo: {logradouro_final}")
        print("="*50)

    except oracledb.Error as e:
        print(f"❌ Erro ao atualizar no banco de dados: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

    pausar()

def alternar_ativo():
    """Alterna o status ATIVO/INATIVO (Soft Delete)."""
    limpar_tela()
    print("="*40)
    print("  6. INATIVAR/ATIVAR REGISTRO (STATUS)  ")
    print("="*40)

    try:
        registro_id = int(input("Digite o ID do registro: "))
    except ValueError:
        print("❌ ID deve ser um número inteiro.")
        pausar()
        return

    registro = fetch_registro_by_id(registro_id)
    if not registro:
        print(f"❌ Nenhum registro encontrado com o ID: {registro_id}")
        pausar()
        return

    status_atual = 'ATIVO' if registro['ATIVO'] == 1 else 'INATIVO'
    novo_status_db = 0 if registro['ATIVO'] == 1 else 1 # 0 = INATIVO, 1 = ATIVO
    novo_status_texto = 'INATIVO' if novo_status_db == 0 else 'ATIVO'
    
    print(f"\nRegistro {registro_id}: {registro['NOME']} (Status atual: {status_atual})")
    confirmacao = input(f"Confirma a alteração do status para {novo_status_texto}? (S/N): ").strip().upper()

    if confirmacao != 'S':
        print("Operação cancelada.")
        pausar()
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        sql = f"""
        UPDATE {TABLE_NAME}
        SET ATIVO = :1, ATUALIZADO_EM = SYSDATE
        WHERE ID = :2
        """
        cursor.execute(sql, [novo_status_db, registro_id])
        conn.commit()
        
        print("\n" + "="*50)
        print(f"✅ REGISTRO ID {registro_id} ALTERADO PARA STATUS: {novo_status_texto}!")
        print("="*50)

    except oracledb.Error as e:
        print(f"❌ Erro ao alterar status no banco: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

    pausar()
    
# --------------------
# D - DELETE (EXCLUIR)
# --------------------
def excluir_registro():
    limpar_tela()
    print("="*30)
    print("  7. EXCLUIR REGISTRO (DEFINITIVO)  ")
    print("="*30)

    try:
        registro_id = int(input("Digite o ID do registro que deseja EXCLUIR: "))
    except ValueError:
        print("❌ ID deve ser um número inteiro.")
        pausar()
        return

    registro = fetch_registro_by_id(registro_id)
    if not registro:
        print(f"❌ Nenhum registro encontrado com o ID: {registro_id}")
        pausar()
        return
    
    print(f"\nRegistro: {registro['ID']} - {registro['NOME']} ({registro['DESCRICAO']})")
    print("🚨 AVISO: Esta operação é IRREVERSÍVEL (DELETE FROM)!")
    confirmacao = input("Confirma a EXCLUSÃO DEFINITIVA? (DIGITE 'SIM' para confirmar): ").strip().upper()

    if confirmacao != 'SIM':
        print("Exclusão cancelada.")
        pausar()
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        sql = f"DELETE FROM {TABLE_NAME} WHERE ID = :1"
        cursor.execute(sql, [registro_id])
        conn.commit()
        
        if cursor.rowcount > 0:
            print("\n" + "="*50)
            print(f"✅ REGISTRO ID {registro_id} EXCLUÍDO DEFINITIVAMENTE!")
            print("="*50)
        else:
            print(f"❌ Não foi possível excluir o registro ID {registro_id}.")


    except oracledb.Error as e:
        print(f"❌ Erro ao excluir no banco de dados: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

    pausar()
    
# ====================================================================================
# FUNÇÕES DE RELATÓRIO E EXPORTAÇÃO
# ====================================================================================

def exportar_para_json():
    """Exporta todos os registros ativos para um arquivo JSON."""
    limpar_tela()
    print("="*40)
    print("  EXPORTAÇÃO DE DADOS PARA JSON  ")
    print("="*40)
    
    # Busca apenas os registros ATIVOS
    registros = fetch_all_registros(ativo_apenas=True)
    
    if not registros:
        print("❌ Não há registros ATIVOS para exportar.")
        pausar()
        return

    filepath = "export_registros_ativos.json"
    
    # Remove a coluna 'ATIVO' para o JSON, pois já é implícito que são ativos
    dados_para_json = []
    for reg in registros:
        temp_reg = reg.copy()
        temp_reg.pop('ATIVO')
        dados_para_json.append(temp_reg)

    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            # Garante que o JSON seja formatado de forma legível (indent=4)
            json.dump(dados_para_json, f, ensure_ascii=False, indent=4)
        
        print("\n" + "="*50)
        print(f"✅ EXPORTAÇÃO CONCLUÍDA!")
        print(f"Registros exportados: {len(dados_para_json)}")
        print(f"Arquivo salvo em: {filepath}")
        print("="*50)

    except Exception as e:
        print(f"❌ Erro ao salvar o arquivo JSON: {e}")

    pausar()

# ====================================================================================
# MENUS
# ====================================================================================

def crud_menu():
    """Menu para operações CRUD."""
    while True:
        limpar_tela()
        print("="*30)
        print("  MENU CRUD - OPERAÇÕES  ")
        print("="*30)
        print("1. Cadastrar NOVO Registro (Inclui consulta à API)")
        print("2. Atualizar Registro")
        print("3. Inativar/Ativar Registro (Status)")
        print("4. Excluir Registro (Definitivo)")
        print("0. Voltar ao Menu Principal")
        print("="*30)
        
        op = input("Opção: ").strip()
        
        if op == "1":
            cadastrar_registro()
        elif op == "2":
            atualizar_registro()
        elif op == "3":
            alternar_ativo()
        elif op == "4":
            excluir_registro()
        elif op == "0":
            return
        else:
            print("Opção inválida!")
            pausar("Pressione ENTER para tentar novamente...")

def relatorios_menu():
    """Menu para listagens e exportação de dados."""
    while True:
        limpar_tela()
        print("="*40)
        print("  MENU RELATÓRIOS E EXPORTAÇÃO  ")
        print("="*40)
        print("1. Listar TODOS os Registros (Ativos e Inativos)")
        print("2. Listar Apenas Registros ATIVOS")
        print("3. Buscar Registro por ID")
        print("4. Exportar Registros ATIVOS para JSON")
        print("0. Voltar ao Menu Principal")
        print("="*40)
        
        op = input("Opção: ").strip()
        
        if op == "1":
            registros = fetch_all_registros(ativo_apenas=False)
            exibir_registros(registros, "Todos os Registros")
        elif op == "2":
            registros = fetch_all_registros(ativo_apenas=True)
            exibir_registros(registros, "Registros ATIVOS")
        elif op == "3":
            buscar_registro_menu()
        elif op == "4":
            exportar_para_json()
        elif op == "0":
            return
        else:
            print("Opção inválida!")
            pausar("Pressione ENTER para tentar novamente...")
            
def menu_principal():
    """Menu principal do sistema (Simplificado)."""
    while True:
        limpar_tela()
        # O cabeçalho foi simplificado conforme solicitado
        print("="*60)
        print("                 PROJETO INOVAREA                 ")
        print("="*60)
        print("\n  MENU PRINCIPAL:")
        print("1. Operações CRUD (Cadastrar, Alterar, Excluir)")
        print("2. Relatórios (Listas, Buscar, Exportar JSON)")
        print("0. Sair")
        print("="*60)
        
        op = input("Opção: ").strip()
        
        if op == "1":
            crud_menu()
        elif op == "2":
            relatorios_menu()
        elif op == "0":
            limpar_tela()
            print("Saindo do InovaREA. Até a próxima!")
            break
        else:
            print("Opção inválida!")
            pausar()

# ====================================================================================
# EXECUÇÃO PRINCIPAL
# ====================================================================================

if __name__ == "__main__":
    
    # 1. Verificação de dependências
    try:
        import requests
    except ImportError:
        limpar_tela()
        print("\n*** ERRO: O módulo 'requests' (para API) não está instalado.")
        print("Execute no terminal: pip install requests")
        pausar()
        exit()

    menu_principal()


