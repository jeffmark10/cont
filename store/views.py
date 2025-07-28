# store/views.py

import logging
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, JsonResponse # Importa JsonResponse para respostas AJAX
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Q, ObjectDoesNotExist # Importa ObjectDoesNotExist
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from urllib.parse import quote
from django.conf import settings
from django.contrib.auth import login
from django.core.cache import cache # Importa o módulo de cache
from django.views.decorators.cache import cache_page # Importa o decorador de cache de página
from django.db import transaction # Importa o módulo de transações
from django.db import models # Importa o módulo models para usar models.Prefetch

# Importa os novos modelos e constantes
from .models import Product, Category, Cart, CartItem, Profile, Order, OrderItem
from .forms import ContactForm, ProductForm, UserRegistrationForm, UserLoginForm, CheckoutForm
from .constants import ( # Importa todas as constantes de mensagem
    MSG_SUCCESS_GENERIC, MSG_ERROR_GENERIC, MSG_WARNING_GENERIC, MSG_INFO_GENERIC,
    CART_QUANTITY_INVALID, CART_STOCK_INSUFFICIENT, CART_ITEM_EXCEEDS_STOCK,
    CART_ITEM_REMOVED, CART_ITEM_UPDATED, CART_PERMISSION_DENIED,
    CART_EMPTY_CHECKOUT, CART_PRODUCT_ADDED, CART_MIGRATION_PARTIAL_STOCK,
    CART_MIGRATION_NO_STOCK, PRODUCT_ADD_SUCCESS, PRODUCT_UPDATE_SUCCESS,
    PRODUCT_DELETE_SUCCESS, PRODUCT_DELETE_INVALID_METHOD, PRODUCT_NOT_FOUND_SEARCH,
    PRODUCT_NO_FEATURED, PRODUCT_NO_LISTED, PRODUCT_CATEGORY_INVALID,
    PRICE_MIN_INVALID, PRICE_MAX_INVALID, AUTH_SIGNUP_SUCCESS, AUTH_SIGNUP_ERROR,
    AUTH_LOGIN_SUCCESS, AUTH_LOGIN_FAILED, AUTH_SELLER_ACCESS_DENIED,
    ORDER_ITEM_UPDATE_SUCCESS, ORDER_ITEM_PERMISSION_DENIED, ORDER_STATUS_UPDATED,
    ORDER_STATUS_INVALID, ORDER_NO_SELLER_PRODUCTS, ORDER_NO_ORDERS_FOUND,
    FORM_ERRORS, FORM_CONTACT_SUCCESS
)
from .utils import get_descendant_category_ids, apply_product_filters_and_sort, apply_order_filters_and_sort # Importa as funções utilitárias

# Configura o logger para este módulo
logger = logging.getLogger(__name__)

# --- Funções Auxiliares ---

def get_categories_tree():
    """
    Busca todas as categorias de nível superior e pré-carrega seus filhos
    para construir a árvore de categorias no menu. Usa cache para otimização.
    """
    categories = cache.get('root_categories_tree')
    if categories is None:
        root_categories = Category.objects.filter(parent__isnull=True).prefetch_related('children')
        categories = list(root_categories)
        cache.set('root_categories_tree', categories, 3600)
        logger.debug("Árvore de categorias carregada do DB e cacheada.")
    else:
        logger.debug("Árvore de categorias carregada do cache.")
    return categories

def get_or_create_cart(request):
    """
    Obtém o carrinho do usuário logado ou da sessão.
    Cria um novo carrinho se não existir.
    Lida com a migração de itens de um carrinho de sessão para um carrinho de usuário.
    """
    session_key = request.session.session_key
    if not session_key:
        request.session.save()
        session_key = request.session.session_key
        logger.debug(f"Nova chave de sessão criada: {session_key}")

    if request.user.is_authenticated:
        user_cart, user_cart_created = Cart.objects.get_or_create(user=request.user)
        if user_cart_created:
            logger.info(f"Carrinho criado para o usuário: {request.user.username}")

        session_cart = None
        if 'cart_id' in request.session:
            try:
                session_cart = Cart.objects.get(id=request.session['cart_id'], session_key=session_key)
                logger.debug(f"Carrinho de sessão encontrado para migração: {session_cart.id}")
            except Cart.DoesNotExist:
                logger.warning(f"Carrinho de sessão com ID {request.session['cart_id']} não encontrado ou chave de sessão inválida. Removendo da sessão.")
                del request.session['cart_id']
                session_cart = None

        if session_cart and session_cart != user_cart:
            logger.info(f"Iniciando migração de itens do carrinho de sessão ({session_cart.id}) para o carrinho do usuário ({user_cart.id}).")
            with transaction.atomic(): # Garante que a migração seja atômica
                for item in session_cart.items.select_related('product').all():
                    try:
                        user_cart_item, item_created = CartItem.objects.get_or_create(
                            cart=user_cart,
                            product=item.product,
                            defaults={'quantity': item.quantity}
                        )
                        if not item_created:
                            quantity_to_add = item.quantity
                            available_stock_for_addition = item.product.stock - user_cart_item.quantity

                            if available_stock_for_addition > 0:
                                actual_added_quantity = min(quantity_to_add, available_stock_for_addition)
                                user_cart_item.quantity += actual_added_quantity
                                user_cart_item.save()
                                logger.debug(f"Item '{item.product.name}' atualizado no carrinho do usuário. Adicionado: {actual_added_quantity}.")
                                if actual_added_quantity < quantity_to_add:
                                    messages.warning(request, CART_MIGRATION_PARTIAL_STOCK.format(
                                        actual_added_quantity=actual_added_quantity,
                                        product_name=item.product.name,
                                        remaining_quantity=(quantity_to_add - actual_added_quantity)
                                    ))
                                    logger.warning(f"Estoque insuficiente para migrar todas as unidades de '{item.product.name}'.")
                            else:
                                messages.warning(request, CART_MIGRATION_NO_STOCK.format(product_name=item.product.name))
                                logger.warning(f"Não foi possível migrar '{item.product.name}' para o carrinho do usuário devido ao estoque zero ou insuficiente.")
                        else:
                            logger.debug(f"Item '{item.product.name}' migrado para o carrinho do usuário com quantidade {item.quantity}.")
                        item.delete() # Remove o item do carrinho da sessão após a tentativa de migração
                    except Exception as e:
                        logger.exception(f"Erro ao migrar item '{item.product.name}' (ID: {item.id}) do carrinho de sessão para o carrinho do usuário: {e}")
                        messages.error(request, MSG_ERROR_GENERIC) # Mensagem genérica para o usuário

            if session_cart.items.count() == 0:
                session_cart.delete()
                logger.info(f"Carrinho de sessão ({session_cart.id}) excluído após migração.")

            if 'cart_id' in request.session:
                del request.session['cart_id']
                logger.debug("cart_id removido da sessão após migração.")

        return user_cart
    else:
        cart_id = request.session.get('cart_id')
        cart = None
        if cart_id:
            try:
                cart = Cart.objects.get(id=cart_id, session_key=session_key)
                logger.debug(f"Carrinho de sessão existente encontrado: {cart.id}")
            except Cart.DoesNotExist:
                logger.warning(f"Carrinho de sessão com ID {cart_id} não encontrado ou chave de sessão inválida. Criando novo carrinho.")
                pass

        if not cart:
            try:
                cart = Cart.objects.create(session_key=session_key)
                request.session['cart_id'] = cart.id
                logger.info(f"Novo carrinho de sessão criado: {cart.id}")
            except Exception as e:
                logger.exception(f"Erro ao criar novo carrinho de sessão: {e}")
                messages.error(request, MSG_ERROR_GENERIC)
                # Em caso de falha crítica na criação do carrinho, podemos redirecionar ou mostrar uma página de erro
                # return redirect('home') # Exemplo
                return None # Retorna None para indicar falha

        return cart

def is_seller_check(user):
    """
    Verifica se o usuário está autenticado e possui um perfil de vendedor.
    """
    is_seller = user.is_authenticated and hasattr(user, 'profile') and user.profile.is_seller
    if not is_seller:
        logger.warning(f"{AUTH_SELLER_ACCESS_DENIED} por usuário: {user.username if user.is_authenticated else 'Anônimo'}")
    return is_seller

seller_required = user_passes_test(is_seller_check, login_url='login')

# --- Helper para respostas AJAX de carrinho ---
def get_cart_data(cart):
    """
    Retorna os dados do carrinho formatados para uma resposta JSON.
    """
    cart_items_data = []
    for item in cart.items.select_related('product').all():
        cart_items_data.append({
            'id': item.id,
            'product_id': item.product.id,
            'product_name': item.product.name,
            'quantity': item.quantity,
            'price': float(item.product.price),
            'total_item_price': float(item.get_total_price()),
            'stock': item.product.stock,
            'image_url': item.product.get_optimized_image_url(width=50, height=50, crop='fill') if item.product.image else settings.STATIC_URL + 'favicon.png',
            'tracking_code': item.product.tracking_code,
        })
    return {
        'cart_count': cart.items.count(),
        'cart_total_price': float(cart.get_total_price()),
        'cart_items': cart_items_data,
    }


# --- Views Principais ---

def home_view(request):
    """
    Renderiza a página inicial, exibindo produtos em destaque.
    """
    try:
        featured_products_queryset = Product.objects.filter(is_featured=True, stock__gt=0).select_related('category', 'seller')[:4]
        featured_products_for_template = []
        for product in featured_products_queryset:
            product_data = {
                'pk': product.pk,
                'name': product.name,
                'price': product.price,
                'image': product.image,
                'optimized_src': product.get_optimized_image_url(width=400, height=400, crop='fill'),
                'optimized_srcset': f"{product.get_optimized_image_url(width=200, height=200, crop='fill')} 200w, " \
                                    f"{product.get_optimized_image_url(width=400, height=400, crop='fill')} 400w, " \
                                    f"{product.get_optimized_image_url(width=600, height=600, crop='fill')} 600w",
                'category': product.category,
                'seller': product.seller,
                'stock': product.stock,
                'is_featured': product.is_featured,
                'created_at': product.created_at,
                'updated_at': product.updated_at,
                'tracking_code': product.tracking_code,
            }
            featured_products_for_template.append(product_data)

        categories = get_categories_tree()
        context = {
            'featured_products': featured_products_for_template,
            'page_title': 'Bem-vindo à Jeci Store!',
            'categories': categories,
        }
        logger.debug("Página inicial renderizada.")
        return render(request, 'home.html', context)
    except Exception as e:
        logger.exception(f"Erro ao renderizar a página inicial: {e}")
        messages.error(request, MSG_ERROR_GENERIC)
        return render(request, '500.html', status=500) # Redireciona para a página de erro 500

def product_list_view(request, category_slug=None):
    """
    Exibe uma lista de produtos, com opções de filtro por categoria, busca,
    faixa de preço e ordenação.
    """
    try:
        products = Product.objects.filter(stock__gt=0).select_related('category', 'seller')
        current_category = None

        products, filter_context = apply_product_filters_and_sort(products, request.GET)

        if category_slug:
            try:
                current_category = get_object_or_404(Category, slug=category_slug)
                filter_context['current_category_filter'] = current_category
                logger.debug(f"Filtrando produtos por categoria: {current_category.name}")
            except ObjectDoesNotExist:
                messages.error(request, PRODUCT_CATEGORY_INVALID)
                logger.error(f"Categoria não encontrada para slug: {category_slug}")
                products = Product.objects.none() # Garante que nenhum produto seja exibido para categoria inválida

        if 'min_price' in request.GET and not filter_context['min_price']:
            messages.error(request, PRICE_MIN_INVALID)
        if 'max_price' in request.GET and not filter_context['max_price']:
            messages.error(request, PRICE_MAX_INVALID)

        paginator = Paginator(products, 8)
        page_number = request.GET.get('page')
        try:
            products = paginator.page(page_number)
            logger.debug(f"Página {products.number} de produtos carregada.")
        except PageNotAnInteger:
            products = paginator.page(1)
            logger.warning(f"Número de página inválido '{page_number}'. Redirecionando para a primeira página.")
        except EmptyPage:
            products = paginator.page(paginator.num_pages)
            logger.warning(f"Página '{page_number}' fora do intervalo. Redirecionando para a última página.")

        categories = get_categories_tree()
        context = {
            'products': products,
            'current_category': current_category,
            'page_title': current_category.name if current_category else 'Nossos Produtos',
            'categories': categories,
            **filter_context,
        }
        return render(request, 'product_list.html', context)
    except Exception as e:
        logger.exception(f"Erro ao renderizar a lista de produtos: {e}")
        messages.error(request, MSG_ERROR_GENERIC)
        return render(request, '500.html', status=500)

def product_detail_view(request, pk):
    """
    Exibe os detalhes de um produto específico.
    """
    try:
        product = get_object_or_404(Product.objects.select_related('category', 'seller'), pk=pk)
        categories = get_categories_tree()
        context = {
            'product': product,
            'page_title': product.name,
            'categories': categories,
        }
        logger.debug(f"Detalhes do produto {product.name} (ID: {pk}) renderizados.")
        return render(request, 'product_detail.html', context)
    except Exception as e:
        logger.exception(f"Erro ao renderizar detalhes do produto {pk}: {e}")
        messages.error(request, MSG_ERROR_GENERIC)
        return render(request, '500.html', status=500)

@cache_page(60 * 15) # Cache por 15 minutos
def about_view(request):
    """
    Renderiza a página 'Sobre Nós'.
    """
    try:
        categories = get_categories_tree()
        context = {
            'page_title': 'Sobre a Jeci Store',
            'categories': categories,
        }
        logger.debug("Página 'Sobre Nós' renderizada.")
        return render(request, 'about.html', context)
    except Exception as e:
        logger.exception(f"Erro ao renderizar a página 'Sobre Nós': {e}")
        messages.error(request, MSG_ERROR_GENERIC)
        return render(request, '500.html', status=500)

@cache_page(60 * 15) # Cache por 15 minutos
def contact_view(request):
    """
    Lida com o formulário de contato e renderiza a página 'Fale Conosco'.
    """
    try:
        categories = get_categories_tree()
        if request.method == 'POST':
            form = ContactForm(request.POST)
            if form.is_valid():
                name = form.cleaned_data['name']
                email = form.cleaned_data['email']
                message = form.cleaned_data['message']

                logger.info(f"Formulário de contato recebido de {name} ({email}). Mensagem: {message[:50]}...")

                messages.success(request, FORM_CONTACT_SUCCESS)
                return redirect('store:contact')
            else:
                messages.error(request, FORM_ERRORS)
                logger.error(f"Erros no formulário de contato: {form.errors.as_json()}") # Loga erros do formulário em JSON
        else:
            form = ContactForm()

        context = {
            'page_title': 'Fale Conosco',
            'categories': categories,
            'form': form,
        }
        logger.debug("Página 'Fale Conosco' renderizada.")
        return render(request, 'contact.html', context)
    except Exception as e:
        logger.exception(f"Erro ao processar a página de contato: {e}")
        messages.error(request, MSG_ERROR_GENERIC)
        return render(request, '500.html', status=500)

# --- Views de Carrinho de Compras (com suporte AJAX) ---

def add_to_cart(request, product_id):
    """
    Adiciona um produto ao carrinho ou atualiza sua quantidade.
    Lida com validações de estoque e respostas AJAX.
    """
    try:
        product = get_object_or_404(Product, id=product_id)
        cart = get_or_create_cart(request)
        if cart is None: # Se a criação do carrinho falhou
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': MSG_ERROR_GENERIC}, status=500)
            return redirect('home') # Ou para uma página de erro

        quantity = int(request.POST.get('quantity', 1))

        if quantity <= 0:
            messages.error(request, CART_QUANTITY_INVALID)
            logger.warning(f"Tentativa de adicionar quantidade inválida ({quantity}) para o produto ID: {product_id}")
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': CART_QUANTITY_INVALID}, status=400)
            return redirect('store:product_detail', pk=product_id)

        if product.stock < quantity:
            messages.error(request, CART_STOCK_INSUFFICIENT.format(stock=product.stock, product_name=product.name))
            logger.warning(f"Estoque insuficiente para adicionar {quantity} de '{product.name}' (ID: {product_id}). Estoque: {product.stock}")
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': CART_STOCK_INSUFFICIENT.format(stock=product.stock, product_name=product.name)}, status=400)
            return redirect('store:product_detail', pk=product_id)

        cart_item, created = CartItem.objects.get_or_create(cart=cart, product=product, defaults={'quantity': quantity})
        if not created:
            if cart_item.quantity + quantity > product.stock:
                messages.error(request, CART_ITEM_EXCEEDS_STOCK.format(
                    current_quantity=cart_item.quantity,
                    product_name=product.name,
                    available_stock=product.stock
                ))
                logger.warning(f"Tentativa de exceder estoque para '{product.name}' (ID: {product_id}). Já no carrinho: {cart_item.quantity}, Tentativa: {quantity}, Estoque: {product.stock}")
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'message': CART_ITEM_EXCEEDS_STOCK.format(
                        current_quantity=cart_item.quantity,
                        product_name=product.name,
                        available_stock=product.stock
                    )}, status=400)
                return redirect('store:product_detail', pk=product_id)
            cart_item.quantity += quantity
            cart_item.save()
            logger.info(f"Quantidade de '{product.name}' (ID: {product_id}) atualizada no carrinho para {cart_item.quantity}.")
        else:
            logger.info(f"{quantity}x '{product.name}' (ID: {product_id}) adicionado ao carrinho.")

        messages.success(request, CART_PRODUCT_ADDED.format(quantity=quantity, product_name=product.name))

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': CART_PRODUCT_ADDED.format(quantity=quantity, product_name=product.name), **get_cart_data(cart)})
        return redirect('store:product_detail', pk=product_id)
    except ValueError as e:
        messages.error(request, CART_QUANTITY_INVALID)
        logger.error(f"ValueError ao adicionar ao carrinho para produto ID {product_id}: {e}")
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': CART_QUANTITY_INVALID}, status=400)
        return redirect('store:product_detail', pk=product_id)
    except Product.DoesNotExist:
        messages.error(request, MSG_ERROR_GENERIC)
        logger.error(f"Produto com ID {product_id} não encontrado ao adicionar ao carrinho.")
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': MSG_ERROR_GENERIC}, status=404)
        return redirect('store:product_list')
    except Exception as e:
        logger.exception(f"Erro inesperado ao adicionar produto ao carrinho (Produto ID: {product_id}): {e}")
        messages.error(request, MSG_ERROR_GENERIC)
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': MSG_ERROR_GENERIC}, status=500)
        return redirect('store:product_list')


def view_cart(request):
    """
    Exibe o conteúdo do carrinho de compras do usuário.
    """
    try:
        cart = get_or_create_cart(request)
        if cart is None: # Se a criação do carrinho falhou
            messages.error(request, MSG_ERROR_GENERIC)
            return redirect('home')

        cart_items = cart.items.select_related('product').all()
        categories = get_categories_tree()
        context = {
            'cart': cart,
            'cart_items': cart_items,
            'page_title': 'Seu Carrinho',
            'categories': categories,
        }
        logger.debug(f"Carrinho (ID: {cart.id}) visualizado. Itens: {cart_items.count()}")
        return render(request, 'cart.html', context)
    except Exception as e:
        logger.exception(f"Erro ao visualizar o carrinho: {e}")
        messages.error(request, MSG_ERROR_GENERIC)
        return render(request, '500.html', status=500)

def update_cart_item(request, item_id):
    """
    Atualiza a quantidade de um item no carrinho ou o remove se a quantidade for zero.
    Lida com validações de estoque e respostas AJAX.
    """
    try:
        cart_item = get_object_or_404(CartItem.objects.select_related('product'), id=item_id)
        cart = get_or_create_cart(request)
        if cart is None:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': MSG_ERROR_GENERIC}, status=500)
            return redirect('home')

        if cart_item.cart != cart:
            messages.error(request, CART_PERMISSION_DENIED)
            logger.warning(f"Tentativa de modificar item de carrinho não pertencente ao usuário/sessão. Item ID: {item_id}, Carrinho do usuário/sessão: {cart.id}")
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': CART_PERMISSION_DENIED}, status=403)
            return redirect('store:view_cart')

        if request.method == 'POST':
            try:
                new_quantity = int(request.POST.get('quantity'))

                if new_quantity <= 0:
                    product_name = cart_item.product.name
                    cart_item.delete()
                    messages.info(request, CART_ITEM_REMOVED.format(product_name=product_name))
                    logger.info(f"Item '{product_name}' (ID: {item_id}) removido do carrinho. Nova quantidade: {new_quantity}")
                    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                        return JsonResponse({'success': True, 'message': CART_ITEM_REMOVED.format(product_name=product_name), 'removed_item_id': item_id, **get_cart_data(cart)})
                else:
                    if new_quantity > cart_item.product.stock:
                        messages.error(request, CART_ITEM_EXCEEDS_STOCK.format(
                            current_quantity=cart_item.quantity,
                            product_name=cart_item.product.name,
                            available_stock=cart_item.product.stock
                        ))
                        logger.warning(f"Tentativa de atualizar quantidade de '{cart_item.product.name}' (ID: {item_id}) para {new_quantity} excede estoque ({cart_item.product.stock}).")
                        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                            return JsonResponse({'success': False, 'message': CART_ITEM_EXCEEDS_STOCK.format(
                                current_quantity=cart_item.quantity,
                                product_name=cart_item.product.name,
                                available_stock=cart_item.product.stock
                            )}, status=400)
                        return redirect('store:view_cart')

                    cart_item.quantity = new_quantity
                    cart_item.save()
                    messages.success(request, CART_ITEM_UPDATED.format(product_name=cart_item.product.name, new_quantity=new_quantity))
                    logger.info(f"Quantidade de '{cart_item.product.name}' (ID: {item_id}) atualizada para {new_quantity}.")
                    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                        return JsonResponse({'success': True, 'message': CART_ITEM_UPDATED.format(product_name=cart_item.product.name, new_quantity=new_quantity), 'updated_item_id': item_id, **get_cart_data(cart)})
            except ValueError as e:
                messages.error(request, CART_QUANTITY_INVALID)
                logger.error(f"ValueError ao atualizar item do carrinho ID {item_id}: {e}")
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'message': CART_QUANTITY_INVALID}, status=400)
            except Exception as e: # Captura outras exceções durante a atualização do item
                logger.exception(f"Erro inesperado ao atualizar item do carrinho ID {item_id}: {e}")
                messages.error(request, MSG_ERROR_GENERIC)
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'message': MSG_ERROR_GENERIC}, status=500)

        return redirect('store:view_cart')
    except CartItem.DoesNotExist:
        messages.error(request, MSG_ERROR_GENERIC)
        logger.error(f"CartItem com ID {item_id} não encontrado ao tentar atualizar.")
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': MSG_ERROR_GENERIC}, status=404)
        return redirect('store:view_cart')
    except Exception as e:
        logger.exception(f"Erro inesperado na view update_cart_item para item ID {item_id}: {e}")
        messages.error(request, MSG_ERROR_GENERIC)
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': MSG_ERROR_GENERIC}, status=500)
        return redirect('store:view_cart')


def remove_from_cart(request, item_id):
    """
    Remove um item específico do carrinho de compras.
    Lida com validações de permissão e respostas AJAX.
    """
    try:
        cart_item = get_object_or_404(CartItem.objects.select_related('product'), id=item_id)
        cart = get_or_create_cart(request)
        if cart is None:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': MSG_ERROR_GENERIC}, status=500)
            return redirect('home')

        if cart_item.cart != cart:
            messages.error(request, CART_PERMISSION_DENIED)
            logger.warning(f"Tentativa de remover item de carrinho não pertencente ao usuário/sessão. Item ID: {item_id}, Carrinho do usuário/sessão: {cart.id}")
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': CART_PERMISSION_DENIED}, status=403)
            return redirect('store:view_cart')

        product_name = cart_item.product.name
        cart_item.delete()
        messages.info(request, CART_ITEM_REMOVED.format(product_name=product_name))
        logger.info(f"Item '{product_name}' (ID: {item_id}) removido do carrinho.")

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': CART_ITEM_REMOVED.format(product_name=product_name), 'removed_item_id': item_id, **get_cart_data(cart)})
        return redirect('store:view_cart')
    except CartItem.DoesNotExist:
        messages.error(request, MSG_ERROR_GENERIC)
        logger.error(f"CartItem com ID {item_id} não encontrado ao tentar remover.")
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': MSG_ERROR_GENERIC}, status=404)
        return redirect('store:view_cart')
    except Exception as e:
        logger.exception(f"Erro inesperado ao remover item do carrinho (Item ID: {item_id}): {e}")
        messages.error(request, MSG_ERROR_GENERIC)
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': MSG_ERROR_GENERIC}, status=500)
        return redirect('store:view_cart')


# View para finalizar a compra com formulário
def checkout_view(request):
    """
    Processa o checkout do carrinho, cria um pedido e redireciona para o WhatsApp.
    Realiza validação de estoque transacional.
    """
    try:
        cart = get_or_create_cart(request)
        if cart is None:
            messages.error(request, MSG_ERROR_GENERIC)
            return redirect('home')

        if not cart.items.exists():
            messages.warning(request, CART_EMPTY_CHECKOUT)
            logger.warning(f"Tentativa de checkout com carrinho vazio para usuário/sessão: {request.user.username if request.user.is_authenticated else request.session.session_key}")
            return redirect('store:view_cart')

        if request.method == 'POST':
            form = CheckoutForm(request.POST, user=request.user)
            if form.is_valid():
                full_name = form.cleaned_data['full_name']
                email = form.cleaned_data['email']
                phone_number = form.cleaned_data['phone_number']
                shipping_address = form.cleaned_data['shipping_address']

                with transaction.atomic():
                    items_to_process = []
                    for item in cart.items.select_related('product').all():
                        product = item.product
                        # Re-check do estoque antes de finalizar a compra
                        if product.stock < item.quantity:
                            messages.error(request, CART_STOCK_INSUFFICIENT.format(
                                product_name=product.name,
                                stock=product.stock
                            ))
                            logger.error(f"Estoque insuficiente no checkout para '{product.name}' (ID: {product.id}).")
                            return redirect('store:view_cart')
                        items_to_process.append(item)

                    order = Order.objects.create(
                        user=request.user if request.user.is_authenticated else None,
                        session_key=request.session.session_key if not request.user.is_authenticated else None,
                        shipping_address=shipping_address,
                        contact_info=f"Nome: {full_name}, Email: {email}, Telefone: {phone_number}",
                        total_price=cart.get_total_price(),
                        status='pending'
                    )
                    logger.info(f"Pedido #{order.id} criado para {full_name}.")

                    whatsapp_message_parts = [
                        f"Olá, gostaria de finalizar meu pedido na Jeci Store!",
                        f"Pedido #{order.id}",
                        f"Cliente: {full_name}",
                        f"Contato: {phone_number} / {email}",
                        f"Endereço de Entrega: {shipping_address}",
                        "\nItens no pedido:"
                    ]

                    for item in items_to_process:
                        OrderItem.objects.create(
                            order=order,
                            product=item.product,
                            quantity=item.quantity,
                            price_at_purchase=item.product.price,
                            tracking_code="",
                            status='pending' # Status inicial do item do pedido
                        )
                        item.product.stock -= item.quantity
                        item.product.save()
                        whatsapp_message_parts.append(f"- {item.quantity}x {item.product.name} (R${item.product.price:.2f})")
                        if item.product.tracking_code:
                            whatsapp_message_parts.append(f" Código de Referência: {item.product.tracking_code}")
                        logger.debug(f"Item de pedido criado para '{item.product.name}'. Estoque atualizado para {item.product.stock}.")

                    cart.items.all().delete()
                    cart.delete()
                    if 'cart_id' in request.session:
                        del request.session['cart_id']
                    logger.info(f"Carrinho (ID: {cart.id}) limpo após a criação do pedido #{order.id}.")

                    whatsapp_message_parts.append(f"\nValor Total do Pedido: R${order.total_price:.2f}")
                    whatsapp_message_parts.append("\nPor favor, me ajude a prosseguir com o pagamento e envio.")

                    full_whatsapp_message = "\n".join(whatsapp_message_parts)
                    encoded_message = quote(full_whatsapp_message)
                    whatsapp_url = f"https://wa.me/{settings.STORE_WHATSAPP_NUMBER}?text={encoded_message}"

                    messages.success(request, MSG_INFO_GENERIC.format(message=f"Seu pedido #{order.id} foi criado com sucesso! Redirecionando para o WhatsApp para finalizar."))
                    logger.info(f"Link de checkout do WhatsApp gerado para o pedido {order.id}.")
                    return redirect(whatsapp_url)
            else:
                messages.error(request, FORM_ERRORS)
                logger.error(f"Erros no formulário de checkout: {form.errors.as_json()}")
        else:
            form = CheckoutForm(user=request.user)

        categories = get_categories_tree()
        context = {
            'page_title': 'Finalizar Compra',
            'cart': cart,
            'form': form,
            'categories': categories,
        }
        return render(request, 'checkout.html', context)
    except Exception as e:
        logger.exception(f"Erro inesperado durante o processo de checkout: {e}")
        messages.error(request, MSG_ERROR_GENERIC)
        return render(request, '500.html', status=500)


def checkout_whatsapp_view(request):
    """
    Redireciona para a nova view de checkout com formulário.
    """
    return redirect('store:checkout')


# --- Views de Autenticação e Perfil (Básicas) ---

def signup_view(request):
    """
    Lida com o registro de novos usuários.
    """
    try:
        categories = get_categories_tree()
        if request.method == 'POST':
            form = UserRegistrationForm(request.POST)
            if form.is_valid():
                user = form.save()
                login(request, user)
                messages.success(request, AUTH_SIGNUP_SUCCESS)
                logger.info(f"Novo usuário registrado e logado: {user.username}")
                return redirect('home')
            else:
                messages.error(request, AUTH_SIGNUP_ERROR)
                logger.error(f"Erros no formulário de registro: {form.errors.as_json()}")
        else:
            form = UserRegistrationForm()
        context = {
            'page_title': 'Registrar-se',
            'form': form,
            'categories': categories,
        }
        logger.debug("Página de registro renderizada.")
        return render(request, 'registration/signup.html', context)
    except Exception as e:
        logger.exception(f"Erro ao processar o registro de usuário: {e}")
        messages.error(request, MSG_ERROR_GENERIC)
        return render(request, '500.html', status=500)

def login_view(request):
    """
    Lida com o login de usuários existentes.
    """
    try:
        categories = get_categories_tree()
        if request.method == 'POST':
            form = UserLoginForm(request, data=request.POST)
            if form.is_valid():
                user = form.get_user()
                login(request, user)
                messages.success(request, AUTH_LOGIN_SUCCESS.format(username=user.username))
                logger.info(f"Usuário logado: {user.username}")
                return redirect('home')
            else:
                messages.error(request, AUTH_LOGIN_FAILED)
                logger.warning(f"Tentativa de login falhou para o usuário: {request.POST.get('username')}. Erros: {form.errors.as_json()}")
        else:
            form = UserLoginForm()
        context = {
            'page_title': 'Entrar',
            'form': form,
            'categories': categories,
        }
        logger.debug("Página de login renderizada.")
        return render(request, 'registration/login.html', context)
    except Exception as e:
        logger.exception(f"Erro ao processar o login de usuário: {e}")
        messages.error(request, MSG_ERROR_GENERIC)
        return render(request, '500.html', status=500)


@login_required
def user_profile_view(request):
    """
    Exibe o perfil do usuário logado e seus pedidos.
    """
    try:
        categories = get_categories_tree()
        user_orders = Order.objects.filter(user=request.user).order_by('-created_at').prefetch_related(
            models.Prefetch('items', queryset=OrderItem.objects.select_related('product'))
        )

        context = {
            'page_title': f'Perfil de {request.user.username}',
            'categories': categories,
            'user_orders': user_orders,
        }
        logger.debug(f"Perfil do usuário {request.user.username} renderizado.")
        return render(request, 'registration/user_profile.html', context)
    except Exception as e:
        logger.exception(f"Erro ao renderizar o perfil do usuário {request.user.username}: {e}")
        messages.error(request, MSG_ERROR_GENERIC)
        return render(request, '500.html', status=500)

# --- Manipuladores de Erro Personalizados ---

def custom_404_view(request, exception):
    """
    Manipulador de erro para páginas não encontradas (404).
    """
    categories = get_categories_tree()
    context = {
        'page_title': 'Página Não Encontrada',
        'categories': categories,
    }
    logger.warning(f"Página 404 acessada para URL: {request.path}. Exceção: {exception}")
    return render(request, '404.html', context, status=404)

def custom_500_view(request):
    """
    Manipulador de erro para erros internos do servidor (500).
    """
    categories = get_categories_tree()
    context = {
        'page_title': 'Erro Interno do Servidor',
        'categories': categories,
    }
    # O log de exceção para 500 geralmente é capturado pelo middleware do Django,
    # mas um log adicional aqui pode ser útil.
    logger.error(f"Página 500 acessada. Request path: {request.path}")
    return render(request, '500.html', context, status=500)


# --- NOVAS VIEWS PARA VENDEDORES ---

@seller_required
def add_product_view(request):
    """
    Permite que um vendedor adicione um novo produto.
    """
    try:
        categories = get_categories_tree()
        if request.method == 'POST':
            form = ProductForm(request.POST, request.FILES)
            if form.is_valid():
                product = form.save(commit=False)
                product.seller = request.user
                product.save()
                messages.success(request, PRODUCT_ADD_SUCCESS.format(product_name=product.name))
                logger.info(f"Produto '{product.name}' adicionado por {request.user.username}.")
                return redirect('store:my_products')
            else:
                messages.error(request, FORM_ERRORS)
                logger.error(f"Erro ao adicionar produto por {request.user.username}: {form.errors.as_json()}")
        else:
            form = ProductForm()

        context = {
            'page_title': 'Adicionar Novo Produto',
            'form': form,
            'categories': categories,
        }
        logger.debug(f"Página 'Adicionar Novo Produto' renderizada para {request.user.username}.")
        return render(request, 'store/seller/seller_add_product.html', context)
    except Exception as e:
        logger.exception(f"Erro ao adicionar produto por {request.user.username}: {e}")
        messages.error(request, MSG_ERROR_GENERIC)
        return render(request, '500.html', status=500)


@seller_required
def my_products_view(request):
    """
    Exibe uma lista dos produtos do vendedor logado, com opções de filtro e ordenação.
    """
    try:
        categories_tree = get_categories_tree()
        products = Product.objects.filter(seller=request.user).select_related('category', 'seller')

        products, filter_context = apply_product_filters_and_sort(products, request.GET, is_seller_view=True)

        if 'min_price' in request.GET and not filter_context['min_price']:
            messages.error(request, PRICE_MIN_INVALID)
        if 'max_price' in request.GET and not filter_context['max_price']:
            messages.error(request, PRICE_MAX_INVALID)
        if 'category_slug' in request.GET and not filter_context['current_category_filter'] and filter_context['category_slug']:
            messages.error(request, PRODUCT_CATEGORY_INVALID)


        paginator = Paginator(products, 10)
        page_number = request.GET.get('page')
        try:
            products = paginator.page(page_number)
            logger.debug(f"Página {products.number} de produtos do vendedor {request.user.username} carregada.")
        except PageNotAnInteger:
            products = paginator.page(1)
            logger.warning(f"Número de página inválido '{page_number}' para produtos do vendedor. Redirecionando para a primeira página.")
        except EmptyPage:
            products = paginator.page(paginator.num_pages)
            logger.warning(f"Página '{page_number}' fora do intervalo para produtos do vendedor. Redirecionando para a última página.")

        context = {
            'page_title': 'Meus Produtos',
            'products': products,
            'categories': categories_tree,
            **filter_context,
        }
        return render(request, 'store/seller/seller_my_products.html', context)
    except Exception as e:
        logger.exception(f"Erro ao renderizar 'Meus Produtos' para o vendedor {request.user.username}: {e}")
        messages.error(request, MSG_ERROR_GENERIC)
        return render(request, '500.html', status=500)


@seller_required
def edit_product_view(request, pk):
    """
    Permite que um vendedor edite um produto existente.
    """
    try:
        product = get_object_or_404(Product.objects.select_related('category', 'seller'), pk=pk, seller=request.user)
        categories = get_categories_tree()
        if request.method == 'POST':
            form = ProductForm(request.POST, request.FILES, instance=product)
            if form.is_valid():
                form.save()
                messages.success(request, PRODUCT_UPDATE_SUCCESS.format(product_name=product.name))
                logger.info(f"Produto '{product.name}' (ID: {product.pk}) atualizado por {request.user.username}.")
                return redirect('store:my_products')
            else:
                messages.error(request, FORM_ERRORS)
                logger.error(f"Erro ao editar produto '{product.name}' (ID: {product.pk}) por {request.user.username}: {form.errors.as_json()}")
        else:
            form = ProductForm(instance=product)

        context = {
            'page_title': f'Editar Produto: {product.name}',
            'form': form,
            'product': product,
            'categories': categories,
        }
        logger.debug(f"Página 'Editar Produto' para '{product.name}' (ID: {product.pk}) renderizada para {request.user.username}.")
        return render(request, 'store/seller/seller_edit_product.html', context)
    except Product.DoesNotExist:
        messages.error(request, MSG_ERROR_GENERIC)
        logger.error(f"Produto com ID {pk} não encontrado ou não pertence ao vendedor {request.user.username} ao tentar editar.")
        return redirect('store:my_products')
    except Exception as e:
        logger.exception(f"Erro inesperado ao editar produto {pk} por {request.user.username}: {e}")
        messages.error(request, MSG_ERROR_GENERIC)
        return render(request, '500.html', status=500)


@seller_required
def delete_product_view(request, pk):
    """
    Permite que um vendedor exclua um produto.
    """
    try:
        product = get_object_or_404(Product, pk=pk, seller=request.user)
        if request.method == 'POST':
            product_name = product.name
            product.delete()
            messages.info(request, PRODUCT_DELETE_SUCCESS.format(product_name=product_name))
            logger.info(f"Produto '{product_name}' (ID: {pk}) excluído por {request.user.username}.")
            return redirect('store:my_products')

        messages.error(request, PRODUCT_DELETE_INVALID_METHOD)
        logger.warning(f"Tentativa de exclusão de produto (ID: {pk}) com método inválido por {request.user.username}.")
        return redirect('store:my_products')
    except Product.DoesNotExist:
        messages.error(request, MSG_ERROR_GENERIC)
        logger.error(f"Produto com ID {pk} não encontrado ou não pertence ao vendedor {request.user.username} ao tentar excluir.")
        return redirect('store:my_products')
    except Exception as e:
        logger.exception(f"Erro inesperado ao excluir produto {pk} por {request.user.username}: {e}")
        messages.error(request, MSG_ERROR_GENERIC)
        return render(request, '500.html', status=500)


# Views para Gerenciamento de Pedidos do Vendedor
@seller_required
def seller_orders_view(request):
    """
    Exibe uma lista de pedidos que contêm produtos do vendedor logado,
    com opções de filtro e ordenação.
    """
    try:
        categories = get_categories_tree()

        seller_products_ids = Product.objects.filter(seller=request.user).values_list('id', flat=True)

        order_items_for_seller = OrderItem.objects.filter(product__id__in=seller_products_ids).select_related('order', 'product')

        order_ids = order_items_for_seller.values_list('order__id', flat=True).distinct()

        orders = Order.objects.filter(id__in=order_ids)

        orders, filter_context = apply_order_filters_and_sort(orders, request.GET, seller_products_ids)

        paginator = Paginator(orders, 10)
        page_number = request.GET.get('page')
        try:
            orders = paginator.page(page_number)
        except PageNotAnInteger:
            orders = paginator.page(1)
        except EmptyPage:
            orders = paginator.page(paginator.num_pages)

        context = {
            'page_title': 'Meus Pedidos de Venda',
            'orders': orders,
            'categories': categories,
            'all_statuses': Order.STATUS_CHOICES,
            **filter_context,
        }
        logger.debug(f"Página 'Meus Pedidos de Venda' renderizada para {request.user.username}.")
        return render(request, 'store/seller/seller_orders.html', context)
    except Exception as e:
        logger.exception(f"Erro ao renderizar 'Meus Pedidos de Venda' para o vendedor {request.user.username}: {e}")
        messages.error(request, MSG_ERROR_GENERIC)
        return render(request, '500.html', status=500)


@seller_required
def seller_order_detail_view(request, order_id):
    """
    Exibe os detalhes de um pedido específico para um vendedor,
    mostrando apenas os itens que ele vende.
    """
    try:
        categories = get_categories_tree()

        order = get_object_or_404(Order.objects.prefetch_related(
            models.Prefetch('items', queryset=OrderItem.objects.select_related('product'))
        ), id=order_id)

        seller_order_items = [
            item for item in order.items.all()
            if item.product and item.product.seller == request.user
        ]

        if not seller_order_items:
            messages.error(request, ORDER_NO_SELLER_PRODUCTS)
            logger.warning(f"Tentativa de acesso não autorizado ao detalhe do pedido {order_id} por {request.user.username}.")
            return redirect('store:seller_orders')

        context = {
            'page_title': f'Detalhes do Pedido #{order.id}',
            'order': order,
            'seller_order_items': seller_order_items,
            'categories': categories,
            'order_statuses': Order.STATUS_CHOICES,
            'order_item_statuses': OrderItem.ITEM_STATUS_CHOICES,
        }
        logger.debug(f"Página de detalhes do pedido #{order.id} renderizada para {request.user.username}.")
        return render(request, 'store/seller/seller_order_detail.html', context)
    except Order.DoesNotExist:
        messages.error(request, MSG_ERROR_GENERIC)
        logger.error(f"Pedido com ID {order_id} não encontrado ao tentar visualizar detalhes.")
        return redirect('store:seller_orders')
    except Exception as e:
        logger.exception(f"Erro inesperado ao visualizar detalhes do pedido {order_id} por {request.user.username}: {e}")
        messages.error(request, MSG_ERROR_GENERIC)
        return render(request, '500.html', status=500)


@seller_required
@transaction.atomic
def seller_update_order_item_status(request, item_id):
    """
    Permite que um vendedor atualize o código de rastreamento e o status de um item de pedido.
    Após a atualização do item, tenta atualizar o status do pedido principal.
    """
    if request.method == 'POST':
        try:
            order_item = get_object_or_404(OrderItem.objects.select_related('product__seller', 'order'), id=item_id)

            if not order_item.product or order_item.product.seller != request.user:
                messages.error(request, ORDER_ITEM_PERMISSION_DENIED)
                logger.warning(f"Tentativa de atualização não autorizada do item de pedido {item_id} por {request.user.username}.")
                return redirect('store:seller_orders')

            new_item_status = request.POST.get('status')
            new_tracking_code = request.POST.get('tracking_code', '').strip()

            valid_item_statuses = [choice[0] for choice in OrderItem.ITEM_STATUS_CHOICES]
            if new_item_status and new_item_status in valid_item_statuses:
                order_item.tracking_code = new_tracking_code
                order_item.status = new_item_status
                order_item.save()
                logger.info(f"OrderItem {item_id} (Produto: '{order_item.product.name}') atualizado para status '{new_item_status}' e código de rastreamento '{new_tracking_code}' por {request.user.username}.")

                if order_item.order.update_status_based_on_items(updated_item_status=new_item_status):
                    messages.success(request, ORDER_STATUS_UPDATED.format(
                        order_id=order_item.order.id,
                        status_display=order_item.order.get_status_display()
                    ))

                messages.success(request, ORDER_ITEM_UPDATE_SUCCESS.format(
                    product_name=order_item.product.name,
                    order_id=order_item.order.id
                ))
                return redirect('store:seller_order_detail', order_id=order_item.order.id)
            else:
                messages.error(request, ORDER_STATUS_INVALID)
                logger.warning(f"Status inválido recebido para o item de pedido {item_id}: '{new_item_status}' por {request.user.username}.")
                return redirect('store:seller_order_detail', order_id=order_item.order.id)
        except OrderItem.DoesNotExist:
            messages.error(request, MSG_ERROR_GENERIC)
            logger.error(f"OrderItem com ID {item_id} não encontrado ao tentar atualizar status/rastreamento.")
            return redirect('store:seller_orders')
        except Exception as e:
            logger.exception(f"Erro inesperado ao atualizar item de pedido {item_id} por {request.user.username}: {e}")
            messages.error(request, MSG_ERROR_GENERIC)
            return redirect('store:seller_orders')
    messages.error(request, MSG_ERROR_GENERIC)
    return redirect('store:seller_orders')
