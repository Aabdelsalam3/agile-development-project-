const express = require("express");
const sqlite3 = require("sqlite3").verbose();
const path = require("path");
const crypto = require("crypto");

const app = express();
const port = 3000;
const sessions = new Map();
const SESSION_COOKIE_NAME = "sid";
const SESSION_TTL_MS = 1000 * 60 * 60 * 8;

const db = new sqlite3.Database("./appointments.db", (err) => {
    if (err) return console.error(err.message);
    console.log("Connected to appointments.db");
});

const hashPassword = (password, salt) => {
    return crypto.scryptSync(password, salt, 64).toString("hex");
};

const parseCookies = (cookieHeader = "") => {
    return cookieHeader
        .split(";")
        .map((part) => part.trim())
        .filter(Boolean)
        .reduce((cookies, pair) => {
            const separatorIndex = pair.indexOf("=");
            if (separatorIndex === -1) return cookies;
            const key = pair.slice(0, separatorIndex);
            const value = pair.slice(separatorIndex + 1);
            cookies[key] = decodeURIComponent(value);
            return cookies;
        }, {});
};

const createSession = (user) => {
    const sessionId = crypto.randomUUID();
    sessions.set(sessionId, {
        user,
        expiresAt: Date.now() + SESSION_TTL_MS
    });
    return sessionId;
};

const getSession = (req) => {
    const cookies = parseCookies(req.headers.cookie);
    const sessionId = cookies[SESSION_COOKIE_NAME];
    if (!sessionId) return null;

    const session = sessions.get(sessionId);
    if (!session) return null;
    if (session.expiresAt < Date.now()) {
        sessions.delete(sessionId);
        return null;
    }

    return { sessionId, session };
};

const requireAuth = (req, res, next) => {
    const auth = getSession(req);
    if (!auth) {
        res.status(401).json({ error: "Authentication required" });
        return;
    }

    req.user = auth.session.user;
    req.sessionId = auth.sessionId;
    next();
};

db.serialize(() => {
    db.run(`
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            password_salt TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    `);

    db.run(`
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            booking_date TEXT NOT NULL,
            booking_day TEXT NOT NULL,
            booking_time TEXT NOT NULL,
            phone_number TEXT NOT NULL
        )
    `);

    const demoEmail = "nick@gmail.com";
    const demoPassword = "money";

    db.get("SELECT id FROM users WHERE lower(email) = lower(?)", [demoEmail], (err, row) => {
        if (err) return;
        const salt = crypto.randomBytes(16).toString("hex");
        const hash = hashPassword(demoPassword, salt);

        if (!row) {
            db.run("INSERT INTO users (email, password_hash, password_salt) VALUES (?, ?, ?)", [demoEmail, hash, salt]);
        } else {
            db.run("UPDATE users SET password_hash = ?, password_salt = ? WHERE id = ?", [hash, salt, row.id]);
        }
    });
});

app.use(express.json());
app.use(express.urlencoded({ extended: false }));
app.use(express.static("public"));

app.get(["/login", "/login.html"], (req, res) => {
    res.sendFile(path.join(__dirname, "public", "login.html"));
});

app.get(["/", "/index.html"], (req, res) => {
    res.sendFile(path.join(__dirname, "public", "index.html"));
});

// --- AUTHENTICATION ROUTES ---
app.post("/api/login", (req, res) => {
    const email = (req.body.email || "").trim();
    const password = req.body.password || "";

    if (!email || !password) return res.status(400).json({ error: "Email and password are required" });

    db.get("SELECT id, email, password_hash, password_salt FROM users WHERE lower(email) = lower(?)", [email], (err, user) => {
        if (err) return res.status(500).json({ error: err.message });
        if (!user) return res.status(401).json({ error: "Invalid email or password" });

        const candidateHash = hashPassword(password, user.password_salt);
        const passwordMatches = crypto.timingSafeEqual(Buffer.from(candidateHash, "hex"), Buffer.from(user.password_hash, "hex"));

        if (!passwordMatches) return res.status(401).json({ error: "Invalid email or password" });

        const sessionId = createSession({ id: user.id, email: user.email });
        res.setHeader("Set-Cookie", `${SESSION_COOKIE_NAME}=${encodeURIComponent(sessionId)}; HttpOnly; Path=/; SameSite=Lax`);
        res.json({ message: "Login successful", user: { id: user.id, email: user.email } });
    });
});

app.get("/api/me", (req, res) => {
    const auth = getSession(req);
    if (!auth) return res.status(401).json({ error: "Not logged in" });
    res.json({ user: auth.session.user });
});

app.post("/api/logout", (req, res) => {
    const auth = getSession(req);
    if (auth) sessions.delete(auth.sessionId);
    res.setHeader("Set-Cookie", `${SESSION_COOKIE_NAME}=; HttpOnly; Path=/; Max-Age=0; SameSite=Lax`);
    res.json({ message: "Logged out" });
});

// --- CRUD APPOINTMENT ROUTES ---

// READ All
app.get("/api/appointments", requireAuth, (req, res) => {
    db.all("SELECT * FROM appointments", [], (err, rows) => {
        if (err) return res.status(500).json({ error: err.message });
        res.json(rows);
    });
});

// CREATE
app.post("/api/appointments", requireAuth, (req, res) => {
    const { name, booking_date, booking_day, booking_time, phone_number } = req.body;
    
    if (!name || !booking_date || !booking_time) {
        return res.status(400).json({ error: "Missing required fields" });
    }

    // Generate a current timestamp ex 2026-05-11 17:38:47
    const created_at = new Date().toISOString().replace('T', ' ').split('.')[0];

    // Added created_at to the SQL statement and the variables array
    const sql = `INSERT INTO appointments (name, booking_date, booking_day, booking_time, phone_number, created_at) VALUES (?, ?, ?, ?, ?, ?)`;
    
    db.run(sql, [name, booking_date, booking_day || "Unknown", booking_time, phone_number || "", created_at], function(err) {
        if (err) {
            console.error("\n🔥 DATABASE CRASH REASON:", err.message, "\n"); 
            return res.status(500).json({ error: err.message });
        }
        res.json({ id: this.lastID, message: "Appointment created successfully" });
    });
});

// UPDATE
app.put("/api/appointments/:id", requireAuth, (req, res) => {
    const { name, booking_date, booking_day, booking_time, phone_number } = req.body;
    const sql = `UPDATE appointments SET name = ?, booking_date = ?, booking_day = ?, booking_time = ?, phone_number = ? WHERE id = ?`;
    
    db.run(sql, [name, booking_date, booking_day || "Unknown", booking_time, phone_number || "", req.params.id], function(err) {
        if (err) return res.status(500).json({ error: err.message });
        res.json({ message: "Appointment updated successfully" });
    });
});

// DELETE
app.delete("/api/appointments/:id", requireAuth, (req, res) => {
    const sql = `DELETE FROM appointments WHERE id = ?`
    db.run(sql, [req.params.id], function(err) {
        if (err) return res.status(500).json({ error: err.message });
        res.json({ message: "Appointment deleted successfully" });
    });
});

app.listen(port, () => {
    console.log(`Server running at http://localhost:${port}`);
});