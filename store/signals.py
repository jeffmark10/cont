# store/signals.py
import logging
from django.db.models.signals import post_save
from django.contrib.auth import get_user_model
from django.dispatch import receiver
# from .models import Profile # REMOVIDA ESTA LINHA: A importação será feita dentro da função

# Configura o logger para este módulo
logger = logging.getLogger(__name__)

# Obtém o modelo de usuário ativo do Django. É uma boa prática usar get_user_model()
# em vez de importar User diretamente de django.contrib.auth.models,
# pois permite que você use um modelo de usuário personalizado no futuro.
User = get_user_model()

# Este decorador conecta a função create_and_save_user_profile ao sinal post_save do modelo User.
# Isso significa que toda vez que um objeto User for salvo (incluindo na criação),
# esta função será executada.
@receiver(post_save, sender=User)
def create_and_save_user_profile(sender, instance, created, **kwargs):
    """
    Cria um objeto Profile para um novo usuário ou salva o perfil existente
    quando um objeto User é salvo.
    """
    # IMPORTAÇÃO LAZY: O modelo Profile é importado aqui, dentro da função.
    # Isso garante que ele só seja carregado quando a função for executada,
    # evitando que seja registrado prematuramente ou múltiplas vezes.
    from .models import Profile

    if created:
        # Se um novo usuário foi criado, cria um perfil correspondente para ele.
        # O campo 'user' do Profile aponta para a instância do User recém-criada.
        Profile.objects.create(user=instance)
        logger.info(f"Perfil criado para o novo usuário: {instance.username}")
    else:
        # Se o usuário não foi recém-criado, tenta salvar o perfil associado.
        # Isso é útil caso haja alterações no perfil que precisem ser persistidas
        # e que não sejam diretamente acionadas por um save no Profile.
        try:
            instance.profile.save()
            logger.debug(f"Perfil salvo para o usuário: {instance.username}")
        except Profile.DoesNotExist:
            # Isso pode acontecer se o sinal for disparado para um usuário
            # que por algum motivo não tem um perfil (ex: migrações antigas ou dados inconsistentes).
            # Para robustez, podemos criar um perfil aqui também, ou apenas logar o erro.
            # Neste caso, vamos criar para garantir a consistência.
            Profile.objects.create(user=instance)
            logger.warning(f"Perfil para o usuário {instance.username} não encontrado, um novo foi criado.")

