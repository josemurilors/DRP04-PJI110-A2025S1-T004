from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, Lancamento, LimiteAlerta, Alerta, Usuario # Importa os modelos de banco de dados
from datetime import datetime, timedelta
import pandas as pd # Para manipulação de dados em DataFrames
import matplotlib.pyplot as plt # Para geração de gráficos
from io import BytesIO # Para lidar com dados em memória (imagens, PDFs)
from reportlab.pdfgen import canvas # Para geração de PDFs
from werkzeug.utils import secure_filename # Para lidar com nomes de arquivos seguros
import os # Para operações de sistema de arquivos

# Inicializa o aplicativo Flask
app = Flask(__name__)
# Configura a URI do banco de dados SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///fluxo_caixa.db'
# Define uma chave secreta para segurança da sessão
app.config['SECRET_KEY'] = 'sua_chave_secreta_aqui_muito_segura'
# Desabilita o rastreamento de modificações do SQLAlchemy para evitar warnings e economizar recursos
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configuração do Flask-Login
login_manager = LoginManager()
login_manager.init_app(app) # Inicializa o Flask-Login com o aplicativo Flask
login_manager.login_view = 'login' # Define a rota para redirecionamento caso o usuário não esteja logado

# Inicializa o SQLAlchemy com o aplicativo Flask
db.init_app(app)

# Função para carregar o usuário a partir do ID para o Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

# Criação do banco de dados e usuário admin
with app.app_context():
    # Garante que o diretório 'instance' existe (usado para o banco de dados)
    os.makedirs(app.instance_path, exist_ok=True)
    
    # Cria todas as tabelas do banco de dados definidas nos modelos
    db.create_all()
    
    # Verifica e cria usuário admin se não existir
    if not Usuario.query.filter_by(username='admin').first():
        try:
            admin = Usuario(
                username='admin',
                nome='Administrador',
                is_admin=True
            )
            admin.set_senha('admin123') # Define a senha para o usuário admin
            db.session.add(admin) # Adiciona o usuário admin ao sessão do banco de dados
            db.session.commit() # Salva as mudanças no banco de dados
            print("Usuário admin criado com sucesso!")
        except Exception as e:
            db.session.rollback() # Reverte a transação em caso de erro
            print(f"Erro ao criar usuário admin: {e}")

# Rotas de autenticação

# Rota para login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        senha = request.form['senha']
        user = Usuario.query.filter_by(username=username).first() # Busca o usuário pelo username
        
        # Verifica se o usuário existe, a senha está correta e o usuário está ativo
        if user and user.check_senha(senha) and user.ativo:
            login_user(user) # Loga o usuário
            return redirect(url_for('index')) # Redireciona para a página inicial
        flash('Credenciais inválidas ou usuário inativo', 'danger') # Exibe mensagem de erro
    
    # Passa valores padrão para o gráfico quando na página de login
    return render_template('login.html', 
                         dados_grafico={'Receitas': 0, 'Despesas': 0},
                         saldo=0)

# Rota para logout
@app.route('/logout')
@login_required # Requer que o usuário esteja logado para acessar esta rota
def logout():
    logout_user() # Faz o logout do usuário
    return redirect(url_for('login')) # Redireciona para a página de login

# Rotas de administração

# Rota para listar usuários (apenas para administradores)
@app.route('/admin/usuarios')
@login_required
def admin_usuarios():
    if not current_user.is_admin: # Verifica se o usuário atual é administrador
        flash('Acesso negado: apenas administradores', 'danger')
        return redirect(url_for('index'))
    
    usuarios = Usuario.query.all() # Busca todos os usuários
    return render_template('admin_usuarios.html', usuarios=usuarios)

# Rota para adicionar um novo usuário (apenas para administradores)
@app.route('/admin/usuarios/novo', methods=['GET', 'POST'])
@login_required
def admin_novo_usuario():
    if not current_user.is_admin:
        flash('Acesso negado: apenas administradores', 'danger')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        # Verifica se o nome de usuário já existe
        if Usuario.query.filter_by(username=request.form['username']).first():
            flash('Nome de usuário já existe!', 'danger')
            return redirect(url_for('admin_novo_usuario'))
            
        usuario = Usuario(
            username=request.form['username'],
            nome=request.form['nome'],
            is_admin=request.form.get('is_admin') == 'on' # Verifica se a checkbox de admin está marcada
        )
        usuario.set_senha(request.form['senha']) # Define a senha do novo usuário
        db.session.add(usuario)
        db.session.commit()
        flash('Usuário criado com sucesso!', 'success')
        return redirect(url_for('admin_usuarios'))
    
    return render_template('admin_novo_usuario.html')

# Rota para editar um usuário existente (apenas para administradores)
@app.route('/admin/usuarios/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def admin_editar_usuario(id):
    if not current_user.is_admin:
        flash('Acesso negado: apenas administradores', 'danger')
        return redirect(url_for('index'))
    
    usuario = Usuario.query.get_or_404(id) # Busca o usuário pelo ID ou retorna 404
    
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

# Rota para ativar/desativar um usuário (apenas para administradores)
@app.route('/admin/usuarios/toggle_ativar/<int:id>')
@login_required
def admin_toggle_ativar_usuario(id):
    if not current_user.is_admin:
        flash('Acesso negado: apenas administradores', 'danger')
        return redirect(url_for('index'))
    
    if id == current_user.id: # Impede que o administrador desative a si mesmo
        flash('Você não pode desativar a si mesmo', 'danger')
        return redirect(url_for('admin_usuarios'))
    
    usuario = Usuario.query.get_or_404(id)
    usuario.ativo = not usuario.ativo # Inverte o status de ativação do usuário
    db.session.commit()
    
    flash(f'Usuário {"ativado" if usuario.ativo else "desativado"} com sucesso!', 'success')
    return redirect(url_for('admin_usuarios'))


# Rotas protegidas (exigem login)

# Context processor para injetar dados padrão em todos os templates
@app.context_processor
def inject_dados_padrao():
    # Valores padrão que serão disponíveis em todos os templates
    return {
        'dados_grafico': {'Receitas': 0, 'Despesas': 0},
        'saldo': 0
    }

# Rota da página inicial
@app.route('/')
@login_required
def index():
    hoje = datetime.now()
    primeiro_dia_mes = hoje.replace(day=1) # Pega o primeiro dia do mês atual
    
    # Filtra os lançamentos do mês atual
    lancamentos_mes = Lancamento.query.filter(
        Lancamento.data >= primeiro_dia_mes,
        Lancamento.data <= hoje
    ).all()
    
    # Calcula receitas, despesas e saldo do mês
    receitas = sum(l.valor for l in lancamentos_mes if l.tipo == 'receita')
    despesas = sum(l.valor for l in lancamentos_mes if l.tipo == 'despesa')
    saldo = receitas - despesas
    
    return render_template('base.html',
                         dados_grafico={'Receitas': receitas, 'Despesas': despesas},
                         saldo=saldo)

# Rota para listar todos os lançamentos
@app.route('/lancamentos')
@login_required
def lancamentos():
    todos_lancamentos = Lancamento.query.order_by(Lancamento.data.desc()).all() # Ordena por data descendente
    return render_template('lancamentos.html', lancamentos=todos_lancamentos)

# Rota para adicionar um novo lançamento
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
        data=datetime.now() # Data do lançamento é a data atual
    )
    
    db.session.add(novo_lancamento)
    db.session.commit()
    
    flash('Lançamento adicionado com sucesso!', 'success')
    return redirect(url_for('lancamentos'))

# Módulo de Relatórios

# Rota para a página de relatórios
@app.route('/relatorios')
@login_required
def relatorios():
    return render_template('relatorios.html')

# Rota para gerar relatórios (PDF ou Excel)
@app.route('/gerar_relatorio', methods=['POST'])
@login_required
def gerar_relatorio():
    data_inicio = datetime.strptime(request.form['data_inicio'], '%Y-%m-%d') # Converte string para datetime
    data_fim = datetime.strptime(request.form['data_fim'], '%Y-%m-%d')
    formato = request.form['formato']
    
    # Filtra os lançamentos dentro do período especificado
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
    
    df = pd.DataFrame(dados) # Cria um DataFrame pandas a partir dos dados
    
    if formato == 'pdf':
        # Gerar PDF usando ReportLab
        buffer = BytesIO() # Buffer em memória para o PDF
        p = canvas.Canvas(buffer)
        
        p.drawString(100, 800, f"Relatório de Fluxo de Caixa - {data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}")
        
        y = 750
        for _, row in df.iterrows(): # Itera sobre as linhas do DataFrame
            p.drawString(100, y, f"{row['Data'].strftime('%d/%m/%Y')} - {row['Tipo']} - {row['Categoria']}: R$ {row['Valor']:.2f}")
            y -= 20
            if y < 50: # Adiciona nova página se o conteúdo exceder o limite
                p.showPage()
                y = 800
        
        p.showPage()
        p.save() # Salva o PDF no buffer
        
        buffer.seek(0) # Retorna ao início do buffer
        return send_file(buffer, as_attachment=True, download_name='relatorio.pdf', mimetype='application/pdf')
    
    elif formato == 'excel':
        # Gerar Excel usando pandas e openpyxl
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False) # Escreve o DataFrame no arquivo Excel
        output.seek(0)
        
        return send_file(
            output,
            as_attachment=True,
            download_name='relatorio.xlsx',
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    
    return redirect(url_for('relatorios'))

# Rota para gerar um gráfico simples (em PNG)
@app.route('/grafico')
@login_required
def gerar_grafico():
    # Gera um gráfico simples de receitas e despesas
    lancamentos = Lancamento.query.all()
    
    dados = {'Receitas': 0, 'Despesas': 0}
    for lanc in lancamentos:
        if lanc.tipo == 'receita':
            dados['Receitas'] += lanc.valor
        else:
            dados['Despesas'] += lanc.valor
    
    plt.figure() # Cria uma nova figura para o gráfico
    plt.bar(dados.keys(), dados.values()) # Cria um gráfico de barras
    plt.title('Resumo Financeiro') # Define o título do gráfico
    
    img = BytesIO()
    plt.savefig(img, format='png') # Salva o gráfico em formato PNG no buffer
    img.seek(0)
    
    return send_file(img, mimetype='image/png')

# Módulo de Alertas

# Rota para a página de alertas
@app.route('/alertas')
@login_required
def alertas():
    limite = LimiteAlerta.query.first() # Busca a configuração de limite de alerta
    alertas = Alerta.query.order_by(Alerta.data.desc()).all() # Busca todos os alertas ordenados por data
    return render_template('alertas.html', limite_alertas=limite, alertas=alertas)

# Rota para configurar os limites de alerta
@app.route('/configurar_alertas', methods=['POST'])
@login_required
def configurar_alertas():
    limite_minimo = float(request.form['limite_minimo'])
    email = request.form['email']
    
    limite = LimiteAlerta.query.first()
    if not limite: # Se não houver configuração de limite, cria uma nova
        limite = LimiteAlerta()
    
    limite.limite_minimo = limite_minimo
    limite.email = email
    
    db.session.add(limite)
    db.session.commit()
    
    flash('Configurações de alerta salvas com sucesso!', 'success')
    return redirect(url_for('alertas'))

# Módulo de Previsão de Caixa

# Rota para a página de previsão de caixa
@app.route('/previsao')
@login_required
def previsao():
    return render_template('previsao.html')

# Rota para calcular a previsão de caixa
@app.route('/calcular_previsao', methods=['POST'])
@login_required
def calcular_previsao():
    meses_analise = int(request.form['meses_analise']) # Número de meses para análise histórica
    meses_previsao = int(request.form['meses_previsao']) # Número de meses para previsão
    
    data_fim = datetime.now()
    data_inicio = data_fim - timedelta(days=30*meses_analise) # Calcula a data de início da análise
    
    # Obter dados históricos
    lancamentos = Lancamento.query.filter(
        Lancamento.data >= data_inicio,
        Lancamento.data <= data_fim
    ).all()
    
    # Calcular médias mensais (simplificado)
    # Soma todas as receitas do período de análise e divide pelo número de meses
    receitas_mensal = sum(
        l.valor for l in lancamentos if l.tipo == 'receita'
    ) / meses_analise
    
    # Soma todas as despesas do período de análise e divide pelo número de meses
    despesas_mensal = sum(
        l.valor for l in lancamentos if l.tipo == 'despesa'
    ) / meses_analise
    
    # Gerar previsão (método simplificado)
    previsao = []
    for i in range(1, meses_previsao + 1):
        mes = (datetime.now() + timedelta(days=30*i)).strftime('%m/%Y') # Calcula o mês futuro
        previsao.append({
            'mes': mes,
            'receitas': receitas_mensal,
            'despesas': despesas_mensal,
            'saldo': receitas_mensal - despesas_mensal # Saldo previsto para o mês
        })
    
    return render_template('previsao.html', previsao=previsao)

# Bloco para iniciar o aplicativo Flask quando o script é executado diretamente
if __name__ == '__main__':
      app.run(debug=True, host='0.0.0.0') # Roda o aplicativo em modo debug (útil para desenvolvimento)