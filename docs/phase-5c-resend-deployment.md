# Phase 5C Resend deployment

The Raspberry Pi deployment keeps `RESEND_API_KEY` and `RESEND_FROM_EMAIL` out of Git. After the backend deployment completes successfully, the `Configure Resend on Raspberry Pi` workflow writes the two GitHub Secrets into the Pi `.env` file and restarts the backend service.
