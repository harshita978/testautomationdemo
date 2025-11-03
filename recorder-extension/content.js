// content.js
if (!window.__recorderActive) {
    window.__recorderActive = false;
    window.__actions = [];
    let fillTimeout;
    let lastRecordedUrl = location.href;

    // --- stable selector generator (prefer id, name, class) ---
    function getSelector(el) {
        if (!el) return null;
        if (el.id) return `#${el.id}`;
        if (el.name) return `[name="${el.name}"]`;
        if (el.className && typeof el.className === 'string') {
            const cls = el.className.trim().split(/\s+/).join('.');
            if (cls) return `.${cls}`;
        }
        let tag = el.tagName.toLowerCase();
        return tag;
    }

    // attach page context
    function attachContext(action) {
        action.pageUrl = location.href;
        action.pageTitle = document.title || "";
        return action;
    }

    // send action to background
    function sendAction(action) {
        attachContext(action);
        chrome.runtime.sendMessage({ type: 'recordAction', action });
    }

    // record click
    function recordClick(e) {
        const el = e.target;
        const sel = getSelector(el);
        const action = { type: 'click', selector: sel, timestamp: Date.now() };
        window.__actions.push(action);
        sendAction(action);
    }

    // record input (debounced)
    function recordInput(e) {
        clearTimeout(fillTimeout);
        const target = e.target;
        fillTimeout = setTimeout(() => {
            const sel = getSelector(target);
            const value = target.value;
            const action = { type: 'fill', selector: sel, value: value, timestamp: Date.now() };
            window.__actions.push(action);
            sendAction(action);
        }, 500);
    }

    // record goto on URL change
    setInterval(() => {
        if (location.href !== lastRecordedUrl) {
            lastRecordedUrl = location.href;
            const gotoAction = { type: 'goto', url: location.href, timestamp: Date.now() };
            window.__actions.push(gotoAction);
            sendAction(gotoAction);
        }
    }, 700);

    // --- start/stop recorder ---
    window.startRecorder = () => {
        if (window.__recorderActive) return;
        window.__recorderActive = true;
        chrome.storage.local.set({ recorderActive: true });
        document.addEventListener('click', recordClick, true);
        document.addEventListener('input', recordInput, true);
        console.log('Recorder started');
    };

    window.stopRecorder = () => {
        if (!window.__recorderActive) return;
        window.__recorderActive = false;
        chrome.storage.local.set({ recorderActive: false });
        document.removeEventListener('click', recordClick, true);
        document.removeEventListener('input', recordInput, true);
        console.log('Recorder stopped');
    };

    // --- resume recorder after reload if it was active ---
    chrome.storage.local.get('recorderActive', (data) => {
        if (data.recorderActive && !window.__recorderActive) {
            startRecorder();
            console.log('Recorder resumed after reload');
        }
    });

    // --- handle SPA / dynamic DOM ---
    let lastUrl = location.href;
    setInterval(() => {
        if (location.href !== lastUrl) {
            lastUrl = location.href;
            if (window.__recorderActive) {
                window.stopRecorder();
                window.startRecorder();
                console.log('Page changed - listeners reattached');
            }
        }
    }, 500);

    const observer = new MutationObserver(() => {
        if (window.__recorderActive) {
            window.stopRecorder();
            window.startRecorder();
        }
    });
    observer.observe(document.body, { childList: true, subtree: true });

    // --- auto-start on load ---
    window.addEventListener('load', () => {
        if (!window.__recorderActive) startRecorder();
    });

    console.log('Content script loaded');
}
