from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

db = SQLAlchemy()

class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuario'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=True)  # Tornado opcional
    senha_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    ativo = db.Column(db.Boolean, default=True)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)

    def set_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def check_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)


class Lancamento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(10), nullable=False)  # 'receita' ou 'despesa'
    categoria = db.Column(db.String(50), nullable=False)
    valor = db.Column(db.Float, nullable=False)
    data = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    descricao = db.Column(db.String(200))
    
    def __repr__(self):
        return f'<Lancamento {self.tipo} - {self.categoria} - {self.valor}>'
        
class LimiteAlerta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    limite_minimo = db.Column(db.Float, default=1000.0)
    email = db.Column(db.String(100))

class Alerta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mensagem = db.Column(db.String(200), nullable=False)
    data = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    lido = db.Column(db.Boolean, default=False)
