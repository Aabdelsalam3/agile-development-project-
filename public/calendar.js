async function loadCalendar() {
    const container = document.getElementById('calendar');
    
    try {
        
        const response = await fetch('/api/appointments');
        const appointments = await response.json();

        appointments.forEach(app => {
            const div = document.createElement('div');
            div.className = 'day-cell';
            div.innerHTML = `
                <strong>${app.booking_date}</strong>
                <div class="appointment-tag">
                    ${app.booking_time} - ${app.name} 
                    <br><small>${app.phone_number}</small>
                </div>
            `;
            container.appendChild(div);
        });

    } catch (error) {
        console.error("Error loading appointments:", error);
    }
}

loadCalendar();