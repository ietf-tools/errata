# Errata Website

This is a simple django re-implementation of the current errata system.
It is not intended to add features beyond these two:
* Verifiers will login via datatracker credentials
* The RPC will vet all new filed errata (and handle spam) before verifiers are asked to look

## Development

Have a datatracker development instance running at `http://localhost:8000` (it will serve as the OIDC provider)
```
dev ➜ /workspace (minimal) $ ./manage.py test

dev ➜ /workspace (minimal) $ ./manage.py runserver 8808
```
and browse to `http://localhost:8808`

### Blob storage

Dev uses [SeaweedFS](https://github.com/seaweedfs/seaweedfs) as an S3-compatible stand-in for production's R2.
The S3 API is at `http://blobstore:9000` inside the compose network (credentials in `docker/seaweedfs/s3.json`),
and the filer UI is at `http://localhost:9002` (buckets live under `/buckets`). The `blobstore-init` service
creates the buckets on startup.

If you previously ran the MinIO-based environment, its data volume (`<project>_blob_data`) is no longer used and
can be removed with `docker volume rm`.
