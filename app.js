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

    const demoEmail = "nick@gmail.com";
    const demoPassword = "money";

    db.get("SELECT id FROM users WHERE lower(email) = lower(?)", [demoEmail], (err, row) => {
        if (err) {
            console.error("Failed to check demo user:", err.message);
            return;
        }

        const salt = crypto.randomBytes(16).toString("hex");
        const hash = hashPassword(demoPassword, salt);

        if (!row) {
            db.run(
                "INSERT INTO users (email, password_hash, password_salt) VALUES (?, ?, ?)",
                [demoEmail, hash, salt],
                (insertErr) => {
                    if (insertErr) {
                        console.error("Failed to create demo user:", insertErr.message);
                        return;
                    }
                    console.log("Demo login user created: nick@gmail.com / money");
                }
            );
            return;
        }

        db.run(
            "UPDATE users SET password_hash = ?, password_salt = ? WHERE id = ?",
            [hash, salt, row.id],
            (updateErr) => {
                if (updateErr) {
                    console.error("Failed to update demo user password:", updateErr.message);
                    return;
                }
                console.log("Demo login user updated: nick@gmail.com / money");
            }
        );
    });
});

app.use(express.json());
app.use(express.urlencoded({ extended: false }));

app.use(express.static("public"));

app.get(["/login", "/login.html"], (req, res) => {
    res.sendFile(path.join(__dirname, "login.html"));
});

app.post("/api/login", (req, res) => {
    const email = (req.body.email || "").trim();
    const password = req.body.password || "";

    if (!email || !password) {
        res.status(400).json({ error: "Email and password are required" });
        return;
    }

    db.get(
        "SELECT id, email, password_hash, password_salt FROM users WHERE lower(email) = lower(?)",
        [email],
        (err, user) => {
            if (err) {
                res.status(500).json({ error: err.message });
                return;
            }

            if (!user) {
                res.status(401).json({ error: "Invalid email or password" });
                return;
            }

            const candidateHash = hashPassword(password, user.password_salt);
            const passwordMatches = crypto.timingSafeEqual(
                Buffer.from(candidateHash, "hex"),
                Buffer.from(user.password_hash, "hex")
            );

            if (!passwordMatches) {
                res.status(401).json({ error: "Invalid email or password" });
                return;
            }

            const sessionId = createSession({ id: user.id, email: user.email });
            res.setHeader(
                "Set-Cookie",
                `${SESSION_COOKIE_NAME}=${encodeURIComponent(sessionId)}; HttpOnly; Path=/; SameSite=Lax`
            );

            res.json({ message: "Login successful", user: { id: user.id, email: user.email } });
        }
    );
});

app.get("/api/me", (req, res) => {
    const auth = getSession(req);
    if (!auth) {
        res.status(401).json({ error: "Not logged in" });
        return;
    }

    res.json({ user: auth.session.user });
});

app.post("/api/logout", (req, res) => {
    const auth = getSession(req);
    if (auth) {
        sessions.delete(auth.sessionId);
    }

    res.setHeader(
        "Set-Cookie",
        `${SESSION_COOKIE_NAME}=; HttpOnly; Path=/; Max-Age=0; SameSite=Lax`
    );
    res.json({ message: "Logged out" });
});


app.get("/api/appointments", requireAuth, (req, res) => {
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