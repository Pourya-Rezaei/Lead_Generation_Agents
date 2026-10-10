from unittest.mock import Mock

from src.connectors.apify_linkedin_jobs import ApifyLinkedInJobsConnector
from src.results import RunStatus


def test_linkedin_jobs_maps_company_and_allowlists_job_fields():
    client = Mock()
    client.run_actor.return_value = {"id": "run-1", "status": "SUCCEEDED", "defaultDatasetId": "ds-1"}
    client.dataset_items.return_value = [
        {
            "jobId": "job-7",
            "title": "Software Engineer",
            "companyName": "  Example Labs ",
            "location": "Berlin",
            "companyWebsite": "https://example.com/",
            "jobUrl": "https://linkedin.com/jobs/view/7",
            "description": "private details should remain in raw allowlist only",
            "salary": "$100k",
            "applicantCount": 12,
        }
    ]

    result = ApifyLinkedInJobsConnector("token", client=client).search("software engineer", "Berlin", 5)

    assert result.status is RunStatus.SUCCEEDED
    assert result.leads[0].name == "Example Labs"
    assert result.leads[0].source == "apify_linkedin_jobs"
    assert result.leads[0].source_id == "job-7"
    assert result.leads[0].website == "https://example.com"
    assert "applicantCount" not in result.raw_records[0]
    client.run_actor.assert_called_once_with(
        "dataji~apify-linkdin-jobs",
        {
            "keywords": "software engineer",
            "location": "Berlin",
            "maxResults": 5,
            "scrapeDetails": True,
            "scrapeCompany": False,
        },
        wait_for_finish=60,
    )


def test_linkedin_jobs_discards_missing_company_and_non_successful_runs():
    client = Mock()
    client.run_actor.return_value = {"id": "run-2", "status": "SUCCEEDED", "defaultDatasetId": "ds-2"}
    client.dataset_items.return_value = [{"jobId": "1", "title": "No company"}, {"companyName": "Good Co", "jobUrl": "https://linkedin.com/jobs/view/2"}]
    result = ApifyLinkedInJobsConnector("token", client=client).search("engineer", "Berlin", 5)
    assert len(result.leads) == 1
    assert result.warnings == ["Discarded 1 malformed LinkedIn job result(s)"]

    client.run_actor.return_value = {"id": "run-3", "status": "FAILED", "defaultDatasetId": "ds-3"}
    result = ApifyLinkedInJobsConnector("token", client=client).search("engineer", "Berlin", 5)
    assert result.status is RunStatus.FAILED
    client.dataset_items.assert_called_once()


def test_linkedin_jobs_resumes_persisted_run_without_starting_actor():
    client = Mock()
    client.wait_for_run.return_value = {"id": "persisted-run", "status": "SUCCEEDED", "defaultDatasetId": "ds-4"}
    client.dataset_items.return_value = [{"jobId": "job-4", "title": "Engineer", "companyName": "Example"}]
    result = ApifyLinkedInJobsConnector("token", client=client).search_existing_run("persisted-run", "engineer", 5)
    assert result.run_id == "persisted-run"
    assert len(result.leads) == 1
    client.wait_for_run.assert_called_once_with("persisted-run", timeout=300, poll_interval=2)
    client.run_actor.assert_not_called()
