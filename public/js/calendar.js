const getDisplayName = (email) => {
    if (!email) return 'User';
    return email.split('@')[0];
};

const renderUserNav = (email) => {
    const nav = document.querySelector('.navlinks');
    if (!nav) return;

    const displayName = getDisplayName(email);
    nav.innerHTML = `
        <li><a href="/index.html">Home</a></li>
        <li><a href="#">About Us</a></li>
        <li><span class="welcome-user">Welcome ${displayName}</span></li>
        <li><button type="button" id="logout-btn" class="logout-btn">Logout</button></li>
    `;

    const logoutButton = document.getElementById('logout-btn');
    if (!logoutButton) return;

    logoutButton.addEventListener('click', async () => {
        await fetch('/api/logout', { method: 'POST' });
        window.location.href = '/login.html';
    });
};

const requireSession = async () => {
    const meResponse = await fetch('/api/me');
    if (!meResponse.ok) {
        window.location.href = '/login.html';
        return null;
    }

    const me = await meResponse.json();
    renderUserNav(me.user?.email);
    return me.user;
};

async function loadCalendar() {
    const container = document.getElementById('appointment-list');
    const user = await requireSession();
    if (!user) return;

    const response = await fetch('/api/appointments');
    if (response.status === 401) {
        window.location.href = '/login.html';
        return;
    }

    if (!response.ok) {
        container.innerHTML = '<p>Unable to load appointments right now.</p>';
        return;
    }

    const appointments = await response.json();

    container.innerHTML = '';

    appointments.forEach(app => {
        const div = document.createElement('div');

        div.style = "background: white; border: 1px solid #ddd; padding: 15px; margin-bottom: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); border-left: 5px solid blue; color: #222;";

        div.innerHTML = `
            <strong style="font-size: 1.2em;">${app.name}</strong>
            <div style="margin-top: 8px;">
                <strong>Date:</strong> ${app.booking_date} (${app.booking_day})
                <br><strong>Time:</strong> <span style="color: blue;">${app.booking_time}</span>
                <br><small style="color: #666;">Phone: ${app.phone_number}</small>
            </div>
        `;
        container.appendChild(div);
    });
}

loadCalendar();