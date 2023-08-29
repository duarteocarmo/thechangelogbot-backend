#!/bin/sh

# echo "Runner script loaded..."

# while true; do
uvicorn thechangelogbot.api.main:app --host 0.0.0.0 --port 8000 
#   API_PID=$!
#   sleep 36000  # Sleep for 10 hours
#   kill $API_PID

#   echo "Running indexer..."

#   index-podcasts
#   echo "Restarting the API..."
# done
