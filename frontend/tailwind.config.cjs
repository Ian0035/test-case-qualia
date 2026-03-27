module.exports = {
  content: ['./index.html', './src/**/*.{js,svelte}'],
  theme: {
    extend: {
      colors: {
        ink: '#16202d',
        mist: '#f5f7fb',
        glow: '#f4a261',
        spruce: '#2a9d8f',
        coral: '#e76f51'
      },
      boxShadow: {
        panel: '0 30px 80px rgba(22, 32, 45, 0.14)'
      },
      fontFamily: {
        display: ['"Segoe UI Variable"', '"Trebuchet MS"', 'sans-serif']
      }
    }
  },
  plugins: []
};
