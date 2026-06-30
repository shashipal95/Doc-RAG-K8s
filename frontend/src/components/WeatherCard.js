"use client";

import React from 'react';

/**
 * A premium, glassmorphism-inspired Weather Card.
 * Displays temperature, condition, location, and astronomy data.
 */
export default function WeatherCard({ data }) {
  if (!data) return null;

  const {
    temp_c = "--",
    condition = "Unknown",
    location = "Unknown",
    sunrise = "--:--",
    sunset = "--:--",
    humidity = "--",
    wind = "--",
    rain_chance = "0"
  } = data;

  // Simple icon mapping based on condition
  const getIcon = (cond) => {
    const c = cond.toLowerCase();
    if (c.includes("sun") || c.includes("clear")) return "☀️";
    if (c.includes("cloud")) return "☁️";
    if (c.includes("rain") || c.includes("shower")) return "🌧️";
    if (c.includes("snow")) return "❄️";
    if (c.includes("thunder")) return "🌩️";
    return "⛅";
  };

  const today = new Date().toLocaleDateString('en-US', { 
    weekday: 'short', 
    month: 'short', 
    day: 'numeric', 
    year: 'numeric' 
  });
  
  const now = new Date().toLocaleTimeString('en-US', { 
    hour: '2-digit', 
    minute: '2-digit' 
  });

  return (
    <div className="weather-card-container" style={{
      margin: "12px 0",
      width: "100%",
      maxWidth: "320px",
      borderRadius: "20px",
      padding: "20px",
      background: "linear-gradient(135deg, #6a11cb 0%, #2575fc 100%)", // Vibrant blue-purple gradient
      color: "white",
      boxShadow: "0 8px 30px rgba(37, 117, 252, 0.25)",
      fontFamily: "Inter, sans-serif",
      position: "relative",
      overflow: "hidden"
    }}>
      {/* Subtle Background Glows */}
      <div style={{
        position: "absolute",
        top: "-10%",
        right: "-10%",
        width: "100px",
        height: "100px",
        background: "rgba(255,255,255,0.08)",
        borderRadius: "50%",
        filter: "blur(30px)"
      }} />

      {/* Header: Location & Time */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "16px" }}>
        <div style={{ maxWidth: "70%" }}>
          <h3 style={{ margin: 0, fontSize: "14px", fontWeight: 600, opacity: 0.9, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{location}</h3>
          <p style={{ margin: "2px 0 0", fontSize: "11px", opacity: 0.7 }}>{today}</p>
        </div>
        <div style={{ textAlign: "right" }}>
          <span style={{ fontSize: "13px", fontWeight: 600, opacity: 0.9 }}>{now}</span>
        </div>
      </div>

      {/* Main Stats: Temp & Condition */}
      <div style={{ display: "flex", alignItems: "center", gap: "16px", marginBottom: "20px" }}>
        <div style={{ fontSize: "44px", lineHeight: 1 }}>{getIcon(condition)}</div>
        <div>
          <div style={{ fontSize: "42px", fontWeight: 700, lineHeight: 1 }}>{temp_c}°<span style={{ fontSize: "24px", fontWeight: 400 }}>C</span></div>
          <p style={{ margin: "4px 0 0", fontSize: "14px", fontWeight: 500, opacity: 0.9 }}>{condition}</p>
        </div>
      </div>

      {/* Divider */}
      <div style={{ height: "1px", background: "rgba(255,255,255,0.15)", marginBottom: "16px" }} />

      {/* Bottom Row: Astronomy & Details */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <span style={{ fontSize: "15px" }}>🌅</span>
          <div>
            <p style={{ margin: 0, fontSize: "9px", textTransform: "uppercase", opacity: 0.6 }}>Sunrise</p>
            <p style={{ margin: 0, fontSize: "11px", fontWeight: 600 }}>{sunrise}</p>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <span style={{ fontSize: "15px" }}>🌇</span>
          <div>
            <p style={{ margin: 0, fontSize: "9px", textTransform: "uppercase", opacity: 0.6 }}>Sunset</p>
            <p style={{ margin: 0, fontSize: "11px", fontWeight: 600 }}>{sunset}</p>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <span style={{ fontSize: "15px" }}>💧</span>
          <div>
            <p style={{ margin: 0, fontSize: "9px", textTransform: "uppercase", opacity: 0.6 }}>Humidity</p>
            <p style={{ margin: 0, fontSize: "11px", fontWeight: 600 }}>{humidity}%</p>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <span style={{ fontSize: "15px" }}>💨</span>
          <div>
            <p style={{ margin: 0, fontSize: "9px", textTransform: "uppercase", opacity: 0.6 }}>Wind</p>
            <p style={{ margin: 0, fontSize: "11px", fontWeight: 600 }}>{wind} km/h</p>
          </div>
        </div>
      </div>
    </div>
  );
}
