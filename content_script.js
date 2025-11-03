// content_script.js - records click, input, and SPA navigation
if (window.__tinyRecorderInstalled) {} else {
  window.__tinyRecorderInstalled = true;
  window.__tinyRecorder = {
    active:false,
    actions:[],
    start(){ this.active=true; },
    stop(){ this.active=false; },
    clear(){ this.actions=[]; },
    exportJSON(){ return JSON.stringify(this.actions, null, 2); }
  };

  function sel(el){
    if(!el) return null;
    if(el.id) return "#"+el.id;
    if(el===document.body) return "body";
    let path=[], c=el;
    while(c && c.nodeType===1 && c!==document.body){
      let tag = c.tagName.toLowerCase(), nth=1, s=c.previousElementSibling;
      while(s){ if(s.tagName===c.tagName) nth++; s=s.previousElementSibling; }
      path.unshift(tag + ":nth-of-type(" + nth + ")");
      c = c.parentElement;
    }
    return path.join(" > ");
  }

  document.addEventListener('click', e=>{
    try{
      if(!window.__tinyRecorder.active) return;
      const s = sel(e.target);
      window.__tinyRecorder.actions.push({type:'click', selector: s, timestamp: Date.now()});
    }catch(e){}
  }, true);

  document.addEventListener('input', e=>{
    try{
      if(!window.__tinyRecorder.active) return;
      const s = sel(e.target);
      window.__tinyRecorder.actions.push({type:'fill', selector: s, value: e.target.value, timestamp: Date.now()});
    }catch(e){}
  }, true);

  (function(){
    const origPush = history.pushState, origReplace = history.replaceState;
    history.pushState = function(){ origPush.apply(this, arguments); window.dispatchEvent(new Event('locationchange')); };
    history.replaceState = function(){ origReplace.apply(this, arguments); window.dispatchEvent(new Event('locationchange')); };
    window.addEventListener('popstate', ()=> window.dispatchEvent(new Event('locationchange')));
    window.addEventListener('locationchange', ()=> {
      if(window.__tinyRecorder.active) {
        window.__tinyRecorder.actions.push({type:'goto', url: location.href, timestamp: Date.now()});
      }
    });
  })();

  chrome.runtime.onMessage.addListener((msg, sender, sendResponse)=>{
    if(!msg || !msg.cmd) return;
    if(msg.cmd === 'START') { window.__tinyRecorder.start(); sendResponse({ok:true}); }
    if(msg.cmd === 'STOP')  { window.__tinyRecorder.stop(); sendResponse({ok:true}); }
    if(msg.cmd === 'CLEAR') { window.__tinyRecorder.clear(); sendResponse({ok:true}); }
    if(msg.cmd === 'EXPORT') { sendResponse({ok:true, json: window.__tinyRecorder.exportJSON()}); }
    if(msg.cmd === 'GET_ALL') { sendResponse({ok:true, actions: window.__tinyRecorder.actions}); }
    return true;
  });
}

