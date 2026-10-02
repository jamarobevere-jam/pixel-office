# Pixel Office

Pixelart office simulation for company monitor displays. 21 people wander,
idle at desks, and occasionally exchange scripted lines — all live over a
WebSocket to an HTML5 Canvas frontend.

# Credits
Idea and cool features made without AI: https://github.com/luisollero

First version: Claude Code and https://github.com/gunnhildr

## Run locally

### Devcontainers
Have the docker installed. Then open project in VSCode -> Reopen in Containers.
This will set up all the requirements.

## Local environment
Install requirements: 

    pip install -r requirements.txt

### Run the app

    python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

Open http://localhost:8000

## Run tests

    pytest

## Edit people or floorplan

Edit `data/people.yaml`, `data/floorplan.yaml`, or `data/interactions.yaml`
— no code changes needed. Restart the server to pick up changes.

## Pixel art
All available art in in data/characters or data/furniture.

All characters made in here https://www.avatarsinpixels.com/chibi/clothing/Body

## Deploy to Azure App Service

Build the image, push it to Azure Container Registry (ACR), and point an
App Service (Linux, container) at it:

    docker build -t pixel-office .
    az acr build --registry <acr-name> --image pixel-office:latest .

    az webapp create --name <app-name> --resource-group <rg> --plan <plan> \
      --deployment-container-image-name <acr-name>.azurecr.io/pixel-office:latest

Then set two app settings that are easy to miss:

    az webapp config appsettings set --name <app-name> --resource-group <rg> \
      --settings WEBSITES_PORT=8000

`WEBSITES_PORT=8000` tells Azure's health probe which port the container
listens on (it otherwise defaults to port 80 and the app never comes up
healthy). You also need to enable **Web sockets** under the App Service's
Configuration > General settings — it is off by default and the `/ws`
endpoint will not work without it.
