// show toast messages from server-flash or fetch responses
function showToast(msg, ms = 2500) {
  const t = document.getElementById('toast');
  if (!t) return;
  t.textContent = msg;
  t.classList.remove('hidden');
  setTimeout(() => { t.classList.add('hidden'); }, ms);
}

// Attach add-to-cart forms to submit via fetch so we can show toast immediately
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.add-form').forEach(form => {
    form.addEventListener('submit', async (ev) => {
      ev.preventDefault();
      const pid = form.dataset.pid;
      try {
        const resp = await fetch(form.action, {
          method: 'POST',
          headers: {'Content-Type':'application/json','X-Requested-With':'XMLHttpRequest'},
          body: JSON.stringify({})
        });
        const j = await resp.json();
        if (j.ok) {
          showToast(j.msg || 'Added to cart');
          setTimeout(()=> location.reload(), 600);
        } else {
          showToast('Add failed');
        }
      } catch (e) {
        showToast('Add failed');
      }
    })
  });

  const co = document.getElementById('checkoutForm');
  if (co) {
    co.addEventListener('submit', async (ev) => {
      ev.preventDefault();
      try {
        const resp = await fetch(co.action, {
          method: 'POST',
          headers: {'Content-Type':'application/json','X-Requested-With':'XMLHttpRequest'},
          body: JSON.stringify({})
        });
        const j = await resp.json();
        if (j.ok) {
          showToast(j.msg || 'Payment done');
          setTimeout(()=> location.href = '/', 900);
        } else showToast('Payment failed');
      } catch (e) {
        showToast('Payment failed');
      }
    });
  }

  setTimeout(() => {
    document.querySelectorAll('.msg').forEach(el => {
      showToast(el.textContent || el.innerText, 2500);
    });
  }, 200);
});