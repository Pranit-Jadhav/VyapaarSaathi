#!/bin/bash
echo "Starting VyapaarSaathi - Backend & Frontend..."

# Activate venv
source .venv/bin/activate

# Start backend (port 8000)
echo "Starting backend on http://127.0.0.1:8000..."
uvicorn main:app --host 127.0.0.1 --port 8000 --reload &
BACKEND_PID=$!

# Wait a bit for backend
sleep 3

# Start frontend (port 5173)
echo "Starting frontend on http://127.0.0.1:5173..."
npm run dev &
FRONTEND_PID=$!

echo "Starting Cloudflare tunnel for WhatsApp..."
cloudflared tunnel --url http://127.0.0.1:8000 &
TUNNEL_PID=$!

echo "All services started! (Backend + Frontend + Cloudflare Tunnel)"
echo "Backend: http://127.0.0.1:8000 | Frontend: http://127.0.0.1:5173"
echo "Watch terminal for Cloudflare tunnel URL (use for Twilio webhook)"
echo "Press Ctrl+C to stop all."

wait $BACKEND_PID $FRONTEND_PID $TUNNEL_PID

