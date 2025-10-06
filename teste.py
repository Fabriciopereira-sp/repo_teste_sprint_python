# =========================================================
# InovaREA - CRUD com Oracle Database (FIAP) e API Externa
# Sprint 4 – Computational Thinking Using Python
# Requisitos: CRUD, Oracle DB, API ViaCEP, Export JSON
# =========================================================

import oracledb # Módulo para conectar ao Oracle
import json
import os
import re
from datetime import datetime
import requests # Módulo para fazer requisições HTTP para a API
import time

# --- Constantes de Conexão ORACLE (CONFIGURADAS) ---
# **Importante**: Use as suas credenciais se estas não funcionarem.
USER = "rm563237"
PASSWORD = "270604"
# Hostname:oracle.fiap.com.br, Port:1521/ORCL
CONNECT_STRING = "oracle.fiap.com.br:1521/ORCL" 

# --- Outras Constantes ---
LOG_FILE = "log.txt"
CEP_API_URL = "https://viacep.com.br/ws/{cep}/json/"

# -----------------------------
# Funções de Apoio e Banco de Dados ORACLE
# -----------------------------
def get_db_connection():
    """Cria e retorna a conexão com o Oracle DB."""
    try:
        # Tenta a conexão usando as credenciais fornecidas
        conn = oracledb.connect(user=USER, password=PASSWORD, dsn=CONNECT_STRING)
        return conn
    except oracledb.Error as e:
        log("ERRO_CONEXAO_DB", f"Falha na conexão Oracle: {e}")
        print("\n*** ERRO CRÍTICO DE CONEXÃO AO ORACLE ***")
        print("Certifique-se de que o Instant Client está instalado e configurado no PATH.")
        print(f"Verifique suas credenciais e se a Tabela/Sequence foram criadas no SQL Developer.")
        return None

def setup_db():
    """Tenta estabelecer a conexão ao iniciar para verificar a saúde do sistema."""
    conn = get_db_connection()
    if conn:
        log("SETUP_DB", "Conexão Oracle estabelecida com sucesso.")
        conn.close()
    else:
        log("SETUP_DB", "Falha ao estabelecer conexão Oracle.")
        
def log(acao, detalhe=""):
    """Escreve log no console e em arquivo"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    linha = f"{ts} | {acao} | {detalhe}"
    print(f"[LOG] {linha}")
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(linha + "\n")
    except Exception:
        pass

# Funções de validação e utilitários
def validar_nome(nome):
    if not isinstance(nome, str): return False
    nome = nome.strip()
    return 2 <= len(nome) <= 60 and bool(re.search(r"[A-Za-z0-9À-ÿ]", nome))

def validar_descricao(desc):
    if not isinstance(desc, str): return False
    return 3 <= len(desc.strip()) <= 200
    
def validar_cep(cep):
    return re.fullmatch(r"^\d{8}$", str(cep).replace('-', '').strip())

def pausar():
    input("\nPressione ENTER para continuar...")

def get_total_registros():
    """Retorna o número total e o status dos registros do Oracle."""
    conn = get_db_connection()
    if not conn: return 0, 0, 0

    total, ativos, inativos = 0, 0, 0
    try:
        cursor = conn.cursor()
        total = cursor.execute("SELECT COUNT(ID) FROM REGISTROS").fetchone()[0]
        ativos = cursor.execute("SELECT COUNT(ID) FROM REGISTROS WHERE ATIVO = 1").fetchone()[0]
        inativos = total - ativos
        return total, ativos, inativos
    except oracledb.Error as e:
        log("ERRO_TOTAL", str(e))
        return 0, 0, 0
    finally:
        conn.close()

def dashboard():
    """Mostra estatísticas rápidas do BD."""
    total, ativos, inativos = get_total_registros()
    print("\n" + "=" * 60)
    print(" " * 15 + "DASHBOARD DE REGISTROS (ORACLE DB)")
    print("=" * 60)
    print(f"Total de Registros (RM{USER[-6:]}): {total}")
    print(f"Ativos: {ativos} | Inativos: {inativos}")
    print("-" * 60)

# -----------------------------
# 1. Integração com API Externa (ViaCEP)
# -----------------------------
def consultar_cep_api(cep):
    """Consulta o ViaCEP para obter informações de endereço."""
    if not validar_cep(cep):
        return None, "CEP inválido. Deve ter 8 dígitos."
    
    cep_limpo = cep.replace('-', '').strip()
    url = CEP_API_URL.format(cep=cep_limpo)
    
    log("API_CALL", f"Consultando CEP {cep_limpo}")
    
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status() 
        data = response.json()
        
        if data.get('erro'):
            log("API_RESPONSE", "CEP não encontrado.")
            return None, "CEP não encontrado na base do ViaCEP."
            
        endereco = {
            "cep": data.get('cep'),
            "logradouro": data.get('logradouro') or "Não Informado",
        }
        log("API_RESPONSE", f"Logradouro encontrado: {endereco['logradouro']}")
        return endereco, None

    except requests.exceptions.RequestException as e:
        log("ERRO_API", f"Falha na consulta do CEP: {e}")
        return None, "Erro ao conectar com a API de CEP (ViaCEP)."


# -----------------------------
# 2. CRUD com Oracle DB
# -----------------------------

def cadastrar(nome, descricao, cep):
    """Adiciona um novo registro e consulta a API de CEP."""
    if not validar_nome(nome): return "Erro: Nome inválido."
    if not validar_descricao(descricao): return "Erro: Descrição inválida."
    
    endereco, erro_api = consultar_cep_api(cep)
    logradouro = "Erro na API/CEP Inválido" if erro_api else endereco.get('logradouro')

    if erro_api and not validar_cep(cep):
         return "Erro: CEP inválido. Use 8 dígitos e garanta a conexão."
         
    conn = get_db_connection()
    if not conn: return "Falha na conexão com o Oracle."
    
    try:
        cursor = conn.cursor()
        
        # O Oracle usa SEQUENCE para gerar IDs automáticos
        sql = """
            INSERT INTO REGISTROS (ID, NOME, DESCRICAO, CEP, LOGRADOURO, ATIVO, CRIADO_EM)
            VALUES (REGISTROS_SEQ.NEXTVAL, :nome, :descricao, :cep, :logradouro, 1, :criado_em)
        """
        
        params = {
            'nome': nome.strip(), 
            'descricao': descricao.strip(), 
            'cep': cep.strip(), 
            'logradouro': logradouro, 
            'criado_em': datetime.now().isoformat(timespec="seconds")
        }
        
        cursor.execute(sql, params)
        conn.commit() # Confirma a transação no Oracle
        return f"Registro '{nome}' cadastrado no Oracle. Logradouro (via API): {logradouro}"
    except oracledb.Error as e:
        log("ERRO_CADASTRAR", str(e))
        return f"Erro ao cadastrar no Oracle DB: {e}"
    finally:
        conn.close()


def listar(modo="ativos"):
    """Lista registros conforme o modo: 'ativos', 'inativos' ou 'todos'."""
    conn = get_db_connection()
    if not conn: return "Falha na conexão com o Oracle."
    
    try:
        if modo == "ativos":
            query = "SELECT ID, NOME, DESCRICAO, ATIVO, CEP, LOGRADOURO FROM REGISTROS WHERE ATIVO = 1 ORDER BY ID DESC"
        elif modo == "inativos":
            query = "SELECT ID, NOME, DESCRICAO, ATIVO, CEP, LOGRADOURO FROM REGISTROS WHERE ATIVO = 0 ORDER BY ID DESC"
        else: # 'todos'
            query = "SELECT ID, NOME, DESCRICAO, ATIVO, CEP, LOGRADOURO FROM REGISTROS ORDER BY ID DESC"
            
        cursor = conn.cursor()
        cursor.execute(query)
        # Extrai os nomes das colunas e os dados
        columns = [col[0] for col in cursor.description]
        itens = [dict(zip(columns, row)) for row in cursor]

        if not itens:
            return "Nenhum registro encontrado."

        saida = ["\n=== LISTA DE REGISTROS (ORACLE) ==="]
        for r in itens:
            status = "ATIVO" if r['ATIVO'] == 1 else "INATIVO"
            saida.append(f"ID: {r['ID']} | {r['NOME']} | Status: {status} | CEP: {r['CEP']} | Logradouro: {r['LOGRADOURO']}")
        return "\n".join(saida)
    
    except oracledb.Error as e:
        log("ERRO_LISTAR", str(e))
        return f"Erro ao listar do Oracle DB: {e}"
    finally:
        conn.close()


def buscar(termo):
    """Busca por ID ou termo no nome/descrição/logradouro."""
    termo = str(termo).strip().upper() 
    conn = get_db_connection()
    if not conn: return "Falha na conexão com o Oracle."
    
    try:
        query = """
            SELECT ID, NOME, DESCRICAO, ATIVO, CEP, LOGRADOURO 
            FROM REGISTROS 
            WHERE TO_CHAR(ID) = :termo 
               OR UPPER(NOME) LIKE :like_termo 
               OR UPPER(DESCRICAO) LIKE :like_termo
               OR UPPER(LOGRADOURO) LIKE :like_termo
            ORDER BY ID DESC
        """
        like_termo = f'%{termo}%'
        
        cursor = conn.cursor()
        cursor.execute(query, {'termo': termo, 'like_termo': like_termo})
        columns = [col[0] for col in cursor.description]
        itens = [dict(zip(columns, row)) for row in cursor]
        
        if not itens:
            return "Nenhum registro encontrado."

        saida = ["\n=== RESULTADOS DA BUSCA (ORACLE) ==="]
        for r in itens:
            status = "ATIVO" if r['ATIVO'] == 1 else "INATIVO"
            saida.append(f"ID: {r['ID']} | {r['NOME']} | Status: {status} | CEP: {r['CEP']} | Logradouro: {r['LOGRADOURO']}")
        return "\n".join(saida)
    
    except oracledb.Error as e:
        log("ERRO_BUSCAR", str(e))
        return f"Erro ao buscar no Oracle DB: {e}"
    finally:
        conn.close()


def atualizar(id_registro, novo_nome, nova_descricao, novo_cep):
    """Atualiza um registro existente."""
    conn = get_db_connection()
    if not conn: return "Falha na conexão com o Oracle."
    
    try:
        cursor = conn.cursor()
        
        registro_atual = cursor.execute("SELECT LOGRADOURO FROM REGISTROS WHERE ID = :id", {'id': id_registro}).fetchone()
        if not registro_atual:
            return "Erro: Registro não encontrado."
        
        updates = []
        params = {}
        logradouro = registro_atual[0]
        
        if novo_nome.strip():
            if not validar_nome(novo_nome): return "Erro: Nome inválido."
            updates.append("NOME = :novo_nome")
            params['novo_nome'] = novo_nome.strip()

        if nova_descricao.strip():
            if not validar_descricao(nova_descricao): return "Erro: Descrição inválida."
            updates.append("DESCRICAO = :nova_descricao")
            params['nova_descricao'] = nova_descricao.strip()
            
        if novo_cep.strip():
            if not validar_cep(novo_cep): return "Erro: Novo CEP inválido."
            
            endereco, erro_api = consultar_cep_api(novo_cep)
            if erro_api:
                logradouro = "API Indisponível/CEP não encontrado"
            else:
                logradouro = endereco.get('logradouro', 'Não Informado')
            
            updates.append("CEP = :novo_cep")
            params['novo_cep'] = novo_cep.strip()
            updates.append("LOGRADOURO = :logradouro")
            params['logradouro'] = logradouro

        if not updates:
            return "Nenhuma alteração válida fornecida."

        updates.append("ATUALIZADO_EM = :atualizado_em")
        params['atualizado_em'] = datetime.now().isoformat(timespec="seconds")
        params['id_registro'] = id_registro 

        sql_update = f"UPDATE REGISTROS SET {', '.join(updates)} WHERE ID = :id_registro"
        cursor.execute(sql_update, params)
        conn.commit()
        
        if cursor.rowcount == 0:
            return "Erro: Registro não encontrado."
            
        return f"Registro ID {id_registro} atualizado no Oracle! Logradouro: {logradouro}"

    except oracledb.Error as e:
        log("ERRO_ATUALIZAR", str(e))
        return f"Erro ao atualizar no Oracle DB: {e}"
    finally:
        conn.close()


def alternar_ativo(id_registro, status):
    """Ativa ou inativa um registro."""
    conn = get_db_connection()
    if not conn: return "Falha na conexão com o Oracle."
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE REGISTROS SET ATIVO = :status, ATUALIZADO_EM = :data_update WHERE ID = :id
        """, {
            'status': 1 if status else 0, 
            'data_update': datetime.now().isoformat(timespec="seconds"), 
            'id': id_registro
        })
        conn.commit()
        if cursor.rowcount == 0:
            return "Erro: Registro não encontrado."
        return f"Registro {id_registro} agora está {'ATIVO' if status else 'INATIVO'} no Oracle."
    except oracledb.Error as e:
        log("ERRO_ATIVAR", str(e))
        return f"Erro ao alterar status no Oracle DB: {e}"
    finally:
        conn.close()


def excluir(id_registro):
    """Exclui registro de forma definitiva (requisito CRUD)."""
    conn = get_db_connection()
    if not conn: return "Falha na conexão com o Oracle."
    
    try:
        cursor = conn.cursor()
        
        registro = cursor.execute("SELECT NOME FROM REGISTROS WHERE ID = :id", {'id': id_registro}).fetchone()
        if registro:
            log("EXCLUIDO", f"ID: {id_registro}, Nome: {registro[0]}")
        
        cursor.execute("DELETE FROM REGISTROS WHERE ID = :id", {'id': id_registro})
        conn.commit()

        if cursor.rowcount == 0:
            return "Erro: Registro não encontrado."
        return f"Registro ID {id_registro} excluído do Oracle."
    except oracledb.Error as e:
        log("ERRO_EXCLUIR", str(e))
        return f"Erro ao excluir no Oracle DB: {e}"
    finally:
        conn.close()

# -----------------------------
# 3. Exportação para JSON
# -----------------------------
def exportar_para_json(filtro="todos"):
    """Exporta os registros (ativos, inativos ou todos) para um arquivo JSON."""
    conn = get_db_connection()
    if not conn: return "Falha na conexão com o Oracle. Exportação cancelada."
    
    try:
        if filtro == "ativos":
            query = "SELECT ID, NOME, DESCRICAO, CEP, LOGRADOURO, ATIVO, CRIADO_EM, ATUALIZADO_EM FROM REGISTROS WHERE ATIVO = 1 ORDER BY ID DESC"
            filename = "export_ativos.json"
        elif filtro == "inativos":
            query = "SELECT ID, NOME, DESCRICAO, CEP, LOGRADOURO, ATIVO, CRIADO_EM, ATUALIZADO_EM FROM REGISTROS WHERE ATIVO = 0 ORDER BY ID DESC"
            filename = "export_inativos.json"
        else: # 'todos'
            query = "SELECT ID, NOME, DESCRICAO, CEP, LOGRADOURO, ATIVO, CRIADO_EM, ATUALIZADO_EM FROM REGISTROS ORDER BY ID DESC"
            filename = "export_todos.json"
            
        cursor = conn.cursor()
        cursor.execute(query)
        columns = [col[0] for col in cursor.description]
        itens = [dict(zip(columns, row)) for row in cursor]
        
        if not itens:
            return f"Nenhum registro encontrado para exportar (Filtro: {filtro})."

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(itens, f, ensure_ascii=False, indent=2)
            
        log("EXPORTACAO_JSON", f"Exportados {len(itens)} registros para {filename}")
        return f"\nSUCESSO: {len(itens)} registros exportados para o arquivo '{filename}'."

    except Exception as e:
        log("ERRO_EXPORTAR", str(e))
        return f"Erro ao exportar/escrever o arquivo JSON: {e}"
    finally:
        conn.close()


# -----------------------------
# 4. Menus
# -----------------------------

def tela_de_inicio():
    """Mostra uma tela de boas-vindas para a apresentação."""
    os.system('cls' if os.name == 'nt' else 'clear') 
    print("=" * 60)
    print(" " * 15 + "PROJETO INOVAREA - SPRINT 4")
    print("=" * 60)
    print("  Tecnologia: Python (oracledb) + Oracle DB (FIAP)")
    print(f"\n  Usuário Oracle: {USER}")
    print("  Requisitos: CRUD Completo, Integração DB, API ViaCEP, Export JSON")
    print("=" * 60)
    time.sleep(1) 
    pausar()


def exportacao_menu():
    while True:
        os.system('cls' if os.name == 'nt' else 'clear') 
        print("\n" + "=" * 60)
        print("          SUBMENU DE EXPORTAÇÃO JSON (30 pts)         ")
        print("=" * 60)
        print("1. Exportar ATIVOS (export_ativos.json)")
        print("2. Exportar INATIVOS (export_inativos.json)")
        print("3. Exportar TODOS (export_todos.json)")
        print("0. Voltar ao menu de Relatórios")
        print("-" * 60)
        op = input("Opção: ")
        if op == "1":
            print(exportar_para_json("ativos")); pausar()
        elif op == "2":
            print(exportar_para_json("inativos")); pausar()
        elif op == "3":
            print(exportar_para_json("todos")); pausar()
        elif op == "0":
            break
        else:
            print("Opção inválida!")


def relatorios_menu():
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        dashboard()
        print("\n" + "=" * 60)
        print("                 SUBMENU DE RELATÓRIOS                ")
        print("=" * 60)
        print("1. Listar ATIVOS")
        print("2. Listar INATIVOS")
        print("3. Buscar por termo (ID, Nome, Descrição ou Logradouro)")
        print("4. Exportar dados para JSON (Submenu de Exportação)") 
        print("0. Voltar ao Menu Principal")
        print("-" * 60)
        op = input("Opção: ")
        if op == "1":
            print(listar("ativos")); pausar()
        elif op == "2":
            print(listar("inativos")); pausar()
        elif op == "3":
            termo = input("Digite termo: ")
            print(buscar(termo)); pausar()
        elif op == "4":
            exportacao_menu() 
        elif op == "0":
            break
        else:
            print("Opção inválida!")


def crud_menu():
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        dashboard()
        print("\n" + "=" * 60)
        print("                SUBMENU DE CRUD (30 pts)              ")
        print("=" * 60)
        print("1. Cadastrar NOVO Registro (Inclui consulta à API - 20 pts)")
        print("2. Listar ATIVOS")
        print("3. Listar TODOS")
        print("4. Buscar Registro")
        print("5. Atualizar Registro (Pode reconsultar a API com novo CEP)")
        print("6. Inativar/Ativar Registro")
        print("7. Excluir Registro (Definitivo)")
        print("0. Voltar ao Menu Principal")
        print("-" * 60)
        op = input("Opção: ")
        if op == "1":
            nome = input("Nome: "); desc = input("Descrição: "); cep = input("CEP (8 dígitos): ")
            print(cadastrar(nome, desc, cep)); pausar()
        elif op == "2":
            print(listar("ativos")); pausar()
        elif op == "3":
            print(listar("todos")); pausar()
        elif op == "4":
            termo = input("Termo: "); print(buscar(termo)); pausar()
        elif op == "5":
            try:
                _id = int(input("ID do registro a atualizar: "))
                novo_nome = input("Novo nome (deixe vazio para manter): ")
                nova_desc = input("Nova descrição (deixe vazio para manter): ")
                novo_cep = input("Novo CEP para reconsultar API (deixe vazio para manter): ")
                print(atualizar(_id, novo_nome, nova_desc, novo_cep))
            except ValueError:
                print("Erro: ID deve ser um número inteiro.")
            pausar()
        elif op == "6":
            try:
                _id = int(input("ID: "))
                status = input("A para ATIVAR, I para INATIVAR: ").strip().upper()
                if status not in {"A", "I"}:
                    print("Erro: use 'A' para ativar ou 'I' para inativar.")
                else:
                    print(alternar_ativo(_id, status == "A"))
            except ValueError:
                print("Erro: ID inválido.")
            pausar()
        elif op == "7":
            try:
                _id = int(input("ID: "))
                confirma = input(f"Tem certeza que deseja EXCLUIR o registro {_id} permanentemente? (S/N): ").strip().upper()
                if confirma == "S":
                    print(excluir(_id))
                else:
                    print("Exclusão cancelada.")
            except ValueError:
                print("Erro: ID inválido.")
            pausar()
        elif op == "0":
            break
        else:
            print("Opção inválida!")


def menu():
    """Função principal do menu."""
    tela_de_inicio() 
    setup_db() # Tenta estabelecer a conexão ao iniciar
    while True:
        os.system('cls' if os.name == 'nt' else 'clear') 
        dashboard()
        print("=== MENU PRINCIPAL ===")
        print("1. CRUD (Cadastrar, Alterar, Excluir)")
        print("2. Relatórios (Listar, Buscar, Exportar JSON)")
        print("0. Sair")
        print("-" * 40)
        op = input("Opção: ")
        if op == "1":
            crud_menu()
        elif op == "2":
            relatorios_menu()
        elif op == "0":
            print("Saindo do InovaREA. Até a próxima!")
            break
        else:
            print("Opção inválida!")
            pausar()


if __name__ == "__main__":
    # Verificação de dependências
    try:
        import requests 
    except ImportError:
        print("\n*** ERRO: O módulo 'requests' (para API) não está instalado. Execute: pip install requests")
        exit()
    try:
        import oracledb 
    except ImportError:
        print("\n*** ERRO: O módulo 'oracledb' não está instalado. Execute: pip install oracledb")
        exit()
        
    menu()
