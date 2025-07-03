# Importa módulos necessários do Flask e outras bibliotecas
from flask import Flask, render_template, request, flash, redirect, url_for, session, g
from datetime import datetime
import os
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from markupsafe import Markup # Importe o Markup para renderizar HTML seguro

# Importa módulos do Firebase Admin SDK
from firebase_admin import credentials, initialize_app, firestore, get_app
from firebase_admin.exceptions import FirebaseError

# Importa a classe Config do arquivo config.py
from config import Config 

# Inicializa a aplicação Flask
app = Flask(__name__)
# Carrega as configurações do arquivo config.py
app.config.from_object(Config)

# Inicializa db e caches para coleções como None globalmente
db = None
_users_collection_cache = None
_services_collection_cache = None # Renomeado de _products_collection_cache

# --- INICIALIZAÇÃO DO FIREBASE ADMIN SDK E FIRESTORE ---
def initialize_firebase_app():
    global db
    try:
        get_app()
        print("Firebase Admin SDK já inicializado.")
    except ValueError:
        print("Tentando inicializar Firebase Admin SDK...")
        path_to_json = os.path.join(os.path.dirname(os.path.abspath(__file__)), "serviceAccountKey.json")
        try:
            cred = credentials.Certificate(path_to_json)
            initialize_app(cred)
            print("Firebase Admin SDK inicializado com sucesso.")
        except Exception as e_cert:
            print(f"\nERRO CRÍTICO NA INICIALIZAÇÃO DO FIREBASE: {e_cert}\n")
            db = None
            return
    try:
        db = firestore.client()
        print("Cliente Firestore obtido com sucesso.")
    except Exception as e_get_client:
        print(f"\nERRO AO OBTER CLIENTE FIRESTORE: {e_get_client}")
        db = None

initialize_firebase_app()

# --- MAPA DE ROTAS DINÂMICAS PARA SERVIÇOS E CATEGORIAS ---
# Este mapa define as categorias principais de serviços e seus subtópicos (serviços específicos)
SERVICE_ROUTES_MAP = {
    'edificacoes': {
        'display_name': "Edificações",
        'services': { # Renomeado de 'subtopics' para 'services'
            'residenciais': "Obras Residenciais",
            'comerciais': "Construções Comerciais",
            'industriais': "Galpões Industriais",
            'predial': "Manutenção Predial",
        }
    },
    'infraestrutura': {
        'display_name': "Infraestrutura",
        'services': {
            'saneamento': "Redes de Saneamento",
            'viaria': "Obras Viárias",
            'pontes': "Pontes e Viadutos",
        }
    },
    'reformas': {
        'display_name': "Reformas e Acabamentos",
        'services': {
            'residenciais_reforma': "Reformas Residenciais",
            'comerciais_reforma': "Reformas Comerciais",
            'interiores': "Design de Interiores",
            'acabamentos': "Acabamentos Fino",
        }
    },
    'projetos': {
        'display_name': "Projetos e Consultoria",
        'services': {
            'arquitetonicos': "Projetos Arquitetônicos",
            'estruturais': "Projetos Estruturais",
            'hidraulicos': "Projetos Hidráulicos",
            'eletricos': "Projetos Elétricos",
            'consultoria': "Consultoria Técnica",
        }
    },
    'destaques': { # Nova categoria para agrupar serviços em destaque ou promoções
        'display_name': "Destaques e Ofertas",
        'services': {
            'promocoes': "Promoções Especiais",
            'novidades': "Novos Serviços",
        }
    }
}

# --- FUNÇÕES AUXILIARES E CONTEXTO ---
def get_users_collection_ref():
    global _users_collection_cache
    if _users_collection_cache: return _users_collection_cache
    if db:
        app_id = os.environ.get('CANVAS_APP_ID', 'default-app-id')
        _users_collection_cache = db.collection(f'artifacts/{app_id}/users')
        return _users_collection_cache
    return None

def get_services_collection_ref(): # Renomeado de get_products_collection_ref
    global _services_collection_cache
    if _services_collection_cache: return _services_collection_cache
    if db:
        app_id = os.environ.get('CANVAS_APP_ID', 'default-app-id')
        _services_collection_cache = db.collection(f'artifacts/{app_id}/public/data/services') # Caminho da coleção alterado
        return _services_collection_cache
    return None

@app.context_processor
def inject_global_vars():
    user_first_name = g.user.get('name', 'Usuário').split(" ")[0] if g.user else None
    # cart_item_count removido, pois não há carrinho
    return dict(year=datetime.now().year, SERVICE_ROUTES_MAP=SERVICE_ROUTES_MAP, logged_in_user_first_name=user_first_name) # Atualizado para SERVICE_ROUTES_MAP

@app.before_request
def load_logged_in_user():
    user_email = session.get('user_email')
    g.user = None
    if user_email and get_users_collection_ref():
        try:
            user_doc = get_users_collection_ref().document(user_email).get()
            if user_doc.exists: g.user = user_doc.to_dict()
            else: session.pop('user_email', None)
        except Exception as e:
            print(f"Erro ao carregar usuário: {e}")
            g.user = None

# --- DECORADOR DE ADMIN ---
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Apenas 'jeffersongarcia2013@gmail.com' terá acesso admin
        if not g.user or g.user.get('email') != 'jeffersongarcia2013@gmail.com':
            flash('Acesso não autorizado. Você precisa ser um administrador para acessar esta página.', 'danger')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

# --- ROTAS PRINCIPAIS E ESTÁTICAS ---
@app.route('/')
@app.route('/inicio')
def home():
    services_ref = get_services_collection_ref() # Renomeado de products_ref
    featured_services = [] # Renomeado de featured_products
    if services_ref:
        try:
            # Busca alguns serviços para destaque na página inicial
            query = services_ref.limit(3).stream()
            for doc in query:
                service_data = doc.to_dict()
                service_data['id'] = doc.id
                # Adiciona um badge de exemplo, pode ser dinâmico no futuro
                if len(featured_services) == 0: service_data['badge'] = 'NOVO'
                featured_services.append(service_data)
        except Exception as e:
            print(f"Erro ao buscar serviços em destaque: {e}")
            
    return render_template('index.html', featured_services=featured_services) # Atualizado para featured_services

@app.route('/meu-perfil')
def meu_perfil():
    if not g.user:
        flash('Você precisa estar logado para acessar seu perfil.', 'danger')
        return redirect(url_for('login'))
    return render_template('meu_perfil.html')

@app.route('/servicos-geral') # Uma página geral para apresentar os serviços
def services_overview(): 
    return render_template('services.html')

@app.route('/sobre')
def about(): return render_template('about.html')

@app.route('/contato')
def contact(): return render_template('contact.html')

@app.route('/escritorios') # Renomeado de /lojas
def offices(): return render_template('stores.html') # Mantém o nome do template por simplicidade, mas o conteúdo será alterado

# --- ROTAS DE SERVIÇOS E CATEGORIAS ---
@app.route('/area/<string:service_category_slug>') # Renomeado de /categoria/<string:category_name>
def service_category_overview(service_category_slug):
    category_data = SERVICE_ROUTES_MAP.get(service_category_slug) # Atualizado para SERVICE_ROUTES_MAP
    if not category_data:
        flash(f'Categoria de serviço "{service_category_slug}" não encontrada.', 'warning')
        return redirect(url_for('home'))

    # Prepara os subtópicos para exibição no template
    services_in_category = []
    for slug, title in category_data['services'].items(): # Atualizado para 'services'
        services_in_category.append({'key': slug, 'title': title})

    return render_template('category_overview.html', 
                           category_key=service_category_slug, 
                           category_data=category_data,
                           services_in_category=services_in_category) # Passa os serviços para o template

@app.route('/<string:service_category_slug>/<string:service_slug>') # Renomeado de /<string:category_slug>/<string:subtopic_slug>
def service_detail_page(service_category_slug, service_slug):
    category_data = SERVICE_ROUTES_MAP.get(service_category_slug) # Atualizado para SERVICE_ROUTES_MAP
    if not category_data or service_slug not in category_data['services']: # Atualizado para 'services'
        flash('Página de serviço não encontrada.', 'warning')
        return redirect(url_for('home'))
        
    service_details_data = {} # Renomeado de subtopic_details_data
    if db:
        try:
            # Busca detalhes específicos do serviço no Firestore
            service_ref = db.collection('service_details').document(service_slug).get() # Coleção alterada
            if service_ref.exists:
                service_details_data = service_ref.to_dict()
                if 'description_html' in service_details_data:
                    service_details_data['description_html'] = Markup(service_details_data['description_html'])
        except Exception as e:
            print(f"Erro ao buscar detalhes do serviço '{service_slug}': {e}")
    
    services_ref = get_services_collection_ref() # Renomeado de products_ref
    related_projects = [] # Renomeado de products para related_projects
    if services_ref:
        try:
            # Busca projetos/serviços relacionados, filtrando pelo service_slug
            # Nota: Para um portfólio, você pode querer buscar projetos com base em tags ou outras propriedades
            query = services_ref.where('service_slug', '==', service_slug).stream()
            for doc in query:
                project_data = doc.to_dict()
                project_data['id'] = doc.id
                related_projects.append(project_data)
        except Exception as e:
            print(f"ERRO ao buscar projetos para '{service_slug}': {e}")
            flash("Ocorreu um erro ao carregar os projetos relacionados.", "danger")
            related_projects = []

    content_title = service_details_data.get('title', category_data['services'][service_slug]) # Atualizado para 'services'
    
    return render_template('subtopic_page.html', # Mantém o nome do template por simplicidade, mas o conteúdo será alterado
                           content_title=content_title,
                           category=service_category_slug,
                           service_details=service_details_data, # Renomeado de subtopic_details
                           related_projects=related_projects) # Renomeado de products

# --- ROTAS DE AUTENTICAÇÃO ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if g.user: return redirect(url_for('home'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        users_ref = get_users_collection_ref()
        if not users_ref:
            flash('Serviço de autenticação indisponível.', 'danger')
            return render_template('login.html')
        try:
            user_doc = users_ref.document(email).get()
            if user_doc.exists:
                user_data = user_doc.to_dict()
                if check_password_hash(user_data.get('password_hash', ''), password):
                    session['user_email'] = user_data['email']
                    flash(f'Login bem-sucedido! Bem-vindo, {user_data.get("name", "").split(" ")[0]}.', 'success')
                    return redirect(url_for('home'))
            flash('E-mail ou senha incorretos.', 'danger')
        except Exception as e:
            flash(f'Erro no servidor: {e}', 'danger')
    return render_template('login.html')

@app.route('/cadastro', methods=['GET', 'POST'])
def register():
    if g.user: return redirect(url_for('home'))
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        
        if not all([name, email, password, request.form.get('confirm_password')]):
            flash('Por favor, preencha todos os campos.', 'warning')
        elif password != request.form.get('confirm_password'):
            flash('As senhas não coincidem.', 'danger')
        else:
            users_ref = get_users_collection_ref()
            if not users_ref:
                 flash('Serviço de cadastro indisponível.', 'danger')
                 return render_template('register.html')
                 
            if users_ref.document(email).get().exists:
                flash('Este e-mail já está cadastrado.', 'danger')
            else:
                users_ref.document(email).set({
                    'name': name, 'email': email,
                    'password_hash': generate_password_hash(password),
                    'created_at': firestore.SERVER_TIMESTAMP,
                    'role': 'user' # Todos os novos usuários são 'user' por padrão
                })
                flash('Cadastro realizado com sucesso! Faça login.', 'success')
                return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Você foi desconectado.', 'info')
    return redirect(url_for('home'))

# --- ROTAS DE ADMINISTRAÇÃO DE SERVIÇOS/PROJETOS ---
@app.route('/admin/services', methods=['GET']) # Renomeado de /admin/products
@admin_required
def admin_services(): # Renomeado de admin_products
    services_ref = get_services_collection_ref()
    all_services = []
    if services_ref:
        try:
            query = services_ref.stream()
            for doc in query:
                service_data = doc.to_dict()
                service_data['id'] = doc.id
                all_services.append(service_data)
        except Exception as e:
            print(f"Erro ao buscar serviços para administração: {e}")
            flash("Ocorreu um erro ao carregar os serviços.", "danger")

    # Coleta todos os slugs de serviços para o dropdown no formulário
    all_service_slugs = []
    for category_slug, category_data in SERVICE_ROUTES_MAP.items():
        for service_slug in category_data['services'].keys():
            all_service_slugs.append(service_slug)
    all_service_slugs.sort() # Opcional: para exibir em ordem alfabética

    return render_template('admin_products.html', # Mantém o nome do template por simplicidade, mas o conteúdo será alterado
                           services=all_services, # Passa os serviços
                           all_service_slugs=all_service_slugs,
                           editing_service=None) # Indica que não está editando

@app.route('/admin/services/add', methods=['POST'])
@admin_required
def add_service():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        image = request.form.get('image', '').strip()
        service_slug = request.form.get('service_slug', '').strip() # O subtópico agora é o service_slug
        
        if not all([name, description, service_slug]):
            flash('Por favor, preencha todos os campos obrigatórios.', 'warning')
            return redirect(url_for('admin_services'))

        services_ref = get_services_collection_ref()
        if not services_ref:
            flash('Serviço de banco de dados indisponível.', 'danger')
            return redirect(url_for('admin_services'))

        try:
            # Adiciona um novo documento à coleção 'services'
            services_ref.add({
                'name': name,
                'description': description,
                'image': image if image else 'placeholder_default.jpg', # Imagem padrão se não for fornecida
                'service_slug': service_slug,
                'created_at': firestore.SERVER_TIMESTAMP
            })
            flash('Serviço adicionado com sucesso!', 'success')
        except Exception as e:
            flash(f'Erro ao adicionar serviço: {e}', 'danger')
    return redirect(url_for('admin_services'))

@app.route('/admin/services/edit/<string:service_id>', methods=['GET', 'POST'])
@admin_required
def edit_service(service_id):
    services_ref = get_services_collection_ref()
    service_doc_ref = services_ref.document(service_id)
    editing_service = None

    try:
        service_doc = service_doc_ref.get()
        if service_doc.exists:
            editing_service = service_doc.to_dict()
            editing_service['id'] = service_doc.id
        else:
            flash('Serviço não encontrado para edição.', 'danger')
            return redirect(url_for('admin_services'))
    except Exception as e:
        flash(f'Erro ao buscar serviço para edição: {e}', 'danger')
        return redirect(url_for('admin_services'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        image = request.form.get('image', '').strip()
        service_slug = request.form.get('service_slug', '').strip()
        
        if not all([name, description, service_slug]):
            flash('Por favor, preencha todos os campos obrigatórios.', 'warning')
            return redirect(url_for('edit_service', service_id=service_id))

        try:
            service_doc_ref.update({
                'name': name,
                'description': description,
                'image': image if image else 'placeholder_default.jpg',
                'service_slug': service_slug
            })
            flash('Serviço atualizado com sucesso!', 'success')
            return redirect(url_for('admin_services'))
        except Exception as e:
            flash(f'Erro ao atualizar serviço: {e}', 'danger')
            return redirect(url_for('edit_service', service_id=service_id))

    # Coleta todos os slugs de serviços para o dropdown no formulário
    all_service_slugs = []
    for category_slug, category_data in SERVICE_ROUTES_MAP.items():
        for slug in category_data['services'].keys():
            all_service_slugs.append(slug)
    all_service_slugs.sort()

    return render_template('admin_products.html', # Mantém o nome do template
                           services=[], # Não precisamos listar todos os serviços aqui, apenas o de edição
                           all_service_slugs=all_service_slugs,
                           editing_service=editing_service)

@app.route('/admin/services/delete/<string:service_id>', methods=['POST'])
@admin_required
def delete_service(service_id):
    services_ref = get_services_collection_ref()
    if not services_ref:
        flash('Serviço de banco de dados indisponível.', 'danger')
        return redirect(url_for('admin_services'))

    try:
        services_ref.document(service_id).delete()
        flash('Serviço excluído com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao excluir serviço: {e}', 'danger')
    return redirect(url_for('admin_services'))

# --- EXECUÇÃO DA APLICAÇÃO ---
if __name__ == '__main__':
    if not app.config.get('SECRET_KEY'):
         print("\nAVISO: 'SECRET_KEY' não configurada!\n")
    app.run(debug=True)
