#!/bin/bash -e

if ! ./manage.py migrate --check ; then
    echo "Unapplied migrations found, waiting to start..."
    sleep 5
    while ! ./manage.py migrate --check ; do
        echo "... still waiting for migrations..."
        sleep 5
    done
fi

echo "Starting Errata server..."

# trap TERM and shut down gunicorn
cleanup () {
    if [[ -n "${gunicorn_pid}" ]]; then
        echo "Terminating gunicorn..."
        kill -TERM "${gunicorn_pid}"
        wait "${gunicorn_pid}"
    fi
}

trap 'trap "" TERM; cleanup' TERM

# start gunicorn in the background so we can trap the TERM signal
gunicorn \
    -c /workspace/gunicorn.conf.py \
    --workers "${ERRATA_GUNICORN_WORKERS:-9}" \
    --max-requests "${ERRATA_GUNICORN_MAX_REQUESTS:-0}" \
    --timeout "${ERRATA_GUNICORN_TIMEOUT:-180}" \
    --bind :8000 \
    --log-level "${ERRATA_GUNICORN_LOG_LEVEL:-info}" \
    --capture-output \
    --access-logfile -\
    ${ERRATA_GUNICORN_EXTRA_ARGS} \
    errata_project.wsgi:application &
gunicorn_pid=$!
wait "${gunicorn_pid}"
