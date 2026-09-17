# Pixel Office

Pixelart office simulation for company monitor displays. 21 people wander,
idle at desks, and occasionally exchange scripted lines — all live over a
WebSocket to an HTML5 Canvas frontend.

## Run locally

    pip install -r requirements.txt
    uvicorn app.main:app --reload

Open http://localhost:8000

## Run tests

    pytest

## Edit people or floorplan

Edit `data/people.yaml`, `data/floorplan.yaml`, or `data/interactions.yaml`
— no code changes needed. Restart the server to pick up changes.

## Deploy to Azure App Service

    docker build -t pixel-office .
    az webapp up --name <app-name> --resource-group <rg> --sku B1 --runtime "PYTHON:3.11"

Or push the built image to Azure Container Registry and point an App
Service (Linux, container) at it, exposing port 8000.
