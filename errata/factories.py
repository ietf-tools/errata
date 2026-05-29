# Copyright The IETF Trust 2026, All Rights Reserved

import factory
from django.utils import timezone

from errata_auth.models import User
from errata.models import (
    Erratum,
    ErratumType,
    MailMessage,
    RfcMetadata,
    StagedErratum,
    StagedErratumStatus,
    Status,
)


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@example.com")
    name = factory.LazyAttribute(lambda o: f"Test User {o.username}")
    roles = factory.LazyFunction(list)
    datatracker_subject_id = factory.Sequence(lambda n: f"subject-{n}")


class RpcUserFactory(UserFactory):
    roles = factory.LazyFunction(lambda: [["auth", "rpc"]])


class RfcMetadataFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = RfcMetadata

    rfc_number = factory.Sequence(lambda n: n + 1)
    title = factory.LazyAttribute(lambda o: f"Test RFC {o.rfc_number}")
    draft_name = ""
    author_names = "Test Author"
    author_emails = ""
    shepherd_email = ""
    doc_ad_email = ""
    area_ad_emails = ""
    std_level = "Informational"
    publication_year = 2020
    publication_month = 6
    group_acronym = "testgroup"
    group_name = "Test Group"
    group_list_email = ""
    stream = "ietf"
    area_acronym = factory.LazyAttribute(lambda o: "ops" if o.stream == "ietf" else "")
    area_assignment = ""
    obsoleted_by = ""
    updated_by = ""


class ErratumFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Erratum

    rfc_metadata = factory.SubFactory(RfcMetadataFactory)
    rfc_number = factory.SelfAttribute("rfc_metadata.rfc_number")
    status = factory.LazyFunction(lambda: Status.objects.get(slug="reported"))
    erratum_type = factory.LazyFunction(
        lambda: ErratumType.objects.get(slug="technical")
    )
    section = "1"
    orig_text = "Original text"
    corrected_text = "Corrected text"
    submitter_name = "Test Submitter"
    submitter_email = "submitter@example.com"
    notes = ""
    submitted_at = factory.LazyFunction(timezone.now)


class StagedErratumFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = StagedErratum

    rfc_metadata = factory.SubFactory(RfcMetadataFactory)
    rfc_number = factory.SelfAttribute("rfc_metadata.rfc_number")
    entry_status = StagedErratumStatus.INCOMPLETE
    section = "1"
    orig_text = "Original text"
    corrected_text = "Corrected text"
    submitter_name = "Test Submitter"
    submitter_email = "submitter@example.com"
    notes = "Test notes"


class MailMessageFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = MailMessage

    to = factory.LazyFunction(lambda: ["recipient@example.com"])
    cc = factory.LazyFunction(list)
    subject = factory.Sequence(lambda n: f"Test Subject {n}")
    body = "Test body content"
    sender = factory.SubFactory(UserFactory)
