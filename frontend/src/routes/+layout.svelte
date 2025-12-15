<script lang="ts">
	import favicon from '$lib/assets/favicon.svg';
	import { token, logout as logoutStore } from '$lib/stores/auth';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';

	let { children } = $props();

	function logout() {
		logoutStore();
		goto('/login');
	}
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
</svelte:head>

<nav class="navbar">
	<div class="nav-container">
		<h1 class="nav-title">Thermal Test System</h1>
		<div class="nav-links">
			{#if $token}
				<a href="/">Dashboard</a>
				<button class="nav-link-btn" on:click={logout}>Logout</button>
			{/if}
		</div>
	</div>
</nav>

<main class="main-content">
	{@render children()}
</main>

<footer class="footer">
	<p>&copy; 2024 Thermal Test System - Industrial Application</p>
</footer>

<style>
	:global(body) {
		margin: 0;
		padding: 0;
		font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
		background-color: #f5f5f5;
		color: #333;
	}

	.navbar {
		background-color: #2c3e50;
		color: white;
		padding: 1rem 0;
		box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
	}

	.nav-container {
		max-width: 1200px;
		margin: 0 auto;
		padding: 0 2rem;
		display: flex;
		justify-content: space-between;
		align-items: center;
	}

	.nav-title {
		font-size: 1.5rem;
		font-weight: 600;
		margin: 0;
	}

	.nav-links {
		display: flex;
		gap: 1.5rem;
		align-items: center;
	}

	.nav-links a {
		color: white;
		text-decoration: none;
		transition: opacity 0.2s;
	}

	.nav-links a:hover {
		opacity: 0.8;
	}

	.nav-link-btn {
		background: none;
		border: none;
		color: white;
		cursor: pointer;
		font-size: 1rem;
		transition: opacity 0.2s;
	}

	.nav-link-btn:hover {
		opacity: 0.8;
	}

	.main-content {
		min-height: calc(100vh - 200px);
	}

	.footer {
		background-color: #2c3e50;
		color: white;
		text-align: center;
		padding: 1rem;
		margin-top: 3rem;
	}
</style>
