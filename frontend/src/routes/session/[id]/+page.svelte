<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { token as tokenStore, checkSession } from '$lib/stores/auth';
	import { api, type TestSession } from '$lib/api';
	import { get } from 'svelte/store';
	import Chart from 'chart.js/auto';

	let session: TestSession | null = null;
	let loading = true;
	let statistics: any = null;
	let heaterData: any[] = [];
	let fanData: any[] = [];
	let heaterChart: Chart | null = null;
	let fanChart: Chart | null = null;
	let heaterPowerChart: Chart | null = null;
	let fanPowerChart: Chart | null = null;

	const sessionId = parseInt($page.params.id);

	onMount(async () => {
		const currentToken = get(tokenStore);
		if (!currentToken) {
			const isValid = await checkSession();
			if (!isValid) {
				goto('/login');
				return;
			}
		}
		await loadSessionData();
	});

	async function loadSessionData() {
		try {
			loading = true;
			
			// Carica sessione
			session = await api.getSession(sessionId);

			// Carica statistiche
			statistics = await api.getSessionStatistics(sessionId);

			// Carica dati per grafici
			const heaterResponse = await api.getChartData(sessionId, 'heater');
			heaterData = heaterResponse.data || [];

			const fanResponse = await api.getChartData(sessionId, 'fan');
			fanData = fanResponse.data || [];

			// Crea grafici dopo un breve delay per assicurarsi che il DOM sia pronto
			setTimeout(() => {
				createCharts();
			}, 100);
		} catch (error: any) {
			console.error('Error loading session data:', error);
			alert('Errore nel caricamento dei dati: ' + (error.message || 'Errore sconosciuto'));
		} finally {
			loading = false;
		}
	}

	function createCharts() {
		// Distruggi grafici esistenti se presenti
		if (heaterChart) heaterChart.destroy();
		if (heaterPowerChart) heaterPowerChart.destroy();
		if (fanChart) fanChart.destroy();
		if (fanPowerChart) fanPowerChart.destroy();

		// Grafico energia heater
		const heaterEnergyCtx = document.getElementById('heater-energy-chart') as HTMLCanvasElement;
		if (heaterEnergyCtx && heaterData.length > 0) {
			heaterChart = new Chart(heaterEnergyCtx, {
				type: 'line',
				data: {
					labels: heaterData.map(d => new Date(d.timestamp).toLocaleTimeString('it-IT')),
					datasets: [{
						label: 'Energia (kWh)',
						data: heaterData.map(d => d.energy_kwh),
						borderColor: 'rgb(231, 76, 60)',
						backgroundColor: 'rgba(231, 76, 60, 0.1)',
						tension: 0.1
					}]
				},
				options: {
					responsive: true,
					plugins: {
						title: {
							display: true,
							text: 'Energia Accumulata - Stufa'
						}
					},
					scales: {
						y: {
							beginAtZero: true
						}
					}
				}
			});
		}

		// Grafico potenza heater
		const heaterPowerCtx = document.getElementById('heater-power-chart') as HTMLCanvasElement;
		if (heaterPowerCtx && heaterData.length > 0) {
			heaterPowerChart = new Chart(heaterPowerCtx, {
				type: 'line',
				data: {
					labels: heaterData.map(d => new Date(d.timestamp).toLocaleTimeString('it-IT')),
					datasets: [{
						label: 'Potenza (W)',
						data: heaterData.map(d => d.power_w),
						borderColor: 'rgb(231, 76, 60)',
						backgroundColor: 'rgba(231, 76, 60, 0.1)',
						tension: 0.1
					}]
				},
				options: {
					responsive: true,
					plugins: {
						title: {
							display: true,
							text: 'Potenza Istantanea - Stufa'
						}
					},
					scales: {
						y: {
							beginAtZero: true
						}
					}
				}
			});
		}

		// Grafico energia fan
		const fanEnergyCtx = document.getElementById('fan-energy-chart') as HTMLCanvasElement;
		if (fanEnergyCtx && fanData.length > 0) {
			fanChart = new Chart(fanEnergyCtx, {
				type: 'line',
				data: {
					labels: fanData.map(d => new Date(d.timestamp).toLocaleTimeString('it-IT')),
					datasets: [{
						label: 'Energia (kWh)',
						data: fanData.map(d => d.energy_kwh),
						borderColor: 'rgb(52, 152, 219)',
						backgroundColor: 'rgba(52, 152, 219, 0.1)',
						tension: 0.1
					}]
				},
				options: {
					responsive: true,
					plugins: {
						title: {
							display: true,
							text: 'Energia Accumulata - Ventilatore'
						}
					},
					scales: {
						y: {
							beginAtZero: true
						}
					}
				}
			});
		}

		// Grafico potenza fan
		const fanPowerCtx = document.getElementById('fan-power-chart') as HTMLCanvasElement;
		if (fanPowerCtx && fanData.length > 0) {
			fanPowerChart = new Chart(fanPowerCtx, {
				type: 'line',
				data: {
					labels: fanData.map(d => new Date(d.timestamp).toLocaleTimeString('it-IT')),
					datasets: [{
						label: 'Potenza (W)',
						data: fanData.map(d => d.power_w),
						borderColor: 'rgb(52, 152, 219)',
						backgroundColor: 'rgba(52, 152, 219, 0.1)',
						tension: 0.1
					}]
				},
				options: {
					responsive: true,
					plugins: {
						title: {
							display: true,
							text: 'Potenza Istantanea - Ventilatore'
						}
					},
					scales: {
						y: {
							beginAtZero: true
						}
					}
				}
			});
		}
	}

	function formatDate(dateString: string) {
		return new Date(dateString).toLocaleString('it-IT');
	}

	async function exportCSV() {
		try {
			const token = get(tokenStore);
			if (!token) {
				alert('Non sei autenticato');
				return;
			}

			const response = await fetch(`/api/data/sessions/${sessionId}/export`, {
				headers: {
					'Authorization': `Bearer ${token}`
				}
			});

			if (response.ok) {
				const blob = await response.blob();
				const url = window.URL.createObjectURL(blob);
				const a = document.createElement('a');
				a.href = url;
				a.download = `session_${sessionId}_${session?.truck_plate || 'data'}.csv`;
				document.body.appendChild(a);
				a.click();
				document.body.removeChild(a);
				window.URL.revokeObjectURL(url);
			} else {
				alert('Errore durante l\'esportazione');
			}
		} catch (error: any) {
			alert('Errore: ' + (error.message || 'Errore sconosciuto'));
		}
	}
</script>

<svelte:head>
	<title>Sessione #{sessionId} - Thermal Test System</title>
</svelte:head>

<div class="session-detail-container">
	<div class="session-header">
		<button class="btn btn-secondary" on:click={() => goto('/')}>← Torna alla Dashboard</button>
		<h2>Sessione #{sessionId} - {session?.truck_plate || 'Caricamento...'}</h2>
		<button class="btn btn-primary" on:click={exportCSV}>Esporta CSV</button>
	</div>

	{#if loading}
		<p class="loading">Caricamento dati...</p>
	{:else if session}
		<!-- Info sessione -->
		<div class="session-info-card">
			<div class="info-grid">
				<div class="info-item">
					<strong>Targa:</strong>
					<span>{session.truck_plate}</span>
				</div>
				<div class="info-item">
					<strong>Stato:</strong>
					<span class="status-badge status-{session.status.toLowerCase()}">{session.status}</span>
				</div>
				<div class="info-item">
					<strong>Durata prevista:</strong>
					<span>{session.duration_minutes} minuti</span>
				</div>
				<div class="info-item">
					<strong>Campionamento:</strong>
					<span>{session.sample_rate_seconds} secondi</span>
				</div>
				{#if session.cell_dimensions}
					<div class="info-item">
						<strong>Dimensioni cella:</strong>
						<span>{session.cell_dimensions}</span>
					</div>
				{/if}
				<div class="info-item">
					<strong>Creata:</strong>
					<span>{formatDate(session.created_at)}</span>
				</div>
				{#if session.started_at}
					<div class="info-item">
						<strong>Avviata:</strong>
						<span>{formatDate(session.started_at)}</span>
					</div>
				{/if}
				{#if session.completed_at}
					<div class="info-item">
						<strong>Completata:</strong>
						<span>{formatDate(session.completed_at)}</span>
					</div>
				{/if}
			</div>
			{#if session.notes}
				<div class="notes">
					<strong>Note:</strong>
					<p>{session.notes}</p>
				</div>
			{/if}
		</div>

		<!-- Statistiche -->
		{#if statistics}
			<div class="statistics-grid">
				<div class="stat-card">
					<h3>Stufa - Statistiche</h3>
					<div class="stat-values">
						<div class="stat-value">
							<label>Potenza Media:</label>
							<span>{statistics.heater?.avg_power_w?.toFixed(2) || '0.00'} W</span>
						</div>
						<div class="stat-value">
							<label>Potenza Max:</label>
							<span>{statistics.heater?.max_power_w?.toFixed(2) || '0.00'} W</span>
						</div>
						<div class="stat-value">
							<label>Potenza Min:</label>
							<span>{statistics.heater?.min_power_w?.toFixed(2) || '0.00'} W</span>
						</div>
						<div class="stat-value">
							<label>Energia Totale:</label>
							<span>{statistics.heater?.total_energy_kwh?.toFixed(3) || '0.000'} kWh</span>
						</div>
						<div class="stat-value">
							<label>Numero Misure:</label>
							<span>{statistics.heater?.measurement_count || 0}</span>
						</div>
					</div>
				</div>

				<div class="stat-card">
					<h3>Ventilatore - Statistiche</h3>
					<div class="stat-values">
						<div class="stat-value">
							<label>Potenza Media:</label>
							<span>{statistics.fan?.avg_power_w?.toFixed(2) || '0.00'} W</span>
						</div>
						<div class="stat-value">
							<label>Potenza Max:</label>
							<span>{statistics.fan?.max_power_w?.toFixed(2) || '0.00'} W</span>
						</div>
						<div class="stat-value">
							<label>Potenza Min:</label>
							<span>{statistics.fan?.min_power_w?.toFixed(2) || '0.00'} W</span>
						</div>
						<div class="stat-value">
							<label>Energia Totale:</label>
							<span>{statistics.fan?.total_energy_kwh?.toFixed(3) || '0.000'} kWh</span>
						</div>
						<div class="stat-value">
							<label>Numero Misure:</label>
							<span>{statistics.fan?.measurement_count || 0}</span>
						</div>
					</div>
				</div>
			</div>
		{/if}

		<!-- Grafici -->
		<div class="charts-section">
			<h3>Grafici Stufa</h3>
			<div class="charts-grid">
				<div class="chart-container">
					<canvas id="heater-power-chart"></canvas>
				</div>
				<div class="chart-container">
					<canvas id="heater-energy-chart"></canvas>
				</div>
			</div>
		</div>

		<div class="charts-section">
			<h3>Grafici Ventilatore</h3>
			<div class="charts-grid">
				<div class="chart-container">
					<canvas id="fan-power-chart"></canvas>
				</div>
				<div class="chart-container">
					<canvas id="fan-energy-chart"></canvas>
				</div>
			</div>
		</div>
	{/if}
</div>

<style>
	.session-detail-container {
		max-width: 1400px;
		margin: 0 auto;
		padding: 2rem;
	}

	.session-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 2rem;
		gap: 1rem;
	}

	.session-header h2 {
		flex: 1;
		margin: 0;
		font-size: 2rem;
	}

	.loading {
		text-align: center;
		padding: 3rem;
		color: #7f8c8d;
		font-size: 1.2rem;
	}

	.session-info-card {
		background: white;
		padding: 1.5rem;
		border-radius: 8px;
		box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
		margin-bottom: 2rem;
	}

	.info-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
		gap: 1rem;
		margin-bottom: 1rem;
	}

	.info-item {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}

	.info-item strong {
		color: #7f8c8d;
		font-size: 0.9rem;
	}

	.status-badge {
		padding: 0.25rem 0.75rem;
		border-radius: 12px;
		font-size: 0.85rem;
		font-weight: 500;
		display: inline-block;
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

	.notes {
		margin-top: 1rem;
		padding-top: 1rem;
		border-top: 1px solid #ddd;
	}

	.notes p {
		margin: 0.5rem 0 0 0;
		color: #555;
	}

	.statistics-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
		gap: 1.5rem;
		margin-bottom: 2rem;
	}

	.stat-card {
		background: white;
		padding: 1.5rem;
		border-radius: 8px;
		box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
	}

	.stat-card h3 {
		margin: 0 0 1rem 0;
		color: #2c3e50;
		border-bottom: 2px solid #3498db;
		padding-bottom: 0.5rem;
	}

	.stat-values {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}

	.stat-value {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 0.5rem;
		background: #f8f9fa;
		border-radius: 4px;
	}

	.stat-value label {
		font-weight: 500;
		color: #555;
	}

	.stat-value span {
		font-weight: 600;
		color: #2c3e50;
		font-size: 1.1rem;
	}

	.charts-section {
		margin-bottom: 3rem;
	}

	.charts-section h3 {
		margin-bottom: 1.5rem;
		color: #2c3e50;
		font-size: 1.5rem;
	}

	.charts-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(500px, 1fr));
		gap: 1.5rem;
	}

	.chart-container {
		background: white;
		padding: 1.5rem;
		border-radius: 8px;
		box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
		height: 400px;
		position: relative;
	}

	.btn {
		padding: 0.75rem 1.5rem;
		border: none;
		border-radius: 4px;
		font-size: 1rem;
		cursor: pointer;
		transition: background-color 0.2s;
		text-decoration: none;
		display: inline-block;
	}

	.btn-primary {
		background-color: #3498db;
		color: white;
	}

	.btn-primary:hover {
		background-color: #2980b9;
	}

	.btn-secondary {
		background-color: #95a5a6;
		color: white;
	}

	.btn-secondary:hover {
		background-color: #7f8c8d;
	}

	@media (max-width: 768px) {
		.session-header {
			flex-direction: column;
			align-items: stretch;
		}

		.charts-grid {
			grid-template-columns: 1fr;
		}

		.chart-container {
			height: 300px;
		}
	}
</style>

