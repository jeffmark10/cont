# store/context_processors.py
from .models import Cart
from django.conf import settings # Importa settings

# Este context processor torna a contagem de itens do carrinho disponível
# em todos os templates.
def cart_items_count(request):
    cart_count = 0
    # Se o usuário estiver autenticado, tenta obter a contagem do carrinho dele
    if request.user.is_authenticated:
        # Verifica se o usuário tem um carrinho associado
        if hasattr(request.user, 'cart'):
            cart_count = request.user.cart.items.count()
    # Se o usuário não estiver autenticado, tenta obter a contagem do carrinho da sessão
    elif 'cart_id' in request.session:
        try:
            # Tenta buscar o carrinho pela ID armazenada na sessão
            cart = Cart.objects.get(id=request.session['cart_id'])
            cart_count = cart.items.count()
        except Cart.DoesNotExist:
            # Se o carrinho não for encontrado (ex: sessão expirou, carrinho deletado),
            # remove a ID do carrinho da sessão para evitar futuras tentativas.
            del request.session['cart_id']
            pass # Não faz nada, a contagem permanece 0
    
    # Adiciona o número do WhatsApp do settings ao contexto
    whatsapp_number = getattr(settings, 'STORE_WHATSAPP_NUMBER', '5511999999999') # Fallback seguro

    return {
        'cart_items_count': cart_count,
        'STORE_WHATSAPP_NUMBER': whatsapp_number, # NOVO: Disponibiliza o número do WhatsApp
    }
