const form = document.getElementById('resetForm');
const errorBox = document.getElementById('error');
const successBox = document.getElementById('success');
const submitBtn = document.getElementById('submitBtn');
const passwordInput = document.getElementById('password');
const strengthBar = passwordInput.parentElement.parentElement.querySelector('.strength-bar');

const urlParams = new URLSearchParams(window.location.search);
const token = urlParams.get('token');

if (!token) {
  showError('Invalid or missing reset token. Please request a new password reset link.');
  form.style.display = 'none';
}

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

function checkPasswordStrength(password) {
  let strength = 0;
  if (password.length >= 8) strength++;
  if (password.length >= 12) strength++;
  if (/[a-z]/.test(password) && /[A-Z]/.test(password)) strength++;
  if (/\d/.test(password)) strength++;
  if (/[^a-zA-Z0-9]/.test(password)) strength++;

  const label = document.getElementById('strengthLabel');
  if (strength <= 2) {
    strengthBar.className = 'strength-bar strength-weak';
    label.textContent = 'Weak';
    label.style.color = '#ef4444';
  } else if (strength <= 4) {
    strengthBar.className = 'strength-bar strength-medium';
    label.textContent = 'Medium';
    label.style.color = '#f59e0b';
  } else {
    strengthBar.className = 'strength-bar strength-strong';
    label.textContent = 'Strong';
    label.style.color = '#10b981';
  }
}

passwordInput.addEventListener('input', (e) => {
  checkPasswordStrength(e.target.value);
});

form.addEventListener('submit', async (e)=>{
  e.preventDefault();
  clearMessages();
  
  const password = document.getElementById('password').value;
  const confirmPassword = document.getElementById('confirmPassword').value;

  if (password !== confirmPassword) {
    showError('Passwords do not match.');
    return;
  }

  if (password.length < 8) {
    showError('Password must be at least 8 characters long.');
    return;
  }

  submitBtn.disabled = true;
  submitBtn.textContent = 'Resetting...';

  try {
    const res = await fetch('/api/auth/password-reset/confirm/', {
      method: 'POST',
      headers: { 'Content-Type':'application/json' },
      body: JSON.stringify({ 
        token: token,
        new_password: password,
        confirm_password: confirmPassword
      })
    });
    
    const data = await res.json();
    
    if (!res.ok) {
      throw new Error(data.error || data.detail || 'Failed to reset password');
    }
    
    showSuccess(data.message);
    form.reset();
    
    setTimeout(() => {
      window.location.href = '/';
    }, 2000);
    
  } catch(err){
    showError(err.message);
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = 'Reset Password';
  }
});
