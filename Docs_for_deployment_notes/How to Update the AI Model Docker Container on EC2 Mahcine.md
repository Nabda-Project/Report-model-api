# How to Update the AI Model Docker Container

Use these instructions when a new version of the `med-report-api` Docker image has been pushed to Docker Hub and you need to update the running server.

## Prerequisites

* Your SSH key (`med-report-key.pem`)
* Your server's Elastic IP address
* Your secret `API_KEY`

---

## Step 1: Connect to the Server

Open your terminal on your local computer, navigate to where your `.pem` key is saved, and SSH into the server:

```bash
ssh -i med-report-key.pem ubuntu@YOUR_ELASTIC_IP
Step 2: Remove the Old Container
Force-stop and delete the currently running container to free up the name and port:

Bash
docker rm -f med-report-api
(Expected output: med-report-api)

Step 3: Pull the Latest Image
Download the newly pushed image from Docker Hub:

Bash
docker pull ziadmo/med-report-api:latest
Step 4: Run the New Container
Start up the new container. Make sure to replace YOUR_SECRET_API_KEY with your actual key:

Bash
docker run -d \
  --name med-report-api \
  --restart unless-stopped \
  -p 8000:8000 \
  -e API_KEY="YOUR_SECRET_API_KEY" \
  ziadmo/med-report-api:latest
(Expected output: A long string of characters representing the new container ID)

Step 5: Verify the Update
1. Watch the container logs to ensure the model loads correctly:

Bash
docker logs -f med-report-api
Wait for the INFO: Uvicorn running on http://0.0.0.0:8000 message, then press Ctrl+C to exit the logs.

2. Run a health check to confirm the API is responding:

Bash
curl http://localhost:8000/health
(Expected output: {"status":"ok","queue_size":0,"total_jobs":0})



ssh -i "med-report-key-2.pem" ubuntu@100.51.212.220
