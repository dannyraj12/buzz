// Global state
let isRefreshing = false;
let refreshInterval;

// DOM elements
const statusElement = document.getElementById('status');
const statusIndicator = document.getElementById('statusIndicator');
const logsElement = document.getElementById('logs');
const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
const clearBtn = document.getElementById('clearBtn');

// Statistics elements
const totalProcessedElement = document.getElementById('totalProcessed');
const successCountElement = document.getElementById('successCount');
const failCountElement = document.getElementById('failCount');
const successRateElement = document.getElementById('successRate');

// Current link elements
const currentLinkElement = document.getElementById('currentLink');
const currentLinkTextElement = document.getElementById('currentLinkText');

// Utility functions
function showLoading(element, message = 'Loading...') {
    element.innerHTML = `<div class="loading"></div> ${message}`;
}

function formatTimestamp(timestamp) {
    try {
        return new Date(timestamp).toLocaleString();
    } catch {
        return timestamp;
    }
}

function formatDuration(seconds) {
    return `${seconds}s`;
}

function getResultColor(result) {
    if (result === 'success') return '#4CAF50';
    if (result.startsWith('timeout')) return '#FF9800';
    if (result.startsWith('error') || result.startsWith('fail')) return '#F44336';
    return '#9E9E9E';
}

// API functions
async function makeRequest(url, options = {}) {
    try {
        const response = await fetch(url, {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            }
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error(`Request to ${url} failed:`, error);
        throw error;
    }
}

// Status and statistics refresh
async function refreshStatus() {
    if (isRefreshing) return;
    
    try {
        const data = await makeRequest('/status');
        const isRunning = data.running;
        const stats = data.stats || {};
        
        // Update status indicator
        statusElement.textContent = isRunning ? 'Running' : 'Idle';
        statusIndicator.className = `status-indicator ${isRunning ? 'status-running' : 'status-idle'}`;
        
        // Update button states
        startBtn.disabled = isRunning;
        stopBtn.disabled = !isRunning;
        
        // Update statistics
        totalProcessedElement.textContent = stats.total_processed || 0;
        successCountElement.textContent = stats.successful_downloads || 0;
        failCountElement.textContent = stats.failed_downloads || 0;
        
        // Calculate success rate
        const total = stats.total_processed || 0;
        const successful = stats.successful_downloads || 0;
        const successRate = total > 0 ? Math.round((successful / total) * 100) : 0;
        successRateElement.textContent = `${successRate}%`;
        
        // Update current link
        if (stats.current_link && isRunning) {
            currentLinkElement.style.display = 'block';
            currentLinkTextElement.textContent = stats.current_link;
        } else {
            currentLinkElement.style.display = 'none';
        }
        
    } catch (error) {
        console.error('Failed to refresh status:', error);
        statusElement.textContent = 'Error';
        statusIndicator.className = 'status-indicator status-idle';
    }
}

// Logs refresh
async function refreshLogs() {
    if (isRefreshing) return;
    
    try {
        const data = await makeRequest('/logs?limit=100');
        const logs = data.logs || [];
        
        if (logs.length === 0) {
            logsElement.textContent = 'No logs available yet...';
            return;
        }
        
        // Format logs for display
        const formattedLogs = logs.map(log => {
            const timestamp = formatTimestamp(log.timestamp);
            const url = log.url.length > 50 ? log.url.substring(0, 50) + '...' : log.url;
            const proxy = log.proxy === 'direct' ? 'DIRECT' : (log.proxy || 'N/A');
            const duration = log.duration ? ` (${formatDuration(log.duration)})` : '';
            const attempt = log.attempt > 1 ? ` [Attempt ${log.attempt}]` : '';
            
            return `[${timestamp}] ${url} via ${proxy} → ${log.result}${duration}${attempt}`;
        }).join('\n');
        
        logsElement.textContent = formattedLogs;
        
        // Auto-scroll to bottom
        logsElement.scrollTop = logsElement.scrollHeight;
        
    } catch (error) {
        console.error('Failed to refresh logs:', error);
        logsElement.textContent = `Error loading logs: ${error.message}`;
    }
}

// Control functions
async function startDownloader() {
    try {
        startBtn.disabled = true;
        startBtn.innerHTML = '<div class="loading"></div> Starting...';
        
        const result = await makeRequest('/start', { method: 'POST' });
        
        if (result.status === 'started') {
            console.log('Downloader started successfully');
            // Refresh status immediately and then start regular updates
            await refreshStatus();
            setTimeout(refreshLogs, 2000); // Give it a moment to start logging
        } else if (result.status === 'already_running') {
            alert('Downloader is already running!');
        } else {
            throw new Error(result.message || 'Unknown error');
        }
        
    } catch (error) {
        console.error('Failed to start downloader:', error);
        alert(`Failed to start downloader: ${error.message}`);
    } finally {
        startBtn.innerHTML = '▶️ Start Downloads';
        await refreshStatus();
    }
}

async function stopDownloader() {
    try {
        stopBtn.disabled = true;
        stopBtn.innerHTML = '<div class="loading"></div> Stopping...';
        
        const result = await makeRequest('/stop', { method: 'POST' });
        
        if (result.status === 'stopped') {
            console.log('Downloader stopped successfully');
        } else {
            throw new Error(result.message || 'Unknown error');
        }
        
    } catch (error) {
        console.error('Failed to stop downloader:', error);
        alert(`Failed to stop downloader: ${error.message}`);
    } finally {
        stopBtn.innerHTML = '⏹️ Stop Downloads';
        await refreshStatus();
    }
}

async function clearLogs() {
    if (!confirm('Are you sure you want to clear all logs?')) {
        return;
    }
    
    try {
        clearBtn.disabled = true;
        clearBtn.innerHTML = '<div class="loading"></div> Clearing...';
        
        await makeRequest('/logs', { method: 'DELETE' });
        await refreshLogs();
        
    } catch (error) {
        console.error('Failed to clear logs:', error);
        alert(`Failed to clear logs: ${error.message}`);
    } finally {
        clearBtn.innerHTML = '🗑️ Clear Logs';
        clearBtn.disabled = false;
    }
}

// Auto-refresh functionality
function startAutoRefresh() {
    // Clear any existing interval
    if (refreshInterval) {
        clearInterval(refreshInterval);
    }
    
    // Set up new interval
    refreshInterval = setInterval(async () => {
        if (!isRefreshing) {
            isRefreshing = true;
            try {
                await Promise.all([refreshStatus(), refreshLogs()]);
            } finally {
                isRefreshing = false;
            }
        }
    }, 3000); // Refresh every 3 seconds
}

function stopAutoRefresh() {
    if (refreshInterval) {
        clearInterval(refreshInterval);
        refreshInterval = null;
    }
}

// Page visibility handling
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        stopAutoRefresh();
    } else {
        startAutoRefresh();
        // Immediate refresh when page becomes visible
        setTimeout(() => {
            refreshStatus();
            refreshLogs();
        }, 100);
    }
});

// Initialize on page load
document.addEventListener('DOMContentLoaded', async () => {
    console.log('Initializing Buzzheavier Auto Downloader...');
    
    // Initial load
    showLoading(logsElement, 'Loading logs...');
    
    try {
        await Promise.all([refreshStatus(), refreshLogs()]);
    } catch (error) {
        console.error('Initial load failed:', error);
    }
    
    // Start auto-refresh
    startAutoRefresh();
    
    console.log('Initialization complete');
});

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    stopAutoRefresh();
});