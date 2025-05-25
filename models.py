from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

# Cria uma instância do SQLAlchemy. 'db' será usado para interagir com o banco de dados.
db = SQLAlchemy()

# Define o modelo de banco de dados para a tabela 'Usuario'
class Usuario(UserMixin, db.Model): # UserMixin fornece implementações padrão para propriedades e métodos do Flask-Login
    __tablename__ = 'usuario' # Define o nome da tabela no banco de dados
    
    id = db.Column(db.Integer, primary_key=True) # Coluna de ID, chave primária, auto-incrementável
    username = db.Column(db.String(50), unique=True, nullable=False) # Nome de usuário, único e obrigatório
    nome = db.Column(db.String(100), nullable=False) # Nome completo do usuário, obrigatório
    email = db.Column(db.String(100), nullable=True)  # Endereço de e-mail, opcional
    senha_hash = db.Column(db.String(200), nullable=False) # Hash da senha, obrigatório
    is_admin = db.Column(db.Boolean, default=False) # Booleano para indicar se o usuário é administrador, padrão é False
    ativo = db.Column(db.Boolean, default=True) # Booleano para indicar se o usuário está ativo, padrão é True
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow) # Data de criação do usuário, padrão é a data e hora UTC atual

    # Método para definir a senha do usuário, gerando um hash seguro
    def set_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    # Método para verificar se a senha fornecida corresponde ao hash armazenado
    def check_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)

# Define o modelo de banco de dados para a tabela 'Lancamento' (fluxo de caixa)
class Lancamento(db.Model):
    id = db.Column(db.Integer, primary_key=True) # Coluna de ID, chave primária
    tipo = db.Column(db.String(10), nullable=False)  # Tipo de lançamento: 'receita' ou 'despesa', obrigatório
    categoria = db.Column(db.String(50), nullable=False) # Categoria do lançamento, obrigatório
    valor = db.Column(db.Float, nullable=False) # Valor do lançamento, obrigatório
    data = db.Column(db.DateTime, nullable=False, default=datetime.utcnow) # Data do lançamento, padrão é a data e hora UTC atual
    descricao = db.Column(db.String(200)) # Descrição opcional do lançamento
    
    # Representação string do objeto Lancamento, útil para depuração
    def __repr__(self):
        return f'<Lancamento {self.tipo} - {self.categoria} - {self.valor}>'
        
# Define o modelo de banco de dados para a tabela 'LimiteAlerta' (configurações de alerta)
class LimiteAlerta(db.Model):
    id = db.Column(db.Integer, primary_key=True) # Coluna de ID, chave primária
    limite_minimo = db.Column(db.Float, default=1000.0) # Valor mínimo para disparo de alerta, padrão é 1000.0
    email = db.Column(db.String(100)) # Endereço de e-mail para envio de alertas

# Define o modelo de banco de dados para a tabela 'Alerta' (alertas gerados)
class Alerta(db.Model):
    id = db.Column(db.Integer, primary_key=True) # Coluna de ID, chave primária
    mensagem = db.Column(db.String(200), nullable=False) # Mensagem do alerta, obrigatória
    data = db.Column(db.DateTime, nullable=False, default=datetime.utcnow) # Data de criação do alerta, padrão é a data e hora UTC atual
    lido = db.Column(db.Boolean, default=False) # Booleano para indicar se o alerta foi lido, padrão é False