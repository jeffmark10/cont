# store/admin.py

from django.contrib import admin
# Importa todos os modelos necessários do seu aplicativo 'store'.
# Certifique-se de que 'Profile' foi importado, pois é um novo modelo.
# NOVO: Importa Order e OrderItem
from .models import Product, Category, Cart, CartItem, Profile, User, Order, OrderItem

# NOVO REGISTRO: ProfileAdmin
# Registra o modelo Profile no painel de administração do Django.
# Isso permite que administradores visualizem e editem os perfis dos usuários.
@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    # Define quais campos serão exibidos na lista de perfis no admin.
    # 'user' mostra o usuário associado, 'is_seller' mostra se ele é um vendedor.
    list_display = ('user', 'is_seller',)

    # Adiciona filtros na barra lateral direita para facilitar a navegação.
    # Permite filtrar por usuários que são ou não vendedores.
    list_filter = ('is_seller',)

    # Habilita uma caixa de busca para pesquisar perfis pelo nome de usuário.
    # 'user__username' permite buscar no campo 'username' do modelo 'User' relacionado.
    search_fields = ('user__username',)

# Registra o modelo Category no painel de administração do Django
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    # Campos que serão exibidos na lista de categorias no admin.
    list_display = ('name', 'parent', 'slug')

    # Campos pelos quais você pode pesquisar as categorias.
    search_fields = ('name', 'slug')

    # Campos que serão preenchidos automaticamente com base em outros campos.
    # 'slug' será preenchido automaticamente ao digitar o 'name' da categoria.
    prepopulated_fields = {'slug': ('name',)}

    # Adiciona um filtro na barra lateral para filtrar por categoria pai.
    list_filter = ('parent',)

# Registra o modelo Product no painel de administração do Django
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    # Campos que serão exibidos na lista de produtos no admin.
    # Adicionei 'seller' para que o vendedor do produto seja visível.
    list_display = ('name', 'category', 'price', 'stock', 'is_featured', 'seller', 'created_at')

    # Campos pelos quais você pode filtrar os produtos.
    # Adicionei 'seller' para permitir filtrar produtos por vendedor.
    list_filter = ('is_featured', 'category', 'seller', 'created_at', 'stock')

    # Campos pelos quais você pode pesquisar os produtos.
    search_fields = ('name', 'description', 'seller__username') # Permite buscar por nome do vendedor.

    # Campos somente leitura no formulário de edição do produto.
    # Isso impede que a data de criação e atualização sejam alteradas manualmente.
    readonly_fields = ('created_at', 'updated_at')

    # Campo para preencher automaticamente o vendedor com o usuário logado ao adicionar um novo produto.
    # Isso é útil para quando os próprios vendedores adicionam seus produtos.
    def save_model(self, request, obj, form, change):
        if not change and not obj.seller: # Se for um novo objeto e o vendedor não estiver definido
            # Define o vendedor como o usuário logado que está adicionando o produto.
            obj.seller = request.user
        super().save_model(request, obj, form, change)

# Registra o modelo de Carrinho no admin
@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    # Campos a serem exibidos na lista de carrinhos.
    # 'get_total_price_display' é um método personalizado para exibir o preço formatado.
    list_display = ('user', 'session_key', 'created_at', 'updated_at', 'get_total_price_display')

    # Filtros para carrinhos.
    list_filter = ('created_at', 'updated_at', 'user')

    # Campos para pesquisa.
    search_fields = ('user__username', 'session_key')

    # Campos somente leitura.
    readonly_fields = ('created_at', 'updated_at')

    # Método personalizado para exibir o preço total do carrinho formatado.
    def get_total_price_display(self, obj):
        # Garante que o total seja exibido com duas casas decimais e o prefixo "Rquot;.
        return f"R$ {obj.get_total_price():.2f}"
    # Define um nome amigável para a coluna no admin.
    get_total_price_display.short_description = "Valor Total"


# Registra o modelo de Item de Carrinho no admin
@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    # Campos a serem exibidos na lista de itens do carrinho.
    list_display = ('cart', 'product', 'quantity', 'added_at', 'get_total_price_display')

    # Filtros para itens do carrinho, incluindo por categoria do produto.
    list_filter = ('added_at', 'product__category')

    # Campos para pesquisa, incluindo por nome do produto e informações do carrinho/usuário.
    search_fields = ('product__name', 'cart__user__username', 'cart__session_key')

    # Campos somente leitura.
    readonly_fields = ('added_at',)

    # Método personalizado para exibir o preço total do item formatado.
    def get_total_price_display(self, obj):
        return f"R$ {obj.get_total_price():.2f}"
    get_total_price_display.short_description = "Total do Item"


# NOVO REGISTRO: OrderAdmin
# Permite gerenciar os pedidos no painel de administração.
class OrderItemInline(admin.TabularInline):
    # Define OrderItem como um inline para Order, permitindo editar itens do pedido
    # diretamente na página de detalhes do pedido.
    model = OrderItem
    extra = 0 # Não adiciona campos extras vazios por padrão.
    # Campos que podem ser editados no inline.
    # Adicionado 'status' ao inline
    fields = ['product', 'quantity', 'price_at_purchase', 'tracking_code', 'status']
    readonly_fields = ['price_at_purchase'] # Preço na compra não deve ser alterado.

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    # Campos a serem exibidos na lista de pedidos.
    list_display = ('id', 'user', 'session_key', 'total_price', 'status', 'created_at')

    # Filtros para pedidos.
    list_filter = ('status', 'created_at', 'user')

    # Campos para pesquisa.
    search_fields = ('user__username', 'session_key', 'shipping_address', 'contact_info')

    # Campos somente leitura.
    readonly_fields = ('created_at', 'updated_at', 'total_price')

    # Adiciona OrderItemInline para que os itens do pedido sejam exibidos e editáveis
    # na página de detalhes do pedido.
    inlines = [OrderItemInline]

# NOVO REGISTRO: OrderItemAdmin
# Permite gerenciar os itens do pedido separadamente no painel de administração.
@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    # Campos a serem exibidos na lista de itens do pedido.
    # Adicionado 'status' ao list_display
    list_display = ('order', 'product', 'quantity', 'price_at_purchase', 'tracking_code', 'status')

    # Filtros para itens do pedido.
    # Adicionado 'status' ao list_filter
    list_filter = ('order__status', 'product__category', 'product__seller', 'status')

    # Campos para pesquisa.
    search_fields = ('order__id__exact', 'product__name', 'tracking_code')

    # Campos somente leitura.
    readonly_fields = ('price_at_purchase',)
