# Interchained Node Operator Rewards Portal

The Node Operator Rewards Portal is a full-stack experience that tracks uptime and performance for Interchained nodes and allocates daily rewards from a shared pool. It is composed of:

- `backend/` — FastAPI service backed by Redis for authentication, node management, health monitoring, and reward distribution.
- `frontend/` — Dark neon glass UI built with vanilla HTML/CSS/JS that consumes the backend API.

Refer to the individual READMEs for detailed setup instructions. When enabling the admin experience, be sure to configure
`PORTAL_ADMIN_PORTAL_PASSWORD` so the dashboard can unlock the privileged controls with the shared passphrase.
