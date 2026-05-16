from pytest import CaptureFixture

from cognitive_os.__main__ import BOOTSTRAP_MESSAGE, main


def test_bootstrap_logs_message(capsys: CaptureFixture[str]) -> None:
    main()

    captured = capsys.readouterr()

    assert BOOTSTRAP_MESSAGE in captured.out
