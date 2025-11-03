// background.js
let actions = [];

// load from storage if available (persistence if worker restarts)
chrome.storage.local.get('recordedActions', (data) => {
    actions = data.recordedActions || [];
});

// listen for messages from content scripts / popup
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg.type === 'recordAction') {
        actions.push(msg.action);
        chrome.storage.local.set({ recordedActions: actions });
        sendResponse({ status: 'ok' });
        return true;
    } else if (msg.type === 'exportActions') {
        // return stored actions (asynchronously)
        chrome.storage.local.get('recordedActions', (data) => {
            sendResponse({ actions: data.recordedActions || actions });
        });
        return true; // keep message channel open for async response
    } else if (msg.type === 'clearActions') {
        actions = [];
        chrome.storage.local.set({ recordedActions: actions });
        sendResponse({ status: 'cleared' });
        return true;
    }
});
