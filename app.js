const express = require("express");
const sqlite3 = require("sqlite3").verbose();
const path = require("path");

const app = express();
const port = 3000;

const db = new sqlite3.Database("./appointments.db", (err) => {
    if (err) return console.error(err.message);
    console.log("Connected to appointments.db");
});


app.use(express.static("public"));


app.get("/api/appointments", (req, res) => {
    const sql = "SELECT * FROM appointments";
    db.all(sql, [], (err, rows) => {
        if (err) {
            res.status(500).json({ error: err.message });
            return;
        }
        res.json(rows);
    });
});

app.listen(port, () => {
    console.log(`Server running at http://localhost:${port}`);
});