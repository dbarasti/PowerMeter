<script lang="ts">
	import { login } from '$lib/stores/auth';
	import { goto } from '$app/navigation';

	let username = '';
	let password = '';
	let error = '';
	let loading = false;

	async function handleSubmit() {
		error = '';
		loading = true;

		const success = await login(username, password);
		
		if (success) {
			goto('/');
		} else {
			error = 'Username o password errati';
		}
		
		loading = false;
	}
</script>

<div class="login-container">
	<div class="login-box">
		<h2>Login</h2>
		<form on:submit|preventDefault={handleSubmit}>
			<div class="form-group">
				<label for="username">Username</label>
				<input
					type="text"
					id="username"
					bind:value={username}
					required
					autofocus
					disabled={loading}
				/>
			</div>
			<div class="form-group">
				<label for="password">Password</label>
				<input
					type="password"
					id="password"
					bind:value={password}
					required
					disabled={loading}
				/>
			</div>
			{#if error}
				<div class="error-message">{error}</div>
			{/if}
			<button type="submit" class="btn btn-primary" disabled={loading}>
				{loading ? 'Accesso in corso...' : 'Accedi'}
			</button>
		</form>
	</div>
</div>

<style>
	.login-container {
		display: flex;
		justify-content: center;
		align-items: center;
		min-height: calc(100vh - 200px);
	}

	.login-box {
		background: white;
		padding: 2rem;
		border-radius: 8px;
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
		width: 100%;
		max-width: 400px;
	}

	.login-box h2 {
		margin-bottom: 1.5rem;
		text-align: center;
	}

	.form-group {
		margin-bottom: 1rem;
	}

	.form-group label {
		display: block;
		margin-bottom: 0.5rem;
		font-weight: 500;
	}

	.form-group input {
		width: 100%;
		padding: 0.75rem;
		border: 1px solid #ddd;
		border-radius: 4px;
		font-size: 1rem;
		box-sizing: border-box;
	}

	.form-group input:focus {
		outline: none;
		border-color: #3498db;
	}

	.error-message {
		color: #e74c3c;
		margin-bottom: 1rem;
		font-size: 0.9rem;
	}

	.btn {
		width: 100%;
		padding: 0.75rem 1.5rem;
		border: none;
		border-radius: 4px;
		font-size: 1rem;
		cursor: pointer;
		transition: background-color 0.2s;
	}

	.btn-primary {
		background-color: #3498db;
		color: white;
	}

	.btn-primary:hover:not(:disabled) {
		background-color: #2980b9;
	}

	.btn:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}
</style>

