const form = document.getElementById('login-form');
const messageEl = document.getElementById('login-message');

const setMessage = (text, isError = false) => {
    if (!messageEl) return;
    messageEl.textContent = text;
    messageEl.style.color = isError ? '#c62828' : '#2e7d32';
};

const redirectToHome = () => {
    window.location.href = '/index.html';
};

const checkExistingSession = async () => {
    try {
        const response = await fetch('/api/me');
        if (response.ok) {
            redirectToHome();
        }
    } catch (error) {
        
    }
};

const handleLoginSubmit = async (event) => {
    event.preventDefault();

    const email = document.getElementById('email')?.value?.trim() || '';
    const password = document.getElementById('password')?.value || '';

    if (!email || !password) {
        setMessage('Please enter both email and password.', true);
        return;
    }

    setMessage('Signing in...');

    try {
        const response = await fetch('/api/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ email, password })
        });

        const payload = await response.json();

        if (!response.ok) {
            setMessage(payload.error || 'Login failed. Please try again.', true);
            return;
        }

        setMessage('Login successful. Redirecting...');
        redirectToHome();
    } catch (error) {
        setMessage('Unable to reach server. Please try again.', true);
    }
};

if (form) {
    form.addEventListener('submit', handleLoginSubmit);
    checkExistingSession();
}
