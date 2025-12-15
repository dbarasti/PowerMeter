<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { token, checkSession } from '$lib/stores/auth';
	import { api, type TestSession } from '$lib/api';
	import { get } from 'svelte/store';

	let sessions: TestSession[] = [];
	let loading = true;
	let showModal = false;
	let formData = {
		truck_plate: '',
		internal_surface_m2: null as number | null,
		external_surface_m2: null as number | null,
		duration_minutes: null as number | null,
		sample_rate_seconds: 5,
		notes: ''
	};
	let creating = false;
	let errorMessage = '';
	let showError = false;

	onMount(async () => {
		const currentToken = get(token);
		if (!currentToken) {
			const isValid = await checkSession();
			if (!isValid) {
				goto('/login');
				return;
			}
		}
		await loadSessions();
	});

	async function loadSessions() {
		try {
			loading = true;
			sessions = await api.getSessions();
		} catch (error) {
			console.error('Error loading sessions:', error);
		} finally {
			loading = false;
		}
	}

	async function createSession() {
		if (!formData.truck_plate) {
			alert('Compila tutti i campi obbligatori');
			return;
		}

		creating = true;
		try {
			await api.createSession({
				truck_plate: formData.truck_plate,
				internal_surface_m2: formData.internal_surface_m2 || undefined,
				external_surface_m2: formData.external_surface_m2 || undefined,
				duration_minutes: formData.duration_minutes || undefined,
				sample_rate_seconds: formData.sample_rate_seconds,
				notes: formData.notes || undefined
			});
			showModal = false;
			formData = {
				truck_plate: '',
				internal_surface_m2: null,
				external_surface_m2: null,
				duration_minutes: null,
				sample_rate_seconds: 5,
				notes: ''
			};
			await loadSessions();
		} catch (error: any) {
			alert('Errore: ' + (error.message || 'Errore sconosciuto'));
		} finally {
			creating = false;
		}
	}

	async function startSession(id: number) {
		if (!confirm('Avviare l\'acquisizione dati per questa sessione?')) return;
		try {
			showError = false;
			errorMessage = '';
			await api.startSession(id);
			await loadSessions();
		} catch (error: any) {
			// Estrai il messaggio di errore dalla risposta
			let errorMsg = 'Impossibile avviare la sessione';
			if (error.detail) {
				errorMsg = error.detail;
			} else if (error.message) {
				errorMsg = error.message;
			}
			errorMessage = errorMsg;
			showError = true;
		}
	}

	async function stopSession(id: number) {
		if (!confirm('Fermare l\'acquisizione dati?')) return;
		try {
			await api.stopSession(id);
			await loadSessions();
		} catch (error: any) {
			alert('Errore: ' + (error.message || 'Impossibile fermare la sessione'));
		}
	}

	function formatDate(dateString: string) {
		return new Date(dateString).toLocaleString('it-IT');
	}
</script>

<svelte:head>
	<title>Dashboard - Thermal Test System</title>
</svelte:head>

	<div class="dashboard-container">
		<div class="dashboard-header">
			<h2>Dashboard Test Termici</h2>
			<button class="btn btn-primary" on:click={() => showModal = true}>Nuova Prova</button>
		</div>

		{#if showError}
			<div class="error-banner">
				<div class="error-content">
					<strong>Errore durante l'avvio dell'acquisizione:</strong>
					<p>{errorMessage}</p>
					<button class="btn btn-secondary" on:click={() => { showError = false; errorMessage = ''; }}>
						Chiudi
					</button>
				</div>
			</div>
		{/if}

	{#if showModal}
		<div class="modal" on:click={(e) => e.target === e.currentTarget && (showModal = false)}>
			<div class="modal-content">
				<span class="close" on:click={() => showModal = false}>&times;</span>
				<h3>Nuova Sessione di Test</h3>
				<form on:submit|preventDefault={createSession}>
					<div class="form-group">
						<label for="truck_plate">Targa Camion *</label>
						<input type="text" id="truck_plate" bind:value={formData.truck_plate} required />
					</div>
					<div class="form-group">
						<label for="internal_surface_m2">Superficie Interna (m²)</label>
						<input type="number" id="internal_surface_m2" bind:value={formData.internal_surface_m2} min="0" step="0.01" placeholder="es: 12.5" />
					</div>
					<div class="form-group">
						<label for="external_surface_m2">Superficie Esterna (m²)</label>
						<input type="number" id="external_surface_m2" bind:value={formData.external_surface_m2} min="0" step="0.01" placeholder="es: 15.2" />
					</div>
					<div class="form-group">
						<label for="duration_minutes">Durata Prova</label>
						<div class="duration-helpers">
							<button 
								type="button" 
								class="duration-btn" 
								class:active={formData.duration_minutes === 60}
								on:click={() => formData.duration_minutes = 60}
							>
								1 ora
							</button>
							<button 
								type="button" 
								class="duration-btn" 
								class:active={formData.duration_minutes === 360}
								on:click={() => formData.duration_minutes = 360}
							>
								6 ore
							</button>
							<button 
								type="button" 
								class="duration-btn" 
								class:active={formData.duration_minutes === 720}
								on:click={() => formData.duration_minutes = 720}
							>
								12 ore
							</button>
							<button 
								type="button" 
								class="duration-btn" 
								class:active={formData.duration_minutes === 1440}
								on:click={() => formData.duration_minutes = 1440}
							>
								24 ore
							</button>
							<button 
								type="button" 
								class="duration-btn" 
								class:active={formData.duration_minutes === null}
								on:click={() => formData.duration_minutes = null}
							>
								Illimitata
							</button>
						</div>
						<input 
							type="number" 
							id="duration_minutes" 
							bind:value={formData.duration_minutes} 
							min="1" 
							placeholder="Oppure inserisci minuti personalizzati" 
						/>
						<small class="help-text">Seleziona una durata standard o inserisci un valore personalizzato. Lascia vuoto per durata illimitata.</small>
					</div>
					<div class="form-group">
						<label for="sample_rate_seconds">Frequenza Campionamento (secondi) *</label>
						<input type="number" id="sample_rate_seconds" bind:value={formData.sample_rate_seconds} min="1" required />
					</div>
					<div class="form-group">
						<label for="notes">Note (opzionale)</label>
						<textarea id="notes" bind:value={formData.notes} rows="3"></textarea>
					</div>
					<button type="submit" class="btn btn-primary" disabled={creating}>
						{creating ? 'Creazione in corso...' : 'Crea Sessione'}
					</button>
				</form>
			</div>
		</div>
	{/if}

	<div class="sessions-list">
		<h3>Sessioni di Test</h3>
		{#if loading}
			<p class="loading">Caricamento sessioni...</p>
		{:else if sessions.length === 0}
			<p>Nessuna sessione trovata. Crea una nuova prova per iniziare.</p>
		{:else}
			{#each sessions as session}
				<div class="session-card">
					<div class="session-card-header">
						<div class="session-card-title">Sessione #{session.id} - {session.truck_plate}</div>
						<span class="session-status status-{session.status.toLowerCase()}">{session.status}</span>
					</div>
					<div class="session-card-body">
						<div class="session-info">
							<strong>Durata prevista:</strong>
							<span>{session.duration_minutes ? `${session.duration_minutes} minuti` : 'Durata illimitata'}</span>
						</div>
						<div class="session-info">
							<strong>Campionamento:</strong>
							<span>{session.sample_rate_seconds} secondi</span>
						</div>
						<div class="session-info">
							<strong>Creata:</strong>
							<span>{formatDate(session.created_at)}</span>
						</div>
						{#if session.started_at}
							<div class="session-info">
								<strong>Avviata:</strong>
								<span>{formatDate(session.started_at)}</span>
							</div>
						{/if}
						{#if session.internal_surface_m2}
							<div class="session-info">
								<strong>Superficie interna:</strong>
								<span>{session.internal_surface_m2} m²</span>
							</div>
						{/if}
						{#if session.external_surface_m2}
							<div class="session-info">
								<strong>Superficie esterna:</strong>
								<span>{session.external_surface_m2} m²</span>
							</div>
						{/if}
					</div>
					{#if session.notes}
						<p class="session-notes">{session.notes}</p>
					{/if}
					<div class="session-actions">
						{#if session.status === 'IDLE'}
							<button class="btn btn-success" on:click={() => startSession(session.id)}>Avvia</button>
							<a href="/session/{session.id}" class="btn btn-secondary">Dettagli</a>
						{:else if session.status === 'RUNNING'}
							<button class="btn btn-danger" on:click={() => stopSession(session.id)}>Ferma</button>
							<a href="/session/{session.id}" class="btn btn-secondary">Monitora</a>
						{:else if session.status === 'COMPLETED'}
							<a href="/session/{session.id}" class="btn btn-primary">Visualizza</a>
						{/if}
					</div>
				</div>
			{/each}
		{/if}
	</div>
</div>

<style>
	.dashboard-container {
		max-width: 1200px;
		margin: 0 auto;
		padding: 2rem;
	}

	.dashboard-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 2rem;
	}

	.dashboard-header h2 {
		font-size: 2rem;
	}

	.btn {
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

	.btn-success {
		background-color: #27ae60;
		color: white;
	}

	.btn-success:hover {
		background-color: #229954;
	}

	.btn-danger {
		background-color: #e74c3c;
		color: white;
	}

	.btn-danger:hover {
		background-color: #c0392b;
	}

	.btn:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.modal {
		position: fixed;
		z-index: 1000;
		left: 0;
		top: 0;
		width: 100%;
		height: 100%;
		background-color: rgba(0, 0, 0, 0.5);
		display: flex;
		justify-content: center;
		align-items: center;
	}

	.modal-content {
		background-color: white;
		padding: 2rem;
		border-radius: 8px;
		width: 90%;
		max-width: 600px;
		position: relative;
		max-height: 90vh;
		overflow-y: auto;
	}

	.close {
		position: absolute;
		right: 1rem;
		top: 1rem;
		font-size: 2rem;
		font-weight: bold;
		cursor: pointer;
		color: #999;
	}

	.close:hover {
		color: #333;
	}

	.form-group {
		margin-bottom: 1rem;
	}

	.form-group label {
		display: block;
		margin-bottom: 0.5rem;
		font-weight: 500;
	}

	.form-group input,
	.form-group textarea {
		width: 100%;
		padding: 0.75rem;
		border: 1px solid #ddd;
		border-radius: 4px;
		font-size: 1rem;
		box-sizing: border-box;
	}

	.help-text {
		display: block;
		margin-top: 0.25rem;
		font-size: 0.85rem;
		color: #7f8c8d;
		font-style: italic;
	}

	.duration-helpers {
		display: flex;
		gap: 0.5rem;
		margin-bottom: 0.75rem;
		flex-wrap: wrap;
	}

	.duration-btn {
		padding: 0.5rem 1rem;
		border: 2px solid #3498db;
		background-color: white;
		color: #3498db;
		border-radius: 4px;
		font-size: 0.9rem;
		cursor: pointer;
		transition: all 0.2s;
		font-weight: 500;
	}

	.duration-btn:hover {
		background-color: #ecf0f1;
		border-color: #2980b9;
		color: #2980b9;
	}

	.duration-btn.active {
		background-color: #3498db;
		color: white;
		border-color: #3498db;
	}

	.duration-btn.active:hover {
		background-color: #2980b9;
		border-color: #2980b9;
	}

	.form-group input:focus,
	.form-group textarea:focus {
		outline: none;
		border-color: #3498db;
	}

	.sessions-list {
		background: white;
		padding: 1.5rem;
		border-radius: 8px;
		box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
	}

	.loading {
		text-align: center;
		padding: 2rem;
		color: #7f8c8d;
	}

	.session-card {
		border: 1px solid #ddd;
		border-radius: 4px;
		padding: 1rem;
		margin-bottom: 1rem;
		background: #fafafa;
	}

	.session-card-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 0.5rem;
	}

	.session-card-title {
		font-size: 1.2rem;
		font-weight: 600;
	}

	.session-status {
		padding: 0.25rem 0.75rem;
		border-radius: 12px;
		font-size: 0.85rem;
		font-weight: 500;
	}

	.status-idle {
		background-color: #ecf0f1;
		color: #34495e;
	}

	.status-running {
		background-color: #3498db;
		color: white;
	}

	.status-completed {
		background-color: #27ae60;
		color: white;
	}

	.session-card-body {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
		gap: 1rem;
		margin-top: 1rem;
	}

	.session-info {
		font-size: 0.9rem;
	}

	.session-info strong {
		display: block;
		margin-bottom: 0.25rem;
		color: #7f8c8d;
	}

	.session-notes {
		margin-top: 0.5rem;
		font-size: 0.9rem;
		color: #7f8c8d;
	}

	.session-actions {
		display: flex;
		gap: 0.5rem;
		margin-top: 1rem;
	}

	.error-banner {
		background-color: #fee;
		border: 2px solid #e74c3c;
		border-radius: 8px;
		padding: 1rem;
		margin-bottom: 1.5rem;
		color: #c0392b;
	}

	.error-content {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.error-content strong {
		font-size: 1.1rem;
	}

	.error-content p {
		margin: 0;
		white-space: pre-line;
		font-size: 0.95rem;
		line-height: 1.5;
	}

	.btn-secondary {
		background-color: #95a5a6;
		color: white;
		align-self: flex-start;
		margin-top: 0.5rem;
	}

	.btn-secondary:hover {
		background-color: #7f8c8d;
	}
</style>
