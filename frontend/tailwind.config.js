/** @type {import('tailwindcss').Config} */
export default {
    content: [
        './index.html',
        './src/**/*.{js,jsx,ts,tsx}',
    ],
    theme: {
        extend: {
            fontFamily: {
                display: ['"Playfair Display"', 'serif'],
                body: ['"Source Serif 4"', 'serif'],
                sans: ['"Source Serif 4"', 'serif'],
                mono: ['"IBM Plex Mono"', 'monospace'],
            },
            colors: {
                paper: 'var(--paper)',
                'paper-raised': 'var(--paper-raised)',
                ink: 'var(--ink)',
                'ink-muted': 'var(--ink-muted)',
                red: 'var(--red)',
                'red-light': 'var(--red-light)',
                gold: 'var(--gold)',
                border: 'var(--border)',
                'border-light': 'var(--border-light)',

                // Legacy mappings to prevent old components from breaking during transition
                void: 'var(--paper)',
                surface: 'var(--paper-raised)',
                panel: 'var(--paper)',
                accent: 'var(--red)',
                accent2: 'var(--red)',
                success: '#167A3E',
                warn: 'var(--gold)',
                danger: 'var(--red)',
                text: 'var(--ink)',
                muted: 'var(--ink-muted)',
            },
            boxShadow: {
                glass: 'none',
                glow: 'none',
            },
            animation: {
                'fade-in': 'fadeIn 0.4s ease-out',
                'slide-up': 'slideUp 0.4s ease-out',
                'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
            },
            keyframes: {
                fadeIn: { '0%': { opacity: 0 }, '100%': { opacity: 1 } },
                slideUp: { '0%': { opacity: 0, transform: 'translateY(16px)' }, '100%': { opacity: 1, transform: 'translateY(0)' } },
            },
        },
    },
    plugins: [],
}
