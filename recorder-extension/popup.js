// popup.js
async function executeTabFunction(funcName) {
    let [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    // ensure content script is present
    await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        files: ['content.js']
    });
    // invoke the function by name in page context
    chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: (fName) => window[fName] && window[fName](),
        args: [funcName]
    });
}

// Export recorded actions from background
async function exportActions() {
    chrome.runtime.sendMessage({ type: 'exportActions' }, (res) => {
        const s = JSON.stringify(res.actions, null, 2);
        const blob = new Blob([s], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "recorded_test.json";
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        if (navigator.clipboard) navigator.clipboard.writeText(s).catch(()=>console.warn('copy failed'));
        console.log('Exported actions:', (res.actions || []).length);
    });
}

async function clearActions() {
    chrome.runtime.sendMessage({ type: 'clearActions' }, (res) => console.log('Actions cleared', res.status));
}

document.getElementById('startBtn').addEventListener('click', () => executeTabFunction('startRecorder'));
document.getElementById('stopBtn').addEventListener('click', () => executeTabFunction('stopRecorder'));
document.getElementById('exportBtn').addEventListener('click', exportActions);
document.getElementById('clearBtn').addEventListener('click', clearActions);
