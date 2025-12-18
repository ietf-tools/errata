# Errata Website

This is a simple django re-implementation of the current errata system.
It is not intended to add features beyond these two:
* Verifiers will login via datatracker credentals
* The RPC will vet all new filed errata (and handle spam) before verifiers are asked to look

## Development

Have a datatracker development instance running at `http://localhost:8000` (it will serve as the OIDC provider)
```
dev ➜ /workspace (minimal) $ ./manage.py test

dev ➜ /workspace (minimal) $ ./manage.py runserver 8808
```
and browse to `http://localhost:8808`
