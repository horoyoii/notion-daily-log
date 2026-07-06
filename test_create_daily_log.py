import unittest
from unittest.mock import Mock, patch

import requests

from archive_last_week import BlockCopyError as ArchiveBlockCopyError
from archive_last_week import NotionArchiver
from archive_single_page import NotionSinglePageArchiver
from create_daily_log import BlockCopyError, NotionWorkLogCreator


class CleanBlockForCopyTests(unittest.TestCase):
    def setUp(self):
        self.creator = NotionWorkLogCreator(
            api_key="test-token",
            template_page_id="template-page",
            data_source_id="data-source",
        )

    def test_omits_null_paragraph_icon_from_append_payload(self):
        block = {
            "id": "source-block",
            "type": "paragraph",
            "has_children": False,
            "paragraph": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {"content": "daily note", "link": None},
                        "plain_text": "daily note",
                        "href": None,
                    }
                ],
                "color": "default",
                "icon": None,
            },
        }

        cleaned = self.creator.clean_block_for_copy(block)

        self.assertEqual(cleaned["type"], "paragraph")
        self.assertNotIn("icon", cleaned["paragraph"])
        self.assertEqual(
            cleaned["paragraph"]["rich_text"][0]["text"],
            {"content": "daily note"},
        )
        self.assertNotIn("href", cleaned["paragraph"]["rich_text"][0])

    def test_preserves_non_null_paragraph_icon(self):
        block = {
            "id": "source-block",
            "type": "paragraph",
            "has_children": False,
            "paragraph": {
                "rich_text": [],
                "color": "default",
                "icon": {"type": "emoji", "emoji": "L"},
            },
        }

        cleaned = self.creator.clean_block_for_copy(block)

        self.assertEqual(cleaned["paragraph"]["icon"], {"type": "emoji", "emoji": "L"})

    def test_raises_when_notion_rejects_block_append(self):
        class FailingResponse:
            text = '{"object":"error","message":"paragraph.icon should be an object"}'

            def raise_for_status(self):
                error = requests.exceptions.HTTPError("400 Client Error")
                error.response = self
                raise error

        block = {
            "id": "source-block",
            "type": "paragraph",
            "has_children": False,
            "paragraph": {"rich_text": [], "color": "default"},
        }

        with patch("create_daily_log.requests.patch", return_value=FailingResponse()):
            with patch("time.sleep"):
                with self.assertRaises(BlockCopyError):
                    self.creator.copy_blocks_to_page("target-page", [block])

    def test_archives_new_page_when_duplicate_copy_fails(self):
        date_info = {
            "formatted_title": "2026년 4월 21일 (화)",
            "iso_date": "2026-04-21",
        }
        self.creator.create_page_in_database = Mock(return_value="new-page-id")
        self.creator.get_page_blocks = Mock(return_value=[{"id": "block"}])
        self.creator.copy_blocks_to_page = Mock(side_effect=BlockCopyError("copy failed"))
        self.creator.archive_incomplete_page = Mock()

        with self.assertRaises(BlockCopyError):
            self.creator.duplicate_page(date_info)

        self.creator.archive_incomplete_page.assert_called_once_with(
            "new-page-id",
            "2026년 4월 21일 (화)",
        )


class ArchiveCopySafetyTests(unittest.TestCase):
    def setUp(self):
        self.archiver = NotionArchiver(
            api_key="test-token",
            database_id="database",
            archive_page_id="archive-page",
        )
        self.single_archiver = NotionSinglePageArchiver(
            api_key="test-token",
            database_id="database",
            archive_page_id="archive-page",
        )

    def test_archive_cleaners_omit_null_values(self):
        block = {
            "id": "source-block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {"content": "archive note", "link": None},
                        "plain_text": "archive note",
                        "href": None,
                    }
                ],
                "icon": None,
                "color": "default",
            },
        }

        for archiver in [self.archiver, self.single_archiver]:
            cleaned = archiver.clean_block_for_copy(block)
            self.assertNotIn("icon", cleaned["paragraph"])
            self.assertNotIn("href", cleaned["paragraph"]["rich_text"][0])

    def test_archive_copy_raises_when_notion_rejects_block_append(self):
        class FailingResponse:
            text = '{"object":"error","message":"paragraph.icon should be an object"}'

            def raise_for_status(self):
                error = requests.exceptions.HTTPError("400 Client Error")
                error.response = self
                raise error

        block = {
            "id": "source-block",
            "type": "paragraph",
            "has_children": False,
            "paragraph": {"rich_text": [], "color": "default"},
        }

        with patch("archive_last_week.requests.patch", return_value=FailingResponse()):
            with patch("time.sleep"):
                with self.assertRaises(ArchiveBlockCopyError):
                    self.archiver.copy_blocks_to_page("target-page", [block])


if __name__ == "__main__":
    unittest.main()
