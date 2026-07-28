# Reels Command Center — Sprint 2

Drugi sprint dodaje rzeczywistą, lokalną integrację YouTube przygotowaną pod oficjalny OAuth Google.

## Co działa

- Google OAuth 2.0 dla konta właściciela kanału;
- szyfrowanie tokenów przed zapisem w PostgreSQL;
- pobranie kanału przez `channels.list(mine=true)`;
- pobranie uploadów z playlisty kanału;
- synchronizacja tytułów, dat, miniaturek, długości i bieżących statystyk;
- osobna migawka statystyk przy każdej synchronizacji;
- panel: status połączenia, synchronizacja, odłączenie i lista filmów;
- test integracji na fałszywym kliencie YouTube — testy nie wykonują połączeń z internetem.

## Pierwsze uruchomienie

1. Zainstaluj i uruchom Docker Desktop.
2. Skopiuj `.env.example` jako `.env`.
3. Zmień wartości `SESSION_SECRET` i `TOKEN_ENCRYPTION_KEY` na dwa długie, losowe ciągi.
4. Utwórz folder `backend/secrets` i włóż do niego pobrany plik OAuth jako:
   `backend/secrets/google_client_secret.json`.
5. W Google Cloud ustaw redirect URI dokładnie:
   `http://127.0.0.1:8000/api/integrations/youtube/callback`
6. Włącz `YouTube Data API v3` i dodaj swój Gmail jako użytkownika testowego aplikacji OAuth.
7. Uruchom:

```bash
docker compose up --build
```

Panel: `http://127.0.0.1:3000`  
API: `http://127.0.0.1:8000`  
Swagger: `http://127.0.0.1:8000/docs`

## Bezpieczeństwo

- Nie commituj `.env` ani `backend/secrets/`.
- Client secret Google, refresh token i access token są sekretami.
- `OAUTH_INSECURE_TRANSPORT=true` jest dopuszczalne wyłącznie lokalnie na `127.0.0.1`.
- Zmiana `TOKEN_ENCRYPTION_KEY` po zapisaniu tokenów uniemożliwi ich odszyfrowanie; wtedy odłącz i połącz konto ponownie.

## Zakres Sprintu 3

- migracje Alembic zamiast `create_all`;
- automatyczny harmonogram synchronizacji;
- wykres wzrostu migawek;
- łączenie filmu YouTube z jedną wspólną rolką RCC;
- obsługa błędów API w czytelnej diagnostyce.
