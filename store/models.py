# store/models.py
from django.db import models
from django.utils.text import slugify
from django.contrib.auth.models import User # Importa o modelo User do Django
from cloudinary.models import CloudinaryField # Importa CloudinaryField
from django.db import transaction # Importa transaction para garantir atomicidade

# NOVO MODELO: Profile (Perfil do Usuário)
# Este modelo estende o modelo User do Django, adicionando informações específicas
# para o perfil do usuário na sua aplicação, como se ele é um vendedor.
class Profile(models.Model):
    # Um relacionamento um-para-um com o modelo User do Django.
    # Se o usuário for excluído, o perfil também será excluído (CASCADE).
    user = models.OneToOneField(User, on_delete=models.CASCADE, verbose_name="Usuário")

    # Campo booleano para indicar se o usuário é um vendedor.
    # O valor padrão é False (não é vendedor).
    is_seller = models.BooleanField(default=False, verbose_name="É Vendedor")

    # Você pode adicionar outros campos aqui, como 'nome_da_loja', 'cnpj', etc.,
    # para armazenar informações adicionais do vendedor ou do cliente.
    # Exemplo: store_name = models.CharField(max_length=100, blank=True, null=True, verbose_name="Nome da Loja")

    class Meta:
        # Define o nome singular e plural para exibição no Django Admin.
        verbose_name = "Perfil"
        verbose_name_plural = "Perfis"

    def __str__(self):
        # Retorna uma representação em string do objeto Profile, útil para o Django Admin.
        return f"Perfil de {self.user.username}"

# Modelo para representar uma categoria de produto
# Permite organizar os produtos em categorias e subcategorias.
class Category(models.Model):
    # Nome da categoria (ex: "Feminino", "Sandálias", "T-Shirts"). Deve ser único.
    name = models.CharField(max_length=100, unique=True, verbose_name="Nome da Categoria")

    # Slug para URLs amigáveis (ex: "feminino", "sandalias"). Gerado automaticamente.
    slug = models.SlugField(max_length=100, unique=True, blank=True)

    # Campo opcional para definir uma categoria pai, permitindo subcategorias.
    # 'self' referencia o próprio modelo Category.
    # Se a categoria pai for excluída, este campo será nulo (SET_NULL).
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children', # Permite acessar subcategorias de uma categoria pai.
        verbose_name="Categoria Pai"
    )

    class Meta:
        # Define o nome da tabela no plural para o Django Admin.
        verbose_name_plural = "Categorias"
        # Ordena as categorias por nome por padrão.
        ordering = ['name']

    def save(self, *args, **kwargs):
        # Sobrescreve o método save para gerar o slug automaticamente se não for fornecido.
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        # Representação em string do objeto Category, mostrando o caminho completo da categoria.
        full_path = [self.name]
        k = self.parent
        while k is not None:
            full_path.append(k.name)
            k = k.parent
        return ' -> '.join(full_path[::-1])

# Modelo para representar um produto na Jeci Store
class Product(models.Model):
    # Nome do produto (ex: "Sandália Verão", "T-Shirt Básica").
    name = models.CharField(max_length=200, verbose_name="Nome do Produto")

    # Descrição detalhada do produto.
    description = models.TextField(verbose_name="Descrição")

    # Preço do produto. Usamos DecimalField para precisão monetária (10 dígitos no total, 2 casas decimais).
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Preço")

    # Campo para upload de imagem. As imagens serão salvas em 'products/' dentro de MEDIA_ROOT.
    # É opcional (blank=True, null=True).
    # Alterado para CloudinaryField para integração com Cloudinary
    image = CloudinaryField('Imagem do Produto', blank=True, null=True)

    # Vincula o produto a uma categoria.
    # Se a categoria for deletada, o produto permanece, mas o campo 'category' será nulo (SET_NULL).
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products', # Permite acessar produtos de uma categoria.
        verbose_name="Categoria",
        db_index=True # Adicionado índice para consultas mais rápidas
    )

    # Vincula o produto a um vendedor (um usuário do Django).
    # Se o vendedor for excluído, os produtos dele não serão excluídos, apenas o campo 'seller' será nulo (SET_NULL).
    seller = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products_listed', # Permite acessar os produtos listados por um usuário.
        verbose_name="Vendedor",
        db_index=True # Adicionado índice para consultas mais rápidas
    )

    # Campo para controlar o estoque do produto. Valor padrão é 0.
    stock = models.PositiveIntegerField(default=0, verbose_name="Estoque")

    # NOVO CAMPO: Código de rastreamento para o produto.
    # Em um sistema real, o código de rastreamento geralmente é gerado por pedido/envio,
    # não por produto. Aqui, para simplificar, ele é associado ao tipo de produto.
    # Se você precisar de um código único por item enviado, considere um modelo de Pedido/ItemPedido.
    # REMOVIDO unique=True pois este é um código de referência, não de rastreamento de envio.
    tracking_code = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="Código de Referência do Produto" # Alterado o verbose_name para clareza
    )

    # Campo booleano para indicar se o produto deve ser exibido na página inicial como destaque.
    is_featured = models.BooleanField(default=False, verbose_name="Destaque na Home")

    # Data e hora em que o produto foi criado (definido automaticamente na criação).
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado Em")

    # Data e hora da última atualização do produto (atualizado automaticamente a cada salvamento).
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado Em")

    class Meta:
        # Define o nome da tabela no plural para o Django Admin.
        verbose_name_plural = "Produtos"
        # Ordena os produtos por nome por padrão.
        ordering = ['name']

    def __str__(self):
        # Representação em string do objeto Product.
        return self.name

    def get_optimized_image_url(self, width=None, height=None, crop='fill', format='auto:webp', quality='auto'):
        """
        Retorna a URL de uma imagem otimizada do Cloudinary.
        """
        if self.image:
            # self.image é um CloudinaryResource
            # Certifique-se de que o CloudinaryField está configurado corretamente no settings.py
            return self.image.build_url(width=width, height=height, crop=crop, format=format, quality=quality)
        return 'https://placehold.co/400x400/cccccc/ffffff?text=Sem+Imagem' # Fallback seguro

# Modelo para representar um carrinho de compras
# Um carrinho pode ser associado a um usuário logado ou a uma sessão anônima.
class Cart(models.Model):
    # Relacionamento um-para-one com o modelo User. Opcional (null=True, blank=True) para carrinhos anônimos.
    # Se o usuário for excluído, o carrinho também será excluído (CASCADE).
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True, verbose_name="Usuário", db_index=True) # Adicionado índice

    # Chave de sessão para carrinhos anônimos. Deve ser única.
    session_key = models.CharField(max_length=40, null=True, blank=True, unique=True, verbose_name="Chave de Sessão", db_index=True) # Adicionado índice

    # Data e hora de criação do carrinho.
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado Em")

    # Data e hora da última atualização do carrinho.
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado Em")

    class Meta:
        verbose_name_plural = "Carrinhos"
        # Ordena os carrinhos pelos mais recentes.
        ordering = ['-created_at']

    def __str__(self):
        # Retorna uma representação em string, indicando se é um carrinho de usuário ou de sessão.
        if self.user:
            return f"Carrinho de {self.user.username}"
        return f"Carrinho de Sessão {self.session_key[:10]}..." # Mostra os primeiros 10 caracteres da chave.

    def get_total_price(self):
        # Calcula o preço total de todos os itens no carrinho.
        return sum(item.get_total_price() for item in self.items.all())

# Modelo para representar um item dentro do carrinho de compras
# Cada linha do carrinho representa um produto e sua quantidade.
class CartItem(models.Model):
    # Relacionamento com o modelo Cart. Se o carrinho for excluído, o item também será (CASCADE).
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items', verbose_name="Carrinho")

    # Relacionamento com o modelo Product. Se o produto for excluído, o item também será (CASCADE).
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="Produto")

    # Quantidade do produto no carrinho. Valor padrão é 1.
    quantity = models.PositiveIntegerField(default=1, verbose_name="Quantidade")

    # Data e hora em que o item foi adicionado ao carrinho.
    added_at = models.DateTimeField(auto_now_add=True, verbose_name="Adicionado Em")

    class Meta:
        verbose_name_plural = "Itens do Carrinho"
        # Garante que um produto só pode aparecer uma vez em um determinado carrinho.
        unique_together = ('cart', 'product')

    def __str__(self):
        # Representação em string do item do carrinho.
        return f"{self.quantity} x {self.product.name} no carrinho de {self.cart}"

    def get_total_price(self):
        # Calcula o preço total para este item específico (quantidade * preço do produto).
        return self.quantity * self.product.price


# NOVO MODELO: Order (Pedido)
# Representa um pedido de compra feito por um usuário (logado ou anônimo).
class Order(models.Model):
    # O usuário que fez o pedido. Pode ser nulo para pedidos de usuários não logados.
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Usuário")

    # Chave de sessão para pedidos de usuários não logados.
    session_key = models.CharField(max_length=40, null=True, blank=True, verbose_name="Chave de Sessão")

    # Endereço de entrega do pedido.
    shipping_address = models.TextField(verbose_name="Endereço de Entrega")

    # Informações de contato (e-mail ou telefone) para o pedido.
    contact_info = models.CharField(max_length=255, verbose_name="Informações de Contato")

    # Preço total do pedido no momento da compra.
    total_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Preço Total")

    # Status do pedido (ex: "Pendente", "Processando", "Enviado", "Concluído", "Cancelado").
    # Usamos choices para garantir valores consistentes.
    STATUS_CHOICES = [
        ('pending', 'Pendente'),
        ('processing', 'Processando'),
        ('shipped', 'Enviado'),
        ('completed', 'Concluído'),
        ('cancelled', 'Cancelado'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Status")

    # Data e hora em que o pedido foi criado.
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado Em")

    # Data e hora da última atualização do pedido.
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado Em")

    class Meta:
        verbose_name = "Pedido"
        verbose_name_plural = "Pedidos"
        ordering = ['-created_at'] # Ordena os pedidos pelos mais recentes.

    def __str__(self):
        # Representação em string do objeto Order.
        if self.user:
            return f"Pedido #{self.id} de {self.user.username}"
        return f"Pedido #{self.id} (Sessão: {self.session_key[:10]}...)"

    @transaction.atomic
    def update_status_based_on_items(self, updated_item_status=None):
        """
        Atualiza o status do pedido principal com base nos status de seus OrderItems.
        Esta é uma lógica de negócio que pode ser ajustada conforme necessário.

        Args:
            updated_item_status (str, optional): O status do item que acabou de ser atualizado.
                                                 Pode ser usado para gatilhos específicos.

        Returns:
            bool: True se o status do pedido foi atualizado, False caso contrário.
        """
        current_order_status = self.status
        new_order_status = current_order_status
        status_updated = False

        # Obtém todos os status dos itens do pedido
        # Assumindo que OrderItem terá um campo 'status'
        all_item_statuses = [item.status for item in self.items.all()]

        # Lógica de exemplo:
        # Se todos os itens estiverem 'shipped', o pedido pode ser 'shipped'.
        # Se todos os itens estiverem 'completed', o pedido pode ser 'completed'.
        # Se algum item for 'cancelled', o pedido pode ser 'cancelled' (ou requer revisão).
        # Se algum item for 'processing' e nenhum for 'shipped'/'completed', o pedido é 'processing'.

        # Simplificando a lógica para o que estava na view:
        if updated_item_status:
            if updated_item_status == 'shipped' and current_order_status in ['pending', 'processing']:
                new_order_status = 'shipped'
            elif updated_item_status == 'completed' and current_order_status == 'shipped':
                new_order_status = 'completed'
            elif updated_item_status == 'processing' and current_order_status == 'pending':
                new_order_status = 'processing'
            elif updated_item_status == 'cancelled' and current_order_status not in ['completed', 'cancelled']:
                new_order_status = 'cancelled'
            elif all(status == 'delivered' for status in all_item_statuses):
                # Se todos os itens do pedido (pertencentes a qualquer vendedor) estiverem 'delivered',
                # o status do pedido principal pode ser 'completed'.
                new_order_status = 'completed'
            elif any(status == 'shipped' for status in all_item_statuses) and new_order_status not in ['completed', 'cancelled']:
                # Se pelo menos um item foi enviado, o pedido está 'shipped' (se não estiver concluído/cancelado)
                new_order_status = 'shipped'
            elif any(status == 'processing' for status in all_item_statuses) and new_order_status not in ['shipped', 'completed', 'cancelled']:
                # Se pelo menos um item está processando, o pedido está 'processing'
                new_order_status = 'processing'


        if new_order_status != current_order_status:
            self.status = new_order_status
            self.save(update_fields=['status']) # Salva apenas o campo status
            status_updated = True

        return status_updated


# NOVO MODELO: OrderItem (Item do Pedido)
# Representa um produto específico dentro de um pedido.
class OrderItem(models.Model):
    # O pedido ao qual este item pertence.
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items', verbose_name="Pedido")

    # O produto que foi comprado.
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, verbose_name="Produto") # SET_NULL caso o produto seja deletado.

    # Quantidade do produto neste item do pedido.
    quantity = models.PositiveIntegerField(verbose_name="Quantidade")

    # Preço do produto no momento da compra (para evitar que o preço mude após o pedido).
    price_at_purchase = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Preço na Compra")

    # NOVO CAMPO: Código de rastreamento para este item específico do pedido.
    tracking_code = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Código de Rastreamento do Envio"
    )

    # Adicionando um campo 'status' ao OrderItem para maior granularidade
    # Isso permite que cada item dentro de um pedido tenha seu próprio status de envio.
    # Se você não precisar dessa granularidade, pode remover este campo.
    # Se for manter, a lógica de `Order.update_status_based_on_items` precisará ser mais sofisticada.
    ITEM_STATUS_CHOICES = [
        ('pending', 'Pendente'),
        ('processing', 'Processando'),
        ('shipped', 'Enviado'),
        ('delivered', 'Entregue'), # Adicionado status para item
        ('returned', 'Devolvido'), # Adicionado status para item
        ('cancelled', 'Cancelado'),
    ]
    status = models.CharField(max_length=20, choices=ITEM_STATUS_CHOICES, default='pending', verbose_name="Status do Item")


    class Meta:
        verbose_name = "Item do Pedido"
        verbose_name_plural = "Itens do Pedido"
        # Não precisa de unique_together aqui, pois um pedido pode ter vários itens do mesmo produto
        # se o usuário adicionou várias vezes e depois fez checkout.

    def __str__(self):
        # Representação em string do objeto OrderItem.
        return f"{self.quantity} x {self.product.name if self.product else 'Produto Removido'} (Pedido #{self.order.id})"

    def get_total_price(self):
        # Calcula o preço total para este item do pedido.
        return self.quantity * self.price_at_purchase
