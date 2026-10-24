# SolarSight AI ☀️

**See the sun. Understand the power.**

SolarSight AI turns hourly weather forecasts into explainable 48-hour
solar-generation estimates. It combines weather data, photovoltaic (PV)
modelling, a dashboard, and generative-AI explanations to help users
understand expected solar output and the assumptions behind it.

> **Project status:** Prototype / hackathon project. Forecasts are
> model-based estimates, not guaranteed production values. Historical
> PVDAQ observations are explored separately and are not, by themselves,
> evidence that the forecast model has been validated.

## Table of contents

-   [Problem](#problem)
-   [Solution](#solution)
-   [Features](#features)
-   [Architecture](#architecture)
-   [Technology stack](#technology-stack)
-   [Live demo](#live-demo)
-   [Getting started](#getting-started)
-   [Configuration](#configuration)
-   [API endpoints](#api-endpoints)
-   [Forecast methodology](#forecast-methodology)
-   [Historical data and limitations](#historical-data-and-limitations)
-   [Deployment](#deployment)
-   [Project structure](#project-structure)
-   [Roadmap](#roadmap)
-   [Acknowledgements](#acknowledgements)
-   [License](#license)

## Problem

Solar power output changes with sunlight, weather, and system
characteristics. A weather forecast alone does not directly tell a user
how much energy a solar installation may produce, and a numerical
estimate can be difficult to interpret without understanding its
assumptions.

## Solution

SolarSight AI presents a 48-hour outlook for solar generation using
hourly weather data and PV modelling. Its dashboard makes the forecast
easier to explore, while Gemini generates a plain-language explanation
of the results and relevant assumptions. A separate historical-data
endpoint demonstrates access to real solar-generation observations from
the public PVDAQ dataset.

## Features

-   **48-hour solar outlook:** Hourly weather-based generation
    estimates.
-   **Interactive dashboard:** Explore the forecast and hourly output.
-   **Baseline model:** Converts forecast shortwave radiation into an
    estimated energy output using configured system assumptions.
-   **Advanced PV modelling:** Uses `pvlib` for solar-position and
    irradiance modelling, with a cell-temperature approximation.
-   **AI explanations:** Uses Gemini 2.5 Flash to explain forecast
    trends in plain language.
-   **Historical observations:** Retrieves PVDAQ data for exploration of
    measured solar-system output.
-   **Cloud-hosted API:** FastAPI application deployed on Google Cloud
    Run.

## Architecture

``` mermaid
flowchart TD
    U[User / Browser Dashboard] --> API[Google Cloud Run<br/>FastAPI]
    API --> WX[Open-Meteo<br/>Hourly weather forecast]
    WX --> BASE[Baseline forecast model]
    WX --> PV[Advanced PV model<br/>pvlib]
    BASE --> API
    PV --> API
    API --> GEM[Gemini 2.5 Flash<br/>Plain-language explanation]
    API --> HIST[PVDAQ historical data endpoint]
    API --> U
```

The diagram is a high-level view of the application's capabilities. The
historical-data path is separate from the live forecast calculation.
Gemini is used for explanation, not as the numerical PV simulation
engine.

## Technology stack

  -----------------------------------------------------------------------
  Component               Technology              Purpose
  ----------------------- ----------------------- -----------------------
  Backend API             Python, FastAPI         Serves the dashboard
                                                  and API endpoints

  Frontend                HTML dashboard          Presents forecast
                                                  information and
                                                  visualizations

  Weather source          Open-Meteo              Provides hourly weather
                                                  forecast data

  Baseline forecast       Python model            Estimates output from
                                                  weather radiation and
                                                  system assumptions

  Advanced PV model       `pvlib`                 Solar position,
                                                  irradiance
                                                  transposition, and
                                                  related PV calculations

  Generative AI           Gemini 2.5 Flash via    Produces
                          Google Gen AI SDK       natural-language
                                                  explanations

  Historical observations NREL/OEDI PVDAQ data    Allows exploration of
                                                  recorded solar-system
                                                  output

  Hosting                 Google Cloud Run        Runs the containerized
                                                  FastAPI application
  -----------------------------------------------------------------------

## Live demo

-   **Application:** https://solarsight-ai-bimwrqfosq-el.a.run.app
-   **GitHub repository:** https://github.com/bhawuk-arora/SolarSight-AI

The live URL may point to a revision that differs from the latest source
in this repository. Check the deployed revision before relying on a
particular feature.

## Getting started

### Prerequisites

-   Python 3.10 or a compatible version supported by the installed
    dependencies
-   Git
-   A Google AI API key for Gemini-powered explanations
-   Internet access for Open-Meteo and PVDAQ requests

### 1. Clone the repository

``` bash
git clone https://github.com/bhawuk-arora/SolarSight-AI.git
cd SolarSight-AI
```

### 2. Create and activate a virtual environment

Linux / macOS / WSL:

``` bash
python3 -m venv .venv
source .venv/bin/activate
```

Windows PowerShell:

``` powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

``` bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure Gemini

Set the API key in your shell. Do not commit secrets to Git.

Linux / macOS / WSL:

``` bash
export GEMINI_API_KEY="YOUR_API_KEY"
```

Windows PowerShell:

``` powershell
$env:GEMINI_API_KEY="YOUR_API_KEY"
```

The application may use a different environment-variable name depending
on the current source configuration. Confirm the variable read by
`main.py` before running if Gemini explanations do not initialize.

### 5. Run locally

``` bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Open these URLs in your browser:

-   Dashboard: http://localhost:8000/dashboard
-   API root: http://localhost:8000/
-   Interactive API documentation: http://localhost:8000/docs

If the application fails to start, confirm that all dependencies in
`requirements.txt` are installed and that the command is run from the
repository root.

## Configuration

Forecasts depend on the selected location and the system assumptions
used by the model. The application has used a Jaipur-area default
location in development, but users should confirm the location and
installation parameters before interpreting results.

Typical PV assumptions include:

-   **System capacity:** rated installation capacity in kW
-   **Performance ratio (PR):** a simplified factor accounting for
    aggregate system losses in the baseline model
-   **Tilt and azimuth:** panel orientation used by the advanced model

These are model inputs, not measurements of a specific installation.
Review the current `main.py` implementation for the exact defaults and
supported request parameters.

## API endpoints

The application includes the following endpoints. Request fields and
response schemas can evolve; `/docs` is the authoritative interactive
reference for the running version.

  -----------------------------------------------------------------------
  Endpoint                            Purpose
  ----------------------------------- -----------------------------------
  `GET /`                             Basic application/root response

  `GET /dashboard`                    Browser dashboard

  `GET /forecast`                     Baseline weather-based forecast

  `GET /forecast/advanced`            Advanced PV modelling using `pvlib`

  `GET /explain`                      AI-generated explanation of
                                      forecast context

  `GET /evaluation/historical`        Retrieves historical PVDAQ
                                      observations for exploration
  -----------------------------------------------------------------------

Example historical-data request:

``` text
/evaluation/historical?date=2023-02-20&system_id=10
```

This example requests historical observations for PVDAQ system 10 on 20
February 2023. It is a data-exploration example, not a claim that the
system matches the Jaipur forecast location.

For exact parameter names, valid ranges, and response examples, start
the application and visit `/docs`.

## Forecast methodology

### Baseline forecast

The baseline approach uses hourly shortwave-radiation data from
Open-Meteo as a proxy for available solar irradiance and applies
system-capacity and performance-ratio assumptions to estimate output.
This is a simplified estimate and does not model every loss or
installation-specific condition.

### Advanced forecast

The advanced route uses `pvlib` for solar-position and irradiance
calculations, including irradiance transposition, and a cell-temperature
approximation. This adds physical modelling detail but does not
automatically make the forecast accurate for a particular site.

### AI explanation

Gemini 2.5 Flash converts forecast context into a readable explanation.
The explanation is an interpretation of model output, not an independent
measurement or proof of forecast accuracy.

## Historical data and limitations

The PVDAQ endpoint is intended for historical data exploration. For
example, a previous development check returned 1,440 observations for
system 10 on 20 February 2023, with a peak AC-power reading of 1,144.5
W. System 10 is located in Colorado, so these observations should not be
presented as Jaipur production data.

**Historical observations are not forecast validation on their own.** A
meaningful validation requires forecasts and measured production matched
by site, timestamp, capacity, and relevant system conditions, followed
by documented error metrics.

Current limitations include:

-   The baseline model uses simplified radiation and performance
    assumptions.
-   The advanced model uses approximations and is not calibrated to a
    particular installation.
-   Shading, soiling, inverter behaviour, degradation, and site-specific
    losses may not be fully represented.
-   Historical PVDAQ observations are not automatically matched to the
    live forecast.
-   No accuracy or improvement claim should be made without a
    documented, matched validation study.

## Deployment

The application is designed to run as a containerized FastAPI service on
Google Cloud Run.

A typical deployment flow is:

1.  Build the application container using the repository's `Dockerfile`.
2.  Configure required runtime environment variables and secrets
    securely.
3.  Deploy the container to Cloud Run.
4.  Verify the health/root response, dashboard, forecast endpoints, and
    Gemini explanation endpoint.
5.  Confirm that the deployed revision includes the source changes
    intended for the demo.

Do not put API keys in source code, container images, screenshots, or
committed `.env` files. Use the platform's supported secret/environment
configuration.

## Project structure

The exact repository layout may change. The main files used by the
application include:

``` text
SolarSight-AI/
├── main.py           # FastAPI application and API endpoints
├── dashboard.html    # Browser dashboard
├── requirements.txt  # Python dependencies
├── Dockerfile        # Container build configuration
└── README.md         # Project documentation
```

Check the repository for any additional tests, assets, configuration
files, or deployment scripts.

## Roadmap

-   Validate forecasts against measured output from the same solar
    installation and time period.
-   Report documented error metrics such as MAE and RMSE after matched
    validation.
-   Add site-specific system configuration and calibration.
-   Improve treatment of shading, inverter efficiency, and other system
    losses.
-   Make the provenance and assumptions behind each estimate clearer.
-   Expand historical-data evaluation using suitable, well-documented
    datasets.

## Acknowledgements

-   [Open-Meteo](https://open-meteo.com/) for weather forecast data.
-   [pvlib Python](https://pvlib-python.readthedocs.io/) for
    photovoltaic modelling tools.
-   [NREL / Open Energy Data Initiative
    (OEDI)](https://data.openei.org/) for the PVDAQ historical data
    resource.
-   Google Cloud Run and Gemini for hosting and generative-AI
    explanation capabilities.

## License

No license has been specified in this README. Add a `LICENSE` file
before describing the repository as open source, and ensure the selected
license is appropriate for the project's code and dependencies.
