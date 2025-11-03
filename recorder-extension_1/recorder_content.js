if (!window.__recorderActive) {
    window.__recorderActive = false;
    window.__actions = [];

    // --- Helper: get unique CSS selector ---
    function getSelector(el) {
        if (!el) return null;
        if (el.id) return `#${el.id}`;
        if (el === document.body) return 'body';
        let path = [], cur = el;
        while(cur && cur.nodeType === 1 && cur !== document.body) {
            let tag = cur.tagName.toLowerCase();
            let nth = 1;
            let sib = cur.previousElementSibling;
            while(sib) { if (sib.tagName === cur.tagName) nth++; sib = sib.previousElementSibling; }
            path.unshift(`${tag}:nth-of-type(${nth})`);
            cur = cur.parentElement;
        }
        return path.join(' > ');
    }

    // --- Load actions immediately ---
    async function loadActions() {
        return new Promise((resolve) => {
            if (chrome && chrome.storage && chrome.storage.local) {
                chrome.storage.local.get('recordedActions', (data) => {
                    window.__actions = data.recordedActions || [];
                    console.log('Loaded actions from storage:', window.__actions.length);
                    resolve();
                });
            } else resolve();
        });
    }

    // --- Persist actions immediately ---
    async function persistActions() {
        if (chrome && chrome.storage && chrome.storage.local) {
            await chrome.storage.local.set({ recordedActions: window.__actions });
        }
    }

    // --- Record events ---
    function recordClick(e) {
        const sel = getSelector(e.target);
        window.__actions.push({ type:'click', selector: sel, timestamp: Date.now() });
        console.log('Recorded click', sel);
        persistActions();
    }

    function recordInput(e) {
        const sel = getSelector(e.target);
        window.__actions.push({ type:'fill', selector: sel, value: e.target.value, timestamp: Date.now() });
        console.log('Recorded fill', sel, e.target.value);
        persistActions();
    }

    // --- Recorder controls ---
    window.startRecorder = async () => {
        if (window.__recorderActive) return;
        await loadActions();
        window.__recorderActive = true;
        document.addEventListener('click', recordClick, true);
        document.addEventListener('input', recordInput, true);
        console.log('Recorder started.');
    };

    window.stopRecorder = () => {
        if (!window.__recorderActive) return;
        window.__recorderActive = false;
        document.removeEventListener('click', recordClick, true);
        document.removeEventListener('input', recordInput, true);
        console.log('Recorder stopped.');
    };

    window.exportRecorder = async () => {
        await loadActions();
        const s = JSON.stringify(window.__actions, null, 2);
        console.log('Exported actions:', s);

        const blob = new Blob([s], {type: "application/json"});
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "flow_recorded.json";
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

        if (navigator.clipboard) {
            navigator.clipboard.writeText(s)
                .then(()=>console.log('Copied to clipboard'))
                .catch(()=>console.warn('Clipboard write failed. Copy manually.'));
        }
    };

    // --- Save actions before page unload/navigation ---
    window.addEventListener('beforeunload', () => {
        if (window.__actions && window.__actions.length) {
            chrome.storage.local.set({ recordedActions: window.__actions });
            console.log('Actions saved before page unload.');
        }
    });

    // --- Detect SPA navigation ---
    let lastUrl = location.href;
    setInterval(async () => {
        if (location.href !== lastUrl) {
            lastUrl = location.href;
            console.log('Page changed, continuing recording...');
            await loadActions();
            if (window.__recorderActive) {
                stopRecorder();
                startRecorder();
            }
        }
    }, 500);

    // --- Dynamic DOM changes ---
    const observer = new MutationObserver(async () => {
        if (window.__recorderActive) {
            stopRecorder();
            await loadActions();
            startRecorder();
        }
    });
    observer.observe(document.body, { childList: true, subtree: true });

    // --- Intercept links opening in new tab ---
    document.addEventListener('click', function(e){
        const a = e.target.closest('a');
        if(a && a.target === '_blank'){
            e.preventDefault();
            window.location.href = a.href;
        }
    }, true);

    // --- Auto-start recording ---
    window.addEventListener('load', () => {
        if (!window.__recorderActive) startRecorder();
    });

    console.log('Recorder script loaded. Use startRecorder(), stopRecorder(), exportRecorder().');
}
