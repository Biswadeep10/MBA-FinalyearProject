# CareFlow Health — Backend TODO

Items for a future backend pass. **Not in scope for the current POC** (keep the app open for local demos without login).

---

## Authentication & authorisation

- [ ] Define roles (e.g. patient, receptionist, admin) and what each route allows
- [ ] Add session or token-based auth (Flask-Login, JWT, or similar — pick one approach)
- [ ] Protect admin routes (`/appointments`, cancel, future admin APIs) behind auth
- [ ] Return proper `401` / `403` JSON/HTML responses from Flask (not browser/AirPlay errors)
- [ ] Document dev credentials or seed users for local testing

---

## Request logging & observability

- [ ] Log each incoming request (method, path, status, duration) so terminal output matches browser traffic
- [ ] Structured logs (JSON) for easier filtering in production
- [ ] Centralise error handling (`@app.errorhandler`) with consistent error payloads
- [ ] Optional: request ID / correlation ID for tracing bookings end-to-end

---

## API & production hardening

- [ ] Move secrets and config to environment variables (`FLASK_SECRET_KEY`, `DATABASE_URL`, etc.)
- [ ] Run behind a production WSGI server (gunicorn/waitress) instead of `app.run(debug=True)`
- [ ] CORS policy if a separate frontend is introduced
- [ ] Rate limiting on public booking endpoints
- [ ] Health check route (`/health`) for deploy probes

---

## macOS local development note

On many Macs, **port 5000 is reserved by AirPlay Receiver**. If you must use port 5000, disable AirPlay in **System Settings → General → AirDrop & Handoff → AirPlay Receiver**, or set `PORT=5001` when starting the app (current default).
