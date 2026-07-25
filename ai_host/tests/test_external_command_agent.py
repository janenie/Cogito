import asyncio
import json

from ai_host.agents.external_command import ExternalCommandAgent
from ai_host.attempt_state import AttemptContext, ReflectionMemory
from ai_host.config import HostConfig


def test_external_command_agent_reads_report(tmp_path):
    script = tmp_path / "agent.py"
    script.write_text(
        "import json,sys\n"
        "report=sys.argv[1]\n"
        "json.dump({"
        "'attempt_id':1,"
        "'outcome':'failure',"
        "'reason':'cleanup_incomplete',"
        "'summary':'submitted too early',"
        "'mistakes':['did not check HUD'],"
        "'next_strategy':['check HUD before finishing']"
        "}, open(report, 'w'))\n"
    )
    config = HostConfig(
        adapter="external-command",
        agent_command=f"python3 {script} {{report_file}}",
        run_dir=tmp_path,
    )
    context = AttemptContext(
        attempt_id=1,
        max_attempts=3,
        scenario_id="daily_routine_cleanup",
        run_dir=tmp_path,
        reflection=ReflectionMemory(),
    )

    result = asyncio.run(ExternalCommandAgent(config).run_attempt(context, None))

    assert result.outcome == "failure"
    assert result.reason == "cleanup_incomplete"
    assert result.next_strategy == ["check HUD before finishing"]


def test_external_command_agent_returns_unknown_without_valid_report(tmp_path):
    config = HostConfig(
        adapter="external-command",
        agent_command="python3 -c 'pass'",
        run_dir=tmp_path,
    )
    context = AttemptContext(
        attempt_id=1,
        max_attempts=3,
        scenario_id="daily_routine_cleanup",
        run_dir=tmp_path,
        reflection=ReflectionMemory(),
    )

    result = asyncio.run(ExternalCommandAgent(config).run_attempt(context, None))

    assert result.outcome == "unknown"
    assert result.reason == "missing_report"
