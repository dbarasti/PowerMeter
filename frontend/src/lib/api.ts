import { get } from 'svelte/store';
import { token } from './stores/auth';

async function authenticatedFetch(url: string, options: RequestInit = {}): Promise<Response> {
	const currentToken = get(token);
	
	const headers = {
		'Content-Type': 'application/json',
		...options.headers
	};

	if (currentToken) {
		headers['Authorization'] = `Bearer ${currentToken}`;
	}

	const response = await fetch(url, {
		...options,
		headers
	});

	if (response.status === 401) {
		// Token scaduto o non valido
		token.set(null);
		window.location.href = '/login';
		throw new Error('Unauthorized');
	}

	return response;
}

export interface TestSession {
	id: number;
	truck_plate: string;
	internal_surface_m2?: number;
	external_surface_m2?: number;
	notes?: string;
	duration_minutes: number | null;
	sample_rate_seconds: number;
	status: string;
	started_at?: string;
	completed_at?: string;
	created_at: string;
	updated_at: string;
}

export interface CreateSessionData {
	truck_plate: string;
	internal_surface_m2?: number;
	external_surface_m2?: number;
	duration_minutes?: number;
	sample_rate_seconds: number;
	notes?: string;
}

export const api = {
	async getSessions(): Promise<TestSession[]> {
		const response = await authenticatedFetch('/api/sessions');
		if (!response.ok) throw new Error('Failed to fetch sessions');
		return response.json();
	},

	async getSession(sessionId: number): Promise<TestSession> {
		const response = await authenticatedFetch(`/api/sessions/${sessionId}`);
		if (!response.ok) throw new Error('Failed to fetch session');
		return response.json();
	},

	async createSession(data: CreateSessionData): Promise<TestSession> {
		const response = await authenticatedFetch('/api/sessions', {
			method: 'POST',
			body: JSON.stringify(data)
		});
		if (!response.ok) {
			const error = await response.json();
			throw new Error(error.detail || 'Failed to create session');
		}
		return response.json();
	},

	async startSession(sessionId: number): Promise<void> {
		const response = await authenticatedFetch(`/api/sessions/${sessionId}/start`, {
			method: 'POST'
		});
		if (!response.ok) {
			const error = await response.json();
			// Lancia un errore con il messaggio dettagliato dal backend
			const errorObj: any = new Error(error.detail || 'Failed to start session');
			errorObj.detail = error.detail || error.message || 'Failed to start session';
			throw errorObj;
		}
	},

	async stopSession(sessionId: number): Promise<void> {
		const response = await authenticatedFetch(`/api/sessions/${sessionId}/stop`, {
			method: 'POST'
		});
		if (!response.ok) {
			const error = await response.json();
			throw new Error(error.detail || 'Failed to stop session');
		}
	},

	async getSessionStatistics(sessionId: number): Promise<any> {
		const response = await authenticatedFetch(`/api/data/sessions/${sessionId}/statistics`);
		if (!response.ok) throw new Error('Failed to fetch statistics');
		return response.json();
	},

	async getChartData(sessionId: number, deviceType: 'heater' | 'fan'): Promise<any> {
		const response = await authenticatedFetch(`/api/data/sessions/${sessionId}/chart/${deviceType}`);
		if (!response.ok) throw new Error('Failed to fetch chart data');
		return response.json();
	},

	async calculateUCoefficient(sessionId: number, tempInternal: number, tempExternal: number): Promise<any> {
		const response = await authenticatedFetch(`/api/data/sessions/${sessionId}/u-coefficient`, {
			method: 'POST',
			body: JSON.stringify({
				temp_internal_avg: tempInternal,
				temp_external_avg: tempExternal
			})
		});
		if (!response.ok) {
			const error = await response.json();
			throw new Error(error.detail || 'Failed to calculate U coefficient');
		}
		return response.json();
	},

	async getUCoefficient(sessionId: number): Promise<any> {
		const response = await authenticatedFetch(`/api/data/sessions/${sessionId}/u-coefficient`);
		if (!response.ok) {
			if (response.status === 404) {
				return null; // Coefficiente non ancora calcolato
			}
			throw new Error('Failed to fetch U coefficient');
		}
		return response.json();
	},

	async updateSession(sessionId: number, data: { internal_surface_m2?: number; external_surface_m2?: number; notes?: string }): Promise<TestSession> {
		const response = await authenticatedFetch(`/api/sessions/${sessionId}`, {
			method: 'PUT',
			body: JSON.stringify(data)
		});
		if (!response.ok) {
			const error = await response.json();
			throw new Error(error.detail || 'Failed to update session');
		}
		return response.json();
	}
};

