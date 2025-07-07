# Importa módulos necessários do Flask e outras bibliotecas
from flask import Flask, render_template, request, flash, redirect, url_for, session, g, jsonify
from datetime import datetime
import os
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from markupsafe import Markup # Importe o Markup para renderizar HTML seguro
import logging # Importa o módulo de logging
import uuid # Para gerar nomes de ficheiro únicos

# Importa módulos do Firebase Admin SDK
from firebase_admin import credentials, initialize_app, firestore, get_app, storage # NOVO: Importa storage
from firebase_admin.exceptions import FirebaseError

# Importa a classe Config do arquivo config.py
from config import Config 

# Inicializa a aplicação Flask
app = Flask(__name__)
# Carrega as configurações do arquivo config.py
app.config.from_object(Config)

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
_services_collection_cache = None # Renomeado de _products_collection_cache

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
            # NOVO: Inicializa o Storage com o nome do bucket
            initialize_app(cred, {'storageBucket': app.config['FIREBASE_STORAGE_BUCKET']}) 
            logger.info("Firebase Admin SDK e Storage inicializados com sucesso.")
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
        # Usa app.config['APP_ID'] para garantir consistência com o config.py
        app_id = app.config['APP_ID'] 
        _users_collection_cache = db.collection(f'artifacts/{app_id}/users')
        return _users_collection_cache
    return None

def get_services_collection_ref(): # Renomeado de get_products_collection_ref
    global _services_collection_cache
    if _services_collection_cache: return _services_collection_cache
    if db:
        # Usa app.config['APP_ID'] para garantir consistência com o config.py
        app_id = app.config['APP_ID'] 
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
            logger.error(f"Erro ao carregar usuário: {e}")
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

# --- FUNÇÃO AUXILIAR PARA UPLOAD DE IMAGEM ---
def upload_image_to_firebase_storage(image_file):
    if not image_file:
        return None

    try:
        bucket = storage.bucket() # Obtém o bucket padrão
        # Gera um nome de ficheiro único para evitar colisões
        filename = f"service_images/{uuid.uuid4()}_{image_file.filename}"
        blob = bucket.blob(filename)
        
        # Faz o upload do ficheiro
        blob.upload_from_file(image_file)
        
        # Define o ficheiro como público (se as regras permitirem)
        # Atenção: Em produção, considere outras formas de acesso (tokens de download)
        blob.make_public() 
        
        logger.info(f"Ficheiro '{filename}' carregado para o Firebase Storage. URL: {blob.public_url}")
        return blob.public_url # Retorna a URL pública do ficheiro
    except Exception as e:
        logger.error(f"Erro ao carregar ficheiro para o Firebase Storage: {e}")
        return None

# --- ROTAS PRINCIPAIS E ESTÁTICAS ---
@app.route('/')
@app.route('/inicio')
def home():
    services_ref = get_services_collection_ref() # Renomeado de products_ref
    featured_services = [] # Renomeado de featured_products
    if services_ref:
        try:
            query = services_ref.limit(3).stream()
            for doc in query:
                service_data = doc.to_dict()
                service_data['id'] = doc.id
                # Garante que category_slug esteja presente
                # Se você adicionou no Firestore, ele virá de lá.
                # Caso contrário, adicione uma lógica para inferir ou um valor padrão.
                service_data['category_slug'] = service_data.get('category_slug', 'edificacoes') # Fallback para garantir que o link funcione
                
                if len(featured_services) == 0: service_data['badge'] = 'NOVO'
                featured_services.append(service_data)
        except Exception as e:
            logger.error(f"Erro ao buscar serviços em destaque: {e}")
            
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

@app.route('/portfolio') # NOVA ROTA PARA O PORTFÓLIO
def portfolio():
    services_ref = get_services_collection_ref()
    portfolio_projects = []
    if services_ref:
        try:
            # Busca todos os serviços/projetos para o portfólio.
            # Se você tiver um campo para marcar "projetos de portfólio" (ex: 'is_portfolio_item': True),
            # pode adicionar um .where('is_portfolio_item', '==', True) aqui.
            query = services_ref.stream()
            for doc in query:
                project_data = doc.to_dict()
                project_data['id'] = doc.id
                # Garante que category_slug esteja presente para a construção de links
                project_data['category_slug'] = project_data.get('category_slug', 'edificacoes') # Fallback
                portfolio_projects.append(project_data)
        except Exception as e:
            logger.error(f"Erro ao buscar projetos para o portfólio: {e}")
            flash("Ocorreu um erro ao carregar os projetos do portfólio.", "danger")
            portfolio_projects = [] # Garante que a lista esteja vazia em caso de erro

    return render_template('portfolio.html', projects=portfolio_projects)

# --- ROTAS DE SERVIÇOS E CATEGORIAS ---
@app.route('/area/<string:service_category_slug>') # Renomeado de /categoria/<string:category_name>
def service_category_overview(service_category_slug):
    logger.debug(f"Acessando service_category_overview com category_slug: {service_category_slug}")
    category_data = SERVICE_ROUTES_MAP.get(service_category_slug) # Atualizado para SERVICE_ROUTES_MAP
    if not category_data:
        logger.warning(f"Categoria de serviço '{service_category_slug}' não encontrada no SERVICE_ROUTES_MAP.")
        flash(f'Categoria de serviço "{service_category_slug}" não encontrada.', 'warning')
        return redirect(url_for('home'))

    # Prepara os subtópicos para exibição no template
    services_in_category = []
    for slug, title in category_data['services'].items(): # Atualizado para 'services'
        services_in_category.append({'key': slug, 'title': title})
    logger.debug(f"Serviços na categoria {service_category_slug}: {services_in_category}")

    return render_template('category_overview.html', 
                           category_key=service_category_slug, 
                           category_data=category_data,
                           services_in_category=services_in_category) # Passa os serviços para o template

@app.route('/<string:service_category_slug>/<string:service_slug>') # Renomeado de /<string:category_slug>/<string:subtopic_slug>
def service_detail_page(service_category_slug, service_slug):
    logger.debug(f"Acessando service_detail_page com category_slug: {service_category_slug}, service_slug: {service_slug}")
    
    category_data = SERVICE_ROUTES_MAP.get(service_category_slug) # Atualizado para SERVICE_ROUTES_MAP
    if not category_data:
        logger.warning(f"Categoria de serviço '{service_category_slug}' não encontrada no SERVICE_ROUTES_MAP.")
        flash('Página de serviço não encontrada.', 'warning')
        return redirect(url_for('home'))
        
    if service_slug not in category_data['services']:
        logger.warning(f"Service slug '{service_slug}' não encontrado na categoria '{service_category_slug}' no SERVICE_ROUTES_MAP.")
        flash('Página de serviço não encontrada.', 'warning')
        return redirect(url_for('home'))
        
    service_details_data = {} # Renomeado de subtopic_details_data
    if db:
        try:
            # Busca detalhes específicos do serviço no Firestore
            # Nota: A coleção 'service_details' deve conter documentos com o service_slug como ID
            service_ref = db.collection('service_details').document(service_slug).get() # Coleção alterada
            if service_ref.exists:
                service_details_data = service_ref.to_dict()
                logger.debug(f"Detalhes do serviço encontrados para '{service_slug}': {service_details_data}")
                if 'description_html' in service_details_data:
                    service_details_data['description_html'] = Markup(service_details_data['description_html'])
            else:
                logger.warning(f"Documento de detalhes do serviço não encontrado no Firestore para service_slug: {service_slug}")
        except Exception as e:
            logger.error(f"Erro ao buscar detalhes do serviço '{service_slug}' no Firestore: {e}")
    
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
            logger.debug(f"Projetos relacionados encontrados para '{service_slug}': {len(related_projects)}")
        except Exception as e:
            logger.error(f"ERRO ao buscar projetos para '{service_slug}': {e}")
            flash("Ocorreu um erro ao carregar os projetos relacionados.", "danger")
            related_projects = []

    content_title = service_details_data.get('title', category_data['services'][service_slug]) # Atualizado para 'services'
    
    return render_template('subtopic_page.html', # Mantém o nome do template por simplicidade, mas o conteúdo será alterado
                           content_title=content_title,
                           category=service_category_slug,
                           service_details=service_details_data, # Renomeado de subtopic_details
                           related_projects=related_projects) # Renomeado de products

# --- NOVA ROTA PARA PÁGINA DE FOTOS DO PROJETO ---
@app.route('/<string:service_category_slug>/<string:service_slug>/fotos')
def project_photos_page(service_category_slug, service_slug):
    logger.debug(f"Acessando project_photos_page com category_slug: {service_category_slug}, service_slug: {service_slug}")
    
    category_data = SERVICE_ROUTES_MAP.get(service_category_slug)
    if not category_data or service_slug not in category_data['services']:
        logger.warning(f"Projeto não encontrado para fotos: category_slug='{service_category_slug}', service_slug='{service_slug}'")
        flash('Página de fotos do projeto não encontrada.', 'warning')
        return redirect(url_for('home'))

    project_title = category_data['services'][service_slug]
    project_photos = [] # Lista para armazenar as URLs das fotos

    if db:
        try:
            # Busca o documento de fotos para o projeto
            # O ID do documento na coleção 'project_images' é o service_slug
            photos_doc = db.collection('project_images').document(service_slug).get()
            if photos_doc.exists:
                photos_data = photos_doc.to_dict()
                # Assumindo que o documento tem um campo 'image_urls' que é um array de strings (URLs públicas)
                project_photos = photos_data.get('image_urls', [])
                logger.debug(f"Fotos encontradas para '{service_slug}': {len(project_photos)} imagens.")
            else:
                logger.warning(f"Documento de fotos não encontrado para service_slug: {service_slug} na coleção 'project_images'.")
            
        except Exception as e:
            logger.error(f"Erro ao buscar fotos do projeto '{service_slug}': {e}")
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
                    users_ref.document(email).set({
                        'name': name, 'email': email,
                        'password_hash': generate_password_hash(password),
                        'created_at': firestore.SERVER_TIMESTAMP,
                        'role': 'user' # Todos os novos usuários são 'user' por padrão
                    })
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
            logger.error(f"Erro ao buscar serviços para administração: {e}")
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
        # image = request.form.get('image', '').strip() # REMOVIDO: Agora é um ficheiro
        service_slug = request.form.get('service_slug', '').strip()
        image_file = request.files.get('image_file') # NOVO: Obtém o ficheiro da imagem

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

        # Determina a category_slug a partir da service_slug
        found_category_slug = None
        for cat_slug, cat_data in SERVICE_ROUTES_MAP.items():
            if service_slug in cat_data['services']:
                found_category_slug = cat_slug
                break
        
        if not found_category_slug:
            flash('Erro: service_slug não corresponde a nenhuma categoria conhecida.', 'danger')
            logger.error(f"Erro ao adicionar serviço: service_slug '{service_slug}' não corresponde a nenhuma categoria conhecida.")
            return redirect(url_for('admin_services'))

        # NOVO: Carrega a imagem para o Firebase Storage
        image_url = upload_image_to_firebase_storage(image_file)
        if not image_url:
            flash('Erro ao carregar a imagem para o armazenamento.', 'danger')
            return redirect(url_for('admin_services'))

        try:
            # Adiciona um novo documento à coleção 'services'
            services_ref.add({
                'name': name,
                'description': description,
                'image_url': image_url, # NOVO: Guarda a URL da imagem do Storage
                'service_slug': service_slug,
                'category_slug': found_category_slug, # Adiciona a category_slug
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
        # image = request.form.get('image', '').strip() # REMOVIDO
        service_slug = request.form.get('service_slug', '').strip()
        image_file = request.files.get('image_file') # NOVO: Obtém o ficheiro da imagem
        
        if not all([name, description, service_slug]):
            flash('Por favor, preencha todos os campos obrigatórios.', 'warning')
            return redirect(url_for('edit_service', service_id=service_id))

        # Determina a category_slug a partir da service_slug
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
            'category_slug': found_category_slug # Atualiza a category_slug
        }

        # NOVO: Se um novo ficheiro de imagem for fornecido, faz o upload e atualiza a URL
        if image_file and image_file.filename != '':
            image_url = upload_image_to_firebase_storage(image_file)
            if not image_url:
                flash('Erro ao carregar a nova imagem para o armazenamento.', 'danger')
                return redirect(url_for('edit_service', service_id=service_id))
            update_data['image_url'] = image_url # Atualiza a URL da imagem

        try:
            service_doc_ref.update(update_data)
            flash('Serviço atualizado com sucesso!', 'success')
            logger.info(f"Serviço '{name}' (ID: {service_id}) atualizado com sucesso. Slug: {service_slug}, Categoria: {found_category_slug}")
            return redirect(url_for('admin_services'))
        except Exception as e:
            flash(f'Erro ao atualizar serviço: {e}', 'danger')
            logger.error(f"Erro ao atualizar serviço (ID: {service_id}): {e}")
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
        # Opcional: Adicionar lógica para apagar a imagem do Storage aqui
        # if 'image_url' in service_data:
        #     bucket = storage.bucket()
        #     blob = bucket.blob(filename_from_url(service_data['image_url']))
        #     blob.delete()

        services_ref.document(service_id).delete()
        flash('Serviço excluído com sucesso!', 'success')
        logger.info(f"Serviço com ID '{service_id}' excluído com sucesso.")
    except Exception as e:
        flash(f'Erro ao excluir serviço: {e}', 'danger')
        logger.error(f"Erro ao excluir serviço (ID: {service_id}): {e}")
    return redirect(url_for('admin_services'))

# --- Rota de API para Sugestões de Pesquisa ---
@app.route('/api/search_suggestions')
def search_suggestions():
    query_term = request.args.get('q', '').lower()
    suggestions = []
    
    if not query_term or len(query_term) < 2: # Retorna vazio se o termo for muito curto
        return jsonify(suggestions)

    services_ref = get_services_collection_ref()
    if not services_ref:
        logger.error("Erro: Coleção de serviços não disponível para sugestões de pesquisa.")
        return jsonify({"error": "Serviço de busca indisponível."}), 500

    try:
        # Pega todos os serviços (ou um número limitado, se houver muitos)
        # Atenção: Para grandes volumes, considere aprimorar a consulta do Firestore
        # ou usar um serviço de busca dedicado (ex: Algolia)
        all_services_docs = services_ref.stream() 
        
        for doc in all_services_docs:
            service_data = doc.to_dict()
            service_name = service_data.get('name', '').lower()
            service_description = service_data.get('description', '').lower()
            service_slug = service_data.get('service_slug')
            service_category_slug = service_data.get('category_slug', 'edificacoes') # Pega a categoria ou usa um padrão
            
            # Verifica se o termo de busca está no nome ou descrição do serviço
            if query_term in service_name or query_term in service_description:
                suggestions.append({
                    'name': service_data.get('name'),
                    'slug': service_slug,
                    'category_slug': service_category_slug, # Essencial para o link correto
                    'link_url': url_for('service_detail_page', service_category_slug=service_category_slug, service_slug=service_slug)
                })
            
            if len(suggestions) >= 10: # Limite o número de sugestões para melhor UX
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
