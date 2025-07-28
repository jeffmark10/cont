# store/apps.py
from django.apps import AppConfig


class StoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'store'

    def ready(self):
        # NOVO: Importa os sinais para que eles sejam registrados quando o aplicativo estiver pronto
        import store.signals
