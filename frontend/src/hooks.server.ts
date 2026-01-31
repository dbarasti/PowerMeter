import { env } from '$env/dynamic/private';
import type { Handle } from '@sveltejs/kit';

// Proxy delle chiamate API al backend (per SSR e chiamate server-side)
export const handle: Handle = async ({ event, resolve }) => {
	// Se la richiesta è per /api/*, fai proxy al backend
	if (event.url.pathname.startsWith('/api')) {
		const backendUrl = env.BACKEND_URL || 'http://backend:8000';
		const apiPath = event.url.pathname.replace('/api', '');
		const targetUrl = `${backendUrl}${apiPath}${event.url.search}`;

		try {
			const headers: Record<string, string> = {};
			event.request.headers.forEach((value, key) => {
				// Non copiare alcuni header che potrebbero causare problemi
				if (key.toLowerCase() !== 'host' && key.toLowerCase() !== 'connection') {
					headers[key] = value;
				}
			});

			const response = await fetch(targetUrl, {
				method: event.request.method,
				headers,
				body: event.request.method !== 'GET' && event.request.method !== 'HEAD' 
					? await event.request.text() 
					: undefined
			});

			const data = await response.text();
			return new Response(data, {
				status: response.status,
				statusText: response.statusText,
				headers: {
					'Content-Type': response.headers.get('Content-Type') || 'application/json'
				}
			});
		} catch (error) {
			console.error('Proxy error:', error);
			return new Response('Proxy error: ' + (error instanceof Error ? error.message : 'Unknown error'), { 
				status: 502,
				headers: { 'Content-Type': 'text/plain' }
			});
		}
	}

	return resolve(event);
};
