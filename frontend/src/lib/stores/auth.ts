import { writable } from 'svelte/store';

export interface User {
	username: string;
	is_active: boolean;
}

export const token = writable<string | null>(null);
export const user = writable<User | null>(null);

// Recupera token da localStorage all'avvio
if (typeof window !== 'undefined') {
	const storedToken = localStorage.getItem('access_token');
	if (storedToken) {
		token.set(storedToken);
	}
}

// Salva token quando cambia
token.subscribe((value) => {
	if (typeof window !== 'undefined') {
		if (value) {
			localStorage.setItem('access_token', value);
		} else {
			localStorage.removeItem('access_token');
		}
	}
});

export async function login(username: string, password: string): Promise<boolean> {
	const formData = new URLSearchParams();
	formData.append('username', username);
	formData.append('password', password);

	try {
		const response = await fetch('/api/auth/login', {
			method: 'POST',
			headers: {
				'Content-Type': 'application/x-www-form-urlencoded'
			},
			body: formData
		});

		if (response.ok) {
			const data = await response.json();
			token.set(data.access_token);
			await checkSession();
			return true;
		}
		return false;
	} catch (error) {
		console.error('Login error:', error);
		return false;
	}
}

export async function checkSession(): Promise<boolean> {
	const currentToken = localStorage.getItem('access_token');
	if (!currentToken) {
		return false;
	}

	try {
		const response = await fetch('/api/auth/me', {
			headers: {
				'Authorization': `Bearer ${currentToken}`
			}
		});

		if (response.ok) {
			const userData = await response.json();
			user.set(userData);
			return true;
		} else {
			token.set(null);
			user.set(null);
			return false;
		}
	} catch (error) {
		console.error('Session check error:', error);
		return false;
	}
}

export function logout() {
	token.set(null);
	user.set(null);
}

