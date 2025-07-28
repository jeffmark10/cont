# store/utils.py

import logging
from django.db.models import Q
from .models import Category, Order, OrderItem, Product # Importa os modelos necessários

logger = logging.getLogger(__name__)

def get_descendant_category_ids(category):
    """
    Retorna uma lista de IDs da categoria fornecida e de todas as suas subcategorias
    em qualquer nível de profundidade.

    Args:
        category (Category): O objeto da categoria inicial.

    Returns:
        list: Uma lista de inteiros contendo os IDs das categorias descendentes.
    """
    category_ids = [category.id]
    for child in category.children.all():
        category_ids.extend(get_descendant_category_ids(child)) # Chamada recursiva
    return category_ids

def apply_product_filters_and_sort(queryset, request_get_params, is_seller_view=False):
    """
    Aplica filtros de busca, preço, categoria e estoque, e ordenação a um queryset de produtos.

    Args:
        queryset (QuerySet): O queryset inicial de produtos.
        request_get_params (dict): Dicionário com os parâmetros GET da requisição.
        is_seller_view (bool): Indica se a função está sendo usada para a view de produtos do vendedor,
                                o que adiciona o filtro de código de rastreamento na busca.

    Returns:
        QuerySet: O queryset de produtos filtrado e ordenado.
        dict: Um dicionário de contexto com os valores dos filtros aplicados para repopular o formulário.
    """
    search_query = request_get_params.get('q', '')
    min_price_str = request_get_params.get('min_price', '')
    max_price_str = request_get_params.get('max_price', '')
    category_slug = request_get_params.get('category_slug', '')
    stock_status = request_get_params.get('stock_status', '')
    sort_by = request_get_params.get('sort_by', 'name') # Padrão 'name' para lista geral, '-created_at' para vendedor

    # Armazena os valores dos filtros para o contexto
    filter_context = {
        'search_query': search_query,
        'min_price': min_price_str,
        'max_price': max_price_str,
        'category_slug': category_slug,
        'stock_status': stock_status,
        'sort_by': sort_by,
        'current_category_filter': None # Será preenchido se category_slug existir
    }

    if search_query:
        search_filter = Q(name__icontains=search_query) | Q(description__icontains=search_query)
        if is_seller_view:
            search_filter |= Q(tracking_code__icontains=search_query) # Apenas para produtos do vendedor
        queryset = queryset.filter(search_filter).distinct()
        logger.debug(f"Filtro de busca aplicado: '{search_query}'.")

    if category_slug:
        try:
            current_category_filter = Category.objects.get(slug=category_slug)
            category_ids_to_filter = get_descendant_category_ids(current_category_filter)
            queryset = queryset.filter(category__id__in=category_ids_to_filter)
            filter_context['current_category_filter'] = current_category_filter
            logger.debug(f"Filtro de categoria aplicado: {current_category_filter.name}.")
        except Category.DoesNotExist:
            logger.warning(f"Tentativa de filtrar por categoria inválida: {category_slug}")
            # Não adiciona mensagem de erro aqui, a view principal fará isso.

    if stock_status == 'in_stock':
        queryset = queryset.filter(stock__gt=0)
        logger.debug("Filtro de estoque: Em Estoque.")
    elif stock_status == 'out_of_stock':
        queryset = queryset.filter(stock=0)
        logger.debug("Filtro de estoque: Esgotado.")

    if min_price_str:
        try:
            min_price = float(min_price_str)
            queryset = queryset.filter(price__gte=min_price)
            filter_context['min_price'] = min_price # Armazena como float para o contexto
            logger.debug(f"Filtro de preço mínimo: R${min_price}.")
        except ValueError:
            logger.error(f"Valor mínimo de preço inválido: {min_price_str}")
            # A view principal adicionará a mensagem de erro

    if max_price_str:
        try:
            max_price = float(max_price_str)
            queryset = queryset.filter(price__lte=max_price)
            filter_context['max_price'] = max_price # Armazena como float para o contexto
            logger.debug(f"Filtro de preço máximo: R${max_price}.")
        except ValueError:
            logger.error(f"Valor máximo de preço inválido: {max_price_str}")
            # A view principal adicionará a mensagem de erro

    # Ordenação
    if sort_by == 'price_asc':
        queryset = queryset.order_by('price')
    elif sort_by == 'price_desc':
        queryset = queryset.order_by('-price')
    elif sort_by == 'name_asc':
        queryset = queryset.order_by('name')
    elif sort_by == 'name_desc':
        queryset = queryset.order_by('-name')
    elif is_seller_view and sort_by == 'stock_asc':
        queryset = queryset.order_by('stock')
    elif is_seller_view and sort_by == 'stock_desc':
        queryset = queryset.order_by('-stock')
    elif sort_by == 'created_at':
        queryset = queryset.order_by('created_at')
    elif sort_by == '-created_at': # Padrão para vendedor
        queryset = queryset.order_by('-created_at')
    else:
        queryset = queryset.order_by('name') # Padrão geral

    logger.debug(f"Ordenação aplicada: {sort_by}.")

    return queryset, filter_context


def apply_order_filters_and_sort(queryset, request_get_params, seller_products_ids=None):
    """
    Aplica filtros de busca e status a um queryset de pedidos.

    Args:
        queryset (QuerySet): O queryset inicial de pedidos.
        request_get_params (dict): Dicionário com os parâmetros GET da requisição.
        seller_products_ids (list, optional): Lista de IDs de produtos do vendedor logado.
                                               Usado para filtrar OrderItems.

    Returns:
        QuerySet: O queryset de pedidos filtrado e ordenado.
        dict: Um dicionário de contexto com os valores dos filtros aplicados.
    """
    search_query = request_get_params.get('q', '')
    status_filter = request_get_params.get('status', 'all')

    filter_context = {
        'search_query': search_query,
        'status_filter': status_filter,
    }

    if search_query:
        # Busca por ID do pedido, nome de usuário, endereço, contato, nome do produto no item ou código de rastreamento no item
        search_filter = (
            Q(id__icontains=search_query) |
            Q(user__username__icontains=search_query) |
            Q(shipping_address__icontains=search_query) |
            Q(contact_info__icontains=search_query) |
            Q(items__product__name__icontains=search_query) |
            Q(items__tracking_code__icontains=search_query)
        )
        queryset = queryset.filter(search_filter).distinct() # distinct para evitar duplicação de pedidos
        logger.debug(f"Filtro de busca aplicado aos pedidos: '{search_query}'.")

    if status_filter and status_filter != 'all':
        queryset = queryset.filter(status=status_filter)
        logger.debug(f"Filtro de status aplicado aos pedidos: '{status_filter}'.")

    # Ordenação padrão para pedidos (mais recentes primeiro)
    queryset = queryset.order_by('-created_at')
    logger.debug("Pedidos ordenados por data de criação (mais recentes primeiro).")

    return queryset, filter_context
