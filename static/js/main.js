// static/js/main.js

document.addEventListener('DOMContentLoaded', function() {
    // --- Lógica do Menu Lateral (Sidebar) ---
    const openSidebarBtn = document.getElementById('openSidebarBtn');
    const closeSidebarBtn = document.getElementById('closeSidebarBtn');
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('overlay');
    const mainContent = document.getElementById('main-content');

    function openSidebar() {
        sidebar.classList.add('active');
        overlay.classList.add('active');
        document.body.classList.add('sidebar-open');
        if (mainContent) {
            mainContent.classList.add('blurred');
        }
    }

    function closeSidebar() {
        sidebar.classList.remove('active');
        overlay.classList.remove('active');
        document.body.classList.remove('sidebar-open');
        if (mainContent) {
            mainContent.classList.remove('blurred');
        }
    }

    if (openSidebarBtn) {
        openSidebarBtn.addEventListener('click', openSidebar);
    }
    if (closeSidebarBtn) {
        closeSidebarBtn.addEventListener('click', closeSidebar);
    }
    if (overlay) {
        overlay.addEventListener('click', closeSidebar);
    }

    // --- Lógica de Expansão/Recolha de Submenus no Sidebar ---
    const submenuToggles = document.querySelectorAll('#sidebar .submenu-toggle');

    submenuToggles.forEach(toggle => {
        toggle.addEventListener('click', function(event) {
            event.preventDefault(); 
            const parentCategory = this.closest('.sidebar-category');
            if (parentCategory) {
                parentCategory.classList.toggle('active');
            }
        });
    });

    // --- Lógica do Indicador de Carregamento (Loading Spinner) ---
    const loadingSpinner = document.getElementById('loading-spinner');

    if (loadingSpinner) {
        // Para requisições HTMX (se você usar)
        document.body.addEventListener('htmx:beforeRequest', function() {
            loadingSpinner.classList.add('show');
        });
        document.body.addEventListener('htmx:afterRequest', function() {
            loadingSpinner.classList.remove('show');
        });

        // Para navegação normal
        window.addEventListener('beforeunload', function() {
            loadingSpinner.classList.add('show');
        });
        // Esconde o spinner no page load, caso ele tenha ficado preso
        window.addEventListener('load', function() {
            loadingSpinner.classList.remove('show');
        });
    }
    
    // --- Lógica Aprimorada para Mensagens Flash (Alertas) ---
    const flashMessagesContainer = document.querySelector('.flash-messages');
    if (flashMessagesContainer) {
        const alerts = flashMessagesContainer.querySelectorAll('.alert');
        alerts.forEach((alert, index) => {
            setTimeout(() => {
                alert.classList.add('show');
            }, 100 + (index * 50));

            setTimeout(() => {
                alert.classList.remove('show');
                alert.addEventListener('transitionend', () => alert.remove(), { once: true });
            }, 4000 + (index * 50));
        });
    }

    // --- Lógica de Animação de Entrada ao Rolar ---
    const animatedElements = document.querySelectorAll('.product-card, .content-layout');
    
    if (window.IntersectionObserver) {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('visible');
                    observer.unobserve(entry.target);
                }
            });
        }, {
            threshold: 0.1
        });
    
        animatedElements.forEach(el => {
            observer.observe(el);
        });
    } else {
        animatedElements.forEach(el => {
            el.classList.add('visible');
        });
    }

    // --- Lógica do Carrossel de Imagens (Nova Funcionalidade) ---
    const imageCarousel = document.getElementById('imageCarousel');
    const prevSlideBtn = document.getElementById('prevSlide');
    const nextSlideBtn = document.getElementById('nextSlide');
    const carouselDotsContainer = document.getElementById('carouselDots');

    if (imageCarousel && prevSlideBtn && nextSlideBtn && carouselDotsContainer) {
        const slides = imageCarousel.querySelectorAll('.carousel-slide');
        let currentSlideIndex = 0;
        const totalSlides = slides.length;

        // Função para atualizar a exibição do slide
        function updateCarousel() {
            imageCarousel.style.transform = `translateX(-${currentSlideIndex * 100}%)`;
            updateDots();
        }

        // Função para atualizar os pontos de navegação
        function updateDots() {
            carouselDotsContainer.innerHTML = ''; // Limpa os pontos existentes
            slides.forEach((_, index) => {
                const dot = document.createElement('span');
                dot.classList.add('dot');
                if (index === currentSlideIndex) {
                    dot.classList.add('active');
                }
                dot.addEventListener('click', () => {
                    currentSlideIndex = index;
                    updateCarousel();
                });
                carouselDotsContainer.appendChild(dot);
            });
        }

        // Navegar para o slide anterior
        prevSlideBtn.addEventListener('click', () => {
            currentSlideIndex = (currentSlideIndex === 0) ? totalSlides - 1 : currentSlideIndex - 1;
            updateCarousel();
        });

        // Navegar para o próximo slide
        nextSlideBtn.addEventListener('click', () => {
            currentSlideIndex = (currentSlideIndex === totalSlides - 1) ? 0 : currentSlideIndex + 1;
            updateCarousel();
        });

        // Inicializa o carrossel e os pontos
        updateCarousel();

        // Opcional: Auto-play do carrossel
        // setInterval(() => {
        //     currentSlideIndex = (currentSlideIndex === totalSlides - 1) ? 0 : currentSlideIndex + 1;
        //     updateCarousel();
        // }, 5000); // Muda de slide a cada 5 segundos
    }

    // --- Lógica de Pesquisa com Sugestões (Autocompletar) ---
    const searchInput = document.querySelector('.search-bar input[name="q"]');
    const searchSuggestionsContainer = document.getElementById('searchSuggestions');

    if (searchInput && searchSuggestionsContainer) {
        let debounceTimer;

        searchInput.addEventListener('input', function() {
            clearTimeout(debounceTimer);
            const searchTerm = this.value.trim();

            if (searchTerm.length > 1) { // Começa a buscar após 2 caracteres
                debounceTimer = setTimeout(() => {
                    fetchSuggestions(searchTerm);
                }, 300); // Debounce de 300ms
            } else {
                searchSuggestionsContainer.innerHTML = ''; // Limpa as sugestões se o termo for muito curto
                searchSuggestionsContainer.style.display = 'none';
            }
        });

        // Esconde as sugestões quando o campo perde o foco
        searchInput.addEventListener('blur', function() {
            // Pequeno atraso para permitir cliques nas sugestões antes de esconder
            setTimeout(() => {
                searchSuggestionsContainer.style.display = 'none';
            }, 100); 
        });

        // Mostra as sugestões novamente se o campo ganhar foco e houver texto
        searchInput.addEventListener('focus', function() {
            if (searchSuggestionsContainer.children.length > 0 && this.value.trim().length > 1) {
                searchSuggestionsContainer.style.display = 'block';
            }
        });


        async function fetchSuggestions(term) {
            try {
                // Endpoint hipotético no backend para buscar sugestões
                // Você precisará criar esta rota no seu app.py
                const response = await fetch(`/api/search_suggestions?q=${encodeURIComponent(term)}`);
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                const suggestions = await response.json();
                displaySuggestions(suggestions);
            } catch (error) {
                console.error("Erro ao buscar sugestões de pesquisa:", error);
                searchSuggestionsContainer.innerHTML = '<div class="suggestion-item">Erro ao carregar sugestões.</div>';
                searchSuggestionsContainer.style.display = 'block';
            }
        }

        function displaySuggestions(suggestions) {
            searchSuggestionsContainer.innerHTML = ''; // Limpa sugestões anteriores
            if (suggestions.length > 0) {
                suggestions.forEach(suggestion => {
                    const div = document.createElement('div');
                    div.classList.add('suggestion-item');
                    div.textContent = suggestion.name; // Assumindo que a sugestão tem uma propriedade 'name'
                    div.addEventListener('mousedown', (event) => { // Usar mousedown para capturar antes do blur
                        event.preventDefault(); // Previne o blur do input
                        searchInput.value = suggestion.name; // Preenche o input com a sugestão
                        // Você pode redirecionar para a página de detalhes do serviço/projeto ou uma página de resultados de busca
                        // Exemplo: window.location.href = `/servicos/${suggestion.slug}`; 
                        // Ou enviar o formulário: searchInput.closest('form').submit();
                        searchSuggestionsContainer.style.display = 'none'; // Esconde as sugestões
                    });
                    searchSuggestionsContainer.appendChild(div);
                });
                searchSuggestionsContainer.style.display = 'block'; // Mostra o contêiner de sugestões
            } else {
                searchSuggestionsContainer.innerHTML = '<div class="suggestion-item">Nenhuma sugestão encontrada.</div>';
                searchSuggestionsContainer.style.display = 'block';
            }
        }
    }
});
