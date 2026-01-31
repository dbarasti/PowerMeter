import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [sveltekit()],
	server: {
		proxy: {
			'/api': {
				target: process.env.BACKEND_URL || 'http://localhost:8000',
				changeOrigin: true
			}
		},
		host: '0.0.0.0',
		port: 5173
	},
	preview: {
		host: '0.0.0.0',
		port: 5173
	}
});
