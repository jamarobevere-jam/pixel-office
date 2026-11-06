# Pixel Office

Pixelart office simulation for company monitor displays. 22 people wander,
idle, and occasionally exchange scripted lines; 21 have assigned desks. All
live over a WebSocket to an HTML5 Canvas frontend.

<img width="2585" height="1726" alt="image" src="https://github.com/user-attachments/assets/1ee120ed-2e10-42e7-b68e-f7671e4aa6da" />

# Credits
Idea and cool features made without AI: https://github.com/luisollero

First version: Claude Code and https://github.com/gunnhildr

## Cloud deployment
Automatically on push to main. 

https://pixel-office-latest.onrender.com/


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
