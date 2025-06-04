import os
import mysql.connector
from flask import Flask, jsonify, request
from urllib.parse import urlparse, parse_qs
import logging

# Configura o logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)

# Variável global para a conexão com o banco de dados
db_connection = None

def log_database_schema():
    """
    Função TEMPORÁRIA para logar o schema do banco de dados.
    Esta função deve ser removida após a descoberta do schema.
    """
    if not db_connection or not db_connection.is_connected():
        logging.error("Não foi possível logar o schema: Conexão com o DB não está ativa.")
        return

    cursor = db_connection.cursor()
    try:
        logging.info("--- Iniciando descoberta do schema do banco de dados ---")

        # 1. Listar todas as tabelas
        cursor.execute("SHOW TABLES;")
        tables = cursor.fetchall()
        logging.info(f"Tabelas encontradas: {tables}")

        # 2. Para cada tabela, descrever suas colunas
        for table_tuple in tables:
            table_name = table_tuple[0]
            logging.info(f"\n--- Descrevendo tabela: '{table_name}' ---")
            cursor.execute(f"DESCRIBE `{table_name}`;")
            columns = cursor.fetchall()
            for col in columns:
                logging.info(f"  Coluna: {col[0]}, Tipo: {col[1]}, Nulo: {col[2]}, Chave: {col[3]}, Padrão: {col[4]}, Extra: {col[5]}")

        logging.info("--- Descoberta do schema concluída ---")

    except mysql.connector.Error as err:
        logging.error(f"Erro ao logar o schema do banco de dados: {err}")
    finally:
        cursor.close()


def init_db():
    global db_connection
    db_url = os.getenv("DATABASE_URL")

    if not db_url:
        logging.warning("WARNING: DATABASE_URL environment variable not set. Using local fallback.")
        db_url = "mysql://root:Thiago123@127.0.0.1:3306/crud_go"

    try:
        parsed_url = urlparse(db_url)
        user = parsed_url.username
        password = parsed_url.password
        host = parsed_url.hostname
        port = parsed_url.port if parsed_url.port else 3306
        database = parsed_url.path.strip('/')

        query_params = parse_qs(parsed_url.query)
        ssl_mode = query_params.get('ssl-mode', [None])[0]

        ssl_config = {}
        if ssl_mode == "REQUIRED":
            ssl_config = {
                'ssl_ca': 'ca.pem',
                'ssl_verify_identity': True,
            }
            logging.info("SSL mode is REQUIRED. Configuring SSL for database connection with CA certificate.")
        elif ssl_mode:
            logging.warning(f"Unsupported SSL mode: {ssl_mode}. Connection might fail.")
        else:
            logging.info("SSL mode not specified in DATABASE_URL.")

        logging.info(f"Attempting to connect to database: {user}@{host}:{port}/{database}")
        db_connection = mysql.connector.connect(
            user=user,
            password=password,
            host=host,
            port=port,
            database=database,
            **ssl_config
        )
        if db_connection.is_connected():
            logging.info("Conectado ao banco de dados MySQL com sucesso!")
            # CHAME A FUNÇÃO DE DESCOBERTA DO SCHEMA AQUI!
            log_database_schema() # <--- NOVA LINHA ADICIONADA AQUI!
        else:
            logging.error("Falha ao conectar ao banco de dados: Conexão não estabelecida.")
            exit(1)
    except mysql.connector.Error as err:
        logging.critical(f"Erro ao conectar ao banco de dados: {err}")
        exit(1)
    except Exception as e:
        logging.critical(f"Erro inesperado durante a inicialização do DB: {e}")
        exit(1)

# Inicia a conexão com o banco de dados quando o aplicativo começa
init_db()

# Rota GET para buscar um computador por device_id
@app.route('/computadores/<string:device_id>', methods=['GET'])
def get_computador_by_device_id(device_id):
    if not db_connection or not db_connection.is_connected():
        logging.warning("Database connection lost. Attempting to re-establish.")
        try:
            init_db()
            if not db_connection or not db_connection.is_connected():
                return jsonify({"error": "Failed to re-establish database connection"}), 500
        except Exception as e:
            logging.error(f"Error during re-connection attempt: {e}")
            return jsonify({"error": "Failed to re-establish database connection"}), 500

    cursor = db_connection.cursor(dictionary=True)
    try:
        query = "SELECT device_id, nome, preco FROM computadores WHERE device_id = %s"
        cursor.execute(query, (device_id,))
        computador = cursor.fetchone()

        if computador:
            return jsonify(computador), 200
        else:
            return jsonify({"error": "Computador não encontrado"}), 404
    except mysql.connector.Error as err:
        logging.error(f"Erro ao buscar computador: {err}")
        return jsonify({"error": "Erro ao buscar o computador"}), 500
    finally:
        cursor.close()

# Rota DELETE para deletar um computador por device_id
@app.route('/computadores/<string:device_id>', methods=['DELETE'])
def delete_computador_by_device_id(device_id):
    if not db_connection or not db_connection.is_connected():
        logging.warning("Database connection lost. Attempting to re-establish.")
        try:
            init_db()
            if not db_connection or not db_connection.is_connected():
                return jsonify({"error": "Failed to re-establish database connection"}), 500
        except Exception as e:
            logging.error(f"Error during re-connection attempt: {e}")
            return jsonify({"error": "Failed to re-establish database connection"}), 500

    cursor = db_connection.cursor()
    try:
        query = "DELETE FROM computadores WHERE device_id = %s"
        cursor.execute(query, (device_id,))
        db_connection.commit()

        if cursor.rowcount > 0:
            return jsonify({"message": "Computador deletado com sucesso"}), 200
        else:
            return jsonify({"error": "Computador não encontrado para deletar"}), 404
    except mysql.connector.Error as err:
        logging.error(f"Erro ao deletar computador: {err}")
        db_connection.rollback()
        return jsonify({"error": "Erro ao deletar o computador"}), 500
    finally:
        cursor.close()

# Bloco principal para rodar a aplicação
if __name__ == '__main__':
    port = int(os.getenv("PORT", 8080))
    logging.info(f"Attempting to start server on port: {port}")
    try:
        app.run(host='0.0.0.0', port=port)
        logging.info(f"Server successfully started on port: {port}")
    except Exception as e:
        logging.critical(f"Server failed to start on port {port}: {e}")
        exit(1)
