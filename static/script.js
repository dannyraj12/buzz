// Demo version - shows backend notice
function showBackendNotice() {
    alert('⚠️ Backend Required\n\nThis is a static demo. To use the full functionality:\n\n1. Deploy the Python FastAPI backend to Render/Railway\n2. Update the API endpoints in this script\n3. Set your MONGO_URI environment variable\n\nThe backend handles:\n• Playwright browser automation\n• MongoDB logging\n• Proxy rotation\n• Download management');
}

// Placeholder functions for demo
function refreshStatus() {
    document.getElementById('status').textContent = 'Backend Required';
    document.getElementById('statusIndicator').className = 'status-indicator status-idle';
}

function refreshLogs() {
    // Demo logs are already in HTML
}

// Initialize demo
document.addEventListener('DOMContentLoaded', () => {
    console.log('Demo mode - Backend required for full functionality');
    refreshStatus();
});