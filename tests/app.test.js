import request from "supertest";
import { describe, it, expect } from "vitest";
import app from "../app.js";

describe("Main page", () => {
  it("should return the index page", async () => {
    const response = await request(app).get("/");

    expect(response.statusCode).toBe(200);

    expect(response.text).toContain("<html");
  });
});

describe("login page", () => {
  it("should return the login page", async () => {
    const response = await request(app).get("/login");

    expect(response.statusCode).toBe(200);

    expect(response.text).toContain("<html");
  });
});

describe("Unknown page", () => {
  it("should return fallback html", async () => {
    const response = await request(app).get("/wrongpage");

    expect(response.statusCode).toBe(200);

    expect(response.text).toContain("This is some html");
  });
});

describe("HTML response type", () => {
  it("should return HTML for the main page", async () => {
    const response = await request(app).get("/");

    expect(response.headers["content-type"]).toContain("text/html");
  });

  it("should return HTML for the login page", async () => {
    const response = await request(app).get("/login");

    expect(response.headers["content-type"]).toContain("text/html");
  });
});

describe("loging page content",()=>{
  it("should contain login content", async()=>{
    const response = await request(app).get("/login");

    expect(response.statusCode).toBe(200);

    expect(response.text).toContain("login");
  });
});

describe("login page", ()=>{
  it("should return contentof loging page", async()=>{
    const response = await request(app).get("/login");

    expect(response.statusCode).toBe(200);

    expect(response.text).toContain("<html")
  });
});

