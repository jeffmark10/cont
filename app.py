# Importa módulos necessários do Flask e outras bibliotecas
from flask import Flask, render_template, request, flash, redirect, url_for, session, g, jsonify
from datetime import datetime
import os
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from markupsafe import Markup # Importe o Markup para renderizar HTML seguro
import logging # Importa o módulo de logging
import uuid # Para gerar nomes de ficheiro únicos
import re # Para extrair nome do ficheiro da URL

# Importa módulos do Firebase Admin SDK (Storage foi removido para local)
from firebase_admin import credentials, initialize_app, firestore, get_app 

# Importa a classe Config do arquivo config.py
from config import Config 

# Inicializa a aplicação Flask
app = Flask(__name__)
# Carrega as configurações do arquivo config.py
app.config.from_object(Config)

# Define a pasta para uploads de imagens locais
UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'images', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True) # Garante que a pasta existe

# Configuração básica de logging
if app.debug:
    logging.basicConfig(level=logging.DEBUG, 
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
else:
    logging.basicConfig(level=logging.INFO, 
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                        filename='app.log', # Salva logs em um arquivo em produção
                        filemode='a') # 'a' para append

# Obter um logger para o seu módulo
logger = logging.getLogger(__name__)

# Adiciona logging para o APP_ID em uso
logger.debug(f"APP_ID em uso: {app.config['APP_ID']}")


# Inicializa db e caches para coleções como None globalmente
db = None
_users_collection_cache = None
_services_collection_cache = None 
_project_images_collection_cache = None # NOVO: Cache para coleção de imagens de projeto

# --- INICIALIZAÇÃO DO FIREBASE ADMIN SDK E FIRESTORE ---
def initialize_firebase_app():
    global db
    try:
        get_app()
        logger.info("Firebase Admin SDK já inicializado.")
    except ValueError:
        logger.info("Tentando inicializar Firebase Admin SDK...")
        path_to_json = os.path.join(os.path.dirname(os.path.abspath(__file__)), "serviceAccountKey.json")
        try:
            cred = credentials.Certificate(path_to_json)
            initialize_app(cred) # Removido 'storageBucket'
            logger.info("Firebase Admin SDK inicializado com sucesso (sem Storage Bucket).")
        except Exception as e_cert:
            logger.critical(f"ERRO CRÍTICO NA INICIALIZAÇÃO DO FIREBASE: {e_cert}")
            db = None
            return
    try:
        db = firestore.client()
        logger.info("Cliente Firestore obtido com sucesso.")
    except Exception as e_get_client:
        logger.critical(f"ERRO AO OBTER CLIENTE FIRESTORE: {e_get_client}")
        db = None

initialize_firebase_app()

# --- MAPA DE ROTAS DINÂMICAS PARA SERVIÇOS E CATEGORIAS ---
# Este mapa define as categorias principais de serviços e seus subtópicos (serviços específicos)
SERVICE_ROUTES_MAP = {
    'edificacoes': {
        'display_name': "Edificações",
        'description': "Soluções completas para construção e reforma de edifícios residenciais, comerciais e industriais.",
        'image': 'Edificacoes.webp', # Estas imagens permanecem em static/images
        'services': { 
            'residenciais': "Obras Residenciais",
            'comerciais': "Construções Comerciais",
            'industriais': "Galpões Industriais",
            'predial': "Manutenção Predial",
        }
    },
    'infraestrutura': {
        'display_name': "Infraestrutura",
        'description': "Projetos e execução de infraestrutura urbana e rural, garantindo desenvolvimento sustentável.",
        'image': 'infraestrutura_urbana.jpg',
        'services': {
            'saneamento': "Redes de Saneamento",
            'viaria': "Obras Viárias",
            'pontes': "Pontes e Viadutos",
        }
    },
    'reformas': {
        'display_name': "Reformas e Acabamentos",
        'description': "Transforme seu espaço com reformas de alta qualidade e acabamentos impecáveis para ambientes internos e externos.",
        'image': 'Reformas e Acabamentos.png',
        'services': {
            'residenciais_reforma': "Reformas Residenciais",
            'comerciais_reforma': "Reformas Comerciais",
            'interiores': "Design de Interiores",
            'acabamentos': "Acabamentos Fino",
        }
    },
    'projetos': {
        'display_name': "Projetos e Consultoria",
        'description': "Desenvolvimento de projetos arquitetônicos, estruturais e de instalações, além de consultoria técnica especializada.",
        'image': 'Projetos e Consultoria.png',
        'services': {
            'arquitetonicos': "Projetos Arquitetônicos",
            'estruturais': "Projetos Estruturais",
            'hidraulicos': "Projetos Hidráulicos",
            'eletricos': "Projetos Elétricos",
            'consultoria': "Consultoria Técnica",
        }
    },
    'destaques': { 
        'display_name': "Destaques e Ofertas",
        'description': "Fique por dentro das nossas promoções e novos serviços.",
        'image': 'construcao_projeto.jpg',
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
        app_id = app.config['APP_ID'] 
        _users_collection_cache = db.collection(f'artifacts/{app_id}/users')
        return _users_collection_cache
    return None

def get_services_collection_ref(): 
    global _services_collection_cache
    if _services_collection_cache: return _services_collection_cache
    if db:
        app_id = app.config['APP_ID'] 
        _services_collection_cache = db.collection(f'artifacts/{app_id}/public/data/services') 
        return _services_collection_cache
    return None

# NOVO: Função para obter a coleção de imagens de projeto
def get_project_images_collection_ref():
    global _project_images_collection_cache
    if _project_images_collection_cache: return _project_images_collection_cache
    if db:
        app_id = app.config['APP_ID']
        # A coleção de imagens de projeto também é pública
        _project_images_collection_cache = db.collection(f'artifacts/{app_id}/public/data/project_images')
        return _project_images_collection_cache
    return None


@app.context_processor
def inject_global_vars():
    user_first_name = g.user.get('name', 'Usuário').split(" ")[0] if g.user else None
    return dict(year=datetime.now().year, SERVICE_ROUTES_MAP=SERVICE_ROUTES_MAP, logged_in_user_first_name=user_first_name)

@app.before_request
def load_logged_in_user():
    user_email = session.get('user_email')
    g.user = None
    if user_email and get_users_collection_ref():
        try:
            user_doc_ref = get_users_collection_ref().document(user_email)
            user_doc = user_doc_ref.get()
            if user_doc.exists: 
                user_data = user_doc.to_dict()
                g.user = user_data
                g.user['role'] = user_data.get('role', 'user') 

                if user_email == 'jeffersongarcia2013@gmail.com' and g.user['role'] != 'admin':
                    g.user['role'] = 'admin'
                    # user_doc_ref.update({'role': 'admin'}) # Descomente para persistir a mudança no Firestore
                    logger.info(f"Papel do usuário '{user_email}' atualizado para 'admin' na sessão.")

            else: 
                session.pop('user_email', None)
        except Exception as e:
            logger.error(f"Erro ao carregar usuário: {e}")
            g.user = None

# --- DECORADOR DE ADMIN ---
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not g.user or g.user.get('role') != 'admin':
            flash('Acesso não autorizado. Você precisa ser um administrador para acessar esta página.', 'danger')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

# --- FUNÇÃO AUXILIAR PARA UPLOAD E EXCLUSÃO DE IMAGEM (ARMAZENAMENTO LOCAL) ---
def upload_image_local(image_file):
    if not image_file:
        return None

    try:
        # Gera um nome de ficheiro único
        unique_filename = str(uuid.uuid4()) + os.path.splitext(image_file.filename)[1]
        file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
        image_file.save(file_path) # Salva o ficheiro localmente
        
        # Retorna o caminho relativo à pasta 'static/images/'
        relative_path = os.path.join('uploads', unique_filename).replace(os.sep, '/')
        logger.info(f"Ficheiro '{unique_filename}' carregado localmente para: {relative_path}")
        return relative_path 
    except Exception as e:
        logger.error(f"Erro ao carregar ficheiro para o armazenamento local: {e}")
        return None

def delete_image_local(image_path):
    if not image_path:
        return

    # Converte o caminho relativo (ex: 'uploads/filename.jpg') para o caminho absoluto
    absolute_path = os.path.join(UPLOAD_FOLDER, os.path.basename(image_path))
    
    try:
        if os.path.exists(absolute_path):
            os.remove(absolute_path)
            logger.info(f"Ficheiro '{image_path}' excluído do armazenamento local.")
        else:
            logger.warning(f"Ficheiro '{image_path}' não encontrado no armazenamento local para exclusão.")
    except Exception as e:
        logger.error(f"Erro ao excluir ficheiro do armazenamento local ('{image_path}'): {e}")


# --- ROTAS PRINCIPAIS E ESTÁTICAS ---
@app.route('/')
@app.route('/inicio')
def home():
    services_ref = get_services_collection_ref() 
    featured_services = [] 
    if services_ref:
        try:
            query = services_ref.limit(3).stream()
            for doc in query:
                service_data = doc.to_dict()
                service_data['id'] = doc.id
                service_data['category_slug'] = service_data.get('category_slug', 'edificacoes') 
                service_data['service_slug'] = service_data.get('service_slug', 'residenciais') 
                
                if len(featured_services) == 0: service_data['badge'] = 'NOVO'
                featured_services.append(service_data)
        except Exception as e:
            logger.error(f"Erro ao buscar serviços em destaque: {e}")
            
    return render_template('index.html', featured_services=featured_services)

@app.route('/meu-perfil')
def meu_perfil():
    if not g.user:
        flash('Você precisa estar logado para acessar seu perfil.', 'danger')
        return redirect(url_for('login'))
    return render_template('meu_perfil.html')

@app.route('/meus-projetos') 
def my_projects():
    if not g.user:
        flash('Você precisa estar logado para acessar seus projetos.', 'danger')
        return redirect(url_for('login'))
    user_projects = [] 
    flash('Esta página está em construção. Seus projetos e solicitações aparecerão aqui em breve!', 'info')
    return render_template('my_projects.html', user_projects=user_projects)

@app.route('/servicos') 
def service_categories_overview(): 
    return render_template('service_categories_overview.html', categories=SERVICE_ROUTES_MAP)

@app.route('/sobre')
def about(): return render_template('about.html')

@app.route('/contato')
def contact(): return render_template('contact.html')

@app.route('/escritorios') 
def offices(): return render_template('stores.html') 

@app.route('/portfolio') 
def portfolio():
    services_ref = get_services_collection_ref()
    portfolio_projects = []
    if services_ref:
        try:
            query = services_ref.stream()
            for doc in query:
                project_data = doc.to_dict()
                project_data['id'] = doc.id
                project_data['category_slug'] = project_data.get('category_slug', 'edificacoes') 
                project_data['service_slug'] = project_data.get('service_slug', 'residenciais') 
                portfolio_projects.append(project_data)
        except Exception as e:
            logger.error(f"Erro ao buscar projetos para o portfólio: {e}")
            flash("Ocorreu um erro ao carregar os projetos do portfólio.", "danger")
            portfolio_projects = [] 

    return render_template('portfolio.html', projects=portfolio_projects)

# --- ROTAS DE SERVIÇOS E CATEGORIAS ---
@app.route('/area/<string:service_category_slug>') 
def service_category_overview(service_category_slug):
    logger.debug(f"Acessando service_category_overview com category_slug: {service_category_slug}")
    category_data = SERVICE_ROUTES_MAP.get(service_category_slug) 
    if not category_data:
        logger.warning(f"Categoria de serviço '{service_category_slug}' não encontrada no SERVICE_ROUTES_MAP.")
        flash(f'Categoria de serviço "{service_category_slug}" não encontrada.', 'warning')
        return redirect(url_for('home'))

    services_in_category = []
    for slug, title in category_data['services'].items(): 
        services_in_category.append({'key': slug, 'title': title})
    logger.debug(f"Serviços na categoria {service_category_slug}: {services_in_category}")

    return render_template('category_overview.html', 
                           category_key=service_category_slug, 
                           category_data=category_data,
                           services_in_category=services_in_category)

@app.route('/<string:service_category_slug>/<string:service_slug>') 
def service_detail_page(service_category_slug, service_slug):
    logger.debug(f"Acessando service_detail_page com category_slug: {service_category_slug}, service_slug: {service_slug}")
    
    category_data = SERVICE_ROUTES_MAP.get(service_category_slug) 
    if not category_data:
        logger.warning(f"Categoria de serviço '{service_category_slug}' não encontrada no SERVICE_ROUTES_MAP.")
        flash('Página de serviço não encontrada.', 'warning')
        return redirect(url_for('home'))
        
    if service_slug not in category_data['services']:
        logger.warning(f"Service slug '{service_slug}' não encontrado na categoria '{service_category_slug}' no SERVICE_ROUTES_MAP.")
        flash('Página de serviço não encontrada.', 'warning')
        return redirect(url_for('home'))
        
    service_details_data = {} 
    if db:
        try:
            service_ref = db.collection('service_details').document(service_slug).get() 
            if service_ref.exists:
                service_details_data = service_ref.to_dict()
                logger.debug(f"Detalhes do serviço encontrados para '{service_slug}': {service_details_data}")
                if 'description_html' in service_details_data:
                    service_details_data['description_html'] = Markup(service_details_data['description_html'])
            else:
                logger.warning(f"Documento de detalhes do serviço não encontrado no Firestore para service_slug: {service_slug}")
        except Exception as e:
            logger.error(f"Erro ao buscar detalhes do serviço '{service_slug}' no Firestore: {e}")
    
    services_ref = get_services_collection_ref() 
    related_projects = [] 
    if services_ref:
        try:
            query = services_ref.where('service_slug', '==', service_slug).stream()
            for doc in query:
                project_data = doc.to_dict()
                project_data['id'] = doc.id
                related_projects.append(project_data)
            logger.debug(f"Projetos relacionados encontrados para '{service_slug}': {len(related_projects)}")
        except Exception as e:
            logger.error(f"ERRO ao buscar projetos para '{service_slug}': {e}")
            flash("Ocorreu um erro ao carregar os projetos relacionados.", "danger")
            related_projects = []

    content_title = service_details_data.get('title', category_data['services'][service_slug]) 
    
    return render_template('subtopic_page.html', 
                           content_title=content_title,
                           category=service_category_slug,
                           service_slug=service_slug, 
                           service_details=service_details_data, 
                           related_projects=related_projects)

# --- ROTA PARA PÁGINA DE FOTOS DO PROJETO ---
@app.route('/<string:service_category_slug>/<string:service_slug>/fotos')
def project_photos_page(service_category_slug, service_slug):
    logger.debug(f"Acessando project_photos_page com category_slug: {service_category_slug}, service_slug: {service_slug}")
    
    category_data = SERVICE_ROUTES_MAP.get(service_category_slug)
    if not category_data or service_slug not in category_data['services']:
        logger.warning(f"Projeto não encontrado para fotos: category_slug='{service_category_slug}', service_slug='{service_slug}'")
        flash('Página de fotos do projeto não encontrada.', 'warning')
        return redirect(url_for('home'))

    project_title = category_data['services'][service_slug]
    project_photos = [] 

    if db:
        try:
            # Busca o documento de fotos para o projeto
            # O ID do documento na coleção 'project_images' é o service_slug
            photos_doc = db.collection('project_images').document(service_slug).get()
            if photos_doc.exists:
                photos_data = photos_doc.to_dict()
                # Assumindo que o documento tem um campo 'image_urls' que é um array de strings (caminhos locais)
                project_photos = photos_data.get('image_urls', [])
                logger.debug(f"Fotos encontradas para '{service_slug}': {len(project_photos)} imagens.")
            else:
                logger.warning(f"Documento de fotos não encontrado para service_slug: {service_slug} na coleção 'project_images'.")
            
        except Exception as e:
            logger.error(f"Erro ao buscar fotos do projeto '{service_slug}' no Firestore: {e}")
            flash("Ocorreu um erro ao carregar as fotos do projeto.", "danger")

    return render_template('project_photos.html', 
                           content_title=project_title,
                           category=service_category_slug,
                           service_slug=service_slug,
                           project_photos=project_photos)


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
                    g.user = user_data
                    g.user['role'] = user_data.get('role', 'user') 

                    flash(f'Login bem-sucedido! Bem-vindo, {user_data.get("name", "").split(" ")[0]}.', 'success')
                    return redirect(url_for('home'))
            flash('E-mail ou senha incorretos.', 'danger')
        except Exception as e:
            flash(f'Erro no servidor: {e}', 'danger')
            logger.error(f"Erro durante o login: {e}")
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
                 
            try:
                if users_ref.document(email).get().exists:
                    flash('Este e-mail já está cadastrado.', 'danger')
                else:
                    new_user_data = {
                        'name': name, 
                        'email': email,
                        'password_hash': generate_password_hash(password),
                        'created_at': firestore.SERVER_TIMESTAMP,
                        'role': 'user' 
                    }
                    if email == 'jeffersongarcia2013@gmail.com':
                        new_user_data['role'] = 'admin'

                    users_ref.document(email).set(new_user_data)
                    flash('Cadastro realizado com sucesso! Faça login.', 'success')
                    return redirect(url_for('login'))
            except Exception as e:
                flash(f'Erro ao registrar usuário: {e}', 'danger')
                logger.error(f"Erro durante o registro: {e}")
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Você foi desconectado.', 'info')
    return redirect(url_for('home'))

# --- ROTAS DE ADMINISTRAÇÃO DE SERVIÇOS/PROJETOS ---
@app.route('/admin/services', methods=['GET']) 
@admin_required
def admin_services(): 
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
            logger.error(f"Erro ao buscar serviços para administração: {e}")
            flash("Ocorreu um erro ao carregar os serviços.", "danger")

    all_service_slugs = []
    for category_slug, category_data in SERVICE_ROUTES_MAP.items():
        for service_slug in category_data['services'].keys():
            all_service_slugs.append(service_slug)
    all_service_slugs.sort() 

    return render_template('admin_services.html', 
                           services=all_services, 
                           all_service_slugs=all_service_slugs,
                           editing_service=None) 

@app.route('/admin/services/add', methods=['POST'])
@admin_required
def add_service():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        service_slug = request.form.get('service_slug', '').strip()
        image_file = request.files.get('image_file') 

        if not all([name, description, service_slug]):
            flash('Por favor, preencha todos os campos obrigatórios.', 'warning')
            return redirect(url_for('admin_services'))
        
        if not image_file or image_file.filename == '':
            flash('Por favor, selecione um ficheiro de imagem para o serviço.', 'warning')
            return redirect(url_for('admin_services'))

        services_ref = get_services_collection_ref()
        if not services_ref:
            flash('Serviço de banco de dados indisponível.', 'danger')
            return redirect(url_for('admin_services'))

        found_category_slug = None
        for cat_slug, cat_data in SERVICE_ROUTES_MAP.items():
            if service_slug in cat_data['services']:
                found_category_slug = cat_slug
                break
        
        if not found_category_slug:
            flash('Erro: service_slug não corresponde a nenhuma categoria conhecida.', 'danger')
            logger.error(f"Erro ao adicionar serviço: service_slug '{service_slug}' não corresponde a nenhuma categoria conhecida.")
            return redirect(url_for('admin_services'))

        # Carrega a imagem para o armazenamento local
        image_path = upload_image_local(image_file)
        if not image_path:
            flash('Erro ao carregar a imagem para o armazenamento local.', 'danger')
            return redirect(url_for('admin_services'))

        try:
            services_ref.add({
                'name': name,
                'description': description,
                'image_url': image_path, # Guarda o caminho local
                'service_slug': service_slug,
                'category_slug': found_category_slug, 
                'created_at': firestore.SERVER_TIMESTAMP
            })
            flash('Serviço adicionado com sucesso!', 'success')
            logger.info(f"Serviço '{name}' adicionado com sucesso. Slug: {service_slug}, Categoria: {found_category_slug}")
        except Exception as e:
            flash(f'Erro ao adicionar serviço: {e}', 'danger')
            logger.error(f"Erro ao adicionar serviço: {e}")
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
            logger.debug(f"Carregando serviço para edição: {editing_service}")
        else:
            flash('Serviço não encontrado para edição.', 'danger')
            logger.warning(f"Serviço com ID '{service_id}' não encontrado para edição.")
            return redirect(url_for('admin_services'))
    except Exception as e:
        flash(f'Erro ao buscar serviço para edição: {e}', 'danger')
        logger.error(f"Erro ao buscar serviço para edição: {e}")
        return redirect(url_for('admin_services'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        service_slug = request.form.get('service_slug', '').strip()
        image_file = request.files.get('image_file') 
        
        if not all([name, description, service_slug]):
            flash('Por favor, preencha todos os campos obrigatórios.', 'warning')
            return redirect(url_for('edit_service', service_id=service_id))

        found_category_slug = None
        for cat_slug, cat_data in SERVICE_ROUTES_MAP.items():
            if service_slug in cat_data['services']:
                found_category_slug = cat_slug
                break

        if not found_category_slug:
            flash('Erro: service_slug não corresponde a nenhuma categoria conhecida.', 'danger')
            logger.error(f"Erro ao editar serviço: service_slug '{service_slug}' não corresponde a nenhuma categoria conhecida.")
            return redirect(url_for('edit_service', service_id=service_id))

        update_data = {
            'name': name,
            'description': description,
            'service_slug': service_slug,
            'category_slug': found_category_slug 
        }

        # Se um novo ficheiro de imagem for fornecido, faz o upload e atualiza a URL
        if image_file and image_file.filename != '':
            image_path = upload_image_local(image_file)
            if not image_path:
                flash('Erro ao carregar a nova imagem para o armazenamento local.', 'danger')
                return redirect(url_for('edit_service', service_id=service_id))
            update_data['image_url'] = image_path 
            # Excluir a imagem antiga do armazenamento local se uma nova for enviada
            if editing_service.get('image_url'):
                delete_image_local(editing_service['image_url'])

        try:
            service_doc_ref.update(update_data)
            flash('Serviço atualizado com sucesso!', 'success')
            logger.info(f"Serviço '{name}' (ID: {service_id}) atualizado com sucesso. Slug: {service_slug}, Categoria: {found_category_slug}")
            return redirect(url_for('admin_services'))
        except Exception as e:
            flash(f'Erro ao atualizar serviço: {e}', 'danger')
            logger.error(f"Erro ao atualizar serviço (ID: {service_id}): {e}")
            return redirect(url_for('edit_service', service_id=service_id))

    all_service_slugs = []
    for category_slug, category_data in SERVICE_ROUTES_MAP.items():
        for slug in category_data['services'].keys():
            all_service_slugs.append(slug)
    all_service_slugs.sort()

    return render_template('admin_services.html', 
                           services=[], 
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
        service_doc = services_ref.document(service_id).get()
        if service_doc.exists:
            service_data = service_doc.to_dict()
            # Exclui a imagem do armazenamento local antes de excluir o documento do Firestore
            if 'image_url' in service_data and service_data['image_url']:
                delete_image_local(service_data['image_url'])
            
            services_ref.document(service_id).delete()
            flash('Serviço excluído com sucesso!', 'success')
            logger.info(f"Serviço com ID '{service_id}' excluído com sucesso.")
        else:
            flash('Serviço não encontrado para exclusão.', 'warning')
            logger.warning(f"Tentativa de excluir serviço com ID '{service_id}' que não existe.")
    except Exception as e:
        flash(f'Erro ao excluir serviço: {e}', 'danger')
        logger.error(f"Erro ao excluir serviço (ID: {service_id}): {e}")
    return redirect(url_for('admin_services'))

# --- NOVO: ROTAS PARA GERENCIAMENTO DE FOTOS DE PROJETO ---
@app.route('/admin/project_photos/<string:service_slug>', methods=['GET', 'POST'])
@admin_required
def admin_project_photos(service_slug):
    project_images_ref = get_project_images_collection_ref()
    project_photos_doc_ref = project_images_ref.document(service_slug)
    project_photos_data = []
    project_title = "Gerenciar Fotos do Projeto" # Título padrão

    # Tenta obter o nome do serviço para exibir na página
    services_ref = get_services_collection_ref()
    if services_ref:
        try:
            service_doc = services_ref.where('service_slug', '==', service_slug).limit(1).get()
            if service_doc:
                for doc in service_doc:
                    project_title = f"Gerenciar Fotos de: {doc.to_dict().get('name', service_slug)}"
                    break
        except Exception as e:
            logger.error(f"Erro ao buscar nome do serviço para {service_slug}: {e}")

    if request.method == 'POST':
        if 'add_photos' in request.form: # Formulário de adicionar fotos
            new_image_files = request.files.getlist('image_files')
            uploaded_paths = []
            for img_file in new_image_files:
                if img_file and img_file.filename != '':
                    path = upload_image_local(img_file)
                    if path:
                        uploaded_paths.append(path)
            
            if uploaded_paths:
                try:
                    # Tenta obter o documento existente
                    doc = project_photos_doc_ref.get()
                    if doc.exists:
                        current_image_urls = doc.to_dict().get('image_urls', [])
                        # Adiciona apenas novas imagens que não estão duplicadas
                        updated_image_urls = list(set(current_image_urls + uploaded_paths))
                        project_photos_doc_ref.update({'image_urls': updated_image_urls})
                    else:
                        # Se o documento não existe, cria um novo
                        project_photos_doc_ref.set({'image_urls': uploaded_paths})
                    flash(f'{len(uploaded_paths)} foto(s) adicionada(s) com sucesso!', 'success')
                except Exception as e:
                    flash(f'Erro ao adicionar fotos: {e}', 'danger')
                    logger.error(f"Erro ao adicionar fotos para {service_slug}: {e}")
            else:
                flash('Nenhuma foto válida selecionada para adicionar.', 'warning')
        
        elif 'delete_photo' in request.form: # Formulário de deletar uma foto
            photo_to_delete = request.form.get('photo_path')
            if photo_to_delete:
                try:
                    doc = project_photos_doc_ref.get()
                    if doc.exists:
                        current_image_urls = doc.to_dict().get('image_urls', [])
                        if photo_to_delete in current_image_urls:
                            current_image_urls.remove(photo_to_delete)
                            project_photos_doc_ref.update({'image_urls': current_image_urls})
                            delete_image_local(photo_to_delete) # Exclui do armazenamento local
                            flash('Foto excluída com sucesso!', 'success')
                        else:
                            flash('Foto não encontrada na lista.', 'warning')
                    else:
                        flash('Projeto não encontrado para excluir foto.', 'warning')
                except Exception as e:
                    flash(f'Erro ao excluir foto: {e}', 'danger')
                    logger.error(f"Erro ao excluir foto '{photo_to_delete}' para {service_slug}: {e}")

        return redirect(url_for('admin_project_photos', service_slug=service_slug))

    # GET request: Carrega as fotos existentes
    if project_images_ref:
        try:
            doc = project_photos_doc_ref.get()
            if doc.exists:
                project_photos_data = doc.to_dict().get('image_urls', [])
        except Exception as e:
            logger.error(f"Erro ao carregar fotos existentes para {service_slug}: {e}")
            flash("Ocorreu um erro ao carregar as fotos existentes.", "danger")

    return render_template('admin_manage_photos.html', 
                           service_slug=service_slug,
                           project_title=project_title,
                           project_photos=project_photos_data)


# --- Rota de API para Sugestões de Pesquisa ---
@app.route('/api/search_suggestions')
def search_suggestions():
    query_term = request.args.get('q', '').lower()
    suggestions = []
    
    if not query_term or len(query_term) < 2: 
        return jsonify(suggestions)

    services_ref = get_services_collection_ref()
    if not services_ref:
        logger.error("Erro: Coleção de serviços não disponível para sugestões de pesquisa.")
        return jsonify({"error": "Serviço de busca indisponível."}), 500

    try:
        all_services_docs = services_ref.stream() 
        
        for doc in all_services_docs:
            service_data = doc.to_dict()
            service_name = service_data.get('name', '').lower()
            service_description = service_data.get('description', '').lower()
            service_slug = service_data.get('service_slug')
            service_category_slug = service_data.get('category_slug', 'edificacoes') 
            
            if query_term in service_name or query_term in service_description:
                suggestions.append({
                    'name': service_data.get('name'),
                    'slug': service_slug,
                    'category_slug': service_category_slug, 
                    'link_url': url_for('service_detail_page', service_category_slug=service_category_slug, service_slug=service_slug)
                })
            
            if len(suggestions) >= 10: 
                break
                
    except Exception as e:
        logger.error(f"Erro ao buscar sugestões de pesquisa no Firestore: {e}")
        return jsonify({"error": "Erro interno ao buscar sugestões."}), 500
        
    return jsonify(suggestions)


# --- EXECUÇÃO DA APLICAÇÃO ---
if __name__ == '__main__':
    if not app.config.get('SECRET_KEY') or app.config['SECRET_KEY'] == 'SUA_CHAVE_SECRETA_MUITO_FORTE':
         logger.warning("AVISO: 'SECRET_KEY' não configurada ou usando valor padrão de desenvolvimento. Mude em produção!")
    app.run(debug=True)

