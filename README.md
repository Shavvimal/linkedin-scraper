# Graph API

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

## Docker

```bash
docker build -t sammy-api .
```

To run, specifying with our `.env` file:

```bash
docker run sammy-api --env-file <env_file>
```

```bash
docker build -t sammy-api . ; docker rm sammy-api ; docker run --detach --env-file docker.env -p 8000:8000 --name sammy-api sammy-api
```

# Deploy

```bash
az login --use-device-code
```

```bash
docker build -t sammy-api .
```

To deploy the Docker image to Azure Container Apps, use the az containerapp up command. (The following commands are shown for the Bash shell. Change the continuation character (\) as appropriate for other shells.)

```bash
az containerapp up --resource-group sammy-api --name fastapi-sammy --ingress external --target-port 8000 --location uksouth --source . --env-vars SECRET=SAUCE
```

Stream logs for your container with:

```bash
az containerapp logs show -n fastapi-sammy -g sammy-api
```

See full output using:

```bash
az containerapp show -n fastapi-sammy -g sammy-api
```
