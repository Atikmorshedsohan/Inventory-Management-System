const form = document.getElementById('forgotForm');
const errorBox = document.getElementById('error');
const successBox = document.getElementById('success');
const submitBtn = document.getElementById('submitBtn');

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

form.addEventListener('submit', async (e)=>{
  e.preventDefault();
  clearMessages();
  
  const email = document.getElementById('email').value.trim();
  submitBtn.disabled = true;
  submitBtn.textContent = 'Sending...';

  try {
    const res = await fetch('/api/auth/password-reset/', {
      method: 'POST',
      headers: { 'Content-Type':'application/json' },
      body: JSON.stringify({ email })
    });
    
    const data = await res.json();
    
    if (!res.ok) {
      throw new Error(data.email?.[0] || data.error || 'Failed to send reset link');
    }
    
    showSuccess(data.message + ' Please check your email inbox (and spam folder) for the reset link.');
    form.reset();
    
  } catch(err){
    showError(err.message);
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = 'Send Reset Link';
  }
});
