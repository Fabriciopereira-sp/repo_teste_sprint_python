import os
import time
import json
import requests
import oracledb
from datetime import datetime

# ======================= CONFIG =======================

DB_USER = os.environ.get("DB_USER", "RM563237")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "270604")
DB_CONNECTION_STRING = os.environ.get("DB_DSN", "oracle.fiap.com.br:1521/ORCL")

TABLE_NAME = "REGISTROS"
SEQ_NAME = "REGISTROS_SEQ"
LOG_FILE = "log.txt"

# ======================= LOG =======================

def write_log(evento, mensagem):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} | {evento} | {mensagem}\n")
    except Exception:
        pass

# ======================= DB =======================

def get_db_connection():
    try:
        conn = oracledb.connect(user=DB_USER, password=DB_PASSWORD, dsn=DB_CONNECTION_STRING)
        write_log("DB_CONNECT", "Conexão Oracle estabelecida.")
        return conn
    except oracledb.Error as e:
        write_log("DB_CONNECT_ERROR", str(e))
        print("\n" + "="*60)
        print("❌ ERRO FATAL: FALHA NA CONEXÃO COM O BANCO DE DADOS")
        print("="*60)
        print(f"Detalhe: {e}")
        input("\nPressione ENTER para sair...")
        raise SystemExit(1)

def setup_schema():
    ddl_table = f"""
        CREATE TABLE {TABLE_NAME} (
            ID            NUMBER PRIMARY KEY,
            NOME          VARCHAR2(100) NOT NULL,
            DESCRICAO     VARCHAR2(4000),
            CEP           VARCHAR2(8),
            LOGRADOURO    VARCHAR2(255),
            ATIVO         NUMBER(1) DEFAULT 1,
            CRIADO_EM     DATE DEFAULT SYSDATE,
            ATUALIZADO_EM DATE
        )
    """
    ddl_seq = f"CREATE SEQUENCE {SEQ_NAME} START WITH 1 INCREMENT BY 1 NOCACHE"
    add_cols = [
        (f"ALTER TABLE {TABLE_NAME} ADD (ATIVO NUMBER(1) DEFAULT 1)", "ATIVO"),
        (f"ALTER TABLE {TABLE_NAME} ADD (CRIADO_EM DATE DEFAULT SYSDATE)", "CRIADO_EM"),
        (f"ALTER TABLE {TABLE_NAME} ADD (ATUALIZADO_EM DATE)", "ATUALIZADO_EM"),
    ]

    with get_db_connection() as conn, conn.cursor() as cur:
        try:
            cur.execute(ddl_table)
            write_log("DDL", f"Tabela {TABLE_NAME} criada.")
        except oracledb.Error as e:
            if "ora-00955" in str(e).lower() or "ora-00942" in str(e).lower():
                write_log("DDL_SKIP", f"Tabela {TABLE_NAME} já existe.")
            else:
                write_log("DDL_ERR", f"Tabela: {e}")

        try:
            cur.execute(ddl_seq)
            write_log("DDL", f"Sequence {SEQ_NAME} criada.")
        except oracledb.Error as e:
            if "ora-00955" in str(e).lower():
                write_log("DDL_SKIP", f"Sequence {SEQ_NAME} já existe.")
            else:
                write_log("DDL_ERR", f"Sequence: {e}")

        for cmd, nome in add_cols:
            try:
                cur.execute(cmd)
                write_log("DDL", f"Coluna {nome} adicionada.")
            except oracledb.Error as e:
                if "already exists" in str(e).lower() or "ora-01430" in str(e).lower():
                    write_log("DDL_SKIP", f"Coluna {nome} já existe.")
                else:
                    write_log("DDL_ERR", f"Coluna {nome}: {e}")

        conn.commit()

# ======================= UTIL =======================

def limpar_tela():
    os.system('cls' if os.name == 'nt' else 'clear')

def pausar(msg="Pressione ENTER para continuar..."):
    input(f"\n{msg}")

# ======================= API (ViaCEP) =======================

def consulta_cep(cep):
    cep = ''.join(filter(str.isdigit, str(cep)))
    if len(cep) != 8:
        print("CEP inválido (deve ter 8 dígitos).")
        return None, None

    url = f"https://viacep.com.br/ws/{cep}/json/"
    for i in range(1, 4):
        try:
            print(f"Consultando API ViaCEP (tentativa {i}/3)...")
            resp = requests.get(url, timeout=5)
            resp.raise_for_status()
            data = resp.json()
            if data.get("erro"):
                print("❌ CEP não encontrado no ViaCEP.")
                write_log("API_VIACEP_NOT_FOUND", cep)
                return None, None
            logradouro = data.get("logradouro", "Logradouro não informado")
            write_log("API_VIACEP_OK", f"{cep} -> {logradouro}")
            return cep, logradouro
        except requests.exceptions.Timeout:
            write_log("API_VIACEP_TIMEOUT", f"Tentativa {i} - {cep}")
        except requests.exceptions.RequestException as e:
            write_log("API_VIACEP_ERR", str(e))
        time.sleep(0.8)

    print("❌ Erro ao consultar a API ViaCEP após múltiplas tentativas.")
    return None, None

# ======================= CRUD =======================

def cadastrar_registro():
    limpar_tela()
    print("="*30)
    print("  1. CADASTRAR NOVO REGISTRO  ")
    print("="*30)

    nome = input("Digite o NOME do registro: ").strip()
    if not nome:
        print("❌ Nome não pode ser vazio.")
        return pausar()

    descricao = input("Digite a DESCRIÇÃO: ").strip()
    cep_input = input("Digite o CEP (para buscar o Logradouro): ").strip()
    cep, logradouro = consulta_cep(cep_input)
    if not logradouro:
        print("❌ Cadastro cancelado. CEP inválido ou não encontrado.")
        return pausar()

    with get_db_connection() as conn, conn.cursor() as cur:
        try:
            sql = f"""
                INSERT INTO {TABLE_NAME}
                    (ID, NOME, DESCRICAO, CEP, LOGRADOURO, ATIVO, CRIADO_EM, ATUALIZADO_EM)
                VALUES
                    ({SEQ_NAME}.NEXTVAL, :p_nome, :p_desc, :p_cep, :p_logradouro, 1, SYSDATE, SYSDATE)
                RETURNING ID INTO :p_id_out
            """
            id_out = cur.var(oracledb.NUMBER)
            cur.execute(sql, {
                "p_nome": nome,
                "p_desc": descricao,
                "p_cep": cep,
                "p_logradouro": logradouro,
                "p_id_out": id_out
            })
            conn.commit()
            novo_id = int(id_out.getvalue()[0])
            write_log("CRUD_CREATE", f"ID={novo_id} nome={nome}")
            print("\n" + "="*50)
            print(f"✅ REGISTRO CADASTRADO COM SUCESSO! ID: {novo_id}")
            print(f"Logradouro salvo: {logradouro}")
            print("="*50)
        except oracledb.Error as e:
            conn.rollback()
            write_log("CRUD_CREATE_ERR", str(e))
            print(f"❌ Erro ao cadastrar no banco de dados: {e}")
    pausar()

def fetch_all_registros(ativo_apenas=False):
    with get_db_connection() as conn, conn.cursor() as cur:
        try:
            base = f"SELECT ID, NOME, DESCRICAO, CEP, LOGRADOURO, ATIVO FROM {TABLE_NAME}"
            sql = base + (" WHERE ATIVO = 1" if ativo_apenas else "") + " ORDER BY ID"
            cur.execute(sql)
            cols = [c[0] for c in cur.description]
            dados = []
            for row in cur.fetchall():
                reg = dict(zip(cols, row))
                reg["ATIVO"] = "SIM" if reg["ATIVO"] == 1 else "NÃO"
                dados.append(reg)
            return dados
        except oracledb.Error as e:
            write_log("CRUD_READ_ERR", str(e))
            print(f"❌ Erro ao buscar registros: {e}")
            return []

def exibir_registros(registros, titulo):
    limpar_tela()
    print("=" * 60)
    print(f"  {titulo.upper()} ({len(registros)} registros)")
    print("=" * 60)
    if not registros:
        print("Nenhum registro encontrado.")
        return pausar()
    print(f"{'ID':<4} | {'ATIVO':<5} | {'NOME':<20} | {'DESCRIÇÃO':<20} | {'LOGRADOURO (ViaCEP)':<30}")
    print("-" * 100)
    for r in registros:
        print(f"{r['ID']:<4} | {r['ATIVO']:<5} | {r['NOME'][:19]:<20} | {r['DESCRICAO'][:19]:<20} | {r['LOGRADOURO'][:29]:<30}")
    pausar()

def fetch_registro_by_id(registro_id: int):
    with get_db_connection() as conn, conn.cursor() as cur:
        try:
            sql = f"""
                SELECT ID, NOME, DESCRICAO, CEP, LOGRADOURO, ATIVO
                  FROM {TABLE_NAME}
                 WHERE ID = :p_id
            """
            cur.execute(sql, {"p_id": registro_id})
            row = cur.fetchone()
            if not row:
                return None
            cols = [c[0] for c in cur.description]
            return dict(zip(cols, row))
        except oracledb.Error as e:
            write_log("CRUD_READ_ONE_ERR", str(e))
            print(f"❌ Erro ao buscar registro: {e}")
            return None

def buscar_registro_menu():
    limpar_tela()
    print("="*30)
    print("  4. BUSCAR REGISTRO POR ID  ")
    print("="*30)
    try:
        registro_id = int(input("Digite o ID do registro que deseja buscar: "))
    except ValueError:
        print("❌ ID deve ser um número inteiro.")
        return pausar()
    reg = fetch_registro_by_id(registro_id)
    if reg:
        limpar_tela()
        print("\n" + "="*50)
        print(f"  ✅ REGISTRO ENCONTRADO (ID: {reg['ID']})")
        print("="*50)
        print(f"Nome: {reg['NOME']}")
        print(f"Descrição: {reg['DESCRICAO']}")
        print(f"CEP: {reg['CEP']}")
        print(f"Logradouro (ViaCEP): {reg['LOGRADOURO']}")
        print(f"Status (Ativo): {'SIM' if reg['ATIVO'] == 1 else 'NÃO'}")
        print("="*50)
    else:
        print(f"❌ Nenhum registro encontrado com o ID: {registro_id}")
    pausar()

def atualizar_registro():
    limpar_tela()
    print("="*30)
    print("  5. ATUALIZAR REGISTRO  ")
    print("="*30)
    try:
        registro_id = int(input("Digite o ID do registro que deseja atualizar: "))
    except ValueError:
        print("❌ ID deve ser um número inteiro.")
        return pausar()

    reg = fetch_registro_by_id(registro_id)
    if not reg:
        print(f"❌ Nenhum registro encontrado com o ID: {registro_id}")
        return pausar()

    print("\n--- Dados Atuais ---")
    print(f"1. Nome: {reg['NOME']}")
    print(f"2. Descrição: {reg['DESCRICAO']}")
    print(f"3. CEP: {reg['CEP']}")
    print(f"   Logradouro: {reg['LOGRADOURO']}")
    print("--------------------")

    novo_nome = input(f"Novo NOME (atual: {reg['NOME']}): ").strip() or reg['NOME']
    nova_descricao = input(f"Nova DESCRIÇÃO (atual: {reg['DESCRICAO']}): ").strip() or reg['DESCRICAO']
    novo_cep = input(f"Novo CEP (deixe em branco para manter {reg['CEP']}): ").strip() or reg['CEP']

    logradouro_final = reg['LOGRADOURO']
    if novo_cep != reg['CEP']:
        cep_validado, novo_logradouro = consulta_cep(novo_cep)
        if novo_logradouro:
            novo_cep = cep_validado
            logradouro_final = novo_logradouro
        else:
            print("CEP inválido/não encontrado. Mantendo CEP/Logradouro anteriores.")
            novo_cep = reg['CEP']
            logradouro_final = reg['LOGRADOURO']

    with get_db_connection() as conn, conn.cursor() as cur:
        try:
            sql = f"""
                UPDATE {TABLE_NAME}
                   SET NOME = :p_nome,
                       DESCRICAO = :p_desc,
                       CEP = :p_cep,
                       LOGRADOURO = :p_log,
                       ATUALIZADO_EM = SYSDATE
                 WHERE ID = :p_id
            """
            cur.execute(sql, {
                "p_nome": novo_nome,
                "p_desc": nova_descricao,
                "p_cep": novo_cep,
                "p_log": logradouro_final,
                "p_id": registro_id
            })
            conn.commit()
            write_log("CRUD_UPDATE", f"ID={registro_id}")
            print("\n" + "="*50)
            print(f"✅ REGISTRO ID {registro_id} ATUALIZADO COM SUCESSO!")
            if novo_cep != reg['CEP']:
                print(f"Novo Logradouro salvo: {logradouro_final}")
            print("="*50)
        except oracledb.Error as e:
            conn.rollback()
            write_log("CRUD_UPDATE_ERR", str(e))
            print(f"❌ Erro ao atualizar no banco de dados: {e}")
    pausar()

def alternar_ativo():
    limpar_tela()
    print("="*40)
    print("  6. INATIVAR/ATIVAR REGISTRO (STATUS)  ")
    print("="*40)
    try:
        registro_id = int(input("Digite o ID do registro: "))
    except ValueError:
        print("❌ ID deve ser um número inteiro.")
        return pausar()

    reg = fetch_registro_by_id(registro_id)
    if not reg:
        print(f"❌ Nenhum registro encontrado com o ID: {registro_id}")
        return pausar()

    status_atual = 'ATIVO' if reg['ATIVO'] == 1 else 'INATIVO'
    novo_status_db = 0 if reg['ATIVO'] == 1 else 1
    novo_status_texto = 'INATIVO' if novo_status_db == 0 else 'ATIVO'  # corrigido

    print(f"\nRegistro {registro_id}: {reg['NOME']} (Status atual: {status_atual})")
    confirmacao = input(f"Confirma a alteração do status para {novo_status_texto}? (S/N): ").strip().upper()
    if confirmacao != 'S':
        print("Operação cancelada.")
        return pausar()

    with get_db_connection() as conn, conn.cursor() as cur:
        try:
            sql = f"UPDATE {TABLE_NAME} SET ATIVO = :p_ativo, ATUALIZADO_EM = SYSDATE WHERE ID = :p_id"
            cur.execute(sql, {"p_ativo": novo_status_db, "p_id": registro_id})
            conn.commit()
            write_log("CRUD_TOGGLE", f"ID={registro_id} -> {novo_status_texto}")
            print("\n" + "="*50)
            print(f"✅ REGISTRO ID {registro_id} ALTERADO PARA STATUS: {novo_status_texto}!")
            print("="*50)
        except oracledb.Error as e:
            conn.rollback()
            write_log("CRUD_TOGGLE_ERR", str(e))
            print(f"❌ Erro ao alterar status no banco: {e}")
    pausar()

def excluir_registro():
    limpar_tela()
    print("="*30)
    print("  7. EXCLUIR REGISTRO (DEFINITIVO)  ")
    print("="*30)
    try:
        registro_id = int(input("Digite o ID do registro que deseja EXCLUIR: "))
    except ValueError:
        print("❌ ID deve ser um número inteiro.")
        return pausar()

    reg = fetch_registro_by_id(registro_id)
    if not reg:
        print(f"❌ Nenhum registro encontrado com o ID: {registro_id}")
        return pausar()

    print(f"\nRegistro: {reg['ID']} - {reg['NOME']} ({reg['DESCRICAO']})")
    print("🚨 AVISO: Esta operação é IRREVERSÍVEL (DELETE FROM)!")
    confirmacao = input("Confirma a EXCLUSÃO DEFINITIVA? (DIGITE 'SIM' para confirmar): ").strip().upper()
    if confirmacao != 'SIM':
        print("Exclusão cancelada.")
        return pausar()

    with get_db_connection() as conn, conn.cursor() as cur:
        try:
            cur.execute(f"DELETE FROM {TABLE_NAME} WHERE ID = :p_id", {"p_id": registro_id})
            conn.commit()
            if cur.rowcount > 0:
                write_log("CRUD_DELETE", f"ID={registro_id}")
                print("\n" + "="*50)
                print(f"✅ REGISTRO ID {registro_id} EXCLUÍDO DEFINITIVAMENTE!")
                print("="*50)
            else:
                print(f"❌ Não foi possível excluir o registro ID {registro_id}.")
        except oracledb.Error as e:
            conn.rollback()
            write_log("CRUD_DELETE_ERR", str(e))
            print(f"❌ Erro ao excluir no banco de dados: {e}")
    pausar()

# ======================= EXPORT =======================

def exportar_para_json():
    limpar_tela()
    print("="*40)
    print("  EXPORTAÇÃO DE DADOS PARA JSON  ")
    print("="*40)

    registros = fetch_all_registros(ativo_apenas=True)
    if not registros:
        print("❌ Não há registros ATIVOS para exportar.")
        return pausar()

    dados = []
    for r in registros:
        rcp = r.copy()
        rcp.pop("ATIVO", None)
        dados.append(rcp)

    filepath = "export_registros_ativos.json"
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=4)
        write_log("EXPORT_JSON", f"{len(dados)} registros -> {filepath}")
        print("\n" + "="*50)
        print("✅ EXPORTAÇÃO CONCLUÍDA!")
        print(f"Registros exportados: {len(dados)}")
        print(f"Arquivo salvo em: {filepath}")
        print("="*50)
    except Exception as e:
        write_log("EXPORT_JSON_ERR", str(e))
        print(f"❌ Erro ao salvar o arquivo JSON: {e}")
    pausar()

# ======================= MENUS =======================

def crud_menu():
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
            exibir_registros(fetch_all_registros(False), "Todos os Registros")
        elif op == "2":
            exibir_registros(fetch_all_registros(True), "Registros ATIVOS")
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
    while True:
        limpar_tela()
        print("="*60)
        print("                 PROJETO INOVAREA                 ")
        print("="*60)
        print("\n  MENU PRINCIPAL:")
        print("1. Operações CRUD (Cadastrar, Alterar, Excluir)")
        print("2. Relatórios (Listas, Buscar, Exportar JSON)")
        print("3. (Primeira execução) Setup do Banco (DDL)")
        print("0. Sair")
        print("="*60)
        op = input("Opção: ").strip()
        if op == "1":
            crud_menu()
        elif op == "2":
            relatorios_menu()
        elif op == "3":
            setup_schema()
            print("✅ Setup concluído.")
            pausar()
        elif op == "0":
            limpar_tela()
            print("Saindo do InovaREA. Até a próxima!")
            break
        else:
            print("Opção inválida!")
            pausar()

# ======================= MAIN =======================

if __name__ == "__main__":
    try:
        import requests  # noqa: F401
    except ImportError:
        print("\n*** ERRO: O módulo 'requests' (para API) não está instalado.")
        print("Execute no terminal: pip install requests")
        pausar()
        raise SystemExit(1)

    menu_principal()
