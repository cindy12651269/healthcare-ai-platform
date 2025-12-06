from agents.intake_agent import IntakeAgent
from agents.structuring_agent import StructuringAgent
from agents.output_agent import OutputAgent

# Full 3-stage Healthcare AI pipeline: Intake → Structuring → Report Output
class HealthcarePipeline:

    def __init__(self):
        self.intake = IntakeAgent()
        self.struct = StructuringAgent()
        self.output = OutputAgent()

    def run(self, raw_text: str, meta: dict) -> dict:
        # Stage 1: intake
        intake_result = self.intake.run(raw_text, meta)

        # Stage 2: structuring
        struct_result = self.struct.run(intake_result)

        # Stage 3: final report (LLM narrative)
        report = self.output.run(struct_result)

        return {
            "structured": struct_result,
            "report": report
        }
