const request = require("supertest");
const { describe, it, expect } = require("vitest");
const app = require("./app");

describe("Main page", () => {
  it("should let user view the main page", async () => {
    const response = await request(app).get("/");

    expect(response.status).toBe(200);
    expect(response.headers["content-type"]).toContain("text/html");
    expect(response.text).toContain("<html");
  });
});