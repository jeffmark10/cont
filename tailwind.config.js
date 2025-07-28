/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './templates/**/*.html', // Procura em todos os arquivos HTML dentro do diretório 'templates'
    './**/templates/**/*.html', // Também verifica templates dentro de apps Django (ex: store/templates)
    './static/src/**/*.js', // Se você tiver arquivos JavaScript adicionando classes Tailwind dinamicamente
    // Adicione outros caminhos se tiver componentes ou arquivos fora dessas pastas padrão
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}