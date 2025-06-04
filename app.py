import os
import mysql.connector
from flask import Flask, jsonify, request
from urllib.parse import urlparse, parse_qs
import logging # Para logging mais detalhado

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
        # Fallback para desenvolvimento local.
        # IMPORTANTE: Para Render, DATABASE_URL DEVE estar configurada
        db_url = "mysql://root:Thiago123@127.0.0.1:3306/crud_go"

    try:
        # Parseia a URL do banco de dados
        # A URL do Aiven é do tipo 'mysql://user:password@host:port/database?ssl-mode=REQUIRED'
        parsed_url = urlparse(db_url)

        # Extrai os componentes
        user = parsed_url.username
        password = parsed_url.password
        host = parsed_url.hostname
        port = parsed_url.port if parsed_url.port else 3306 # Porta padrão MySQL
        database = parsed_url.path.strip('/') # Remove a barra inicial

        # Extrai parâmetros da query, incluindo ssl-mode
        query_params = parse_qs(parsed_url.query)
        ssl_mode = query_params.get('ssl-mode', [None])[0]

        # Configurações SSL
        ssl_config = {}
        if ssl_mode == "REQUIRED":
            # AQUI ESTÁ A MUDANÇA: Usando o caminho do certificado CA
            # O Render vai encontrar 'ca.pem' se ele estiver na raiz do seu projeto
            ssl_config = {
                'ssl_ca': 'ca.pem', # <--- APONTA PARA O ARQUIVO CA.PEM
                'ssl_verify_identity': True, # Mantenha esta linha para verificar a identidade do servidor
            }
            logging.info("SSL mode is REQUIRED. Configuring SSL for database connection with CA certificate.")
        elif ssl_mode:
            logging.warning(f"Unsupported SSL mode: {ssl_mode}. Connection might fail.")
        else:
            logging.info("SSL mode not specified in DATABASE_URL.")


        # Conecta ao banco de dados
        logging.info(f"Attempting to connect to database: {user}@{host}:{port}/{database}")
        db_connection = mysql.connector.connect(
            user=user,
            password=password,
            host=host,
            port=port,
            database=database,
            **ssl_config # Adiciona as configurações SSL, se houver
        )
        # Tenta fazer um ping para verificar a conexão imediatamente
        if db_connection.is_connected():
            logging.info("Conectado ao banco de dados MySQL com sucesso!")
            # Configurações de pool de conexão (opcional, mas recomendado)
            # mysql-connector-python não tem um pool de conexão global como sql.DB em Go.
            # Você normalmente usaria um Connection Pool separado (como mysql.connector.pooling)
            # ou gerenciaria as conexões por requisição em apps maiores.
            # Para este exemplo simples, uma conexão global é aceitável.
        else:
            logging.error("Falha ao conectar ao banco de dados: Conexão não estabelecida.")
            exit(1) # Sai da aplicação se a conexão falhar
    except mysql.connector.Error as err:
        logging.critical(f"Erro ao conectar ao banco de dados: {err}")
        exit(1) # Sai da aplicação se a conexão falhar
    except Exception as e:
        logging.critical(f"Erro inesperado durante a inicialização do DB: {e}")
        exit(1)

# Inicia a conexão com o banco de dados quando o aplicativo começa
# Esta chamada é feita uma vez na inicialização da aplicação
init_db()

# Rota GET para buscar um computador por device_id
@app.route('/computadores/<string:device_id>', methods=['GET'])
def get_computador_by_device_id(device_id):
    if not db_connection or not db_connection.is_connected():
        # Tenta reconectar se a conexão caiu (básico)
        logging.warning("Database connection lost. Attempting to re-establish.")
        try:
            init_db() # Tenta inicializar novamente
            if not db_connection or not db_connection.is_connected():
                return jsonify({"error": "Failed to re-establish database connection"}), 500
        except Exception as e:
            logging.error(f"Error during re-connection attempt: {e}")
            return jsonify({"error": "Failed to re-establish database connection"}), 500


    cursor = db_connection.cursor(dictionary=True) # dictionary=True para obter resultados como dicionários
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
        # Tenta reconectar se a conexão caiu (básico)
        logging.warning("Database connection lost. Attempting to re-establish.")
        try:
            init_db() # Tenta inicializar novamente
            if not db_connection or not db_connection.is_connected():
                return jsonify({"error": "Failed to re-establish database connection"}), 500
        except Exception as e:
            logging.error(f"Error during re-connection attempt: {e}")
            return jsonify({"error": "Failed to re-establish database connection"}), 500

    cursor = db_connection.cursor()
    try:
        query = "DELETE FROM computadores WHERE device_id = %s"
        cursor.execute(query, (device_id,))
        db_connection.commit() # Confirma a transação

        if cursor.rowcount > 0:
            return jsonify({"message": "Computador deletado com sucesso"}), 200
        else:
            return jsonify({"error": "Computador não encontrado para deletar"}), 404
    except mysql.connector.Error as err:
        logging.error(f"Erro ao deletar computador: {err}")
        db_connection.rollback() # Reverte a transação em caso de erro
        return jsonify({"error": "Erro ao deletar o computador"}), 500
    finally:
        cursor.close()

# Bloco principal para rodar a aplicação
if __name__ == '__main__':
    port = int(os.getenv("PORT", 8080)) # Padrão para 8080 se PORT não estiver definida
    logging.info(f"Attempting to start server on port: {port}")
    try:
        app.run(host='0.0.0.0', port=port)
        logging.info(f"Server successfully started on port: {port}")
    except Exception as e:
        logging.critical(f"Server failed to start on port {port}: {e}")
        exit(1)
