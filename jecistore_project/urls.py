# jecistore_project/urls.py

from django.contrib import admin
from django.urls import path, include
from store.views import home_view, login_view # Importa a nova view de login
from django.conf import settings
from django.conf.urls.static import static # Importe static

# Importa os manipuladores de erro personalizados
from store.views import custom_404_view, custom_500_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home_view, name='home'), 
    path('store/', include('store.urls')), 
    # Usa a view de login personalizada
    path('accounts/login/', login_view, name='login'), 
    path('accounts/', include('django.contrib.auth.urls')),
]

# Apenas para servir arquivos de mídia e estáticos durante o desenvolvimento
# Em produção, o Cloudinary (para mídia) e o Render (para estáticos) servirão esses arquivos.
if settings.DEBUG:
    # DESCOMENTADO: Esta linha é necessária para servir arquivos de mídia localmente em desenvolvimento.
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) 
    # Mantenha esta linha para STATIC_URL se você ainda quiser servir estáticos localmente
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT) 

# Manipuladores de erro personalizados
handler404 = custom_404_view
handler500 = custom_500_view

