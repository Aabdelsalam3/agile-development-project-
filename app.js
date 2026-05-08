// const http = require("node:http");
// const fs = require("fs/promises");
// const express = require("express");

// const app = http.createServer(async (req, res) => {
//   let content;

//   if (req.url === "/") {
//     content = await fs.readFile("index.html", "utf-8");
//   } else if (req.url === "/login") {
//     content = await fs.readFile("login.html", "utf-8");
//   } else {
//     content = "<h1>This is some html</h1>";
//   }

//   res.end(content);
// });

// app.listen(3000, () => {
//   console.log("Server running on http://localhost:3000");
// });


const http = require("node:http");
const fs = require("fs/promises");

const app = http.createServer(async (req, res) => {
  let content;

  if (req.url === "/") {
    content = await fs.readFile("index.html", "utf-8");
  } else if (req.url === "/login") {
    content = await fs.readFile("login.html", "utf-8");
  } else {
    content = "<h1>This is some html</h1>";
  }

  res.setHeader("Content-Type", "text/html");

  res.end(content);
});

module.exports = app;