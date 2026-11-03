# Copyright The IETF Trust 2026, All Rights Reserved

from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from errata_project.context_processors import release_info

COMMIT = "92b88d7a1b2c3d4e5f60718293a4b5c6d7e8f901"


class ReleaseInfoTest(TestCase):
    def setUp(self):
        self.request = RequestFactory().get("/")

    @override_settings(
        RELEASE_VERSION="1.4.2", RELEASE_HASH=COMMIT, RELEASE_BRANCH="main"
    )
    def test_release_links_to_github_release(self):
        context = release_info(self.request)
        self.assertEqual(context["release_version"], "1.4.2")
        self.assertEqual(context["release_label"], "1.4.2 (main - 92b88d7)")
        self.assertEqual(
            context["release_url"],
            "https://github.com/ietf-tools/errata/releases/tag/1.4.2",
        )

    @override_settings(
        RELEASE_VERSION="2.0.0-dev.57", RELEASE_HASH=COMMIT, RELEASE_BRANCH="feat/x"
    )
    def test_dev_build_links_to_commit(self):
        context = release_info(self.request)
        self.assertEqual(context["release_label"], "2.0.0-dev.57 (feat/x - 92b88d7)")
        self.assertEqual(
            context["release_url"],
            f"https://github.com/ietf-tools/errata/commit/{COMMIT}",
        )

    @override_settings(
        RELEASE_VERSION="2.0.0-dev.57", RELEASE_HASH="", RELEASE_BRANCH=""
    )
    def test_dev_build_without_commit_has_no_link(self):
        context = release_info(self.request)
        self.assertEqual(context["release_label"], "2.0.0-dev.57")
        self.assertEqual(context["release_url"], "")

    @override_settings(RELEASE_VERSION="", RELEASE_HASH=COMMIT, RELEASE_BRANCH="main")
    def test_no_version_gives_empty_context(self):
        context = release_info(self.request)
        self.assertEqual(context["release_version"], "")
        self.assertEqual(context["release_label"], "")
        self.assertEqual(context["release_url"], "")


class ReleaseFooterTest(TestCase):
    @override_settings(
        RELEASE_VERSION="1.4.2", RELEASE_HASH=COMMIT, RELEASE_BRANCH="main"
    )
    def test_footer_shows_version(self):
        response = self.client.get(reverse("errata_search"))
        self.assertContains(response, "1.4.2 (main - 92b88d7)")
        self.assertContains(
            response, 'href="https://github.com/ietf-tools/errata/releases/tag/1.4.2"'
        )

    @override_settings(RELEASE_VERSION="", RELEASE_HASH="", RELEASE_BRANCH="")
    def test_footer_omits_version_when_unset(self):
        response = self.client.get(reverse("errata_search"))
        self.assertNotContains(response, "Version ")
        self.assertNotContains(response, "github.com/ietf-tools/errata/releases")
        self.assertNotContains(response, "github.com/ietf-tools/errata/commit")

    @override_settings(RELEASE_VERSION="", RELEASE_HASH="", RELEASE_BRANCH="")
    def test_footer_always_links_status_and_bug_reports(self):
        response = self.client.get(reverse("errata_search"))
        self.assertContains(response, 'href="https://status.ietf.org"')
        self.assertContains(
            response, 'href="https://github.com/ietf-tools/errata/issues"'
        )
