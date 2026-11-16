"""Tests for the dedicated JUnit XML report generator."""

from xml.etree import ElementTree as ET

from promptdrift.models import RegressionReport, TestRun
from promptdrift.models.result import EvaluationResult
from promptdrift.reports.junit import write_junit_report


def make_report(tests, duration_ms=456):
    return RegressionReport(
        provider="mock",
        model="test-model",
        tests=tests,
        duration_ms=duration_ms,
    )


def make_test_run(
    test_id="test_example",
    status="PASS",
    latency_ms=123,
    evaluations=None,
):
    return TestRun(
        test_id=test_id,
        provider="mock",
        model="test-model",
        input="test input",
        output="test output",
        latency_ms=latency_ms,
        status=status,
        evaluations=evaluations or [],
    )


class TestJUnitReport:
    def test_creates_xml_file_and_parent_directories(self, tmp_path):
        path = tmp_path / "reports" / "ci" / "results.xml"

        report = make_report([make_test_run()])

        write_junit_report(report, path)

        assert path.is_file()
        assert path.parent.is_dir()

        root = ET.parse(path).getroot()
        assert root.tag == "testsuites"

    def test_generates_correct_test_counts_and_names(self, tmp_path):
        path = tmp_path / "results.xml"

        failure = EvaluationResult(
            passed=False,
            assertion="contains",
            expected="30 days",
            actual="7 days",
            reason="Required text does not appear in the output.",
            severity="fail",
        )

        report = make_report(
            [
                make_test_run("refund-policy", "FAIL", evaluations=[failure]),
                make_test_run("tone-check"),
                make_test_run("length-guard"),
            ]
        )

        write_junit_report(report, path)

        root = ET.parse(path).getroot()
        suite = root.find("testsuite")

        assert suite is not None
        assert root.attrib["tests"] == "3"
        assert root.attrib["failures"] == "1"
        assert suite.attrib["tests"] == "3"
        assert suite.attrib["failures"] == "1"

        testcases = suite.findall("testcase")
        assert len(testcases) == 3

        names = [testcase.attrib["name"] for testcase in testcases]
        assert names == ["refund-policy", "tone-check", "length-guard"]

    def test_failed_test_contains_first_failed_assertion(self, tmp_path):
        path = tmp_path / "results.xml"

        first_failure = EvaluationResult(
            passed=False,
            assertion="contains",
            expected="30 days",
            actual="7 days",
            reason="Refund period is incorrect.",
            severity="fail",
        )

        second_failure = EvaluationResult(
            passed=False,
            assertion="equals",
            expected="success",
            actual="failure",
            reason="Unexpected result.",
            severity="fail",
        )

        report = make_report(
            [
                make_test_run(
                    "refund-policy",
                    status="FAIL",
                    evaluations=[first_failure, second_failure],
                )
            ]
        )

        write_junit_report(report, path)

        root = ET.parse(path).getroot()
        testcase = root.find("./testsuite/testcase")

        assert testcase is not None

        failure = testcase.find("failure")
        assert failure is not None

        assert failure.attrib["message"] == "Refund period is incorrect."
        assert "contains" in failure.text
        assert "30 days" in failure.text

        # Only the first failed assertion should be included.
        assert len(testcase.findall("failure")) == 1

    def test_passing_and_warning_tests_have_no_failure_element(self, tmp_path):
        path = tmp_path / "results.xml"

        warning = EvaluationResult(
            passed=False,
            assertion="contains",
            expected="optional phrase",
            actual="different output",
            reason="Optional phrase was not found.",
            severity="warn",
        )

        report = make_report(
            [
                make_test_run("passing-test", status="PASS"),
                make_test_run(
                    "warning-test",
                    status="WARN",
                    evaluations=[warning],
                ),
            ]
        )

        write_junit_report(report, path)

        root = ET.parse(path).getroot()
        suite = root.find("testsuite")

        assert suite is not None

        for testcase in suite.findall("testcase"):
            assert testcase.find("failure") is None

        assert suite.attrib["failures"] == "0"

    def test_execution_time_is_reported_in_seconds(self, tmp_path):
        path = tmp_path / "results.xml"

        report = make_report(
            [
                make_test_run("test-one", latency_ms=123),
                make_test_run("test-two", latency_ms=333),
            ],
            duration_ms=456,
        )

        write_junit_report(report, path)

        root = ET.parse(path).getroot()
        suite = root.find("testsuite")

        assert suite is not None
        assert root.attrib["time"] == "0.456"

        testcases = suite.findall("testcase")

        assert testcases[0].attrib["time"] == "0.123"
        assert testcases[1].attrib["time"] == "0.333"
