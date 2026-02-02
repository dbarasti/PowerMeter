<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { token as tokenStore, checkSession } from '$lib/stores/auth';
	import { api, type TestSession } from '$lib/api';
	import { get } from 'svelte/store';
	import { browser } from '$app/environment';
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
	let heaterVoltageChart: Chart | null = null;
	let fanVoltageChart: Chart | null = null;
	let heaterFrequencyChart: Chart | null = null;
	let fanFrequencyChart: Chart | null = null;

	// Coefficiente U
	let uCoefficient: any = null;
	let tempInternal: number = 0;
	let tempExternal: number = 0;
	let calculatingU = false;
	let uError: string | null = null;

	// Modifica superfici
	let editingSurfaces = false;
	let editInternalSurface: number = 0;
	let editExternalSurface: number = 0;
	let updatingSurfaces = false;

	// Auto-refresh
	let refreshInterval: ReturnType<typeof setInterval> | null = null;
	let lastRefreshTime: Date | null = null;
	const REFRESH_INTERVAL_MS = 1000; // 1s per aggiornamenti più frequenti e fluidi

	const sessionId = parseInt($page.params.id);

	onMount(async () => {
		// Importa e registra plugin zoom solo lato client (non durante SSR)
		if (browser) {
			try {
				const zoomModule = await import('chartjs-plugin-zoom');
				Chart.register(zoomModule.default);
				await import('chartjs-adapter-date-fns');
			} catch (error) {
				console.error('Errore caricamento plugin zoom:', error);
			}
		}

		const currentToken = get(tokenStore);
		if (!currentToken) {
			const isValid = await checkSession();
			if (!isValid) {
				goto('/login');
				return;
			}
		}
		await loadSessionData();
		
		// Avvia auto-refresh ogni 5 secondi
		refreshInterval = setInterval(async () => {
			// Non ricaricare se:
			// - siamo in modalità modifica
			// - la sessione è completata (i dati non cambiano più)
			if (!editingSurfaces && !calculatingU && !updatingSurfaces && session?.status !== 'COMPLETED') {
				await updateChartsData();
				lastRefreshTime = new Date();
			}
		}, REFRESH_INTERVAL_MS);
	});

	onDestroy(() => {
		// Pulisci l'intervallo quando il componente viene distrutto
		if (refreshInterval) {
			clearInterval(refreshInterval);
			refreshInterval = null;
		}
	});

	async function loadSessionData() {
		// Salva la posizione di scroll corrente
		const scrollPosition = window.scrollY || document.documentElement.scrollTop;
		
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
				// Ripristina la posizione di scroll dopo che il DOM è stato aggiornato
				requestAnimationFrame(() => {
					window.scrollTo(0, scrollPosition);
				});
			}, 100);

			// Carica coefficiente U se esiste
			await loadUCoefficient();
		} catch (error: any) {
			console.error('Error loading session data:', error);
			alert('Errore nel caricamento dei dati: ' + (error.message || 'Errore sconosciuto'));
		} finally {
			loading = false;
			// Ripristina la posizione di scroll anche in caso di errore
			requestAnimationFrame(() => {
				window.scrollTo(0, scrollPosition);
			});
		}
	}

	// Funzione per aggiornare solo i dati dei grafici senza ricrearli
	async function updateChartsData() {
		try {
			// Aggiorna sessione e statistiche in background
			const [sessionData, statsData, heaterResponse, fanResponse] = await Promise.all([
				api.getSession(sessionId),
				api.getSessionStatistics(sessionId),
				api.getChartData(sessionId, 'heater'),
				api.getChartData(sessionId, 'fan')
			]);

			// Aggiorna i dati senza triggerare re-render della pagina
			session = sessionData;
			statistics = statsData;
			const newHeaterData = heaterResponse.data || [];
			const newFanData = fanResponse.data || [];

			// Confronta i dati per vedere se sono cambiati (confronto efficiente)
			const heaterChanged = newHeaterData.length !== heaterData.length || 
				(newHeaterData.length > 0 && heaterData.length > 0 && 
				 (newHeaterData[newHeaterData.length - 1].timestamp !== heaterData[heaterData.length - 1].timestamp ||
				  newHeaterData[newHeaterData.length - 1].energy_kwh !== heaterData[heaterData.length - 1].energy_kwh));
			
			const fanChanged = newFanData.length !== fanData.length ||
				(newFanData.length > 0 && fanData.length > 0 &&
				 (newFanData[newFanData.length - 1].timestamp !== fanData[fanData.length - 1].timestamp ||
				  newFanData[newFanData.length - 1].energy_kwh !== fanData[fanData.length - 1].energy_kwh));

			if (heaterChanged || fanChanged) {
				heaterData = newHeaterData;
				fanData = newFanData;
				
				// Se i grafici non esistono ancora, creali
				if (!heaterChart && !fanChart && (heaterData.length > 0 || fanData.length > 0)) {
					createCharts();
				} else {
					// Altrimenti aggiorna solo i dati
					updateCharts();
				}
			}
		} catch (error: any) {
			console.error('Error updating charts data:', error);
			// Non mostrare alert per errori di aggiornamento automatico
		}
	}

	async function loadUCoefficient() {
		try {
			uCoefficient = await api.getUCoefficient(sessionId);
			if (uCoefficient) {
				tempInternal = uCoefficient.temp_internal_avg;
				tempExternal = uCoefficient.temp_external_avg;
			}
		} catch (error: any) {
			console.error('Error loading U coefficient:', error);
			// Non è un errore critico, potrebbe semplicemente non essere ancora calcolato
		}
	}

	async function calculateU() {
		if (!tempInternal || !tempExternal) {
			uError = 'Inserire entrambe le temperature';
			return;
		}

		if (tempInternal <= tempExternal) {
			uError = 'La temperatura interna deve essere maggiore della temperatura esterna';
			return;
		}

		try {
			calculatingU = true;
			uError = null;
			uCoefficient = await api.calculateUCoefficient(sessionId, tempInternal, tempExternal);
		} catch (error: any) {
			uError = error.message || 'Errore nel calcolo del coefficiente U';
			console.error('Error calculating U coefficient:', error);
		} finally {
			calculatingU = false;
		}
	}

	// Funzione per aggiornare i grafici esistenti senza ricrearli
	function updateCharts() {
		// Aggiorna grafico energia heater
		if (heaterChart && heaterData.length > 0) {
			heaterChart.data.datasets[0].data = heaterData.map(d => ({
				x: new Date(d.timestamp).getTime(),
				y: d.energy_kwh
			}));
			heaterChart.update('none'); // 'none' = nessuna animazione per aggiornamento fluido
		}

		// Aggiorna grafico potenza heater
		if (heaterPowerChart && heaterData.length > 0) {
			heaterPowerChart.data.datasets[0].data = heaterData.map(d => ({
				x: new Date(d.timestamp).getTime(),
				y: d.power_w
			}));
			heaterPowerChart.update('none');
		}

		// Aggiorna grafico tensione heater (solo se esiste e ci sono dati)
		if (heaterVoltageChart && heaterData.length > 0) {
			if (heaterData.some(d => d.voltage_v != null)) {
				heaterVoltageChart.data.datasets[0].data = heaterData.map(d => ({
					x: new Date(d.timestamp).getTime(),
					y: d.voltage_v
				}));
				heaterVoltageChart.update('none');
			}
		}

		// Aggiorna grafico frequenza heater (solo se esiste e ci sono dati)
		if (heaterFrequencyChart && heaterData.length > 0) {
			if (heaterData.some(d => d.frequency_hz != null)) {
				heaterFrequencyChart.data.datasets[0].data = heaterData.map(d => ({
					x: new Date(d.timestamp).getTime(),
					y: d.frequency_hz
				}));
				heaterFrequencyChart.update('none');
			}
		}

		// Aggiorna grafico energia fan
		if (fanChart && fanData.length > 0) {
			fanChart.data.datasets[0].data = fanData.map(d => ({
				x: new Date(d.timestamp).getTime(),
				y: d.energy_kwh
			}));
			fanChart.update('none');
		}

		// Aggiorna grafico potenza fan
		if (fanPowerChart && fanData.length > 0) {
			fanPowerChart.data.datasets[0].data = fanData.map(d => ({
				x: new Date(d.timestamp).getTime(),
				y: d.power_w
			}));
			fanPowerChart.update('none');
		}

		// Aggiorna grafico tensione fan (solo se esiste e ci sono dati)
		if (fanVoltageChart && fanData.length > 0) {
			if (fanData.some(d => d.voltage_v != null)) {
				fanVoltageChart.data.datasets[0].data = fanData.map(d => ({
					x: new Date(d.timestamp).getTime(),
					y: d.voltage_v
				}));
				fanVoltageChart.update('none');
			}
		}

		// Aggiorna grafico frequenza fan (solo se esiste e ci sono dati)
		if (fanFrequencyChart && fanData.length > 0) {
			if (fanData.some(d => d.frequency_hz != null)) {
				fanFrequencyChart.data.datasets[0].data = fanData.map(d => ({
					x: new Date(d.timestamp).getTime(),
					y: d.frequency_hz
				}));
				fanFrequencyChart.update('none');
			}
		}
	}

	// Funzione helper per creare opzioni comuni dei grafici con zoom/pan
	function getChartOptions(title: string, beginAtZero: boolean = true) {
		return {
			responsive: true,
			maintainAspectRatio: true,
			parsing: false, // Migliora performance con molti dati
			interaction: {
				intersect: false,
				mode: 'index' as const
			},
			plugins: {
				title: {
					display: true,
					text: title
				},
				zoom: {
					pan: {
						enabled: true,
						mode: 'x' as const,
						modifierKey: 'ctrl' as const
					},
					zoom: {
						wheel: {
							enabled: true,
							speed: 0.1
						},
						pinch: {
							enabled: true
						},
						mode: 'x' as const,
						drag: {
							enabled: true,
							modifierKey: 'shift' as const
						}
					}
				},
				legend: {
					display: true
				},
				tooltip: {
					enabled: true,
					mode: 'index' as const,
					intersect: false
				}
			},
			scales: {
				x: {
					type: 'time' as const,
					time: {
						parser: 'yyyy-MM-dd\'T\'HH:mm:ss',
						tooltipFormat: 'dd/MM/yyyy HH:mm:ss',
						displayFormats: {
							millisecond: 'HH:mm:ss.SSS',
							second: 'HH:mm:ss',
							minute: 'HH:mm',
							hour: 'HH:mm',
							day: 'dd/MM',
							week: 'dd/MM',
							month: 'MM/yyyy',
							year: 'yyyy'
						}
					},
					title: {
						display: true,
						text: 'Tempo'
					}
				},
				y: {
					beginAtZero: beginAtZero,
					title: {
						display: true
					}
				}
			}
		};
	}

	function createCharts() {
		// Distruggi grafici esistenti se presenti
		if (heaterChart) heaterChart.destroy();
		if (heaterPowerChart) heaterPowerChart.destroy();
		if (heaterVoltageChart) heaterVoltageChart.destroy();
		if (heaterFrequencyChart) heaterFrequencyChart.destroy();
		if (fanChart) fanChart.destroy();
		if (fanPowerChart) fanPowerChart.destroy();
		if (fanVoltageChart) fanVoltageChart.destroy();
		if (fanFrequencyChart) fanFrequencyChart.destroy();

		// Grafico energia heater
		const heaterEnergyCtx = document.getElementById('heater-energy-chart') as HTMLCanvasElement;
		if (heaterEnergyCtx && heaterData.length > 0) {
			heaterChart = new Chart(heaterEnergyCtx, {
				type: 'line',
				data: {
					datasets: [{
						label: 'Energia (kWh)',
						data: heaterData.map(d => ({
							x: new Date(d.timestamp).getTime(),
							y: d.energy_kwh
						})),
						borderColor: 'rgb(231, 76, 60)',
						backgroundColor: 'rgba(231, 76, 60, 0.1)',
						tension: 0.1,
						pointRadius: 0, // Nascondi punti per performance
						pointHoverRadius: 4
					}]
				},
				options: {
					...getChartOptions('Energia Accumulata - Stufa', true),
					scales: {
						...getChartOptions('', true).scales,
						y: {
							...getChartOptions('', true).scales.y,
							title: {
								display: true,
								text: 'Energia (kWh)'
							}
						}
					},
					plugins: {
						...getChartOptions('', true).plugins,
						title: {
							display: true,
							text: 'Energia Accumulata - Stufa'
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
					datasets: [{
						label: 'Potenza (W)',
						data: heaterData.map(d => ({
							x: new Date(d.timestamp).getTime(),
							y: d.power_w
						})),
						borderColor: 'rgb(231, 76, 60)',
						backgroundColor: 'rgba(231, 76, 60, 0.1)',
						tension: 0.1,
						pointRadius: 0,
						pointHoverRadius: 4
					}]
				},
				options: {
					...getChartOptions('Potenza Istantanea - Stufa', true),
					scales: {
						...getChartOptions('', true).scales,
						y: {
							...getChartOptions('', true).scales.y,
							title: {
								display: true,
								text: 'Potenza (W)'
							}
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
					datasets: [{
						label: 'Energia (kWh)',
						data: fanData.map(d => ({
							x: new Date(d.timestamp).getTime(),
							y: d.energy_kwh
						})),
						borderColor: 'rgb(52, 152, 219)',
						backgroundColor: 'rgba(52, 152, 219, 0.1)',
						tension: 0.1,
						pointRadius: 0,
						pointHoverRadius: 4
					}]
				},
				options: {
					...getChartOptions('Energia Accumulata - Ventilatore', true),
					scales: {
						...getChartOptions('', true).scales,
						y: {
							...getChartOptions('', true).scales.y,
							title: {
								display: true,
								text: 'Energia (kWh)'
							}
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
					datasets: [{
						label: 'Potenza (W)',
						data: fanData.map(d => ({
							x: new Date(d.timestamp).getTime(),
							y: d.power_w
						})),
						borderColor: 'rgb(52, 152, 219)',
						backgroundColor: 'rgba(52, 152, 219, 0.1)',
						tension: 0.1,
						pointRadius: 0,
						pointHoverRadius: 4
					}]
				},
				options: {
					...getChartOptions('Potenza Istantanea - Ventilatore', true),
					scales: {
						...getChartOptions('', true).scales,
						y: {
							...getChartOptions('', true).scales.y,
							title: {
								display: true,
								text: 'Potenza (W)'
							}
						}
					}
				}
			});
		}

		// Grafico tensione heater
		const heaterVoltageCtx = document.getElementById('heater-voltage-chart') as HTMLCanvasElement;
		if (heaterVoltageCtx && heaterData.length > 0 && heaterData.some(d => d.voltage_v != null)) {
			heaterVoltageChart = new Chart(heaterVoltageCtx, {
				type: 'line',
				data: {
					datasets: [{
						label: 'Tensione (V)',
						data: heaterData.map(d => ({
							x: new Date(d.timestamp).getTime(),
							y: d.voltage_v
						})),
						borderColor: 'rgb(155, 89, 182)',
						backgroundColor: 'rgba(155, 89, 182, 0.1)',
						tension: 0.1,
						pointRadius: 0,
						pointHoverRadius: 4
					}]
				},
				options: {
					...getChartOptions('Tensione - Stufa', false),
					scales: {
						...getChartOptions('', false).scales,
						y: {
							...getChartOptions('', false).scales.y,
							title: {
								display: true,
								text: 'Tensione (V)'
							}
						}
					}
				}
			});
		}

		// Grafico frequenza heater
		const heaterFrequencyCtx = document.getElementById('heater-frequency-chart') as HTMLCanvasElement;
		if (heaterFrequencyCtx && heaterData.length > 0 && heaterData.some(d => d.frequency_hz != null)) {
			heaterFrequencyChart = new Chart(heaterFrequencyCtx, {
				type: 'line',
				data: {
					datasets: [{
						label: 'Frequenza (Hz)',
						data: heaterData.map(d => ({
							x: new Date(d.timestamp).getTime(),
							y: d.frequency_hz
						})),
						borderColor: 'rgb(241, 196, 15)',
						backgroundColor: 'rgba(241, 196, 15, 0.1)',
						tension: 0.1,
						pointRadius: 0,
						pointHoverRadius: 4
					}]
				},
				options: {
					...getChartOptions('Frequenza - Stufa', false),
					scales: {
						...getChartOptions('', false).scales,
						y: {
							...getChartOptions('', false).scales.y,
							title: {
								display: true,
								text: 'Frequenza (Hz)'
							}
						}
					}
				}
			});
		}

		// Grafico tensione fan
		const fanVoltageCtx = document.getElementById('fan-voltage-chart') as HTMLCanvasElement;
		if (fanVoltageCtx && fanData.length > 0 && fanData.some(d => d.voltage_v != null)) {
			fanVoltageChart = new Chart(fanVoltageCtx, {
				type: 'line',
				data: {
					datasets: [{
						label: 'Tensione (V)',
						data: fanData.map(d => ({
							x: new Date(d.timestamp).getTime(),
							y: d.voltage_v
						})),
						borderColor: 'rgb(155, 89, 182)',
						backgroundColor: 'rgba(155, 89, 182, 0.1)',
						tension: 0.1,
						pointRadius: 0,
						pointHoverRadius: 4
					}]
				},
				options: {
					...getChartOptions('Tensione - Ventilatore', false),
					scales: {
						...getChartOptions('', false).scales,
						y: {
							...getChartOptions('', false).scales.y,
							title: {
								display: true,
								text: 'Tensione (V)'
							}
						}
					}
				}
			});
		}

		// Grafico frequenza fan
		const fanFrequencyCtx = document.getElementById('fan-frequency-chart') as HTMLCanvasElement;
		if (fanFrequencyCtx && fanData.length > 0 && fanData.some(d => d.frequency_hz != null)) {
			fanFrequencyChart = new Chart(fanFrequencyCtx, {
				type: 'line',
				data: {
					datasets: [{
						label: 'Frequenza (Hz)',
						data: fanData.map(d => ({
							x: new Date(d.timestamp).getTime(),
							y: d.frequency_hz
						})),
						borderColor: 'rgb(241, 196, 15)',
						backgroundColor: 'rgba(241, 196, 15, 0.1)',
						tension: 0.1,
						pointRadius: 0,
						pointHoverRadius: 4
					}]
				},
				options: {
					...getChartOptions('Frequenza - Ventilatore', false),
					scales: {
						...getChartOptions('', false).scales,
						y: {
							...getChartOptions('', false).scales.y,
							title: {
								display: true,
								text: 'Frequenza (Hz)'
							}
						}
					}
				}
			});
		}
	}

	function formatDate(dateString: string) {
		return new Date(dateString).toLocaleString('it-IT');
	}

	// Funzione per resettare lo zoom su tutti i grafici
	function resetAllZoom() {
		const charts = [
			heaterChart,
			heaterPowerChart,
			heaterVoltageChart,
			heaterFrequencyChart,
			fanChart,
			fanPowerChart,
			fanVoltageChart,
			fanFrequencyChart
		];

		charts.forEach(chart => {
			if (chart) {
				// Reset zoom usando il plugin
				if ((chart as any).zoomScale) {
					(chart as any).zoomScale('x', { min: undefined, max: undefined });
					(chart as any).zoomScale('y', { min: undefined, max: undefined });
				}
				// Reset alternativo: ripristina gli assi
				if (chart.scales && chart.scales.x) {
					chart.scales.x.options.min = undefined;
					chart.scales.x.options.max = undefined;
				}
				if (chart.scales && chart.scales.y) {
					chart.scales.y.options.min = undefined;
					chart.scales.y.options.max = undefined;
				}
				chart.update('none');
			}
		});
	}

	async function startSession() {
		if (!session) return;
		if (!confirm('Avviare l\'acquisizione dati per questa sessione?')) return;
		try {
			await api.startSession(sessionId);
			await loadSessionData(); // Ricarica i dati per aggiornare lo stato
		} catch (error: any) {
			// Estrai il messaggio di errore dalla risposta
			let errorMsg = 'Impossibile avviare la sessione';
			if (error.detail) {
				errorMsg = error.detail;
			} else if (error.message) {
				errorMsg = error.message;
			}
			alert(errorMsg);
		}
	}

	async function stopSession() {
		if (!session) return;
		if (!confirm('Fermare l\'acquisizione dati?')) return;
		try {
			await api.stopSession(sessionId);
			await loadSessionData(); // Ricarica i dati per aggiornare lo stato
		} catch (error: any) {
			alert('Errore: ' + (error.message || 'Impossibile fermare la sessione'));
		}
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
				// Ora il file è un ZIP contenente più file CSV (uno per ogni ora)
				a.download = `session_${sessionId}_${session?.truck_plate || 'data'}.zip`;
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

	function startEditSurfaces() {
		if (session) {
			editInternalSurface = session.internal_surface_m2 || 0;
			editExternalSurface = session.external_surface_m2 || 0;
			editingSurfaces = true;
		}
	}

	function cancelEditSurfaces() {
		editingSurfaces = false;
		editInternalSurface = 0;
		editExternalSurface = 0;
	}

	async function saveSurfaces() {
		if (!session) return;

		try {
			updatingSurfaces = true;
			const updated = await api.updateSession(sessionId, {
				internal_surface_m2: editInternalSurface || undefined,
				external_surface_m2: editExternalSurface || undefined
			});
			
			// Aggiorna la sessione locale
			session = updated;
			editingSurfaces = false;
			
			// Se c'è un coefficiente U calcolato, potrebbe essere necessario ricalcolarlo
			// (ma non lo facciamo automaticamente, l'utente può ricalcolarlo se vuole)
			
			alert('Superfici aggiornate con successo');
		} catch (error: any) {
			alert('Errore: ' + (error.message || 'Impossibile aggiornare le superfici'));
		} finally {
			updatingSurfaces = false;
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
		<div class="header-info">
			{#if lastRefreshTime}
				<span class="refresh-indicator" title="Ultimo aggiornamento: {lastRefreshTime.toLocaleTimeString('it-IT')}">
					🔄 Aggiornamento automatico ogni 5s
				</span>
			{/if}
		</div>
		<div class="header-actions">
			{#if session?.status === 'IDLE'}
				<button class="btn btn-success" on:click={startSession}>Avvia Prova</button>
			{:else if session?.status === 'RUNNING'}
				<button class="btn btn-danger" on:click={stopSession}>Ferma Prova</button>
			{/if}
			<button class="btn btn-primary" on:click={exportCSV}>Esporta CSV</button>
		</div>
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
					<span>{session.duration_minutes ? `${session.duration_minutes} minuti` : 'Durata illimitata'}</span>
				</div>
				<div class="info-item">
					<strong>Campionamento:</strong>
					<span>{session.sample_rate_seconds} secondi</span>
				</div>
				<div class="info-item surface-item">
					<strong>Superficie interna:</strong>
					{#if editingSurfaces}
						<input
							type="number"
							bind:value={editInternalSurface}
							step="0.01"
							min="0"
							class="surface-input"
							placeholder="m²"
						/>
					{:else}
						<span>{session.internal_surface_m2 || 'Non specificata'} {session.internal_surface_m2 ? 'm²' : ''}</span>
					{/if}
				</div>
				<div class="info-item surface-item">
					<strong>Superficie esterna:</strong>
					{#if editingSurfaces}
						<input
							type="number"
							bind:value={editExternalSurface}
							step="0.01"
							min="0"
							class="surface-input"
							placeholder="m²"
						/>
					{:else}
						<span>{session.external_surface_m2 || 'Non specificata'} {session.external_surface_m2 ? 'm²' : ''}</span>
					{/if}
				</div>
				{#if editingSurfaces}
					<div class="info-item surface-actions">
						<button class="btn btn-success" on:click={saveSurfaces} disabled={updatingSurfaces}>
							{updatingSurfaces ? 'Salvataggio...' : 'Salva'}
						</button>
						<button class="btn btn-secondary" on:click={cancelEditSurfaces} disabled={updatingSurfaces}>
							Annulla
						</button>
					</div>
				{:else}
					<div class="info-item surface-actions">
						<button class="btn btn-primary" on:click={startEditSurfaces}>
							Modifica Superfici
						</button>
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
						{#if statistics.heater?.avg_voltage_v}
							<div class="stat-value">
								<label>Tensione Media:</label>
								<span>{statistics.heater.avg_voltage_v.toFixed(1)} V</span>
							</div>
						{/if}
						{#if statistics.heater?.avg_frequency_hz}
							<div class="stat-value">
								<label>Frequenza Media:</label>
								<span>{statistics.heater.avg_frequency_hz.toFixed(2)} Hz</span>
							</div>
						{/if}
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
						{#if statistics.fan?.avg_voltage_v}
							<div class="stat-value">
								<label>Tensione Media:</label>
								<span>{statistics.fan.avg_voltage_v.toFixed(1)} V</span>
							</div>
						{/if}
						{#if statistics.fan?.avg_frequency_hz}
							<div class="stat-value">
								<label>Frequenza Media:</label>
								<span>{statistics.fan.avg_frequency_hz.toFixed(2)} Hz</span>
							</div>
						{/if}
						<div class="stat-value">
							<label>Numero Misure:</label>
							<span>{statistics.fan?.measurement_count || 0}</span>
						</div>
					</div>
				</div>
			</div>
		{/if}

		<!-- Calcolatore Coefficiente U -->
		{#if session.status === 'COMPLETED' && session.internal_surface_m2 && session.external_surface_m2}
			<div class="u-coefficient-section">
				<h3>Calcolo Coefficiente di Dispersione Termica (U)</h3>
				
				<!-- Formula esplicita -->
				<div class="formula-section">
					<h4>Formula di Calcolo</h4>
					<div class="formula-box">
						<div class="formula-step">
							<strong>1. Superficie Equivalente (A_eq):</strong>
							<div class="formula">A<sub>eq</sub> = √(A<sub>int</sub> × A<sub>ext</sub>)</div>
							<div class="formula-desc">Media geometrica tra superficie interna ed esterna</div>
						</div>
						<div class="formula-step">
							<strong>2. Potenza Media (P_media):</strong>
							<div class="formula">P<sub>media</sub> = E<sub>tot</sub> / t</div>
							<div class="formula-desc">Energia totale (Wh) divisa per durata prova (h) → risultato in W</div>
						</div>
						<div class="formula-step">
							<strong>3. Differenza Temperatura (ΔT):</strong>
							<div class="formula">ΔT = T<sub>int</sub> - T<sub>ext</sub></div>
							<div class="formula-desc">Differenza tra temperatura media interna ed esterna (°C)</div>
						</div>
						<div class="formula-step highlight">
							<strong>4. Coefficiente U (Trasmittanza Globale):</strong>
							<div class="formula">U = P<sub>media</sub> / (A<sub>eq</sub> × ΔT)</div>
							<div class="formula-desc">Unità: W/m²K (Watt per metro quadro per Kelvin)</div>
						</div>
					</div>
				</div>
				
				<div class="u-coefficient-card">
					{#if uError}
						<div class="error-message">{uError}</div>
					{/if}

					{#if uCoefficient}
						<!-- Risultato calcolato -->
						<div class="u-result">
							<h4>Risultato Calcolo</h4>
							<div class="u-result-grid">
								<div class="u-result-item">
									<label>Superficie Equivalente (A_eq):</label>
									<span>{uCoefficient.equivalent_surface_m2?.toFixed(2)} m²</span>
									<small>√(A_int × A_ext) = √({session.internal_surface_m2} × {session.external_surface_m2})</small>
								</div>
								<div class="u-result-item">
									<label>Potenza Media (P_media):</label>
									<span>{uCoefficient.avg_power_w?.toFixed(2)} W</span>
									<small>E_tot / durata</small>
								</div>
								<div class="u-result-item">
									<label>Differenza Temperatura (ΔT):</label>
									<span>{uCoefficient.delta_t?.toFixed(2)} °C</span>
									<small>T_int - T_ext = {uCoefficient.temp_internal_avg} - {uCoefficient.temp_external_avg}</small>
								</div>
								<div class="u-result-item highlight">
									<label>Coefficiente U (Trasmittanza Globale):</label>
									<span class="u-value">{uCoefficient.u_value?.toFixed(4)} W/m²K</span>
									<small>P_media / (A_eq × ΔT)</small>
								</div>
							</div>
							<div class="u-meta">
								<small>Calcolato il {new Date(uCoefficient.calculated_at).toLocaleString('it-IT')}</small>
							</div>
						</div>
					{/if}

					<!-- Form per inserire temperature -->
					<div class="u-form">
						<h4>{uCoefficient ? 'Ricalcola con nuove temperature' : 'Inserisci Temperature'}</h4>
						<div class="u-form-grid">
							<div class="form-group">
								<label for="temp-internal">Temperatura Media Interna (°C) *</label>
								<input
									type="number"
									id="temp-internal"
									bind:value={tempInternal}
									step="0.1"
									required
									placeholder="es. 20.0"
								/>
							</div>
							<div class="form-group">
								<label for="temp-external">Temperatura Media Esterna (°C) *</label>
								<input
									type="number"
									id="temp-external"
									bind:value={tempExternal}
									step="0.1"
									required
									placeholder="es. 5.0"
								/>
							</div>
						</div>
						<button
							class="btn btn-primary"
							on:click={calculateU}
							disabled={calculatingU}
						>
							{calculatingU ? 'Calcolo in corso...' : (uCoefficient ? 'Ricalcola' : 'Calcola Coefficiente U')}
						</button>
					</div>
				</div>
			</div>
		{/if}

		<!-- Grafici -->
		<div class="charts-section">
			<div class="charts-header">
				<h3>Grafici Stufa</h3>
				<div class="chart-controls">
					<button class="btn btn-small" on:click={resetAllZoom} title="Ripristina zoom su tutti i grafici">
						Ripristina Zoom
					</button>
					<div class="zoom-help">
						<strong>Zoom e Pan:</strong>
						<ul>
							<li>🔍 <strong>Zoom:</strong> Rotella mouse o pinch (mobile)</li>
							<li>👆 <strong>Pan:</strong> Trascina con <kbd>Ctrl</kbd> (o <kbd>Shift</kbd> per drag-to-zoom)</li>
							<li>🔄 <strong>Reset:</strong> Doppio click sul grafico</li>
						</ul>
					</div>
				</div>
			</div>
			<div class="charts-grid">
				<div class="chart-container">
					<canvas id="heater-power-chart"></canvas>
				</div>
				<div class="chart-container">
					<canvas id="heater-energy-chart"></canvas>
				</div>
				<div class="chart-container">
					<canvas id="heater-voltage-chart"></canvas>
				</div>
				<div class="chart-container">
					<canvas id="heater-frequency-chart"></canvas>
				</div>
			</div>
		</div>

		<div class="charts-section">
			<div class="charts-header">
				<h3>Grafici Ventilatore</h3>
			</div>
			<div class="charts-grid">
				<div class="chart-container">
					<canvas id="fan-power-chart"></canvas>
				</div>
				<div class="chart-container">
					<canvas id="fan-energy-chart"></canvas>
				</div>
				<div class="chart-container">
					<canvas id="fan-voltage-chart"></canvas>
				</div>
				<div class="chart-container">
					<canvas id="fan-frequency-chart"></canvas>
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
		flex-wrap: wrap;
	}

	.session-header h2 {
		flex: 1;
		margin: 0;
		font-size: 2rem;
		min-width: 200px;
	}

	.header-info {
		display: flex;
		align-items: center;
		gap: 1rem;
	}

	.refresh-indicator {
		font-size: 0.85rem;
		color: #7f8c8d;
		opacity: 0.8;
	}

	.header-actions {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
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

	.surface-item {
		align-items: center;
	}

	.surface-input {
		width: 120px;
		padding: 0.5rem;
		border: 1px solid #ddd;
		border-radius: 4px;
		font-size: 1rem;
		text-align: right;
	}

	.surface-input:focus {
		outline: none;
		border-color: #3498db;
		box-shadow: 0 0 0 2px rgba(52, 152, 219, 0.2);
	}

	.surface-actions {
		grid-column: span 2;
		justify-content: flex-start;
		gap: 0.5rem;
		background: transparent;
		padding: 0.5rem 0;
		flex-direction: row;
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

	.charts-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		margin-bottom: 1.5rem;
		gap: 1rem;
		flex-wrap: wrap;
	}

	.charts-section h3 {
		margin: 0;
		color: #2c3e50;
		font-size: 1.5rem;
	}

	.chart-controls {
		display: flex;
		gap: 1rem;
		align-items: flex-start;
	}

	.btn-small {
		padding: 0.4rem 0.8rem;
		font-size: 0.875rem;
		background: #3498db;
		color: white;
		border: none;
		border-radius: 4px;
		cursor: pointer;
		transition: background 0.2s;
	}

	.btn-small:hover {
		background: #2980b9;
	}

	.zoom-help {
		background: #f8f9fa;
		border: 1px solid #dee2e6;
		border-radius: 4px;
		padding: 0.75rem;
		font-size: 0.875rem;
		max-width: 300px;
	}

	.zoom-help strong {
		display: block;
		margin-bottom: 0.5rem;
		color: #2c3e50;
	}

	.zoom-help ul {
		margin: 0.5rem 0 0 0;
		padding-left: 1.25rem;
		list-style: none;
	}

	.zoom-help li {
		margin: 0.25rem 0;
		line-height: 1.4;
	}

	.zoom-help kbd {
		background: #e9ecef;
		border: 1px solid #ced4da;
		border-radius: 3px;
		padding: 0.1rem 0.3rem;
		font-size: 0.8em;
		font-family: monospace;
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

	.u-coefficient-section {
		margin-bottom: 3rem;
	}

	.u-coefficient-section h3 {
		margin-bottom: 1.5rem;
		color: #2c3e50;
		font-size: 1.5rem;
	}

	.formula-section {
		background: #f8f9fa;
		padding: 1.5rem;
		border-radius: 8px;
		margin-bottom: 2rem;
		border-left: 4px solid #3498db;
	}

	.formula-section h4 {
		margin: 0 0 1rem 0;
		color: #2c3e50;
		font-size: 1.2rem;
	}

	.formula-box {
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.formula-step {
		background: white;
		padding: 1rem;
		border-radius: 4px;
		border: 1px solid #ddd;
	}

	.formula-step.highlight {
		background: #e8f5e9;
		border: 2px solid #4caf50;
	}

	.formula-step strong {
		display: block;
		margin-bottom: 0.5rem;
		color: #2c3e50;
	}

	.formula {
		font-family: 'Courier New', monospace;
		font-size: 1.1rem;
		font-weight: 600;
		color: #2c3e50;
		margin: 0.5rem 0;
		padding: 0.5rem;
		background: #f8f9fa;
		border-radius: 4px;
		text-align: center;
	}

	.formula-step.highlight .formula {
		background: #c8e6c9;
		color: #2e7d32;
		font-size: 1.2rem;
	}

	.formula-desc {
		font-size: 0.9rem;
		color: #666;
		margin-top: 0.25rem;
		font-style: italic;
	}

	.u-coefficient-card {
		background: white;
		padding: 2rem;
		border-radius: 8px;
		box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
	}

	.error-message {
		background: #fee;
		color: #c33;
		padding: 1rem;
		border-radius: 4px;
		margin-bottom: 1.5rem;
		border-left: 4px solid #e74c3c;
	}

	.u-result {
		margin-bottom: 2rem;
		padding-bottom: 2rem;
		border-bottom: 2px solid #ecf0f1;
	}

	.u-result h4 {
		margin: 0 0 1rem 0;
		color: #2c3e50;
	}

	.u-result-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
		gap: 1rem;
	}

	.u-result-item {
		background: #f8f9fa;
		padding: 1rem;
		border-radius: 4px;
	}

	.u-result-item label {
		display: block;
		font-weight: 600;
		color: #555;
		margin-bottom: 0.5rem;
		font-size: 0.9rem;
	}

	.u-result-item span {
		display: block;
		font-size: 1.3rem;
		font-weight: 700;
		color: #2c3e50;
		margin-bottom: 0.25rem;
	}

	.u-result-item.highlight {
		background: #e8f5e9;
		border: 2px solid #4caf50;
	}

	.u-result-item.highlight .u-value {
		color: #2e7d32;
		font-size: 1.5rem;
	}

	.u-result-item small {
		color: #777;
		font-size: 0.85rem;
	}

	.u-meta {
		margin-top: 1rem;
		text-align: right;
		color: #777;
	}

	.u-form h4 {
		margin: 0 0 1rem 0;
		color: #2c3e50;
	}

	.u-form-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
		gap: 1rem;
		margin-bottom: 1.5rem;
	}

	.u-form .form-group {
		display: flex;
		flex-direction: column;
	}

	.u-form .form-group label {
		margin-bottom: 0.5rem;
		font-weight: 500;
		color: #555;
	}

	.u-form .form-group input {
		padding: 0.75rem;
		border: 1px solid #ddd;
		border-radius: 4px;
		font-size: 1rem;
	}

	.u-form .form-group input:focus {
		outline: none;
		border-color: #3498db;
		box-shadow: 0 0 0 2px rgba(52, 152, 219, 0.2);
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

		.u-result-grid {
			grid-template-columns: 1fr;
		}

		.u-form-grid {
			grid-template-columns: 1fr;
		}
	}
</style>

