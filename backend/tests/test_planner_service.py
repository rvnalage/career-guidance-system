import asyncio

from app.services import planner_service


def test_plan_agent_response_metadata_and_dependency_integrity(monkeypatch):
	def _mock_router(message, context):
		return "learning_path", "Base learning guidance", "Start with week 1 fundamentals", 0.84, ["roadmap"]

	async def _mock_recalibration(user_id, intents):
		return {intent: 0 for intent in intents}

	async def _noop_async(_state):
		return None

	def _noop_sync(_state):
		return None

	monkeypatch.setattr(planner_service, "get_agent_response_with_confidence", _mock_router)
	monkeypatch.setattr(planner_service, "get_intent_recalibration", _mock_recalibration)
	monkeypatch.setattr(planner_service, "_maybe_load_recommendation_memory", _noop_async)
	monkeypatch.setattr(planner_service, "_maybe_load_profile_memory_tool", _noop_async)
	monkeypatch.setattr(planner_service, "_collect_supporting_notes", _noop_sync)
	monkeypatch.setattr(planner_service, "_maybe_run_recommendation_tool", _noop_async)
	monkeypatch.setattr(planner_service, "_maybe_run_skill_gap_tool", _noop_async)
	monkeypatch.setattr(planner_service, "_maybe_run_interview_tool", _noop_async)
	monkeypatch.setattr(planner_service, "_maybe_run_learning_path_tool", _noop_async)
	monkeypatch.setattr(planner_service, "_maybe_run_networking_tool", _noop_async)
	monkeypatch.setattr(planner_service, "_maybe_run_job_market_tool", _noop_async)

	result = asyncio.run(
		planner_service.plan_agent_response(
			"Create a learning roadmap for data science",
			context={},
			user_id="planner-test-user",
		)
	)

	assert len(result.plan_id) == 16
	assert result.planner_duration_ms >= 0
	assert result.intent == "learning_path"
	assert result.steps

	step_names = {step.name for step in result.steps}
	for step in result.steps:
		for dependency in step.depends_on:
			assert dependency in step_names

	for item in result.outcome_scores:
		score = int(item.get("score", 0))
		assert 0 <= score <= 100


def test_plan_variant_prefers_quick_signal_for_interview(monkeypatch):
	def _mock_router(message, context):
		return "interview_prep", "Interview guidance", "Start daily mock rounds", 0.88, ["interview"]

	async def _mock_recalibration(user_id, intents):
		return {intent: 0 for intent in intents}

	async def _noop_async(_state):
		return None

	def _noop_sync(_state):
		return None

	monkeypatch.setattr(planner_service, "get_agent_response_with_confidence", _mock_router)
	monkeypatch.setattr(planner_service, "get_intent_recalibration", _mock_recalibration)
	monkeypatch.setattr(planner_service, "_maybe_load_recommendation_memory", _noop_async)
	monkeypatch.setattr(planner_service, "_maybe_load_profile_memory_tool", _noop_async)
	monkeypatch.setattr(planner_service, "_collect_supporting_notes", _noop_sync)
	monkeypatch.setattr(planner_service, "_maybe_run_recommendation_tool", _noop_async)
	monkeypatch.setattr(planner_service, "_maybe_run_skill_gap_tool", _noop_async)
	monkeypatch.setattr(planner_service, "_maybe_run_learning_path_tool", _noop_async)
	monkeypatch.setattr(planner_service, "_maybe_run_networking_tool", _noop_async)
	monkeypatch.setattr(planner_service, "_maybe_run_job_market_tool", _noop_async)

	result = asyncio.run(
		planner_service.plan_agent_response(
			"Need a quick interview prep sprint for tomorrow",
			context={},
			user_id="variant-test-user",
		)
	)

	assert result.plan_variant == "interview_prep:A"
	assert isinstance(result.plan_variant_reason, str)
	assert "execution-first" in result.reply.lower()
	assert any(step.name == "plan_variant_selector" for step in result.steps)


def test_select_plan_variant_uses_recalibration_and_plan_id_fallback():
	state = planner_service.PlannerState(message="Need roadmap", context={})
	state.intent_recalibration = {"learning_path": -4}
	label, reason = planner_service._select_plan_variant(state, "learning_path")
	assert label == "B"
	assert "weaker" in reason

	state.intent_recalibration = {"learning_path": 5}
	label, reason = planner_service._select_plan_variant(state, "learning_path")
	assert label == "A"
	assert "strong" in reason

	state.intent_recalibration = {"learning_path": 0}
	state.plan_id = "abc123def456789f"
	label, reason = planner_service._select_plan_variant(state, "learning_path")
	assert label == "B"
	assert "A/B split" in reason


def test_run_tool_safely_records_error_type_and_fallback_detail():
	state = planner_service.PlannerState(message="test", context={})

	async def _boom(_state):
		raise ValueError("boom")

	asyncio.run(
		planner_service._run_tool_safely(
			state,
			step_name="jobs_tool",
			depends_on=["primary_learning_path"],
			runner=_boom,
			failure_detail="Job market fetch failed",
		)
	)

	assert state.steps
	last = state.steps[-1]
	assert last.name == "jobs_tool"
	assert last.error_type == "ValueError"
	assert "Fallback: continued plan" in last.detail
	assert last.depends_on == ["primary_learning_path"]