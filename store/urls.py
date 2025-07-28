# store/urls.py

from django.urls import path
from . import views
from django.contrib.auth import views as auth_views # Importa as views de autenticação do Django

app_name = 'store'

urlpatterns = [
    # Rotas de Produtos e Páginas Estáticas
    path('produtos/', views.product_list_view, name='product_list'),
    path('produtos/categoria/<slug:category_slug>/', views.product_list_view, name='product_list_by_category'),
    path('produtos/<int:pk>/', views.product_detail_view, name='product_detail'),
    path('sobre/', views.about_view, name='about'),
    path('contato/', views.contact_view, name='contact'),

    # Rotas de Carrinho de Compras
    path('carrinho/adicionar/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('carrinho/', views.view_cart, name='view_cart'),
    path('carrinho/atualizar/<int:item_id>/', views.update_cart_item, name='update_cart_item'),
    path('carrinho/remover/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    # NOVA ROTA: Checkout com formulário
    path('carrinho/checkout/', views.checkout_view, name='checkout'),
    # A rota original `checkout_whatsapp` agora redireciona para a nova `checkout` view
    path('carrinho/finalizar-whatsapp/', views.checkout_whatsapp_view, name='checkout_whatsapp'),

    # Rotas de Autenticação e Perfil
    path('registrar/', views.signup_view, name='signup'),
    path('perfil/', views.user_profile_view, name='user_profile'),
    # As URLs de login/logout/password_reset já estão incluídas via 'django.contrib.auth.urls' no urls.py principal

    # NOVAS ROTAS PARA VENDEDORES
    path('vendedor/adicionar-produto/', views.add_product_view, name='add_product'),
    path('vendedor/meus-produtos/', views.my_products_view, name='my_products'),
    path('vendedor/editar-produto/<int:pk>/', views.edit_product_view, name='edit_product'),
    path('vendedor/excluir-produto/<int:pk>/', views.delete_product_view, name='delete_product'),

    # NOVO: Rotas de Gerenciamento de Pedidos para Vendedores
    path('vendedor/pedidos/', views.seller_orders_view, name='seller_orders'),
    path('vendedor/pedidos/<int:order_id>/', views.seller_order_detail_view, name='seller_order_detail'),
    path('vendedor/pedidos/item/<int:item_id>/atualizar/', views.seller_update_order_item_status, name='seller_update_order_item_status'),
]
