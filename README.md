# ietf126-rpp-hackathon

## OAuth2 Provider

This project uses Authentik as an OAuth2 provider for the registrars. The Authentik instance is configured to run on `localhost:9991` for registrar A and `localhost:9993` for registrar B.

Configuration files for the Authentik instances are located in the `registrar/oauth2` and `registrar/oauth2b` directories. You can start the Authentik instances using Docker Compose.

The registrars are configured to use these Authentik instances for authentication. The configuration is specified in the `.env` and `.env.registrar-b` files in the `registrar/backend` directory.

### Authentik config

Create a new application in Authentik for each registrar. Use the following settings:
- Application type: OAuth2
- Redirect URI: `http://localhost:<registrar_port>/api/auth/callback` (replace `<registrar_port>` with the port of the registrar, e.g., `8001` for registrar A and `8002` for registrar B)
- Client ID and Client Secret: Use the values specified in the `.env` and `.env.registrar-b` files.

Create a user in Authentik for each registrar. Use the following settings:
- Username: `user1` for registrar A and `user2` for registrar B
- Password: same as the username (for simplicity in this hackathon setup)

Create a group and add the users to the group. Assign the group to the application created for each registrar.

## Starting the registry

```bash
cd registry
./start.sh
```

## Starting registrar A

```bash
cd registrar
./start.sh
```

## Starting registrar B

```bash
cd registrar
./start.sh --port 8002 --frontend-port 5175 --name 'Registrar B' --env-file .env.registrar-b
```

## Starting OIDC provider 1

Does authentication for registrar A

```bash
cd registrar/oauth2/
docker compose up -d
```

## Starting OIDC provider 2

Does authentication for registrar B

```bash
cd registrar/oauth2b/
docker compose up -d
```
