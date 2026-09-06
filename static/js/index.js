const form = document.getElementById('loginForm');
const errorBox = document.getElementById('error');

function togglePassword(id) {
  const input = document.getElementById(id);
  input.type = input.type === 'password' ? 'text' : 'password';
}

function showError(msg){
  errorBox.style.display = 'block';
  errorBox.textContent = msg;
}

function clearError(){
  errorBox.style.display = 'none';
  errorBox.textContent = '';
}

(function redirectIfAuthed(){
  const token = localStorage.getItem('access') || sessionStorage.getItem('access');
  if (token) {
    window.location.href = '/dashboard/';
  }
})();

form.addEventListener('submit', async (e)=>{
  e.preventDefault();
  clearError();
  const email = document.getElementById('email').value.trim();
  const password = document.getElementById('password').value;
  const remember = document.getElementById('remember').checked;
  try {
    const res = await fetch('/api/auth/token/', {
      method: 'POST',
      headers: { 'Content-Type':'application/json' },
      body: JSON.stringify({ email, password })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Invalid credentials');
    if (remember) {
      localStorage.setItem('access', data.access);
      localStorage.setItem('refresh', data.refresh);
    } else {
      sessionStorage.setItem('access', data.access);
      sessionStorage.setItem('refresh', data.refresh);
    }
    window.location.href = '/dashboard/';
  } catch(err){
    showError(err.message);
  }
});
