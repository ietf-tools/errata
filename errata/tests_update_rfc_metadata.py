# Copyright The IETF Trust 2026, All Rights Reserved

from datetime import date
from unittest.mock import MagicMock

from django.test import TestCase

from rpcapi_client.models import (
    Area,
    AreaDirector,
    Group,
    PaginatedRfcMetadataList,
    RelatedDraft,
    ReverseRelatedRfc,
    RfcAuthor,
    RfcMetadata as ApiRfcMetadata,
    RfcStatus,
    Shepherd,
    StreamName,
)

from errata.factories import RfcMetadataFactory
from errata.models import RfcMetadata
from errata.utils import update_rfc_metadata


# ---------------------------------------------------------------------------
# Builder helpers
# ---------------------------------------------------------------------------


def _make_author(name="Alice", *, is_editor=False, email="alice@example.com"):
    return RfcAuthor(titlepage_name=name, is_editor=is_editor, email=email)


def _make_rfc(
    number,
    *,
    title="Test RFC",
    stream_slug="ietf",
    status_name="Informational",
    authors=None,
    area=None,
    ad=None,
    draft=None,
    group_list_email="",
    obsoleted_by=None,
    updated_by=None,
):
    return ApiRfcMetadata(
        number=number,
        title=title,
        published=date(2020, 6, 1),
        status=RfcStatus(slug="inf", name=status_name),
        authors=authors if authors is not None else [_make_author()],
        group=Group(acronym="testgroup", name="Test Group"),
        area=area,
        stream=StreamName(slug=stream_slug, name=stream_slug.upper()),
        ad=ad,
        group_list_email=group_list_email,
        draft=draft,
        obsoleted_by=obsoleted_by if obsoleted_by is not None else [],
        updated_by=updated_by if updated_by is not None else [],
    )


def _make_page(results, *, count=None):
    return PaginatedRfcMetadataList(
        count=count if count is not None else len(results),
        results=results,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class UpdateRfcMetadataTest(TestCase):
    def _run(self, page_or_pages, rfc_numbers=()):
        mock_rpcapi = MagicMock()
        if isinstance(page_or_pages, list):
            mock_rpcapi.red_doc_list.side_effect = page_or_pages
        else:
            mock_rpcapi.red_doc_list.return_value = page_or_pages
        update_rfc_metadata(rfc_numbers=rfc_numbers, rpcapi=mock_rpcapi)
        return mock_rpcapi

    # --- record creation / update ---

    def test_creates_rfc_metadata_record(self):
        self._run(_make_page([_make_rfc(1234, title="Test Protocol")]))
        rfc = RfcMetadata.objects.get(rfc_number=1234)
        self.assertEqual(rfc.title, "Test Protocol")
        self.assertEqual(rfc.std_level, "Informational")
        self.assertEqual(rfc.stream, "ietf")
        self.assertEqual(rfc.publication_year, 2020)
        self.assertEqual(rfc.publication_month, 6)
        self.assertEqual(rfc.group_acronym, "testgroup")
        self.assertEqual(rfc.group_name, "Test Group")

    def test_updates_existing_rfc_metadata(self):
        RfcMetadataFactory(rfc_number=1234, title="Old Title")
        self._run(_make_page([_make_rfc(1234, title="New Title")]))
        self.assertEqual(RfcMetadata.objects.get(rfc_number=1234).title, "New Title")

    # --- authors ---

    def test_author_names_joined_with_comma(self):
        self._run(
            _make_page(
                [
                    _make_rfc(
                        1234,
                        authors=[
                            _make_author("Alice"),
                            _make_author("Bob"),
                        ],
                    )
                ]
            )
        )
        self.assertEqual(
            RfcMetadata.objects.get(rfc_number=1234).author_names, "Alice, Bob"
        )

    def test_editor_author_gets_ed_suffix(self):
        self._run(
            _make_page(
                [
                    _make_rfc(
                        1234,
                        authors=[
                            _make_author("Alice", is_editor=True),
                        ],
                    )
                ]
            )
        )
        self.assertIn(
            "Alice, Ed.", RfcMetadata.objects.get(rfc_number=1234).author_names
        )

    def test_valid_author_email_included(self):
        self._run(
            _make_page(
                [
                    _make_rfc(
                        1234,
                        authors=[
                            _make_author(email="alice@example.com"),
                        ],
                    )
                ]
            )
        )
        self.assertIn(
            "alice@example.com", RfcMetadata.objects.get(rfc_number=1234).author_emails
        )

    def test_none_author_email_excluded(self):
        self._run(
            _make_page(
                [
                    _make_rfc(
                        1234,
                        authors=[
                            RfcAuthor(titlepage_name="Alice", email=None),
                        ],
                    )
                ]
            )
        )
        self.assertEqual(RfcMetadata.objects.get(rfc_number=1234).author_emails, [])

    # --- area ---

    def test_area_acronym_set_when_area_present(self):
        area = Area(acronym="ops", name="Operations")
        self._run(_make_page([_make_rfc(1234, area=area)]))
        self.assertEqual(RfcMetadata.objects.get(rfc_number=1234).area_acronym, "ops")

    def test_area_acronym_empty_when_no_area(self):
        self._run(_make_page([_make_rfc(1234, area=None)]))
        self.assertEqual(RfcMetadata.objects.get(rfc_number=1234).area_acronym, "")

    def test_area_ad_email_included(self):
        area = Area(
            acronym="ops", name="Operations", ads=[AreaDirector(email="ad@example.com")]
        )
        self._run(_make_page([_make_rfc(1234, area=area)]))
        self.assertIn(
            "ad@example.com", RfcMetadata.objects.get(rfc_number=1234).area_ad_emails
        )

    def test_none_area_ad_email_excluded(self):
        area = Area(acronym="ops", name="Operations", ads=[AreaDirector(email=None)])
        self._run(_make_page([_make_rfc(1234, area=area)]))
        self.assertEqual(RfcMetadata.objects.get(rfc_number=1234).area_ad_emails, [])

    def test_area_ad_emails_empty_when_no_ads(self):
        area = Area(acronym="ops", name="Operations", ads=None)
        self._run(_make_page([_make_rfc(1234, area=area)]))
        self.assertEqual(RfcMetadata.objects.get(rfc_number=1234).area_ad_emails, [])

    # --- doc AD ---

    def test_doc_ad_email_set_when_ad_present(self):
        self._run(
            _make_page([_make_rfc(1234, ad=AreaDirector(email="dad@example.com"))])
        )
        self.assertEqual(
            RfcMetadata.objects.get(rfc_number=1234).doc_ad_email, "dad@example.com"
        )

    def test_doc_ad_email_empty_when_no_ad(self):
        self._run(_make_page([_make_rfc(1234, ad=None)]))
        self.assertEqual(RfcMetadata.objects.get(rfc_number=1234).doc_ad_email, "")

    def test_doc_ad_email_empty_when_ad_email_is_none(self):
        self._run(_make_page([_make_rfc(1234, ad=AreaDirector(email=None))]))
        self.assertEqual(RfcMetadata.objects.get(rfc_number=1234).doc_ad_email, "")

    # --- draft ---

    def test_draft_name_set_from_draft(self):
        draft = RelatedDraft(
            id=1, name="draft-test-rfc", title="Test RFC", shepherd=None, ad=None
        )
        self._run(_make_page([_make_rfc(1234, draft=draft)]))
        self.assertEqual(
            RfcMetadata.objects.get(rfc_number=1234).draft_name, "draft-test-rfc"
        )

    def test_draft_name_empty_when_no_draft(self):
        self._run(_make_page([_make_rfc(1234, draft=None)]))
        self.assertEqual(RfcMetadata.objects.get(rfc_number=1234).draft_name, "")

    def test_shepherd_email_set_from_draft(self):
        draft = RelatedDraft(
            id=1,
            name="draft-test-rfc",
            title="Test RFC",
            shepherd=Shepherd(email="shepherd@example.com"),
            ad=None,
        )
        self._run(_make_page([_make_rfc(1234, draft=draft)]))
        self.assertEqual(
            RfcMetadata.objects.get(rfc_number=1234).shepherd_email,
            "shepherd@example.com",
        )

    def test_shepherd_email_empty_when_no_shepherd(self):
        draft = RelatedDraft(
            id=1, name="draft-test-rfc", title="Test RFC", shepherd=None, ad=None
        )
        self._run(_make_page([_make_rfc(1234, draft=draft)]))
        self.assertEqual(RfcMetadata.objects.get(rfc_number=1234).shepherd_email, "")

    # --- related RFCs ---

    def test_obsoleted_by_formatted_and_sorted(self):
        self._run(
            _make_page(
                [
                    _make_rfc(
                        1234,
                        obsoleted_by=[
                            ReverseRelatedRfc(title="Placeholder", id=2, number=9999),
                            ReverseRelatedRfc(title="Placeholder", id=1, number=5678),
                        ],
                    )
                ]
            )
        )
        self.assertEqual(
            RfcMetadata.objects.get(rfc_number=1234).obsoleted_by, "RFC5678, RFC9999"
        )

    def test_updated_by_formatted(self):
        self._run(
            _make_page(
                [
                    _make_rfc(
                        1234,
                        updated_by=[
                            ReverseRelatedRfc(title="Placeholder", id=1, number=5000),
                        ],
                    )
                ]
            )
        )
        self.assertEqual(RfcMetadata.objects.get(rfc_number=1234).updated_by, "RFC5000")

    def test_empty_obsoleted_by_and_updated_by(self):
        self._run(_make_page([_make_rfc(1234, obsoleted_by=[], updated_by=[])]))
        rfc = RfcMetadata.objects.get(rfc_number=1234)
        self.assertEqual(rfc.obsoleted_by, "")
        self.assertEqual(rfc.updated_by, "")

    # --- API call parameters ---

    def test_passes_rfc_number_filter_to_api(self):
        mock = self._run(_make_page([]), rfc_numbers=(1234, 5678))
        call_kwargs = mock.red_doc_list.call_args.kwargs
        self.assertEqual(set(call_kwargs["number"]), {1234, 5678})

    def test_no_number_filter_when_rfc_numbers_empty(self):
        mock = self._run(_make_page([]), rfc_numbers=())
        call_kwargs = mock.red_doc_list.call_args.kwargs
        self.assertNotIn("number", call_kwargs)

    # --- pagination ---

    def test_single_page_makes_one_api_call(self):
        mock = self._run(_make_page([_make_rfc(1234)]))
        self.assertEqual(mock.red_doc_list.call_count, 1)

    def test_pagination_fetches_subsequent_pages(self):
        page1 = _make_page([_make_rfc(1234)], count=2)
        page2 = _make_page([_make_rfc(5678)], count=2)
        mock = self._run([page1, page2])
        self.assertEqual(mock.red_doc_list.call_count, 2)
        self.assertTrue(RfcMetadata.objects.filter(rfc_number=1234).exists())
        self.assertTrue(RfcMetadata.objects.filter(rfc_number=5678).exists())

    def test_second_page_call_includes_offset(self):
        page1 = _make_page([_make_rfc(1234)], count=2)
        page2 = _make_page([_make_rfc(5678)], count=2)
        mock = self._run([page1, page2])
        second_call_kwargs = mock.red_doc_list.call_args_list[1].kwargs
        self.assertEqual(second_call_kwargs["offset"], 1)
