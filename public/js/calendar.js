async function loadCalendar() {
    
    const container = document.getElementById('appointment-list');
    
    if (!container) {
        console.error("Could not find the 'appointment-list' container in the HTML.");
        return;
    }

    try {
        const response = await fetch('/api/appointments');
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

    } catch (error) {
        console.error("Error loading appointments:", error);
        container.innerHTML = "<p style='color: red;'>Failed to load data from the database.</p>";
    }
}

loadCalendar();