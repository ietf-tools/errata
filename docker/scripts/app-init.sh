#!/bin/bash

WORKSPACEDIR="/workspace"

# Handle Linux host mounting the workspace dir as root
if [ ! -O "${WORKSPACEDIR}/ietf" ]; then
    sudo chown -R dev:dev $WORKSPACEDIR
fi

# Add /workspace as a safe git directory
git config --global --add safe.directory /workspace

if [ -z "$EDITOR_VSCODE" ]; then
    CODE=0
    if [ -z "$*" ]; then
        echo "-----------------------------------------------------------------"
        echo "Ready!"
        echo "-----------------------------------------------------------------"
        echo
        echo "You can execute arbitrary commands now, e.g.,"
        echo
        echo "    errata/manage.py runserver 8001"
        echo
        echo "to start a development instance of Errata."
        echo
        echo "    errata/manage.py test --settings=settings_test"
        echo
        echo "to run all the python tests."
        echo
        bash
    else
        echo "Executing \"$*\" and stopping container."
        echo
        bash -c "$*"
        CODE=$?
    fi
    exit $CODE
fi