let appointmentsData = [];
let currentDate = new Date(); 
let selectedDate = new Date();

// --- Auth & Setup ---
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

// --- Data Processing ---
const processAppointments = (rawData) => {
    const map = {};
    rawData.forEach(app => {
        const d = new Date(app.booking_date);
        if(isNaN(d)) return;
        
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

// --- UI Rendering ---
const renderCalendar = (groupedData) => {
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();
    
    const monthNames = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
    document.getElementById('current-month-year').innerText = `${monthNames[month]} ${year}`;
    
    const daysContainer = document.getElementById('calendar-days');
    daysContainer.innerHTML = '';
    
    const firstDay = new Date(year, month, 1).getDay();
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    
    for (let i = 0; i < firstDay; i++) {
        const emptyDiv = document.createElement('div');
        emptyDiv.className = 'calendar-day empty';
        daysContainer.appendChild(emptyDiv);
    }
    
    const selectedDateStr = new Date(selectedDate.getTime() - (selectedDate.getTimezoneOffset() * 60000)).toISOString().split('T')[0];

    for (let day = 1; day <= daysInMonth; day++) {
        const d = new Date(year, month, day);
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
            renderCalendar(groupedData);
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
    
    const options = { weekday: 'long', year: 'numeric', month: 'long', day: '2-digit' };
    const dateObj = new Date(dateStr + "T00:00:00"); 
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
            <div class="appointment-actions">
                <button class="action-btn edit" onclick="openModalForEdit(${app.id})"><i class="fa-solid fa-pen"></i></button>
                <button class="action-btn delete" onclick="deleteAppointment(${app.id})"><i class="fa-solid fa-trash"></i></button>
            </div>
        `;
        listContainer.appendChild(item);
    });
};

// --- CRUD Operations ---

// Fetch data from DB and refresh UI
const loadAndRenderData = async () => {
    const response = await fetch('/api/appointments');
    if (!response.ok) return;
    
    appointmentsData = await response.json();
    const groupedData = processAppointments(appointmentsData);
    const selectedDateStr = new Date(selectedDate.getTime() - (selectedDate.getTimezoneOffset() * 60000)).toISOString().split('T')[0];
    
    renderCalendar(groupedData);
    renderDetailPanel(groupedData, selectedDateStr);
    updateStats(groupedData, selectedDateStr);
};

// Delete Appointment
window.deleteAppointment = async (id) => {
    if(!confirm("Are you sure you want to delete this appointment?")) return;
    
    await fetch(`/api/appointments/${id}`, { method: 'DELETE' });
    loadAndRenderData(); // Refresh UI
};

// --- Modal Logic ---
const modal = document.getElementById('appointment-modal');
const form = document.getElementById('appointment-form');

const openModal = () => {
    modal.classList.remove('hidden');
};

const closeModal = () => {
    modal.classList.add('hidden');
    form.reset();
    document.getElementById('app-id').value = '';
};

// Setup Add New
document.getElementById('add-btn').addEventListener('click', () => {
    document.getElementById('modal-title').innerText = "Add New Appointment";
    // Pre-fill the date picker with the currently selected date
    const selectedDateStr = new Date(selectedDate.getTime() - (selectedDate.getTimezoneOffset() * 60000)).toISOString().split('T')[0];
    document.getElementById('app-date').value = selectedDateStr;
    openModal();
});

// Setup Edit
window.openModalForEdit = (id) => {
    const app = appointmentsData.find(a => a.id === id);
    if (!app) return;
    
    document.getElementById('modal-title').innerText = "Edit Appointment";
    document.getElementById('app-id').value = app.id;
    document.getElementById('app-name').value = app.name;
    document.getElementById('app-date').value = app.booking_date;
    document.getElementById('app-time').value = app.booking_time;
    document.getElementById('app-phone').value = app.phone_number;
    
    openModal();
};

document.getElementById('close-modal').addEventListener('click', closeModal);

// Handle Form Submit (Create or Update)
form.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const id = document.getElementById('app-id').value;
    const isEditing = !!id;
    
    const dateVal = document.getElementById('app-date').value;
    const dateObj = new Date(dateVal + "T00:00:00");
    const dayName = dateObj.toLocaleDateString(undefined, { weekday: 'long' });

    const payload = {
        name: document.getElementById('app-name').value,
        booking_date: dateVal,
        booking_day: dayName,
        booking_time: document.getElementById('app-time').value,
        phone_number: document.getElementById('app-phone').value
    };

    const url = isEditing ? `/api/appointments/${id}` : '/api/appointments';
    const method = isEditing ? 'PUT' : 'POST';

    await fetch(url, {
        method: method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });

    closeModal();
    loadAndRenderData(); // Refresh UI
});

// --- Initialization ---
const setupControls = () => {
    document.getElementById('prev-month').addEventListener('click', () => {
        currentDate.setMonth(currentDate.getMonth() - 1);
        loadAndRenderData();
    });
    
    document.getElementById('next-month').addEventListener('click', () => {
        currentDate.setMonth(currentDate.getMonth() + 1);
        loadAndRenderData();
    });
    
    document.getElementById('today-btn').addEventListener('click', () => {
        currentDate = new Date();
        selectedDate = new Date();
        loadAndRenderData();
    });
};

async function initDashboard() {
    const user = await requireSession();
    if (!user) return;
    setupControls();
    loadAndRenderData();
}

initDashboard();