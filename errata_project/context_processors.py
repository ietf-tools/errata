# Copyright The IETF Trust 2026, All Rights Reserved

from django.conf import settings

REPOSITORY_URL = "https://github.com/ietf-tools/errata"


def release_info(request):
    """Add the running release's version, branch and commit to the context

    The label reads like "1.4.2 (main - 92b88d7)". Release versions link to
    their GitHub release. Development builds (versions containing "-dev")
    have no release, so link to the commit.
    """
    version = settings.RELEASE_VERSION
    commit = settings.RELEASE_HASH
    branch = settings.RELEASE_BRANCH
    if not version:
        return {"release_version": "", "release_label": "", "release_url": ""}

    details = " - ".join(part for part in (branch, commit[:7]) if part)
    label = f"{version} ({details})" if details else version
    if "-dev" not in version:
        url = f"{REPOSITORY_URL}/releases/tag/{version}"
    elif commit:
        url = f"{REPOSITORY_URL}/commit/{commit}"
    else:
        url = ""
    return {"release_version": version, "release_label": label, "release_url": url}
