#!/bin/sh

echo "Runner script loaded..."

while true; do
  uvicorn thechangelogbot.api.main:app --host 0.0.0.0 --port 8000 &
  API_PID=$!
  # sleep every 5 minutes
  sleep 1800
  kill $API_PID
  echo "Running indexer..."
  index-podcasts
  echo "Restarting the API..."
done
