"""Sequential orchestration of the five BankIQ agents with live progress.

The pipeline runs Intent -> Data Analyst -> Root Cause -> Impact Forecast ->
Executive Report. It is an async generator: it yields an
:class:`AgentProgressEvent` when each agent starts and finishes, and a final
:class:`FinalReport` at the end.

Fault tolerance is first-class. Every agent runs inside a guard that, on
failure, logs the traceback via Rich, emits a ``FAILED`` progress event, and
substitutes a typed *degraded* result so the rest of the pipeline can still
produce partial value. If the report stage itself fails, a degraded report is
synthesized from whatever upstream results exist. The caller therefore always
receives a terminal :class:`FinalReport`, never an unhandled exception.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator

from app.agents.data_analyst_agent import DataAnalystAgent
from app.agents.executive_report_agent import ExecutiveReportAgent
from app.agents.general_assistant_agent import GeneralAssistantAgent
from app.agents.impact_forecast_agent import ImpactForecastAgent
from app.agents.intent_agent import IntentAgent
from app.agents.root_cause_agent import RootCauseAgent
from app.agents.simple_query_agent import SimpleQueryAgent
from app.agents.triage_agent import TriageAgent
from app.constants import (
    ORDERED_AGENT_NAMES,
    OUT_OF_SCOPE_DECLINE_MESSAGE,
    REJECTION_MESSAGE,
    SERVICE_UNAVAILABLE_MESSAGE,
)
from app.core.logging import get_logger
from app.models.analysis import AnalysisResult
from app.models.events import AgentProgressEvent, AgentStatus
from app.models.impact import ImpactResult
from app.models.intent import ParsedIntent
from app.models.investigation import FinalReport, InvestigationContext
from app.models.report import ExecutiveReport, ReportSection
from app.models.root_cause import RootCauseResult
from app.models.triage import DirectAnswer, QuestionCategory
from app.services.dataset_repository import DatasetRepository
from app.services.llm_client import GroqLlmClient

_logger = get_logger("pipeline")

_TOTAL_STEPS: int = len(ORDERED_AGENT_NAMES)

# Yielded items are either a progress event or the terminal report.
PipelineYield = AgentProgressEvent | FinalReport


class InvestigationPipeline:
    """Runs the five-agent investigation and streams progress events."""

    def __init__(
        self,
        llm_client: GroqLlmClient,
        dataset_repository: DatasetRepository,
    ) -> None:
        """Initialize the pipeline and its (stateless) agents.

        Args:
            llm_client: The shared Groq LLM client.
            dataset_repository: The shared dataset repository.
        """
        self._dataset_repository = dataset_repository
        self._triage_agent = TriageAgent(llm_client)
        self._intent_agent = IntentAgent(llm_client)
        self._data_analyst_agent = DataAnalystAgent(llm_client, dataset_repository)
        self._root_cause_agent = RootCauseAgent(llm_client, dataset_repository)
        self._impact_forecast_agent = ImpactForecastAgent(llm_client, dataset_repository)
        self._executive_report_agent = ExecutiveReportAgent(llm_client)
        self._simple_query_agent = SimpleQueryAgent(llm_client, dataset_repository)
        self._general_assistant_agent = GeneralAssistantAgent(llm_client)

    async def run(self, question: str) -> AsyncIterator[PipelineYield]:
        """Triage the question, then dispatch to the matching handling path.

        A lightweight triage step runs first and classifies the question. Only
        genuine KPI investigations run the full five-agent pipeline; simple
        lookups and general questions take cheaper paths, and guardrail
        violations are refused outright. Every path ends with exactly one
        terminal :class:`FinalReport`, so the SSE contract is unchanged.

        Args:
            question: The user's natural-language question.

        Yields:
            :class:`AgentProgressEvent` items followed by one :class:`FinalReport`.
        """
        async for event in self._announce_start(
            self._triage_agent, step_index=0, total_steps=1
        ):
            yield event
        triage_started_at = time.perf_counter()
        try:
            decision = await self._triage_agent.run(question)
            yield self._completed(
                self._triage_agent, 0, triage_started_at,
                f"Routing: {decision.category.value}", total_steps=1,
            )
        except Exception as error:
            # If triage itself can't run, the language model is unavailable
            # (rate limit, exhausted quota, or misconfigured) — so the five
            # investigation agents would all fail the same way. Rather than fan
            # out to five more doomed LLM calls, return one honest "temporarily
            # unavailable" report and ask the user to retry.
            yield self._failed(self._triage_agent, 0, triage_started_at, error, total_steps=1)
            async for item in self._run_unavailable(question):
                yield item
            return

        if decision.category is QuestionCategory.REJECTED:
            async for item in self._run_rejection(question):
                yield item
        elif decision.category is QuestionCategory.SIMPLE_QUERY:
            async for item in self._run_simple_query(question):
                yield item
        elif decision.category is QuestionCategory.OUT_OF_SCOPE:
            async for item in self._run_general_answer(question):
                yield item
        else:
            async for item in self._run_investigation(question):
                yield item

    async def _run_investigation(self, question: str) -> AsyncIterator[PipelineYield]:
        """Execute the full five-agent pipeline for a KPI investigation.

        Args:
            question: The user's natural-language banking question.

        Yields:
            :class:`AgentProgressEvent` items as agents start/finish, followed by
            exactly one terminal :class:`FinalReport`.
        """
        pipeline_started_at = time.perf_counter()
        context = InvestigationContext(question=question)
        any_stage_degraded = False

        # --- Step 1: Intent ------------------------------------------------
        async for event in self._announce_start(self._intent_agent, step_index=0):
            yield event
        intent_started_at = time.perf_counter()
        try:
            context.parsed_intent = await self._intent_agent.run(question)
            yield self._completed(self._intent_agent, 0, intent_started_at,
                                  f"Identified KPI: {context.parsed_intent.primary_kpi}")
        except Exception as error:
            any_stage_degraded = True
            context.parsed_intent = self._build_fallback_intent(question)
            yield self._failed(self._intent_agent, 0, intent_started_at, error)

        # --- Step 2: Data Analyst -----------------------------------------
        async for event in self._announce_start(self._data_analyst_agent, step_index=1):
            yield event
        analyst_started_at = time.perf_counter()
        try:
            context.analysis_result = await self._data_analyst_agent.run(
                context.parsed_intent
            )
            yield self._completed(
                self._data_analyst_agent, 1, analyst_started_at,
                f"Flagged {len(context.analysis_result.flagged_anomalies)} anomalies",
            )
        except Exception as error:
            any_stage_degraded = True
            context.analysis_result = AnalysisResult(degraded=True)
            yield self._failed(self._data_analyst_agent, 1, analyst_started_at, error)

        # --- Step 3: Root Cause -------------------------------------------
        async for event in self._announce_start(self._root_cause_agent, step_index=2):
            yield event
        root_cause_started_at = time.perf_counter()
        try:
            context.root_cause_result = await self._root_cause_agent.run(
                context.parsed_intent, context.analysis_result
            )
            yield self._completed(
                self._root_cause_agent, 2, root_cause_started_at,
                "Causal chain assembled",
            )
        except Exception as error:
            any_stage_degraded = True
            context.root_cause_result = RootCauseResult(degraded=True)
            yield self._failed(self._root_cause_agent, 2, root_cause_started_at, error)

        # --- Step 4: Impact Forecast --------------------------------------
        async for event in self._announce_start(self._impact_forecast_agent, step_index=3):
            yield event
        impact_started_at = time.perf_counter()
        try:
            context.impact_result = await self._impact_forecast_agent.run(
                context.parsed_intent, context.root_cause_result
            )
            scenario = context.impact_result.scenario_type
            headline = context.impact_result.headline_total_exposure_cr
            label = "Value captured" if scenario == "opportunity" else "Exposure"
            yield self._completed(
                self._impact_forecast_agent, 3, impact_started_at,
                f"{label}: ₹{headline:.2f} Cr",
            )
        except Exception as error:
            any_stage_degraded = True
            context.impact_result = ImpactResult(degraded=True)
            yield self._failed(self._impact_forecast_agent, 3, impact_started_at, error)

        # --- Step 5: Executive Report -------------------------------------
        async for event in self._announce_start(self._executive_report_agent, step_index=4):
            yield event
        report_started_at = time.perf_counter()
        try:
            report = await self._executive_report_agent.run(context)
            yield self._completed(
                self._executive_report_agent, 4, report_started_at,
                "Executive report ready",
            )
        except Exception as error:
            any_stage_degraded = True
            report = self._build_degraded_report(context)
            yield self._failed(self._executive_report_agent, 4, report_started_at, error)

        if any_stage_degraded and report.degraded_notice is None:
            report.degraded_notice = (
                "This report was produced in degraded mode because one or more "
                "analysis stages could not complete. Findings may be partial."
            )

        duration_ms = (time.perf_counter() - pipeline_started_at) * 1000.0
        _logger.info("Pipeline finished in %.0f ms (degraded=%s)", duration_ms, any_stage_degraded)
        yield FinalReport(
            question=question,
            report=report,
            parsed_intent=context.parsed_intent,
            analysis_result=context.analysis_result,
            root_cause_result=context.root_cause_result,
            impact_result=context.impact_result,
            degraded=any_stage_degraded,
            duration_ms=duration_ms,
        )

    # -- lightweight (non-investigation) paths ------------------------------

    async def _run_simple_query(self, question: str) -> AsyncIterator[PipelineYield]:
        """Answer a factual lookup without the root-cause/impact/report stages.

        Reuses the intent agent to scope the data slice, then answers directly
        from that slice in a single LLM call.

        Args:
            question: The user's factual question.

        Yields:
            Progress events followed by one terminal :class:`FinalReport`.
        """
        path_started_at = time.perf_counter()

        async for event in self._announce_start(
            self._intent_agent, step_index=0, total_steps=2
        ):
            yield event
        intent_started_at = time.perf_counter()
        try:
            parsed_intent = await self._intent_agent.run(question)
            yield self._completed(
                self._intent_agent, 0, intent_started_at,
                f"Scoped to: {parsed_intent.primary_kpi}", total_steps=2,
            )
        except Exception as error:
            parsed_intent = self._build_fallback_intent(question)
            yield self._failed(
                self._intent_agent, 0, intent_started_at, error, total_steps=2
            )

        async for event in self._announce_start(
            self._simple_query_agent, step_index=1, total_steps=2
        ):
            yield event
        answer_started_at = time.perf_counter()
        degraded = False
        try:
            answer = await self._simple_query_agent.run(question, parsed_intent)
            yield self._completed(
                self._simple_query_agent, 1, answer_started_at,
                "Answer ready", total_steps=2,
            )
        except Exception as error:
            degraded = True
            answer = DirectAnswer(
                answer=(
                    "BankIQ could not retrieve the data to answer this question. "
                    "Verify the datasets are generated and the GROQ_API_KEY is set, "
                    "then retry."
                ),
                headline="Quick answer unavailable",
                degraded=True,
            )
            yield self._failed(
                self._simple_query_agent, 1, answer_started_at, error, total_steps=2
            )

        yield self._build_direct_final_report(
            question, answer, "BankIQ Quick Answer", path_started_at, degraded=degraded
        )

    async def _run_general_answer(self, question: str) -> AsyncIterator[PipelineYield]:
        """Answer a general banking/finance question, or decline if off-topic.

        Args:
            question: The user's general question.

        Yields:
            Progress events followed by one terminal :class:`FinalReport`.
        """
        path_started_at = time.perf_counter()

        async for event in self._announce_start(
            self._general_assistant_agent, step_index=0, total_steps=1
        ):
            yield event
        answer_started_at = time.perf_counter()
        degraded = False
        try:
            answer = await self._general_assistant_agent.run(question)
            yield self._completed(
                self._general_assistant_agent, 0, answer_started_at,
                "Answer ready", total_steps=1,
            )
        except Exception as error:
            degraded = True
            answer = DirectAnswer(
                answer=OUT_OF_SCOPE_DECLINE_MESSAGE,
                headline="Assistant unavailable",
                degraded=True,
            )
            yield self._failed(
                self._general_assistant_agent, 0, answer_started_at, error, total_steps=1
            )

        yield self._build_direct_final_report(
            question, answer, "BankIQ Assistant", path_started_at, degraded=degraded
        )

    async def _run_rejection(self, question: str) -> AsyncIterator[PipelineYield]:
        """Refuse a guardrail-violating request with a fixed message.

        No further agents or LLM calls run; the refusal text is a fixed server
        constant so a crafted prompt cannot coax a harmful or leaky reply.

        Args:
            question: The original (rejected) user message.

        Yields:
            A single terminal :class:`FinalReport` carrying the refusal.
        """
        started_at = time.perf_counter()
        _logger.info("Request rejected by guardrails: %r", question)
        report = ExecutiveReport(
            title="Request Declined",
            executive_summary=REJECTION_MESSAGE,
            what_happened=ReportSection(heading="What Happened", body=""),
            triggering_event=ReportSection(heading="Triggering Event", body=""),
            why_it_happened=ReportSection(heading="Why It Happened", body=""),
            financial_impact=ReportSection(heading="Financial Impact", body=""),
            recommended_actions=[],
            confidence_statement="",
        )
        yield FinalReport(
            question=question,
            report=report,
            degraded=False,
            duration_ms=(time.perf_counter() - started_at) * 1000.0,
        )

    async def _run_unavailable(self, question: str) -> AsyncIterator[PipelineYield]:
        """Return one degraded report when the LLM is unavailable for triage.

        Used as the fail-soft path when the triage step raises (rate limit,
        quota exhausted, or misconfiguration). No further agents run, so a single
        failed question costs at most one LLM call instead of six.

        Args:
            question: The original user question.

        Yields:
            A single terminal :class:`FinalReport` carrying the retry message.
        """
        started_at = time.perf_counter()
        answer = DirectAnswer(
            answer=SERVICE_UNAVAILABLE_MESSAGE,
            headline="BankIQ is temporarily unavailable",
            degraded=True,
        )
        yield self._build_direct_final_report(
            question, answer, "BankIQ Temporarily Unavailable", started_at, degraded=True
        )

    @staticmethod
    def _build_minimal_report(title: str, answer: DirectAnswer) -> ExecutiveReport:
        """Wrap a direct answer in a minimal, well-formed executive report.

        Args:
            title: The report title for this lightweight path.
            answer: The direct answer to surface.

        Returns:
            An :class:`ExecutiveReport` carrying the answer in the summary only.
            The analytical sections are left empty so the UI, which hides empty
            sections, renders just the answer — not a skeleton of bare headings.
        """
        notice = (
            "This answer was produced in degraded mode; some data may be unavailable."
            if answer.degraded
            else None
        )
        return ExecutiveReport(
            title=title,
            executive_summary=answer.answer,
            what_happened=ReportSection(heading="What Happened", body=""),
            triggering_event=ReportSection(heading="Triggering Event", body=""),
            why_it_happened=ReportSection(heading="Why It Happened", body=""),
            financial_impact=ReportSection(heading="Financial Impact", body=""),
            recommended_actions=[],
            confidence_statement="",
            degraded_notice=notice,
        )

    def _build_direct_final_report(
        self,
        question: str,
        answer: DirectAnswer,
        title: str,
        started_at: float,
        *,
        degraded: bool,
    ) -> FinalReport:
        """Assemble the terminal report for a lightweight path.

        Args:
            question: The original user question.
            answer: The direct answer produced by the path.
            title: The report title for this path.
            started_at: ``time.perf_counter`` captured when the path began.
            degraded: Whether the path fell back to a degraded answer.

        Returns:
            The terminal :class:`FinalReport`.
        """
        duration_ms = (time.perf_counter() - started_at) * 1000.0
        _logger.info(
            "Direct-answer path finished in %.0f ms (degraded=%s)", duration_ms, degraded
        )
        return FinalReport(
            question=question,
            report=self._build_minimal_report(title, answer),
            degraded=degraded,
            duration_ms=duration_ms,
        )

    # -- progress event helpers --------------------------------------------

    async def _announce_start(
        self, agent: object, *, step_index: int, total_steps: int = _TOTAL_STEPS
    ) -> AsyncIterator[AgentProgressEvent]:
        """Yield a RUNNING progress event for an agent about to execute.

        Args:
            agent: The agent that is starting (must expose name/display_name).
            step_index: Zero-based pipeline position of the agent.
            total_steps: Total steps in the path the agent belongs to.

        Yields:
            A single RUNNING :class:`AgentProgressEvent`.
        """
        agent_name = agent.agent_name
        display_name = agent.display_name
        _logger.info("[%s] started", agent_name)
        yield AgentProgressEvent(
            agent_name=agent_name,
            display_name=display_name,
            status=AgentStatus.RUNNING,
            message=f"{display_name} is working...",
            step_index=step_index,
            total_steps=total_steps,
        )

    def _completed(
        self,
        agent: object,
        step_index: int,
        started_at: float,
        message: str,
        *,
        total_steps: int = _TOTAL_STEPS,
    ) -> AgentProgressEvent:
        """Build a COMPLETED progress event with elapsed timing.

        Args:
            agent: The agent that finished.
            step_index: Zero-based pipeline position of the agent.
            started_at: ``time.perf_counter`` value captured before the agent ran.
            message: Short user-facing completion message.
            total_steps: Total steps in the path the agent belongs to.

        Returns:
            A COMPLETED :class:`AgentProgressEvent`.
        """
        elapsed_ms = (time.perf_counter() - started_at) * 1000.0
        return AgentProgressEvent(
            agent_name=agent.agent_name,
            display_name=agent.display_name,
            status=AgentStatus.COMPLETED,
            message=message,
            step_index=step_index,
            total_steps=total_steps,
            elapsed_ms=elapsed_ms,
        )

    def _failed(
        self,
        agent: object,
        step_index: int,
        started_at: float,
        error: Exception,
        *,
        total_steps: int = _TOTAL_STEPS,
    ) -> AgentProgressEvent:
        """Build a FAILED progress event and log the underlying error.

        Args:
            agent: The agent that failed.
            step_index: Zero-based pipeline position of the agent.
            started_at: ``time.perf_counter`` value captured before the agent ran.
            error: The exception raised by the agent.
            total_steps: Total steps in the path the agent belongs to.

        Returns:
            A FAILED :class:`AgentProgressEvent`.
        """
        elapsed_ms = (time.perf_counter() - started_at) * 1000.0
        agent_name = agent.agent_name
        display_name = agent.display_name
        _logger.exception("[%s] failed: %s", agent_name, error)
        return AgentProgressEvent(
            agent_name=agent_name,
            display_name=display_name,
            status=AgentStatus.FAILED,
            message=f"{display_name} failed; continuing in degraded mode.",
            step_index=step_index,
            total_steps=total_steps,
            elapsed_ms=elapsed_ms,
        )

    # -- degraded fallbacks -------------------------------------------------

    @staticmethod
    def _build_fallback_intent(question: str) -> ParsedIntent:
        """Construct a best-effort intent when the intent agent is unavailable.

        Uses simple keyword detection so degraded analysis still has a scope.

        Args:
            question: The original user question.

        Returns:
            A :class:`ParsedIntent` populated heuristically from the question.
        """
        from app.constants import ALL_DATASET_NAMES, ALL_PRODUCT_TYPES, ALL_ZONES

        lowered = question.lower()
        # Match the longest zone name first so "Northwest"/"Southeast" win over
        # their "North"/"South" prefixes.
        detected_zone = next(
            (
                zone
                for zone in sorted(ALL_ZONES, key=len, reverse=True)
                if zone.lower() in lowered
            ),
            None,
        )
        detected_product = next(
            (product for product in ALL_PRODUCT_TYPES if product.lower() in lowered), None
        )
        return ParsedIntent(
            primary_kpi="loan approval rate",
            focus_zone=detected_zone,
            focus_quarter="Q3 2025",
            comparison_quarter="Q2 2025",
            focus_product=detected_product,
            target_datasets=list(ALL_DATASET_NAMES),
            normalized_question=question.strip(),
            interpretation_notes="Heuristic fallback intent (intent agent unavailable).",
        )

    @staticmethod
    def _build_degraded_report(context: InvestigationContext) -> ExecutiveReport:
        """Synthesize a degraded report from whatever upstream results exist.

        Args:
            context: The investigation context, possibly partially populated.

        Returns:
            A minimal but well-formed :class:`ExecutiveReport`.
        """
        root_cause_text = (
            context.root_cause_result.primary_root_cause
            if context.root_cause_result and context.root_cause_result.primary_root_cause
            else "Root cause could not be determined automatically."
        )
        if context.impact_result and context.impact_result.headline_total_exposure_cr:
            _scenario = context.impact_result.scenario_type
            _label = "value captured" if _scenario == "opportunity" else "estimated exposure"
            exposure_text = f"₹{context.impact_result.headline_total_exposure_cr:.2f} Cr {_label}."
        else:
            exposure_text = "Financial impact could not be quantified."
        analysis_text = (
            context.analysis_result.overall_summary
            if context.analysis_result and context.analysis_result.overall_summary
            else "Detailed analysis was unavailable."
        )
        return ExecutiveReport(
            title="BankIQ Investigation (Degraded)",
            executive_summary=(
                "The investigation completed in degraded mode. "
                f"{root_cause_text} {exposure_text}"
            ),
            what_happened=ReportSection(heading="What Happened", body=analysis_text),
            triggering_event=ReportSection(
                heading="Triggering Event",
                body="The triggering event could not be confirmed in degraded mode.",
            ),
            why_it_happened=ReportSection(heading="Why It Happened", body=root_cause_text),
            financial_impact=ReportSection(heading="Financial Impact", body=exposure_text),
            recommended_actions=[],
            confidence_statement="Low confidence: produced from partial results.",
            degraded_notice=(
                "BankIQ could not fully complete this investigation. Verify the "
                "GROQ_API_KEY is configured and the datasets are generated, then retry."
            ),
        )
