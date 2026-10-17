import os
from datetime import datetime, timezone

import requests
import pandas as pd
from pvlib import atmosphere, irradiance, solarposition, temperature
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from google import genai

app = FastAPI(
    title="SolarSight AI",
    description="Weather-driven rooftop solar estimation",
    version="0.2.0",
)


@app.get("/")
def home():
    return {
        "app": "SolarSight AI",
        "status": "running",
        "dashboard": "/dashboard",
        "docs": "/docs",
    }


@app.get("/dashboard", include_in_schema=False)
def dashboard():
    return FileResponse("dashboard.html")


@app.get("/forecast")
def forecast(
    latitude: float = Query(26.2389, ge=-90, le=90),
    longitude: float = Query(73.0243, ge=-180, le=180),
    capacity_kw: float = Query(5.0, gt=0, le=10000),
):
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": (
            "temperature_2m,cloud_cover,shortwave_radiation,wind_speed_10m"
        ),
        "forecast_hours": 48,
        "past_hours": 0,
        "timezone": "Asia/Kolkata",
    }

    try:
        response = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params=params,
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()
        hourly = data["hourly"]
    except (requests.RequestException, KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Weather forecast source failed: {exc}",
        )

    results = []
    total_kwh = 0.0

    for i, time in enumerate(hourly["time"]):
        radiation = hourly["shortwave_radiation"][i]
        cloud = hourly["cloud_cover"][i]
        temperature = hourly["temperature_2m"][i]
        wind = hourly["wind_speed_10m"][i]

        # Simplified, uncalibrated baseline model.
        # Assumes hourly shortwave radiation is a proxy for panel-plane irradiance.
        performance_ratio = 0.80
        estimated_kw = min(
            capacity_kw,
            max(0.0, capacity_kw * radiation / 1000 * performance_ratio),
        )

        # Each record represents one hourly interval; kW × 1 hour ≈ kWh.
        interval_hours = 1.0
        estimated_kwh = estimated_kw * interval_hours
        total_kwh += estimated_kwh

        results.append({
            "time": time,
            "solar_radiation_w_m2": radiation,
            "cloud_cover_percent": cloud,
            "temperature_c": temperature,
            "wind_speed_10m_kmh": wind,
            "estimated_power_kw": round(estimated_kw, 3),
            "estimated_energy_kwh": round(estimated_kwh, 3),
        })

    return {
        "data_provenance": {
            "provider": "Open-Meteo",
            "source_url": "https://api.open-meteo.com/v1/forecast",
            "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
            "forecast_start_local": hourly["time"][0] if hourly["time"] else None,
            "forecast_end_local": hourly["time"][-1] if hourly["time"] else None,
            "timezone": data.get("timezone", "Asia/Kolkata"),
            "requested_forecast_hours": 48,
            "returned_hourly_records": len(hourly["time"]),
        },
        "location": {
            "latitude": data.get("latitude"),
            "longitude": data.get("longitude"),
            "timezone": data.get("timezone"),
        },
        "system_capacity_kw": capacity_kw,
        "model_assumptions": {
            "performance_ratio": 0.80,
            "interval_hours": 1.0,
            "radiation_input": "Open-Meteo shortwave_radiation (W/m²)",
            "irradiance_alignment": "Not adjusted for panel tilt or orientation",
            "temperature_loss_model": "Not applied",
            "calibration_status": "Uncalibrated illustrative baseline",
        },
        "forecast_hours": len(results),
        "estimated_energy_next_48h_kwh": round(total_kwh, 2),
        "method": (
            "Estimated power (kW) = capacity (kW) × shortwave radiation "
            "(W/m²) / 1000 × assumed performance ratio (0.80); "
            "hourly energy (kWh) = estimated power (kW) × 1 hour."
        ),
        "disclaimer": (
            "Illustrative weather-based estimate, not measured generation. "
            "The 0.80 performance ratio is an assumption, not site-calibrated. "
            "Actual output depends on orientation, shading, equipment and losses."
        ),
        "hourly_forecast": results,
    }



@app.get("/forecast/advanced")
def forecast_advanced(
    latitude: float = Query(26.2389, ge=-90, le=90),
    longitude: float = Query(73.0243, ge=-180, le=180),
    capacity_kw: float = Query(5.0, gt=0, le=10000),
    tilt: float = Query(20.0, ge=0, le=90),
    azimuth: float = Query(180.0, ge=0, le=360),
):
    """PV estimate using solar position, irradiance transposition, and temperature."""
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": (
            "temperature_2m,wind_speed_10m,"
            "shortwave_radiation,direct_normal_irradiance,diffuse_radiation"
        ),
        "forecast_hours": 48,
        "past_hours": 0,
        "timezone": "Asia/Kolkata",
    }

    try:
        response = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params=params,
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()
        hourly = data["hourly"]
        required = (
            "time", "temperature_2m", "wind_speed_10m",
            "shortwave_radiation", "direct_normal_irradiance", "diffuse_radiation",
        )
        if any(key not in hourly for key in required):
            raise ValueError("Weather source did not return all required radiation fields.")
        if not hourly["time"]:
            raise ValueError("Weather source returned no hourly records.")
    except (requests.RequestException, KeyError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=f"Advanced weather input failed: {exc}")

    times = pd.DatetimeIndex(pd.to_datetime(hourly["time"]))
    if times.tz is None:
        times = times.tz_localize(data.get("timezone", "Asia/Kolkata"))

    # Keep only hours whose timestamps are at or after the current hour.
    now_local = pd.Timestamp.now(tz=data.get("timezone", "Asia/Kolkata"))
    current_hour = now_local.floor("h")
    keep = times >= current_hour
    times = times[keep]

    if len(times) == 0:
        raise HTTPException(status_code=502, detail="Weather provider returned no current or future hours.")

    # Filter every weather series with the same mask to keep inputs aligned.
    for key in (
        "temperature_2m", "wind_speed_10m", "shortwave_radiation",
        "direct_normal_irradiance", "diffuse_radiation",
    ):
        hourly[key] = [value for value, include in zip(hourly[key], keep) if include]

    times_utc = times.tz_convert("UTC")

    temp_air = pd.Series(hourly["temperature_2m"], index=times_utc, dtype=float)
    wind_speed = pd.Series(hourly["wind_speed_10m"], index=times_utc, dtype=float) / 3.6  # Open-Meteo km/h -> m/s
    ghi = pd.Series(hourly["shortwave_radiation"], index=times_utc, dtype=float).clip(lower=0)
    dni = pd.Series(hourly["direct_normal_irradiance"], index=times_utc, dtype=float).clip(lower=0)
    dhi = pd.Series(hourly["diffuse_radiation"], index=times_utc, dtype=float).clip(lower=0)

    solar_pos = solarposition.get_solarposition(
        times_utc, latitude=latitude, longitude=longitude
    )
    zenith = solar_pos["apparent_zenith"].clip(upper=90)
    dni_extra = irradiance.get_extra_radiation(times_utc)
    airmass = atmosphere.get_relative_airmass(zenith)

    poa = irradiance.get_total_irradiance(
        surface_tilt=tilt,
        surface_azimuth=azimuth,
        solar_zenith=zenith,
        solar_azimuth=solar_pos["azimuth"],
        dni=dni,
        ghi=ghi,
        dhi=dhi,
        dni_extra=dni_extra,
        airmass=airmass,
        model="haydavies",
    )["poa_global"].fillna(0).clip(lower=0)

    # Explicit illustrative assumptions; no manufacturer-specific module data.
    # SAPM open-rack glass/glass coefficients are used as a generic proxy.
    temp_cell = temperature.sapm_cell(
        poa_global=poa,
        temp_air=temp_air,
        wind_speed=wind_speed,
        a=-3.47,
        b=-0.0594,
        deltaT=3,
    )
    temp_coefficient_per_c = -0.004  # assumed -0.4%/°C relative to 25°C
    temperature_factor = (1 + temp_coefficient_per_c * (temp_cell - 25)).clip(lower=0)
    performance_ratio = 0.80
    estimated_power = (
        capacity_kw * (poa / 1000) * performance_ratio * temperature_factor
    ).clip(lower=0, upper=capacity_kw)

    results = []
    total_kwh = 0.0
    for i, timestamp in enumerate(times):
        power = float(estimated_power.iloc[i])
        energy = power  # one-hour interval approximation
        total_kwh += energy
        results.append({
            "time": str(timestamp),
            "solar_zenith_deg": round(float(solar_pos["apparent_zenith"].iloc[i]), 2),
            "poa_irradiance_w_m2": round(float(poa.iloc[i]), 2),
            "cell_temperature_c": round(float(temp_cell.iloc[i]), 2),
            "estimated_power_kw": round(power, 3),
            "estimated_energy_kwh": round(energy, 3),
        })

    return {
        "model": "pvlib transposition + SAPM cell-temperature proxy",
        "location": {"latitude": latitude, "longitude": longitude, "timezone": data.get("timezone")},
        "system_capacity_kw": capacity_kw,
        "panel": {"tilt_deg": tilt, "azimuth_deg": azimuth},
        "data_provenance": {
            "provider": "Open-Meteo",
            "source_url": "https://api.open-meteo.com/v1/forecast",
            "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
            "returned_hourly_records": len(results),
        },
        "estimated_energy_next_48h_kwh": round(total_kwh, 2),
        "model_assumptions": {
            "performance_ratio": performance_ratio,
            "temperature_coefficient_per_c": temp_coefficient_per_c,
            "temperature_model": "SAPM cell-temperature coefficients used as generic proxy",
            "calibration_status": "Illustrative, uncalibrated; not validated against measured output",
            "limitations": "Uses forecast radiation components and assumed module/system parameters; no shading, soiling, inverter model, or site calibration.",
        },
        "hourly_forecast": results,
    }

@app.get("/explain")
def explain_forecast(
    latitude: float = Query(26.2389, ge=-90, le=90),
    longitude: float = Query(73.0243, ge=-180, le=180),
    capacity_kw: float = Query(5.0, gt=0, le=10000),
    model: str = Query("baseline", pattern="^(baseline|advanced)$"),
    tilt: float = Query(20, ge=0, le=90),
    azimuth: float = Query(180, ge=0, le=360),
):
    if model == "advanced":
        data = forecast_advanced(
            latitude=latitude,
            longitude=longitude,
            capacity_kw=capacity_kw,
            tilt=tilt,
            azimuth=azimuth,
        )
        hourly = data["hourly_forecast"]
        energy_kwh = data.get(
            "estimated_energy_next_48h_kwh",
            data.get("energy_kwh"),
        )
        peak = max(hourly, key=lambda h: h["estimated_power_kw"])
        evidence = {
            "forecast_model": "Advanced PV (pvlib)",
            "location": data["location"],
            "system_capacity_kw": capacity_kw,
            "panel_tilt_degrees": tilt,
            "panel_azimuth_degrees": azimuth,
            "estimated_energy_kwh": energy_kwh,
            "peak_estimated_hour": peak,
            "sample_hourly_forecast": hourly[::6],
            "model_assumptions": data.get("model_assumptions", {}),
            "data_provenance": data.get("data_provenance", {}),
            "limitations": (
                "Illustrative, uncalibrated PV estimate. Generic temperature "
                "model and temperature coefficient; no shading, soiling, "
                "manufacturer-specific parameters, inverter model, or "
                "site calibration."
            ),
        }
        disclaimer = evidence["limitations"]
    else:
        data = forecast(
            latitude=latitude,
            longitude=longitude,
            capacity_kw=capacity_kw,
        )
        hourly = data["hourly_forecast"]
        energy_kwh = data["estimated_energy_next_48h_kwh"]
        peak = max(hourly, key=lambda h: h["estimated_power_kw"])
        daylight = [
            h for h in hourly if h["solar_radiation_w_m2"] > 0
        ]
        cloudiest = sorted(
            daylight,
            key=lambda h: h["cloud_cover_percent"],
            reverse=True,
        )[:3]
        evidence = {
            "forecast_model": "Baseline",
            "location": data["location"],
            "system_capacity_kw": capacity_kw,
            "estimated_energy_next_48h_kwh": energy_kwh,
            "peak_estimated_hour": peak,
            "cloudiest_daylight_hours": cloudiest,
            "sample_hourly_forecast": hourly[::6],
            "method": data["method"],
            "limitations": data["disclaimer"],
        }
        disclaimer = data["disclaimer"]

    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "asia-south1")

    if not project:
        raise HTTPException(
            status_code=500,
            detail="GOOGLE_CLOUD_PROJECT is not configured.",
        )

    try:
        client = genai.Client(
            vertexai=True,
            project=project,
            location=location,
        )
        prompt = (
            "You are SolarSight AI, an energy forecasting assistant. "
            "Explain only the supplied forecast evidence. Give a concise "
            "summary, 2-3 observations, and limitations. Distinguish "
            "estimated output from measured generation. Do not invent "
            "carbon savings, prices, measurements, or confidence percentages. "
            "Clearly identify the selected model. For Baseline, explain that "
            "the 80% performance ratio is assumed. For Advanced PV, explain "
            "that tilt, azimuth, radiation components, and a generic "
            "temperature adjustment are used, with uncalibrated assumptions. "
            "Do not claim either model is validated against actual site output.\n\n"
            f"Evidence: {evidence}"
        )
        result = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )

        if not result.text:
            raise ValueError("Gemini returned an empty response.")

        return {
            "model": "gemini-2.5-flash",
            "forecast_model": model,
            "forecast_energy_estimate_kwh": energy_kwh,
            "explanation": result.text,
            "evidence": evidence,
            "disclaimer": disclaimer,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Gemini explanation failed: {str(exc)}",
        )