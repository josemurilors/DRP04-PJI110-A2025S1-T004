from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, Lancamento, LimiteAlerta, Alerta, Usuario
from datetime import datetime, timedelta
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO
from reportlab.pdfgen import canvas
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///fluxo_caixa.db'
app.config['SECRET_KEY'] = 'sua_chave_secreta_aqui_muito_segura'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configuração do Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

db.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

# Criação do banco de dados e usuário admin
with app.app_context():
    # Garante que o diretório instance existe
    os.makedirs(app.instance_path, exist_ok=True)
    
    # Cria todas as tabelas
    db.create_all()
    
    # Verifica e cria usuário admin
    if not Usuario.query.filter_by(username='admin').first():
        try:
            admin = Usuario(
                username='admin',
                nome='Administrador',
                is_admin=True
            )
            admin.set_senha('admin123')
            db.session.add(admin)
            db.session.commit()
            print("Usuário admin criado com sucesso!")
        except Exception as e:
            db.session.rollback()
            print(f"Erro ao criar usuário admin: {e}")

# Rotas de autenticação
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        senha = request.form['senha']
        user = Usuario.query.filter_by(username=username).first()
        
        if user and user.check_senha(senha) and user.ativo:
            login_user(user)
            return redirect(url_for('index'))
        flash('Credenciais inválidas ou usuário inativo', 'danger')
    
    # Passa valores padrão para o gráfico quando na página de login
    return render_template('login.html', 
                         dados_grafico={'Receitas': 0, 'Despesas': 0},
                         saldo=0)
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# Rotas de administração
@app.route('/admin/usuarios')
@login_required
def admin_usuarios():
    if not current_user.is_admin:
        flash('Acesso negado: apenas administradores', 'danger')
        return redirect(url_for('index'))
    
    usuarios = Usuario.query.all()
    return render_template('admin_usuarios.html', usuarios=usuarios)

@app.route('/admin/usuarios/novo', methods=['GET', 'POST'])
@login_required
def admin_novo_usuario():
    if not current_user.is_admin:
        flash('Acesso negado: apenas administradores', 'danger')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        if Usuario.query.filter_by(username=request.form['username']).first():
            flash('Nome de usuário já existe!', 'danger')
            return redirect(url_for('admin_novo_usuario'))
            
        usuario = Usuario(
            username=request.form['username'],
            nome=request.form['nome'],
            is_admin=request.form.get('is_admin') == 'on'
        )
        usuario.set_senha(request.form['senha'])
        db.session.add(usuario)
        db.session.commit()
        flash('Usuário criado com sucesso!', 'success')
        return redirect(url_for('admin_usuarios'))
    
    return render_template('admin_novo_usuario.html')

@app.route('/admin/usuarios/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def admin_editar_usuario(id):
    if not current_user.is_admin:
        flash('Acesso negado: apenas administradores', 'danger')
        return redirect(url_for('index'))
    
    usuario = Usuario.query.get_or_404(id)
    
    if request.method == 'POST':
        usuario.username = request.form['username']
        usuario.nome = request.form['nome']
        usuario.is_admin = request.form.get('is_admin') == 'on'
        
        if request.form['senha']:  # Só atualiza a senha se foi fornecida
            usuario.set_senha(request.form['senha'])
            
        db.session.commit()
        flash('Usuário atualizado com sucesso!', 'success')
        return redirect(url_for('admin_usuarios'))
    
    return render_template('admin_editar_usuario.html', usuario=usuario)

@app.route('/admin/usuarios/toggle_ativar/<int:id>')
@login_required
def admin_toggle_ativar_usuario(id):
    if not current_user.is_admin:
        flash('Acesso negado: apenas administradores', 'danger')
        return redirect(url_for('index'))
    
    if id == current_user.id:
        flash('Você não pode desativar a si mesmo', 'danger')
        return redirect(url_for('admin_usuarios'))
    
    usuario = Usuario.query.get_or_404(id)
    usuario.ativo = not usuario.ativo
    db.session.commit()
    
    flash(f'Usuário {"ativado" if usuario.ativo else "desativado"} com sucesso!', 'success')
    return redirect(url_for('admin_usuarios'))


# Rotas protegidas
@app.context_processor
def inject_dados_padrao():
    # Valores padrão que serão disponíveis em todos os templates
    return {
        'dados_grafico': {'Receitas': 0, 'Despesas': 0},
        'saldo': 0
    }

@app.route('/')
@login_required
def index():
    hoje = datetime.now()
    primeiro_dia_mes = hoje.replace(day=1)
    
    lancamentos_mes = Lancamento.query.filter(
        Lancamento.data >= primeiro_dia_mes,
        Lancamento.data <= hoje
    ).all()
    
    receitas = sum(l.valor for l in lancamentos_mes if l.tipo == 'receita')
    despesas = sum(l.valor for l in lancamentos_mes if l.tipo == 'despesa')
    saldo = receitas - despesas
    
    return render_template('base.html',
                         dados_grafico={'Receitas': receitas, 'Despesas': despesas},
                         saldo=saldo)

@app.route('/lancamentos')
@login_required
def lancamentos():
    todos_lancamentos = Lancamento.query.order_by(Lancamento.data.desc()).all()
    return render_template('lancamentos.html', lancamentos=todos_lancamentos)

@app.route('/adicionar_lancamento', methods=['POST'])
@login_required
def adicionar_lancamento():
    tipo = request.form['tipo']
    categoria = request.form['categoria']
    valor = float(request.form['valor'])
    descricao = request.form['descricao']
    
    novo_lancamento = Lancamento(
        tipo=tipo,
        categoria=categoria,
        valor=valor,
        descricao=descricao,
        data=datetime.now()
    )
    
    db.session.add(novo_lancamento)
    db.session.commit()
    
    flash('Lançamento adicionado com sucesso!', 'success')
    return redirect(url_for('lancamentos'))



# Módulo de Relatórios
@app.route('/relatorios')
@login_required
def relatorios():
    return render_template('relatorios.html')

@app.route('/gerar_relatorio', methods=['POST'])
@login_required
def gerar_relatorio():
    data_inicio = datetime.strptime(request.form['data_inicio'], '%Y-%m-%d')
    data_fim = datetime.strptime(request.form['data_fim'], '%Y-%m-%d')
    formato = request.form['formato']
    
    lancamentos = Lancamento.query.filter(
        Lancamento.data >= data_inicio,
        Lancamento.data <= data_fim
    ).all()
    
    # Criar DataFrame para análise
    dados = []
    for lanc in lancamentos:
        dados.append({
            'Data': lanc.data,
            'Tipo': lanc.tipo,
            'Categoria': lanc.categoria,
            'Valor': lanc.valor
        })
    
    df = pd.DataFrame(dados)
    
    if formato == 'pdf':
        # Gerar PDF
        buffer = BytesIO()
        p = canvas.Canvas(buffer)
        
        p.drawString(100, 800, f"Relatório de Fluxo de Caixa - {data_inicio} a {data_fim}")
        
        y = 750
        for _, row in df.iterrows():
            p.drawString(100, y, f"{row['Data']} - {row['Tipo']} - {row['Categoria']}: R$ {row['Valor']:.2f}")
            y -= 20
        
        p.showPage()
        p.save()
        
        buffer.seek(0)
        return send_file(buffer, as_attachment=True, download_name='relatorio.pdf', mimetype='application/pdf')
    
    elif formato == 'excel':
        # Gerar Excel
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        output.seek(0)
        
        return send_file(
            output,
            as_attachment=True,
            download_name='relatorio.xlsx',
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    
    return redirect(url_for('relatorios'))

@app.route('/grafico')
@login_required
def gerar_grafico():
    # Gera um gráfico simples
    lancamentos = Lancamento.query.all()
    
    dados = {'Receitas': 0, 'Despesas': 0}
    for lanc in lancamentos:
        if lanc.tipo == 'receita':
            dados['Receitas'] += lanc.valor
        else:
            dados['Despesas'] += lanc.valor
    
    plt.figure()
    plt.bar(dados.keys(), dados.values())
    plt.title('Resumo Financeiro')
    
    img = BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    
    return send_file(img, mimetype='image/png')

# Módulo de Alertas
@app.route('/alertas')
@login_required
def alertas():
    limite = LimiteAlerta.query.first()
    alertas = Alerta.query.order_by(Alerta.data.desc()).all()
    return render_template('alertas.html', limite_alertas=limite, alertas=alertas)

@app.route('/configurar_alertas', methods=['POST'])
@login_required
def configurar_alertas():
    limite_minimo = float(request.form['limite_minimo'])
    email = request.form['email']
    
    limite = LimiteAlerta.query.first()
    if not limite:
        limite = LimiteAlerta()
    
    limite.limite_minimo = limite_minimo
    limite.email = email
    
    db.session.add(limite)
    db.session.commit()
    
    flash('Configurações de alerta salvas com sucesso!', 'success')
    return redirect(url_for('alertas'))

# Módulo de Previsão de Caixa
@app.route('/previsao')
@login_required
def previsao():
    return render_template('previsao.html')

@app.route('/calcular_previsao', methods=['POST'])
@login_required
def calcular_previsao():
    meses_analise = int(request.form['meses_analise'])
    meses_previsao = int(request.form['meses_previsao'])
    
    data_fim = datetime.now()
    data_inicio = data_fim - timedelta(days=30*meses_analise)
    
    # Obter dados históricos
    lancamentos = Lancamento.query.filter(
        Lancamento.data >= data_inicio,
        Lancamento.data <= data_fim
    ).all()
    
    # Calcular médias mensais (simplificado)
    receitas_mensal = sum(
        l.valor for l in lancamentos if l.tipo == 'receita'
    ) / meses_analise
    
    despesas_mensal = sum(
        l.valor for l in lancamentos if l.tipo == 'despesa'
    ) / meses_analise
    
    # Gerar previsão (método simplificado)
    previsao = []
    for i in range(1, meses_previsao + 1):
        mes = (datetime.now() + timedelta(days=30*i)).strftime('%m/%Y')
        previsao.append({
            'mes': mes,
            'receitas': receitas_mensal,
            'despesas': despesas_mensal,
            'saldo': receitas_mensal - despesas_mensal
        })
    
    return render_template('previsao.html', previsao=previsao)

if __name__ == '__main__':
    app.run(debug=True)
