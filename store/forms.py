# store/forms.py

from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm # Importa AuthenticationForm
from django.contrib.auth import get_user_model # Importa get_user_model para referenciar o modelo User
from .models import Product, Category 

# Obtém o modelo de usuário ativo do Django.
User = get_user_model()

# Formulário de Contato
# Este formulário é para que os usuários possam enviar mensagens.
class ContactForm(forms.Form):
    # Campo para o nome do remetente.
    name = forms.CharField(
        max_length=100, 
        label="Seu Nome",
        widget=forms.TextInput(attrs={
            'class': 'shadow-sm appearance-none border border-stone-300 rounded-lg w-full py-3 px-4 text-gray-700 leading-tight focus:outline-none focus:ring-2 focus:ring-pink-500 focus:border-transparent transition duration-200', 
            'placeholder': 'Seu nome completo'
        })
    )
    # Campo para o e-mail do remetente.
    email = forms.EmailField(
        label="Seu E-mail",
        widget=forms.EmailInput(attrs={
            'class': 'shadow-sm appearance-none border border-stone-300 rounded-lg w-full py-3 px-4 text-gray-700 leading-tight focus:outline-none focus:ring-2 focus:ring-pink-500 focus:border-transparent transition duration-200', 
            'placeholder': 'seu.email@exemplo.com'
        })
    )
    # Campo para a mensagem. Usa um Textarea para múltiplas linhas.
    message = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 6, 
            'class': 'shadow-sm appearance-none border border-stone-300 rounded-lg w-full py-3 px-4 text-gray-700 leading-tight focus:outline-none focus:ring-2 focus:ring-pink-500 focus:border-transparent transition duration-200', 
            'placeholder': 'Escreva sua mensagem aqui...'
        }),
        label="Sua Mensagem"
    )

# NOVO FORMULÁRIO: ProductForm
# Este formulário é baseado no modelo Product e será usado por vendedores para adicionar/editar produtos.
class ProductForm(forms.ModelForm):
    class Meta:
        # Define o modelo base para este formulário.
        model = Product
        # Campos que o vendedor poderá preencher.
        # 'seller' NÃO está incluído aqui, pois será preenchido automaticamente pela view (ou admin).
        # NOVO: Adicionado 'tracking_code'
        fields = ['name', 'description', 'price', 'image', 'category', 'stock', 'is_featured', 'tracking_code']
        
        # Personalização dos widgets para aplicar classes Tailwind CSS.
        # Isso ajuda a estilizar os campos do formulário para corresponder ao design do seu site.
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'shadow-sm appearance-none border border-stone-300 rounded-lg w-full py-3 px-4 text-gray-700 leading-tight focus:outline-none focus:ring-2 focus:ring-pink-500 focus:border-transparent transition duration-200', 
                'placeholder': 'Nome do Produto'
            }),
            'description': forms.Textarea(attrs={
                'class': 'shadow-sm appearance-none border border-stone-300 rounded-lg w-full py-3 px-4 text-gray-700 leading-tight focus:outline-none focus:ring-2 focus:ring-pink-500 focus:border-transparent transition duration-200', 
                'rows': 6, 
                'placeholder': 'Descrição detalhada do produto'
            }),
            'price': forms.NumberInput(attrs={
                'class': 'shadow-sm appearance-none border border-stone-300 rounded-lg w-full py-3 px-4 text-gray-700 leading-tight focus:outline-none focus:ring-2 focus:ring-pink-500 focus:border-transparent transition duration-200', 
                'step': '0.01', # Permite valores decimais com duas casas.
                'min': '0'     # Garante que o preço não seja negativo.
            }),
            'stock': forms.NumberInput(attrs={
                'class': 'shadow-sm appearance-none border border-stone-300 rounded-lg w-full py-3 px-4 text-gray-700 leading-tight focus:outline-none focus:ring-2 focus:ring-pink-500 focus:border-transparent transition duration-200', 
                'min': '0'     # Garante que o estoque não seja negativo.
            }),
            'category': forms.Select(attrs={
                'class': 'shadow-sm appearance-none border border-stone-300 rounded-lg w-full py-3 px-4 text-gray-700 leading-tight focus:outline-none focus:ring-2 focus:ring-pink-500 focus:border-transparent transition duration-200'
            }),
            'image': forms.ClearableFileInput(attrs={
                'class': 'shadow-sm appearance-none border border-stone-300 rounded-lg w-full py-3 px-4 text-gray-700 leading-tight focus:outline-none focus:ring-2 focus:ring-pink-500 focus:border-transparent transition duration-200'
            }),
            'is_featured': forms.CheckboxInput(attrs={
                'class': 'form-checkbox h-5 w-5 text-pink-600 ml-2' # Ajuste de estilo para checkbox.
            }),
            # NOVO: Widget para o campo tracking_code
            'tracking_code': forms.TextInput(attrs={
                'class': 'shadow-sm appearance-none border border-stone-300 rounded-lg w-full py-3 px-4 text-gray-700 leading-tight focus:outline-none focus:ring-2 focus:ring-pink-500 focus:border-transparent transition duration-200', 
                'placeholder': 'Ex: ABC123XYZ'
            }),
        }
        # Rótulos amigáveis para os campos do formulário, exibidos para o usuário.
        labels = {
            'name': "Nome do Produto",
            'description': "Descrição",
            'price': "Preço (R$)",
            'image': "Imagem do Produto",
            'category': "Categoria",
            'stock': "Estoque",
            'is_featured': "Destacar na Página Inicial?",
            'tracking_code': "Código de Rastreamento (Opcional)" # NOVO: Rótulo
        }

# NOVO FORMULÁRIO: UserRegistrationForm
# Personaliza o UserCreationForm do Django para aplicar estilos Tailwind CSS.
class UserRegistrationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        # CORREÇÃO: Removido 'model = forms.CharField'. UserCreationForm já define model = User.
        # fields = UserCreationForm.Meta.fields + ('email',) # Adiciona o campo de email
        # Para adicionar o campo 'email' ao UserCreationForm, é melhor adicioná-lo explicitamente
        # como um campo no formulário e depois sobrescrever o método save() se necessário,
        # ou garantir que ele esteja no UserCreationForm.Meta.fields.
        # No Django 5.x, UserCreationForm já inclui 'username' e 'password'.
        # Se você quiser 'email' no registro, precisa adicioná-lo e garantir que o save() o trate.
        # Para simplificar e evitar o erro, vamos manter os campos padrão do UserCreationForm
        # e adicionar o email como um campo extra se realmente precisar dele no formulário.
        # Se você quer que o email seja parte do modelo de usuário padrão, você pode adicioná-lo
        # ao `fields` e ele será tratado automaticamente.
        fields = ('username', 'email', 'password', 'password2') # Incluindo email aqui

        # Personaliza os widgets para aplicar classes Tailwind CSS.
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'shadow-sm appearance-none border border-stone-300 rounded-lg w-full py-3 px-4 text-gray-700 leading-tight focus:outline-none focus:ring-2 focus:ring-pink-500 focus:border-transparent transition duration-200',
                'placeholder': 'Seu nome de usuário'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'shadow-sm appearance-none border border-stone-300 rounded-lg w-full py-3 px-4 text-gray-700 leading-tight focus:outline-none focus:ring-2 focus:ring-pink-500 focus:border-transparent transition duration-200',
                'placeholder': 'seu.email@exemplo.com'
            }),
            'password': forms.PasswordInput(attrs={
                'class': 'shadow-sm appearance-none border border-stone-300 rounded-lg w-full py-3 px-4 text-gray-700 leading-tight focus:outline-none focus:ring-2 focus:ring-pink-500 focus:border-transparent transition duration-200',
                'placeholder': 'Sua senha'
            }),
            'password2': forms.PasswordInput(attrs={ # Campo de confirmação de senha
                'class': 'shadow-sm appearance-none border border-stone-300 rounded-lg w-full py-3 px-4 text-gray-700 leading-tight focus:outline-none focus:ring-2 focus:ring-pink-500 focus:border-transparent transition duration-200',
                'placeholder': 'Confirme sua senha'
            }),
        }
        # Rótulos amigáveis para os campos.
        labels = {
            'username': "Nome de Usuário",
            'email': "E-mail",
            'password': "Senha",
            'password2': "Confirme a Senha",
        }

# NOVO FORMULÁRIO: UserLoginForm
# Personaliza o AuthenticationForm do Django para aplicar estilos Tailwind CSS.
class UserLoginForm(AuthenticationForm):
    # Personaliza os widgets para aplicar classes Tailwind CSS.
    username = forms.CharField(
        label="Nome de Usuário",
        widget=forms.TextInput(attrs={
            'class': 'shadow-sm appearance-none border border-stone-300 rounded-lg w-full py-3 px-4 text-gray-700 leading-tight focus:outline-none focus:ring-2 focus:ring-pink-500 focus:border-transparent transition duration-200',
            'placeholder': 'Seu nome de usuário'
        })
    )
    password = forms.CharField(
        label="Senha",
        widget=forms.PasswordInput(attrs={
            'class': 'shadow-sm appearance-none border border-stone-300 rounded-lg w-full py-3 px-4 text-gray-700 leading-tight focus:outline-none focus:ring-2 focus:ring-pink-500 focus:border-transparent transition duration-200',
            'placeholder': 'Sua senha'
        })
    )

# store/forms.py (Adicione ao final do arquivo)

class CheckoutForm(forms.Form):
    full_name = forms.CharField(
        max_length=255,
        label="Nome Completo",
        widget=forms.TextInput(attrs={
            'class': 'shadow-sm appearance-none border border-stone-300 rounded-lg w-full py-3 px-4 text-gray-700 leading-tight focus:outline-none focus:ring-2 focus:ring-pink-500 focus:border-transparent transition duration-200',
            'placeholder': 'Seu nome completo'
        })
    )
    email = forms.EmailField(
        label="Seu E-mail",
        required=False, # Pode ser opcional se o usuário já estiver logado
        widget=forms.EmailInput(attrs={
            'class': 'shadow-sm appearance-none border border-stone-300 rounded-lg w-full py-3 px-4 text-gray-700 leading-tight focus:outline-none focus:ring-2 focus:ring-pink-500 focus:border-transparent transition duration-200',
            'placeholder': 'seu.email@exemplo.com'
        })
    )
    phone_number = forms.CharField(
        max_length=20,
        label="Número de Telefone (WhatsApp)",
        widget=forms.TextInput(attrs={
            'class': 'shadow-sm appearance-none border border-stone-300 rounded-lg w-full py-3 px-4 text-gray-700 leading-tight focus:outline-none focus:ring-2 focus:ring-pink-500 focus:border-transparent transition duration-200',
            'placeholder': 'Ex: 5511987654321 (com DDD)'
        })
    )
    shipping_address = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 4,
            'class': 'shadow-sm appearance-none border border-stone-300 rounded-lg w-full py-3 px-4 text-gray-700 leading-tight focus:outline-none focus:ring-2 focus:ring-pink-500 focus:border-transparent transition duration-200',
            'placeholder': 'Rua, número, bairro, cidade, estado, CEP'
        }),
        label="Endereço de Entrega Completo"
    )

    # Você pode adicionar mais campos como CPF, complemento, etc., conforme necessário.

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user and user.is_authenticated:
            self.fields['full_name'].initial = user.get_full_name() or user.username
            self.fields['email'].initial = user.email
            # Se você tiver um campo de telefone no perfil do usuário, pode pré-preencher aqui
            # if hasattr(user, 'profile') and user.profile.phone:
            #     self.fields['phone_number'].initial = user.profile.phone