#!/bin/sh

echo "Runner script loaded..."

while true; do
  echo "Running API..."
  uvicorn thechangelogbot.api.main:app --host 0.0.0.0 --port 8000 &
  echo "Done!"
  API_PID=$!
  # sleep every 5 minutes
  sleep 86400
  kill $API_PID
  echo "Running indexer..."
  index-podcasts
  echo "Restarting the API..."
done
