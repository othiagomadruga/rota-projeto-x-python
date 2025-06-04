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
            # log_database_schema() # <--- REMOVA OU COMENTE ESTA LINHA AGORA!
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

# --- Funções Auxiliares para Reusar o Código ---
def _get_db_cursor():
    """Retorna um cursor do banco de dados, tentando reconectar se necessário."""
    if not db_connection or not db_connection.is_connected():
        logging.warning("Database connection lost. Attempting to re-establish.")
        try:
            init_db()
            if not db_connection or not db_connection.is_connected():
                raise Exception("Failed to re-establish database connection")
        except Exception as e:
            logging.error(f"Error during re-connection attempt: {e}")
            raise

    return db_connection.cursor(dictionary=True) # dictionary=True para resultados como dicionários

def _fetch_devices(query, params=None):
    """Executa uma query e retorna múltiplos dispositivos."""
    try:
        cursor = _get_db_cursor()
        cursor.execute(query, params)
        devices = cursor.fetchall()
        return jsonify(devices), 200
    except Exception as e:
        logging.error(f"Error fetching devices: {e}")
        return jsonify({"error": "Erro ao buscar dispositivos"}), 500
    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()

def _fetch_single_device(query, params=None):
    """Executa uma query e retorna um único dispositivo."""
    try:
        cursor = _get_db_cursor()
        cursor.execute(query, params)
        device = cursor.fetchone()
        if device:
            return jsonify(device), 200
        else:
            return jsonify({"error": "Dispositivo não encontrado"}), 404
    except Exception as e:
        logging.error(f"Error fetching single device: {e}")
        return jsonify({"error": "Erro ao buscar o dispositivo"}), 500
    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()

# --- ROTAS DA API ---

# Rota para pegar todos os dispositivos
@app.route('/desktop', methods=['GET'])
def get_all_devices():
    query = "SELECT id, hostname, equipment_name, os, os_version, location, manufacturer, model FROM devices"
    return _fetch_devices(query)

# Rota para pegar todos os dispositivos por plataforma
@app.route('/desktop/<string:platform>', methods=['GET'])
def get_devices_by_platform(platform):
    # Garante que a plataforma está em lowercase para comparação (se o DB for case-insensitive)
    # ou ajuste para corresponder exatamente como está no seu DB.
    # Ex: 'windows', 'macos', 'linux'
    query = "SELECT id, hostname, equipment_name, os, os_version, location, manufacturer, model FROM devices WHERE os = %s"
    return _fetch_devices(query, (platform.lower(),)) # Convertendo para lowercase para a query

# Rota para pegar um dispositivo específico por ID e plataforma
@app.route('/desktop/<string:platform>/<int:device_id>', methods=['GET'])
def get_specific_device_by_platform_and_id(platform, device_id):
    query = "SELECT id, hostname, equipment_name, os, os_version, location, manufacturer, model FROM devices WHERE os = %s AND id = %s"
    return _fetch_single_device(query, (platform.lower(), device_id)) # Convertendo para lowercase para a query

# Rota DELETE para deletar um computador por ID (usando o 'id' da tabela 'devices')
@app.route('/computadores/<int:device_id>', methods=['DELETE'])
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
        query = "DELETE FROM devices WHERE id = %s" # <--- ALTERADO PARA USAR 'id' DA TABELA 'devices'
        cursor.execute(query, (device_id,))
        db_connection.commit()

        if cursor.rowcount > 0:
            return jsonify({"message": f"Dispositivo {device_id} deletado com sucesso"}), 200
        else:
            return jsonify({"error": f"Dispositivo {device_id} não encontrado para deletar"}), 404
    except mysql.connector.Error as err:
        logging.error(f"Erro ao deletar dispositivo: {err}")
        db_connection.rollback()
        return jsonify({"error": "Erro ao deletar o dispositivo"}), 500
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
