# store/constants.py

# Mensagens gerais
MSG_SUCCESS_GENERIC = "Operação realizada com sucesso!"
MSG_ERROR_GENERIC = "Ocorreu um erro inesperado. Por favor, tente novamente mais tarde."
MSG_WARNING_GENERIC = "Atenção: {message}"
MSG_INFO_GENERIC = "Informação: {message}"

# Mensagens do Carrinho
CART_QUANTITY_INVALID = "A quantidade do produto deve ser um número positivo."
CART_STOCK_INSUFFICIENT = "Desculpe, só temos {stock} unidades de '{product_name}' em estoque."
CART_ITEM_EXCEEDS_STOCK = "Não é possível adicionar mais. Você já tem {current_quantity} unidades de '{product_name}' no carrinho e só temos {available_stock} em estoque."
CART_ITEM_REMOVED = "Item '{product_name}' removido do carrinho com sucesso."
CART_ITEM_UPDATED = "Quantidade de '{product_name}' atualizada para {new_quantity} unidades."
CART_PERMISSION_DENIED = "Você não tem permissão para modificar este item do carrinho."
CART_EMPTY_CHECKOUT = "Seu carrinho está vazio. Adicione produtos antes de finalizar a compra."
CART_PRODUCT_ADDED = "{quantity}x {product_name} adicionado ao seu carrinho!"
CART_MIGRATION_PARTIAL_STOCK = "Adicionado {actual_added_quantity} unidades de '{product_name}'. O restante ({remaining_quantity}) não pôde ser migrado por limite de estoque."
CART_MIGRATION_NO_STOCK = "Não foi possível migrar '{product_name}' para o seu carrinho devido ao estoque insuficiente."

# Mensagens de Produto
PRODUCT_ADD_SUCCESS = "Produto '{product_name}' adicionado com sucesso!"
PRODUCT_UPDATE_SUCCESS = "Produto '{product_name}' atualizado com sucesso!"
PRODUCT_DELETE_SUCCESS = "Produto '{product_name}' excluído com sucesso."
PRODUCT_DELETE_INVALID_METHOD = "Método inválido para exclusão. Por favor, use o formulário de exclusão."
PRODUCT_NOT_FOUND_SEARCH = "Nenhum produto encontrado para '{search_query}'. Tente outra busca."
PRODUCT_NO_FEATURED = "Nenhum produto em destaque no momento. Volte mais tarde para conferir nossas novidades!"
PRODUCT_NO_LISTED = "Você ainda não tem nenhum produto cadastrado em sua loja."
PRODUCT_CATEGORY_INVALID = "A categoria selecionada é inválida ou não existe."

# Mensagens de Preço
PRICE_MIN_INVALID = "O valor mínimo de preço inserido é inválido."
PRICE_MAX_INVALID = "O valor máximo de preço inserido é inválido."

# Mensagens de Autenticação/Registro
AUTH_SIGNUP_SUCCESS = "Sua conta foi criada com sucesso! Você está logado(a)."
AUTH_SIGNUP_ERROR = "Houve um problema ao criar sua conta. Por favor, corrija os erros no formulário."
AUTH_LOGIN_SUCCESS = "Bem-vindo(a) de volta, {username}!"
AUTH_LOGIN_FAILED = "Nome de usuário ou senha inválidos. Por favor, tente novamente."
AUTH_SELLER_ACCESS_DENIED = "Acesso negado. Você não tem permissão para acessar esta área."

# Mensagens de Pedido (Vendedor)
ORDER_ITEM_UPDATE_SUCCESS = "Item do pedido '{product_name}' (Pedido #{order_id}) atualizado com sucesso."
ORDER_ITEM_PERMISSION_DENIED = "Você não tem permissão para atualizar este item do pedido."
ORDER_STATUS_UPDATED = "Status do Pedido #{order_id} atualizado para '{status_display}'."
ORDER_STATUS_INVALID = "O status fornecido para o item do pedido é inválido."
ORDER_NO_SELLER_PRODUCTS = "Você não tem permissão para visualizar este pedido ou ele não contém produtos seus."
ORDER_NO_ORDERS_FOUND = "Nenhum pedido encontrado para seus produtos com os filtros aplicados."

# Mensagens de Formulário
FORM_ERRORS = "Por favor, corrija os erros no formulário."
FORM_CONTACT_SUCCESS = "Sua mensagem foi enviada com sucesso! Em breve entraremos em contato."
