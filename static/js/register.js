const form = document.getElementById('registerForm');
const errorBox = document.getElementById('error');
const successBox = document.getElementById('success');

function togglePassword(id) {
  const input = document.getElementById(id);
  input.type = input.type === 'password' ? 'text' : 'password';
}

function showError(msg){
  errorBox.style.display = 'block';
  errorBox.textContent = msg;
  successBox.style.display = 'none';
}

function showSuccess(msg){
  successBox.style.display = 'block';
  successBox.textContent = msg;
  errorBox.style.display = 'none';
}

function clearMessages(){
  errorBox.style.display = 'none';
  successBox.style.display = 'none';
}

(function redirectIfAuthed(){
  const token = localStorage.getItem('access') || sessionStorage.getItem('access');
  if (token) {
    window.location.href = '/dashboard/';
  }
})();

form.addEventListener('submit', async (e)=>{
  e.preventDefault();
  clearMessages();
  
  const name = document.getElementById('name').value.trim();
  const email = document.getElementById('email').value.trim();
  const password = document.getElementById('password').value;
  const password_confirm = document.getElementById('password_confirm').value;
  const role = document.getElementById('role').value;

  if (password !== password_confirm) {
    showError('Passwords do not match');
    return;
  }

  if (password.length < 8) {
    showError('Password must be at least 8 characters');
    return;
  }

  try {
    const res = await fetch('/api/auth/register/', {
      method: 'POST',
      headers: { 'Content-Type':'application/json' },
      body: JSON.stringify({ name, email, password, password_confirm, role })
    });
    
    const data = await res.json();
    
    if (!res.ok) {
      if (data.email) {
        throw new Error(data.email[0]);
      } else if (data.password) {
        throw new Error(data.password[0]);
      } else {
        throw new Error(data.detail || 'Registration failed');
      }
    }
    
    showSuccess('Registration successful! Redirecting to login...');
    form.reset();
    setTimeout(() => {
      window.location.href = '/';
    }, 2000);
  } catch(err){
    showError(err.message);
  }
});
