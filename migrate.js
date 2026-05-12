const sqlite3 = require("sqlite3").verbose();

const db = new sqlite3.Database("./appointments.db", (err) => {
    if (err) return console.error("Could not connect to DB:", err.message);
    console.log("Connected to your existing appointments.db");
});

db.serialize(() => {
    console.log("Upgrading database...");

    db.run("ALTER TABLE appointments ADD COLUMN booking_day TEXT DEFAULT 'Unknown'", (err) => {
        if (err) {
            console.log("Column 'booking_day' likely already exists, skipping...");
        } else {
            console.log("✅ Added 'booking_day' column.");
        }
    });


    db.run("ALTER TABLE appointments ADD COLUMN phone_number TEXT DEFAULT ''", (err) => {
        if (err) {
            console.log("Column 'phone_number' likely already exists, skipping...");
        } else {
            console.log("✅ Added 'phone_number' column.");
        }
    });
});

setTimeout(() => {
    db.close((err) => {
        if (err) return console.error(err.message);
        console.log("🎉 Migration complete! Your old data is safe.");
        console.log("You can safely delete this migrate.js file now.");
    });
}, 1000);
