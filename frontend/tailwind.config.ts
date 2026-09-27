import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // BSt-Next CI
        navy: {
          DEFAULT: '#0B2545',
          50: '#E8EBF0',
          100: '#D1D7E1',
          200: '#A3AFC3',
          300: '#7587A5',
          400: '#475F87',
          500: '#0B2545',
          600: '#091E37',
          700: '#071629',
          800: '#040F1B',
          900: '#02070D',
        },
        lime: {
          DEFAULT: '#A3E635',
          50: '#F6FCE8',
          100: '#EDFAD0',
          200: '#DBF5A2',
          300: '#C9F073',
          400: '#B7EB45',
          500: '#A3E635',
          600: '#8FD822',
          700: '#6FA61A',
          800: '#4F7412',
          900: '#2F420A',
        },
      },
    },
  },
  plugins: [],
};
export default config;
