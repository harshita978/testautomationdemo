async function executeTabFunction(funcName) {
    let [tab] = await chrome.tabs.query({active: true, currentWindow: true});
    chrome.scripting.executeScript({
        target: {tabId: tab.id},
        func: (f) => window[f] && window[f](),
        args: [funcName]
    });
}

document.getElementById('startBtn').addEventListener('click', () => executeTabFunction('startRecorder'));
document.getElementById('stopBtn').addEventListener('click', () => executeTabFunction('stopRecorder'));
document.getElementById('exportBtn').addEventListener('click', () => executeTabFunction('exportRecorder'));
