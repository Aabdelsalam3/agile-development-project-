let appointmentsData = [];
let currentDate = new Date(); // Context: May 2026 based on prompt, but dynamic
let selectedDate = new Date();

const renderUserNav = (email) => {
    const nav = document.getElementById('user-nav');
    if (!nav) return;
    nav.innerHTML = `<button type="button" id="logout-btn" class="logout-btn">Logout</button>`;
    
    document.getElementById('logout-btn').addEventListener('click', async () => {
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

// Map raw data into an object grouped by Date String (YYYY-MM-DD)
const processAppointments = (rawData) => {
    const map = {};
    rawData.forEach(app => {
        // Assuming booking_date is format 'YYYY-MM-DD' or similar parsable string
        // If your DB has varying formats, this ensures we map it to standard ISO date keys
        const d = new Date(app.booking_date);
        if(isNaN(d)) return; // skip invalid dates
        
        const dateStr = d.toISOString().split('T')[0];
        if (!map[dateStr]) map[dateStr] = [];
        map[dateStr].push(app);
    });
    return map;
};

const updateStats = (groupedData, currentSelectedDateStr) => {
    document.getElementById('total-bookings').innerText = appointmentsData.length;
    document.getElementById('booked-days').innerText = Object.keys(groupedData).length;
    
    const selectedCount = groupedData[currentSelectedDateStr] ? groupedData[currentSelectedDateStr].length : 0;
    document.getElementById('selected-day-bookings').innerText = selectedCount;
};

const renderCalendar = (groupedData) => {
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();
    
    // Update Header
    const monthNames = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
    document.getElementById('current-month-year').innerText = `${monthNames[month]} ${year}`;
    
    const daysContainer = document.getElementById('calendar-days');
    daysContainer.innerHTML = '';
    
    const firstDay = new Date(year, month, 1).getDay();
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    
    // Pad empty days at start
    for (let i = 0; i < firstDay; i++) {
        const emptyDiv = document.createElement('div');
        emptyDiv.className = 'calendar-day empty';
        daysContainer.appendChild(emptyDiv);
    }
    
    const selectedDateStr = selectedDate.toISOString().split('T')[0];

    // Create days
    for (let day = 1; day <= daysInMonth; day++) {
        const d = new Date(year, month, day);
        // Correct for timezone offset when generating key
        const localDateStr = new Date(d.getTime() - (d.getTimezoneOffset() * 60000)).toISOString().split('T')[0];
        
        const dayDiv = document.createElement('div');
        dayDiv.className = `calendar-day ${localDateStr === selectedDateStr ? 'selected' : ''}`;
        
        let innerHTML = `<span class="day-number">${day}</span>`;
        
        if (groupedData[localDateStr]) {
            const count = groupedData[localDateStr].length;
            innerHTML += `<span class="booking-badge">${count} booking${count > 1 ? 's' : ''}</span>`;
        }
        
        dayDiv.innerHTML = innerHTML;
        
        dayDiv.addEventListener('click', () => {
            selectedDate = new Date(year, month, day);
            renderCalendar(groupedData); // Re-render to update selected border
            renderDetailPanel(groupedData, localDateStr);
            updateStats(groupedData, localDateStr);
        });
        
        daysContainer.appendChild(dayDiv);
    }
};

const renderDetailPanel = (groupedData, dateStr) => {
    const detailTitle = document.getElementById('detail-date-title');
    const detailCount = document.getElementById('detail-count');
    const listContainer = document.getElementById('appointment-list');
    
    // Format date nicely (e.g. Wednesday, May 06, 2026)
    const options = { weekday: 'long', year: 'numeric', month: 'long', day: '2-digit' };
    const dateObj = new Date(dateStr + "T00:00:00"); // Force local by appending time
    detailTitle.innerText = dateObj.toLocaleDateString(undefined, options);
    
    const dayAppointments = groupedData[dateStr] || [];
    detailCount.innerText = `${dayAppointments.length} booking${dayAppointments.length !== 1 ? 's' : ''}`;
    
    if (dayAppointments.length === 0) {
        listContainer.innerHTML = `<div class="empty-state">No bookings for this day.</div>`;
        return;
    }
    
    listContainer.innerHTML = '';
    dayAppointments.forEach(app => {
        const item = document.createElement('div');
        item.className = 'appointment-item';
        item.innerHTML = `
            <h4>${app.name}</h4>
            <div class="appointment-details">
                <span class="appointment-time"><i class="fa-regular fa-clock"></i> ${app.booking_time}</span>
                <span><i class="fa-solid fa-phone"></i> ${app.phone_number}</span>
            </div>
        `;
        listContainer.appendChild(item);
    });
};

const setupControls = (groupedData) => {
    document.getElementById('prev-month').addEventListener('click', () => {
        currentDate.setMonth(currentDate.getMonth() - 1);
        renderCalendar(groupedData);
    });
    
    document.getElementById('next-month').addEventListener('click', () => {
        currentDate.setMonth(currentDate.getMonth() + 1);
        renderCalendar(groupedData);
    });
    
    document.getElementById('today-btn').addEventListener('click', () => {
        currentDate = new Date();
        selectedDate = new Date();
        const localSelected = new Date(selectedDate.getTime() - (selectedDate.getTimezoneOffset() * 60000)).toISOString().split('T')[0];
        renderCalendar(groupedData);
        renderDetailPanel(groupedData, localSelected);
        updateStats(groupedData, localSelected);
    });
};

async function initDashboard() {
    const user = await requireSession();
    if (!user) return;

    const response = await fetch('/api/appointments');
    if (response.status === 401) {
        window.location.href = '/login.html';
        return;
    }

    if (!response.ok) {
        document.getElementById('appointment-list').innerHTML = '<div class="empty-state">Failed to load API.</div>';
        return;
    }

    appointmentsData = await response.json();
    const groupedData = processAppointments(appointmentsData);
    
    // Set initial selected date key
    const initialSelectedStr = new Date(selectedDate.getTime() - (selectedDate.getTimezoneOffset() * 60000)).toISOString().split('T')[0];

    setupControls(groupedData);
    renderCalendar(groupedData);
    renderDetailPanel(groupedData, initialSelectedStr);
    updateStats(groupedData, initialSelectedStr);
}

initDashboard();