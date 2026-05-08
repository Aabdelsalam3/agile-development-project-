import { describe, it, expect, beforeEach } from "vitest";

import {
  createBooking,
  getBookingById,
  getDailyBookings,
  updateBookingTime,
  cancelBooking,
  deleteBooking,
  resetBookings,
} from "./booking.js";
beforeEach(() => {
  resetBookings();
});
describe("Create booking", () => {
  it("should not create a booking if a required field is missing", () => {
    expect(() => {
      createBooking({
        name: "Navid",
        date: "2026-05-10",
      });
    }).toThrow("Missing required field");
  });

  it("should not create a booking for a conflicting time slot", () => {
    createBooking({
      name: "Navid",
      date: "2026-05-10",
      time: "10:00",
    });

    expect(() => {
      createBooking({
        name: "Ali",
        date: "2026-05-10",
        time: "10:00",
      });
    }).toThrow("Time slot already booked");
  });

  it("should allow a customer to create a booking", () => {
    const booking = createBooking({
      name: "Navid",
      date: "2026-05-10",
      time: "10:00",
    });

    expect(booking.name).toBe("Navid");
    expect(booking.date).toBe("2026-05-10");
    expect(booking.time).toBe("10:00");
    expect(booking.status).toBe("confirmed");
  });
});

describe("Read booking", () => {
  it("should view a single booking by id", () => {
    const booking = createBooking({
      name: "Navid",
      date: "2026-05-10",
      time: "10:00",
    });

    const result = getBookingById(booking.id);

    expect(result).toEqual(booking);
  });

  it("should return a correctly formatted booking", () => {
    const booking = createBooking({
      name: "Navid",
      date: "2026-05-10",
      time: "10:00",
    });

    expect(booking).toHaveProperty("id");
    expect(booking).toHaveProperty("name");
    expect(booking).toHaveProperty("date");
    expect(booking).toHaveProperty("time");
    expect(booking).toHaveProperty("status");
  });

  it("should view daily bookings", () => {
    createBooking({
      name: "Navid",
      date: "2026-05-10",
      time: "10:00",
    });

    createBooking({
      name: "Ali",
      date: "2026-05-10",
      time: "11:00",
    });

    createBooking({
      name: "Sara",
      date: "2026-05-11",
      time: "12:00",
    });

    const dailyBookings = getDailyBookings("2026-05-10");

    expect(dailyBookings.length).toBe(2);
  });
});

describe("Update booking", () => {
  it("should update appointment time", () => {
    const booking = createBooking({
      name: "Navid",
      date: "2026-05-10",
      time: "10:00",
    });

    const updatedBooking = updateBookingTime(booking.id, "12:00");

    expect(updatedBooking.time).toBe("12:00");
  });

  it("should cancel a booking", () => {
    const booking = createBooking({
      name: "Navid",
      date: "2026-05-10",
      time: "10:00",
    });

    const cancelledBooking = cancelBooking(booking.id);

    expect(cancelledBooking.status).toBe("cancelled");
  });

  it("should allow a customer to reschedule appointment", () => {
    const booking = createBooking({
      name: "Navid",
      date: "2026-05-10",
      time: "10:00",
    });

    const rescheduled = updateBookingTime(booking.id, "14:00");

    expect(rescheduled.time).toBe("14:00");
  });
});

describe("Delete booking", () => {
  it("should delete a valid booking", () => {
    const booking = createBooking({
      name: "Navid",
      date: "2026-05-10",
      time: "10:00",
    });

    const deletedBooking = deleteBooking(booking.id);

    expect(deletedBooking.id).toBe(booking.id);
    expect(getBookingById(booking.id)).toBeUndefined();
  });

  it("should not delete an invalid booking", () => {
    expect(() => {
      deleteBooking("wrong-id");
    }).toThrow("Booking not found");
  });

  it("should allow a customer to remove their appointment", () => {
    const booking = createBooking({
      name: "Navid",
      date: "2026-05-10",
      time: "10:00",
    });

    deleteBooking(booking.id);

    const result = getBookingById(booking.id);

    expect(result).toBeUndefined();
  });
});